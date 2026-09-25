"""
TDCC Equity Distribution Sync Tool (集保戶股權分散表每週同步工具)
Downloads and synchronizes:
1. 全市場 2,000+ 檔上市櫃股票當週最新股權分散級距表 (via Open Data)
2. 支援指定單檔個股回補近一年歷史數據 (via TDCC Web Portal)
"""

import os
import sys
import argparse
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.tdcc_fetcher import TdccFetcher
from src.tdcc_db import TdccDB
from src.sync_utils import print_cutoff_banner

def main():
    parser = argparse.ArgumentParser(description="集保戶股權分散表每週同步工具")
    parser.add_argument("--stock", type=str, help="指定單一個股代號 (如 2330) 進行近一年歷史回補")
    parser.add_argument("--stocks", nargs="+", help="指定多檔個股代號進行歷史回補")
    args = parser.parse_args()

    print_cutoff_banner("tdcc")

    db = TdccDB()
    fetcher = TdccFetcher()

    # 若指定個股回補歷史
    targets = []
    if args.stock:
        targets.append(args.stock)
    if args.stocks:
        targets.extend(args.stocks)

    if targets:
        print(f"[*] 啟動指定個股歷史回補模式，標的: {targets} ...")
        for sid in targets:
            print(f"[*] 正在連線集保中心查詢 {sid} 近一年所有週次股權分散資料...")
            records = fetcher.fetch_stock_history_web(sid)
            if records:
                inserted = db.insert_records(records)
                print(f"[✓] {sid} 歷史回補完成！寫入 {inserted} 筆明細，涵蓋 {len(set(r['date'] for r in records))} 週。")
                summary = db.get_stock_summary(sid)
                print(f"    最新狀態 ({summary['date']}): 千張大戶: {summary['pct_over_1000']}% | 400張大戶: {summary['pct_over_400']}% | 總股東: {summary['total_shareholders']:,} 人")
            else:
                print(f"[!] {sid} 未查詢到歷史資料。")
        return

    # 預設模式：同步當週最新全市場資料
    print("================================================================================")
    print("  [集保戶股權分散表每週同步 - 全市場上市櫃]")
    print(f"  資料庫路徑: {db.db_path}")
    print("================================================================================")

    start_time = time.time()
    print("[*] 正在向政府資料開放平台下載全市場最新週 CSV...")
    records = fetcher.fetch_latest_all_market()

    if not records:
        print("[!] 下載或解析失敗，請確認網路連線。")
        return

    date_str = records[0]["date"]
    print(f"[*] 成功下載並解析 {len(records):,} 筆級距記錄！資料日期: {date_str}")
    inserted = db.insert_records(records)
    elapsed = time.time() - start_time

    stock_count = db.get_stock_count(date_str)
    all_dates = db.get_date_count()

    print("================================================================================")
    print("  [同步完成報告 - 集保戶股權分散表]")
    print(f"  本次寫入筆數: {inserted:,} 筆")
    print(f"  涵蓋上市櫃股票數: {stock_count:,} 檔")
    print(f"  資料庫累積週次數: {all_dates} 週")
    print(f"  總耗時: {elapsed:.2f} 秒")
    print("================================================================================")

if __name__ == "__main__":
    main()
