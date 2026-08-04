#!/usr/bin/env python3
"""舆情交叉分析报告 · 主入口

用法：
  python run_daily.py --fetch    # 抓取所有数据源 → data/YYYY-MM-DD/*.json
  python run_daily.py --report   # 生成骨架 → brief.md + digest.json
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
    "ths_market": ("同花顺行情(指数K线/资金榜)", False),
    "ths": ("同花顺热榜", False),
    "cls": ("财联社电报", False),
    "wscn": ("华尔街见闻日历", False),
    "sentiment": ("市场情绪(连板/炸板率/成交额)", False),
    "zsxq": ("知识星球", True),
    "jiuyan": ("韭研公社", True),
    "alphapai": ("Alpha派", True),
}


def _market_with_fallback(cfg: dict, creds: dict) -> dict:
    """同花顺为主；指数K线或资金榜任一落空时，用东方财富补齐缺的那部分。"""
    from src.fetchers import eastmoney, ths_market

    data = ths_market.fetch_all(cfg, creds)
    data["source"] = "同花顺"
    need_idx = not data.get("indexes")
    need_ff = not any((data.get("fundflow") or {}).values())
    if not (need_idx or need_ff):
        return data

    print("[ths_market] ⚠️  同花顺部分数据为空，用东方财富兜底 ...", flush=True)
    try:
        em = eastmoney.fetch_all(cfg)
    except Exception as e:  # noqa: BLE001
        data.setdefault("errors", []).append(f"东财兜底也失败: {str(e)[:100]}")
        return data

    if need_idx and em.get("indexes"):
        data["indexes"] = em["indexes"]
        data["watchlist_kline"] = em.get("watchlist_kline") or data.get("watchlist_kline")
        data["watchlist_names"] = em.get("watchlist_names")
        data["source"] = "同花顺(指数用东财兜底)"
    if need_ff and any((em.get("fundflow") or {}).values()):
        data["fundflow"] = em["fundflow"]
        data["source"] = data["source"] + "+资金榜东财兜底"
    return data


def do_fetch(date_str: str, only: set[str] | None):
    cfg = load_config()
    creds = load_credentials()
    from src.fetchers import (
        alphapai, cls, jiuyan, sentiment, ths, ths_market, wscn, zsxq,
    )

    modules = {
        "ths_market": lambda: _market_with_fallback(cfg, creds),
        "ths": lambda: ths.fetch_all(cfg, creds),
        "cls": lambda: cls.fetch_all(cfg),
        "wscn": lambda: wscn.fetch_all(cfg),
        "sentiment": lambda: sentiment.fetch_all(cfg, date_str, creds),
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
            if key == "ths_market":
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

    root = os.path.dirname(os.path.abspath(__file__))
    tool = os.path.join(root, "tools", "harvest_token.py")
    for site in sites:
        # 没有浏览器 profile 说明从未登录过，静默续期必然失败，直接给出明确指引
        profile = os.path.join(root, "config", ".browser_profile", site)
        if not os.path.isdir(profile):
            print(f"[refresh] ⏭️  跳过 {site}：还没登录过")
            print(f"[refresh]     请先在菜单里选 [{'3' if site == 'jiuyan' else '2'}] 登录一次")
            continue

        print(f"[refresh] 刷新 {site} 凭证 ...", flush=True)
        r = subprocess.run(
            [sys.executable, tool, site, "--headless"], capture_output=True, text=True
        )
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0:
            if r.stderr.strip():  # 真实原因在 stderr 里，必须打出来
                print("[refresh] 错误详情：")
                print("   " + r.stderr.strip()[-800:].replace("\n", "\n   "))
            print(f"[refresh] ⚠️  {site} 刷新失败，将使用 credentials.json 中的现有凭证")


def do_report(date_str: str):
    from src.report.skeleton import write_skeleton

    path = write_skeleton(date_str)
    print(f"✅ 骨架已生成：{path}")
    print(f"   素材包：{os.path.join(os.path.dirname(path), 'digest.json')}")
    print("下一步：在本仓库打开 Claude Code，说『生成今日报告』。")


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
