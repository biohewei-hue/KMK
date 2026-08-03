"""华尔街见闻财经日历（公开接口）：只保留中国/美国、重要性≥3星的数据与事件。

接口返回结构随版本变动过，这里做多重容错：
- 尝试多个候选接口
- 条目位置、国家字段、重要性字段都按多种命名兼容
- 全部落空时保留原始响应片段，便于下次定位问题
"""

import time
from datetime import datetime, timedelta

from ..http import get_json, make_session
from ..normalize import find_item_lists

CANDIDATES = [
    "https://api-one.wallstcn.com/apiv1/finfo/calendars",
    "https://api-one.wallstcn.com/apiv1/finfo/calendars/data",
    "https://api-one.wallstcn.com/apiv1/finfo/calendars/events",
]

# 国家字段可能是中文名、两位码、或数字ID（1=中国 2=美国 是常见约定）
COUNTRY_ALIASES = {
    "中国": {"中国", "cn", "china", "中國", "1"},
    "美国": {"美国", "us", "usa", "united states", "america", "2"},
}

COUNTRY_KEYS = ("country", "country_name", "countryname", "region", "area", "country_id")
IMPORTANCE_KEYS = ("importance", "stars", "star", "level", "important")
TIME_KEYS = ("public_date", "timestamp", "time", "date", "publish_time", "display_time")
TITLE_KEYS = ("title", "name", "event", "indicator")


def _get(d: dict, keys) -> str:
    for k, v in d.items():
        if k.lower().replace("_", "") in {x.replace("_", "") for x in keys}:
            if v not in (None, "", []):
                return str(v)
    return ""


def _match_country(val: str, wanted: list[str]) -> str | None:
    low = str(val).strip().lower()
    for name in wanted:
        if low in COUNTRY_ALIASES.get(name, {name}):
            return name
        if name in str(val):  # 中文直接包含
            return name
    return None


def _fmt_time(raw: str) -> str:
    if not raw:
        return ""
    try:
        ts = int(float(raw))
        if ts > 1e12:  # 毫秒
            ts //= 1000
        if ts > 1e9:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except (ValueError, TypeError):
        pass
    return str(raw)[:16]


def fetch_calendar(days_ahead: int = 7, min_importance: int = 3, countries=None) -> dict:
    countries = countries or ["中国", "美国"]
    s = make_session(headers={"Referer": "https://wallstreetcn.com/calendar"})
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days_ahead)

    out, debug, raw_total = [], [], 0
    for url in CANDIDATES:
        try:
            data = get_json(
                s, url, retries=1,
                params={"start": int(start.timestamp()), "end": int(end.timestamp())},
            )
        except Exception as e:  # noqa: BLE001
            debug.append(f"{url.rsplit('/', 1)[-1]}: 请求失败 {str(e)[:60]}")
            continue

        # 结构未知时靠启发式定位条目数组
        lists = find_item_lists(data)
        items = max(lists, key=lambda kv: len(kv[1]))[1] if lists else []
        raw_total += len(items)
        kept = 0
        for it in items:
            country = _match_country(_get(it, COUNTRY_KEYS), countries)
            if not country:
                continue
            imp_raw = _get(it, IMPORTANCE_KEYS)
            try:
                imp = int(float(imp_raw))
            except (ValueError, TypeError):
                imp = 0
            if imp < min_importance:
                continue
            out.append({
                "time": _fmt_time(_get(it, TIME_KEYS)),
                "country": country,
                "importance": imp,
                "title": _get(it, TITLE_KEYS),
                "forecast": it.get("forecast"),
                "previous": it.get("previous"),
                "actual": it.get("actual"),
            })
            kept += 1
        debug.append(f"{url.rsplit('/', 1)[-1]}: 原始{len(items)}条 → 命中{kept}条")
        if kept:
            break

    out.sort(key=lambda x: x["time"])
    result = {"calendar": out, "_debug": debug}
    if not out:
        result["_提示"] = (
            f"未取到符合条件的日历（原始条目共{raw_total}条）。"
            "若原始条目数为0说明接口变更；若>0说明国家/重要性字段命名有变，"
            "请把 wscn.json 发给 Claude 修正字段映射。"
        )
    return result


def fetch_all(cfg: dict) -> dict:
    c = cfg.get("calendar", {})
    return fetch_calendar(
        c.get("days_ahead", 7), c.get("min_importance", 3), c.get("countries")
    )
