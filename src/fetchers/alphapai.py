"""Alpha派（需凭证）：蓝宝书、PaiPai总结的『每日必看』栏目、24h个股提及、重点研报。

Alpha派接口非公开文档。本模块提供通用抓取框架：
在 config/credentials.json → alphapai 中配置 cookie/headers 后，
首次使用请在浏览器打开『每日必看』/蓝宝书页面，F12 复制对应 XHR 请求
（右键『复制为cURL』）发给 Claude，把真实 endpoint 填入下方常量即可。
"""

import time

from ..http import get_json, make_session

# TODO(首次接线): 用抓包得到的真实接口替换
DAILY_MUST_READ_URL = ""  # 每日必看栏目列表接口
BLUEBOOK_URL = ""         # 蓝宝书内容接口
FEED_URL = ""             # 信息流/研报接口


def _session(creds: dict):
    a = creds.get("alphapai") or {}
    if not a.get("cookie") and not a.get("headers"):
        raise RuntimeError("缺少 Alpha派 凭证（config/credentials.json → alphapai）")
    return make_session(cookie=a.get("cookie", ""), headers=a.get("headers") or {})


def fetch_all(cfg: dict, creds: dict) -> dict:
    s = _session(creds)
    out = {"daily_must_read": [], "bluebook": [], "feed": [], "errors": []}
    if not DAILY_MUST_READ_URL:
        out["errors"].append(
            "Alpha派接口尚未接线：请抓包『每日必看』页面的XHR请求发给Claude完成配置"
        )
        return out
    try:
        out["daily_must_read"] = get_json(s, DAILY_MUST_READ_URL)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"daily_must_read: {e}")
    for name, url in [("bluebook", BLUEBOOK_URL), ("feed", FEED_URL)]:
        if not url:
            continue
        try:
            out[name] = get_json(s, url)
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{name}: {e}")
    return out
