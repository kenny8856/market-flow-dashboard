"""
TDCC Equity Distribution Terminal Query Tool (集保戶股權分散表終端查詢工具)
Queries:
1. Individual stock big shareholder % (>1000 shares, >400 shares) vs retail %
2. Weekly trend of big holder concentration
3. Whole-market highest big-holder concentration screener
4. Database statistics
"""

import os
import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.tdcc_db import TdccDB

def show_stats(db: TdccDB):
    latest = db.get_latest_date()
    date_count = db.get_date_count()
    stock_count = db.get_stock_count(latest)

    print("================================================================================")
    print("  【集保戶股權分散表資料庫落地狀態統計】")
    print(f"  * 資料庫路徑: {db.db_path}")
    print(f"  * 累積週次數: {date_count} 週")
    print(f"  * 最新資料週次: {latest}")
    print(f"  * 最新週收錄上市櫃檔數: {stock_count:,} 檔")

    with db._get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tdcc_distribution")
        total_rows = c.fetchone()[0]
    print(f"  * 總級距資料筆數: {total_rows:,} 筆")
    print("================================================================================")

def show_stock_detail(db: TdccDB, stock_id: str, date_str: str = None):
    summary = db.get_stock_summary(stock_id, date_str)
    if not summary:
        print(f"[!] 查無股票代號 {stock_id} 之股權分散資料。請確認代號是否正確。")
        return

    hist = db.get_stock_history(stock_id, limit_weeks=8)

    print("================================================================================")
    print(f"  【個股股權分散與籌碼集中度分析 - {stock_id}】")
    print(f"  * 資料日期: {summary['date']}")
    print(f"  * 總股東人數: {summary['total_shareholders']:,} 人")
    print(f"  * 總集保股數: {summary['total_shares']:,} 股 ({summary['total_shares'] / 1e7:,.2f} 萬張)")
    print("--------------------------------------------------------------------------------")
    print(f"  🏦 千張大戶持股比率 (>1,000張):  {summary['pct_over_1000']:>6.2f} %  (主力與外資大戶底倉)")
    print(f"  💼 400張以上大戶比率 (>400張):    {summary['pct_over_400']:>6.2f} %  (實質主力籌碼)")
    print(f"  👥 散戶持股比率 (<10張):          {summary['pct_retail_under_10']:>6.2f} %  (零股與奈米散戶)")
    print(f"  👥 散戶持股比率 (<50張):          {summary['pct_retail_under_50']:>6.2f} %  (一般散戶水位)")
    print("--------------------------------------------------------------------------------")

    if len(hist) > 1:
        print("  [近期週次股權集中度變動趨勢]:")
        print("  週次日期     千張大戶%    400張大戶%    散戶(<10張)%    總股東人數")
        for h in hist:
            print(f"  {h['date']}    {h['pct_over_1000']:>7.2f}%     {h['pct_over_400']:>8.2f}%       {h['pct_retail_under_10']:>7.2f}%     {h['total_shareholders']:>10,d} 人")
    print("================================================================================")

def show_top_big_holders(db: TdccDB, limit: int = 25):
    latest = db.get_latest_date()
    if not latest:
        print("[!] 資料庫中尚無資料。")
        return

    print("================================================================================")
    print(f"  【全市場千張大戶持股比例最高排行 TOP {limit} (資料週次: {latest})】")
    print("--------------------------------------------------------------------------------")
    print("  排行   代號    千張大戶%   400張大戶%   散戶(<10張)%    總股東人數")
    print("--------------------------------------------------------------------------------")

    with db._get_conn() as conn:
        c = conn.cursor()
        # 級距 15 = 千張大戶，過濾 4 碼普通股且股東人數 >= 500 人以排除少數特殊標的
        c.execute("""
            SELECT stock_id, share_percent, shareholders
            FROM tdcc_distribution
            WHERE date = ? AND holding_level = 15 AND length(stock_id) = 4 AND shareholders >= 500
            ORDER BY share_percent DESC LIMIT ?
        """, (latest, limit))
        rows = c.fetchall()

    for idx, r in enumerate(rows, 1):
        sid = r["stock_id"]
        summary = db.get_stock_summary(sid, latest)
        if summary:
            print(f"  #{idx:2d}   {sid:<6s}   {summary['pct_over_1000']:>6.2f}%     {summary['pct_over_400']:>7.2f}%       {summary['pct_retail_under_10']:>7.2f}%      {summary['total_shareholders']:>9,d} 人")
    print("================================================================================")

def main():
    parser = argparse.ArgumentParser(description="集保戶股權分散表終端查詢工具")
    parser.add_argument("stock", nargs="?", help="股票代號 (如 2330, 2317)")
    parser.add_argument("--top-big", action="store_true", help="全市場千張大戶持股比例前 25 大排行")
    parser.add_argument("--limit", type=int, default=25, help="排行筆數限制")
    parser.add_argument("--date", type=str, help="指定週次日期 (YYYY-MM-DD)")
    parser.add_argument("--stats", "-s", action="store_true", help="檢視資料庫統計狀態")
    args = parser.parse_args()

    db = TdccDB()

    if args.stats:
        show_stats(db)
        return

    if args.top_big:
        show_top_big_holders(db, limit=args.limit)
        return

    if args.stock:
        show_stock_detail(db, args.stock, args.date)
        return

    show_stats(db)
    print("\n[提示] 請輸入股票代號查詢，例如: python query_tdcc.py 2330")
    print("       或查詢千張大戶排行: python query_tdcc.py --top-big")

if __name__ == "__main__":
    main()
