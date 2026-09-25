import sqlite3
c=sqlite3.connect('db/tpex_market.db').cursor()
row = c.execute('SELECT close_price, volume_lots FROM daily_quotes WHERE stock_id=''3105'' AND date=''2020-01-02''').fetchone()
print('3105 on 2020-01-02:', row)
row2 = c.execute('SELECT close_price, volume_lots FROM daily_quotes WHERE stock_id=''3105'' AND date=''2026-09-22''').fetchone()
print('3105 on 2026-09-22:', row2)
