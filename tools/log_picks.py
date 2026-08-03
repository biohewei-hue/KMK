#!/usr/bin/env python3
"""记录当日推荐股与见底判断，供次日自动复盘。

Claude 写完报告后调用，无需用户手动操作：
  python tools/log_picks.py 2026-08-03 --picks '[{"code":"SH688256","name":"寒武纪",
      "reason":"算力订单","buy_zone":"580-600","stop":"555","target":"700"}]' \
      --stance 筑底中 --evidence "MACD底背离+成交额地量"
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.review import log_bottom_call, log_picks  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--picks", help="JSON数组：[{code,name,reason,buy_zone,stop,target}]")
    ap.add_argument("--stance", help="见底判断：未见底/筑底中/已见底/反弹中继")
    ap.add_argument("--evidence", default="", help="判断依据一句话")
    args = ap.parse_args()

    if args.picks:
        picks = json.loads(args.picks)
        print(f"✅ 已记录 {len(picks)} 只推荐 → {log_picks(args.date, picks)}")
    if args.stance:
        print(f"✅ 已记录见底判断『{args.stance}』→ "
              f"{log_bottom_call(args.date, args.stance, args.evidence)}")


if __name__ == "__main__":
    main()
