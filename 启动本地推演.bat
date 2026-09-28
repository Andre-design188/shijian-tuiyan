@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 史鉴推演：启动本地服务
python scripts\serve_local.py --background %*
if errorlevel 1 (
  echo.
  echo 没有启动成功，原因见上面。经过也记在 logs\serve_local.log。
  pause
  exit /b 1
)
echo.
echo 这个窗口 5 秒后自动关闭。
timeout /t 5 >nul
