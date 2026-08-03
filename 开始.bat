@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title 舆情交叉分析报告系统

:: 找可用的 Python（用 --version 实测，避免误认应用商店的占位程序）
set PY=
python --version >nul 2>&1 && set PY=python
if "!PY!"=="" (
  py --version >nul 2>&1 && set PY=py
)
if "!PY!"=="" (
  echo.
  echo   [!] 没有找到 Python，需要先装一次（以后就不用装了）
  echo.
  echo   最简单的办法：
  echo     打开「Microsoft Store」应用商店，搜索 Python，点「获取」
  echo.
  echo   或去 python.org/downloads 下载，
  echo   安装时【务必勾选】"Add Python to PATH"。
  echo.
  echo   装好后重新双击本文件即可。
  echo.
  pause
  exit /b
)

:menu
cls
echo.
echo  ============================================================
echo              舆情交叉分析报告系统
echo  ============================================================
echo.
echo    [1]  首次安装        ^(第一次使用选这个，装完不用再选^)
echo.
echo    [2]  登录 Alpha派    ^(弹浏览器，登录后点开「每日必看」^)
echo    [3]  登录 韭研公社    ^(弹浏览器，登录后点开「关注」栏目^)
echo.
echo    [4]  抓取今日数据 + 生成报告骨架      ^<^<^< 每天点这个
echo.
echo    [5]  检查凭证状态
echo    [6]  只抓免登录的数据源 ^(抓不通时的保底方案^)
echo.
echo    [0]  退出
echo.
echo  ============================================================
echo.
set choice=
set /p choice=  请输入数字后按回车：

if "%choice%"=="1" goto install
if "%choice%"=="2" goto login_ap
if "%choice%"=="3" goto login_jy
if "%choice%"=="4" goto daily
if "%choice%"=="5" goto check
if "%choice%"=="6" goto safe
if "%choice%"=="0" exit /b
goto menu

:install
cls
echo.
echo   正在安装依赖，第一次比较慢（几分钟），请耐心等待...
echo.
!PY! -m pip install --upgrade pip
!PY! -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo   正在安装浏览器组件...
echo.
!PY! -m playwright install chromium
if not exist "config\credentials.json" (
  copy "config\credentials.example.json" "config\credentials.json" >nul
  echo.
  echo   已生成凭证文件 config\credentials.json
)
echo.
echo   [OK] 安装完成！接下来请依次选 [2] 和 [3] 登录。
echo.
pause
goto menu

:login_ap
cls
echo.
echo   即将弹出浏览器窗口，请在浏览器里：
echo.
echo     1. 登录 Alpha派
echo     2. 点开「蓝宝书」 - 「PaiPai总结」 - 「每日必看」
echo     3. 等内容显示出来，往下滚动几屏
echo     4. 然后【直接关闭浏览器窗口】
echo.
pause
!PY! tools\harvest_token.py alphapai
echo.
pause
goto menu

:login_jy
cls
echo.
echo   即将弹出浏览器窗口，请在浏览器里：
echo.
echo     1. 登录 韭研公社
echo     2. 点开「关注」栏目下的「每日公社内容精选」
echo        「学习笔记」「公告内容精选」「盘前纪要」
echo     3. 等内容显示出来，往下滚动几屏
echo     4. 然后【直接关闭浏览器窗口】
echo.
pause
!PY! tools\harvest_token.py jiuyan
echo.
pause
goto menu

:daily
cls
echo.
echo   正在抓取今日数据，需要几分钟，请勿关闭窗口...
echo.
!PY! run_daily.py --all --refresh
echo.
echo  ============================================================
echo   抓取结束，数据已存到 data\ 目录下今天日期的文件夹。
echo.
echo   接下来：在本文件夹打开 Claude Code，说「生成今日报告」
echo  ============================================================
echo.
pause
goto menu

:check
cls
echo.
!PY! tools\check_token.py
echo.
pause
goto menu

:safe
cls
echo.
echo   只抓不需要登录的数据源（大盘技术研判、资金榜、热榜、
echo   财联社电报、财经日历、雪球热帖）...
echo.
!PY! run_daily.py --all --only eastmoney,ths,cls,wscn,xueqiu
echo.
pause
goto menu

:failed
echo.
echo   [!] 安装出错了，请把上面的报错内容复制给 Claude。
echo.
pause
goto menu
