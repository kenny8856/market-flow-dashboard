"""
Taiwan Stock Market Sector Capital Flow & Rotation Analysis Tool (台股產業類股資金流向與族群輪動分析)
Aggregates:
1. Daily sector turnover amount & % share of total market
2. Institutional net buying/selling amount by sector (外資/投信族群流向)
3. Multi-day sector momentum & capital rotation trends (資金吸水怪獸偵測)
"""

import os
import sys
import sqlite3
import argparse
from typing import Dict, List, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")

INDUSTRY_NAMES = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學生技", "08": "玻璃陶瓷",
    "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業",
    "13": "電子工業", "14": "建材營造", "15": "航運業",   "16": "觀光餐旅",
    "17": "金融保險", "18": "貿易百貨", "19": "綜合",     "20": "其他",
    "21": "化學工業", "22": "生技醫療", "23": "油電燃氣", "24": "半導體業",
    "25": "電腦週邊", "26": "光電業",   "27": "通信網路", "28": "電子零組件",
    "29": "電子通路", "30": "資訊服務", "31": "其他電子", "32": "文化創意",
    "33": "農業科技", "34": "綠能環保"
}

def get_stock_industry_map() -> Dict[str, str]:
    db_path = os.path.join(DB_DIR, "stock_geography.db")
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT stock_id, industry FROM stocks")
    mapping = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    return mapping

def get_sector_flow(date_str: Optional[str] = None) -> Dict[str, Any]:
    stock_ind = get_stock_industry_map()
    twse_db = os.path.join(DB_DIR, "twse_market.db")
    tpex_db = os.path.join(DB_DIR, "tpex_market.db")

    conn_tw = sqlite3.connect(twse_db)
    c_tw = conn_tw.cursor()

    if not date_str:
        c_tw.execute("SELECT MAX(date) FROM daily_quotes")
        r = c_tw.fetchone()
        date_str = r[0] if r else None

    if not date_str:
        conn_tw.close()
        return {}

    # 1. 抓取上市行情與法人
    q_tw = c_tw.execute("""
        SELECT q.stock_id, q.amount, i.foreign_net, i.trust_net, q.close_price
        FROM daily_quotes q
        LEFT JOIN daily_institutional i ON q.date = i.date AND q.stock_id = i.stock_id
        WHERE q.date = ?
    """, (date_str,)).fetchall()
    conn_tw.close()

    # 2. 抓取上櫃行情與法人
    q_tp = []
    if os.path.exists(tpex_db):
        conn_tp = sqlite3.connect(tpex_db)
        c_tp = conn_tp.cursor()
        try:
            q_tp = c_tp.execute("""
                SELECT q.stock_id, q.amount, i.foreign_net, i.trust_net, q.close_price
                FROM daily_quotes q
                LEFT JOIN daily_institutional i ON q.date = i.date AND q.stock_id = i.stock_id
                WHERE q.date = ?
            """, (date_str,)).fetchall()
        except Exception:
            pass
        conn_tp.close()

    all_rows = q_tw + q_tp
    total_market_turnover = sum(r[1] or 0 for r in all_rows)

    sectors: Dict[str, Dict[str, Any]] = {}
    for sid, amt, f_net, t_net, close_p in all_rows:
        raw_ind = stock_ind.get(sid, "20")
        ind_name = INDUSTRY_NAMES.get(raw_ind, f"類股{raw_ind}")

        if ind_name not in sectors:
            sectors[ind_name] = {
                "industry_code": raw_ind,
                "industry_name": ind_name,
                "turnover": 0,
                "foreign_net_amt": 0.0,
                "trust_net_amt": 0.0,
                "stocks_count": 0
            }

        p = close_p or 0.0
        sectors[ind_name]["turnover"] += (amt or 0)
        sectors[ind_name]["foreign_net_amt"] += ((f_net or 0) * p)
        sectors[ind_name]["trust_net_amt"] += ((t_net or 0) * p)
        sectors[ind_name]["stocks_count"] += 1

    sector_list = list(sectors.values())
    sector_list.sort(key=lambda x: x["turnover"], reverse=True)

    for s in sector_list:
        s["pct_share"] = (s["turnover"] / total_market_turnover * 100.0) if total_market_turnover else 0.0

    return {
        "date": date_str,
        "total_turnover": total_market_turnover,
        "sectors": sector_list
    }

def print_sector_flow(date_str: Optional[str] = None, top: int = 15):
    res = get_sector_flow(date_str)
    if not res:
        print("[!] 無法取得類股資金流向資料。")
        return

    d = res["date"]
    tot = res["total_turnover"]
    sectors = res["sectors"][:top]

    print("================================================================================")
    print(f"  【全市場產業類股資金流向與族群輪動分析】")
    print(f"  * 資料日期: {d} | 全市場上市櫃總成交: {tot / 1e8:,.1f} 億元")
    print("--------------------------------------------------------------------------------")
    print("  排行   產業類別     成交金額 (億)   佔大盤比重%   外資估買賣超 (億)   投信估買賣超 (億)")
    print("--------------------------------------------------------------------------------")

    for idx, s in enumerate(sectors, 1):
        name = s["industry_name"]
        t_amt = s["turnover"] / 1e8
        pct = s["pct_share"]
        f_amt = s["foreign_net_amt"] / 1e8
        t_amt_inst = s["trust_net_amt"] / 1e8

        # 資金聚集警告 (熱門族群)
        tag = ""
        if pct >= 35.0:
            tag = " 🔥[重押集中]"
        elif pct >= 15.0:
            tag = " ⚡[熱門板塊]"

        f_str = f"{f_amt:>+8.1f}"
        t_str = f"{t_amt_inst:>+8.1f}"
        print(f"  #{idx:2d}   {name:<10s}   {t_amt:>9.1f}      {pct:>6.2f}%       {f_str}          {t_str}    {tag}")
    print("================================================================================")

def main():
    parser = argparse.ArgumentParser(description="台股產業類股資金流向與族群輪動分析工具")
    parser.add_argument("--date", "-d", type=str, help="指定日期 (YYYY-MM-DD)")
    parser.add_argument("--top", "-t", type=int, default=15, help="顯示排行數量 (預設 15)")
    args = parser.parse_args()

    print_sector_flow(args.date, args.top)

if __name__ == "__main__":
    main()
