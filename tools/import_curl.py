#!/usr/bin/env python3
"""把浏览器抓到的 cURL 接入本系统。

用法：
  1. F12 → Network → 目标请求 → 右键『Copy as cURL(bash)』
  2. 保存到文件，例如 my.txt（Windows 下用 PowerShell: Set-Content my.txt）
  3. python tools/import_curl.py alphapai.daily_list my.txt

已知的端点名（fetcher 会按名查找）：
  alphapai.daily_list      每日必看 列表
  alphapai.bluebook_list   蓝宝书 列表
  alphapai.report_detail   研报/报告 详情（已内置，可覆盖）
  jiuyan.article_list      韭研公社 文章列表
  jiuyan.article_detail    韭研公社 文章详情
"""

import json
import os
import sys

# 兼容 Windows：不能按 "/" 切分路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.curl_import import parse_curl, save_endpoint  # noqa: E402

# 认证类请求头：登记端点时剥离，提示用户放进 credentials.json
AUTH_HEADERS = {"authorization", "token", "x-token", "x-auth-token", "cookie"}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    key, path = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as f:
        spec = parse_curl(f.read())

    auth = {k: v for k, v in spec["headers"].items() if k in AUTH_HEADERS}
    spec["headers"] = {k: v for k, v in spec["headers"].items() if k not in AUTH_HEADERS}
    cookie = spec.pop("cookie", "")

    out = save_endpoint(key, spec)
    print(f"✅ 端点已登记 [{key}] → {out}")
    print(json.dumps(spec, ensure_ascii=False, indent=2))
    if auth or cookie:
        print("\n⚠️  以下凭证未写入 endpoints.json（避免入库），请确认它们已在 config/credentials.json：")
        for k, v in auth.items():
            print(f"   {k}: {v[:40]}...")
        if cookie:
            print(f"   cookie: {cookie[:60]}...")


if __name__ == "__main__":
    main()
