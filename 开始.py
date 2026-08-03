#!/usr/bin/env python3
"""菜单式启动器（双击本文件即可运行）。

与 开始.bat 功能相同，但 .py 不会被 Windows SmartScreen 拦截。
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

MENU = """
 ============================================================
             舆情交叉分析报告系统
 ============================================================

   [1]  首次安装        (第一次使用选这个，装完不用再选)

   [2]  登录 Alpha派    (弹浏览器，登录后点开「每日必看」)
   [3]  登录 韭研公社    (弹浏览器，登录后点开「关注」栏目)

   [4]  抓取今日数据 + 生成报告骨架      <<< 每天点这个

   [5]  检查凭证状态
   [6]  只抓免登录的数据源 (抓不通时的保底方案)

   [7]  用 Edge 登录  (上面弹出的浏览器被拦截时改用这个)
   [8]  填写知识星球 cookie

   [0]  退出

 ============================================================
"""

LOGIN_TIPS = {
    "alphapai": """
   即将弹出浏览器窗口，请在浏览器里：

     1. 登录 Alpha派
     2. 点开「蓝宝书」→「PaiPai总结」→「每日必看」
     3. 等内容显示出来，往下滚动几屏
     4. 然后【直接关闭浏览器窗口】
""",
    "jiuyan": """
   即将弹出浏览器窗口，请在浏览器里：

     1. 登录 韭研公社
     2. 点开「关注」栏目下的「每日公社内容精选」
        「学习笔记」「公告内容精选」「盘前纪要」
     3. 等内容显示出来，往下滚动几屏
     4. 然后【直接关闭浏览器窗口】
""",
}


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def run(args, desc=""):
    if desc:
        print(f"\n   {desc}\n")
    return subprocess.run([PY, *args], cwd=ROOT).returncode


def pause():
    try:
        input("\n   按回车返回菜单...")
    except (EOFError, KeyboardInterrupt):
        pass


def do_install():
    clear()
    print("\n   正在安装依赖，第一次比较慢（几分钟），请耐心等待...\n")
    if run(["-m", "pip", "install", "-r", "requirements.txt"]) != 0:
        print("\n   [!] 安装出错，请把上面的报错内容复制给 Claude。")
        return pause()
    print("\n   正在安装浏览器组件（国内可能较慢）...\n")
    if run(["-m", "playwright", "install", "chromium"]) != 0:
        print("\n   [提示] 浏览器组件没装成功（国内下载常失败），")
        print("          不影响使用——登录时会自动改用你系统里的 Edge。")

    cred = os.path.join(ROOT, "config", "credentials.json")
    if not os.path.exists(cred):
        example = os.path.join(ROOT, "config", "credentials.example.json")
        with open(example, encoding="utf-8") as f:
            content = f.read()
        with open(cred, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n   已生成凭证文件 {cred}")
    print("\n   [OK] 安装完成！接下来请依次选 [2] 和 [3] 登录。")
    pause()


def do_login(site, browser="auto"):
    clear()
    print(LOGIN_TIPS[site])
    if browser == "edge":
        print("   本次将驱动你系统里的 Edge（不是自带的浏览器）。")
        print("   注意：请先关掉所有已打开的 Edge 窗口，否则可能启动失败。\n")
    try:
        input("   准备好后按回车，浏览器就会打开...")
    except (EOFError, KeyboardInterrupt):
        return
    args = [os.path.join("tools", "harvest_token.py"), site]
    if browser != "auto":
        args += ["--browser", browser]
    run(args)
    pause()


def do_login_edge():
    clear()
    print("\n   用 Edge 登录哪个网站？\n")
    print("     [1]  Alpha派")
    print("     [2]  韭研公社\n")
    try:
        c = input("   请输入数字：").strip()
    except (EOFError, KeyboardInterrupt):
        return
    site = {"1": "alphapai", "2": "jiuyan"}.get(c)
    if site:
        do_login(site, browser="edge")


def do_daily():
    clear()
    run(["run_daily.py", "--all", "--refresh"], "正在抓取今日数据，需要几分钟，请勿关闭窗口...")
    print("\n" + " " + "=" * 58)
    print("   抓取结束，数据已存到 data\\ 目录下今天日期的文件夹。")
    print("\n   接下来：在本文件夹打开 Claude Code，说「生成今日报告」")
    print(" " + "=" * 58)
    pause()


def do_safe():
    clear()
    run(
        ["run_daily.py", "--all", "--only", "eastmoney,ths,cls,wscn,xueqiu"],
        "只抓不需要登录的数据源（大盘技术研判、资金榜、热榜、财联社电报、财经日历、雪球热帖）...",
    )
    pause()


def do_zsxq_cookie():
    clear()
    print("""
   知识星球 cookie 填写

   获取方法：
     1. 用浏览器打开 wx.zsxq.com 并扫码登录
     2. 按 F12 → 选 Network(网络) 标签 → 刷新页面
     3. 点任意一个请求 → 找到 Request Headers 里的 Cookie
     4. 复制【整行】cookie 内容（必须包含 zsxq_access_token）

   然后粘贴到下面（右键粘贴，粘贴完按回车）：
""")
    try:
        cookie = input("   > ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not cookie:
        print("\n   已取消。")
        return pause()
    if "zsxq_access_token" not in cookie:
        print("\n   ⚠️  这段内容里没有 zsxq_access_token，可能复制得不完整。")
        try:
            if input("   仍然保存？(y/n)：").strip().lower() != "y":
                return pause()
        except (EOFError, KeyboardInterrupt):
            return

    path = os.path.join(ROOT, "config", "credentials.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    data.setdefault("zsxq", {})["cookie"] = cookie
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n   ✅ 已保存到 {path}")
    pause()


ACTIONS = {
    "1": do_install,
    "2": lambda: do_login("alphapai"),
    "3": lambda: do_login("jiuyan"),
    "4": do_daily,
    "5": lambda: (clear(), run([os.path.join("tools", "check_token.py")]), pause()),
    "6": do_safe,
    "7": do_login_edge,
    "8": do_zsxq_cookie,
}


def main():
    while True:
        clear()
        print(MENU)
        try:
            choice = input("   请输入数字后按回车：").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice == "0":
            return
        action = ACTIONS.get(choice)
        if action:
            action()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
