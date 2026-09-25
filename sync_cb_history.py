"""
Sync Taiwan Convertible Bond (CB) Historical Data
Backfills or updates daily CB market data and basic profiles into db/cb_market.db.

Usage:
    python sync_cb_history.py --catchup
    python sync_cb_history.py --days 7
    python sync_cb_history.py --start 2020-01-01 --end 2026-09-17
    python sync_cb_history.py --date 2026-09-17
"""

import os
import sys
import argparse
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.cb_fetcher import CBFetcher
from src import cb_db
from src.sync_utils import get_sync_cutoff_info, print_cutoff_banner, get_smart_catchup_range


def sync_range(start_date: str, end_date: str, force: bool = False):
    """Sync CB data for a specified date range."""
    cb_db.init_db()
    fetcher = CBFetcher()

    print("=" * 70)
    print("臺灣可轉換公司債 (CB) 市場資料庫同步程式")
    print(f"同步區間: {start_date} ~ {end_date} (強制覆蓋: {force})")
    print("=" * 70)

    # 1. 更新可轉債基本資料 (Master Table)
    print("\n[步驟 1/2] 更新全市場可轉債基本資料 (TPEx OpenAPI)...")
    basics = fetcher.fetch_cb_basic_info()
    if basics:
        saved_b = cb_db.save_basic_info(basics)
        print(f"  -> 成功取得並儲存 {saved_b} 檔可轉債基本資料")
    else:
        print("  -> 警告: 未能取得可轉債發行資料，將使用本機股票庫對應")

    # 2. 準備日期列表
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    date_list = []
    curr = start_dt
    while curr <= end_dt:
        date_list.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)

    print(f"\n[步驟 2/2] 開始下載每日行情 (共 {len(date_list)} 天)...")
    synced_dates = cb_db.get_synced_dates()

    total_days = len(date_list)
    success_days = 0
    holiday_days = 0
    total_records = 0

    for idx, d_str in enumerate(date_list, 1):
        if not force and d_str in synced_dates:
            print(f"  [{idx}/{total_days}] {d_str} -> [已同步過，跳過]")
            continue

        dt = datetime.strptime(d_str, "%Y-%m-%d")
        if dt.weekday() >= 5:
            cb_db.mark_no_data_date(d_str)
            holiday_days += 1
            continue

        print(f"  [{idx}/{total_days}] {d_str} 下載中...", end=" ", flush=True)
        try:
            quotes = fetcher.fetch_cb_daily(d_str)
            if not quotes:
                cb_db.mark_no_data_date(d_str)
                print("無交易資料 / 休市 (標記完成)")
                holiday_days += 1
            else:
                saved = cb_db.save_daily_quotes(d_str, quotes)
                print(f"成功儲存 {saved} 筆行情指標")
                success_days += 1
                total_records += saved
        except Exception as e:
            print(f"下載失敗: {e}")

        time.sleep(0.3)

    print("\n" + "=" * 70)
    print("同步作業完成！")
    print(f"  * 成功同步交易日: {success_days} 天")
    print(f"  * 休市/無資料: {holiday_days} 天")
    print(f"  * 累積新增筆數: {total_records} 筆")
    print(f"  * 資料庫路徑: {cb_db.DB_PATH}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Sync Taiwan Convertible Bond (CB) Market Data")
    parser.add_argument("--days", type=int, default=None, help="Sync past N days from today")
    parser.add_argument("--catchup", action="store_true", help="智慧接續同步模式 (無論出差隔多久，自動自上次進度補齊至最新)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--date", type=str, default=None, help="Sync a single date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if already synced")

    args = parser.parse_args()

    print_cutoff_banner("cb")
    cutoff_info = get_sync_cutoff_info("cb")
    safe_end = cutoff_info["target_end_date"]

    if args.catchup:
        latest_in_db = cb_db.get_latest_date()
        default_s = (datetime.now().date() - timedelta(days=365)).strftime("%Y-%m-%d")
        start_date, end_date, needs_sync, msg = get_smart_catchup_range("cb", latest_in_db, default_start=default_s)
        print(f">> [智慧接續補齊模式] {msg}\n")
        if not needs_sync:
            print("[✓] 可轉債資料庫已是最新狀態，無需同步。")
            return
        sync_range(start_date, end_date, force=args.force)
        return

    if args.date:
        start_date = args.date
        end_date = args.date
    elif args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.start:
        start_date = args.start
        end_date = safe_end
    elif args.days:
        end_date = safe_end
        start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    else:
        # 預設：自動使用智慧接續模式
        latest_in_db = cb_db.get_latest_date()
        default_s = "2020-01-01"
        start_date, end_date, needs_sync, msg = get_smart_catchup_range("cb", latest_in_db, default_start=default_s)
        print(f">> [預設智慧接續模式] {msg}\n")
        if not needs_sync:
            print("[✓] 可轉債資料庫已是最新狀態，無需同步。")
            return

    if end_date > safe_end and not cutoff_info["is_today_included"]:
        print(f"[提示] 指定結束日 ({end_date}) 超過最新公布日，自動調整終點為: {safe_end}")
        end_date = safe_end

    sync_range(start_date, end_date, force=args.force)


if __name__ == "__main__":
    main()
