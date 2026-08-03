#!/usr/bin/env python3
"""自动抓取凭证与接口（用真实浏览器拦截请求，免去手工复制 cURL）。

韭研公社的 token 由 timestamp 派生且会过期，Alpha派 JWT 约30天到期；
本工具用 Playwright 打开站点、监听 XHR，把新鲜凭证与列表接口一并落盘。

首次使用（有界面，需要你手动登录一次，登录态会保存在本地 profile）：
    python tools/harvest_token.py jiuyan
    python tools/harvest_token.py alphapai

之后每日刷新（无界面，复用已保存的登录态）：
    python tools/harvest_token.py jiuyan --headless

依赖：pip install playwright && playwright install chromium
"""

import argparse
import json
import os
import sys
import time

# 兼容 Windows：不能按 "/" 切分路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import CONFIG_DIR, load_credentials  # noqa: E402
from src.curl_import import SKIP_HEADERS, save_endpoint  # noqa: E402
from src.normalize import normalize_list  # noqa: E402

PROFILE_DIR = os.path.join(CONFIG_DIR, ".browser_profile")

SITES = {
    "jiuyan": {
        "url": "https://www.jiuyangongshe.com/",
        "match": "jiuyangongshe.com",
        "api_hint": "/jystock-app/api/",
        # 逐个访问这些页面以触发目标栏目的 XHR
        "visit": [
            "https://www.jiuyangongshe.com/",
            "https://www.jiuyangongshe.com/action",
        ],
        "cred_headers": ["token", "timestamp"],
    },
    "alphapai": {
        "url": "https://alphapai-web.rabyte.cn/reading/home",
        "match": "rabyte.cn",
        "api_hint": "/external/alpha/api/",
        "visit": [
            "https://alphapai-web.rabyte.cn/reading/home",
            "https://alphapai-web.rabyte.cn/reading/home/my-focus",
        ],
        "cred_headers": ["authorization", "x-device"],
    },
}

AUTH_HEADERS = {"authorization", "token", "timestamp", "x-device", "x-token", "cookie"}


def harvest(site_key: str, headless: bool, wait: int) -> dict:
    from playwright.sync_api import sync_playwright  # 延迟导入，未装时给友好提示

    site = SITES[site_key]
    captured: dict[str, dict] = {}   # url → 请求信息
    responses: dict[str, list] = {}  # url → 归一化条目
    creds: dict[str, str] = {}
    seen_cookie: list[str] = []      # 请求头里的 cookie（浏览器关闭后仍可用）

    os.makedirs(PROFILE_DIR, exist_ok=True)
    launch_kwargs = {"headless": headless, "viewport": {"width": 1400, "height": 900}}
    # 环境已自带 chromium 时（如受限容器），用 CHROMIUM_PATH 指定，免去 playwright install
    if os.environ.get("CHROMIUM_PATH"):
        launch_kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            os.path.join(PROFILE_DIR, site_key), **launch_kwargs
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_request(req):
            if site["match"] not in req.url or site["api_hint"] not in req.url:
                return
            h = {k.lower(): v for k, v in req.headers.items()}
            for name in site["cred_headers"]:
                if h.get(name):
                    creds[name] = h[name]
            if h.get("cookie"):
                seen_cookie.append(h["cookie"])
            captured[req.url] = {
                "method": req.method,
                "headers": {
                    k: v for k, v in h.items()
                    if k not in SKIP_HEADERS and k not in AUTH_HEADERS and not k.startswith(":")
                },
                "post_data": req.post_data,
            }

        def on_response(res):
            if site["match"] not in res.url or site["api_hint"] not in res.url:
                return
            try:
                items = normalize_list(res.json())
            except Exception:  # noqa: BLE001
                return
            if items:
                responses[res.url] = items

        page.on("request", on_request)
        page.on("response", on_response)

        for url in site["visit"]:
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(2500)
            except Exception as e:  # noqa: BLE001
                print(f"   访问 {url} 超时/失败：{str(e)[:80]}")

        if not headless:
            print("\n" + "=" * 60)
            print("浏览器已打开，请在浏览器里完成以下操作：")
            print("  1. 若未登录 → 先登录")
            print("  2. 点开目标栏目（Alpha派：蓝宝书 → PaiPai总结 → 每日必看；")
            print("     韭研公社：关注 → 每日公社内容精选 / 学习笔记 / 盘前纪要）")
            print("  3. 让列表内容加载出来（多滚动几下更好）")
            print(f"  4. 完成后【直接关闭浏览器窗口】即可（或等 {wait} 秒自动结束）")
            print("=" * 60, flush=True)
            deadline = time.time() + wait
            while time.time() < deadline:
                try:
                    page.wait_for_timeout(1000)
                    if not ctx.pages:  # 用户关闭了浏览器 → 视为完成
                        break
                except Exception:  # noqa: BLE001 - 窗口被关闭时抛错，属正常结束
                    break
            print(f"已捕获 {len(captured)} 个接口请求，{len(responses)} 个返回列表数据。")

        # 优先用请求头里抓到的 cookie；浏览器已关闭时 ctx.cookies() 会失败
        cookie_str = seen_cookie[-1] if seen_cookie else ""
        if not cookie_str:
            try:
                key = site["match"].split(".")[-2]
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in ctx.cookies()
                    if key in c.get("domain", "")
                )
            except Exception:  # noqa: BLE001 - 浏览器已关闭，无 cookie 可读
                pass
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass

    return {"creds": creds, "cookie": cookie_str, "requests": captured, "lists": responses}


def persist(site_key: str, result: dict):
    """凭证写入 credentials.json，列表接口写入 endpoints.json。"""
    creds = load_credentials()
    entry = creds.setdefault(site_key, {})
    for k, v in result["creds"].items():
        entry[k.replace("-", "_")] = v
    if result["cookie"]:
        entry["cookie"] = result["cookie"]
    path = os.path.join(CONFIG_DIR, "credentials.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 凭证已更新 → {path}")
    for k in result["creds"]:
        print(f"   {k}: {result['creds'][k][:32]}...")
    if result["cookie"]:
        print(f"   cookie: {result['cookie'][:50]}...")

    if not result["lists"]:
        print("\n⚠️  未捕获到返回列表数据的接口。请用有界面模式，手动点开目标栏目后再结束。")
        return
    print(f"\n发现 {len(result['lists'])} 个返回列表的接口：")
    for i, (url, items) in enumerate(
        sorted(result["lists"].items(), key=lambda kv: -len(kv[1]))
    ):
        sample = items[0].get("title") or (items[0].get("text") or "")[:40]
        print(f"  [{i}] {len(items):3}条  {url}")
        print(f"        样例: {sample}")
        if i == 0:  # 条目最多的登记为主列表接口
            req = result["requests"].get(url, {})
            body = None
            if req.get("post_data"):
                try:
                    body = json.loads(req["post_data"])
                except Exception:  # noqa: BLE001
                    body = req["post_data"]
            from urllib.parse import parse_qsl, urlparse, urlunparse

            u = urlparse(url)
            save_endpoint(
                f"{site_key}.article_list" if site_key == "jiuyan" else f"{site_key}.daily_list",
                {
                    "method": req.get("method", "GET"),
                    "url": urlunparse((u.scheme, u.netloc, u.path, "", "", "")),
                    "params": dict(parse_qsl(u.query, keep_blank_values=True)),
                    "headers": req.get("headers") or {},
                    "body": body,
                },
            )
            print("        ✅ 已登记为主列表接口")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", choices=list(SITES))
    ap.add_argument("--headless", action="store_true", help="无界面模式（复用已保存登录态）")
    ap.add_argument("--wait", type=int, default=120, help="有界面模式下的等待秒数")
    args = ap.parse_args()

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("需要先安装：pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"开始抓取 [{args.site}] ...")
    t0 = time.time()
    try:
        result = harvest(args.site, args.headless, args.wait)
    except Exception as e:  # noqa: BLE001 - 转成人话，避免用户面对原始 traceback
        msg = str(e)
        print(f"\n❌ 抓取失败：{msg[:300]}")
        if "Executable doesn't exist" in msg or "playwright install" in msg:
            print("\n   原因：浏览器组件没装好。请在菜单里重新选 [1] 首次安装，")
            print("   或手动运行：python -m playwright install chromium")
        sys.exit(1)

    if not result["creds"]:
        print("\n❌ 未捕获到凭证请求头。")
        if args.headless:
            print("   无界面模式依赖已保存的登录态。请先用有界面模式登录一次：")
            print(f"   在菜单里选 [{'3' if args.site == 'jiuyan' else '2'}]")
        else:
            print("   请确认已在浏览器里登录，并点开了目标栏目。")
        sys.exit(1)
    persist(args.site, result)
    print(f"\n耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
