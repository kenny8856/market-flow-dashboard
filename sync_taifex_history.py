import os
import sys
import argparse
import time
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.taifex_large_trader_fetcher import TaifexLargeTraderFetcher
from src.taifex_db import TaifexLargeTraderDB
from src.sync_utils import get_sync_cutoff_info, print_cutoff_banner, get_smart_catchup_range

def run_sync(start_date: str, end_date: str, db: TaifexLargeTraderDB, fetcher: TaifexLargeTraderFetcher):
    print("================================================================================")
    print(f"  [期交所大額交易人歷史同步系統 - 全市場期貨與個股期貨] 執行中...")
    print(f"  目標區間: {start_date} ~ {end_date}")
    print(f"  目標標的: 全市場所有期貨商品與個股期貨 (包含臺指、電子、金融、台積電、鴻海等 300+ 檔)")
    print(f"  包含合約: 當月契約、所有契約、遠月契約 (公式: 所有-當月)、週契約")
    print(f"  資料庫路徑: {db.db_path}")
    print("================================================================================")

    start_time = time.time()
    records = fetcher.fetch_chunked_history(start_date, end_date, chunk_days=80, delay_seconds=0.8)

    if not records:
        print("\n[!] 未抓取到任何資料，請檢查網路連線或日期設定。")
        return

    print(f"\n[*] 抓取完成！共解析出 {len(records):,} 筆契約記錄。正在寫入 SQLite 資料庫...")
    inserted = db.insert_records(records)
    elapsed = time.time() - start_time

    # 統計資料庫狀態
    earliest = db.get_earliest_date()
    latest = db.get_latest_date()
    day_count = db.get_date_count()
    all_c = db.get_all_contracts()

    print("================================================================================")
    print(f"  [同步完成報告]")
    print(f"  本次寫入/更新記錄數: {inserted:,} 筆")
    print(f"  收錄商品總數: {len(all_c)} 檔期貨與個股期貨")
    print(f"  資料庫最新交易日: {latest}")
    print(f"  資料庫最舊交易日: {earliest}")
    print(f"  資料庫涵蓋總交易日: {day_count} 天")
    print(f"  總耗時: {elapsed:.2f} 秒")
    print("================================================================================")

def main():
    parser = argparse.ArgumentParser(description="期交所期貨大額交易人未沖銷部位結構歷史資料庫同步工具")
    parser.add_argument("--start", type=str, help="起始日期 (YYYY-MM-DD)，預設為一年前")
    parser.add_argument("--end", type=str, help="結束日期 (YYYY-MM-DD)，預設依官方發布時程判定")
    parser.add_argument("--catchup", action="store_true", help="智慧接續同步模式 (無論出差隔多久，自動自上次進度補齊至最新)")
    parser.add_argument("--daily", action="store_true", help="每日增量同步模式 (自動接續同步缺漏日)")
    args = parser.parse_args()

    print_cutoff_banner("taifex")
    cutoff_info = get_sync_cutoff_info("taifex")
    safe_end = cutoff_info["target_end_date"]

    db = TaifexLargeTraderDB()
    fetcher = TaifexLargeTraderFetcher()

    if args.catchup or args.daily:
        latest_in_db = db.get_latest_date()
        default_s = "2020-01-01"
        start_str, end_str, needs_sync, msg = get_smart_catchup_range("taifex", latest_in_db, default_start=default_s)
        print(f">> [智慧接續補齊模式] {msg}\n")
        if not needs_sync:
            print("[✓] 期貨大額交易人資料庫已是最新狀態，無需同步。")
            return
        run_sync(start_str, end_str, db, fetcher)
        return

    # 預設歷史區間：從 2020-01-01 開始
    end_str = args.end if args.end else safe_end
    if end_str > safe_end and not cutoff_info["is_today_included"]:
        print(f"[提示] 指定結束日 ({end_str}) 超過官方公布時程，自動調整終點為: {safe_end}")
        end_str = safe_end

    end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()

    if args.start:
        start_str = args.start
    else:
        start_str = "2020-01-01"

    run_sync(start_str, end_str, db, fetcher)

if __name__ == "__main__":
    main()
