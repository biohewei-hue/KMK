"""华尔街见闻财经日历（公开接口）：只保留中国/美国、重要性≥3星的数据与事件。"""

import time
from datetime import datetime, timedelta

from ..http import get_json, make_session

CALENDAR_URL = "https://api-one.wallstcn.com/apiv1/finfo/calendars"

COUNTRY_MAP = {"中国": {"中国", "CN", "China"}, "美国": {"美国", "US", "United States"}}


def fetch_calendar(days_ahead: int = 7, min_importance: int = 3, countries=None) -> list[dict]:
    countries = countries or ["中国", "美国"]
    allowed = set()
    for c in countries:
        allowed |= COUNTRY_MAP.get(c, {c})
    s = make_session(headers={"Referer": "https://wallstreetcn.com/calendar"})
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days_ahead)
    params = {
        "start": int(start.timestamp()),
        "end": int(end.timestamp()),
    }
    data = get_json(s, CALENDAR_URL, params=params)
    items = (data.get("data") or {}).get("items") or []
    out = []
    for it in items:
        country = it.get("country") or it.get("country_name") or ""
        importance = it.get("importance") or it.get("stars") or 0
        if country not in allowed or importance < min_importance:
            continue
        ts = it.get("public_date") or it.get("timestamp") or 0
        out.append(
            {
                "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "",
                "country": country,
                "importance": importance,
                "title": it.get("title") or it.get("name") or "",
                "forecast": it.get("forecast"),
                "previous": it.get("previous"),
                "actual": it.get("actual"),
            }
        )
    out.sort(key=lambda x: x["time"])
    return out


def fetch_all(cfg: dict) -> dict:
    c = cfg.get("calendar", {})
    return {
        "calendar": fetch_calendar(
            c.get("days_ahead", 7), c.get("min_importance", 3), c.get("countries")
        )
    }
