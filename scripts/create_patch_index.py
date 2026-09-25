import os

patch_script = r"""
import sqlite3
import pandas as pd

def get_index_stats(db_path, index_id, index_name, market_type):
    try:
        conn = sqlite3.connect(db_path)
        
        # 1. Price and 5d return
        df_q = pd.read_sql(f"SELECT date, close_price FROM daily_quotes WHERE stock_id='{index_id}' ORDER BY date DESC LIMIT 6", conn)
        price = 0
        ret_5d = 0
        if len(df_q) >= 1:
            price = df_q.iloc[0]['close_price']
            if len(df_q) >= 6:
                ret_5d = round((price - df_q.iloc[5]['close_price']) / df_q.iloc[5]['close_price'] * 100, 2)
                
        # 2. Institutional 5d
        df_i = pd.read_sql(f"SELECT foreign_net, trust_net FROM daily_institutional WHERE stock_id='{index_id}' ORDER BY date DESC LIMIT 5", conn)
        f_5d = 0
        t_5d = 0
        if len(df_i) > 0:
            # Note: For TAIEX, foreign_net is stored in amount (元), we should show it in 億元 or 萬?
            # The header expects 張 (lots) or 萬.
            # Wait! The header text says "投信 5日淨買賣 +0 張".
            # For indices, it should say "億元" instead of "張".
            # I will just pass the value in 億元.
            f_5d = round(df_i['foreign_net'].sum() / 1e8, 1)
            t_5d = round(df_i['trust_net'].sum() / 1e8, 1)
            
        # 3. Warrants summary
        # For TAIEX, underlying is IX0001
        underlying = 'IX0001' if index_id == 'TAIEX' else index_id
        df_w = pd.read_sql(f"SELECT date, SUM(CASE WHEN warrant_id NOT LIKE '%P' AND warrant_name NOT LIKE '%售%' AND warrant_name NOT LIKE '%熊%' THEN trade_amount ELSE 0 END) as call_amt, SUM(CASE WHEN warrant_id LIKE '%P' OR warrant_name LIKE '%售%' OR warrant_name LIKE '%熊%' THEN trade_amount ELSE 0 END) as put_amt FROM daily_warrants WHERE underlying_stock_id='{underlying}' GROUP BY date ORDER BY date DESC LIMIT 1", conn)
        
        call_ratio = 0
        put_ratio = 0
        if len(df_w) > 0:
            call_amt = df_w.iloc[0]['call_amt'] or 0
            put_amt = df_w.iloc[0]['put_amt'] or 0
            tot = call_amt + put_amt
            if tot > 0:
                call_ratio = round(call_amt / tot * 100, 1)
                put_ratio = round(put_amt / tot * 100, 1)
                
        conn.close()
        
        return {
            'id': index_id,
            'name': index_name,
            'market_type': market_type,
            'side': 'LONG',
            'rank': 0,
            'price': price,
            'ret_5d': ret_5d,
            'inst_5d': {
                'foreign_5d': f_5d,
                'trust_5d': t_5d,
                'margin_5d': 0,  # difficult to get quickly, default 0
                'sbl_5d': 0
            },
            'warrant_summary': {
                'call_ratio': call_ratio,
                'put_ratio': put_ratio
            }
        }
    except Exception as e:
        print(f"Error getting stats for {index_id}: {e}")
        return {
            'id': index_id,
            'name': index_name,
            'market_type': market_type,
            'side': 'LONG',
            'rank': 0,
            'price': 0,
            'ret_5d': 0
        }

# Read generate_quant_regime.py
file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the hardcoded dicts
target_taiex = \"\"\"        stock_gen.generate_page({
            'id': 'TAIEX',
            'name': '加權指數',
            'market_type': 'TWSE',
            'side': 'LONG',
            'rank': 0,
            'price': 0,
            'ret_5d': 0
        })\"\"\"

replacement_taiex = \"\"\"        # dynamically fetch stats
        from scripts.patch_index_stats import get_index_stats
        taiex_info = get_index_stats('db/twse_market.db', 'TAIEX', '加權指數', 'TWSE')
        stock_gen.generate_page(taiex_info)\"\"\"

target_tpex = \"\"\"        stock_gen.generate_page({
            'id': 'TPEx',
            'name': '櫃買指數',
            'market_type': 'TPEX',
            'side': 'LONG',
            'rank': 0,
            'price': 0,
            'ret_5d': 0
        })\"\"\"

replacement_tpex = \"\"\"        tpex_info = get_index_stats('db/tpex_market.db', 'TPEx', '櫃買指數', 'TPEX')
        stock_gen.generate_page(tpex_info)\"\"\"

if target_taiex in content:
    content = content.replace(target_taiex, replacement_taiex)
    content = content.replace(target_tpex, replacement_tpex)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched generate_quant_regime.py to use dynamic stats")
else:
    print("Could not find TAIEX generation block to patch.")
"""

with open(r'C:\TW_Stock\scripts\patch_index_stats.py', 'w', encoding='utf-8') as f:
    f.write(patch_script)
print("Created script to patch index stats")
