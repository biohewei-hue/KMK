"""同花顺涨停池/炸板池采集 —— 连板高度、炸板率、高标名单。

情绪周期的三个温度计，用来判断"退潮还是启动"：
  · 连板高度：最高连板数。回落=退潮，回升=有资金愿意接力
  · 炸板率   = 炸板数 / (涨停数 + 炸板数)。>50% 说明承接弱，封板质量差
  · 2板以上家数：晋级梯队厚度，比单看涨停总数更能反映赚钱效应

端点（同花顺，无需凭证）：
  涨停池 https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool
  炸板池 https://data.10jqka.com.cn/dataapi/limit_up/open_limit_up_pool

跨日快照存 SNAPSHOT/limit_pool_<date>.json，本脚本自动读最近若干份算高度趋势——
**单日的连板高度没有意义，方向才有意义**。

备注：东财 push2ex 的 getTopicZTPool 是同类数据的替代源，若同花顺改版可切换。
"""
import datetime as dt
import json
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import config  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")
BASE = "https://data.10jqka.com.cn/dataapi/limit_up/"
HEADERS = {"User-Agent": UA, "Referer": "https://data.10jqka.com.cn/datacenterph/limitup/",
           "X-Requested-With": "XMLHttpRequest"}

# 330329=连续涨停天数 199112=名称 10=最新价 9002/9001=首次/最后封板时间
FIELDS = "199112,10,9001,330329,330325,9002,133,1000"


def _pool(kind: str, day: str) -> list[dict]:
    """kind: limit_up_pool / open_limit_up_pool"""
    params = {"page": 1, "limit": 200, "field": FIELDS, "filter": "HS,GEM2STAR",
              "order_field": "330329", "order_type": 0,
              "date": day.replace("-", ""), "_": int(time.time() * 1000)}
    r = requests.get(BASE + kind, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    d = r.json().get("data") or {}
    return d.get("info") or []


def _boards(x: dict) -> int:
    """连续涨停天数。字段名随版本变过，逐个兜底。"""
    for k in ("330329", "continue_num", "limit_up_days", "high"):
        v = x.get(k)
        if v not in (None, "", "-"):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                pass
    return 1


def _name(x: dict) -> str:
    return x.get("name") or x.get("199112") or x.get("stock_name") or ""


def _history(days: int = 6) -> list[dict]:
    """读最近的快照，供判断高度/炸板率的方向。"""
    out = []
    for f in sorted(config.SNAPSHOT.glob("limit_pool_*.json"))[-days:]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"date": f.stem.replace("limit_pool_", ""),
                        "max_boards": d.get("max_boards"),
                        "zt": d.get("zt_count"), "broken": d.get("broken_rate")})
        except Exception:                                        # noqa: BLE001
            continue
    return out


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else config.today()

    try:
        zt = _pool("limit_up_pool", day)
    except Exception as e:                                       # noqa: BLE001
        print(f"❌ 涨停池抓取失败：{str(e)[:120]}")
        sys.exit(1)
    try:
        zb = _pool("open_limit_up_pool", day)
    except Exception as e:                                       # noqa: BLE001
        print(f"⚠️  炸板池抓取失败（炸板率将缺失）：{str(e)[:80]}")
        zb = []

    boards = [_boards(x) for x in zt]
    height = max(boards) if boards else 0
    n_zt, n_zb = len(zt), len(zb)

    # 高标 = 最高板与次高板（≥2 板才算梯队）
    leaders = sorted(
        ({"name": _name(x), "code": x.get("code"), "boards": b}
         for x, b in zip(zt, boards) if b >= max(height - 1, 2)),
        key=lambda r: -r["boards"])[:12]

    result = {
        "date": day,
        "zt_count": n_zt,
        "zb_count": n_zb,
        "broken_rate": round(n_zb / max(n_zt + n_zb, 1) * 100, 1) if zb else None,
        "max_boards": height,
        "boards_2plus": sum(1 for b in boards if b >= 2),
        "boards_3plus": sum(1 for b in boards if b >= 3),
        "leaders": leaders,
    }

    config.save_raw("limit_pool.json", result, day)
    config.SNAPSHOT.mkdir(parents=True, exist_ok=True)
    (config.SNAPSHOT / f"limit_pool_{day}.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8")

    hist = _history()
    prev = [h for h in hist if h["date"] < day]
    trend = ""
    if prev:
        p = prev[-1]
        if p.get("max_boards") is not None:
            d = height - p["max_boards"]
            trend = f"（前日{p['max_boards']}板，{'回升+' if d > 0 else '回落' if d < 0 else '持平'}{abs(d) or ''}）"

    print(f"[{day}] 涨停{n_zt} 炸板{n_zb}"
          + (f" 炸板率{result['broken_rate']}%" if zb else " 炸板率缺失"))
    print(f"       连板高度 {height}板{trend}｜2板以上{result['boards_2plus']}只｜"
          f"3板以上{result['boards_3plus']}只")
    if leaders:
        print("       高标：" + "、".join(f"{x['name']}{x['boards']}板" for x in leaders[:6]))
    if len(hist) >= 2:
        print("       高度轨迹：" + " → ".join(
            f"{h['date'][5:]}:{h['max_boards']}板" for h in hist[-5:]))


if __name__ == "__main__":
    main()
