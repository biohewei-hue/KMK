#!/usr/bin/env python3
"""舆情交叉分析报告 · 主入口

用法：
  python run_daily.py --fetch    # 抓取所有数据源 → data/YYYY-MM-DD/*.json
  python run_daily.py --report   # 生成报告骨架 → data/YYYY-MM-DD/report_skeleton.md
  python run_daily.py --all      # 抓取 + 骨架
  python run_daily.py --fetch --only ths,cls   # 只抓部分源
  python run_daily.py --date 2026-08-02        # 指定日期
"""

import argparse
import os
import sys
import traceback
from datetime import datetime

from src.config import load_config, load_credentials, save_json

FETCHERS = {
    "eastmoney": ("东方财富(指数K线/资金榜)", False),
    "ths": ("同花顺热榜", False),
    "cls": ("财联社电报", False),
    "wscn": ("华尔街见闻日历", False),
    "xueqiu": ("雪球", True),
    "zsxq": ("知识星球", True),
    "jiuyan": ("韭研公社", True),
    "alphapai": ("Alpha派", True),
}


def do_fetch(date_str: str, only: set[str] | None):
    cfg = load_config()
    creds = load_credentials()
    from src.fetchers import alphapai, cls, eastmoney, jiuyan, ths, wscn, xueqiu, zsxq

    modules = {
        "eastmoney": lambda: eastmoney.fetch_all(cfg),
        "ths": lambda: ths.fetch_all(cfg, creds),
        "cls": lambda: cls.fetch_all(cfg),
        "wscn": lambda: wscn.fetch_all(cfg),
        "xueqiu": lambda: xueqiu.fetch_all(cfg, creds),
        "zsxq": lambda: zsxq.fetch_all(cfg, creds),
        "jiuyan": lambda: jiuyan.fetch_all(cfg, creds),
        "alphapai": lambda: alphapai.fetch_all(cfg, creds),
    }
    errors = {}
    for key, fn in modules.items():
        if only and key not in only:
            continue
        label, needs_cred = FETCHERS[key]
        print(f"[{key}] 抓取 {label} ...", flush=True)
        try:
            data = fn()
            save_json(date_str, key, data)
            print(f"[{key}] ✅ 已保存 data/{date_str}/{key}.json")
            if key == "eastmoney":
                # 用东财解析出的真实名称补全监控池（供后续雪球搜索等使用）
                resolved = data.get("watchlist_names") or {}
                for w in cfg.get("watchlist", []):
                    if resolved.get(w["code"]):
                        w["name"] = resolved[w["code"]]
        except Exception as e:  # noqa: BLE001
            errors[key] = str(e)
            hint = "（需在 config/credentials.json 配置凭证）" if needs_cred else ""
            print(f"[{key}] ❌ {e} {hint}")
            traceback.print_exc()
    if errors:
        save_json(date_str, "_fetch_errors", errors)
    print(f"\n完成：{len(modules) - len(errors)} 成功 / {len(errors)} 失败")


def do_refresh(sites: list[str]):
    """抓取前用浏览器刷新易过期的凭证（韭研公社 token 每次请求都变）。"""
    import subprocess

    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "harvest_token.py")
    for site in sites:
        print(f"[refresh] 刷新 {site} 凭证 ...", flush=True)
        r = subprocess.run(
            [sys.executable, tool, site, "--headless"], capture_output=True, text=True
        )
        print(r.stdout.strip() or r.stderr.strip()[:400])
        if r.returncode != 0:
            print(f"[refresh] ⚠️  {site} 刷新失败，将使用 credentials.json 中的现有凭证")
            print(f"[refresh]     首次使用请先跑：python tools/harvest_token.py {site}")


def do_report(date_str: str):
    from src.report.skeleton import write_skeleton

    path = write_skeleton(date_str)
    print(f"✅ 报告骨架已生成：{path}")
    print("下一步：在本仓库打开 Claude Code，说『生成今日报告』，Claude 会按 CLAUDE.md 流程完成分析章节。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", help="逗号分隔的数据源: " + ",".join(FETCHERS))
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument(
        "--refresh",
        nargs="?",
        const="jiuyan,alphapai",
        help="抓取前用浏览器刷新凭证（默认 jiuyan,alphapai）",
    )
    args = ap.parse_args()
    if not (args.fetch or args.report or args.all):
        ap.print_help()
        sys.exit(1)
    only = set(args.only.split(",")) if args.only else None
    if args.refresh:
        do_refresh(args.refresh.split(","))
    if args.fetch or args.all:
        do_fetch(args.date, only)
    if args.report or args.all:
        do_report(args.date)


if __name__ == "__main__":
    main()
