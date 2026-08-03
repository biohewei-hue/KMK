"""通用 JSON 结构解析：在响应结构未知时，自动定位文章列表与正文文本。

抓包接入的接口返回结构各不相同（data.list / data.records / data.page.content ...），
这里用启发式遍历，避免每接一个接口就改一次代码。
"""

import re

ID_KEYS = ("id", "topicid", "articleid", "reportid", "code", "uuid", "key")
TITLE_KEYS = ("title", "name", "subject", "headline", "shorttitle", "maintitle")
TEXT_KEYS = (
    "content", "text", "body", "summary", "abstract", "digest", "detail",
    "desc", "description", "brief", "viewpoint", "conclusion", "remark",
)
TIME_KEYS = ("time", "createtime", "publishtime", "date", "pubdate", "updatetime", "ctime")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def strip_html(s: str) -> str:
    s = _TAG_RE.sub("\n", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS_RE.sub("\n\n", s).strip()


def _norm_key(k: str) -> str:
    return k.lower().replace("_", "").replace("-", "")


def _pick(d: dict, keys) -> str:
    for k, v in d.items():
        if _norm_key(k) in keys and isinstance(v, (str, int, float)) and str(v).strip():
            return str(v)
    return ""


def find_item_lists(obj, path="", out=None) -> list[tuple[str, list]]:
    """递归查找『看起来像文章列表』的数组：元素是 dict 且含标题类字段。"""
    if out is None:
        out = []
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if dicts and any(_pick(x, TITLE_KEYS) or _pick(x, TEXT_KEYS) for x in dicts):
            out.append((path, dicts))
        for i, x in enumerate(obj[:3]):
            find_item_lists(x, f"{path}[{i}]", out)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_item_lists(v, f"{path}.{k}" if path else k, out)
    return out


def to_item(d: dict) -> dict:
    """把任意结构的一条记录归一化为 {id, title, time, text, raw}。"""
    text = ""
    for k, v in d.items():
        if _norm_key(k) in TEXT_KEYS and isinstance(v, str) and len(v) > len(text):
            text = v
    return {
        "id": _pick(d, ID_KEYS),
        "title": _pick(d, TITLE_KEYS),
        "time": _pick(d, TIME_KEYS),
        "text": strip_html(text),
        "raw": d,
    }


def normalize_list(payload) -> list[dict]:
    """从任意响应中提取归一化的条目列表（取元素最多的那个数组）。"""
    lists = find_item_lists(payload)
    if not lists:
        return []
    _, best = max(lists, key=lambda kv: len(kv[1]))
    return [to_item(d) for d in best]


def deep_text(obj, min_len: int = 40) -> str:
    """递归抽取响应中所有较长的文本字段并拼接（用于详情页正文）。"""
    chunks = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and (_norm_key(k) in TEXT_KEYS or len(v) >= min_len):
                    t = strip_html(v)
                    if len(t) >= min_len:
                        chunks.append(t)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(obj)
    seen, out = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return "\n\n".join(out)
