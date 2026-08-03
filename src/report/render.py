"""report.md → 自包含 HTML（电脑阅读版）。

不依赖第三方 markdown 库：报告结构固定（标题/表格/加粗/列表/引用），
自己转换可控且省一个依赖。输出单文件，支持深浅色，表格横向滚动。
"""

import html
import os
import re

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--dim:#666;--line:#e5e5e5;--accent:#c0392b;
--card:#fafafa;--up:#c0392b;--down:#27865a;--mark:#fff3cd}
@media(prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e8e8e8;--dim:#9aa0a6;
--line:#2c2f36;--accent:#ff6b5b;--card:#1e2128;--up:#ff6b5b;--down:#4ade80;--mark:#3d3520}}
:root[data-theme=dark]{--bg:#16181d;--fg:#e8e8e8;--dim:#9aa0a6;--line:#2c2f36;
--accent:#ff6b5b;--card:#1e2128;--up:#ff6b5b;--down:#4ade80;--mark:#3d3520}
:root[data-theme=light]{--bg:#fff;--fg:#1a1a1a;--dim:#666;--line:#e5e5e5;
--accent:#c0392b;--card:#fafafa;--up:#c0392b;--down:#27865a;--mark:#fff3cd}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;padding:2rem 1rem 4rem;
font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
-webkit-text-size-adjust:100%}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 .3rem;letter-spacing:-.01em}
h2{font-size:1.25rem;margin:2.4rem 0 .9rem;padding-bottom:.4rem;
border-bottom:2px solid var(--line)}
h3{font-size:1.05rem;margin:1.6rem 0 .6rem;color:var(--accent)}
p{margin:.7rem 0}
ul,ol{margin:.6rem 0;padding-left:1.4rem}
li{margin:.3rem 0}
strong{font-weight:600}
blockquote{margin:.8rem 0;padding:.8rem 1rem;background:var(--card);
border-left:3px solid var(--accent);border-radius:0 6px 6px 0}
blockquote p{margin:.3rem 0}
hr{border:0;border-top:1px solid var(--line);margin:2.5rem 0}
.tw{overflow-x:auto;margin:1rem 0;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;min-width:max-content;font-size:.92rem}
th,td{padding:.5rem .8rem;text-align:left;border-bottom:1px solid var(--line);
white-space:nowrap}
th{background:var(--card);font-weight:600;position:sticky;top:0}
tr:hover td{background:var(--card)}
.meta{color:var(--dim);font-size:.88rem;margin-bottom:2rem}
.up{color:var(--up)}.down{color:var(--down)}
mark{background:var(--mark);color:inherit;padding:0 .2em;border-radius:2px}
code{background:var(--card);padding:.1em .4em;border-radius:3px;font-size:.9em}
.foot{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);
color:var(--dim);font-size:.85rem}
@media(max-width:600px){body{padding:1.2rem .8rem 3rem;font-size:15px}
h1{font-size:1.4rem}h2{font-size:1.15rem}}
"""

_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|$")


def _inline(t: str) -> str:
    """行内格式：转义 → 加粗/代码/涨跌着色。"""
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    # 涨跌幅着色：+1.23% 红、-1.23% 绿（A股习惯）
    t = re.sub(r"(?<![\w.])\+(\d+(?:\.\d+)?%)", r'<span class="up">+\1</span>', t)
    t = re.sub(r"(?<![\w.])-(\d+(?:\.\d+)?%)", r'<span class="down">-\1</span>', t)
    return t


def md_to_html(md: str) -> str:
    lines, out, i = md.split("\n"), [], 0
    list_open = quote_open = False

    def close_blocks():
        nonlocal list_open, quote_open
        if list_open:
            out.append("</ul>")
            list_open = False
        if quote_open:
            out.append("</blockquote>")
            quote_open = False

    while i < len(lines):
        ln = lines[i].rstrip()

        # 表格：当前行以 | 开头且下一行是分隔行
        if ln.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            close_blocks()
            head = [c.strip() for c in ln.strip("|").split("|")]
            out.append('<div class="tw"><table><thead><tr>')
            out.extend(f"<th>{_inline(c)}</th>" for c in head)
            out.append("</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table></div>")
            continue

        if not ln.strip():
            close_blocks()
            i += 1
            continue

        if ln.startswith("### "):
            close_blocks()
            out.append(f"<h3>{_inline(ln[4:])}</h3>")
        elif ln.startswith("## "):
            close_blocks()
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("# "):
            close_blocks()
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.startswith("---"):
            close_blocks()
            out.append("<hr>")
        elif ln.startswith("> "):
            if not quote_open:
                close_blocks()
                out.append("<blockquote>")
                quote_open = True
            out.append(f"<p>{_inline(ln[2:])}</p>")
        elif re.match(r"^[-*] ", ln.strip()):
            if quote_open:
                out.append("</blockquote>")
                quote_open = False
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{_inline(ln.strip()[2:])}</li>")
        else:
            if not quote_open:
                close_blocks()
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1

    close_blocks()
    return "\n".join(out)


def render(md: str, title: str = "舆情研判报告") -> str:
    body = md_to_html(md)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><div class="wrap">{body}
<div class="foot">本页由舆情交叉分析系统自动生成 · 信息聚合分析，不构成投资建议</div>
</div></body></html>"""


def render_file(md_path: str, out_path: str = "") -> str:
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    title = "舆情研判报告"
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()
    out_path = out_path or os.path.splitext(md_path)[0] + ".html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render(md, title))
    return out_path
