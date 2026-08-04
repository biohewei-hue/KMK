"""同花顺行情数据：指数/个股K线、资金流排行、涨停与炸板池。

替代东方财富作为主数据源（东财保留为兜底，见 run_daily.py）。

⚠️ 同花顺接口未在开发环境验证过（无外网），字段与参数以实跑为准。
抓取失败时会保留诊断信息；若某接口长期失败，用 HAR 导入重新接线：
  F12 → 打开对应页面 → Save all as HAR → python tools/import_har.py x.har --save ths
"""

import json
import re
import time

from ..curl_import import get_endpoint
from ..http import get_json, make_session

KLINE_URL = "https://d.10jqka.com.cn/v6/line/{code}/01/last1800.js"

# 同花顺资金流（HTML 表格）。5日榜的路径参数不确定，按候选依次尝试。
FUND_URLS = {
    "concept": [
        "https://data.10jqka.com.cn/funds/gnzjl/field/tradezdf/order/desc/page/1/ajax/1/free/1/",
        "https://data.10jqka.com.cn/funds/gnzjl/board/2/field/tradezdf/order/desc/page/1/ajax/1/",
    ],
    "industry": [
        "https://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/page/1/ajax/1/free/1/",
        "https://data.10jqka.com.cn/funds/hyzjl/board/2/field/tradezdf/order/desc/page/1/ajax/1/",
    ],
    "stock": [
        "https://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/page/1/ajax/1/free/1/",
    ],
}

LIMIT_UP_URL = "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
OPEN_LIMIT_URL = "https://data.10jqka.com.cn/dataapi/limit_up/open_limit_up_pool"

_HEADERS = {
    "Referer": "https://data.10jqka.com.cn/",
    "X-Requested-With": "XMLHttpRequest",
}


def _session(creds: dict | None = None):
    cookie = ((creds or {}).get("ths") or {}).get("cookie", "")
    return make_session(cookie=cookie, headers=dict(_HEADERS))


# ---------------------------------------------------------------- K线

def fetch_kline(ths_code: str, days: int = 250) -> list[dict]:
    """同花顺K线。ths_code 形如 zs_1A0001（指数）/ hs_600519（个股）。

    响应是 JSONP：quotebridge_v6_line_xxx({...})，data 字段为
    "日期,开,高,低,收,量,额;日期,..." 的分号分隔串。
    """
    s = _session()
    s.headers["Referer"] = "https://stockpage.10jqka.com.cn/"
    r = s.get(KLINE_URL.format(code=ths_code), timeout=20)
    r.raise_for_status()
    text = r.text.strip()
    m = re.search(r"\((\{.*\})\)\s*;?\s*$", text, re.S)
    if not m:
        raise RuntimeError(f"K线响应格式异常（前80字符）：{text[:80]}")
    payload = json.loads(m.group(1))
    raw = payload.get("data") or ""
    out = []
    for rec in raw.split(";"):
        p = rec.split(",")
        if len(p) < 7:
            continue
        try:
            out.append({
                "date": f"{p[0][:4]}-{p[0][4:6]}-{p[0][6:8]}",
                "open": float(p[1]), "high": float(p[2]), "low": float(p[3]),
                "close": float(p[4]), "volume": float(p[5]), "amount": float(p[6]),
            })
        except ValueError:
            continue
    return out[-days:]


# ---------------------------------------------------------------- 资金流

_TAG_RE = re.compile(r"<[^>]+>")
_NUM_RE = re.compile(r"-?[\d.]+")


def _parse_fund_table(html: str, top_n: int) -> list[dict]:
    """解析同花顺资金流 HTML 表格。表头列序可能变动，按『名称+亿』特征提取。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for row in rows:
        cells = [_TAG_RE.sub("", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c.replace("&nbsp;", " ").strip() for c in cells if c.strip()]
        if len(cells) < 4:
            continue
        # 名称：第一个含中文且不含数字单位的单元格
        name = next((c for c in cells if re.search(r"[一-龥]", c)
                     and not c.endswith(("%", "亿", "万"))), "")
        if not name or name in ("序号", "板块", "行业"):
            continue
        # 净流入：带"亿"的数值，或最大的数值列
        net = None
        for c in cells:
            if "亿" in c:
                mm = _NUM_RE.search(c)
                if mm:
                    net = float(mm.group())
                    break
        pct = None
        for c in cells:
            if c.endswith("%"):
                mm = _NUM_RE.search(c)
                if mm:
                    pct = float(mm.group())
                    break
        if net is None:
            continue
        out.append({"name": name, "main_net_5d_yi": net, "pct_chg_5d": pct})
        if len(out) >= top_n:
            break
    return out


def fetch_fundflow(kind: str, top_n: int = 20, creds: dict | None = None) -> tuple[list[dict], str]:
    """返回 (榜单, 诊断信息)。kind: concept/industry/stock"""
    s = _session(creds)
    spec = get_endpoint("ths", f"fund_{kind}")  # HAR 导入的端点优先
    urls = [spec["url"]] if spec else FUND_URLS.get(kind, [])
    notes = []
    for url in urls:
        try:
            r = s.get(url, timeout=20, params=(spec or {}).get("params") or {})
            r.raise_for_status()
            rows = _parse_fund_table(r.text, top_n)
            notes.append(f"{url[-40:]} → {len(rows)}行")
            if rows:
                return rows, "；".join(notes)
        except Exception as e:  # noqa: BLE001
            notes.append(f"{url[-40:]} → {str(e)[:60]}")
    return [], "；".join(notes) or "无可用URL"


# ---------------------------------------------------------------- 涨停/炸板

def _limit_pool(s, url: str, date_str: str) -> list[dict]:
    params = {
        "page": "1", "limit": "200", "date": date_str.replace("-", ""),
        "field": "199112,10,9001,330329,330325,9002,330329,133,1000",
        "filter": "HS,GEM2STAR", "order_field": "330329", "order_type": "0", "_": int(time.time() * 1000),
    }
    data = get_json(s, url, retries=1, params=params)
    return ((data.get("data") or {}).get("info")) or []


def fetch_limit_pool(date_str: str, creds: dict | None = None) -> dict:
    """连板高度与炸板率——判断情绪周期位置的核心指标。"""
    s = _session(creds)
    try:
        zt = _limit_pool(s, LIMIT_UP_URL, date_str)
    except Exception as e:  # noqa: BLE001
        return {"error": f"涨停池抓取失败: {str(e)[:100]}"}
    try:
        zb = _limit_pool(s, OPEN_LIMIT_URL, date_str)
    except Exception:  # noqa: BLE001
        zb = []

    def boards_of(x):
        # 330329=连续涨停天数；不同版本字段名可能是 continue_num
        for k in ("330329", "continue_num", "limit_up_days"):
            v = x.get(k)
            if v not in (None, ""):
                try:
                    return int(float(v))
                except (ValueError, TypeError):
                    pass
        return 1

    boards = [boards_of(x) for x in zt]
    height = max(boards) if boards else 0
    leaders = [
        {"name": x.get("name") or x.get("199112"), "code": x.get("code"), "boards": b}
        for x, b in zip(zt, boards) if b >= max(height - 1, 2)
    ][:10]
    n_zt, n_zb = len(zt), len(zb)
    return {
        "zt_count": n_zt,
        "zb_count": n_zb,
        "broken_rate": round(n_zb / max(n_zt + n_zb, 1) * 100, 1),
        "max_boards": height,
        "boards_2plus": sum(1 for b in boards if b >= 2),
        "leaders": leaders,
    }


# ---------------------------------------------------------------- 汇总

def _ths_code(code: str) -> str:
    """SH600519 → hs_600519"""
    return "hs_" + code[2:]


def fetch_all(cfg: dict, creds: dict | None = None) -> dict:
    days = cfg.get("signals", {}).get("kline_days", 250)
    top_n = cfg.get("fundflow", {}).get("top_n", 20)
    out: dict = {"indexes": {}, "fundflow": {}, "watchlist_kline": {}, "errors": [], "notes": {}}

    for idx in cfg.get("indexes", []):
        code = idx.get("ths_code")
        if not code:
            out["errors"].append(f"{idx['name']}: config 未配 ths_code")
            continue
        try:
            out["indexes"][idx["name"]] = fetch_kline(code, days)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"指数{idx['name']}: {str(e)[:100]}")

    for kind, key in [("concept", "concept_top20_5d"), ("industry", "industry_top20_5d"),
                      ("stock", "stock_top20_5d")]:
        rows, note = fetch_fundflow(kind, top_n, creds)
        out["fundflow"][key] = rows
        out["notes"][f"fund_{kind}"] = note
        if not rows:
            out["errors"].append(f"资金流{kind}未取到数据（{note[:80]}）")

    for w in cfg.get("watchlist", []):
        try:
            out["watchlist_kline"][w["code"]] = fetch_kline(_ths_code(w["code"]), days)
        except Exception as e:  # noqa: BLE001
            out["watchlist_kline"][w["code"]] = {"error": str(e)[:80]}

    return out
