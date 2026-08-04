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

   [4]  抓取今日数据                     <<< 每天第1步
   [13] 生成报告 (调用本机 Claude Code)   <<< 每天第2步
   [10] 发布报告 (电脑版网页 + 手机版飞书) <<< 每天第3步

   [5]  检查凭证状态
   [6]  只抓免登录的数据源 (抓不通时的保底方案)

   [7]  用 Edge 登录  (上面弹出的浏览器被拦截时改用这个)
   [8]  填写知识星球 cookie
   [9]  配置飞书推送
   [11] 打开今日数据文件夹 (找 brief.md / digest.json 发给 Claude)
   [12] 备份配置 (换电脑时用，含登录凭证)
   [14] 单独测试某个数据源 (排查用)
   [15] 重置某个网站的连接 (登录坏了从头来)

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
        ["run_daily.py", "--all", "--only", "ths_market,ths,cls,wscn,sentiment"],
        "只抓不需要登录的数据源（指数K线、资金榜、热榜、情绪指标、财联社电报、财经日历）...",
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


def do_feishu_config():
    clear()
    print("""
   配置飞书推送（把手机版报告推到你的飞书）

   获取 webhook 地址：
     1. 打开飞书，进入任意一个群（可以自建一个只有你自己的群）
     2. 群设置 → 群机器人 → 添加机器人 → 自定义机器人
     3. 起个名字（如「舆情研判」）→ 下一步
     4. 【安全设置】建议勾选「签名校验」，会给你一个密钥
     5. 复制 webhook 地址（https://open.feishu.cn/open-apis/bot/v2/hook/...）
""")
    try:
        hook = input("   粘贴 webhook 地址：").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not hook:
        print("\n   已取消。")
        return pause()
    if "open.feishu.cn" not in hook and "larksuite" not in hook:
        print("\n   ⚠️  这看起来不像飞书 webhook 地址，但仍会保存。")
    try:
        secret = input("   签名密钥（没勾选签名校验就直接回车跳过）：").strip()
    except (EOFError, KeyboardInterrupt):
        secret = ""

    path = os.path.join(ROOT, "config", "credentials.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    entry = data.setdefault("feishu", {})
    entry["webhook"] = hook
    if secret:
        entry["secret"] = secret
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n   ✅ 已保存。生成报告后选 [10] 即可推送到飞书。")
    pause()


def do_open_data():
    clear()
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(ROOT, "data", date)
    if not os.path.isdir(folder):
        print(f"\n   ❌ 还没有今天({date})的数据，请先选 [4] 抓取。\n")
        return pause()

    need = ["brief.md", "digest.json"]
    print(f"\n   今日数据目录：{folder}\n")
    for n in need:
        f = os.path.join(folder, n)
        ok = os.path.exists(f)
        size = f"{os.path.getsize(f) / 1024:.0f} KB" if ok else "缺失"
        print(f"   {'✅' if ok else '❌'} {n}  {size}")
    print("""
   把上面两个文件发给 Claude，即可生成报告。
   （报告写好后保存为 report.md 放回本目录，再选 [10] 发布）
""")
    if os.name == "nt":
        os.startfile(folder)  # noqa: S606 - Windows 打开资源管理器
    pause()


def do_claude_report():
    clear()
    import shutil
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")
    brief = os.path.join(ROOT, "data", date, "brief.md")
    if not os.path.exists(brief):
        print(f"\n   ❌ 今天({date})还没有数据，请先选 [4] 抓取。\n")
        return pause()

    claude = shutil.which("claude")
    if not claude:
        print("""
   ❌ 没找到本机版 Claude Code。

   安装方法（装一次就够）：
     1. 去 nodejs.org 下载安装 Node.js
     2. 打开 PowerShell，运行：
            npm install -g @anthropic-ai/claude-code
     3. 再运行 claude 登录一次你的账号

   装好后重新选 [13] 即可。

   （不想装也行：选 [11] 把 brief.md 和 digest.json 发给网页版 Claude，
     写好的 report.md 放回 data 目录，同样能用 [10] 发布）
""")
        return pause()

    print("\n   正在调用 Claude Code 生成报告...")
    print("   过程中可能会询问是否允许读写文件，选允许即可。\n")
    subprocess.run([claude, "生成今日报告"], cwd=ROOT)
    report = os.path.join(ROOT, "data", date, "report.md")
    print(f"\n   {'✅ 报告已生成：' + report if os.path.exists(report) else '⚠️  没找到 report.md，可能未生成完成'}")
    pause()


SOURCES = [
    ("ths_market", "同花顺行情(K线/资金榜)"), ("ths", "同花顺热榜"),
    ("sentiment", "情绪指标(连板/炸板/成交额)"), ("cls", "财联社电报"),
    ("wscn", "财经日历"), ("zsxq", "知识星球"),
    ("jiuyan", "韭研公社"), ("alphapai", "Alpha派"),
]


def do_test_source():
    clear()
    print("\n   单独测试一个数据源（便于定位是哪个源出问题）\n")
    for i, (_, label) in enumerate(SOURCES, 1):
        print(f"     [{i}] {label}")
    try:
        c = input("\n   请输入数字：").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not c.isdigit() or not 1 <= int(c) <= len(SOURCES):
        return
    key, label = SOURCES[int(c) - 1]
    clear()
    run(["run_daily.py", "--fetch", "--only", key], f"正在测试 {label} ...")
    from datetime import datetime

    f = os.path.join(ROOT, "data", datetime.now().strftime("%Y-%m-%d"), f"{key}.json")
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"\n   {'✅' if size > 200 else '⚠️  文件很小，可能没抓到内容'} {f}（{size / 1024:.1f} KB）")
        print("   把这个文件发给 Claude 即可定位问题。")
    pause()


def do_reset_site():
    clear()
    import shutil

    print("\n   重置哪个网站的连接？\n")
    print("     [1]  Alpha派")
    print("     [2]  韭研公社\n")
    print("   重置会清掉：浏览器登录态、已登记的接口、该站凭证")
    print("   清完后需要重新走一遍登录流程。\n")
    try:
        c = input("   请输入数字（回车取消）：").strip()
    except (EOFError, KeyboardInterrupt):
        return
    site = {"1": "alphapai", "2": "jiuyan"}.get(c)
    if not site:
        return

    # 1) 浏览器 profile
    prof = os.path.join(ROOT, "config", ".browser_profile", site)
    if os.path.isdir(prof):
        shutil.rmtree(prof, ignore_errors=True)
        print(f"\n   ✅ 已清除浏览器登录态")

    # 2) 已登记的列表接口（保留抓包确认过的详情接口）
    ep_path = os.path.join(ROOT, "config", "endpoints.json")
    if os.path.exists(ep_path):
        with open(ep_path, encoding="utf-8") as f:
            try:
                eps = json.load(f)
            except json.JSONDecodeError:
                eps = {}
        node = eps.get(site) or {}
        for k in ("daily_list", "bluebook_list", "article_list", "article_detail"):
            if node.pop(k, None):
                print(f"   ✅ 已清除接口登记 {site}.{k}")
        with open(ep_path, "w", encoding="utf-8") as f:
            json.dump(eps, f, ensure_ascii=False, indent=2)

    # 3) 凭证
    cred_path = os.path.join(ROOT, "config", "credentials.json")
    if os.path.exists(cred_path):
        with open(cred_path, encoding="utf-8") as f:
            try:
                creds = json.load(f)
            except json.JSONDecodeError:
                creds = {}
        if creds.pop(site, None):
            with open(cred_path, "w", encoding="utf-8") as f:
                json.dump(creds, f, ensure_ascii=False, indent=2)
            print(f"   ✅ 已清除 {site} 凭证")

    label = "Alpha派" if site == "alphapai" else "韭研公社"
    print(f"""
   {label} 已重置。接下来：
     1. 选 [7] → 选 {c}，在弹出的浏览器里登录
     2. 【关键】把目标栏目点开，让文章列表显示出来，滚动几屏
     3. 关闭浏览器窗口
     4. 选 [5] 看是否出现「✅ ...列表」
""")
    pause()


def do_backup():
    clear()
    import zipfile
    from datetime import datetime

    cfg_dir = os.path.join(ROOT, "config")
    out = os.path.join(ROOT, f"KMK配置备份_{datetime.now():%Y%m%d}.zip")
    # 只打包凭证与配置，不含浏览器 profile（体积大且换机后重登更可靠）
    files = ["credentials.json", "endpoints.json", "config.yaml"]

    picked = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in files:
            f = os.path.join(cfg_dir, n)
            if os.path.exists(f):
                z.write(f, arcname=f"config/{n}")
                picked.append(n)

    print(f"\n   ✅ 已生成备份：{out}\n")
    for n in files:
        print(f"   {'✅' if n in picked else '—'} {n}")
    print("""
   换电脑的做法：
     1. 把这个 zip 拷到新电脑（U盘/微信/网盘都行）
     2. 新电脑上下载并解压 KMK，先跑 [1] 首次安装
     3. 把 zip 里的 config 文件夹解压覆盖到 KMK 文件夹
     4. 跑 [7] 重新登录一次（浏览器登录态不在备份里）

   ⚠️ 这个 zip 含你的登录凭证，别发给别人、别传公开网盘。
""")
    if os.name == "nt":
        os.startfile(ROOT)  # noqa: S606
    pause()


def do_publish():
    clear()
    run([os.path.join("tools", "publish.py")],
        "正在生成电脑版网页并推送手机版到飞书...")
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
    "9": do_feishu_config,
    "10": do_publish,
    "11": do_open_data,
    "12": do_backup,
    "13": do_claude_report,
    "14": do_test_source,
    "15": do_reset_site,
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
