import sys
import argparse
import csv
from datetime import datetime
from typing import List, Dict, Any

from src.margin_db import MarginDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def format_signed_int(val: int) -> str:
    """格式化帶有正負號之整數千分位"""
    if val > 0:
        return f"+{val:,}"
    elif val < 0:
        return f"{val:,}"
    return "0"

def print_stock_table(stock_info: Dict[str, str], rows: List[Dict[str, Any]]):
    sid = stock_info["stock_id"]
    sname = stock_info["stock_name"]
    mkt = stock_info["market_type"]

    print("=" * 125)
    print(f"  [個股融資融券(信用交易)明細] - {sid} {sname} ({mkt})  |  共 {len(rows)} 個交易日")
    print("=" * 125)
    print(f"{'日期':<11} | {'資買':>7} {'資賣':>7} {'現償':>6} {'融資餘額':>9} {'融資增減':>9} {'資使用率':>8} | {'券賣(空)':>8} {'券買(補)':>8} {'券償':>6} {'融券餘額':>9} {'融券增減':>9} | {'券資比':>8} {'資券互抵':>8}")
    print("-" * 125)

    for r in rows:
        d = r["date"]
        mb = f"{r['margin_buy']:,}"
        ms = f"{r['margin_sell']:,}"
        mc = f"{r['margin_cash_redemption']:,}"
        m_bal = f"{r['margin_today_bal']:,}"
        m_chg = format_signed_int(r['margin_change'])
        m_util = f"{r['margin_utilization_rate']:.1f}%"

        ss = f"{r['short_sell']:,}"
        sb = f"{r['short_buy']:,}"
        sc = f"{r['short_cash_redemption']:,}"
        s_bal = f"{r['short_today_bal']:,}"
        s_chg = format_signed_int(r['short_change'])

        ratio = f"{r['short_margin_ratio']:.1f}%"
        offset = f"{r['offset_shares']:,}"

        print(f"{d:<11} | {mb:>7} {ms:>7} {mc:>6} {m_bal:>9} {m_chg:>9} {m_util:>8} | {ss:>8} {sb:>8} {sc:>6} {s_bal:>9} {s_chg:>9} | {ratio:>8} {offset:>8}")

    print("=" * 125)
    print("說明: 1. 數量單位皆為『張』(1,000股)。")
    print("      2. 券資比 = (融券今日餘額 ÷ 融資今日餘額) × 100%，為台股觀察主力軋空強度之重要指標。\n")

def print_top_ratio_table(date_str: str, rows: List[Dict[str, Any]]):
    print("=" * 115)
    print(f"  [全市場【高券資比 (潛在軋空強勢股)】排行榜] 日期: {date_str}  (共 {len(rows)} 檔，門檻: 融資餘額>=500張)")
    print("=" * 115)
    print(f"{'排名':<4} {'代號':<6} {'名稱':<8} {'市場':<4} | {'券資比':>8} | {'融券餘額(張)':>12} {'融券當日增減':>12} | {'融資餘額(張)':>12} {'融資當日增減':>12} | {'資券互抵':>8}")
    print("-" * 115)

    for idx, r in enumerate(rows, 1):
        sid = r["stock_id"]
        sname = r["stock_name"]
        mkt = r["market_type"]
        ratio = f"{r['short_margin_ratio']:.1f}%"
        s_bal = f"{r['short_today_bal']:,}"
        s_chg = format_signed_int(r['short_change'])
        m_bal = f"{r['margin_today_bal']:,}"
        m_chg = format_signed_int(r['margin_change'])
        offset = f"{r['offset_shares']:,}"

        print(f"{idx:<4} {sid:<6} {sname:<8} {mkt:<4} | {ratio:>8} | {s_bal:>12} {s_chg:>12} | {m_bal:>12} {m_chg:>12} | {offset:>8}")

    print("=" * 115)
    print("說明: 單位皆為『張』。\n")

def print_rank_table(title: str, date_str: str, rows: List[Dict[str, Any]], sort_key: str):
    print("=" * 115)
    print(f"  [{title}] 日期: {date_str}  (共 {len(rows)} 檔)")
    print("=" * 115)
    print(f"{'排名':<4} {'代號':<6} {'名稱':<8} {'市場':<4} | {'融資增減(張)':>12} {'融資餘額(張)':>12} | {'融券增減(張)':>12} {'融券餘額(張)':>12} | {'券資比':>8}")
    print("-" * 115)

    for idx, r in enumerate(rows, 1):
        sid = r["stock_id"]
        sname = r["stock_name"]
        mkt = r["market_type"]
        m_chg = format_signed_int(r['margin_change'])
        m_bal = f"{r['margin_today_bal']:,}"
        s_chg = format_signed_int(r['short_change'])
        s_bal = f"{r['short_today_bal']:,}"
        ratio = f"{r['short_margin_ratio']:.1f}%"

        print(f"{idx:<4} {sid:<6} {sname:<8} {mkt:<4} | {m_chg:>12} {m_bal:>12} | {s_chg:>12} {s_bal:>12} | {ratio:>8}")

    print("=" * 115)
    print("說明: 單位皆為『張』。\n")

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
    parser = argparse.ArgumentParser(description="臺灣全市場個股融資融券查詢工具")
    parser.add_argument("query", nargs="?", default=None, help="股票代號或名稱 (如 2330, 台積電, 8069, 元太)")
    parser.add_argument("--days", type=int, default=30, help="查詢天數 (預設 30 天)")
    parser.add_argument("--top-ratio", action="store_true", help="查詢最新一日高券資比排行 (軋空指標)")
    parser.add_argument("--top-margin-buy", action="store_true", help="查詢最新一日融資買超/增額前 20 大")
    parser.add_argument("--top-short-sell", action="store_true", help="查詢最新一日融券放空/增額前 20 大")
    parser.add_argument("--limit", type=int, default=20, help="排行筆數限制 (預設 20 筆)")
    parser.add_argument("--date", type=str, default=None, help="指定排行查詢日期 (YYYY-MM-DD)")
    parser.add_argument("--export", action="store_true", help="匯出查詢結果至 CSV")
    parser.add_argument("--stats", action="store_true", help="檢視資料庫收錄現況與統計")

    args = parser.parse_args()
    db = MarginDatabase()

    if args.stats:
        s = db.get_market_stats()
        print("=" * 65)
        print("  【臺灣證交所與櫃買中心 個股融資融券資料庫 (margin_trading.db) 現況】")
        print("=" * 65)
        print(f"  * 上市股票記錄數 (TWSE)    : {s['twse_records']:,} 筆")
        print(f"  * 上櫃股票記錄數 (TPEx)    : {s['tpex_records']:,} 筆")
        print(f"  * 資料庫總明細筆數         : {s['total_records']:,} 筆")
        print(f"  * 收錄交易日數             : {s['trading_days']} 個開盤日")
        print(f"  * 涵蓋個股數量             : {s['stocks_count']:,} 檔 (上市 + 上櫃)")
        print(f"  * 收錄時間跨度             : {s['min_date']} ~ {s['max_date']}")
        print("=" * 65)
        return

    if args.top_ratio:
        date_str, rows = db.query_top_ratio(date_str=args.date, limit=args.limit)
        print_top_ratio_table(date_str, rows)
        if args.export and rows:
            export_to_csv(f"margin_top_ratio_{date_str}.csv", rows)
        return

    if args.top_margin_buy:
        date_str, rows = db.query_top_margin_buy(date_str=args.date, limit=args.limit)
        print_rank_table("全市場【融資買超 (增額前 20 大)】排行榜", date_str, rows, "margin_change")
        if args.export and rows:
            export_to_csv(f"margin_top_buy_{date_str}.csv", rows)
        return

    if args.top_short_sell:
        date_str, rows = db.query_top_short_sell(date_str=args.date, limit=args.limit)
        print_rank_table("全市場【融券放空 (增額前 20 大)】排行榜", date_str, rows, "short_change")
        if args.export and rows:
            export_to_csv(f"margin_top_short_{date_str}.csv", rows)
        return

    if not args.query:
        args.query = "2330"

    stock_info, rows = db.query_stock_margin(args.query, days=args.days)
    if not stock_info or not rows:
        print(f"[提示] 查無股票 '{args.query}' 之融資融券資料，請確認代號或名稱是否正確。")
        return

    print_stock_table(stock_info, rows)

    if args.export and rows:
        fn = f"margin_{stock_info['stock_id']}_{stock_info['stock_name']}.csv"
        export_to_csv(fn, rows)

if __name__ == "__main__":
    main()
