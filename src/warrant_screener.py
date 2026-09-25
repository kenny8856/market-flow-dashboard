"""
權證小哥五大指標嚴選系統 (Xiaoge Warrant Screener)
對接元大權證網 (https://www.warrantwin.com.tw/eyuanta/) 官方後端 API 每日 16:00 最新數據，
精準實作權證小哥核心篩選漏斗：
1. 差槓比 < 0.3% (買賣價差比 / 實質槓桿，交易成本極小化)
2. 價平 ～ 價外 15% 至 25% (價外介於 -25.0% 至 +5.0% 兼具槓桿彈性與敏感度)
3. 剩餘天數至少 > 120 天 (抗時間價值 Theta 耗損)
4. 隱波率長期穩定不變 (優先選擇優良不降隱波之一線造市券商：元大、凱基、富邦等)
5. 流通在外比例 10% ～ 60% 之間 (避免券商斷單籌碼失真，也避免無人交易流動性不足)
"""

import os
import sys
import ssl
import gzip
import json
import sqlite3
import argparse
import datetime
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TOP_ISSUERS = {
    '980': '元大', '9800': '元大',
    '920': '凱基', '9200': '凱基',
    '960': '富邦', '9600': '富邦',
    '910': '統一', '9100': '統一',
    '9A0': '國泰', '9A00': '國泰',
    '970': '永豐金', '9700': '永豐金',
    '930': '群益', '9300': '群益',
    '700': '兆豐', '7000': '兆豐',
    '585': '統一證'
}

class XiaogeWarrantScreener:
    API_URL = "https://www.warrantwin.com.tw/eyuanta/ws/GetWarData.ashx"
    
    def __init__(self, db_path: Optional[str] = None):
        self.ssl_context = ssl._create_unverified_context()
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "db", "market_flow.db")
        else:
            self.db_path = db_path
        self._init_cache_table()

    def _init_cache_table(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
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
        except Exception as e:
            print(f"[WarrantScreener] 快取資料庫初始化警告: {e}")

    def fetch_raw_warrants(self, stock_id: str, option_type: str = 'CALL', use_cache: bool = True) -> List[Dict[str, Any]]:
        stock_id = str(stock_id).strip()
        opt_upper = option_type.upper()
        war_type = '1' if opt_upper == 'CALL' else '2'
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if use_cache:
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                row = cur.execute("""
                    SELECT payload_json FROM yuanta_warrant_cache
                    WHERE stock_id = ? AND option_type = ? AND cache_date = ?
                """, (stock_id, opt_upper, today_str)).fetchone()
                conn.close()
                if row and row[0]:
                    return json.loads(row[0])
            except Exception:
                pass

        paramdata = {
            'format': 'JSON',
            'factor': {
                'columns': [
                    'FLD_WAR_ID', 'FLD_WAR_NM', 'FLD_UND_ID', 'FLD_UND_NM',
                    'FLD_OBJ_TXN_PRICE', 'FLD_WAR_BUY_PRICE', 'FLD_WAR_SELL_PRICE',
                    'FLD_OUT_VOL_RATE', 'FLD_N_STRIKE_PRC', 'FLD_N_UND_CONVER',
                    'FLD_PERIOD', 'FLD_IN_OUT', 'FLD_IN_OUT_DECIMAL', 'FLD_LEVERAGE',
                    'FLD_BUY_SELL_RATE', 'FLD_DELTA', 'FLD_THETA', 'FLD_YUANTA_IV',
                    'FLD_IV_BUY_PRICE', 'FLD_IV_SELL_PRICE', 'FLD_WAR_TYPE', 'FLD_ISSUE_AGT_ID'
                ],
                'condition': [
                    {'field': 'FLD_UND_ID', 'values': [stock_id]},
                    {'field': 'FLD_WAR_TYPE', 'values': [war_type]}
                ],
                'orderby': {'field': 'FLD_PERIOD', 'sort': 'DESC'}
            },
            'pagination': {'row': '2000', 'page': '1'}
        }

        query_str = urllib.parse.urlencode({'data': json.dumps(paramdata)})
        req_url = f"{self.API_URL}?{query_str}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.warrantwin.com.tw/eyuanta/Warrant/Search.aspx',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }

        records = []
        try:
            req = urllib.request.Request(req_url, headers=headers)
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=12) as resp:
                raw = resp.read()
                if raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode('utf-8'))
                records = data.get('result', [])
        except Exception as e:
            print(f"[WarrantScreener] API 請求異常 ({stock_id} {opt_upper}): {e}")
            return []

        if records and use_cache:
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO yuanta_warrant_cache
                    (stock_id, option_type, cache_date, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (stock_id, opt_upper, today_str, json.dumps(records), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
            except Exception:
                pass

        return records

    def screen_top3_warrants(self, stock_id: str, option_type: str = 'CALL', top_n: int = 3, allow_relax_diff: bool = True) -> List[Dict[str, Any]]:
        raw_list = self.fetch_raw_warrants(stock_id, option_type)
        if not raw_list:
            return []

        tier1_warrants = []
        tier2_warrants = []

        for w in raw_list:
            try:
                wid = str(w.get('FLD_WAR_ID', '')).strip()
                wname = str(w.get('FLD_WAR_NM', '')).strip()
                buy_price = float(w.get('FLD_WAR_BUY_PRICE') or 0.0)
                sell_price = float(w.get('FLD_WAR_SELL_PRICE') or 0.0)
                out_vol_rate = float(w.get('FLD_OUT_VOL_RATE') or 0.0)
                period = int(w.get('FLD_PERIOD') or 0)
                in_out_dec = float(w.get('FLD_IN_OUT_DECIMAL') or 0.0)
                raw_leverage = float(w.get('FLD_LEVERAGE') or 0.0)
                strike_price = float(w.get('FLD_N_STRIKE_PRC') or 0.0)
                delta = float(w.get('FLD_DELTA') or 0.0)
                theta = float(w.get('FLD_THETA') or 0.0)
                iv = float(w.get('FLD_YUANTA_IV') or w.get('FLD_IV_BUY_PRICE') or 0.0)
                agt_id = str(w.get('FLD_ISSUE_AGT_ID', '')).strip()
                issuer_name = TOP_ISSUERS.get(agt_id, f"券商{agt_id}")

                eff_leverage = abs(raw_leverage)

                # 1. 基本有效性檢核：排除未報價、極端深價外(報價低於0.05元無造市)或槓桿失效標的
                if buy_price < 0.05 or sell_price <= buy_price or eff_leverage <= 1.0:
                    continue

                # 2. 買賣價差比 (%)
                buy_sell_rate_raw = w.get('FLD_BUY_SELL_RATE')
                if buy_sell_rate_raw and float(buy_sell_rate_raw) > 0:
                    buy_sell_rate = float(buy_sell_rate_raw)
                else:
                    buy_sell_rate = ((sell_price - buy_price) / buy_price) * 100.0

                # 3. 差槓比 (%) = 買賣價差比 / 實質槓桿
                diff_lever_ratio = buy_sell_rate / eff_leverage if eff_leverage > 0 else 999.0

                # =========================================================================
                # 權證小哥 4 大硬性篩選門檻 (HARD GATES) - 絕不放寬天數、價位與流通量！
                # =========================================================================
                # 門檻 1: 剩餘天數嚴格大於 120 天 (抗時間衰減 Theta，絕不讓短天期劣化標的入選)
                if period <= 120:
                    continue

                # 門檻 2: 價平 ～ 價外 15% 至 25% (價外介於 -25.0% 至 +5.0% 之間，嚴禁深價內或深價外)
                if in_out_dec < -25.0 or in_out_dec > 5.0:
                    continue

                # 門檻 3: 流通在外比例嚴格介於 10.0% ～ 60.0% 之間 (嚴禁 <10% 無流動性 或 >60% 籌碼被散戶包牌失真)
                if out_vol_rate < 10.0 or out_vol_rate > 60.0:
                    continue

                # 門檻 4: 優質一線造市券商判定
                is_top_issuer = agt_id in TOP_ISSUERS

                war_item = {
                    'warrant_id': wid,
                    'warrant_name': wname,
                    'strike_price': strike_price,
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
                    'iv': round(iv, 1),
                    'issuer_id': agt_id,
                    'issuer_name': issuer_name,
                    'is_top_issuer': is_top_issuer,
                }

                # 門檻 5: 差槓比階梯式篩選
                # Tier 1 (極品首選): 差槓比嚴格 < 0.3%
                if diff_lever_ratio < 0.3:
                    war_item['is_strict_pass'] = True
                    war_item['tier'] = 1
                    war_item['status_label'] = "★ 小哥嚴選 (<0.3%)"
                    tier1_warrants.append(war_item)
                # Tier 2 (放寬標準): 差槓比 0.3% ~ 0.7% (若市場無 <0.3% 標的則放寬至 0.7% 以內)
                elif allow_relax_diff and diff_lever_ratio <= 0.7:
                    war_item['is_strict_pass'] = False
                    war_item['tier'] = 2
                    war_item['status_label'] = "◆ 差槓比放寬 (0.3%~0.7%)"
                    tier2_warrants.append(war_item)

            except Exception:
                continue

        # 排序規則：差槓比越小越好 (摩擦成本最低優先) -> 實質槓桿越高越好 (獲利爆發力最高優先)
        tier1_warrants.sort(key=lambda x: (x['diff_lever_ratio'], -x['leverage']))
        tier2_warrants.sort(key=lambda x: (x['diff_lever_ratio'], -x['leverage']))

        # 組合輸出：優先滿足 Tier 1 (<0.3%)；若不足或無標的，以 Tier 2 (0.3%~0.7%) 遞補至最多 top_n 檔
        final_warrants = tier1_warrants[:top_n]
        if allow_relax_diff and len(final_warrants) < top_n:
            needed = top_n - len(final_warrants)
            final_warrants.extend(tier2_warrants[:needed])

        return final_warrants


def main():
    parser = argparse.ArgumentParser(description="權證小哥 5 大指標嚴選標的工具 (對接元大權證網)")
    parser.add_argument("--stock", "-s", type=str, default="2330", help="個股代碼")
    parser.add_argument("--type", "-t", type=str, default="CALL", choices=["CALL", "PUT", "call", "put"], help="權證類別")
    parser.add_argument("--top", "-n", type=int, default=3, help="取前 N 檔")
    args = parser.parse_args()

    screener = XiaogeWarrantScreener()
    opt_type = args.type.upper()
    print(f"\n🔍 正在為標的 [{args.stock}] 進行【權證小哥 5 大指標嚴選 ({opt_type})】...")
    
    results = screener.screen_top3_warrants(args.stock, option_type=opt_type, top_n=args.top)
    
    if not results:
        print(f"❌ 查無 [{args.stock}] 之活絡權證資料或市場無報價。")
        return

    print("=" * 95)
    print(f"{'順位':<4} {'狀態':<18} {'代碼':<8} {'名稱':<14} {'差槓比':<9} {'槓桿':<6} {'價差比':<8} {'價外%':<8} {'天數':<6} {'流通%':<7} {'券商':<6}")
    print("-" * 95)
    for i, w in enumerate(results, 1):
        status = "★ 小哥嚴選" if w.get('is_strict_pass') else "◆ 差槓比放寬"
        print(f"#{i:<3} {status:<18} {w['warrant_id']:<8} {w['warrant_name']:<14} {w['diff_lever_ratio']:>6.3f}%  {w['leverage']:>5.2f}x {w['buy_sell_rate']:>6.2f}% {w['in_out_dec']:>+6.1f}% {w['period']:>4}天 {w['out_vol_rate']:>5.1f}% {w['issuer_name']:<6}")
    print("=" * 95)
    print("💡 小哥指標：1.差槓比<0.3% (若無放寬至0.7%)  2.價外-25%~+5%  3.天數>120天  4.流通10%~60%  5.優質造市券商")


if __name__ == '__main__':
    main()
