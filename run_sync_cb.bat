@echo off
chcp 65001 >nul
title 臺灣可轉換公司債 (CB) 市場資料庫同步系統

:menu
cls
echo ================================================================================
echo   臺灣可轉換公司債 (CB) 市場資料庫同步系統
echo ================================================================================
echo.
echo 【官方發布時程與防呆備註】
echo   * 官方時程：營業日 16:00 之後由櫃買中心公布可轉債收盤行情與折溢價。
echo   * 防呆機制：若當前未達 16:00，系統自動排除今日，終點設為前一營業日。
echo.
echo 請選擇功能項目：
echo   [1] 智慧接續同步至最新 (推薦：出差多久都能自動接續補齊)
echo   [2] 同步最近 7 天資料
echo   [3] 回補完整歷史資料 (自 2020-01-01 起)
echo   [4] 查詢最新可轉債行情 (依成交量排行)
echo   [5] 查詢低溢價率 / 折價可轉債
echo   [0] 離開
echo.
echo ================================================================================
set /p choice=請輸入選項 [0-5] (預設為 1): 
if "%choice%"=="" set choice=1

cd /d "%~dp0"

if "%choice%"=="1" (
    echo.
    python sync_cb_history.py --catchup
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    python sync_cb_history.py --days 7
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    python sync_cb_history.py --start 2020-01-01
    echo.
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    python query_cb.py --sort volume --limit 25
    echo.
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    python query_cb.py --undervalued --limit 25
    echo.
    pause
    goto menu
)
if "%choice%"=="0" exit /b
goto menu
