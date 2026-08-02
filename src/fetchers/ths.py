"""同花顺：个股热榜（公开接口）+ 概念热榜。

热榜接口无需登录。抓取时会保存快照，供 analysis/heat.py 做
「升温最快 / 降温最快 / 新上榜」对比（对比昨日快照与今日快照）。
"""

from ..http import get_json, make_session

HOT_STOCK_URL = (
    "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"
)
HOT_CONCEPT_URL = (
    "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate"
)


def fetch_hot_stocks(list_type: str = "normal") -> list[dict]:
    """个股热榜。type=hour 小时榜。返回 [{rank, code, name, rate, hot_tag, concepts}, ...]"""
    s = make_session(headers={"Referer": "https://eq.10jqka.com.cn/"})
    params = {"stock_type": "a", "type": "hour", "list_type": list_type}
    data = get_json(s, HOT_STOCK_URL, params=params)
    items = (data.get("data") or {}).get("stock_list") or []
    out = []
    for i, it in enumerate(items):
        tag = it.get("tag") or {}
        out.append(
            {
                "rank": i + 1,
                "code": it.get("code"),
                "name": it.get("name"),
                "rate": it.get("rate"),  # 热度值
                "rise_rank": it.get("order"),
                "hot_tag": it.get("hot_tag") or tag.get("popularity_tag"),
                "concepts": tag.get("concept_tag"),
                "analysis": it.get("analyse"),  # 上榜解析（如有）
            }
        )
    return out


def fetch_hot_concepts() -> list[dict]:
    """概念板块热榜。"""
    s = make_session(headers={"Referer": "https://eq.10jqka.com.cn/"})
    params = {"type": "concept"}
    data = get_json(s, HOT_CONCEPT_URL, params=params)
    items = (data.get("data") or {}).get("plate_list") or []
    return [
        {
            "rank": i + 1,
            "code": it.get("code"),
            "name": it.get("name"),
            "rate": it.get("rate"),
            "hot_tag": it.get("hot_tag"),
        }
        for i, it in enumerate(items)
    ]


def fetch_all(cfg: dict, creds: dict) -> dict:
    out = {"hot_stocks": [], "hot_concepts": [], "errors": []}
    try:
        out["hot_stocks"] = fetch_hot_stocks()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"hot_stocks: {e}")
    try:
        out["hot_concepts"] = fetch_hot_concepts()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"hot_concepts: {e}")
    return out
