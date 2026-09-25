"""
權證多因子量化評分與推薦機制 (EtfinfoGo Warrant Screener)
基於實戰摩擦成本為核心的六維度多因子量化評分模型，
取代原本的「權證小哥」簡單條件篩選，提供更精確的權證推薦。
"""

import os
import ssl
import json
import sqlite3
import urllib.request
import datetime
from typing import List, Dict, Any

TOP_ISSUERS = {
    '92': '凱基', '70': '元大', '98': '群益',
    '81': '富邦', '93': '華南', '91': '統一',
    '72': '兆豐', '88': '元富', '14': '永豐',
    '58': '康和'
}

class MultiFactorWarrantScreener:
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db', 'market_flow.db')
        if self.use_cache:
            self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS yuanta_warrant_cache (
                    stock_id TEXT,
                    option_type TEXT,
                    cache_date TEXT,
                    payload_json TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (stock_id, option_type, cache_date)
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def fetch_raw_warrants(self, stock_id: str, option_type: str = 'CALL') -> List[Dict]:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        opt_upper = option_type.upper()
        
        if self.use_cache:
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                res = c.execute("""
                    SELECT payload_json FROM yuanta_warrant_cache
                    WHERE stock_id=? AND option_type=? AND cache_date=?
                """, (stock_id, opt_upper, today_str)).fetchone()
                conn.close()
                if res and res[0]:
                    return json.loads(res[0])
            except Exception:
                pass

        wtype = '1' if opt_upper == 'CALL' else '2'
        url = 'https://www.warrantwin.com.tw/eyuanta/Warrant/GetWarData.ashx'
        payload = f"dmode=2&a=0&wtype={wtype}&stk={stock_id}".encode('utf-8')
        
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://www.warrantwin.com.tw',
            'Referer': f'https://www.warrantwin.com.tw/eyuanta/Warrant/Search.aspx?stk={stock_id}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, data=payload, headers=headers)
        
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                import gzip
                if response.info().get('Content-Encoding') == 'gzip':
                    raw_data = gzip.decompress(response.read()).decode('utf-8')
                else:
                    raw_data = response.read().decode('utf-8')
                data = json.loads(raw_data)
                records = data.get('Table', [])
        except Exception as e:
            return []

        if records and self.use_cache:
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO yuanta_warrant_cache
                    (stock_id, option_type, cache_date, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (stock_id, opt_upper, today_str, json.dumps(records), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
            except Exception:
                pass

        return records

    def _calc_score_and_tag(self, w: Dict) -> Dict:
        """
        計算多因子分數與推薦標籤
        """
        wid = str(w.get('FLD_WAR_ID', '')).strip()
        wname = str(w.get('FLD_WAR_NM', '')).strip()
        buy_price = float(w.get('FLD_WAR_BUY_PRICE') or 0.0)
        sell_price = float(w.get('FLD_WAR_SELL_PRICE') or 0.0)
        out_vol_rate = float(w.get('FLD_OUT_VOL_RATE') or 0.0)
        period = int(w.get('FLD_PERIOD') or 0)
        in_out_dec = float(w.get('FLD_IN_OUT_DECIMAL') or 0.0)
        raw_leverage = float(w.get('FLD_LEVERAGE') or 0.0)
        delta = float(w.get('FLD_DELTA') or 0.0)
        theta = float(w.get('FLD_THETA') or 0.0)
        
        eff_leverage = abs(raw_leverage)
        
        if buy_price <= 0.0 or sell_price <= 0.0 or eff_leverage <= 0.0:
            return None
            
        buy_sell_rate_raw = w.get('FLD_BUY_SELL_RATE')
        if buy_sell_rate_raw and float(buy_sell_rate_raw) > 0:
            buy_sell_rate = float(buy_sell_rate_raw)
        else:
            buy_sell_rate = ((sell_price - buy_price) / buy_price) * 100.0
            
        diff_lever_ratio = buy_sell_rate / eff_leverage if eff_leverage > 0 else 999.0
        abs_delta = abs(delta)
        theta_loss_ratio = (abs(theta) / buy_price) * 100.0 if buy_price > 0 else 999.0

        # -------------------------------------------------------------------
        # 因子計分
        # -------------------------------------------------------------------
        total_score = 0.0
        
        # 因子 1：差槓比 (Max 30)
        if diff_lever_ratio <= 0.20:
            total_score += 30
        elif diff_lever_ratio <= 0.35:
            total_score += 26
        elif diff_lever_ratio <= 0.50:
            total_score += 20
        elif diff_lever_ratio <= 0.80:
            total_score += 12
        elif diff_lever_ratio <= 1.50:
            total_score += 5
            
        # 因子 2：距到期天數 (Max 20)
        if 90 <= period <= 240:
            total_score += 20
        elif 60 <= period < 90:
            total_score += 15
        elif period > 240:
            total_score += 14
        elif 30 <= period < 60:
            total_score += 6
            
        # 因子 3：價內外程度 (Max 20)
        m = in_out_dec
        if -15.0 <= m <= -3.0:
            total_score += 20
        elif -3.0 < m <= 5.0:
            total_score += 16
        elif -25.0 <= m < -15.0:
            total_score += 12
        elif 5.0 < m <= 15.0:
            total_score += 10
        elif abs(m) > 25.0:
            total_score += 3
        else:
            total_score += 8
            
        # 因子 4：Delta 敏感度 (Max 15)
        if 0.35 <= abs_delta <= 0.65:
            total_score += 15
        elif (0.20 <= abs_delta < 0.35) or (0.65 < abs_delta <= 0.80):
            total_score += 10
        elif abs_delta > 0.80:
            total_score += 6
        elif abs_delta < 0.20:
            total_score += 3
            
        # 因子 5：Theta 每日損耗 (Max 10)
        if theta_loss_ratio <= 1.0:
            total_score += 10
        elif theta_loss_ratio <= 2.0:
            total_score += 8
        elif theta_loss_ratio <= 3.5:
            total_score += 5
        else:
            total_score += 2
            
        # 因子 6：風控與流動性 (+5 / -45)
        if out_vol_rate > 80.0:
            total_score -= 20
        if buy_price < 0.20:
            total_score -= 25
            
        # Optional: 造市加分，假設我們有委買賣量的話 (若無則略過)
        bid_vol = float(w.get('FLD_WAR_BUY_VOL') or 0.0)
        ask_vol = float(w.get('FLD_WAR_SELL_VOL') or 0.0)
        if (bid_vol + ask_vol) >= 200.0:
            total_score += 5
            
        # 邊界鉗制
        total_score = max(0.0, min(100.0, total_score))
        
        # -------------------------------------------------------------------
        # 推薦標籤
        # -------------------------------------------------------------------
        tag = "標準流通"
        if total_score >= 80.0:
            tag = "⭐ 首選精選"
        elif eff_leverage >= 6.0 and total_score >= 65.0:
            tag = "⚡ 高槓桿"
        elif theta_loss_ratio <= 1.2 and period >= 120 and total_score >= 60.0:
            tag = "🛡️ 低時間損耗"
        elif abs(m) <= 5.0 and total_score >= 60.0:
            tag = "🎯 價平穩健"
        elif total_score < 45.0:
            tag = "⚠️ 觀察中"
            
        agt_id = str(w.get('FLD_ISSUE_AGT_ID', '')).strip()
        issuer_name = TOP_ISSUERS.get(agt_id, f"商{agt_id}")
        
        return {
            'warrant_id': wid,
            'warrant_name': wname,
            'strike_price': float(w.get('FLD_N_STRIKE_PRC') or 0.0),
            'buy_price': buy_price,
            'sell_price': sell_price,
            'spread_ticks': round((sell_price - buy_price) / 0.01, 1),
            'period': period,
            'in_out_dec': in_out_dec,
            'leverage': round(eff_leverage, 2),
            'raw_leverage': raw_leverage,
            'buy_sell_rate': round(buy_sell_rate, 2),
            'diff_lever_ratio': round(diff_lever_ratio, 3),
            'out_vol_rate': round(out_vol_rate, 1),
            'delta': round(delta, 3),
            'theta': round(theta, 4),
            'theta_loss_ratio': round(theta_loss_ratio, 2),
            'iv': round(float(w.get('FLD_YUANTA_IV') or w.get('FLD_IV_BUY_PRICE') or 0.0), 1),
            'issuer_id': agt_id,
            'issuer_name': issuer_name,
            'total_score': total_score,
            'recommend_tag': tag
        }

    def screen_top3_warrants(self, stock_id: str, option_type: str = 'CALL', top_n: int = 3) -> List[Dict[str, Any]]:
        raw_list = self.fetch_raw_warrants(stock_id, option_type)
        if not raw_list:
            return []

        scored_warrants = []
        for w in raw_list:
            try:
                res = self._calc_score_and_tag(w)
                if res is not None:
                    scored_warrants.append(res)
            except Exception:
                continue

        # 依照綜合分數降冪排序，分數相同時比較差槓比
        scored_warrants.sort(key=lambda x: (x['total_score'], -x['diff_lever_ratio']), reverse=True)
        
        return scored_warrants[:top_n]

# 相容舊版呼叫，把 XiaogeWarrantScreener 指向新版
XiaogeWarrantScreener = MultiFactorWarrantScreener
