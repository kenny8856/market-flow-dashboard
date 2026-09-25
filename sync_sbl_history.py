import sys
import argparse
import time
from datetime import datetime, timedelta
from typing import List

from src.sbl_fetcher import SBLFetcher
from src.sbl_db import SBLDatabase
from src.sync_utils import get_sync_cutoff_info, print_cutoff_banner, get_smart_catchup_range

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_candidate_dates(start_date_str: str, end_date_str: str) -> List[str]:
    """產生指定日期範圍內的所有平日（週一至週五）清單"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    
    dates = []
    curr = start_dt
    while curr <= end_dt:
        if curr.weekday() < 5:
            dates.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
    return dates

def sync_sbl(
    start_date: str = "2020-01-01",
    end_date: str = None,
    daily_mode: bool = False,
    catchup_mode: bool = False,
    delay: float = 1.2
):
    print_cutoff_banner("sbl")
    db = SBLDatabase()
    fetcher = SBLFetcher(polite_delay=delay)

    cutoff_info = get_sync_cutoff_info("sbl")
    safe_end_date = cutoff_info["target_end_date"]

    if catchup_mode:
        latest_date = db.get_latest_date()
        start_date, end_date, needs_sync, msg = get_smart_catchup_range("sbl", latest_date, default_start="2020-01-01")
        print(f">> [智慧接續補齊模式] {msg}\n")
        if not needs_sync:
            print("[✓] 資料庫已是最完整最新狀態，無需同步。")
            return
    else:
        if not end_date:
            end_date = safe_end_date
        elif end_date > safe_end_date and not cutoff_info["is_today_included"]:
            print(f"[提示] 指定結束日 ({end_date}) 超過最新公布日，自動調整終點為: {safe_end_date}")
            end_date = safe_end_date

        if daily_mode:
            start_date = (datetime.now().date() - timedelta(days=7)).strftime("%Y-%m-%d")

    mode_label = "智慧接續補齊" if catchup_mode else ("日常增量(7天)" if daily_mode else "歷史全量回溯")
    print("=" * 90)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動全市場個股借券與借券賣出資料庫同步")
    print(f"同步區間: {start_date} ~ {end_date} | 模式: {mode_label} | 請求間隔: {delay}s")
    print("=" * 90)

    candidate_dates = get_candidate_dates(start_date, end_date)
    synced_dates = db.get_synced_dates()
    total_dates = len(candidate_dates)

    print(f">> 目標候選工作日總計: {total_dates} 天 (已自動排除週末例假日)")
    print(f">> 資料庫已收錄完整: {len(synced_dates)} 天\n")

    synced_count = 0
    holiday_count = 0
    start_time = time.time()

    for idx, date_str in enumerate(candidate_dates, 1):
        progress_pct = round(idx / total_dates * 100, 1)

        if date_str in synced_dates:
            print(f"[{idx}/{total_dates}] {date_str} ({progress_pct}%) -> [已完整收錄，跳過]")
            continue

        print(f"[{idx}/{total_dates}] {date_str} ({progress_pct}%)...", end=" ", flush=True)

        completeness = db.check_date_completeness(date_str)

        try:
            # 1. 抓取借券餘額 (TWT72U: 上市 + 上櫃)
            if not completeness["has_balance"]:
                bal_rows = fetcher.fetch_sbl_balance(date_str)
                if bal_rows:
                    db.save_sbl_balance(date_str, bal_rows)

            # 2. 抓取上市借券賣出與融券 (TWT93U)
            if not completeness["has_twse_short"]:
                twse_short = fetcher.fetch_twse_sbl_short(date_str)
                if twse_short:
                    db.save_sbl_short(date_str, twse_short, market_type="上市")

            # 3. 抓取上櫃借券賣出與融券 (margin_sbl)
            if not completeness["has_tpex_short"]:
                tpex_short = fetcher.fetch_tpex_sbl_short(date_str)
                if tpex_short:
                    db.save_sbl_short(date_str, tpex_short, market_type="上櫃")

            # 再次檢查完整度
            final_status = db.check_date_completeness(date_str)
            db.record_sync_progress(date_str, final_status["bal_cnt"], final_status["twse_short_cnt"] + final_status["tpex_short_cnt"])

            if final_status["bal_cnt"] == 0 and final_status["twse_short_cnt"] == 0 and final_status["tpex_short_cnt"] == 0:
                print("未開盤或無資料 (標記休市)")
                holiday_count += 1
                continue

            if final_status["has_balance"] and final_status["has_twse_short"] and final_status["has_tpex_short"]:
                print(f"完整寫入 (借券餘額: {final_status['bal_cnt']}筆, 借券賣出: {final_status['twse_short_cnt'] + final_status['tpex_short_cnt']}筆 [上市{final_status['twse_short_cnt']}+上櫃{final_status['tpex_short_cnt']}])")
                synced_count += 1
            else:
                print(f"部分寫入 (餘額: {final_status['bal_cnt']}, 上市: {final_status['twse_short_cnt']}, 上櫃: {final_status['tpex_short_cnt']})，保留進度以便後續補跑")

        except Exception as e:
            print(f"發生異常: {e}")
            time.sleep(3.0)

    elapsed = round(time.time() - start_time, 2)
    stats = db.get_market_stats()

    print("\n" + "=" * 90)
    print("【借券資料庫同步完成報告】")
    print(f"本次同步耗時: {elapsed} 秒 | 新增交易日: {synced_count} 天 | 休市日: {holiday_count} 天")
    print(f"資料庫最新收錄範圍: {stats['min_date']} ~ {stats['max_date']} (共 {stats['trading_days']} 個開盤交易日)")
    print(f"全市場總筆數: {stats['total_records']:,} 筆 (借券餘額 {stats['balance_records']:,} 筆 + 借券賣出/融券 {stats['short_records']:,} 筆)")
    print(f"涵蓋上市櫃股票數: {stats['stocks_count']:,} 檔")
    print("=" * 90)

def main():
    parser = argparse.ArgumentParser(description="臺灣全市場個股借券資料庫歷史回溯與每日同步工具")
    parser.add_argument("--start", type=str, default="2020-01-01", help="開始日期 (YYYY-MM-DD，預設 2020-01-01)")
    parser.add_argument("--end", type=str, default=None, help="結束日期 (YYYY-MM-DD，預設依官方發布時程自動判定)")
    parser.add_argument("--catchup", action="store_true", help="智慧接續同步模式 (無論出差隔多久，自動自上次進度補齊至最新)")
    parser.add_argument("--daily", action="store_true", help="日常盤後增量模式 (自動同步近 7 天缺漏數據)")
    parser.add_argument("--delay", type=float, default=1.2, help="請求間隔延遲秒數 (預設 1.2 秒)")

    args = parser.parse_args()
    sync_sbl(
        start_date=args.start,
        end_date=args.end,
        daily_mode=args.daily,
        catchup_mode=args.catchup,
        delay=args.delay
    )

if __name__ == "__main__":
    main()
