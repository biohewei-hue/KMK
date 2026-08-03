"""cURL 解析与端点登记。

浏览器 F12 → 右键『Copy as cURL』 → 保存为文本 → 用 tools/import_curl.py 导入，
即可把任意接口接入本系统，无需改代码。
"""

import json
import os
import shlex
from urllib.parse import parse_qsl, urlparse, urlunparse

from .config import CONFIG_DIR

ENDPOINTS_PATH = os.path.join(CONFIG_DIR, "endpoints.json")

# 这些请求头不需要保存（浏览器指纹/协商类，requests 会自行处理）
SKIP_HEADERS = {
    "accept-encoding", "connection", "content-length", "host",
    "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site",
    "priority", "pragma", "cache-control",
}


def parse_curl(text: str) -> dict:
    """解析 cURL 命令 → {method, url, params, headers, cookie, body}"""
    text = text.strip()
    # 去掉行尾续行符与换行
    text = text.replace("\\\n", " ").replace("\\\r\n", " ")
    tokens = shlex.split(text)
    if tokens and tokens[0] == "curl":
        tokens = tokens[1:]

    url, method, headers, cookie, body = "", "", {}, "", None
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("-H", "--header"):
            i += 1
            raw = tokens[i]
            if ":" in raw:
                k, v = raw.split(":", 1)
                k, v = k.strip(), v.strip()
                if k.lower() == "cookie":
                    cookie = v
                elif k.lower() not in SKIP_HEADERS:
                    headers[k.lower()] = v
        elif t in ("-b", "--cookie"):
            i += 1
            cookie = tokens[i]
        elif t in ("-X", "--request"):
            i += 1
            method = tokens[i].upper()
        elif t in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"):
            i += 1
            body = tokens[i]
        elif t in ("--url",):
            i += 1
            url = tokens[i]
        elif t.startswith("http"):
            url = t
        elif t in ("--compressed", "-s", "-sS", "-k", "-i", "-L", "-v"):
            pass
        i += 1

    if not url:
        raise ValueError("未在 cURL 中找到 URL")
    if not method:
        method = "POST" if body else "GET"

    u = urlparse(url)
    params = dict(parse_qsl(u.query, keep_blank_values=True))
    base = urlunparse((u.scheme, u.netloc, u.path, "", "", ""))

    parsed_body = None
    if body:
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = dict(parse_qsl(body, keep_blank_values=True)) or body

    return {
        "method": method,
        "url": base,
        "params": params,
        "headers": headers,
        "cookie": cookie,
        "body": parsed_body,
    }


def load_endpoints() -> dict:
    if not os.path.exists(ENDPOINTS_PATH):
        return {}
    with open(ENDPOINTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_endpoint(key: str, spec: dict):
    """key 形如 'alphapai.daily_list'，凭证类请求头不写入（留在 credentials.json）。"""
    data = load_endpoints()
    source, _, name = key.partition(".")
    data.setdefault(source, {})[name or "default"] = spec
    with open(ENDPOINTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return ENDPOINTS_PATH


def get_endpoint(source: str, name: str) -> dict | None:
    return (load_endpoints().get(source) or {}).get(name)
