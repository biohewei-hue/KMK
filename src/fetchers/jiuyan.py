"""韭研公社（需凭证）：关注栏目 — 每日公社内容精选(含链接帖全文)、学习笔记、
公告内容精选、盘前纪要等。

认证方式（由抓包确认）：
  Cookie: SESSION=xxx
  token: <64位十六进制签名>     ← 与 timestamp 成对，服务端校验
  timestamp: 2026-08-03T00:03:47Z
  platform: 3
签名盐值在其前端JS内，无法离线复算，因此 token/timestamp 需成对配置在
config/credentials.json → jiuyan，失效后重新抓包替换即可。

列表接口可用 tools/import_curl.py 登记到 config/endpoints.json（推荐），
未登记时会自动探测常见路径。
"""

import re
import time

from ..curl_import import get_endpoint
from ..http import make_session, post_json
from ..normalize import deep_text, normalize_list, strip_html

BASE = "https://web-api.jiuyangongshe.com/jystock-app/api/v1"

# 关注栏目中需要重点抓取的帖子标题关键词
FOCUS_KEYWORDS = ["公社内容精选", "学习笔记", "公告内容精选", "盘前纪要", "精选", "复盘", "早报"]

# 列表接口未登记时的候选路径（POST + JSON body）
LIST_CANDIDATES = [
    (BASE + "/article/list", {"limit": 30, "start": 1, "user_id": ""}),
    (BASE + "/community/article/list", {"limit": 30, "start": 1, "user_id": ""}),
    (BASE + "/user/session", {"limit": 30, "start": 1, "user_id": ""}),
    (BASE + "/article/home", {"limit": 30, "start": 1}),
    (BASE + "/note/list", {"limit": 30, "start": 1}),
]
DETAIL_CANDIDATES = [BASE + "/article/detail", BASE + "/community/article/detail"]


def _session(creds: dict):
    j = creds.get("jiuyan") or {}
    cookie = j.get("cookie", "")
    hdrs = dict(j.get("headers") or {})
    token = j.get("token") or hdrs.get("token", "")
    ts = j.get("timestamp") or hdrs.get("timestamp", "")
    if not cookie and not token:
        raise RuntimeError(
            "缺少韭研公社凭证（config/credentials.json → jiuyan.cookie / jiuyan.token）"
        )
    headers = {
        "Content-Type": "application/json",
        "platform": "3",
        "Origin": "https://www.jiuyangongshe.com",
        "Referer": "https://www.jiuyangongshe.com/",
    }
    if token:
        headers["token"] = token
    # token 与 timestamp 成对校验，必须使用抓包时的原始 timestamp
    headers["timestamp"] = ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    headers.update({k: v for k, v in hdrs.items() if k not in ("token", "timestamp")})
    return make_session(cookie=cookie, headers=headers)


def _fetch_list(s) -> tuple[list[dict], list[str]]:
    """优先用登记端点，否则探测候选路径。返回 (归一化条目, 日志)。"""
    log = []
    spec = get_endpoint("jiuyan", "article_list")
    if spec:
        body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
        data = post_json(s, spec["url"], json=body, params=spec.get("params") or {})
        items = normalize_list(data)
        log.append(f"登记端点 {spec['url']} → {len(items)} 条")
        if items:
            return items, log
    for url, body in LIST_CANDIDATES:
        try:
            data = post_json(s, url, retries=1, json=body)
            items = normalize_list(data)
            log.append(f"{url} → {len(items)} 条")
            if items:
                log.append(f"✅ 命中：{url}")
                return items, log
        except Exception as e:  # noqa: BLE001
            log.append(f"{url} → {str(e)[:80]}")
    return [], log


def _fetch_detail(s, article_id: str) -> dict | None:
    spec = get_endpoint("jiuyan", "article_detail")
    urls = [spec["url"]] if spec else DETAIL_CANDIDATES
    for url in urls:
        for body in ({"article_id": article_id}, {"id": article_id}):
            try:
                data = post_json(s, url, retries=1, json=body)
                text = deep_text(data)
                if text:
                    raw = str(data)
                    return {
                        "article_id": article_id,
                        "text": text,
                        "links": re.findall(r'href=[\\"\']?(https?://[^\\"\'\s>]+)', raw),
                    }
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def fetch_all(cfg: dict, creds: dict) -> dict:
    s = _session(creds)
    max_articles = cfg.get("jiuyan", {}).get("max_articles", 200)
    articles, probe_log = _fetch_list(s)
    articles = articles[:max_articles]
    out = {
        "total_articles": len(articles),
        "article_list": articles,
        "focus_details": [],
        "linked_details": [],
        "probe_log": probe_log,
        "errors": [],
    }
    if not articles:
        out["errors"].append(
            "韭研公社列表接口未命中：请抓包『关注』栏目的XHR，用 "
            "python tools/import_curl.py jiuyan.article_list <文件> 导入"
        )
        return out

    focus = [a for a in articles if any(k in (a.get("title") or "") for k in FOCUS_KEYWORDS)]
    for a in focus[:30]:
        aid = a.get("id")
        if not aid:
            continue
        d = _fetch_detail(s, aid)
        if not d:
            # 列表里已带正文时直接使用
            if a.get("text"):
                d = {"article_id": aid, "text": a["text"], "links": []}
            else:
                out["errors"].append(f"详情抓取失败: {a.get('title')}")
                continue
        d["title"] = a.get("title")
        d["time"] = a.get("time")
        out["focus_details"].append(d)

        # 「每日公社内容精选」正文里引用的站内帖，逐个抓全文
        for link in d.get("links") or []:
            m = re.search(r"jiuyangongshe\.com/a/(\w+)", link)
            if m:
                ld = _fetch_detail(s, m.group(1))
                if ld:
                    out["linked_details"].append(ld)
                time.sleep(0.4)
        time.sleep(0.4)

    for d in out["focus_details"]:
        d["text"] = strip_html(d["text"])
    return out
