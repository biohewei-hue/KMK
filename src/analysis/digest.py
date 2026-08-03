"""把 8 个原始 json 压缩成一个 digest.json，供 Claude 单文件读取。

四步压缩：去模板 → 去重合并 → 限长 → 按价值排序。
目标：读入从 ~100k tokens 降到 ~20k。
"""

import re
from collections import defaultdict

from ..config import load_json

# 每源正文长度上限（字符）
LIMITS = {
    "jiuyan_focus": 2000,   # 公社精选/学习笔记/盘前纪要（最高价值，给最多额度）
    "jiuyan_linked": 1200,  # 精选帖内链接指向的帖子
    "alphapai": 1500,       # 蓝宝书/每日必看
    "zsxq": 800,            # 星球文字帖
    "xueqiu": 300,          # 雪球热帖
    "cls": 150,             # 财联社电报
}

# 各源保留条数上限
COUNTS = {
    "jiuyan_focus": 12, "jiuyan_linked": 15, "alphapai": 12,
    "zsxq": 30, "xueqiu": 12, "cls": 40,
}

# 模板化噪音：免责声明、推广、页脚
NOISE = [
    r"风险提示[：:][^\n]{0,200}",
    r"本文[^\n]{0,30}不构成[^\n]{0,100}",
    r"投资有风险[^\n]{0,100}",
    r"以上内容仅供参考[^\n]{0,100}",
    r"版权[^\n]{0,60}",
    r"更多[^\n]{0,20}请关注[^\n]{0,60}",
    r"扫码[^\n]{0,40}",
    r"点击[^\n]{0,10}(阅读原文|查看详情)[^\n]{0,20}",
    r"https?://\S+",
]
_NOISE_RE = re.compile("|".join(NOISE))
_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")

# PDF/音频等附件：只留标题不解析内容
ATTACHMENT_RE = re.compile(r"\.(pdf|mp3|m4a|wav|mp4|docx?|pptx?|xlsx?)$", re.I)


def clean(text: str) -> str:
    if not text:
        return ""
    t = _NOISE_RE.sub("", text)
    t = _WS_RE.sub(" ", t)
    return _NL_RE.sub("\n\n", t).strip()


def _fingerprint(text: str) -> str:
    """用于判重：取前后各40个非空白字符。"""
    s = re.sub(r"\s+", "", text)
    return s[:40] + s[-40:] if len(s) > 80 else s


def dedupe(items: list[dict]) -> list[dict]:
    """跨源去重：正文指纹相同的合并，记录出现过的所有来源。"""
    seen: dict[str, dict] = {}
    for it in items:
        fp = _fingerprint(it.get("text") or it.get("title") or "")
        if not fp:
            continue
        if fp in seen:
            src = it.get("source")
            if src and src not in seen[fp]["sources"]:
                seen[fp]["sources"].append(src)
        else:
            it = dict(it)
            it["sources"] = [it.get("source")] if it.get("source") else []
            seen[fp] = it
    return list(seen.values())


def _trim(text: str, limit: int) -> str:
    t = clean(text)
    if len(t) <= limit:
        return t
    return t[:limit] + f"…（原文共{len(t)}字，已截断）"


def build_digest(date_str: str, cfg: dict) -> dict:
    """汇总各源精华。结构扁平，便于 Claude 一次读完。"""
    d: dict = {"date": date_str, "sources": {}}

    # —— 韭研公社：关注栏目（最高价值）——
    jy = load_json(date_str, "jiuyan") or {}
    focus, linked = [], []
    for a in (jy.get("focus_details") or [])[: COUNTS["jiuyan_focus"]]:
        focus.append({
            "title": a.get("title"),
            "time": a.get("time"),
            "text": _trim(a.get("text") or "", LIMITS["jiuyan_focus"]),
        })
    for a in (jy.get("linked_details") or [])[: COUNTS["jiuyan_linked"]]:
        linked.append({
            "title": a.get("title"),
            "text": _trim(a.get("text") or "", LIMITS["jiuyan_linked"]),
        })
    d["sources"]["韭研公社"] = {
        "栏目帖": focus, "精选内链帖": linked,
        "抓取状态": jy.get("errors") or "正常",
    }

    # —— Alpha派：蓝宝书 / 每日必看 ——
    ap = load_json(date_str, "alphapai") or {}
    ap_items = []
    for x in (ap.get("details") or [])[: COUNTS["alphapai"]]:
        ap_items.append({
            "title": x.get("title"),
            "text": _trim(x.get("text") or "", LIMITS["alphapai"]),
        })
    if not ap_items:  # 没抓到正文时退回列表标题
        ap_items = [
            {"title": x.get("title"), "text": _trim(x.get("text") or "", 300)}
            for x in (ap.get("daily_must_read") or [])[: COUNTS["alphapai"]]
        ]
    d["sources"]["Alpha派"] = {"每日必看": ap_items, "抓取状态": ap.get("errors") or "正常"}

    # —— 知识星球：文字帖全文；PDF/音频只留标题 ——
    zx = load_json(date_str, "zsxq") or {}
    talks, attachments = [], []
    for t in (zx.get("talk_posts") or [])[: COUNTS["zsxq"]]:
        files = t.get("files") or []
        att = [f for f in files if f and ATTACHMENT_RE.search(f)]
        if att:
            attachments.extend(att)
        txt = _trim(t.get("text") or "", LIMITS["zsxq"])
        if txt:
            talks.append({"time": (t.get("time") or "")[:16], "text": txt})
    d["sources"]["知识星球"] = {
        "24h帖数": zx.get("total_24h", 0),
        "文字帖": talks,
        "附件标题": attachments[:20],  # PDF/音频不解析内容
    }

    # —— 雪球：热帖观点 ——
    xq = load_json(date_str, "xueqiu") or {}
    posts = sorted(
        xq.get("hot_posts") or [], key=lambda p: -(p.get("replies") or 0)
    )[: COUNTS["xueqiu"]]
    d["sources"]["雪球"] = [
        {
            "title": p.get("title") or "",
            "text": _trim(p.get("text") or "", LIMITS["xueqiu"]),
            "评论数": p.get("replies"),
        }
        for p in posts
    ]

    # —— 财联社：只留加红重要电报 ——
    cl = load_json(date_str, "cls") or {}
    tele = cl.get("telegraphs") or []
    red = [t for t in tele if t.get("is_red")] or tele
    d["sources"]["财联社"] = [
        {
            "time": (t.get("time") or "")[-5:],
            "text": _trim((t.get("title") or "") + " " + (t.get("content") or ""), LIMITS["cls"]),
        }
        for t in red[: COUNTS["cls"]]
    ]

    return d


def cross_source_ranking(date_str: str, cfg: dict, mentions: dict, delta: dict) -> dict:
    """热度排行：跨源提及 + 热榜排名变化 + 资金流，合成两个榜单。"""
    em = load_json(date_str, "eastmoney") or {}
    ths = load_json(date_str, "ths") or {}
    ff = {x["name"]: x for x in (em.get("fundflow") or {}).get("stock_top20_5d") or []}
    hot_rank = {x["name"]: x["rank"] for x in ths.get("hot_stocks") or []}
    rise = {x["name"]: x["rank_delta"] for x in delta.get("rising") or []}
    fall = {x["name"]: x["rank_delta"] for x in delta.get("falling") or []}

    rows = defaultdict(dict)
    for name, m in (mentions.get("mentions") or {}).items():
        rows[name]["提及"] = m["total"]
        rows[name]["源数"] = m["source_count"]
    for name, rank in hot_rank.items():
        rows[name]["热榜名次"] = rank
    for name, dlt in {**rise, **fall}.items():
        rows[name]["名次变化"] = dlt
    for name, f in ff.items():
        rows[name]["主力5日净流入亿"] = f["main_net_5d_yi"]

    def heat_score(r):
        # 热度绝对值：热榜靠前 + 多源提及 + 资金流入
        s = 0
        if "热榜名次" in r:
            s += max(0, 60 - r["热榜名次"]) * 2
        s += r.get("提及", 0) * 3 + r.get("源数", 0) * 10
        s += max(0.0, float(r.get("主力5日净流入亿", 0) or 0))
        return s

    def rise_score(r):
        # 升温速度：名次跃升 + 多源同时提及（新共识）
        return r.get("名次变化", 0) * 5 + r.get("源数", 0) * 8 + r.get("提及", 0)

    items = [{"name": k, **v} for k, v in rows.items() if v]
    top_heat = sorted(items, key=lambda r: -heat_score(r))[:15]
    top_rise = sorted(
        [r for r in items if r.get("名次变化", 0) > 0 or r.get("源数", 0) >= 2],
        key=lambda r: -rise_score(r),
    )[:15]
    return {
        "热度最高": top_heat,
        "升温最快": top_rise,
        "降温最快": (delta.get("falling") or [])[:10],
    }
