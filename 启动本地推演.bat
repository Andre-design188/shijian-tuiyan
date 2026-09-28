@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 史鉴推演本地服务：推演期间请保持这个窗口打开
echo 史鉴推演本地服务。推演期间请一直开着这个窗口，关掉就不能推演了。
echo.
python scripts\serve_local.py %*
echo.
echo 本地服务已停止。经过记录在 logs\serve_local.log。
pause
