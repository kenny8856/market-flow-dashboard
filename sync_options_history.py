"""
TAIFEX Options Market Historical Sync Tool (期交所選擇權市場全量歷史同步工具)
Downloads and synchronizes:
1. txo_pc_ratio (每日臺指選擇權 Put/Call Ratio)
2. txo_strike_quotes (每日 TXO 各履約價行情與未沖銷契約數，用於 Max Pain 計算)
3. txo_institutional (三大法人選擇權契約金額與未平倉多空部位)
4. txo_large_trader (選擇權大額交易人與特法部位)
Supports chunked historical retrieval, smart catch-up, and daily incremental updates.
"""

import os
import sys
import argparse
import time
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.taifex_options_fetcher import TaifexOptionsFetcher
from src.taifex_options_db import TaifexOptionsDB
from src.sync_utils import get_sync_cutoff_info, print_cutoff_banner, get_smart_catchup_range

def split_date_chunks(start_str: str, end_str: str, chunk_days: int = 25):
    """將大日期區間切分為小區間，保護網路與伺服器"""
    start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()

    cur = start_dt
    while cur <= end_dt:
        nxt = min(cur + timedelta(days=chunk_days - 1), end_dt)
        yield cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")
        cur = nxt + timedelta(days=1)

def run_sync(start_date: str, end_date: str, db: TaifexOptionsDB, fetcher: TaifexOptionsFetcher):
    print("================================================================================")
    print("  [期交所選擇權市場歷史同步系統 - TAIFEX Options]")
    print(f"  目標區間: {start_date} ~ {end_date}")
    print(f"  包含模組: 1. Put/Call Ratio | 2. TXO 各履約價OI與行情 | 3. 三大法人 | 4. 大額交易人")
    print(f"  資料庫路徑: {db.db_path}")
    print("================================================================================")

    chunks = list(split_date_chunks(start_date, end_date, chunk_days=25))
    total_chunks = len(chunks)
    print(f"[*] 共規劃切分為 {total_chunks} 個分段批次依序同步 (每批約 25 天)...\n")

    start_time = time.time()
    total_pc = 0
    total_sq = 0
    total_inst = 0
    total_lt = 0

    for idx, (c_start, c_end) in enumerate(chunks, 1):
        print(f"[{idx:2d}/{total_chunks}] 正在同步區間 {c_start} ~ {c_end} ...")
        t0 = time.time()

        try:
            # 1. Put/Call Ratio
            pc = fetcher.fetch_pc_ratio(c_start, c_end)
            if pc:
                total_pc += db.insert_pc_ratios(pc)

            # 2. Strike Quotes & OI
            sq = fetcher.fetch_strike_quotes(c_start, c_end)
            if sq:
                total_sq += db.insert_strike_quotes(sq)

            # 3. Institutional
            inst = fetcher.fetch_institutional_positions(c_start, c_end)
            if inst:
                total_inst += db.insert_institutional(inst)

            # 4. Large Trader
            lt = fetcher.fetch_large_trader_positions(c_start, c_end)
            if lt:
                total_lt += db.insert_large_trader(lt)

            t_elapsed = time.time() - t0
            print(f"     -> 完成！P/C筆數: {len(pc):2d} | 履約價筆數: {len(sq):5,d} | 法人: {len(inst):3d} | 特法: {len(lt):4d} (耗時 {t_elapsed:.1f}s)")
        except Exception as e:
            print(f"     [!] 批次 {c_start} ~ {c_end} 抓取時發生異常: {e}")

        time.sleep(0.8) # 友善請求延遲

    total_elapsed = time.time() - start_time

    # 統計資料庫狀態
    earliest = db.get_earliest_date()
    latest = db.get_latest_date()
    day_count = db.get_date_count()

    print("\n================================================================================")
    print("  [同步完成報告 - TAIFEX Options]")
    print(f"  Put/Call Ratio 總筆數: {total_pc:,} 筆")
    print(f"  各履約價未平倉行情總數: {total_sq:,} 筆")
    print(f"  三大法人契約明細總數: {total_inst:,} 筆")
    print(f"  大額交易人契約明細總數: {total_lt:,} 筆")
    print(f"  資料庫涵蓋開盤日數: {day_count} 天")
    print(f"  資料庫最舊日期: {earliest}")
    print(f"  資料庫最新日期: {latest}")
    print(f"  總耗時: {total_elapsed:.1f} 秒")
    print("================================================================================")

    # 若最新日有資料，試算最新 Max Pain
    if latest:
        try:
            mp = db.calculate_max_pain(latest)
            print(f"\n[*] 【{latest} 最新期權定位快報】")
            print(f"    - 近月合約: {mp.get('expiry_month')}")
            print(f"    - Max Pain (最大痛點磁吸位): {mp.get('max_pain_strike'):,.0f} 點")
            print(f"    - 上檔壓力牆 (Call 最大未平倉): {mp.get('top_call_resistance_strike'):,.0f} 點 (OI: {mp.get('top_call_oi'):,} 口)")
            print(f"    - 下檔支撐牆 (Put 最大未平倉): {mp.get('top_put_support_strike'):,.0f} 點 (OI: {mp.get('top_put_oi'):,} 口)")
        except Exception as e:
            print(f"    [!] 試算最新 Max Pain 失敗: {e}")

def main():
    parser = argparse.ArgumentParser(description="期交所選擇權市場歷史全量同步與日常增量工具")
    parser.add_argument("--start", type=str, default="2020-01-01", help="起始日期 (YYYY-MM-DD)，預設為 2020-01-01")
    parser.add_argument("--end", type=str, help="結束日期 (YYYY-MM-DD)，預設依官方發布時程判定")
    parser.add_argument("--catchup", action="store_true", help="智慧接續同步模式 (自動自上次進度補齊至最新)")
    parser.add_argument("--daily", action="store_true", help="每日增量同步模式 (自動接續同步缺漏日)")
    args = parser.parse_args()

    print_cutoff_banner("options")
    cutoff_info = get_sync_cutoff_info("options")
    safe_end = cutoff_info["target_end_date"]

    db = TaifexOptionsDB()
    fetcher = TaifexOptionsFetcher()

    if args.catchup or args.daily:
        latest_in_db = db.get_latest_date()
        default_s = "2020-01-01"
        start_str, end_str, needs_sync, msg = get_smart_catchup_range("options", latest_in_db, default_start=default_s)
        print(f">> [智慧接續補齊模式] {msg}\n")
        if not needs_sync:
            print("[✓] 選擇權資料庫已是最新狀態，無需同步。")
            return
        run_sync(start_str, end_str, db, fetcher)
        return

    end_str = args.end if args.end else safe_end
    if end_str > safe_end and not cutoff_info["is_today_included"]:
        print(f"[提示] 指定結束日 ({end_str}) 超過官方公布時程，自動調整終點為: {safe_end}")
        end_str = safe_end

    start_str = args.start
    run_sync(start_str, end_str, db, fetcher)

if __name__ == "__main__":
    main()
