#!/usr/bin/env python3
"""检查各站凭证有效性：Alpha派 JWT 剩余天数、其他源凭证是否已填。

用法：python tools/check_token.py
"""

import base64
import json
import os
import sys
from datetime import datetime

# 兼容 Windows：不能按 "/" 切分路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_credentials  # noqa: E402
from src.curl_import import load_endpoints  # noqa: E402


def jwt_expiry(token: str):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        d = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(d["exp"])
    except Exception:  # noqa: BLE001
        return None


def main():
    creds = load_credentials()
    if not creds:
        print("❌ 未找到 config/credentials.json（可从 credentials.example.json 复制）")
        sys.exit(1)

    ap = creds.get("alphapai") or {}
    token = ap.get("authorization", "")
    if token:
        exp = jwt_expiry(token)
        if exp:
            days = (exp - datetime.now()).days
            flag = "✅" if days > 3 else "⚠️ 即将过期"
            print(f"{flag} Alpha派 JWT 有效至 {exp:%Y-%m-%d %H:%M}（剩余 {days} 天）")
        else:
            print("⚠️  Alpha派 authorization 无法解析，可能格式有误")
        print(f"   x-device: {'✅ 已配置' if ap.get('x_device') else '❌ 缺失'}")
    else:
        print("❌ Alpha派 authorization 未配置")

    j = creds.get("jiuyan") or {}
    has_pair = bool(j.get("token")) and bool(j.get("timestamp"))
    print(f"{'✅' if j.get('cookie') else '❌'} 韭研公社 cookie（SESSION）")
    print(f"{'✅' if has_pair else '⚠️ '} 韭研公社 token/timestamp 成对配置"
          + ("" if has_pair else "：两者必须同时提供"))

    z = (creds.get("zsxq") or {}).get("cookie", "")
    ok = "zsxq_access_token" in z
    print(f"{'✅' if ok else '❌'} 知识星球 cookie"
          + ("" if ok else "：需包含 zsxq_access_token"))


    # 列表接口是否已登记（登录抓取成功的关键标志）
    print("\n--- 接口登记状态 ---")
    eps = load_endpoints()
    for src, name, label in [
        ("alphapai", "daily_list", "Alpha派 每日必看列表"),
        ("jiuyan", "article_list", "韭研公社 文章列表"),
    ]:
        got = (eps.get(src) or {}).get(name)
        if got:
            print(f"✅ {label} → {got.get('url', '')}")
        else:
            print(f"❌ {label} 未登记：请在菜单里重新登录一次该网站")

    ok = all((eps.get(s) or {}).get(n) for s, n in
             [("alphapai", "daily_list"), ("jiuyan", "article_list")])
    print("\n" + ("🎉 全部就绪，可以选 [4] 抓取数据了"
                  if ok else "⚠️  还有网站没抓通，但不影响其他章节，也可先选 [4] 试跑"))


if __name__ == "__main__":
    main()
