"""韭研公社（需凭证）：关注栏目 — 每日公社内容精选(含链接帖全文)、学习笔记、
公告内容精选、盘前纪要等。

说明：公社的 app 接口带签名头（token/timestamp）。本模块按已知接口形式实现；
若首次运行报错，请在浏览器打开 jiuyangongshe.com 对应栏目页面，
F12 → Network → 找到返回文章列表的 XHR 请求 → 右键『复制为cURL』发给 Claude 接线。
"""

import re
import time

from ..http import make_session, post_json

BASE = "https://app.jiuyangongshe.com/jystock-app/api/v1"
LIST_URL = BASE + "/article/list"
DETAIL_URL = BASE + "/article/detail"

# 关注栏目中需要重点抓取的帖子标题关键词
FOCUS_KEYWORDS = ["公社内容精选", "学习笔记", "公告内容精选", "盘前纪要", "精选"]


def _session(creds: dict):
    j = creds.get("jiuyan") or {}
    headers = dict(j.get("headers") or {})
    cookie = j.get("cookie", "")
    if not headers.get("token") and not cookie:
        raise RuntimeError(
            "缺少韭研公社凭证（config/credentials.json → jiuyan.cookie 或 jiuyan.headers.token）"
        )
    headers.setdefault("timestamp", str(int(time.time() * 1000)))
    headers.setdefault("platform", "3")
    headers["Content-Type"] = "application/json"
    headers.setdefault("Origin", "https://www.jiuyangongshe.com")
    headers.setdefault("Referer", "https://www.jiuyangongshe.com/")
    return make_session(cookie=cookie, headers=headers)


def fetch_article_list(s, page: int = 1, limit: int = 20) -> list[dict]:
    data = post_json(s, LIST_URL, json={"pageCount": page, "limit": limit})
    items = (data.get("data") or {}).get("list") or (data.get("data") or []) or []
    out = []
    for it in items:
        out.append(
            {
                "article_id": it.get("article_id") or it.get("id"),
                "title": it.get("title") or "",
                "time": it.get("create_time") or it.get("time"),
                "author": (it.get("user") or {}).get("nickname") or it.get("nickname"),
                "read": it.get("read_count"),
                "comment": it.get("comment_count"),
            }
        )
    return out


def fetch_article_detail(s, article_id) -> dict:
    data = post_json(s, DETAIL_URL, json={"article_id": article_id})
    d = data.get("data") or {}
    content = d.get("content") or ""
    text = re.sub(r"<[^>]+>", "", content)  # 去HTML标签
    links = re.findall(r'href="([^"]+)"', content)
    return {"article_id": article_id, "title": d.get("title"), "text": text, "links": links}


def fetch_all(cfg: dict, creds: dict) -> dict:
    s = _session(creds)
    max_articles = cfg.get("jiuyan", {}).get("max_articles", 200)
    articles = []
    page = 1
    while len(articles) < max_articles:
        batch = fetch_article_list(s, page)
        if not batch:
            break
        articles.extend(batch)
        page += 1
        time.sleep(0.5)

    # 命中关注栏目关键词的帖子抓全文（其中"公社内容精选"里引用的站内链接帖也一并抓取）
    focus = [a for a in articles if any(k in a["title"] for k in FOCUS_KEYWORDS)]
    details, linked_details, errors = [], [], []
    for a in focus:
        try:
            d = fetch_article_detail(s, a["article_id"])
            details.append(d)
            for link in d["links"]:
                m = re.search(r"jiuyangongshe\.com/a/(\w+)", link)
                if m:
                    try:
                        linked_details.append(fetch_article_detail(s, m.group(1)))
                        time.sleep(0.5)
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"linked {link}: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"detail {a['title']}: {e}")
        time.sleep(0.5)

    return {
        "total_articles": len(articles),
        "article_list": articles,
        "focus_details": details,       # 关注栏目帖子全文
        "linked_details": linked_details,  # 精选帖内链接指向的帖子全文
        "errors": errors,
    }
