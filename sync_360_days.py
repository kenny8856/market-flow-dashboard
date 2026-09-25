import sys
import argparse
import time
from datetime import datetime
from src.market_db import MarketDatabase
from src.official_history_fetcher import OfficialHistoryFetcher

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def sync_historical_data(start_date: str = "2020-01-01", market: str = "ALL", delay: float = 1.2):
    print("=" * 85)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動台股自 {start_date} 歷史收盤行情與三大法人全量回溯同步")
    print(f"目標市場: {market} | 存取間隔: {delay} 秒 | 模式: 官方直連、斷點續傳、先刪後存")
    print("=" * 85)

    fetcher = OfficialHistoryFetcher(polite_delay=delay)
    candidate_dates = fetcher.get_candidate_trading_dates(start_date=start_date)
    total_dates = len(candidate_dates)
    print(f">> 候選工作日總計: {total_dates} 天 (已自動排除週末例假日)")

    db_twse = MarketDatabase(market="TWSE") if market.upper() in ["TWSE", "ALL"] else None
    db_tpex = MarketDatabase(market="TPEx") if market.upper() in ["TPEX", "ALL"] else None

    synced_twse = db_twse.get_synced_dates() if db_twse else set()
    synced_tpex = db_tpex.get_synced_dates() if db_tpex else set()

    for idx, date_str in enumerate(candidate_dates, 1):
        progress_pct = round(idx / total_dates * 100, 1)
        twse_done = date_str in synced_twse
        tpex_done = date_str in synced_tpex

        if (not db_twse or twse_done) and (not db_tpex or tpex_done):
            # 已同步過，跳過 (斷點續傳)
            print(f"[{idx}/{total_dates}] {date_str} (進度: {progress_pct}%) -> [已於資料庫存在，跳過]")
            continue

        print(f"[{idx}/{total_dates}] {date_str} (進度: {progress_pct}%)...", end=" ", flush=True)

        status_msgs = []

        # 1. 處理上市 (TWSE)
        if db_twse and not twse_done:
            try:
                twse_q, twse_i = fetcher.fetch_twse_daily_data(date_str)
                db_twse.save_daily_data(date_str, twse_q, twse_i)
                status_msgs.append(f"TWSE(行情:{len(twse_q)}, 法人:{len(twse_i)})")
            except Exception as e:
                status_msgs.append(f"TWSE錯誤:{e}")

        # 2. 處理上櫃 (TPEx)
        if db_tpex and not tpex_done:
            try:
                tpex_q, tpex_i = fetcher.fetch_tpex_daily_data(date_str)
                db_tpex.save_daily_data(date_str, tpex_q, tpex_i)
                status_msgs.append(f"TPEx(行情:{len(tpex_q)}, 法人:{len(tpex_i)})")
            except Exception as e:
                status_msgs.append(f"TPEx錯誤:{e}")

        print(" | ".join(status_msgs))

    print("\n" + "=" * 85)
    print("【歷史全量同步完工報告】")
    if db_twse:
        s_twse = db_twse.get_market_stats()
        print(f"  * 上市資料庫 (twse_market.db): 現存總行情 {s_twse['quotes_count']:,} 筆、總法人 {s_twse['institutional_count']:,} 筆 (共 {s_twse['trading_days']} 個交易日)")
    if db_tpex:
        s_tpex = db_tpex.get_market_stats()
        print(f"  * 上櫃資料庫 (tpex_market.db): 現存總行情 {s_tpex['quotes_count']:,} 筆、總法人 {s_tpex['institutional_count']:,} 筆 (共 {s_tpex['trading_days']} 個交易日)")
    print("=" * 85)

def main():
    parser = argparse.ArgumentParser(description="台股歷史行情與三大法人全量回溯同步腳本")
    parser.add_argument("--start", type=str, default="2020-01-01", help="回溯起始日 (預設 2020-01-01)")
    parser.add_argument("--market", type=str, default="ALL", choices=["TWSE", "TPEX", "ALL"], help="目標市場: ALL, TWSE, TPEX (預設 ALL)")
    parser.add_argument("--delay", type=float, default=1.2, help="每次官方請求間隔秒數 (預設 1.2 秒)")

    args = parser.parse_args()
    sync_historical_data(start_date=args.start, market=args.market, delay=args.delay)

if __name__ == "__main__":
    main()
