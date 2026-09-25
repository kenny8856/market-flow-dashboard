"""
TAIFEX Options Terminal Query Tool (期交所選擇權市場終端查詢工具)
Queries:
1. Put/Call Ratio history & trend
2. Max Pain (最大痛點) & Strike OI Walls (支撐壓力牆)
3. Institutional net options positions
4. Database summary & statistics
"""

import os
import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.taifex_options_db import TaifexOptionsDB

def show_stats(db: TaifexOptionsDB):
    earliest = db.get_earliest_date()
    latest = db.get_latest_date()
    date_count = db.get_date_count()

    print("================================================================================")
    print("  【期交所選擇權資料庫落地狀態統計】")
    print(f"  * 資料庫路徑: {db.db_path}")
    print(f"  * 收錄總開盤日數: {date_count} 天")
    print(f"  * 最早收錄日期: {earliest}")
    print(f"  * 最新收錄日期: {latest}")

    with db._get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM txo_pc_ratio")
        n_pc = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM txo_strike_quotes")
        n_sq = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM txo_institutional")
        n_inst = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM txo_large_trader")
        n_lt = c.fetchone()[0]

    print(f"  * Put/Call Ratio 筆數: {n_pc:,} 筆")
    print(f"  * 各履約價未平倉行情筆數: {n_sq:,} 筆")
    print(f"  * 三大法人契約明細筆數: {n_inst:,} 筆")
    print(f"  * 大額交易人部位筆數: {n_lt:,} 筆")
    print("================================================================================")

def show_pc_ratio(db: TaifexOptionsDB, days: int = 15):
    rows = db.get_pc_ratio_history(days=days)
    if not rows:
        print("[!] 資料庫中查無 Put/Call Ratio 資料。")
        return

    print("================================================================================")
    print(f"  【臺指選擇權 Put/Call Ratio 近 {len(rows)} 個交易日走勢】")
    print("  指標意涵: P/C未平倉比率 > 100% 代表多方防守/偏多；< 100% 代表空方避險/偏空")
    print("--------------------------------------------------------------------------------")
    print("  日期        賣權成交量   買權成交量  成交量P/C比%   賣權未平倉   買權未平倉  未平倉P/C比%  多空傾向")
    print("--------------------------------------------------------------------------------")

    for r in rows:
        pc_oi = r["pc_ratio_oi"]
        if pc_oi >= 120.0:
            bias = "🟢 極度偏多"
        elif pc_oi >= 105.0:
            bias = "🟢 偏多防守"
        elif pc_oi >= 95.0:
            bias = "⚪ 中性格局"
        elif pc_oi >= 80.0:
            bias = "🔴 偏空格局"
        else:
            bias = "🔴 深度避險"

        print(f"  {r['date']}  {r['put_volume']:>10,d}  {r['call_volume']:>10,d}  {r['pc_ratio_volume']:>10.2f}%  {r['put_oi']:>10,d}  {r['call_oi']:>10,d}  {pc_oi:>10.2f}%   {bias}")
    print("================================================================================")

def show_max_pain(db: TaifexOptionsDB, date_str: str = None, expiry_month: str = None):
    if not date_str:
        date_str = db.get_latest_date()
    if not date_str:
        print("[!] 資料庫中尚無選擇權資料。")
        return

    res = db.calculate_max_pain(date_str, expiry_month)
    if not res.get("max_pain_strike"):
        print(f"[!] 無法計算 {date_str} 之 Max Pain: {res.get('error', '查無合約')}")
        return

    exp = res["expiry_month"]
    mp = res["max_pain_strike"]
    c_wall = res["top_call_resistance_strike"]
    c_oi = res["top_call_oi"]
    p_wall = res["top_put_support_strike"]
    p_oi = res["top_put_oi"]

    print("================================================================================")
    print(f"  【臺指選擇權 Max Pain 最大痛點與支撐壓力牆分析】")
    print(f"  * 評估交易日期: {date_str} | 合約代號: {exp}")
    print("--------------------------------------------------------------------------------")
    print(f"  🎯 Max Pain (莊家最大獲利結算點位): {mp:,.0f} 點")
    print(f"  🧱 上檔壓力牆 (Call 最大未平倉履約價): {c_wall:,.0f} 點  (未平倉: {c_oi:,} 口)")
    print(f"  🛡️ 下檔支撐牆 (Put 最大未平倉履約價): {p_wall:,.0f} 點  (未平倉: {p_oi:,} 口)")
    print(f"  📏 莊家預估震盪防守區間: {p_wall:,.0f} 點  ~  {c_wall:,.0f} 點")
    print("--------------------------------------------------------------------------------")
    print("  [核心履約價未平倉量分佈 Top 10 (由低至高)]:")
    print("  履約價      Call 未平倉 (口)    Put 未平倉 (口)    未平倉多空傾向")

    # 找出履約價在 Max Pain 附近 +- 1500 點
    curve = res.get("pain_curve", [])
    around = [p for p in curve if abs(p["strike"] - mp) <= 1200 and (p["call_oi"] > 0 or p["put_oi"] > 0)]
    for p in around:
        s = p["strike"]
        c = p["call_oi"]
        pt = p["put_oi"]
        tag = ""
        if s == mp:
            tag += " [🎯 Max Pain]"
        if s == c_wall:
            tag += " [🧱 Call壓力牆]"
        if s == p_wall:
            tag += " [🛡️ Put支撐牆]"
        print(f"  {s:>7,.0f}       {c:>10,d}          {pt:>10,d}       {tag}")
    print("================================================================================")

def show_institutional(db: TaifexOptionsDB, date_str: str = None):
    if not date_str:
        date_str = db.get_latest_date()
    if not date_str:
        print("[!] 資料庫中尚無法人選擇權資料。")
        return

    rows = db.get_institutional_summary(date_str)
    if not rows:
        print(f"[!] 查無 {date_str} 之三大法人選擇權明細。")
        return

    print("================================================================================")
    print(f"  【臺指選擇權三大法人多空契約金額與未平倉部位 ({date_str})】")
    print("--------------------------------------------------------------------------------")
    print("  買賣權   身分別     買方未平倉 (口)   賣方未平倉 (口)   淨未平倉口數   淨未平倉金額 (千元)")
    print("--------------------------------------------------------------------------------")

    for r in rows:
        cp = r["call_put"]
        itype = r["institution_type"]
        net_l = r["net_oi_lots"]
        net_amt = r["net_oi_amount"]

        cp_str = "買權 CALL" if cp == "CALL" else "賣權 PUT "
        print(f"  {cp_str}  {itype:<8s}   {r['buy_oi_lots']:>10,d}      {r['sell_oi_lots']:>10,d}      {net_l:>10,d}      {net_amt:>14,.0f}")
    print("================================================================================")

def main():
    parser = argparse.ArgumentParser(description="期交所選擇權市場終端查詢工具")
    parser.add_argument("--pc-ratio", "-p", action="store_true", help="檢視臺指選擇權 Put/Call Ratio 歷史走勢")
    parser.add_argument("--max-pain", "-m", action="store_true", help="計算最新一日之 Max Pain 最大痛點與支撐壓力牆")
    parser.add_argument("--institutional", "-i", action="store_true", help="檢視三大法人選擇權最新未平倉契約金額與口數")
    parser.add_argument("--date", type=str, help="指定查詢日期 (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=15, help="查詢天數，預設 15 天")
    parser.add_argument("--stats", "-s", action="store_true", help="顯示選擇權資料庫狀態與筆數統計")
    args = parser.parse_args()

    db = TaifexOptionsDB()

    if args.stats:
        show_stats(db)
        return

    if args.pc_ratio:
        show_pc_ratio(db, days=args.days)
        return

    if args.max_pain:
        show_max_pain(db, date_str=args.date)
        return

    if args.institutional:
        show_institutional(db, date_str=args.date)
        return

    # 若未指定參數，預設全覽
    show_stats(db)
    print()
    show_max_pain(db, date_str=args.date)
    print()
    show_pc_ratio(db, days=args.days)
    print()
    show_institutional(db, date_str=args.date)

if __name__ == "__main__":
    main()
