"""Alpha派（需凭证）：蓝宝书、PaiPai『每日必看』、研报详情、24h个股提及。

认证方式（由抓包确认）：
  authorization: <JWT>     ← 真正的登录凭证，有效期约30天
  x-device: <设备指纹>
  x-from: web
配置在 config/credentials.json → alphapai。

列表类接口通过 tools/import_curl.py 登记到 config/endpoints.json，
详情接口已内置。抓不到列表时会自动探测常见路径。
"""

import time
from urllib.parse import urlencode

from ..curl_import import get_endpoint
from ..http import get_json, make_session
from ..normalize import deep_text, normalize_list

BASE = "https://alphapai-web.rabyte.cn/external/alpha/api"
WEB = "https://alphapai-web.rabyte.cn"

# 已由抓包确认的详情接口
REPORT_DETAIL = BASE + "/mix/hot/topic/report/detail/v2"

# 列表接口未抓包时的候选路径（首次运行自动探测，命中后打印出来即可固化）
LIST_CANDIDATES = [
    (BASE + "/mix/hot/topic/report/list/v2", {"type": "21", "pageNum": "1", "pageSize": "20", "isUs": "false"}),
    (BASE + "/mix/hot/topic/report/page/v2", {"type": "21", "pageNum": "1", "pageSize": "20", "isUs": "false"}),
    (BASE + "/mix/hot/topic/report/list", {"type": "21", "pageNum": "1", "pageSize": "20"}),
    (BASE + "/mix/hot/topic/list/v2", {"type": "21", "pageNum": "1", "pageSize": "20"}),
    (BASE + "/mix/hot/topic/page/v2", {"type": "21", "pageNum": "1", "pageSize": "20"}),
]


def _session(creds: dict):
    a = creds.get("alphapai") or {}
    token = a.get("authorization") or (a.get("headers") or {}).get("authorization", "")
    if not token:
        raise RuntimeError(
            "缺少 Alpha派 authorization（config/credentials.json → alphapai.authorization）"
        )
    headers = {
        "authorization": token,
        "x-from": "web",
        "Referer": WEB + "/reading/home",
        "Origin": WEB,
    }
    if a.get("x_device"):
        headers["x-device"] = a["x_device"]
    headers.update(a.get("headers") or {})
    return make_session(cookie=a.get("cookie", ""), headers=headers)


def fetch_detail(s, item_id: str, is_us: bool = False) -> dict:
    """研报/报告详情（接口已确认可用）。"""
    spec = get_endpoint("alphapai", "report_detail")
    url = spec["url"] if spec else REPORT_DETAIL
    params = dict(spec.get("params") or {}) if spec else {}
    params.update({"id": item_id, "isUs": "true" if is_us else "false"})
    data = get_json(s, url, params=params)
    return {"id": item_id, "text": deep_text(data), "raw": data}


def _fetch_list_from_endpoint(s, name: str) -> list[dict]:
    """按 endpoints.json 中登记的端点抓列表（由 tools/import_curl.py 导入）。"""
    spec = get_endpoint("alphapai", name)
    if not spec:
        return []
    kwargs = {"params": spec.get("params") or {}}
    if spec.get("headers"):
        kwargs["headers"] = spec["headers"]
    if spec["method"] == "POST":
        body = spec.get("body")
        data = s.post(spec["url"], json=body, timeout=20, **kwargs).json()
    else:
        data = get_json(s, spec["url"], **kwargs)
    return normalize_list(data)


def probe_lists(s) -> tuple[list[dict], list[str]]:
    """列表端点未登记时，探测候选路径。返回 (条目, 探测日志)。"""
    log = []
    for url, params in LIST_CANDIDATES:
        try:
            data = get_json(s, url, retries=1, params=params)
            items = normalize_list(data)
            log.append(f"{url}?{urlencode(params)} → {len(items)} 条")
            if items:
                log.append(f"✅ 命中：{url}")
                return items, log
        except Exception as e:  # noqa: BLE001
            log.append(f"{url} → {str(e)[:80]}")
    return [], log


def fetch_all(cfg: dict, creds: dict) -> dict:
    s = _session(creds)
    out = {"daily_must_read": [], "bluebook": [], "details": [], "probe_log": [], "errors": []}

    for key, name in [("daily_must_read", "daily_list"), ("bluebook", "bluebook_list")]:
        try:
            out[key] = _fetch_list_from_endpoint(s, name)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")

    if not out["daily_must_read"]:
        items, log = probe_lists(s)
        out["probe_log"] = log
        out["daily_must_read"] = items
        if not items:
            out["errors"].append(
                "Alpha派列表接口未命中：请抓包『每日必看』/蓝宝书列表页的XHR，"
                "用 python tools/import_curl.py alphapai.daily_list <文件> 导入"
            )

    # 抓正文（每日必看 + 蓝宝书，各取前若干条）
    seen = set()
    for item in (out["daily_must_read"] + out["bluebook"])[:30]:
        iid = item.get("id")
        if not iid or iid in seen:
            continue
        seen.add(iid)
        try:
            d = fetch_detail(s, iid)
            d["title"] = item.get("title")
            d["time"] = item.get("time")
            out["details"].append(d)
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"detail {iid}: {str(e)[:100]}")
    return out
