#!/usr/bin/env python3
"""检查各站凭证有效性：Alpha派 JWT 剩余天数、其他源凭证是否已填。

用法：python tools/check_token.py
"""

import base64
import json
import sys
from datetime import datetime

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])

from src.config import load_credentials  # noqa: E402


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

    x = (creds.get("xueqiu") or {}).get("cookie", "")
    print(f"{'✅ 已配置登录 cookie' if x else 'ℹ️  未配置，将自动使用游客 token'} 雪球")


if __name__ == "__main__":
    main()
