#!/usr/bin/env python3
"""从 HAR 文件批量发现并接入接口（比逐个复制 cURL 省事得多）。

导出 HAR：
  F12 → Network → 只勾 Fetch/XHR → 刷新页面并点开目标栏目
  → 面板内右键任意请求 → 『Save all as HAR with content』

用法：
  python tools/import_har.py alphapai.har                    # 只分析，列出所有接口
  python tools/import_har.py alphapai.har --save alphapai    # 分析并自动登记最像列表的接口

⚠️ HAR 内含 cookie 与 token，属于凭证文件，勿提交仓库（*.har 已在 .gitignore）。
"""

import json
import sys
from urllib.parse import parse_qsl, urlparse, urlunparse

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])

from src.curl_import import SKIP_HEADERS, save_endpoint  # noqa: E402
from src.normalize import normalize_list  # noqa: E402

AUTH_HEADERS = {"authorization", "token", "x-token", "x-auth-token", "cookie"}
SKIP_EXT = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ico", ".map")

# 端点名 → 用于识别用途的 URL 关键词
NAME_HINTS = [
    ("daily_list", ("daily", "today", "must", "necessary", "reading/list")),
    ("bluebook_list", ("bluebook", "blue", "book")),
    ("article_list", ("article", "post", "topic", "note", "feed")),
    ("report_detail", ("detail",)),
]


def load_entries(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        har = json.load(f)
    return (har.get("log") or {}).get("entries") or []


def analyze(entries: list[dict]) -> list[dict]:
    out = []
    for e in entries:
        req, res = e.get("request") or {}, e.get("response") or {}
        url = req.get("url", "")
        u = urlparse(url)
        if not url.startswith("http") or u.path.lower().endswith(SKIP_EXT):
            continue
        mime = ((res.get("content") or {}).get("mimeType") or "").lower()
        body = (res.get("content") or {}).get("text") or ""
        if "json" not in mime and not body.strip().startswith(("{", "[")):
            continue

        items, sample = [], None
        try:
            payload = json.loads(body)
            items = normalize_list(payload)
            if items:
                sample = items[0].get("title") or (items[0].get("text") or "")[:40]
        except Exception:  # noqa: BLE001
            pass

        headers = {}
        for h in req.get("headers") or []:
            k = (h.get("name") or "").lower()
            if k not in SKIP_HEADERS and k not in AUTH_HEADERS and not k.startswith(":"):
                headers[k] = h.get("value")

        post = req.get("postData") or {}
        parsed_body = None
        if post.get("text"):
            try:
                parsed_body = json.loads(post["text"])
            except json.JSONDecodeError:
                parsed_body = dict(parse_qsl(post["text"], keep_blank_values=True))

        out.append(
            {
                "method": req.get("method", "GET"),
                "url": urlunparse((u.scheme, u.netloc, u.path, "", "", "")),
                "params": dict(parse_qsl(u.query, keep_blank_values=True)),
                "headers": headers,
                "body": parsed_body,
                "status": res.get("status"),
                "item_count": len(items),
                "sample": sample,
            }
        )
    out.sort(key=lambda x: -x["item_count"])
    return out


def guess_name(url: str) -> str | None:
    low = url.lower()
    for name, hints in NAME_HINTS:
        if any(h in low for h in hints):
            return name
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    source = None
    if "--save" in sys.argv:
        source = sys.argv[sys.argv.index("--save") + 1]

    found = analyze(load_entries(path))
    if not found:
        print("未在 HAR 中发现 JSON 接口。请确认导出时勾选了 'with content'。")
        sys.exit(1)

    print(f"共发现 {len(found)} 个 JSON 接口，按『疑似列表条目数』排序：\n")
    for i, f in enumerate(found[:40]):
        flag = f"📋 {f['item_count']}条" if f["item_count"] else "  —  "
        print(f"[{i:2}] {flag} {f['method']:4} {f['url']}")
        if f["params"]:
            print(f"          params: {json.dumps(f['params'], ensure_ascii=False)[:120]}")
        if f["body"]:
            print(f"          body:   {json.dumps(f['body'], ensure_ascii=False)[:120]}")
        if f["sample"]:
            print(f"          样例:   {f['sample']}")

    if not source:
        print("\n加 --save <源名> 可自动登记，例如：")
        print(f"  python tools/import_har.py {path} --save alphapai")
        return

    saved = []
    for f in found:
        if f["item_count"] < 2:
            continue
        name = guess_name(f["url"]) or "article_list"
        key = f"{source}.{name}"
        if key in saved:
            continue
        spec = {k: f[k] for k in ("method", "url", "params", "headers", "body")}
        save_endpoint(key, spec)
        saved.append(key)
        print(f"\n✅ 已登记 [{key}] → {f['url']}（{f['item_count']} 条）")
    if not saved:
        print("\n⚠️  没有接口返回可识别的列表数据。请确认已在页面上点开目标栏目再导出 HAR。")


if __name__ == "__main__":
    main()
