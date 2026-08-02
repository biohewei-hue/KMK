"""热度分析：
1. 同花顺热榜 今日 vs 昨日 对比 → 升温最快 / 降温最快 / 新上榜 / 掉出榜单
2. 跨源个股提及统计：知识星球、韭研公社、Alpha派、财联社、雪球中出现的股票名计数
"""

import os
import re
from datetime import datetime, timedelta

from ..config import DATA_DIR, load_json


def _prev_snapshot(date_str: str, name: str, max_back: int = 7):
    """向前找最近一份历史快照（跳过周末/缺数据日）。"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    for _ in range(max_back):
        d -= timedelta(days=1)
        prev = d.strftime("%Y-%m-%d")
        if os.path.exists(os.path.join(DATA_DIR, prev)):
            data = load_json(prev, name)
            if data:
                return prev, data
    return None, None


def hot_list_delta(date_str: str) -> dict:
    """同花顺热榜对比。"""
    today = load_json(date_str, "ths") or {}
    prev_date, prev = _prev_snapshot(date_str, "ths")
    t_list = today.get("hot_stocks") or []
    p_list = (prev or {}).get("hot_stocks") or []
    p_rank = {x["name"]: x["rank"] for x in p_list}
    t_rank = {x["name"]: x["rank"] for x in t_list}

    rising, falling, new_entries = [], [], []
    for x in t_list:
        if x["name"] in p_rank:
            delta = p_rank[x["name"]] - x["rank"]  # 正数=排名上升
            item = {**x, "rank_prev": p_rank[x["name"]], "rank_delta": delta}
            if delta > 0:
                rising.append(item)
            elif delta < 0:
                falling.append(item)
        else:
            new_entries.append(x)
    dropped = [x for x in p_list if x["name"] not in t_rank]

    rising.sort(key=lambda x: x["rank_delta"], reverse=True)
    falling.sort(key=lambda x: x["rank_delta"])
    return {
        "compared_with": prev_date,
        "rising": rising[:15],
        "falling": falling[:15],
        "new_entries": new_entries,
        "dropped": dropped[:15],
    }


# A股名称匹配：2-8个汉字/字母，排除常见非股票词由调用方处理
_CODE_RE = re.compile(r"(?:SH|SZ|sh|sz)?[036]\d{5}")


def _collect_texts(date_str: str) -> list[tuple[str, str]]:
    """汇总各源文本 → [(source, text)]"""
    out = []
    zsxq = load_json(date_str, "zsxq") or {}
    for t in zsxq.get("all_topics") or []:
        out.append(("知识星球", t.get("text") or ""))
    jy = load_json(date_str, "jiuyan") or {}
    for a in jy.get("article_list") or []:
        out.append(("韭研公社", a.get("title") or ""))
    for d in (jy.get("focus_details") or []) + (jy.get("linked_details") or []):
        out.append(("韭研公社", d.get("text") or ""))
    cls_data = load_json(date_str, "cls") or {}
    for t in cls_data.get("telegraphs") or []:
        out.append(("财联社", (t.get("title") or "") + " " + (t.get("content") or "")))
    xq = load_json(date_str, "xueqiu") or {}
    for p in xq.get("hot_posts") or []:
        out.append(("雪球", (p.get("title") or "") + " " + (p.get("text") or "")))
    ap = load_json(date_str, "alphapai") or {}
    out.append(("Alpha派", str(ap.get("daily_must_read") or "")))
    out.append(("Alpha派", str(ap.get("bluebook") or "")))
    return out


def cross_source_mentions(date_str: str, names: list[str]) -> dict:
    """统计给定股票名在各源的提及次数。names 来自监控池+热榜股票名。"""
    texts = _collect_texts(date_str)
    result = {}
    for name in set(names):
        if not name or len(name) < 2:
            continue
        per_source: dict[str, int] = {}
        for src, text in texts:
            c = text.count(name)
            if c:
                per_source[src] = per_source.get(src, 0) + c
        if per_source:
            result[name] = {
                "total": sum(per_source.values()),
                "sources": per_source,
                "source_count": len(per_source),
            }
    ranked = sorted(result.items(), key=lambda kv: (-kv[1]["source_count"], -kv[1]["total"]))
    return {"mentions": dict(ranked)}
