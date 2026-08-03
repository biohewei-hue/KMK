"""把报告推送到飞书（手机阅读版）。

手机上没人看4000字，所以只推**决策必需**的部分：
今日结论 / 见底判断 / 关键情绪数据 / 3只推荐股 / 热度Top5。
完整版看电脑上的 HTML。

用飞书群「自定义机器人」webhook，无需创建应用、无需审批。
配置：credentials.json → feishu.webhook（可选 feishu.secret 做签名校验）
"""

import base64
import hashlib
import hmac
import re
import time

from ..http import make_session

# 见底判断四档 → 卡片配色
STANCE_COLOR = {
    "未见底": "red", "筑底中": "orange", "已见底": "green", "反弹中继": "blue",
}


def _section(md: str, title_kw: str) -> str:
    """按二级标题取某一章的正文。"""
    pat = re.compile(rf"^##\s*.*{re.escape(title_kw)}.*$", re.M)
    m = pat.search(md)
    if not m:
        return ""
    rest = md[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def _strip_md(t: str) -> str:
    """飞书 lark_md 支持 **加粗**，但表格/引用需要转成纯文本。"""
    t = re.sub(r"^\|.*\|$", "", t, flags=re.M)      # 去表格
    t = re.sub(r"^[\s:|-]+$", "", t, flags=re.M)
    t = re.sub(r"^>\s?", "", t, flags=re.M)          # 去引用符
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _extract_stance(md: str) -> str:
    for s in STANCE_COLOR:
        if s in md[:1500]:  # 结论段里出现的即为当日表态
            return s
    return ""


def _md_block(text: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": text}}


def build_card(md: str, date_str: str, html_url: str = "") -> dict:
    """构造飞书交互卡片（手机友好：短、分块、重点前置）。"""
    stance = _extract_stance(md)
    conclusion = _strip_md(_section(md, "今日结论"))[:900]
    picks = _strip_md(_section(md, "明日推荐"))[:1200]
    heat = _strip_md(_section(md, "热度榜"))[:500]

    elements = []
    if conclusion:
        elements.append(_md_block(conclusion))
    if stance:
        elements.append({"tag": "hr"})
        elements.append(_md_block(f"**见底判断：{stance}**"))
    if picks:
        elements += [{"tag": "hr"}, _md_block("**📈 明日推荐**\n" + picks)]
    if heat:
        elements += [{"tag": "hr"}, _md_block("**🔥 热度**\n" + heat)]
    if html_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看完整报告"},
                "url": html_url,
                "type": "primary",
            }],
        })
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "信息聚合分析，不构成投资建议"}],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"舆情研判 · {date_str}"},
                "template": STANCE_COLOR.get(stance, "blue"),
            },
            "elements": elements,
        },
    }


def _sign(secret: str, timestamp: str) -> str:
    """飞书自定义机器人签名校验：HMAC-SHA256(key=timestamp\\nsecret, msg='')"""
    key = f"{timestamp}\n{secret}".encode()
    return base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode()


def send(md: str, date_str: str, creds: dict, html_url: str = "") -> dict:
    fs = creds.get("feishu") or {}
    webhook = fs.get("webhook", "")
    if not webhook:
        raise RuntimeError("未配置飞书 webhook（credentials.json → feishu.webhook）")

    payload = build_card(md, date_str, html_url)
    if fs.get("secret"):
        ts = str(int(time.time()))
        payload["timestamp"] = ts
        payload["sign"] = _sign(fs["secret"], ts)

    s = make_session()
    r = s.post(webhook, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (0, None):
        raise RuntimeError(f"飞书返回错误 {data.get('code')}: {data.get('msg')}")
    return data
