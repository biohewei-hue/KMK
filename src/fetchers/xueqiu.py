"""雪球（需 cookie）：热帖、热股榜、监控池个股讨论。"""

from ..http import get_json, make_session

HOT_TOPIC_URL = "https://xueqiu.com/statuses/hot/listV2.json"
HOT_STOCK_URL = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json"
SEARCH_URL = "https://xueqiu.com/query/v1/search/status.json"


def _session(creds: dict):
    cookie = (creds.get("xueqiu") or {}).get("cookie", "")
    if not cookie:
        raise RuntimeError("缺少雪球 cookie（config/credentials.json → xueqiu.cookie）")
    return make_session(cookie=cookie, headers={"Referer": "https://xueqiu.com/"})


def fetch_hot_posts(s, size: int = 20) -> list[dict]:
    """今日话题热帖（含评论数/转发数，用于'高讨论帖'排序）。"""
    params = {"since_id": "-1", "max_id": "-1", "size": str(size)}
    data = get_json(s, HOT_TOPIC_URL, params=params)
    items = data.get("items") or []
    out = []
    for it in items:
        st = it.get("original_status") or {}
        out.append(
            {
                "title": st.get("title") or "",
                "text": (st.get("description") or "")[:500],
                "user": (st.get("user") or {}).get("screen_name"),
                "replies": st.get("reply_count"),
                "retweets": st.get("retweet_count"),
                "likes": st.get("like_count"),
                "url": "https://xueqiu.com" + (st.get("target") or ""),
                "created": st.get("timeBefore"),
            }
        )
    out.sort(key=lambda x: x.get("replies") or 0, reverse=True)
    return out


def fetch_hot_stocks(s, size: int = 30) -> list[dict]:
    """雪球热股榜（沪深）。"""
    params = {"size": str(size), "_type": "12", "type": "12"}
    data = get_json(s, HOT_STOCK_URL, params=params)
    items = (data.get("data") or {}).get("items") or []
    return [
        {
            "rank": i + 1,
            "code": it.get("code"),
            "name": it.get("name"),
            "pct": it.get("percent"),
            "hot_value": it.get("value"),
        }
        for i, it in enumerate(items)
    ]


def search_stock_posts(s, keyword: str, count: int = 10) -> list[dict]:
    """按关键词搜讨论（用于监控池个股）。"""
    params = {"sortId": "2", "q": keyword, "count": str(count)}
    data = get_json(s, SEARCH_URL, params=params)
    items = data.get("list") or []
    return [
        {
            "title": it.get("title") or "",
            "text": (it.get("description") or "")[:300],
            "replies": it.get("reply_count"),
            "created_at": it.get("created_at"),
        }
        for it in items
    ]


def fetch_all(cfg: dict, creds: dict) -> dict:
    s = _session(creds)
    xq = cfg.get("xueqiu", {})
    out = {"hot_posts": [], "hot_stocks": [], "watchlist_posts": {}, "errors": []}
    try:
        out["hot_posts"] = fetch_hot_posts(s, xq.get("hot_posts", 20))
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"hot_posts: {e}")
    try:
        out["hot_stocks"] = fetch_hot_stocks(s, xq.get("hot_stocks", 30))
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"hot_stocks: {e}")
    for w in cfg.get("watchlist", []):
        if not w.get("name"):
            continue
        try:
            out["watchlist_posts"][w["name"]] = search_stock_posts(s, w["name"])
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"watchlist {w['name']}: {e}")
    return out
