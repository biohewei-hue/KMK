"""生成 brief.md（8章精简骨架）与 digest.json（压缩后的素材包）。

设计原则：
- 程序做机械活（算指标、排序、统计），输出紧凑事实，不堆砌原始列表
- Claude 只读 digest.json + brief.md 两个文件，不读 8 个原始 json
- 报告成品目标 4000 字，只给结论不给流水账
"""

import json
import os

from ..analysis.digest import build_digest, cross_source_ranking
from ..analysis.heat import cross_source_mentions, hot_list_delta
from ..analysis.review import run as run_review
from ..analysis.signals import index_snapshot
from ..config import day_dir, load_config, load_json

TODO = "> ⬜ **待撰写**\n"


def _fmt_index(s: dict) -> str:
    ma, macd = s["ma"], s["macd"]
    pos = []
    for k, label in [("ma5", "MA5"), ("ma20", "MA20"), ("ma60", "MA60")]:
        if ma[k]:
            pos.append(f"{label}{'上' if s['close'] > ma[k] else '下'}({ma[k]})")
    lines = [
        f"**{s['name']}** {s['close']} ({s['pct_chg']:+.2f}%) | " + "、".join(pos),
        f"  MACD {macd['dif']}/{macd['dea']} 柱{macd['hist']}"
        f"({'收窄' if abs(macd['hist']) < abs(macd['hist_prev']) else '放大'})"
        f" | RSI {s['rsi14']} | KDJ J{s['kdj']['j']}",
    ]
    for d in s["divergences"]:
        lines.append(f"  ⚠️ **{d['indicator']}{d['type']}**：{d['detail']}")
    if not s["divergences"]:
        lines.append("  背离：无")
    for b in s["breakouts"]:
        lines.append(f"  🔔 **{b['type']}**：{b['detail']}")
    return "\n".join(lines)


def _fmt_rank_table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "（无数据）"
    head = "| " + " | ".join(["#", "名称"] + cols) + " |"
    sep = "| " + " | ".join(["---"] * (len(cols) + 2)) + " |"
    out = [head, sep]
    for i, r in enumerate(rows, 1):
        vals = [str(r.get(c, "—")) for c in cols]
        out.append(f"| {i} | {r.get('name', '')} | " + " | ".join(vals) + " |")
    return "\n".join(out)


def _fmt_fundflow(rows: list[dict], n: int = 20) -> str:
    if not rows:
        return "（无数据）"
    return "、".join(
        f"{r['name']}({r['main_net_5d_yi']}亿)" for r in rows[:n]
    )


def _fmt_sentiment(sent: dict) -> str:
    b = sent.get("breadth") or {}
    lp = sent.get("limit_pool") or {}
    nb = sent.get("northbound") or {}
    lines = []
    if b:
        lines.append(
            f"涨{b['up']}/跌{b['down']} (涨占比{b['up_ratio']}%)｜"
            f"涨停{b['limit_up']} 跌停{b['limit_down']}｜两市成交{b['amount_yi']:.0f}亿"
        )
    if lp and not lp.get("error"):
        leaders = "、".join(f"{x['name']}{x['boards']}板" for x in (lp.get("leaders") or [])[:5])
        lines.append(
            f"连板高度**{lp['max_boards']}板**｜2板以上{lp['boards_2plus']}只｜"
            f"炸板率{lp['broken_rate']}%｜高标：{leaders or '无'}"
        )
    if nb.get("net_yi") is not None:
        lines.append(f"北向净流入 {nb['net_yi']}亿")
    return "\n".join(f"- {x}" for x in lines) or "（数据缺失）"


def build(date_str: str) -> tuple[str, dict]:
    cfg = load_config()
    em = load_json(date_str, "eastmoney") or {}
    ths = load_json(date_str, "ths") or {}
    wscn = load_json(date_str, "wscn") or {}
    sent = load_json(date_str, "sentiment") or {}

    # 计算
    snaps = [
        index_snapshot(name, kl, cfg)
        for name, kl in (em.get("indexes") or {}).items()
        if isinstance(kl, list) and len(kl) > 60
    ]
    delta = hot_list_delta(date_str)
    resolved = em.get("watchlist_names") or {}
    names = [resolved.get(w["code"]) or w["name"] for w in cfg.get("watchlist", [])]
    names += [x["name"] for x in ths.get("hot_stocks") or []]
    mentions = cross_source_mentions(date_str, [n for n in names if n])
    ranking = cross_source_ranking(date_str, cfg, mentions, delta)
    ff = em.get("fundflow") or {}

    # 监控池异动（只列有信号的，不列打分表）
    watch_hits = []
    hot_rank = {x["name"]: x["rank"] for x in ths.get("hot_stocks") or []}
    ff_names = {x["name"] for x in ff.get("stock_top20_5d") or []}
    for w in cfg.get("watchlist", []):
        nm = resolved.get(w["code"]) or w["name"]
        if not nm:
            continue
        sig = []
        m = (mentions.get("mentions") or {}).get(nm)
        if m and m["source_count"] >= 2:
            sig.append(f"{m['source_count']}源提及{m['total']}次")
        if nm in hot_rank:
            sig.append(f"热榜第{hot_rank[nm]}")
        if nm in ff_names:
            sig.append("资金榜Top20")
        if sig:
            watch_hits.append(f"{nm}：" + "、".join(sig))

    S = [f"# 舆情研判 · {date_str}\n"]

    S.append("## 一、今日结论\n")
    S.append("（市场状态 / 见底判断 / 明日操作倾向 / 3只推荐股各一句）\n" + TODO)

    S.append("## 二、大盘研判与见底判断\n")
    for s in snaps:
        S.append(_fmt_index(s) + "\n")
    S.append("**市场情绪**\n" + _fmt_sentiment(sent) + "\n")
    S.append("**研判**（技术图形 + 多源观点交叉 → 未来走势大概率形态 + 见底判断）\n" + TODO)

    S.append("## 三、热度榜\n")
    S.append("**热度最高**\n" + _fmt_rank_table(
        ranking["热度最高"], ["提及", "源数", "热榜名次", "主力5日净流入亿"]) + "\n")
    S.append("**升温最快**\n" + _fmt_rank_table(
        ranking["升温最快"], ["名次变化", "提及", "源数"]) + "\n")
    fall = ranking["降温最快"]
    S.append("**降温最快**：" + ("、".join(
        f"{x['name']}(第{x['rank_prev']}→{x['rank']})" for x in fall) if fall else "无") + "\n")
    S.append("**升温原因解读**\n" + TODO)

    if watch_hits:
        S.append("## 三·补 · 我的持仓异动\n" + "\n".join(f"- {h}" for h in watch_hits) + "\n")

    S.append("## 四、资金榜（近5日主力净流入Top20）\n")
    S.append("**概念**：" + _fmt_fundflow(ff.get("concept_top20_5d") or []) + "\n")
    S.append("**行业**：" + _fmt_fundflow(ff.get("industry_top20_5d") or []) + "\n")
    S.append("**个股**：" + _fmt_fundflow(ff.get("stock_top20_5d") or []) + "\n")

    S.append("## 五、今日最重要的信息\n")
    S.append("（读 digest.json 后按**重要性**排序，不按来源分类。"
             "每条格式：结论｜来源标签｜影响标的｜时效｜可信度）\n" + TODO)

    S.append("## 六、各源精华\n")
    S.append("（公社/星球/Alpha派/雪球，每源只留最重要3-5条）\n" + TODO)

    S.append("## 七、日历与风险（中美三星及以上）\n")
    cal = wscn.get("calendar") or []
    if cal:
        for c in cal[:15]:
            S.append(f"- {c['time']} [{c['country']}] {'★' * int(c['importance'])} "
                     f"{c['title']}（前值{c.get('previous') or '—'} 预期{c.get('forecast') or '—'}）")
    else:
        S.append("（无数据）")
    S.append("")

    S.append("## 八、明日推荐（3只）\n")
    S.append("（逻辑｜催化剂｜买点位｜止损位｜目标空间｜风险。按当日行情自由判断风格）\n" + TODO)

    review = run_review(date_str)
    rv = review.get("推荐股复盘") or {}
    S.append("## 附 · 复盘\n")
    if rv.get("样本数"):
        S.append(f"历史推荐 {rv['样本数']} 次，胜率 {rv['胜率%']}%，平均收益 {rv['平均收益%']}%")
        for r in (rv.get("明细") or [])[-6:]:
            S.append(f"- {r['推荐日']} {r['股票']}：{r['累计涨跌%']:+.2f}%"
                     f"（最大 {r['期间最大涨幅%']:+.2f}%，持有{r['持有天数']}天）")
    else:
        S.append(rv.get("status", "暂无历史推荐记录"))
    hist = review.get("见底判断轨迹") or []
    if hist:
        S.append("\n**见底判断轨迹**（保持口径一致）")
        for h in hist[-6:]:
            S.append(f"- {h['date']}：{h['stance']}")
    S.append("")

    S.append("\n---\n*信息聚合分析，不构成投资建议。*\n")

    digest = build_digest(date_str, cfg)
    digest["复盘"] = review
    return "\n".join(S), digest


def write_skeleton(date_str: str) -> str:
    brief, digest = build(date_str)
    d = day_dir(date_str)
    brief_path = os.path.join(d, "brief.md")
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief)
    with open(os.path.join(d, "digest.json"), "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=1)
    return brief_path
