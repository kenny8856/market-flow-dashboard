"""
Cross-Market Event-Driven Analysis Engine for US Top 10 Giants vs Taiwan Supply Chain
File: scripts/us_macro_event_driver.py
"""

import os
import sys
import sqlite3
import argparse
import datetime
import pandas as pd

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'us_tw_supply_chain.db')

def get_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    return sqlite3.connect(DB_PATH)

def fetch_latest_us_performance():
    """
    嘗試抓取美股十大巨頭最近一天的股價變動 (Yahoo Finance API via yfinance or requests)
    """
    tickers = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'AMD', 'QCOM']
    data = []
    try:
        import yfinance as yf
        print("連線 Yahoo Finance 抓取美股十大巨頭最新收盤數據中...")
        df = yf.download(tickers, period='5d', interval='1d', progress=False)
        closes = df['Close']
        for t in tickers:
            if t in closes.columns:
                s = closes[t].dropna()
                if len(s) >= 2:
                    p_now = float(s.iloc[-1])
                    p_prev = float(s.iloc[-2])
                    chg_pct = round((p_now - p_prev) / p_prev * 100, 2)
                    data.append({
                        'us_ticker': t,
                        'price': round(p_now, 2),
                        'change_pct': chg_pct,
                        'date': str(s.index[-1].date())
                    })
    except Exception as e:
        print(f"yfinance 抓取略過或離線模式 ({e})，使用模擬/常規預設值。")
        # 預設範例數值
        default_changes = {
            'NVDA': 4.5, 'AAPL': -1.2, 'MSFT': 1.8, 'GOOGL': 0.9, 'AMZN': 2.3,
            'META': -0.8, 'TSLA': 5.2, 'AVGO': 3.1, 'AMD': 3.8, 'QCOM': 1.1
        }
        for t in tickers:
            data.append({
                'us_ticker': t,
                'price': 100.0,
                'change_pct': default_changes.get(t, 1.0),
                'date': '最新收盤'
            })
    return pd.DataFrame(data)

def simulate_event_impact(us_ticker: str, us_change_pct: float):
    """
    計算單一美股巨頭劇烈變動 (如財報公佈大漲/大跌) 對台灣供應鏈的推演與理論開盤衝擊
    """
    conn = get_db()
    us_ticker = us_ticker.upper()
    g_info = pd.read_sql("SELECT * FROM us_giants WHERE us_ticker = ?", conn, params=(us_ticker,))
    if g_info.empty:
        print(f"查無巨頭代號: {us_ticker}")
        return

    g = g_info.iloc[0]
    direction = "🔥 大漲" if us_change_pct > 0 else "❄️ 大跌"

    print("=" * 86)
    print(f"🚨【跨市場事件驅動推算報告】美股巨頭 {g['name_zh']} ({us_ticker}) 昨夜/盤後波動 {us_change_pct:+.2f}% ({direction})")
    print(f"🏛️ 核心領域: {g['core_segment']} | 重點產品: {g['key_products']}")
    print("=" * 86)

    query = """
    SELECT 
        r.tw_ticker AS ticker,
        r.tw_name AS name,
        c.industry,
        r.supplied_product,
        r.est_revenue_pct_mid AS rev_pct,
        c.est_market_cap_bil_twd AS mcap
    FROM supply_chain_relations r
    JOIN tw_companies c ON r.tw_ticker = c.tw_ticker
    WHERE r.us_ticker = ?
    ORDER BY r.est_revenue_pct_mid DESC
    """
    df = pd.read_sql(query, conn, params=(us_ticker,))
    if df.empty:
        print("無相關台廠資料")
        return

    # 產業敏感彈性係數 (Beta Multiplier)
    def get_beta(ind, prod):
        p_str = (ind + " " + prod).lower()
        if "水冷" in p_str or "散熱" in p_str or "導軌" in p_str:
            return 1.45  # 高彈性零組件
        elif "asic" in p_str or "設計" in p_str:
            return 1.40  # 高估值晶片設計
        elif "機櫃" in p_str or "伺服器" in p_str or "pcb" in p_str:
            return 1.25  # 伺服器組裝與主板
        elif "晶圓代工" in p_str:
            return 1.10  # 龍頭權值
        else:
            return 1.00

    results = []
    taiex_point_est = 0.0

    for _, row in df.iterrows():
        rev_exposure = row['rev_pct'] / 100.0
        beta = get_beta(row['industry'], row['supplied_product'])
        
        # 理論個股衝擊幅度 = 美股變動 * 營收佔比開根號 (兼顧非線性傳導) * 產業彈性 Beta
        # 實務經驗：營收佔比 30% 以上的股票，受美股大漲大跌的衝擊約為美股幅度的 0.4 ~ 0.8 倍
        theoretical_impact = us_change_pct * (rev_exposure ** 0.65) * beta
        
        # 對加權指數點數估計 (台積電每漲1%約80~90點，鴻海每漲1%約10點，廣達每漲1%約5點)
        point_contribution = 0.0
        if row['ticker'] == '2330':
            point_contribution = theoretical_impact * 85.0
        elif row['ticker'] == '2317':
            point_contribution = theoretical_impact * 10.0
        elif row['ticker'] == '2382':
            point_contribution = theoretical_impact * 5.0
        elif row['ticker'] == '2308':
            point_contribution = theoretical_impact * 4.0
        elif row['ticker'] == '2454':
            point_contribution = theoretical_impact * 7.0

        taiex_point_est += point_contribution

        action_signal = "強力跟進聚焦" if theoretical_impact > 3.0 else ("偏多留意" if theoretical_impact > 1.0 else ("中性看待" if theoretical_impact > -1.0 else ("避險停利" if theoretical_impact > -3.0 else "嚴防跳空下殺")))

        results.append({
            '代號': row['ticker'],
            '名稱': row['name'],
            '巨頭營收佔比': f"{row['rev_pct']:.1f}%",
            '核心供應鏈': row['supplied_product'][:24] + ('...' if len(row['supplied_product']) > 24 else ''),
            '理論開盤波動': f"{theoretical_impact:+.2f}%",
            '晨盤戰術定位': action_signal
        })

    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    print("-" * 86)
    print(f"📊【台股加權指數理論開盤跳空推算】")
    print(f"⚡ 由 {g['name_zh']} ({us_ticker}) 牽引之指標權值股預估對大盤點數貢獻: 【 {taiex_point_est:+.1f} 點 】")
    print(f"💡 操盤錦囊: 營收佔比越高的中小型組件股 (如 {results[0]['代號']} {results[0]['名稱']}) 開盤彈性最大，權值龍頭則主導大盤跳空量能。")
    print("=" * 86)
    conn.close()

def run_latest_morning_briefing():
    """
    掃描美股十大巨頭最新收盤，自動產出隔日台股開盤關聯受惠/受害全景晨報
    """
    df_us = fetch_latest_us_performance()
    print("\n" + "=" * 90)
    print("🌅【美股十大巨頭昨夜最新動態 × 台股清晨連動晨報】")
    print("=" * 90)
    
    conn = get_db()
    for _, row in df_us.iterrows():
        t = row['us_ticker']
        c = row['change_pct']
        g_name = conn.execute("SELECT name_zh FROM us_giants WHERE us_ticker = ?", (t,)).fetchone()
        name_zh = g_name[0] if g_name else t
        
        # 抓受惠最高前2名台廠
        top_tw = conn.execute("""
            SELECT r.tw_ticker, r.tw_name, r.est_revenue_pct_mid 
            FROM supply_chain_relations r 
            WHERE r.us_ticker = ? 
            ORDER BY r.est_revenue_pct_mid DESC LIMIT 2
        """, (t,)).fetchall()
        
        tw_str = ", ".join([f"{x[0]} {x[1]} (佔比{x[2]:.0f}%)" for x in top_tw])
        tag = "🟢 強勢領漲" if c >= 2.0 else ("🔴 弱勢承壓" if c <= -2.0 else "⚪ 平穩震盪")
        print(f"[{tag}] {t:<5} {name_zh:<8} 漲跌: {c:>+6.2f}% | 核心牽動台廠: {tw_str}")

    print("=" * 90)
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="US Giants vs TW Supply Chain Event Driver")
    parser.add_argument('--simulate', action='store_true', help='執行單一巨頭事件推算')
    parser.add_argument('--ticker', type=str, default='NVDA', help='美股巨頭代號 (預設 NVDA)')
    parser.add_argument('--change', type=float, default=8.0, help='美股變動幅度百分比 (例: 8.0 或 -6.5)')
    parser.add_argument('--morning', action='store_true', help='美股最新收盤與台股晨會連動全景簡報')

    args = parser.parse_args()

    if args.morning:
        run_latest_morning_briefing()
    elif args.simulate or args.ticker:
        simulate_event_impact(args.ticker, args.change)
    else:
        run_latest_morning_briefing()
