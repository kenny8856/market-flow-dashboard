"""
Query and Analysis Utility for US Top 10 Giants vs Taiwan Supply Chain
Usage:
    python scripts/query_us_tw_supply_chain.py --giant NVDA
    python scripts/query_us_tw_supply_chain.py --tw 2330
    python scripts/query_us_tw_supply_chain.py --rank
"""

import sys
import os
import sqlite3
import argparse
import pandas as pd

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'us_tw_supply_chain.db')

def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def query_by_giant(ticker: str):
    conn = get_conn()
    ticker = ticker.upper()
    g_info = pd.read_sql("SELECT * FROM us_giants WHERE us_ticker = ?", conn, params=(ticker,))
    if g_info.empty:
        print(f"查無美股代號: {ticker}。支援代號: NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, AVGO, AMD, QCOM")
        return

    g = g_info.iloc[0]
    print("=" * 80)
    print(f"🏛️ 【美股巨頭】{g['name_zh']} ({g['us_ticker']} - {g['name_en']})")
    print(f"💰 市值規模: 約 {g['market_cap_bil_usd']:,.0f} 億美元 | 核心領域: {g['core_segment']}")
    print(f"🔑 核心產品架構: {g['key_products']}")
    print("=" * 80)

    query = """
    SELECT 
        r.tw_ticker AS '台股代號',
        r.tw_name AS '公司名稱',
        r.relation_category AS '供應鏈環節',
        r.supplied_product AS '供應產品 / 專案',
        (r.est_revenue_pct_mid || '%') AS '估計營收佔比',
        ('(' || r.est_revenue_pct_low || '% ~ ' || r.est_revenue_pct_high || '%)') AS '預估區間',
        r.tier_level AS '供應商層級',
        r.official_basis AS '財報/研報認證來源'
    FROM supply_chain_relations r
    WHERE r.us_ticker = ?
    ORDER BY r.est_revenue_pct_mid DESC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    print(df.to_string(index=False))
    print("=" * 80)
    conn.close()

def query_by_tw(ticker: str):
    conn = get_conn()
    c_info = pd.read_sql("SELECT * FROM tw_companies WHERE tw_ticker = ?", conn, params=(ticker,))
    if c_info.empty:
        print(f"查無台股代號: {ticker}")
        return

    c = c_info.iloc[0]
    print("=" * 80)
    print(f"🇹🇼 【台股公司】{c['tw_ticker']} {c['name']} ({c['market']} | {c['industry']})")
    print(f"🏢 估計市值: 約 {c['est_market_cap_bil_twd']:,.0f} 億元新台幣")
    print("=" * 80)

    query = """
    SELECT 
        r.us_ticker AS '美股巨頭',
        r.us_name AS '巨頭名稱',
        r.relation_category AS '供應項目',
        r.supplied_product AS '供應細節產品',
        (r.est_revenue_pct_mid || '%') AS '營收佔比(中位)',
        r.tier_level AS '層級'
    FROM supply_chain_relations r
    WHERE r.tw_ticker = ?
    ORDER BY r.est_revenue_pct_mid DESC
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    if df.empty:
        print("此公司暫未收錄至美股前十大巨頭主要直接供應鏈名單中。")
    else:
        print(df.to_string(index=False))
        total_exp = pd.read_sql("SELECT SUM(est_revenue_pct_mid) as tot FROM supply_chain_relations WHERE tw_ticker = ?", conn, params=(ticker,)).iloc[0]['tot']
        print("-" * 80)
        print(f"🔥 美股十大巨頭合計佔該公司營收比重約達: {total_exp:.1f}%")
    print("=" * 80)
    conn.close()

def query_macro_rank():
    conn = get_conn()
    print("=" * 90)
    print("🌐 【美股十大巨頭對台灣股市供應鏈之影響力綜合排行榜】")
    print("※ 權重指標: 綜合關聯市值 (Sum of 台廠市值 × 該巨頭營收佔比)")
    print("=" * 90)

    query = """
    SELECT 
        m.us_ticker AS '美股代號',
        m.us_name AS '巨頭名稱',
        g.market_cap_bil_usd AS '美股市值(億美元)',
        m.total_partners_count AS '核心台廠夥伴數',
        m.weighted_tw_mcap_influence_bil_twd AS '台股市值牽引權重(億NTD)',
        m.key_sector_focus AS '牽動核心領域與指標股'
    FROM giant_macro_impact m
    JOIN us_giants g ON m.us_ticker = g.us_ticker
    ORDER BY m.weighted_tw_mcap_influence_bil_twd DESC
    """
    df = pd.read_sql(query, conn)
    print(df.to_string(index=False))
    print("=" * 90)
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Query US Top 10 Giants vs TW Supply Chain")
    parser.add_argument('--giant', type=str, help='查詢美股巨頭 (例: NVDA, AAPL, MSFT, AMZN, TSLA)')
    parser.add_argument('--tw', type=str, help='查詢台股代號 (例: 2330, 2317, 3661, 6669)')
    parser.add_argument('--rank', action='store_true', help='美股十大巨頭對台股牽引力排行榜')

    args = parser.parse_args()

    if args.giant:
        query_by_giant(args.giant)
    elif args.tw:
        query_by_tw(args.tw)
    elif args.rank:
        query_macro_rank()
    else:
        query_macro_rank()
