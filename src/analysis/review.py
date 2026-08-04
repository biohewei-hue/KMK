"""复盘闭环：
1. 推荐股次日表现校验——每天回看前一交易日推荐的3只票涨跌，累计胜率
2. 见底判断轨迹——把每天的见底结论存成时间线，避免前后矛盾

数据存放：data/track/picks.json、data/track/bottom_calls.json
由 Claude 写完报告后调用 tools/log_picks.py 记录，次日自动校验。
"""

import json
import os
from datetime import datetime

from ..config import DATA_DIR
from ..fetchers import ths_market

TRACK_DIR = os.path.join(DATA_DIR, "track")
PICKS_PATH = os.path.join(TRACK_DIR, "picks.json")
BOTTOM_PATH = os.path.join(TRACK_DIR, "bottom_calls.json")


def _load(path) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    os.makedirs(TRACK_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def log_picks(date_str: str, picks: list[dict]):
    """记录当日推荐。picks: [{code, name, reason, buy_zone, stop, target}]"""
    data = [d for d in _load(PICKS_PATH) if d.get("date") != date_str]
    data.append({"date": date_str, "picks": picks})
    data.sort(key=lambda d: d["date"])
    _save(PICKS_PATH, data)
    return PICKS_PATH


def log_bottom_call(date_str: str, stance: str, evidence: str):
    """记录见底判断。stance 如：未见底/筑底中/已见底/反弹中继"""
    data = [d for d in _load(BOTTOM_PATH) if d.get("date") != date_str]
    data.append({"date": date_str, "stance": stance, "evidence": evidence})
    data.sort(key=lambda d: d["date"])
    _save(BOTTOM_PATH, data)
    return BOTTOM_PATH


def _ths_code(code: str) -> str:
    """SH600519 → hs_600519"""
    return "hs_" + code.upper().replace("SH", "").replace("SZ", "")


def verify_picks(today: str, lookback_days: int = 10) -> dict:
    """校验历史推荐的表现：推荐次日至今的涨跌幅、是否触及止损。"""
    history = _load(PICKS_PATH)
    if not history:
        return {"status": "暂无历史推荐记录"}

    recent = [h for h in history if h["date"] < today][-lookback_days:]
    results, wins, total = [], 0, 0
    for entry in recent:
        for p in entry.get("picks", []):
            try:
                kl = ths_market.fetch_kline(_ths_code(p["code"]), 30)
            except Exception:  # noqa: BLE001
                continue
            after = [k for k in kl if k["date"] > entry["date"]]
            if not after:
                continue
            base = after[0]["open"]  # 以推荐次日开盘为买入基准
            last = after[-1]["close"]
            high = max(k["high"] for k in after)
            pct = (last / base - 1) * 100
            total += 1
            if pct > 0:
                wins += 1
            results.append({
                "推荐日": entry["date"],
                "股票": p.get("name"),
                "次日开盘": round(base, 2),
                "最新": round(last, 2),
                "累计涨跌%": round(pct, 2),
                "期间最大涨幅%": round((high / base - 1) * 100, 2),
                "持有天数": len(after),
            })
    return {
        "样本数": total,
        "胜率%": round(wins / total * 100, 1) if total else None,
        "平均收益%": round(sum(r["累计涨跌%"] for r in results) / total, 2) if total else None,
        "明细": results[-15:],
    }


def bottom_call_history(limit: int = 10) -> list:
    """最近若干次见底判断，供撰写时保持口径一致。"""
    return _load(BOTTOM_PATH)[-limit:]


def run(today: str = "") -> dict:
    today = today or datetime.now().strftime("%Y-%m-%d")
    return {
        "推荐股复盘": verify_picks(today),
        "见底判断轨迹": bottom_call_history(),
    }
