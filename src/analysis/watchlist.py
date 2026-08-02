"""监控池个股信号分级：强关注 / 关注 / 观察。

打分维度：
- 舆情：跨源提及数与来源数（雪球/同花顺热榜/Alpha派/韭研公社/星球/财联社）
- 热榜：是否上同花顺热榜、排名变化
- 技术：背离/突破信号
- 资金：是否进入近5日主力净流入Top20
"""

from ..config import load_json
from .signals import detect_breakouts, detect_divergence


def grade_watchlist(date_str: str, cfg: dict, mentions: dict) -> list[dict]:
    em = load_json(date_str, "eastmoney") or {}
    ths = load_json(date_str, "ths") or {}
    hot = {x["name"]: x for x in ths.get("hot_stocks") or []}
    ff_names = {x["name"] for x in (em.get("fundflow") or {}).get("stock_top20_5d") or []}
    klines = em.get("watchlist_kline") or {}
    resolved = em.get("watchlist_names") or {}
    sig_cfg = cfg.get("signals", {})

    out = []
    for w in cfg.get("watchlist", []):
        code = w["code"]
        name = resolved.get(code) or w["name"]  # 东财解析的真实名称优先
        if not name:
            continue
        score = 0
        reasons = []

        m = mentions.get("mentions", {}).get(name)
        for alias in w.get("aliases") or []:
            am = mentions.get("mentions", {}).get(alias)
            if am and (not m or am["total"] > m["total"]):
                m = am
        if m:
            score += min(m["total"], 10) + m["source_count"] * 2
            srcs = "、".join(f"{k}×{v}" for k, v in m["sources"].items())
            reasons.append(f"舆情提及 {m['total']} 次（{srcs}）")

        if name in hot:
            h = hot[name]
            score += 5
            reasons.append(f"同花顺热榜第{h['rank']}名")

        kl = klines.get(code)
        if isinstance(kl, list) and len(kl) > 60:
            divs = detect_divergence(kl, sig_cfg.get("divergence_lookback", 60))
            brks = detect_breakouts(
                kl,
                tuple(sig_cfg.get("breakout_windows", [20, 60])),
                sig_cfg.get("volume_spike_ratio", 1.5),
            )
            for s in divs:
                score += 4
                reasons.append(f"{s['indicator']}{s['type']}")
            for s in brks:
                score += 3
                reasons.append(f"{s['type']}：{s['detail']}")

        if name in ff_names:
            score += 4
            reasons.append("近5日主力净流入Top20")

        level = "强关注" if score >= 15 else ("关注" if score >= 7 else "观察")
        out.append(
            {"code": code, "name": name, "level": level, "score": score, "signals": reasons}
        )
    out.sort(key=lambda x: -x["score"])
    return out
