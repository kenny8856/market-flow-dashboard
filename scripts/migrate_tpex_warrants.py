import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import sqlite3
import time
from datetime import datetime
from src.warrant_linker import WarrantLinker

DB_PATH = "d:/TW_Stock/db/tpex_market.db"

def migrate():
    start_time = time.time()
    print("=" * 80)
    print("開始將 tpex_market.db 內過去一年 263 萬筆上櫃權證資料遷移至 daily_warrants 並鏈結個股...")
    print("=" * 80)

    linker = WarrantLinker()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. 建立權證名稱快取
    c.execute("""
        SELECT DISTINCT stock_name FROM daily_quotes 
        WHERE length(stock_id) = 6 AND (stock_id LIKE '7%' OR stock_name LIKE '%購%' OR stock_name LIKE '%售%');
    """)
    names = [r[0] for r in c.fetchall()]
    print(f">> 提取出 {len(names):,} 個不重複權證名稱，正在進行個股名稱智慧匹配...")

    name_map = {}
    for n in names:
        name_map[n] = linker.link(n)

    matched_cnt = sum(1 for v in name_map.values() if v[0])
    print(f">> 智慧關聯完成！成功匹配標的個股: {matched_cnt:,} 檔 ({matched_cnt/len(name_map)*100:.1f}%)")

    # 2. 串流讀取 daily_quotes 並寫入 daily_warrants
    print(">> 正在讀取歷史行情並批次寫入 daily_warrants 資料表...")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    read_cursor = conn.cursor()
    write_cursor = conn.cursor()

    read_cursor.execute("""
        SELECT date, stock_id, stock_name, amount, volume_shares, volume_lots
        FROM daily_quotes 
        WHERE length(stock_id) = 6 AND (stock_id LIKE '7%' OR stock_name LIKE '%購%' OR stock_name LIKE '%售%');
    """)

    batch_size = 50000
    batch = []
    total_inserted = 0

    insert_sql = """
    INSERT OR REPLACE INTO daily_warrants (
        date, warrant_id, warrant_name, trade_amount, trade_volume, trade_lots,
        underlying_stock_id, underlying_stock_name, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    while True:
        rows = read_cursor.fetchmany(batch_size)
        if not rows:
            break

        for r in rows:
            d_date, w_id, w_name, amt, vol_s, vol_l = r
            s_id, s_name = name_map.get(w_name, ("", ""))
            batch.append((
                d_date,
                w_id,
                w_name,
                float(amt or 0),
                int(vol_s or 0),
                int(vol_l or 0),
                s_id,
                s_name,
                now_str
            ))

        write_cursor.executemany(insert_sql, batch)
        conn.commit()
        total_inserted += len(batch)
        print(f"   已寫入 {total_inserted:,} / 2,631,453 筆...", flush=True)
        batch = []

    duration = round(time.time() - start_time, 2)
    print("=" * 80)
    print(f"【上櫃歷史權證遷移完成】 共寫入 {total_inserted:,} 筆權證歷史數據，耗時 {duration} 秒！")
    print("=" * 80)

    # 驗證
    c.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(*) FROM daily_warrants;")
    res = c.fetchone()
    print(f"daily_warrants 資料表目前狀態: 日期範圍 {res[0]} ~ {res[1]} (共 {res[2]} 個交易日, 總筆數 {res[3]:,} 筆)")
    conn.close()

if __name__ == "__main__":
    migrate()
