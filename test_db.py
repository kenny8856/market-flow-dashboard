import sqlite3
c=sqlite3.connect('db/tpex_market.db').cursor()
row = c.execute('SELECT stock_id, date, close_price FROM daily_quotes WHERE stock_id=''7792'' ORDER BY date LIMIT 1').fetchone()
print(repr(row))
