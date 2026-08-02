"""财联社电报（公开接口，需按官方网页算法计算 sign 参数）。

sign = md5(sha1(按key排序后的查询字符串))
"""

import hashlib
import time
from urllib.parse import urlencode

from ..http import get_json, make_session

TELEGRAPH_URL = "https://www.cls.cn/nodeapi/updateTelegraphList"

BASE_PARAMS = {
    "app": "CailianpressWeb",
    "category": "",
    "hasFirstVipArticle": "1",
    "os": "web",
    "rn": "20",
    "subscribedColumnIds": "",
    "sv": "8.4.6",
}


def _sign(params: dict) -> str:
    qs = urlencode(sorted(params.items()))
    sha = hashlib.sha1(qs.encode()).hexdigest()
    return hashlib.md5(sha.encode()).hexdigest()


def fetch_telegraphs(pages: int = 5) -> list[dict]:
    """滚动电报，按 lastTime 翻页。返回 [{time, title, content, is_red}, ...] 时间倒序。"""
    s = make_session(headers={"Referer": "https://www.cls.cn/telegraph"})
    out = []
    last_time = int(time.time())
    for _ in range(pages):
        params = dict(BASE_PARAMS)
        params["lastTime"] = str(last_time)
        params["sign"] = _sign(params)
        data = get_json(s, TELEGRAPH_URL, params=params)
        rolls = ((data.get("data") or {}).get("roll_data")) or []
        if not rolls:
            break
        for r in rolls:
            out.append(
                {
                    "id": r.get("id"),
                    "time": time.strftime(
                        "%Y-%m-%d %H:%M", time.localtime(r.get("ctime", 0))
                    ),
                    "title": r.get("title") or "",
                    "content": r.get("content") or r.get("brief") or "",
                    "is_red": bool(r.get("level") == "A" or r.get("bold")),  # 加红加粗=重要
                    "stocks": [x.get("name") for x in (r.get("stock_list") or [])],
                }
            )
        last_time = rolls[-1].get("ctime", last_time) - 1
    return out


def fetch_all(cfg: dict) -> dict:
    pages = cfg.get("cls", {}).get("pages", 5)
    return {"telegraphs": fetch_telegraphs(pages)}
