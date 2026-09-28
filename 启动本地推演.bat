@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动史鉴推演本地版……
python scripts\serve_local.py %*
if errorlevel 1 pause
