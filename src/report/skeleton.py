"""生成报告骨架 report_skeleton.md：
定量章节（指数技术数据、热榜对比、资金榜、日历、电报）直接填好；
定性章节（内容总结、交叉验证、见底判断、荐股）附上原始素材 + 待Claude撰写标记。
最终报告由 Claude 阅读骨架与 data/日期/*.json 后撰写为 report.md（流程见 CLAUDE.md）。
"""

import os

from ..config import day_dir, load_config, load_json
from ..analysis.heat import cross_source_mentions, hot_list_delta
from ..analysis.signals import index_snapshot
from ..analysis.watchlist import grade_watchlist

TODO = "> ⬜ **待Claude撰写**：阅读上方素材与 data/{date}/ 原始数据后完成本节分析。\n"


def _fmt_index(snap: dict) -> str:
    ma = snap["ma"]
    macd = snap["macd"]
    hist_dir = "收窄" if abs(macd["hist"]) < abs(macd["hist_prev"]) else "放大"
    lines = [
        f"**{snap['name']}**（{snap['date']}）收 {snap['close']}，{snap['pct_chg']:+.2f}%",
        f"- 均线：MA5 {ma['ma5']} / MA10 {ma['ma10']} / MA20 {ma['ma20']} / MA60 {ma['ma60']}",
        f"- MACD：DIF {macd['dif']}，DEA {macd['dea']}，柱 {macd['hist']}（较前日{hist_dir}）"
        f"；RSI14 {snap['rsi14']}；KDJ K{snap['kdj']['k']} D{snap['kdj']['d']} J{snap['kdj']['j']}",
    ]
    if snap["divergences"]:
        for s in snap["divergences"]:
            lines.append(f"- ⚠️ **{s['indicator']} {s['type']}**：{s['detail']}")
    else:
        lines.append("- 背离：暂无有效背离信号")
    if snap["breakouts"]:
        for s in snap["breakouts"]:
            lines.append(f"- 🔔 **{s['type']}**：{s['detail']}")
    return "\n".join(lines)


def _fmt_fundflow_table(rows: list[dict]) -> str:
    if not rows:
        return "（无数据）"
    out = ["| 排名 | 名称 | 近5日主力净流入(亿) | 近5日涨跌幅% |", "| --- | --- | --- | --- |"]
    for i, r in enumerate(rows):
        out.append(f"| {i + 1} | {r['name']} | {r['main_net_5d_yi']} | {r['pct_chg_5d']} |")
    return "\n".join(out)


def _fmt_hot_delta(delta: dict) -> str:
    lines = [f"（对比基准：{delta.get('compared_with') or '无历史快照，首日运行'}）", ""]
    for title, key, fmt in [
        ("🔥 升温最快", "rising", lambda x: f"{x['name']} 第{x['rank_prev']}→第{x['rank']}名（↑{x['rank_delta']}）"),
        ("❄️ 降温最快", "falling", lambda x: f"{x['name']} 第{x['rank_prev']}→第{x['rank']}名（↓{-x['rank_delta']}）"),
        ("🆕 新上榜", "new_entries", lambda x: f"{x['name']} 第{x['rank']}名"),
        ("📉 掉出榜单", "dropped", lambda x: f"{x['name']}（昨日第{x['rank']}名）"),
    ]:
        items = delta.get(key) or []
        lines.append(f"**{title}**：" + ("、".join(fmt(x) for x in items[:10]) if items else "无"))
    return "\n".join(lines)


def build_skeleton(date_str: str) -> str:
    cfg = load_config()
    em = load_json(date_str, "eastmoney") or {}
    ths = load_json(date_str, "ths") or {}
    cls_data = load_json(date_str, "cls") or {}
    wscn = load_json(date_str, "wscn") or {}
    zsxq = load_json(date_str, "zsxq") or {}
    jiuyan = load_json(date_str, "jiuyan") or {}
    xueqiu = load_json(date_str, "xueqiu") or {}
    alphapai = load_json(date_str, "alphapai") or {}
    todo = TODO.format(date=date_str)

    # ---- 计算 ----
    index_snaps = []
    for name, kl in (em.get("indexes") or {}).items():
        if isinstance(kl, list) and len(kl) > 60:
            index_snaps.append(index_snapshot(name, kl, cfg))
    delta = hot_list_delta(date_str)
    resolved = em.get("watchlist_names") or {}
    names = [resolved.get(w["code"]) or w["name"] for w in cfg.get("watchlist", [])]
    names += [x["name"] for x in ths.get("hot_stocks") or []]
    names = [n for n in names if n]
    mentions = cross_source_mentions(date_str, names)
    graded = grade_watchlist(date_str, cfg, mentions)
    ff = em.get("fundflow") or {}

    S = []  # sections
    S.append(f"# 舆情交叉分析报告 · {date_str}\n")

    S.append("## 今日核心\n" + todo)

    S.append("## 〇 · 大盘技术研判（上证指数 / 科创50 / 创业板指）\n")
    for snap in index_snaps:
        S.append(_fmt_index(snap) + "\n")
    S.append("**走势预判与见底判断**（重点：背离信号、趋势突破、市场何时见底）\n" + todo)

    S.append("## 一 · 持仓舆情预警（监控池信号分级）\n")
    if graded:
        S.append("| 级别 | 股票 | 得分 | 信号 |\n| --- | --- | --- | --- |")
        for g in graded:
            S.append(f"| {g['level']} | {g['name']}({g['code']}) | {g['score']} | {'；'.join(g['signals']) or '—'} |")
        S.append("")
    else:
        S.append("（监控池为空：请在 config/config.yaml → watchlist 填入15只个股）\n")

    S.append("## 二 · 风险热度事件\n" + todo)
    S.append("## 三 · 机会热度事件\n" + todo)
    S.append("## 四 · 主线热度事件\n" + todo)

    S.append("## 五 · 热度变化（同花顺热榜对比）\n")
    S.append(_fmt_hot_delta(delta) + "\n")
    hot20 = (ths.get("hot_stocks") or [])[:20]
    if hot20:
        S.append("**当前热榜Top20**：" + "、".join(f"{x['rank']}.{x['name']}" for x in hot20) + "\n")
    S.append("**热度解读**\n" + todo)

    S.append("## 六~八 · 行业/公司深度（MLCC、存储、消费等板块逻辑）\n" + todo)

    S.append("## 九 · 星球重点股票提醒（黑金会员星球）\n")
    if zsxq:
        S.append(f"- 24h 帖数：**{zsxq.get('total_24h', 0)}**，其中文字帖 {len(zsxq.get('talk_posts') or [])} 篇")
        for t in (zsxq.get("talk_posts") or [])[:30]:
            txt = (t.get("text") or "").replace("\n", " ")[:200]
            S.append(f"  - [{t.get('time', '')[:16]}] {txt}")
        S.append("")
    else:
        S.append("（未抓到数据：检查 zsxq cookie）\n")
    S.append("**文字帖内容归纳 + 个股提及统计**\n" + todo)

    S.append("## 十 · Alpha派推荐与点评（蓝宝书 / PaiPai每日必看）\n")
    if alphapai.get("errors"):
        S.append("抓取状态：" + "；".join(alphapai["errors"]) + "\n")
    S.append("**每日必看内容归纳 + 24h提及统计 + 重点研报**\n" + todo)

    S.append("## 十一 · 公社精选（韭研公社·关注栏目）\n")
    if jiuyan:
        S.append(f"- 抓取帖子共 {jiuyan.get('total_articles', 0)} 篇；关注栏目命中 {len(jiuyan.get('focus_details') or [])} 篇；精选内链帖 {len(jiuyan.get('linked_details') or [])} 篇")
        for d in (jiuyan.get("focus_details") or [])[:20]:
            S.append(f"  - 《{d.get('title')}》")
        S.append("")
    else:
        S.append("（未抓到数据：检查 jiuyan token）\n")
    S.append("**每日公社内容精选（含链接帖全文）、学习笔记、公告内容精选、盘前纪要 总结分析**\n" + todo)

    S.append("## 十二 · 雪球高讨论帖\n")
    for p in (xueqiu.get("hot_posts") or [])[:15]:
        S.append(f"- 《{p.get('title') or (p.get('text') or '')[:40]}》 评论{p.get('replies')} 赞{p.get('likes')} — {p.get('user')}")
    S.append("\n**热帖观点归纳**\n" + todo)

    S.append("## 十三 · 政策信号（已证实/传闻分级）\n" + todo)
    S.append("## 十四 · 各方判断比对\n" + todo)
    S.append("## 十五 · 交叉验证\n")
    top_mentions = list(mentions.get("mentions", {}).items())[:20]
    if top_mentions:
        S.append("跨源提及统计（来源数优先）：")
        for name, m in top_mentions:
            srcs = "、".join(f"{k}×{v}" for k, v in m["sources"].items())
            S.append(f"- **{name}**：{m['total']}次 / {m['source_count']}个来源（{srcs}）")
        S.append("")
    S.append(todo)
    S.append("## 十六 · 小作文（待核实传闻）\n" + todo)

    S.append("## 十七 · 财联社电报精选（时间线）\n")
    tele = cls_data.get("telegraphs") or []
    red = [t for t in tele if t.get("is_red")]
    for t in (red or tele)[:25]:
        title = t.get("title") or (t.get("content") or "")[:60]
        S.append(f"- **{t.get('time', '')[-5:]}** {title}")
    S.append("\n**电报解读**\n" + todo)

    S.append("## 十八 · 中美财经日历（华尔街见闻·三星及以上）\n")
    cal = wscn.get("calendar") or []
    if cal:
        S.append("| 时间 | 国家 | ★ | 事件 | 前值 | 预期 | 实际 |\n| --- | --- | --- | --- | --- | --- | --- |")
        for c in cal:
            S.append(f"| {c['time']} | {c['country']} | {c['importance']} | {c['title']} | {c.get('previous') or '—'} | {c.get('forecast') or '—'} | {c.get('actual') or '—'} |")
        S.append("")
    else:
        S.append("（无数据或抓取失败）\n")

    S.append("## 十九 · 资金榜（近5日主力净流入 Top20）\n")
    S.append("### 概念板块\n" + _fmt_fundflow_table(ff.get("concept_top20_5d") or []) + "\n")
    S.append("### 行业板块\n" + _fmt_fundflow_table(ff.get("industry_top20_5d") or []) + "\n")
    S.append("### 个股\n" + _fmt_fundflow_table(ff.get("stock_top20_5d") or []) + "\n")

    S.append("## 二十 · 综合研判：热度最高与升温最快的行业/个股\n" + todo)
    S.append("## 二一 · 明日最值得关注的3只股票（附逻辑与风险）\n" + todo)
    S.append("\n---\n*数据来源：雪球/同花顺/Alpha派/韭研公社/知识星球/财联社/华尔街见闻/东方财富。本报告为舆情信息聚合分析，不构成投资建议。*\n")
    return "\n".join(S)


def write_skeleton(date_str: str) -> str:
    content = build_skeleton(date_str)
    path = os.path.join(day_dir(date_str), "report_skeleton.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
