import sys
import argparse
import csv
import sqlite3
from typing import List, Dict, Any, Optional
from src.market_db import TWSE_DB_PATH, TPEX_DB_PATH

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_stock_daily_data(stock_id: str, days: int = 360, market: str = "auto") -> List[Dict[str, Any]]:
    """
    Python 調用 API 介面：獲取特定個股在資料庫中過去 N 天之完整收盤行情與三大法人買賣超
    回傳列表，每筆包含開高低收量與三大法人各別買賣張數。
    """
    # 自動偵測所屬資料庫 (TWSE 上市 或 TPEx 上櫃)
    db_paths = []
    if market.upper() == "TWSE":
        db_paths = [TWSE_DB_PATH]
    elif market.upper() == "TPEX":
        db_paths = [TPEX_DB_PATH]
    else:
        db_paths = [TWSE_DB_PATH, TPEX_DB_PATH]

    results = []
    for p in db_paths:
        if not p.exists():
            continue
        with sqlite3.connect(str(p)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                q.date, q.stock_id, q.stock_name,
                q.open_price, q.high_price, q.low_price, q.close_price, q.change_price,
                q.volume_shares, q.volume_lots, q.amount, q.transaction_count,
                COALESCE(i.foreign_net_lots, 0) AS foreign_net_lots,
                COALESCE(i.trust_net_lots, 0) AS trust_net_lots,
                COALESCE(i.dealer_net / 1000, 0) AS dealer_net_lots,
                COALESCE(i.total_net_lots, 0) AS total_net_lots,
                COALESCE(i.foreign_buy / 1000, 0) AS foreign_buy_lots,
                COALESCE(i.foreign_sell / 1000, 0) AS foreign_sell_lots,
                COALESCE(i.trust_buy / 1000, 0) AS trust_buy_lots,
                COALESCE(i.trust_sell / 1000, 0) AS trust_sell_lots
            FROM daily_quotes q
            LEFT JOIN daily_institutional i ON q.date = i.date AND q.stock_id = i.stock_id
            WHERE q.stock_id = ?
            ORDER BY q.date DESC
            LIMIT ?;
            """, (stock_id, days))
            rows = [dict(r) for r in cursor.fetchall()]
            if rows:
                results = rows
                break

    return sorted(results, key=lambda x: x["date"])

def display_stock_history(stock_id: str, days: int = 30, export_csv: bool = False):
    rows = get_stock_daily_data(stock_id, days=days)

    if not rows:
        print(f"\n[!] 在本地資料庫中查無 {stock_id} 的行情資料。")
        print("    提示：請確認是否已執行 `python sync_360_days.py` 或 `python daily_sync.py` 進行歷史同步。")
        return

    first = rows[0]
    last = rows[-1]
    stock_name = last["stock_name"]

    print("=" * 105)
    print(f"【個股歷史行情與三大法人明細】 {stock_id} {stock_name} (共收錄 {len(rows)} 個交易日: {first['date']} ~ {last['date']})")
    print("=" * 105)

    header = f"{'交易日期':<10} | {'開盤':>7} | {'最高':>7} | {'最低':>7} | {'收盤':>7} | {'漲跌':>6} | {'成交量(張)':>10} | {'外資(張)':>9} | {'投信(張)':>9} | {'自營商(張)':>9} | {'三大法人合計'}"
    print(header)
    print("-" * 105)

    tot_foreign = 0
    tot_trust = 0
    tot_dealer = 0
    tot_net = 0
    all_closes = []

    for r in rows:
        if r['close_price'] is not None:
            all_closes.append(r['close_price'])
        tot_foreign += r['foreign_net_lots']
        tot_trust += r['trust_net_lots']
        tot_dealer += r['dealer_net_lots']
        tot_net += r['total_net_lots']

        chg_str = f"{r['change_price']:+.2f}" if r['change_price'] is not None else "--"
        print(f"{r['date']:<10} | {r['open_price']:>7.2f} | {r['high_price']:>7.2f} | {r['low_price']:>7.2f} | {r['close_price']:>7.2f} | {chg_str:>6} | {r['volume_lots']:>10,d} | {r['foreign_net_lots']:>9,d} | {r['trust_net_lots']:>9,d} | {r['dealer_net_lots']:>9,d} | {r['total_net_lots']:>10,d}張")

    print("-" * 105)
    print(f"【期間累計統計】 期間收盤最高: {max(all_closes) if all_closes else '--'} | 最低: {min(all_closes) if all_closes else '--'} | 最新收盤: {last['close_price']}")
    print(f"三大法人累計: 外資={tot_foreign:+,d} 張 | 投信={tot_trust:+,d} 張 | 自營商={tot_dealer:+,d} 張 | 三大法人總計={tot_net:+,d} 張")
    print("=" * 105)

    if export_csv and rows:
        filename = f"history_{stock_id}_{stock_name}_{len(rows)}days.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "日期", "股票代號", "股票名稱", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差",
                "成交股數", "成交張數", "成交金額", "成交筆數",
                "外資買賣超(張)", "投信買賣超(張)", "自營商買賣超(張)", "三大法人合計(張)",
                "外資買進(張)", "外資賣出(張)", "投信買進(張)", "投信賣出(張)"
            ])
            for r in rows:
                writer.writerow([
                    r["date"], r["stock_id"], r["stock_name"],
                    r["open_price"], r["high_price"], r["low_price"], r["close_price"], r["change_price"],
                    r["volume_shares"], r["volume_lots"], r["amount"], r["transaction_count"],
                    r["foreign_net_lots"], r["trust_net_lots"], r["dealer_net_lots"], r["total_net_lots"],
                    r["foreign_buy_lots"], r["foreign_sell_lots"], r["trust_buy_lots"], r["trust_sell_lots"]
                ])
        print(f"[匯出成功] 已輸出至 CSV: {filename}")

def main():
    parser = argparse.ArgumentParser(description="台股個股歷史行情與三大法人明細查詢工具")
    parser.add_argument("stock_id", type=str, help="股票代號 (如 2330, 2317, 2454)")
    parser.add_argument("--days", type=int, default=30, help="回溯交易日天數 (預設 30 天，可設 180 或 360)")
    parser.add_argument("--export", action="store_true", help="是否匯出為 CSV 報表")

    args = parser.parse_args()
    display_stock_history(args.stock_id, days=args.days, export_csv=args.export)

if __name__ == "__main__":
    main()
