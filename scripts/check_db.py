import sqlite3
import pandas as pd

# 1. Check Feb 2026 Volume for TAIEX
conn = sqlite3.connect('db/twse_market.db')
df_taiex = pd.read_sql("SELECT date, close_price, volume_shares, volume_lots FROM daily_quotes WHERE stock_id='TAIEX' AND date >= '2026-01-25' AND date <= '2026-03-05' ORDER BY date", conn)
print("--- TAIEX Volume around Feb 2026 ---")
print(df_taiex.head(20))

# 2. Check institutional data for TAIEX
df_inst = pd.read_sql("SELECT * FROM daily_institutional WHERE stock_id='TAIEX'", conn)
print(f"--- TAIEX Institutional Data Count: {len(df_inst)} ---")

# 3. Check warrants for 臺股指
df_war = pd.read_sql("SELECT DISTINCT underlying_stock_id, underlying_stock_name FROM daily_warrants WHERE underlying_stock_name LIKE '%臺股指%'", conn)
print("--- TAIEX Warrants Underlying Info ---")
print(df_war)

# 4. Check TPEx volume for Feb 2026
conn_tpex = sqlite3.connect('db/tpex_market.db')
df_tpex = pd.read_sql("SELECT date, close_price, volume_shares, volume_lots FROM daily_quotes WHERE stock_id='TPEx' AND date >= '2026-01-25' AND date <= '2026-03-05' ORDER BY date", conn_tpex)
print("--- TPEx Volume around Feb 2026 ---")
print(df_tpex.head(20))

conn.close()
conn_tpex.close()
