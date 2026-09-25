import sqlite3
conn=sqlite3.connect('db/tpex_market.db')
c=conn.cursor()
c.execute('SELECT stock_id, date, close_price, volume_lots FROM daily_quotes ORDER BY stock_id, date DESC')
rows = c.fetchall()
to_delete = []
current_streak = []
prev_key = None

for r in rows:
    sid, d, cp, vol = r
    key = (sid, cp, vol)
    if key == prev_key:
        current_streak.append(r)
    else:
        if len(current_streak) > 3 and current_streak[0][3] > 0:
            # A streak of >3 days with identical price and non-zero volume
            # Keep the FIRST one (which is the most recent date since we ordered DESC)
            # Delete the rest
            to_delete.extend([x[1] for x in current_streak[1:]])
        current_streak = [r]
        prev_key = key

if len(current_streak) > 3 and current_streak[0][3] > 0:
    to_delete.extend([x[1] for x in current_streak[1:]])

print(f'Found {len(to_delete)} fake duplicate rows to delete.')

