import sqlite3
import pandas as pd
import numpy as np

def calculate_vp(df_quotes, days=90):
    if len(df_quotes) < 5:
        return {}
    df = df_quotes.head(days)
    min_p = df['low_price'].min()
    max_p = df['high_price'].max()
    if min_p == max_p:
        return {'poc_price': min_p, 'va_low': min_p, 'va_high': min_p}
        
    num_bins = 50
    step = (max_p - min_p) / num_bins
    bin_edges = [min_p + i * step for i in range(num_bins + 1)]
    bin_volumes = [0.0] * num_bins
    
    for _, row in df.iterrows():
        l = row['low_price']
        h = row['high_price']
        v = row['volume_lots']
        if h == l:
            idx = max(0, min(int((l - min_p) / step), num_bins - 1))
            bin_volumes[idx] += v
            continue
            
        b_start = max(0, min(int((l - min_p) / step), num_bins - 1))
        b_end = max(0, min(int((h - min_p) / step), num_bins - 1))
        span = max(1, b_end - b_start + 1)
        v_per_bin = v / float(span)
        for bi in range(b_start, b_end + 1):
            bin_volumes[bi] += v_per_bin
            
    poc_idx = bin_volumes.index(max(bin_volumes))
    poc_price = round((bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2.0, 2)
    
    total_vol = sum(bin_volumes)
    target_vol = total_vol * 0.70
    current_vol = bin_volumes[poc_idx]
    left = poc_idx
    right = poc_idx
    
    while current_vol < target_vol and (left > 0 or right < num_bins - 1):
        v_left = bin_volumes[left - 1] if left > 0 else -1.0
        v_right = bin_volumes[right + 1] if right < num_bins - 1 else -1.0
        if v_right >= v_left:
            right += 1
            current_vol += bin_volumes[right]
        else:
            left -= 1
            current_vol += bin_volumes[left]
            
    va_low = round(bin_edges[left], 2)
    va_high = round(bin_edges[right + 1], 2)
    return {'poc_price': poc_price, 'va_low': va_low, 'va_high': va_high}

def get_index_stats(db_path, index_id, index_name, market_type):
    try:
        conn = sqlite3.connect(db_path)
        # Fetch 90 days for VP
        df_q = pd.read_sql(f"SELECT date, low_price, high_price, close_price, volume_lots FROM daily_quotes WHERE stock_id='{index_id}' ORDER BY date DESC LIMIT 90", conn)
        price = 0
        ret_5d = 0
        vp = {}
        if len(df_q) >= 1:
            price = df_q.iloc[0]['close_price']
            vp = calculate_vp(df_q, days=90)
            if len(df_q) >= 6:
                ret_5d = round((price - df_q.iloc[5]['close_price']) / df_q.iloc[5]['close_price'] * 100, 2)
                
        df_i = pd.read_sql(f"SELECT foreign_net, trust_net FROM daily_institutional WHERE stock_id='{index_id}' ORDER BY date DESC LIMIT 5", conn)
        f_5d = 0
        t_5d = 0
        if len(df_i) > 0:
            f_5d = round(df_i['foreign_net'].sum() / 1e8, 1)
            t_5d = round(df_i['trust_net'].sum() / 1e8, 1)
            
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
            'vp': vp,
            'inst_5d': {
                'foreign_5d': f_5d,
                'trust_5d': t_5d,
                'margin_5d': 0,
                'sbl_5d': 0
            },
            'warrant_summary': {
                'call_ratio': call_ratio,
                'put_ratio': put_ratio
            }
        }
    except Exception as e:
        print(f"Error getting stats for {index_id}: {e}")
        return {'id': index_id, 'name': index_name, 'market_type': market_type, 'price': 0, 'ret_5d': 0, 'vp': {}, 'inst_5d': {}, 'warrant_summary': {}}
