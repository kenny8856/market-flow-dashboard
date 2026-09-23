@echo off
chcp 65001 >nul
cd /d "%~dp0"

python scripts\set_github_token.py

echo.
pause
