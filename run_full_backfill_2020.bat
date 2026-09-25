@echo off
title 臺股全量歷史數據自動補足系統 (2020-01-01 起)

echo ================================================================================
echo   【臺股全量歷史數據自動補足系統 (自 2020-01-01 起)】
echo ================================================================================
echo.
echo 即將依序執行以下歷史全量補齊作業：
echo   [0] 臺股上市櫃行情與三大法人 (主資料庫)
echo   [1] 融資融券 (margin)
echo   [2] 借券與借券賣出 (sbl)
echo   [3] 選擇權全鏈數據 (options)
echo   [4] 櫃買可轉債 (cb)
echo   [5] 期交所大額交易人 (taifex)
echo   [6] 上市權證 (twse_warrants)
echo.
echo 警告：此作業會從官方網站抓取高達 5 年以上的鉅量資料，
echo 將耗費非常長的時間 (可能需通宵執行)，請確保網路連線穩定且不會休眠！
echo.
echo ================================================================================
pause

echo.
echo [0/6] 正在回補 臺股上市櫃行情與三大法人 歷史資料...
python sync_360_days.py --start 2020-01-01

echo.
echo [1/6] 正在回補 融資融券 歷史資料...
python sync_margin_history.py --start 2020-01-01

echo.
echo [2/6] 正在回補 借券與借券賣出 歷史資料...
python sync_sbl_history.py --start 2020-01-01

echo.
echo [3/6] 正在回補 選擇權全鏈數據 歷史資料...
python sync_options_history.py --start 2020-01-01

echo.
echo [4/6] 正在回補 櫃買可轉債 (CB) 歷史資料...
python sync_cb_history.py --start 2020-01-01

echo.
echo [5/6] 正在回補 期交所大額交易人 歷史資料...
python sync_taifex_history.py --start 2020-01-01

echo.
echo [6/6] 正在回補 上市權證 歷史資料...
python scripts\sync_twse_warrants_history.py --start 2020-01-01

echo.
echo ================================================================================
echo 全數歷史資料補足作業已全部結束，您可以開始回測了！
echo ================================================================================
pause
