import sqlite3
conn = sqlite3.connect('db/tpex_market.db')
c = conn.cursor()
res = c.execute('SELECT date, open_price, high_price, low_price, close_price, volume_lots FROM daily_quotes WHERE stock_id=''7792'' ORDER BY date DESC LIMIT 20').fetchall()
for r in res: print(r)
