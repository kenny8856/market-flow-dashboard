import sqlite3
c = sqlite3.connect('db/twse_market.db').cursor()
print(c.execute("SELECT date, close_price FROM daily_quotes WHERE stock_id='2330' ORDER BY date DESC LIMIT 3").fetchall())
