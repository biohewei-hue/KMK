import time

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def make_session(cookie: str = "", headers: dict | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})
    if cookie:
        s.headers["Cookie"] = cookie
    if headers:
        s.headers.update(headers)
    return s


def get_json(session: requests.Session, url: str, retries: int = 3, **kwargs):
    """GET 并解析 JSON，指数退避重试。"""
    last = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=20, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 - 采集器需要吞掉一切网络异常后重试
            last = e
            time.sleep(2**i)
    raise RuntimeError(f"GET {url} 失败: {last}")


def post_json(session: requests.Session, url: str, retries: int = 3, **kwargs):
    last = None
    for i in range(retries):
        try:
            r = session.post(url, timeout=20, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2**i)
    raise RuntimeError(f"POST {url} 失败: {last}")
