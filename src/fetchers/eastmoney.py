"""东方财富公开接口：指数K线、板块/个股近5日主力资金净流入排行。

无需凭证，作为同花顺资金流数据的稳定替代（用户本机也可用 iFinD 导出后替换）。
"""

from ..http import get_json, make_session

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
ULIST_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"


def _secid(code: str) -> str:
    """SH688213 → 1.688213；SZ300054 → 0.300054"""
    return ("1." if code.upper().startswith("SH") else "0.") + code[2:]


def fetch_names(codes: list[str]) -> dict[str, str]:
    """批量解析股票真实名称（用于校正/补全 config 里的 watchlist 名称）。"""
    if not codes:
        return {}
    s = make_session()
    params = {
        "secids": ",".join(_secid(c) for c in codes),
        "fields": "f12,f14",
        "fltt": "2",
        "invt": "2",
    }
    data = get_json(s, ULIST_URL, params=params)
    rows = (data.get("data") or {}).get("diff") or []
    by_num = {r.get("f12"): r.get("f14") for r in rows}
    return {c: by_num.get(c[2:], "") for c in codes}

# 板块类型：东财 fs 参数。若首次运行发现概念/行业内容对调，交换这两个值即可。
FS_CONCEPT = "m:90+t:3+f:!50"   # 概念板块
FS_INDUSTRY = "m:90+t:2+f:!50"  # 行业板块
FS_STOCK = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2"  # 沪深A股


def fetch_kline(secid: str, days: int = 250) -> list[dict]:
    """日K线（前复权）。返回 [{date, open, close, high, low, volume, amount}, ...]"""
    s = make_session()
    params = {
        "secid": secid,
        "klt": "101",
        "fqt": "1",
        "lmt": str(days),
        "end": "20500101",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    data = get_json(s, KLINE_URL, params=params)
    klines = (data.get("data") or {}).get("klines") or []
    out = []
    for line in klines:
        p = line.split(",")
        out.append(
            {
                "date": p[0],
                "open": float(p[1]),
                "close": float(p[2]),
                "high": float(p[3]),
                "low": float(p[4]),
                "volume": float(p[5]),
                "amount": float(p[6]),
            }
        )
    return out


def _fetch_fundflow_rank(fs: str, top_n: int) -> list[dict]:
    """近5日主力净流入排行。f164=5日主力净额(元) f165=5日主力净占比 f109=5日涨跌幅"""
    s = make_session()
    params = {
        "pn": "1",
        "pz": str(top_n),
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f164",
        "fs": fs,
        "fields": "f12,f14,f109,f164,f165,f166,f167,f168,f169",
    }
    data = get_json(s, CLIST_URL, params=params)
    rows = (data.get("data") or {}).get("diff") or []
    out = []
    for r in rows:
        out.append(
            {
                "code": r.get("f12"),
                "name": r.get("f14"),
                "pct_chg_5d": r.get("f109"),
                "main_net_5d_yi": round((r.get("f164") or 0) / 1e8, 2),  # 亿元
                "main_net_pct_5d": r.get("f165"),
            }
        )
    return out


def fetch_all(cfg: dict) -> dict:
    top_n = cfg.get("fundflow", {}).get("top_n", 20)
    days = cfg.get("signals", {}).get("kline_days", 250)
    result = {"indexes": {}, "fundflow": {}}
    for idx in cfg.get("indexes", []):
        result["indexes"][idx["name"]] = fetch_kline(idx["secid"], days)
    result["fundflow"]["concept_top20_5d"] = _fetch_fundflow_rank(FS_CONCEPT, top_n)
    result["fundflow"]["industry_top20_5d"] = _fetch_fundflow_rank(FS_INDUSTRY, top_n)
    result["fundflow"]["stock_top20_5d"] = _fetch_fundflow_rank(FS_STOCK, top_n)
    # 监控池：真实名称解析 + 个股K线（用于个股技术信号）
    codes = [w["code"] for w in cfg.get("watchlist", [])]
    try:
        result["watchlist_names"] = fetch_names(codes)
    except Exception as e:  # noqa: BLE001
        result["watchlist_names"] = {}
        result["names_error"] = str(e)
    result["watchlist_kline"] = {}
    for code in codes:
        try:
            result["watchlist_kline"][code] = fetch_kline(_secid(code), days)
        except Exception as e:  # noqa: BLE001
            result["watchlist_kline"][code] = {"error": str(e)}
    return result
