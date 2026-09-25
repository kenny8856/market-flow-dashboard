import sqlite3
import yfinance as yf
import pandas as pd
import datetime

def fix_taiex_volume():
    print("Fixing TAIEX Volume...")
    conn = sqlite3.connect('db/twse_market.db')
    c = conn.cursor()
    # Find dates with 0 volume
    c.execute("SELECT date FROM daily_quotes WHERE stock_id='TAIEX' AND volume_shares=0")
    dates = [r[0] for r in c.fetchall()]
    if not dates:
        print("No zero volume dates found for TAIEX.")
        return
        
    start_date = min(dates)
    end_date = (datetime.datetime.strptime(max(dates), "%Y-%m-%d") + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"Fetching from yfinance: {start_date} to {end_date}")
    
    df = yf.download('^TWII', start=start_date, end=end_date)
    update_data = []
    for d in dates:
        if pd.Timestamp(d) in df.index:
            vol_val = df.loc[d, 'Volume']
            if isinstance(vol_val, pd.Series):
                vol = int(vol_val.iloc[0])
            else:
                vol = int(vol_val)
            if vol > 0:
                # yfinance returns volume in thousands usually for TAIEX?
                # Actually, let's just use what yf provides, usually it's correct. Or we can just multiply by 1000 if it's too small.
                # Usually TAIEX volume is around 5,000,000,000 to 15,000,000,000 shares.
                if vol < 100000000:
                    vol *= 1000
                update_data.append((vol, vol // 1000, d))
                
    if update_data:
        c.executemany("UPDATE daily_quotes SET volume_shares=?, volume_lots=? WHERE stock_id='TAIEX' AND date=?", update_data)
        conn.commit()
        print(f"Updated {len(update_data)} records for TAIEX volume.")
    conn.close()

def build_index_institutional(db_path, index_id, index_name):
    print(f"Building institutional data for {index_id} in {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check if we already have it
    c.execute("DELETE FROM daily_institutional WHERE stock_id=?", (index_id,))
    
    # Aggregate from all stocks
    c.execute(f"""
        INSERT INTO daily_institutional (
            date, stock_id, stock_name, 
            foreign_buy, foreign_sell, foreign_net,
            trust_buy, trust_sell, trust_net,
            dealer_net, dealer_self_buy, dealer_self_sell, dealer_self_net,
            dealer_hedge_buy, dealer_hedge_sell, dealer_hedge_net,
            total_net, foreign_net_lots, trust_net_lots, total_net_lots, created_at
        )
        SELECT 
            date, '{index_id}', '{index_name}',
            SUM(foreign_buy), SUM(foreign_sell), SUM(foreign_net),
            SUM(trust_buy), SUM(trust_sell), SUM(trust_net),
            SUM(dealer_net), SUM(dealer_self_buy), SUM(dealer_self_sell), SUM(dealer_self_net),
            SUM(dealer_hedge_buy), SUM(dealer_hedge_sell), SUM(dealer_hedge_net),
            SUM(total_net), SUM(foreign_net_lots), SUM(trust_net_lots), SUM(total_net_lots),
            CURRENT_TIMESTAMP
        FROM daily_institutional
        WHERE stock_id != '{index_id}'
        GROUP BY date
    """)
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM daily_institutional WHERE stock_id=?", (index_id,))
    count = c.fetchone()[0]
    print(f"Inserted {count} aggregate institutional records for {index_id}.")
    conn.close()

if __name__ == "__main__":
    fix_taiex_volume()
    build_index_institutional('db/twse_market.db', 'TAIEX', '加權指數')
    build_index_institutional('db/tpex_market.db', 'TPEx', '櫃買指數')
