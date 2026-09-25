"""
Convertible Bond (CB) Query Tool
Query Taiwan Convertible Bond daily quotes, conversion metrics, and history.

Usage:
    python query_cb.py --date 2026-09-17
    python query_cb.py --date 2026-09-17 --sort volume --limit 20
    python query_cb.py --date 2026-09-17 --undervalued
    python query_cb.py --cb 15602
    python query_cb.py --stock 1560
"""

import os
import sys
import argparse
from datetime import datetime
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src import cb_db


def print_table(rows, headers, col_keys):
    """Utility to print a well-aligned ASCII table."""
    if not rows:
        print("查無符合條件的資料。")
        return

    # Prepare string matrix
    matrix = []
    for r in rows:
        line = []
        for k in col_keys:
            val = r.get(k)
            if val is None:
                line.append("-")
            elif isinstance(val, float):
                if "rate" in k or "percent" in k:
                    line.append(f"{val:+.2f}%")
                else:
                    line.append(f"{val:.2f}")
            elif isinstance(val, int):
                line.append(f"{val:,}")
            else:
                line.append(str(val))
        matrix.append(line)

    # Calculate column widths (handling wide East Asian characters)
    def char_width(s):
        import unicodedata
        w = 0
        for ch in s:
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                w += 2
            else:
                w += 1
        return w

    col_widths = [char_width(h) for h in headers]
    for row in matrix:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], char_width(val))

    def pad_cell(s, width, align="right"):
        cur_w = char_width(s)
        pad = max(0, width - cur_w)
        if align == "left":
            return s + " " * pad
        elif align == "center":
            left_pad = pad // 2
            right_pad = pad - left_pad
            return " " * left_pad + s + " " * right_pad
        else:
            return " " * pad + s

    # Print header
    header_str = " | ".join(pad_cell(h, col_widths[i], "center") for i, h in enumerate(headers))
    sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_str)
    print(sep_str)

    # Print rows
    for row in matrix:
        line_str = " | ".join(
            pad_cell(row[i], col_widths[i], "left" if i in (0, 1, 2, 3) else "right")
            for i in range(len(row))
        )
        print(line_str)


def query_date(date_str: str, sort_by: str = "volume", limit: int = 30, undervalued: bool = False):
    """Query quotes on a specific date."""
    conn = cb_db.get_connection()
    cur = conn.cursor()

    where_clause = "WHERE date = ?"
    if undervalued:
        where_clause += " AND premium_rate IS NOT NULL AND premium_rate <= 10.0"

    sort_clause = "volume_lots DESC, trade_amount DESC"
    if sort_by == "premium" or undervalued:
        sort_clause = "premium_rate ASC"
    elif sort_by == "conv_value":
        sort_clause = "conversion_value DESC"
    elif sort_by == "close":
        sort_clause = "close_price DESC"

    query = f"""
        SELECT * FROM daily_cb_quotes
        {where_clause}
        ORDER BY {sort_clause}
        LIMIT ?
    """
    cur.execute(query, (date_str, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    print(f"\n[可轉債市場行情] 日期: {date_str} (排序: {sort_by}, 筆數: {len(rows)})")
    headers = [
        "CB代號", "CB名稱", "標的", "標的名稱",
        "開盤", "最高", "最低", "收/參", "成交量(張)",
        "轉換價", "股票現價", "轉換價值", "折溢價率",
        "發行張數", "剩餘張數", "上市日", "到期日"
    ]
    # Use close_price if available, else reference_price for display
    for r in rows:
        cp = r.get("close_price")
        rp = r.get("reference_price")
        r["disp_price"] = cp if cp is not None else (f"{rp:.2f}*" if rp else "-")

    col_keys = [
        "cb_id", "cb_name", "underlying_id", "underlying_name",
        "open_price", "high_price", "low_price", "disp_price", "volume_lots",
        "conversion_price", "underlying_close_price", "conversion_value", "premium_rate",
        "issue_lots", "outstanding_lots", "listing_date", "maturity_date"
    ]
    print_table(rows, headers, col_keys)
    print("註: '收/參' 標記 * 者表示當日無撮合成交，以官方轉債參考價列示。")


def query_cb(cb_id: str, limit: int = 30):
    """Query history of a specific CB."""
    rows = cb_db.query_cb_history(cb_id, limit=limit)
    if not rows:
        print(f"查無 CB 代號 {cb_id} 之資料。")
        return

    name = rows[0].get("cb_name", "")
    stock_id = rows[0].get("underlying_id", "")
    stock_name = rows[0].get("underlying_name", "")
    print(f"\n[可轉債歷史明細] {cb_id} {name} (標的: {stock_id} {stock_name})")

    headers = [
        "交易日期", "開盤", "最高", "最低", "收盤", "成交量(張)",
        "成交金額", "轉換價", "標的股價", "轉換價值", "折溢價率", "剩餘張數"
    ]
    col_keys = [
        "date", "open_price", "high_price", "low_price", "close_price", "volume_lots",
        "trade_amount", "conversion_price", "underlying_close_price", "conversion_value",
        "premium_rate", "outstanding_lots"
    ]
    print_table(rows, headers, col_keys)


def query_stock(stock_id: str):
    """Query all CBs associated with a specific underlying stock."""
    rows = cb_db.query_cb_by_stock(stock_id, limit=50)
    if not rows:
        print(f"查無標的股票 {stock_id} 之可轉債資料。")
        return

    stock_name = rows[0].get("underlying_name", "")
    print(f"\n[個股發行之可轉債] 標的: {stock_id} {stock_name}")

    headers = [
        "日期", "CB代號", "CB名稱", "收/參", "成交量(張)",
        "轉換價", "股票現價", "轉換價值", "折溢價率", "發行張數", "剩餘張數", "到期日"
    ]
    for r in rows:
        cp = r.get("close_price")
        rp = r.get("reference_price")
        r["disp_price"] = cp if cp is not None else (f"{rp:.2f}*" if rp else "-")

    col_keys = [
        "date", "cb_id", "cb_name", "disp_price", "volume_lots",
        "conversion_price", "underlying_close_price", "conversion_value",
        "premium_rate", "issue_lots", "outstanding_lots", "maturity_date"
    ]
    print_table(rows, headers, col_keys)


def main():
    parser = argparse.ArgumentParser(description="Query Taiwan Convertible Bond (CB) Market Data")
    parser.add_argument("--date", type=str, default=None, help="Query date (YYYY-MM-DD)")
    parser.add_argument("--cb", type=str, default=None, help="Query specific CB ID (e.g. 15602)")
    parser.add_argument("--stock", type=str, default=None, help="Query CBs of underlying stock ID (e.g. 1560)")
    parser.add_argument("--sort", type=str, default="volume", choices=["volume", "premium", "conv_value", "close"], help="Sort field")
    parser.add_argument("--limit", type=int, default=25, help="Number of rows to display")
    parser.add_argument("--undervalued", action="store_true", help="Filter for low premium / discounted CBs")

    args = parser.parse_args()

    if args.cb:
        query_cb(args.cb, limit=args.limit)
    elif args.stock:
        query_stock(args.stock)
    elif args.date:
        query_date(args.date, sort_by=args.sort, limit=args.limit, undervalued=args.undervalued)
    else:
        # 預設查詢資料庫中最新一日
        conn = cb_db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(date) FROM daily_cb_quotes")
        r = cur.fetchone()
        latest_date = r[0] if r and r[0] else datetime.now().strftime("%Y-%m-%d")
        conn.close()
        query_date(latest_date, sort_by=args.sort, limit=args.limit, undervalued=args.undervalued)


if __name__ == "__main__":
    main()
