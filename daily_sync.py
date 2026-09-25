import sys
import argparse
import time
from datetime import datetime, timedelta
from src.market_db import MarketDatabase
from src.official_history_fetcher import OfficialHistoryFetcher
from src.warrant_fetcher import WarrantFetcher
from src.sync_utils import get_sync_cutoff_info, print_cutoff_banner

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_missing_dates(db_twse: MarketDatabase, db_tpex: MarketDatabase) -> list:
    """
    自動偵測資料庫現有最新交易日，並計算從該日到官方最新可用交易日之間所有待補齊的平日工作日。
    自動排除週末（週六、週日）並進行發布時間防呆。
    """
    latest_twse = db_twse.get_latest_date()
    latest_tpex = db_tpex.get_latest_date()

    candidates = [d for d in [latest_twse, latest_tpex] if d]
    cutoff_info = get_sync_cutoff_info("market")
    target_end_str = cutoff_info["target_end_date"]
    target_end = datetime.strptime(target_end_str, "%Y-%m-%d").date()

    if not candidates:
        return [target_end_str] if target_end.weekday() < 5 else []

    baseline_str = min(candidates)
    baseline_dt = datetime.strptime(baseline_str, "%Y-%m-%d").date()

    needed_dates = []
    curr = baseline_dt
    while curr <= target_end:
        c_str = curr.strftime("%Y-%m-%d")
        if curr.weekday() < 5:
            needed_dates.append(c_str)
        curr += timedelta(days=1)

    return sorted(list(set(needed_dates)))

def sync_single_date(date_str: str, fetcher: OfficialHistoryFetcher, db_twse: MarketDatabase, db_tpex: MarketDatabase) -> dict:
    """
    同步單一交易日之上市與上櫃資料（行情、三大法人），採原子性事務「先刪後存」以防重複。
    """
    # 1. 處理上市 (TWSE) 行情與三大法人
    twse_q, twse_i = fetcher.fetch_twse_daily_data(date_str)
    if twse_q or twse_i:
        db_twse.save_daily_data(date_str, twse_q, twse_i)

    # 2. 處理上櫃 (TPEx) 行情與三大法人
    tpex_q, tpex_i = fetcher.fetch_tpex_daily_data(date_str)
    if tpex_q or tpex_i:
        db_tpex.save_daily_data(date_str, tpex_q, tpex_i)

    return {
        "date": date_str,
        "twse_quotes": len(twse_q),
        "twse_inst": len(twse_i),
        "tpex_quotes": len(tpex_q),
        "tpex_inst": len(tpex_i)
    }

def sync_warrants_data(w_fetcher: WarrantFetcher, db_twse: MarketDatabase, db_tpex: MarketDatabase, target_dates: list = None) -> dict:
    """
    同步最新權證公開資料並自動補齊所有缺漏交易日。
    1. TWSE: 對接官方盤後 MI_INDEX (type=0999) 及 OpenAPI，自動比對 daily_quotes 與 daily_warrants 進行斷差補齊。
    2. TPEx: 對接 OpenAPI (mopsfin_t187ap42_O) 並自動從已入庫之 daily_quotes 補齊缺漏之歷史權證。
    """
    print("\n>> 正在同步上市櫃權證資料 (官方盤後即時端點 + 歷史缺漏自動補齊)...")
    
    # 找出 TWSE 與 TPEx 各自 daily_quotes 中有成交量但 daily_warrants 缺漏的交易日
    with db_twse.get_connection() as conn_twse:
        c_twse = conn_twse.cursor()
        c_twse.execute("SELECT DISTINCT date FROM daily_quotes WHERE volume_shares > 0 ORDER BY date DESC LIMIT 30;")
        twse_q_dates = [r[0] for r in c_twse.fetchall()]
        c_twse.execute("SELECT DISTINCT date FROM daily_warrants ORDER BY date DESC LIMIT 30;")
        twse_w_dates = set(r[0] for r in c_twse.fetchall())

    with db_tpex.get_connection() as conn_tpex:
        c_tpex = conn_tpex.cursor()
        c_tpex.execute("SELECT DISTINCT date FROM daily_quotes WHERE volume_shares > 0 ORDER BY date DESC LIMIT 30;")
        tpex_q_dates = [r[0] for r in c_tpex.fetchall()]
        c_tpex.execute("SELECT DISTINCT date FROM daily_warrants ORDER BY date DESC LIMIT 30;")
        tpex_w_dates = set(r[0] for r in c_tpex.fetchall())

    missing_twse = [d for d in twse_q_dates if d not in twse_w_dates]
    missing_tpex = [d for d in tpex_q_dates if d not in tpex_w_dates]

    if target_dates:
        for td in target_dates:
            if td not in missing_twse and td not in twse_w_dates:
                missing_twse.append(td)
            if td not in missing_tpex and td not in tpex_w_dates:
                missing_tpex.append(td)

    # 確保今日盤後若缺漏亦納入檢查清單
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    if now.weekday() < 5 and (now.hour > 15 or (now.hour == 15 and now.minute >= 0)):
        if today_str not in twse_w_dates and today_str not in missing_twse:
            missing_twse.append(today_str)
        if today_str not in tpex_w_dates and today_str not in missing_tpex:
            missing_tpex.append(today_str)

    missing_twse.sort()
    missing_tpex.sort()

    twse_count = 0
    tpex_count = 0
    latest_twse_date = None
    latest_tpex_date = None

    # 1. 處理 TWSE 上市權證
    if missing_twse:
        print(f"  * 偵測到 TWSE 上市權證待補齊交易日: {missing_twse}")
        for d in missing_twse:
            print(f"    -> 正在擷取 TWSE 上市權證 ({d})...", end=" ", flush=True)
            twse_date, twse_rows, _ = w_fetcher.fetch_twse_warrants(date_str=d)
            if twse_rows:
                db_twse.save_daily_warrants(twse_date, twse_rows)
                matched = sum(1 for r in twse_rows if r.get("underlying_stock_id"))
                print(f"成功入庫！共 {len(twse_rows):,} 筆 (關聯個股 {matched:,} 筆)")
                twse_count += len(twse_rows)
                latest_twse_date = twse_date
            else:
                print("無資料或休市")
    else:
        # 若無缺漏，確認最新交易日
        twse_date, twse_rows, _ = w_fetcher.fetch_twse_warrants()
        if twse_rows and twse_date not in twse_w_dates:
            db_twse.save_daily_warrants(twse_date, twse_rows)
            matched = sum(1 for r in twse_rows if r.get("underlying_stock_id"))
            print(f"  * 上市權證 (TWSE): 最新交易日 {twse_date} 入庫共 {len(twse_rows):,} 筆 (關聯個股 {matched:,} 筆)")
            twse_count = len(twse_rows)
            latest_twse_date = twse_date
        else:
            print(f"  * 上市權證 (TWSE): 資料庫已收錄最新交易日，無需重複抓取")

    # 2. 處理 TPEx 上櫃權證
    # 優先嘗試以 OpenAPI 取得最新日
    tpex_date, tpex_rows, _ = w_fetcher.fetch_tpex_warrants()
    if tpex_rows and tpex_date not in tpex_w_dates:
        db_tpex.save_daily_warrants(tpex_date, tpex_rows)
        matched = sum(1 for r in tpex_rows if r.get("underlying_stock_id"))
        print(f"  * 上櫃權證 (TPEx): 最新交易日 {tpex_date} 入庫共 {len(tpex_rows):,} 筆 (關聯個股 {matched:,} 筆)")
        tpex_count = len(tpex_rows)
        latest_tpex_date = tpex_date
        if tpex_date in missing_tpex:
            missing_tpex.remove(tpex_date)

    # 若 TPEx 仍有歷史缺漏交易日（如 2026-09-17, 2026-09-18），直接從本機 daily_quotes 提取入庫
    if missing_tpex:
        print(f"  * 補齊 TPEx 上櫃歷史權證 (自本地行情表提取): {missing_tpex}")
        with db_tpex.get_connection() as conn_tpex:
            c = conn_tpex.cursor()
            for d in missing_tpex:
                c.execute("""
                    SELECT date, stock_id, stock_name, amount, volume_shares, volume_lots
                    FROM daily_quotes 
                    WHERE date = ? AND length(stock_id) = 6 AND (stock_id LIKE '7%' OR stock_name LIKE '%購%' OR stock_name LIKE '%售%');
                """, (d,))
                q_rows = c.fetchall()
                if q_rows:
                    tpex_db_rows = []
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for r in q_rows:
                        wid = str(r[1]).strip()
                        wname = str(r[2]).strip()
                        amt = float(r[3] or 0.0)
                        vol_shares = int(r[4] or 0)
                        vol_lots = int(r[5] or 0)
                        sid, sname = w_fetcher.linker.link(wname)
                        tpex_db_rows.append({
                            "date": d,
                            "warrant_id": wid,
                            "warrant_name": wname,
                            "trade_amount": amt,
                            "trade_volume": vol_shares,
                            "trade_lots": vol_lots,
                            "underlying_stock_id": sid,
                            "underlying_stock_name": sname,
                            "created_at": now_str
                        })
                    db_tpex.save_daily_warrants(d, tpex_db_rows)
                    print(f"    -> TPEx {d} 補齊完成！共 {len(tpex_db_rows):,} 筆")
                    tpex_count += len(tpex_db_rows)
                    latest_tpex_date = d
    else:
        print(f"  * 上櫃權證 (TPEx): 資料庫已收錄最新狀態")

    return {
        "twse_date": latest_twse_date,
        "twse_count": twse_count,
        "tpex_date": latest_tpex_date,
        "tpex_count": tpex_count
    }

def run_daily_sync(target_date: str = None, skip_warrants: bool = False):
    print_cutoff_banner("market")
    start_time = time.time()
    fetcher = OfficialHistoryFetcher(polite_delay=1.0)
    w_fetcher = WarrantFetcher()
    db_twse = MarketDatabase(market="TWSE")
    db_tpex = MarketDatabase(market="TPEx")

    cutoff_info = get_sync_cutoff_info("market")
    safe_end_str = cutoff_info["target_end_date"]
    today_str = datetime.now().strftime("%Y-%m-%d")
    latest_date = db_twse.get_latest_date() or "無紀錄"

    print("=" * 80)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動台股每日盤後一鍵更新作業 (智慧斷差自動補齊模式)")
    print("=" * 80)
    print(f"  * 資料庫目前最新收錄日: 【{latest_date}】")
    print(f"  * 官方最新可用交易日: 【{safe_end_str}】")

    # 決定待同步日期清單
    if target_date:
        dates_to_sync = [target_date]
        print(f"  * 模式: 手動指定日期更新 【{target_date}】")
    else:
        dates_to_sync = get_missing_dates(db_twse, db_tpex)
        if not dates_to_sync:
            print("\n>> 【提示】行情資料庫已是最新狀態，且中間無任何待補齊之開盤交易日。")
        elif len(dates_to_sync) == 1 and dates_to_sync[0] == today_str:
            print(f"  * 狀態: 每日例行更新，目標交易日 【{today_str}】")
        else:
            print(f"  * 狀態: 偵測到斷差！共有 {len(dates_to_sync)} 個工作日需補齊: {dates_to_sync}")

    print("-" * 80)

    # 1. 逐日同步行情與三大法人並執行先刪後存
    if dates_to_sync:
        for idx, d_str in enumerate(dates_to_sync, 1):
            print(f"[{idx}/{len(dates_to_sync)}] 正在處理交易日 {d_str}...", end=" ", flush=True)
            res = sync_single_date(d_str, fetcher, db_twse, db_tpex)
            
            twse_status = f"TWSE(行情:{res['twse_quotes']}筆, 法人:{res['twse_inst']}筆)" if res['twse_quotes'] > 0 else "TWSE(無交易)"
            tpex_status = f"TPEx(行情:{res['tpex_quotes']}筆, 法人:{res['tpex_inst']}筆)" if res['tpex_quotes'] > 0 else "TPEx(無交易)"
            print(f"完成 -> {twse_status} | {tpex_status}")

    # 2. 同步最新權證資料 (對接官方盤後與斷差自動補齊)
    if not skip_warrants:
        sync_warrants_data(w_fetcher, db_twse, db_tpex, target_dates=dates_to_sync)

    duration = round(time.time() - start_time, 2)
    s_twse = db_twse.get_market_stats()
    s_tpex = db_tpex.get_market_stats()

    print("-" * 80)
    print("【更新作業完成報告】")
    print(f"  * 總耗費時間: {duration} 秒")
    print(f"  * 上市資料庫: 最新收錄至 {s_twse['end_date']} (共 {s_twse['trading_days']} 個交易日，行情 {s_twse['quotes_count']:,} 筆，權證 {s_twse.get('warrants_count', 0):,} 筆)")
    print(f"  * 上櫃資料庫: 最新收錄至 {s_tpex['end_date']} (共 {s_tpex['trading_days']} 個交易日，行情 {s_tpex['quotes_count']:,} 筆，權證 {s_tpex.get('warrants_count', 0):,} 筆)")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="台股每日盤後資料一鍵更新工具 (具備假日與斷差自動補齊)")
    parser.add_argument("--date", type=str, default=None, help="手動指定更新特定日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--skip-warrants", action="store_true", help="跳過權證資料同步")
    args = parser.parse_args()

    run_daily_sync(target_date=args.date, skip_warrants=args.skip_warrants)

if __name__ == "__main__":
    main()
