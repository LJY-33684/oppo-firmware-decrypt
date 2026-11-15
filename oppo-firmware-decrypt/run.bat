@echo off
chcp 65001 >nul
cd /d %~dp0

rem 1) 实际执行一次 --version：可同时识破 PATH 缺失与 WindowsApps 空存根
python --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到可用的 Python 环境。
    echo        请安装 Python 3.10 或更高版本，安装时勾选 "Add python.exe to PATH"。
    echo        若已安装仍报错，请检查 PATH，或改用 py -3 启动。
    pause
    exit /b 1
)

rem 2) 版本门槛：低于 3.10 直接给出可读提示
python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前 Python 版本低于 3.10，本工具需要 Python 3.10+。
    python --version
    pause
    exit /b 1
)

rem 3) GUI 需要 tkinter：部分精简运行时（含沙箱运行时）缺 Tcl/Tk，需换解释器
python -c "import tkinter;tkinter.Tk().destroy()" >nul 2>nul
if not errorlevel 1 goto run_default

py -3 -c "import tkinter;tkinter.Tk().destroy()" >nul 2>nul
if not errorlevel 1 (
    echo [提示] 默认 python 缺少 tkinter，改用 py -3 启动。
    py -3 main.py
    if errorlevel 1 pause
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python315\python.exe" (
    "%LocalAppData%\Programs\Python\Python315\python.exe" -c "import tkinter;tkinter.Tk().destroy()" >nul 2>nul
    if not errorlevel 1 (
        echo [提示] 默认 python 缺少 tkinter，改用 Python 3.15 启动。
        "%LocalAppData%\Programs\Python\Python315\python.exe" main.py
        if errorlevel 1 pause
        exit /b 0
    )
)

echo [错误] 当前 Python 缺少 tkinter（Tcl/Tk）组件，无法启动图形界面。
echo        请安装官方 Python 3.10+（勾选 tcl/tk），或改用命令行：
echo        python decrypt_cli.py decrypt --input ^<固件^>
pause
exit /b 1

:run_default
python main.py
if errorlevel 1 pause
