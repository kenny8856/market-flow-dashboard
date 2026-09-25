@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ===============================================================================
echo   【臺股量化實戰報告 - Gmail 一鍵自動寄送系統】
echo ===============================================================================
echo.
echo   * 準備將最新量化報告 (quant_regime.html 及 dashboard.html) 透過 Gmail SMTP 寄送
echo   * 設定檔位置: config/email_config.json
echo.

python send_report_email.py

echo.
echo ===============================================================================
pause
