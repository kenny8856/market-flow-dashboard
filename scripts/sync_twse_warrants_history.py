import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import json
import ssl
import urllib.request
import sqlite3
import argparse
from datetime import datetime
from src.warrant_linker import WarrantLinker
from src.market_db import MarketDatabase

TWSE_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&response=json&type={wtype}"

import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

def clean_num(val, is_float=False):
    if val is None:
        return 0.0 if is_float else 0
    s = str(val).replace(",", "").replace(" ", "").strip()
    if not s or s in ("--", "N/A"):
        return 0.0 if is_float else 0
    try:
        return float(s) if is_float else int(float(s))
    except ValueError:
        return 0.0 if is_float else 0

def fetch_twse_warrants_day(date_iso: str, linker: WarrantLinker, ssl_ctx: ssl.SSLContext, name_cache: dict, active_only: bool = False, max_retries: int = 3):
    """
    抓取特定日期的 TWSE 上市權證行情 (涵蓋 0999 認購權證 與 0999P 認售權證) 並關聯個股。支援 gzip 壓縮與失敗重試。
    """
    d_clean = date_iso.replace("-", "")
    warrant_types = ["0999", "0999P"]
    all_raw_rows = []

    for wtype in warrant_types:
        url = TWSE_INDEX_URL.format(date_str=d_clean, wtype=wtype)
        req = urllib.request.Request(url, headers=HEADERS)

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
                    raw = resp.read()
                    if resp.info().get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    data = json.loads(raw.decode("utf-8", errors="ignore"))
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"\n  [連線異常] {date_iso} ({wtype}) 最終請求失敗: {e}")
                    data = None
                time.sleep(2.0 * (attempt + 1))

        if data and data.get("stat") == "OK":
            for t in data.get("tables", []):
                t_data = t.get("data", [])
                if len(t_data) > 0:
                    all_raw_rows.extend(t_data)
                    break

    if not all_raw_rows:
        return date_iso, []

    rows = all_raw_rows
    result = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for r in rows:
        wid = str(r[1]).strip()
        wname = str(r[2]).strip()
        vol_shares = clean_num(r[3])
        amt = clean_num(r[5], is_float=True)

        if active_only and vol_shares == 0 and amt == 0:
            continue

        if wname not in name_cache:
            name_cache[wname] = linker.link(wname)
        sid, sname = name_cache[wname]

        result.append({
            "date": date_iso,
            "warrant_id": wid,
            "warrant_name": wname,
            "trade_amount": amt,
            "trade_volume": vol_shares,
            "trade_lots": vol_shares // 1000,
            "underlying_stock_id": sid,
            "underlying_stock_name": sname,
            "created_at": now_str
        })

    return date_iso, result

def sync_twse_warrants_history(start_date: str = "2020-01-01", active_only: bool = False, workers: int = 2, delay: float = 1.0):
    start_time = time.time()
    db = MarketDatabase(market="TWSE")
    linker = WarrantLinker()
    ssl_ctx = ssl._create_unverified_context()
    name_cache = {}

    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT date FROM daily_quotes 
            WHERE volume_shares > 0 AND date >= ?
            ORDER BY date DESC 
        """, (start_date,))
        target_dates = [r[0] for r in c.fetchall()]

        # 找出已存在 daily_warrants 的日期
        c.execute("SELECT DISTINCT date FROM daily_warrants;")
        existing_dates = {r[0] for r in c.fetchall()}

    missing_dates = [d for d in target_dates if d not in existing_dates]
    missing_dates.sort(reverse=True)

    print("=" * 80)
    print(f"啟動 TWSE 上市權證歷史回溯同步 (目標起始日: {start_date})")
    print("=" * 80)
    print(f"  * 行情交易日總數: {len(target_dates)} 天")
    print(f"  * 權證已同步天數: {len(existing_dates)} 天")
    print(f"  * 待補齊權證天數: {len(missing_dates)} 天")
    print(f"  * 並行線程數: {workers} | 儲存模式: {'僅有成交量>0' if active_only else '全量權證'}")
    print("-" * 80)

    if not missing_dates:
        print(">> 所有歷史交易日之上市權證皆已同步完成！無需重複抓取。")
        return

    # 批次並行抓取並即時落庫 (斷點續傳)
    total_missing = len(missing_dates)
    completed_cnt = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # 依序提交任務
        futures = {
            executor.submit(fetch_twse_warrants_day, d, linker, ssl_ctx, name_cache, active_only): d 
            for d in missing_dates
        }

        for future in as_completed(futures):
            completed_cnt += 1
            d_str, rows = future.result()
            t0 = time.time()

            if rows:
                db.save_daily_warrants(d_str, rows)
                matched = sum(1 for r in rows if r["underlying_stock_id"])
                print(f"[{completed_cnt}/{total_missing}] {d_str} 完成落庫！共 {len(rows):,} 筆 (關聯個股 {matched:,} 筆)", flush=True)
            else:
                print(f"[{completed_cnt}/{total_missing}] {d_str} 無權證交易或休市", flush=True)

            time.sleep(delay)

    duration = round(time.time() - start_time, 2)
    print("=" * 80)
    print(f"【TWSE 上市權證歷史同步完成】 總耗時: {duration} 秒")
    stats = db.get_market_stats()
    print(f"  * 上市權證資料庫現有總筆數: {stats.get('warrants_count', 0):,} 筆")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="TWSE 上市權證歷史資料回溯同步工具")
    parser.add_argument("--start", type=str, default="2020-01-01", help="回溯起始日 (預設 2020-01-01)")
    parser.add_argument("--active-only", action="store_true", help="僅儲存當日有成交(量>0)之權證，可大幅提升速度與節省空間")
    parser.add_argument("--workers", type=int, default=2, help="並行請求線程數 (預設 2，兼顧效能與連線安全)")
    parser.add_argument("--delay", type=float, default=1.0, help="每次寫入間隔秒數 (預設 1.0 秒)")
    args = parser.parse_args()

    sync_twse_warrants_history(start_date=args.start, active_only=args.active_only, workers=args.workers, delay=args.delay)

if __name__ == "__main__":
    main()
