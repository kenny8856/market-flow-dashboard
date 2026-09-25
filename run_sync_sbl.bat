@echo off
chcp 65001 >nul
title 臺灣全市場個股借券與借券賣出資料庫同步與分析系統

:menu
cls
echo ================================================================================
echo   臺灣全市場個股借券與借券賣出 (SBL) 資料庫系統
echo ================================================================================
echo.
echo 【官方發布時程與防呆備註】
echo   * 官方時程：營業日 20:30 之後由交易所與櫃買中心公布借券餘額與借券賣出表。
echo   * 防呆機制：若當前未達 20:30，系統自動排除今日，終點設為前一營業日。
echo.
echo 請選擇功能項目：
echo   --------------------【資料庫同步與補齊】--------------------
echo   [1] 智慧接續同步至最新 (推薦：出差多久都能自動接續補齊)
echo   [2] 快速同步最近 7 天
echo   [3] 歷史全量回溯重掃 (從 2020-01-01 至今完整重建)
echo.
echo   --------------------【借券籌碼查詢與篩選】------------------
echo   [4] 查詢 台積電 (2330) 最新借券與借券賣出明細
echo   [5] 查詢 鴻海   (2317) 最新借券與借券賣出明細
echo   [6] 查詢 元太   (8069) 最新借券與借券賣出明細
echo   [7] 查詢 全市場【借券賣出餘額 (放空存量)】前 20 大排行
echo   [8] 查詢 全市場【借券總餘額】前 20 大排行
echo   [9] 查詢 全市場【當日借券賣出量 (放空力道)】前 20 大排行
echo   [10] 自訂查詢任一個股或中文名稱 (如: 長榮、群創)
echo   [11] 檢視資料庫目前收錄統計現況
echo   [0] 離開
echo.
echo ================================================================================
set /p choice=請輸入選項 [0-11] (預設為 1): 
if "%choice%"=="" set choice=1

cd /d "%~dp0"

if "%choice%"=="1" (
    echo.
    python sync_sbl_history.py --catchup
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    python sync_sbl_history.py --daily
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    python sync_sbl_history.py --start 2020-01-01
    echo.
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    python query_sbl.py 2330 --days 15
    echo.
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    python query_sbl.py 2317 --days 15
    echo.
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    python query_sbl.py 8069 --days 15
    echo.
    pause
    goto menu
)
if "%choice%"=="7" (
    echo.
    python query_sbl.py --top-short --limit 20
    echo.
    pause
    goto menu
)
if "%choice%"=="8" (
    echo.
    python query_sbl.py --top-borrow --limit 20
    echo.
    pause
    goto menu
)
if "%choice%"=="9" (
    echo.
    python query_sbl.py --top-sell --limit 20
    echo.
    pause
    goto menu
)
if "%choice%"=="10" (
    echo.
    set /p sname=請輸入欲查詢之股票代號或中文簡稱: 
    python query_sbl.py %sname% --days 15
    echo.
    pause
    goto menu
)
if "%choice%"=="11" (
    echo.
    python query_sbl.py --stats
    echo.
    pause
    goto menu
)
if "%choice%"=="0" exit /b
goto menu
