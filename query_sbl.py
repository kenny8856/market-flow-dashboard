import sys
import argparse
import csv
from datetime import datetime
from typing import List, Dict, Any

from src.sbl_db import SBLDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def format_lots(val: Any) -> str:
    """將股數轉為張數千分位顯示 (股數 // 1000)"""
    if val is None or val == 0:
        return "0"
    lots = int(val) // 1000
    return f"{lots:,}"

def print_stock_table(stock_info: Dict[str, str], rows: List[Dict[str, Any]]):
    sid = stock_info["stock_id"]
    sname = stock_info["stock_name"]
    mkt = stock_info["market_type"]
    
    print("=" * 115)
    print(f"  [個股借券與借券賣出籌碼明細] - {sid} {sname} ({mkt})  |  共 {len(rows)} 個交易日")
    print("=" * 115)
    print(f"{'日期':<11} {'收盤價':>7} | {'借券借入':>9} {'借券還券':>9} {'借券餘額':>11} | {'借券賣出':>9} {'借券賣還':>9} {'借券賣餘額':>11} {'使用率':>8} | {'融券餘額':>8}")
    print("-" * 115)

    for r in rows:
        d = r["date"]
        p = f"{r['close_price']:.2f}" if r["close_price"] is not None else "   -  "
        b_in = format_lots(r["sbl_total_borrow"])
        b_ret = format_lots(r["sbl_total_return"])
        b_bal = format_lots(r["sbl_total_bal"])

        s_sell = format_lots(r["sbl_short_sell"])
        s_ret = format_lots(r["sbl_short_return"])
        s_bal = format_lots(r["sbl_short_bal"])
        rate = f"{r['sbl_short_utilization_rate']:.1f}%" if r["sbl_short_utilization_rate"] else "  0.0%"

        m_bal = format_lots(r["margin_bal"])

        print(f"{d:<11} {p:>7} | {b_in:>9} {b_ret:>9} {b_bal:>11} | {s_sell:>9} {s_ret:>9} {s_bal:>11} {rate:>8} | {m_bal:>8}")

    print("=" * 115)
    print("說明: 1. 數量單位除收盤價與使用率外，其餘皆已換算為『張』(1,000股)。")
    print("      2. 借券賣出使用率 = (借券賣出餘額 ÷ 借券總餘額) × 100%，代表借入股票中已在市場放空之比例。\n")

def print_top_table(title: str, date_str: str, rows: List[Dict[str, Any]]):
    print("=" * 110)
    print(f"  [{title}] 日期: {date_str}  (共 {len(rows)} 檔)")
    print("=" * 110)
    print(f"{'排名':<4} {'代號':<6} {'名稱':<8} {'市場':<4} {'收盤':>7} | {'借券總餘額(張)':>14} | {'當日借賣(張)':>12} {'借券賣餘額(張)':>14} {'使用率':>8} | {'融券餘額(張)':>10}")
    print("-" * 110)

    for idx, r in enumerate(rows, 1):
        sid = r["stock_id"]
        sname = r["stock_name"]
        mkt = r["market_type"]
        p = f"{r['close_price']:.2f}" if r["close_price"] is not None else "   -  "
        b_bal = format_lots(r["sbl_total_bal"])
        s_sell = format_lots(r["sbl_short_sell"])
        s_bal = format_lots(r["sbl_short_bal"])
        rate = f"{r['sbl_short_utilization_rate']:.1f}%" if r["sbl_short_utilization_rate"] else "  0.0%"
        m_bal = format_lots(r["margin_bal"])

        print(f"{idx:<4} {sid:<6} {sname:<8} {mkt:<4} {p:>7} | {b_bal:>14} | {s_sell:>12} {s_bal:>14} {rate:>8} | {m_bal:>10}")

    print("=" * 110)
    print("說明: 借券數量單位為『張』。\n")

def export_to_csv(filename: str, rows: List[Dict[str, Any]]):
    if not rows:
        print("[提示] 無資料可匯出")
        return
    fieldnames = list(rows[0].keys())
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[成功] 已將 {len(rows)} 筆明細匯出至 CSV: {filename}")

def main():
    parser = argparse.ArgumentParser(description="臺灣全市場個股借券與借券賣出查詢工具")
    parser.add_argument("query", nargs="?", default=None, help="股票代號或名稱 (如 2330, 台積電, 8069, 元太)")
    parser.add_argument("--days", type=int, default=30, help="查詢天數 (預設 30 天)")
    parser.add_argument("--top-short", action="store_true", help="查詢最新一日借券賣出餘額排行 (放空部位最大前幾名)")
    parser.add_argument("--top-borrow", action="store_true", help="查詢最新一日借券總餘額排行")
    parser.add_argument("--top-sell", action="store_true", help="查詢最新一日當日借券賣出新增量排行")
    parser.add_argument("--limit", type=int, default=20, help="排行筆數限制 (預設 20 筆)")
    parser.add_argument("--date", type=str, default=None, help="指定排行查詢日期 (YYYY-MM-DD)")
    parser.add_argument("--export", action="store_true", help="匯出查詢結果至 CSV")
    parser.add_argument("--stats", action="store_true", help="檢視資料庫收錄現況與統計")

    args = parser.parse_args()
    db = SBLDatabase()

    if args.stats:
        s = db.get_market_stats()
        print("=" * 65)
        print("  【臺灣證交所與櫃買中心 個股借券資料庫 (stock_sbl.db) 現況】")
        print("=" * 65)
        print(f"  * 借券餘額記錄數 (TWT72U)   : {s['balance_records']:,} 筆")
        print(f"  * 借券賣出/融券數 (TWT93U)  : {s['short_records']:,} 筆")
        print(f"  * 資料庫總明細筆數          : {s['total_records']:,} 筆")
        print(f"  * 收錄交易日數              : {s['trading_days']} 個開盤日")
        print(f"  * 涵蓋個股數量              : {s['stocks_count']:,} 檔 (上市 + 上櫃)")
        print(f"  * 收錄時間跨度              : {s['min_date']} ~ {s['max_date']}")
        print("=" * 65)
        return

    if args.top_short:
        date_str, rows = db.query_top_sbl_short(date_str=args.date, sort_by="sbl_short_bal", limit=args.limit)
        print_top_table("全市場【借券賣出餘額 (放空存量)】排行榜", date_str, rows)
        if args.export and rows:
            export_to_csv(f"sbl_top_short_{date_str}.csv", rows)
        return

    if args.top_borrow:
        date_str, rows = db.query_top_sbl_balance(date_str=args.date, sort_by="sbl_total_bal", limit=args.limit)
        print_top_table("全市場【借券總餘額】排行榜", date_str, rows)
        if args.export and rows:
            export_to_csv(f"sbl_top_borrow_{date_str}.csv", rows)
        return

    if args.top_sell:
        date_str, rows = db.query_top_sbl_short(date_str=args.date, sort_by="sbl_short_sell", limit=args.limit)
        print_top_table("全市場【當日借券賣出量 (當日放空力道)】排行榜", date_str, rows)
        if args.export and rows:
            export_to_csv(f"sbl_top_sell_{date_str}.csv", rows)
        return

    if not args.query:
        # 預設查詢台積電
        args.query = "2330"

    stock_info, rows = db.query_stock_sbl(args.query, days=args.days)
    if not stock_info or not rows:
        print(f"[提示] 查無股票 '{args.query}' 之借券資料，請確認代號或名稱是否正確。")
        return

    print_stock_table(stock_info, rows)

    if args.export and rows:
        fn = f"sbl_{stock_info['stock_id']}_{stock_info['stock_name']}.csv"
        export_to_csv(fn, rows)

if __name__ == "__main__":
    main()
