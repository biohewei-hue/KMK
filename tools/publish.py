#!/usr/bin/env python3
"""发布报告：生成电脑版 HTML + 推送手机版到飞书。

  python tools/publish.py                 # 今天，两个都做
  python tools/publish.py 2026-08-03      # 指定日期
  python tools/publish.py --html-only     # 只生成 HTML，不推飞书
  python tools/publish.py --url https://...  # 卡片里附完整报告链接
"""

import argparse
import os
import sys
import webbrowser
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATA_DIR, load_credentials  # noqa: E402
from src.report.feishu import send  # noqa: E402
from src.report.render import render_file  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--feishu-only", action="store_true")
    ap.add_argument("--url", default="", help="完整报告的可访问链接，放进飞书卡片按钮")
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()

    md_path = os.path.join(DATA_DIR, args.date, "report.md")
    if not os.path.exists(md_path):
        print(f"❌ 找不到 {md_path}")
        print("   请先让 Claude 生成报告（说『生成今日报告』）")
        sys.exit(1)
    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    if not args.feishu_only:
        out = render_file(md_path)
        print(f"✅ 电脑版已生成：{out}")
        if not args.no_open:
            try:
                webbrowser.open("file://" + os.path.abspath(out))
            except Exception:  # noqa: BLE001
                pass

    if not args.html_only:
        creds = load_credentials()
        if not (creds.get("feishu") or {}).get("webhook"):
            print("⏭️  跳过飞书推送：未配置 webhook")
            print("   在菜单里选 [9] 配置飞书，或手动填 credentials.json → feishu.webhook")
            return
        try:
            send(md, args.date, creds, args.url)
            print("✅ 手机版已推送到飞书")
        except Exception as e:  # noqa: BLE001
            print(f"❌ 飞书推送失败：{e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
