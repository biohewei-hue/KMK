"""市场情绪指标（东方财富公开接口，无需凭证）。

见底判断的核心依据：地量见地价、跌停家数收敛、连板高度回升、北向回流。
"""

from ..http import get_json, make_session

CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
ULIST_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

FS_STOCK = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2"


def _all_stocks(s) -> list[dict]:
    """全市场个股快照：涨跌幅、成交额、换手。分页拉全。"""
    out, pn = [], 1
    while True:
        params = {
            "pn": str(pn), "pz": "1000", "po": "1", "np": "1", "fltt": "2", "invt": "2",
            "fid": "f3", "fs": FS_STOCK, "fields": "f12,f14,f3,f6,f8,f10",
        }
        data = get_json(s, CLIST_URL, params=params)
        diff = (data.get("data") or {}).get("diff") or []
        if not diff:
            break
        out.extend(diff)
        if len(diff) < 1000:
            break
        pn += 1
        if pn > 8:  # 安全上限，A股约5000+只
            break
    return out


def fetch_breadth() -> dict:
    """涨跌家数、涨跌停家数、成交额、涨幅分布。"""
    s = make_session()
    rows = _all_stocks(s)
    up = down = flat = limit_up = limit_down = 0
    amount = 0.0
    for r in rows:
        pct = r.get("f3")
        if pct in (None, "-"):
            continue
        pct = float(pct)
        amount += float(r.get("f6") or 0)
        if pct > 0:
            up += 1
        elif pct < 0:
            down += 1
        else:
            flat += 1
        # 主板10%、创业板/科创板20%，留0.3容差覆盖四舍五入
        code = str(r.get("f12") or "")
        cap = 20.0 if code.startswith(("30", "68")) else 10.0
        if pct >= cap - 0.3:
            limit_up += 1
        elif pct <= -(cap - 0.3):
            limit_down += 1
    return {
        "total": len(rows),
        "up": up,
        "down": down,
        "flat": flat,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "amount_yi": round(amount / 1e8, 0),  # 两市成交额（亿元）
        "up_ratio": round(up / max(len(rows), 1) * 100, 1),
    }


def fetch_northbound() -> dict:
    """北向资金当日净流入（亿元）。接口不可用时返回 None，不阻断整体抓取。"""
    s = make_session()
    try:
        data = get_json(
            s,
            "https://push2.eastmoney.com/api/qt/kamt/get",
            retries=1,
            params={"fields1": "f1,f3", "fields2": "f51,f52,f54,f56"},
        )
        d = data.get("data") or {}
        hk2sh = (d.get("hk2sh") or {}).get("netBuyAmt")
        hk2sz = (d.get("hk2sz") or {}).get("netBuyAmt")
        if hk2sh is None and hk2sz is None:
            return {"net_yi": None, "note": "接口无数据（北向实时数据已于2024年8月起停止披露）"}
        return {"net_yi": round((float(hk2sh or 0) + float(hk2sz or 0)) / 1e4, 2)}
    except Exception as e:  # noqa: BLE001
        return {"net_yi": None, "note": f"抓取失败: {str(e)[:80]}"}


ZT_POOL_URL = "https://push2ex.eastmoney.com/getTopicZTPool"  # 涨停池
ZB_POOL_URL = "https://push2ex.eastmoney.com/getTopicZBPool"  # 炸板池
_UT = "7eea3edcaed734bea9cbfc24409ed989"


def _pool(s, url: str, date_str: str) -> list[dict]:
    params = {
        "ut": _UT, "dpt": "wz.ztzt", "Pageindex": "0", "pagesize": "200",
        "sort": "fbt:asc", "date": date_str.replace("-", ""),
    }
    data = get_json(s, url, retries=1, params=params)
    return ((data.get("data") or {}).get("pool")) or []


def fetch_limit_pool(date_str: str) -> dict:
    """连板高度与炸板率——判断情绪周期位置的核心指标。"""
    s = make_session(headers={"Referer": "https://quote.eastmoney.com/"})
    try:
        zt = _pool(s, ZT_POOL_URL, date_str)
    except Exception as e:  # noqa: BLE001
        return {"error": f"涨停池抓取失败: {str(e)[:80]}"}
    try:
        zb = _pool(s, ZB_POOL_URL, date_str)
    except Exception:  # noqa: BLE001
        zb = []

    boards = [int(x.get("lbc") or 1) for x in zt]
    height = max(boards) if boards else 0
    leaders = [
        {"name": x.get("n"), "code": x.get("c"), "boards": int(x.get("lbc") or 1)}
        for x in zt
        if int(x.get("lbc") or 1) >= max(height - 1, 2)
    ][:10]
    n_zt, n_zb = len(zt), len(zb)
    return {
        "zt_count": n_zt,
        "zb_count": n_zb,
        "broken_rate": round(n_zb / max(n_zt + n_zb, 1) * 100, 1),  # 炸板率%
        "max_boards": height,          # 连板高度
        "boards_2plus": sum(1 for b in boards if b >= 2),
        "leaders": leaders,            # 高标（最高板及次高板）
    }


def fetch_all(cfg: dict, date_str: str = "") -> dict:
    out = {"errors": []}
    try:
        out["breadth"] = fetch_breadth()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"breadth: {e}")
    out["northbound"] = fetch_northbound()
    if date_str:
        out["limit_pool"] = fetch_limit_pool(date_str)
    return out
