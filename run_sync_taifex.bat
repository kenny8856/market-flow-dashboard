@echo off
chcp 65001 >nul
title 臺灣期交所 - 大額交易人籌碼同步系統

:menu
cls
echo ================================================================================
echo   臺灣期交所 (TAIFEX) 大額交易人籌碼資料庫同步系統
echo ================================================================================
echo.
echo 【官方發布時程與防呆備註】
echo   * 官方時程：營業日 15:30 之後由期交所公布大額交易人未沖銷部位結構表。
echo   * 防呆機制：若當前未達 15:30，系統自動排除今日，終點設為前一營業日。
echo.
echo 請選擇功能項目：
echo   [1] 智慧接續同步至最新 (推薦：出差多久都能自動接續補齊)
echo   [2] 回補完整歷史資料 (自 2020-01-01 起，含全數個股期貨)
echo   [3] 查詢 臺股期貨 (TX) 最新 5 天大額交易人籌碼
echo   [4] 查詢 台積電期貨 (CD) 最新 5 天大額交易人籌碼
echo   [5] 查詢 鴻海期貨 (DH) 最新 5 天大額交易人籌碼
echo   [6] 列出資料庫收錄之所有期貨商品清單 (--list)
echo   [7] 自訂查詢任一商品 (輸入名稱或代碼)
echo   [0] 離開
echo.
echo ================================================================================
set /p choice=請輸入選項 [0-7] (預設為 1): 
if "%choice%"=="" set choice=1

cd /d "%~dp0"

if "%choice%"=="1" (
    echo.
    python sync_taifex_history.py --catchup
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    python sync_taifex_history.py
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    python query_taifex_trader.py TX --days 5
    echo.
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    python query_taifex_trader.py CD --days 5
    echo.
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    python query_taifex_trader.py DH --days 5
    echo.
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    python query_taifex_trader.py --list
    echo.
    pause
    goto menu
)
if "%choice%"=="7" (
    echo.
    set /p custom_target=請輸入期貨名稱或代碼 (如: 台積電, 鴻海, 聯發科, 聯電, TX, CD...): 
    python query_taifex_trader.py %custom_target% --days 5
    echo.
    pause
    goto menu
)
if "%choice%"=="0" exit /b
goto menu
