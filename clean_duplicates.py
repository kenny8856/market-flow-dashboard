import sqlite3

def clean_duplicates():
    conn = sqlite3.connect('db/tpex_market.db', timeout=30)
    c = conn.cursor()
    
    print("Fetching distinct stock_ids...")
    stock_ids = [r[0] for r in c.execute("SELECT DISTINCT stock_id FROM daily_quotes").fetchall()]
    print(f"Total stocks: {len(stock_ids)}")
    
    total_deleted = 0
    for i, sid in enumerate(stock_ids):
        rows = c.execute("SELECT stock_id, date, close_price, volume_lots FROM daily_quotes WHERE stock_id=? ORDER BY date DESC", (sid,)).fetchall()
        if not rows:
            continue
            
        to_delete = []
        current_streak = []
        prev_key = None
        
        for r in rows:
            key = (r[0], r[2], r[3])
            if key == prev_key:
                current_streak.append(r)
            else:
                if len(current_streak) > 3 and current_streak[0][3] > 0:
                    to_delete.extend([x[1] for x in current_streak[1:]])
                current_streak = [r]
                prev_key = key
                
        if len(current_streak) > 3 and current_streak[0][3] > 0:
            to_delete.extend([x[1] for x in current_streak[1:]])
            
        if to_delete:
            chunk_size = 500
            for j in range(0, len(to_delete), chunk_size):
                chunk = to_delete[j:j+chunk_size]
                placeholders = ','.join(['?'] * len(chunk))
                c.execute(f"DELETE FROM daily_quotes WHERE stock_id=? AND date IN ({placeholders})", [sid] + chunk)
                c.execute(f"DELETE FROM daily_institutional WHERE stock_id=? AND date IN ({placeholders})", [sid] + chunk)
            conn.commit()
            total_deleted += len(to_delete)
        
        if (i+1) % 100 == 0:
            print(f"Processed {i+1}/{len(stock_ids)} stocks. Deleted {total_deleted} rows so far.")
            
    print(f"Cleanup complete. Total duplicate rows deleted: {total_deleted}")

if __name__ == '__main__':
    clean_duplicates()
