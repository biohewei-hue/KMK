"""知识星球（需 cookie）：黑金会员星球 24小时帖子，重点抓取文字帖(talk)全文。"""

import time
from datetime import datetime, timedelta, timezone

from ..http import get_json, make_session

GROUPS_URL = "https://api.zsxq.com/v2/groups"
TOPICS_URL = "https://api.zsxq.com/v2/groups/{gid}/topics"

TZ = timezone(timedelta(hours=8))


def _session(creds: dict):
    cookie = (creds.get("zsxq") or {}).get("cookie", "")
    if not cookie:
        raise RuntimeError("缺少知识星球 cookie（config/credentials.json → zsxq.cookie）")
    return make_session(
        cookie=cookie,
        headers={
            "Referer": "https://wx.zsxq.com/",
            "Origin": "https://wx.zsxq.com",
            "x-version": "2.77.0",
        },
    )


def find_group(s, keyword: str) -> dict | None:
    """在已加入的星球中按名称关键词定位星球。"""
    data = get_json(s, GROUPS_URL)
    groups = (data.get("resp_data") or {}).get("groups") or []
    for g in groups:
        if keyword in (g.get("name") or ""):
            return {"group_id": g.get("group_id"), "name": g.get("name")}
    return None


def fetch_topics(s, gid, hours: int = 24, max_topics: int = 100) -> list[dict]:
    """抓取最近 hours 小时的帖子，翻页直到超出时间窗。"""
    cutoff = datetime.now(TZ) - timedelta(hours=hours)
    out = []
    end_time = None
    while len(out) < max_topics:
        params = {"scope": "all", "count": "20"}
        if end_time:
            params["end_time"] = end_time
        data = get_json(s, TOPICS_URL.format(gid=gid), params=params)
        topics = (data.get("resp_data") or {}).get("topics") or []
        if not topics:
            break
        stop = False
        for t in topics:
            ct_raw = t.get("create_time") or ""
            try:
                ct = datetime.fromisoformat(ct_raw.replace("+0800", "+08:00"))
            except ValueError:
                ct = datetime.now(TZ)
            if ct < cutoff:
                stop = True
                break
            ttype = t.get("type")
            talk = t.get("talk") or {}
            qa = t.get("question") or {}
            text = talk.get("text") or qa.get("text") or (t.get("solution") or {}).get("text") or ""
            out.append(
                {
                    "topic_id": t.get("topic_id"),
                    "type": ttype,  # talk=文字帖(重点) q&a=问答
                    "time": ct_raw,
                    "author": (talk.get("owner") or {}).get("name"),
                    "text": text,
                    "images": len(talk.get("images") or []),
                    "files": [f.get("name") for f in (talk.get("files") or [])],
                    "likes": t.get("likes_count"),
                    "comments": t.get("comments_count"),
                }
            )
            end_time = ct_raw
        if stop:
            break
        time.sleep(1)  # 星球接口限频较严
    return out


def fetch_all(cfg: dict, creds: dict) -> dict:
    z = cfg.get("zsxq", {})
    s = _session(creds)
    gid = z.get("group_id")
    gname = ""
    if not gid:
        g = find_group(s, z.get("group_keyword", "黑金"))
        if not g:
            raise RuntimeError(f"未找到名称包含『{z.get('group_keyword')}』的星球，请在 config.yaml 填 group_id")
        gid, gname = g["group_id"], g["name"]
    topics = fetch_topics(s, gid, z.get("hours", 24), z.get("max_topics", 100))
    talk_posts = [t for t in topics if t["type"] == "talk" and t["text"]]
    return {
        "group": {"id": gid, "name": gname},
        "total_24h": len(topics),
        "talk_posts": talk_posts,  # 文字帖（重点分析对象）
        "all_topics": topics,
    }
