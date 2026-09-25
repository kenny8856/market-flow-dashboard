import sqlite3

def fix_index_inst(db_path, index_id, index_name):
    print(f"Fixing {index_id} in {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("DELETE FROM daily_institutional WHERE stock_id=?", (index_id,))
    
    # We join daily_institutional and daily_quotes to compute the exact NTD amount for each stock, then sum them up!
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
            i.date, '{index_id}', '{index_name}',
            0, 0, SUM(i.foreign_net * q.close_price),
            0, 0, SUM(i.trust_net * q.close_price),
            SUM(i.dealer_net * q.close_price),
            0, 0, SUM(i.dealer_self_net * q.close_price),
            0, 0, SUM(i.dealer_hedge_net * q.close_price),
            SUM(i.total_net * q.close_price),
            0, 0, 0,
            CURRENT_TIMESTAMP
        FROM daily_institutional i
        JOIN daily_quotes q ON i.stock_id = q.stock_id AND i.date = q.date
        WHERE i.stock_id != '{index_id}'
        GROUP BY i.date
    """)
    conn.commit()
    print(f"Done fixing {index_id}.")
    conn.close()

if __name__ == "__main__":
    fix_index_inst('db/twse_market.db', 'TAIEX', '加權指數')
    fix_index_inst('db/tpex_market.db', 'TPEx', '櫃買指數')
