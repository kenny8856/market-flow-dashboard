import sqlite3
conn=sqlite3.connect('db/tpex_market.db')
c=conn.cursor()
res=c.execute('SELECT date, close_price, volume_lots FROM daily_quotes WHERE stock_id=''7792'' ORDER BY date').fetchall()
for r in res[:10]: print(r)
print('...')
for r in res[-10:]: print(r)
