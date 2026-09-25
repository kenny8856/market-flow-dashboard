@echo off
chcp 65001 >nul
title 臺灣期交所 - 選擇權市場與 Max Pain 籌碼系統

:menu
cls
echo ================================================================================
echo   臺灣期交所 (TAIFEX) 選擇權市場資料庫同步與分析系統
echo ================================================================================
echo.
echo 【官方發布時程與防呆備註】
echo   * 官方時程：營業日 15:30 之後由期交所公布選擇權交易行情與 Put/Call Ratio。
echo   * 防呆機制：若當前未達 15:30，系統自動排除今日，終點設為前一營業日。
echo.
echo 請選擇功能項目：
echo   [1] 智慧接續同步至最新 (推薦：自動接續缺漏日)
echo   [2] 回補自 2020-01-01 完整選擇權歷史全鏈數據
echo   [3] 計算最新一日 Max Pain (最大痛點) 與支撐壓力牆
echo   [4] 查詢 臺指選擇權 Put/Call Ratio 近 15 天走勢
echo   [5] 查詢 三大法人選擇權多空契約金額與部位
echo   [6] 檢視 選擇權資料庫狀態與總筆數統計
echo   [0] 離開
echo.
echo ================================================================================
set /p choice=請輸入選項 [0-6] (預設為 1): 
if "%choice%"=="" set choice=1

cd /d "%~dp0"

if "%choice%"=="1" (
    echo.
    python sync_options_history.py --catchup
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    python sync_options_history.py --start 2020-01-01
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    python query_options.py --max-pain
    echo.
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    python query_options.py --pc-ratio --days 15
    echo.
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    python query_options.py --institutional
    echo.
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    python query_options.py --stats
    echo.
    pause
    goto menu
)
if "%choice%"=="0" (
    exit /b
)

goto menu
