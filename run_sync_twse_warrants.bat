@echo off
chcp 65001 >nul
title 臺灣證交所 (TWSE) 上市權證資料庫歷史同步系統

echo ================================================================================
echo    臺灣證交所 (TWSE) 上市權證資料庫 (2020-01-01 起) 自動回溯建置程式
echo ================================================================================
echo.
echo 說明：
echo 1. 證交所 (TWSE) 每日權證約 3.2 萬檔，一年期共約 750 萬筆。
echo 2. 程式自動從證交所行情 (MI_INDEX type=0999) 下載並自動連結個股代號與名稱。
echo 3. 具備斷點續傳功能：若中斷，下次啟動會自動跳過已下載日期！
echo.
echo 請選擇回補模式：
echo [1] 回補一年期「有效活躍權證」（推薦：節省空間、速度快，量大於 0）
echo [2] 回補一年期「全量權證」（含成交量為 0 之全量權證）
echo [3] 僅回補最近 30 天
echo [4] 檢視權證資料庫統計狀態
echo [5] 結束
echo.
set /p choice=請輸入選項 [1-5] (預設為 1): 

cd /d "%~dp0"

if "%choice%"=="2" (
    echo.
    echo [執行] 正在啟動全量權證回溯，請保持連線...
    python scripts\sync_twse_warrants_history.py --start 2020-01-01
    goto done
)
if "%choice%"=="3" (
    echo.
    echo [執行] 正在啟動最近 30 天權證回溯...
    python scripts\sync_twse_warrants_history.py --days 30 --active-only
    goto done
)
if "%choice%"=="4" (
    echo.
    python query_warrants.py --stats
    goto done
)
if "%choice%"=="5" (
    exit /b
)

echo.
echo [執行] 正在啟動活躍權證回溯...
python scripts\sync_twse_warrants_history.py --start 2020-01-01 --active-only

:done
echo.
echo ================================================================================
echo 作業結束！您可以使用 python query_warrants.py --stats 檢視結果。
echo ================================================================================
pause
