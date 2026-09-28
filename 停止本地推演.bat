@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 史鉴推演：停止本地服务
python scripts\serve_local.py --stop %*
timeout /t 3 >nul
