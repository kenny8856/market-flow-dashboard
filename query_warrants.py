import sys
import os
import sqlite3
import json
import csv
import argparse
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TWSE_DB_PATH = "db/twse_market.db"
TPEX_DB_PATH = "db/tpex_market.db"

def search_warrants(
    stock_query: str = None,
    warrant_query: str = None,
    market: str = "ALL",
    date: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    依個股代號/名稱、權證代號/名稱查詢權證資料庫。
    """
    targets = []
    if market.upper() in ("ALL", "TWSE"):
        targets.append(("上市(TWSE)", TWSE_DB_PATH))
    if market.upper() in ("ALL", "TPEX"):
        targets.append(("上櫃(TPEx)", TPEX_DB_PATH))

    results = []

    for m_label, db_path in targets:
        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if date:
            where_clauses.append("date = ?")
            params.append(date)
        else:
            # 預設取最新日期
            cursor.execute("SELECT MAX(date) FROM daily_warrants;")
            row = cursor.fetchone()
            latest_d = row[0] if row else None
            if latest_d:
                where_clauses.append("date = ?")
                params.append(latest_d)

        if stock_query:
            where_clauses.append("(underlying_stock_id = ? OR underlying_stock_name LIKE ?)")
            params.extend([stock_query, f"%{stock_query}%"])

        if warrant_query:
            where_clauses.append("(warrant_id = ? OR warrant_name LIKE ?)")
            params.extend([warrant_query, f"%{warrant_query}%"])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"""
        SELECT 
            date, warrant_id, warrant_name, trade_amount, trade_volume, trade_lots,
            underlying_stock_id, underlying_stock_name
        FROM daily_warrants
        {where_sql}
        ORDER BY trade_amount DESC
        LIMIT ?;
        """
        params.append(limit)

        for row in cursor.execute(sql, params).fetchall():
            d = dict(row)
            d["market"] = m_label
            # 判斷認購或認售
            wname = d["warrant_name"]
            if "購" in wname or "牛" in wname:
                d["type"] = "認購"
            elif "售" in wname or "熊" in wname:
                d["type"] = "認售"
            else:
                d["type"] = "其他"
            results.append(d)

        conn.close()

    # 依成交金額降序排序
    results.sort(key=lambda x: x["trade_amount"], reverse=True)
    return results[:limit]

def display_results(results: List[Dict[str, Any]], query_str: str):
    if not results:
        print(f"\n>> 查無符合條件之權證資料 (查詢條件: {query_str})")
        return

    first_date = results[0]["date"]
    print("\n" + "=" * 110)
    print(f"【權證關聯個股查詢報告】 查詢標的: 【{query_str}】 | 資料日期: 【{first_date}】")
    print("=" * 110)

    # 彙整統計
    total_amount = sum(r["trade_amount"] for r in results)
    total_volume = sum(r["trade_volume"] for r in results)
    total_lots = sum(r["trade_lots"] for r in results)
    call_count = sum(1 for r in results if r["type"] == "認購")
    put_count = sum(1 for r in results if r["type"] == "認售")

    print(f"  * 關聯權證檔數: {len(results)} 檔 (認購: {call_count} 檔 | 認售: {put_count} 檔)")
    print(f"  * 權證總成交金額: {total_amount:,.0f} 元 ({total_amount/10000:,.2f} 萬元)")
    print(f"  * 權證總成交張數: {total_lots:,} 張 (股數: {total_volume:,} 股)")
    print("-" * 110)
    print(f"{'權證代號':<8} {'市場':<8} {'類型':<6} {'標的代號':<8} {'標的名稱':<10} {'成交金額(元)':>16} {'成交張數':>10} {'權證名稱':<24}")
    print("-" * 110)

    for r in results:
        m_short = "TWSE" if "TWSE" in r["market"] else "TPEx"
        amt_str = f"{r['trade_amount']:,.0f}"
        vol_str = f"{r['trade_lots']:,}"
        s_id = r["underlying_stock_id"] or "--"
        s_name = r["underlying_stock_name"] or "--"
        print(f"{r['warrant_id']:<8} {m_short:<8} {r['type']:<6} {s_id:<8} {s_name:<10} {amt_str:>16} {vol_str:>10} {r['warrant_name']:<24}")

    print("=" * 110)

def export_enhanced_json(results: List[Dict[str, Any]], filepath: str):
    """
    導出官方 OpenAPI 原格式並額外擴充【個股代號】與【個股名稱】兩欄之標準 JSON 格式。
    """
    output_data = []
    for r in results:
        rec = {
            "交易日期": r["date"],
            "權證代號": r["warrant_id"],
            "權證名稱": r["warrant_name"],
            "成交金額": str(r["trade_amount"]),
            "成交張數": str(r["trade_lots"]),
            "個股代號": r["underlying_stock_id"] or "",
            "個股名稱": r["underlying_stock_name"] or "",
            "市場": r["market"]
        }
        output_data.append(rec)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f">> [成功導出 JSON] 已寫入 {len(output_data)} 筆資料至: {filepath}")

def export_csv(results: List[Dict[str, Any]], filepath: str):
    """
    導出 CSV 格式。
    """
    keys = ["date", "market", "type", "underlying_stock_id", "underlying_stock_name", "warrant_id", "warrant_name", "trade_amount", "trade_volume", "trade_lots"]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in keys})
    print(f">> [成功導出 CSV] 已寫入 {len(results)} 筆資料至: {filepath}")

def show_db_stats():
    """
    顯示上市與上櫃權證資料庫的落地儲存統計與日期涵蓋範圍。
    """
    print("=" * 80)
    print("【權證資料庫落地儲存狀態報告】")
    print("=" * 80)

    for market_name, db_path in [("上市 (TWSE)", TWSE_DB_PATH), ("上櫃 (TPEx)", TPEX_DB_PATH)]:
        if not os.path.exists(db_path):
            print(f"  * {market_name}: 資料庫檔案不存在 ({db_path})")
            continue

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(*), COUNT(DISTINCT underlying_stock_id)
            FROM daily_warrants;
        """)
        row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM daily_warrants WHERE underlying_stock_id != '' AND underlying_stock_id IS NOT NULL;")
        linked_row = c.fetchone()
        conn.close()

        min_d, max_d, n_days, total_rows, unique_stocks = row
        linked_cnt = linked_row[0] if linked_row else 0
        pct = (linked_cnt / total_rows * 100) if total_rows > 0 else 0

        print(f"  * 【{market_name}】 資料庫路徑: {db_path}")
        print(f"    - 資料表名稱: daily_warrants")
        print(f"    - 日期範圍: {min_d or '無'} ~ {max_d or '無'} (共 {n_days or 0} 個交易日)")
        print(f"    - 總權證紀錄筆數: {total_rows or 0:,} 筆")
        print(f"    - 成功關聯標的個股: {linked_cnt:,} 筆 ({pct:.1f}%)，涵蓋 {unique_stocks:,} 檔不同個股")
        print("-" * 80)
    print("=" * 80)

def display_history_trend(stock_query: str, days: int = 30):
    """
    查詢並分析特定個股在過去 N 天內的權證交易歷史趨勢 (認購 vs 認售、多空比率、每日金額變化)。
    """
    targets = [("上市", TWSE_DB_PATH), ("上櫃", TPEX_DB_PATH)]
    daily_stats = {} # date -> dict
    stock_info = {"id": stock_query, "name": stock_query}
    warrant_totals = {} # wid -> dict

    for _, db_path in targets:
        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 取得最近 N 個有該標的權證交易之日期
        sql = """
        SELECT date, warrant_id, warrant_name, trade_amount, trade_volume, trade_lots,
               underlying_stock_id, underlying_stock_name
        FROM daily_warrants
        WHERE underlying_stock_id = ? OR underlying_stock_name LIKE ?
        ORDER BY date DESC;
        """
        rows = c.execute(sql, [stock_query, f"%{stock_query}%"]).fetchall()
        for r in rows:
            d_date = r["date"]
            stock_info["id"] = r["underlying_stock_id"]
            stock_info["name"] = r["underlying_stock_name"]

            wname = r["warrant_name"]
            is_call = ("購" in wname or "牛" in wname)
            is_put = ("售" in wname or "熊" in wname)

            if d_date not in daily_stats:
                daily_stats[d_date] = {
                    "date": d_date,
                    "call_amount": 0.0,
                    "put_amount": 0.0,
                    "call_lots": 0,
                    "put_lots": 0,
                    "warrants_count": 0
                }

            daily_stats[d_date]["warrants_count"] += 1
            amt = float(r["trade_amount"] or 0)
            lots = int(r["trade_lots"] or 0)

            if is_call:
                daily_stats[d_date]["call_amount"] += amt
                daily_stats[d_date]["call_lots"] += lots
            elif is_put:
                daily_stats[d_date]["put_amount"] += amt
                daily_stats[d_date]["put_lots"] += lots

            # 權證彙整
            wid = r["warrant_id"]
            if wid not in warrant_totals:
                warrant_totals[wid] = {
                    "warrant_id": wid,
                    "warrant_name": wname,
                    "type": "認購" if is_call else ("認售" if is_put else "其他"),
                    "total_amount": 0.0,
                    "total_lots": 0
                }
            warrant_totals[wid]["total_amount"] += amt
            warrant_totals[wid]["total_lots"] += lots

        conn.close()

    if not daily_stats:
        print(f"\n>> 查無個股 【{stock_query}】 過去歷史權證紀錄。")
        return

    # 排序日期並取最近 N 天
    sorted_dates = sorted(list(daily_stats.keys()), reverse=True)[:days]
    sorted_dates.sort() # 正序顯示

    print("\n" + "=" * 105)
    print(f"【個股歷史權證多空趨勢報告】 標的: 【{stock_info['id']} {stock_info['name']}】 (近 {len(sorted_dates)} 個交易日)")
    print("=" * 105)
    print(f"{'交易日期':<12} {'認購金額(萬元)':>16} {'認售金額(萬元)':>16} {'合計金額(萬元)':>16} {'認購/認售比':>14} {'活躍檔數':>10}")
    print("-" * 105)

    sum_call = 0.0
    sum_put = 0.0

    for d in sorted_dates:
        st = daily_stats[d]
        c_amt_w = st["call_amount"] / 10000
        p_amt_w = st["put_amount"] / 10000
        t_amt_w = (st["call_amount"] + st["put_amount"]) / 10000
        ratio_str = f"{(st['call_amount'] / st['put_amount']):.2f}x" if st["put_amount"] > 0 else ("純認購" if st["call_amount"] > 0 else "--")
        
        sum_call += st["call_amount"]
        sum_put += st["put_amount"]

        print(f"{d:<12} {c_amt_w:>16,.2f} {p_amt_w:>16,.2f} {t_amt_w:>16,.2f} {ratio_str:>14} {st['warrants_count']:>10}")

    print("-" * 105)
    total_period = sum_call + sum_put
    overall_ratio = f"{(sum_call / sum_put):.2f}x" if sum_put > 0 else "純認購"
    print(f"【期間累計統計】 期間權證總成交金額: {total_period/10000:,.2f} 萬元 ({total_period:,.0f} 元)")
    print(f"  * 累計認購成交金額: {sum_call/10000:,.2f} 萬元 ({(sum_call/total_period*100) if total_period>0 else 0:.1f}%)")
    print(f"  * 累計認售成交金額: {sum_put/10000:,.2f} 萬元 ({(sum_put/total_period*100) if total_period>0 else 0:.1f}%)")
    print(f"  * 總多空金額比 (認購/認售): {overall_ratio}")
    print("=" * 105)

    # 顯示期間最活躍前 5 檔權證
    top_warrants = sorted(warrant_totals.values(), key=lambda x: x["total_amount"], reverse=True)[:5]
    if top_warrants:
        print("\n>> 期間累計成交金額最高之主要權證 Top 5:")
        for idx, tw in enumerate(top_warrants, 1):
            print(f"   {idx}. {tw['warrant_id']} {tw['warrant_name']:<20} ({tw['type']}) -> 累計成交: {tw['total_amount']/10000:,.2f} 萬元, {tw['total_lots']:,} 張")
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="台股權證資料庫查詢與個股關聯工具")
    parser.add_argument("query", nargs="?", default=None, help="查詢之個股代號/名稱 或 權證代號/名稱 (例如: 2330, 台積電, 前鼎, 4908)")
    parser.add_argument("--stock", "-s", type=str, default=None, help="依標的個股代號或名稱查詢")
    parser.add_argument("--warrant", "-w", type=str, default=None, help="依權證代號或名稱查詢")
    parser.add_argument("--market", "-m", choices=["ALL", "TWSE", "TPEX"], default="ALL", help="市場篩選 (預設 ALL)")
    parser.add_argument("--date", "-d", type=str, default=None, help="指定查詢日期 (YYYY-MM-DD，預設最新收錄日)")
    parser.add_argument("--days", type=int, default=None, help="查詢歷史天數趨勢 (例如: --days 30, --days 180, --days 360)")
    parser.add_argument("--stats", action="store_true", help="檢視上市與上櫃權證資料庫之儲存總筆數與日期範圍")
    parser.add_argument("--limit", "-l", type=int, default=50, help="最多回傳筆數 (預設 50)")
    parser.add_argument("--export-json", type=str, default=None, help="導出為附加【個股代號】與【個股名稱】之 JSON 檔案路徑")
    parser.add_argument("--export-csv", type=str, default=None, help="導出為 CSV 檔案路徑")

    args = parser.parse_args()

    if args.stats:
        show_db_stats()
        return

    stock_q = args.stock
    warrant_q = args.warrant

    if args.query:
        if len(args.query) == 6 and args.query.isdigit():
            warrant_q = args.query
        else:
            stock_q = args.query

    # 如果有指定 --days，執行歷史趨勢多日分析
    if args.days and stock_q:
        display_history_trend(stock_q, days=args.days)
        return

    if not stock_q and not warrant_q:
        show_db_stats()
        print("\n>> 【快速查詢範例】:")
        print("   python query_warrants.py 2330               # 查詢台積電最新權證明細")
        print("   python query_warrants.py 4908 --days 30     # 查詢上櫃前鼎近 30 天歷史權證多空趨勢")
        print("   python query_warrants.py 4908 --days 360    # 查詢上櫃前鼎近一年歷史權證多空趨勢")
        print("   python query_warrants.py 2330 --export-json tsmc_warrants.json")
        print("   python query_warrants.py --stats            # 檢視資料庫完整統計")
        return

    display_label = stock_q or warrant_q or "全市場熱門權證 (依成交金額排序)"
    results = search_warrants(
        stock_query=stock_q,
        warrant_query=warrant_q,
        market=args.market,
        date=args.date,
        limit=args.limit
    )

    display_results(results, display_label)

    if not args.date and not args.days and stock_q:
        print(f"💡 [提示] 本表為最新單日明細。欲分析歷史多日趨勢，請加上參數: python query_warrants.py {stock_q} --days 30 (或 --days 360)")

    if args.export_json:
        export_enhanced_json(results, args.export_json)

    if args.export_csv:
        export_csv(results, args.export_csv)

if __name__ == "__main__":
    main()
