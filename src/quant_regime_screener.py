"""
投行機構 3 模組市場狀態與執行風控系統 - 核心量化引擎 (含全市場與個股權證分析)
================================================================================
模組 1：市場狀態濾網 (Macro & Breadth Regime) + 臺股立體籌碼多空溫度計 (含全市場權證總額)
模組 2：多空標的篩選池 (Stock Ranking Engine) + 個股權證多空資金流剖析 (無權證者跳過並向下遞補)
模組 3：執行與部位管理 (Execution & Position Sizing with ATR)
"""

import os
import sqlite3
from collections import defaultdict
from .warrant_screener import XiaogeWarrantScreener

# 資料庫預設路徑
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")


class QuantRegimeScreener:
    def __init__(self, db_dir=DB_DIR):
        self.db_dir = db_dir
        self.twse_db = os.path.join(db_dir, "twse_market.db")
        self.tpex_db = os.path.join(db_dir, "tpex_market.db")
        self.margin_db = os.path.join(db_dir, "margin_trading.db")
        self.sbl_db = os.path.join(db_dir, "stock_sbl.db")
        self.taifex_db = os.path.join(db_dir, "taifex_large_trader.db")
        self.cb_db = os.path.join(db_dir, "cb_market.db")
        self.xiaoge_screener = XiaogeWarrantScreener()

    def run_analysis(self, target_date=None):
        """
        執行全套投行三模組量化運算 (整合全市場權證與個股權證)
        """
        # 1. 取得日期序列 (近 130 個交易日，確保 60~120 日 Volume Profile 成交量分佈圖樣本充足)
        conn_twse = sqlite3.connect(self.twse_db)
        cur = conn_twse.cursor()
        
        if target_date:
            dates = [r[0] for r in cur.execute(
                "SELECT DISTINCT date FROM daily_quotes WHERE date <= ? ORDER BY date DESC LIMIT 130", 
                (target_date,)
            ).fetchall()][::-1]
        else:
            dates = [r[0] for r in cur.execute(
                "SELECT DISTINCT date FROM daily_quotes ORDER BY date DESC LIMIT 130"
            ).fetchall()][::-1]
            
        latest_date = dates[-1]
        prev_date = dates[-2] if len(dates) >= 2 else dates[-1]
        d_5d = dates[-5] if len(dates) >= 5 else dates[0]
        d_10d = dates[-10] if len(dates) >= 10 else dates[0]
        d_20d = dates[-20] if len(dates) >= 20 else dates[0]
        
        # 2. 抓取全市場行情歷史
        conn_tpex = sqlite3.connect(self.tpex_db)
        quotes_history = {} # stock_id -> list of (d, o, h, l, c, v)
        stock_names = {}
        stock_markets = {}
        
        for conn, mkt in [(conn_twse, 'TWSE'), (conn_tpex, 'TPEX')]:
            c_cur = conn.cursor()
            for r in c_cur.execute(
                f"SELECT date, stock_id, stock_name, open_price, high_price, low_price, close_price, volume_lots "
                f"FROM daily_quotes WHERE date >= '{dates[0]}' AND date <= '{latest_date}'"
            ).fetchall():
                d, s, name, o, h, l, c, v = r
                if c is not None and v is not None:
                    if s not in quotes_history:
                        quotes_history[s] = []
                    quotes_history[s].append((d, float(o or c), float(h or c), float(l or c), float(c), float(v)))
                    stock_names[s] = name
                    stock_markets[s] = mkt
                    
        conn_twse.close()
        conn_tpex.close()
        
        # 3. 模組 1：計算市場狀態濾網 (Macro & Breadth Regime)
        # (1) 計算全市場站上 60MA (季線) 比例
        above_60ma_count = 0
        valid_stocks_count = 0
        
        for s, hist in quotes_history.items():
            if len(s) != 4 or not s.isdigit():
                continue
            if len(hist) >= 50 and hist[-1][0] == latest_date:
                valid_stocks_count += 1
                closes_60 = [x[4] for x in hist[-60:]]
                ma60 = sum(closes_60) / len(closes_60)
                if hist[-1][4] > ma60:
                    above_60ma_count += 1
                    
        breadth_pct = round((above_60ma_count / valid_stocks_count) * 100, 2) if valid_stocks_count > 0 else 50.0
        
        # (2) 抓取期交所臺指期 (TX) 前五大 / 前十大特法 (近月/遠月/全月) 與 外資淨空單口數/金額
        conn_fut = sqlite3.connect(self.taifex_db)
        cur_fut = conn_fut.cursor()
        fut_rows = cur_fut.execute("""
            SELECT contract_type, net_top5, net_top5_spec, net_top10, net_top10_spec, market_oi
            FROM futures_large_traders WHERE date = ? AND contract_code = 'TX'
        """, (latest_date,)).fetchall()

        foreign_row = cur_fut.execute("""
            SELECT foreign_buy_oi, foreign_sell_oi, foreign_net_oi, foreign_net_amt_yi
            FROM futures_foreign_institutional WHERE date = ?
        """, (latest_date,)).fetchone()
        
        if not foreign_row:
            try:
                from src.macro_chips_updater import update_foreign_futures
                update_foreign_futures(latest_date)
                foreign_row = cur_fut.execute("""
                    SELECT foreign_buy_oi, foreign_sell_oi, foreign_net_oi, foreign_net_amt_yi
                    FROM futures_foreign_institutional WHERE date = ?
                """, (latest_date,)).fetchone()
            except Exception as e:
                pass

        if not foreign_row:
            foreign_row = cur_fut.execute("""
                SELECT foreign_buy_oi, foreign_sell_oi, foreign_net_oi, foreign_net_amt_yi
                FROM futures_foreign_institutional ORDER BY date DESC LIMIT 1
            """).fetchone()

        conn_fut.close()

        tx_details = {
            'top5_spec_near': 0, 'top5_spec_far': 0, 'top5_spec_all': 0,
            'top10_spec_near': 0, 'top10_spec_far': 0, 'top10_spec_all': 0,
            'market_oi': 0,
            'foreign_buy_oi': 0, 'foreign_sell_oi': 0, 'foreign_net_oi': 0, 'foreign_net_amt_yi': 0.0
        }
        for r in fut_rows:
            c_type, n5, n5_spec, n10, n10_spec, m_oi = r
            if "所有" in c_type or c_type == "999999":
                tx_details['top5_spec_all'] = n5_spec or 0
                tx_details['top10_spec_all'] = n10_spec or 0
                tx_details['market_oi'] = m_oi or 0
            elif "當月" in c_type or "近月" in c_type:
                tx_details['top5_spec_near'] = n5_spec or 0
                tx_details['top10_spec_near'] = n10_spec or 0
            elif "遠月" in c_type:
                tx_details['top5_spec_far'] = n5_spec or 0
                tx_details['top10_spec_far'] = n10_spec or 0

        if foreign_row:
            tx_details['foreign_buy_oi'] = foreign_row[0] or 0
            tx_details['foreign_sell_oi'] = foreign_row[1] or 0
            tx_details['foreign_net_oi'] = foreign_row[2] or 0
            tx_details['foreign_net_amt_yi'] = foreign_row[3] or 0.0

        # 法人籌碼生態與主力多空對峙動態解讀
        if tx_details['top5_spec_near'] > 15000 and tx_details['foreign_net_oi'] < -50000:
            tx_dynamic_desc = f"前五大特法在近月契約佈建 +{tx_details['top5_spec_near']:,} 口強大多單護盤，直接抗衡外資高達 {tx_details['foreign_net_oi']:,} 口現貨避險空單；特法遠月小幅避險 ({tx_details['top5_spec_far']:+,}口)，呈現「近月軋空護盤、遠月對沖防禦」之跨月套利對峙格局。"
        elif tx_details['top10_spec_all'] > 0:
            tx_dynamic_desc = f"特法全月維持淨多單防守 (+{tx_details['top10_spec_all']:,}口)，近月多單主力護盤意願偏強。"
        else:
            tx_dynamic_desc = f"特法全月呈現淨空單 ({tx_details['top10_spec_all']:,}口)，期貨主力心態轉趨防守警戒。"
        tx_details['dynamic_desc'] = tx_dynamic_desc
        tx_net_oi = tx_details['top10_spec_all']

        # (3) 抓取大盤融資最新狀況 (上市 TWSE + 上櫃 TPEx 官方金額「億元」與雙市場維持率)
        conn_m = sqlite3.connect(self.margin_db)
        cur_m = conn_m.cursor()
        m_row = cur_m.execute("""
            SELECT twse_margin_bal_yi, twse_margin_chg_yi, twse_collateral_yi, twse_maint_ratio,
                   tpex_margin_bal_yi, tpex_margin_chg_yi, tpex_collateral_yi, tpex_maint_ratio,
                   total_margin_bal_yi, total_margin_chg_yi, total_collateral_yi, total_maint_ratio
            FROM market_margin_summary WHERE date = ?
        """, (latest_date,)).fetchone()

        if not m_row:
            try:
                from src.macro_chips_updater import update_market_margin_summary
                update_market_margin_summary(latest_date)
                m_row = cur_m.execute("""
                    SELECT twse_margin_bal_yi, twse_margin_chg_yi, twse_collateral_yi, twse_maint_ratio,
                           tpex_margin_bal_yi, tpex_margin_chg_yi, tpex_collateral_yi, tpex_maint_ratio,
                           total_margin_bal_yi, total_margin_chg_yi, total_collateral_yi, total_maint_ratio
                    FROM market_margin_summary WHERE date = ?
                """, (latest_date,)).fetchone()
            except Exception as e:
                pass

        if not m_row:
            # 若當前交易日尚未公布或休市，自動抓取最近一個有效收盤交易日之官方數據
            m_row = cur_m.execute("""
                SELECT twse_margin_bal_yi, twse_margin_chg_yi, twse_collateral_yi, twse_maint_ratio,
                       tpex_margin_bal_yi, tpex_margin_chg_yi, tpex_collateral_yi, tpex_maint_ratio,
                       total_margin_bal_yi, total_margin_chg_yi, total_collateral_yi, total_maint_ratio
                FROM market_margin_summary ORDER BY date DESC LIMIT 1
            """).fetchone()

        conn_m.close()

        if m_row:
            margin_stats = {
                'twse_bal_yi': m_row[0],
                'twse_chg_yi': m_row[1],
                'twse_col_yi': m_row[2],
                'twse_maint_ratio': m_row[3],
                'tpex_bal_yi': m_row[4],
                'tpex_chg_yi': m_row[5],
                'tpex_col_yi': m_row[6],
                'tpex_maint_ratio': m_row[7],
                'total_bal_yi': m_row[8],
                'total_chg_yi': m_row[9],
                'total_col_yi': m_row[10],
                'total_maint_ratio': m_row[11]
            }
        else:
            margin_stats = {
                'twse_bal_yi': 0.0, 'twse_chg_yi': 0.0, 'twse_col_yi': 0.0, 'twse_maint_ratio': 160.0,
                'tpex_bal_yi': 0.0, 'tpex_chg_yi': 0.0, 'tpex_col_yi': 0.0, 'tpex_maint_ratio': 160.0,
                'total_bal_yi': 0.0, 'total_chg_yi': 0.0, 'total_col_yi': 0.0, 'total_maint_ratio': 160.0
            }

        # 融資狀態判定文案
        if margin_stats['total_maint_ratio'] >= 170.0:
            margin_status_desc = "籌碼健康充足，維持率遠高於安全線 (無多殺多斷頭風險)"
        elif margin_stats['total_maint_ratio'] >= 160.0:
            margin_status_desc = "維持率處於中性常態區間，槓桿水位正常"
        elif margin_stats['total_maint_ratio'] >= 140.0:
            margin_status_desc = "維持率下滑逼近警戒線，提防個別融資鬆動"
        else:
            margin_status_desc = "🚨 維持率跌入斷頭恐慌區 (<140%)，提防多殺多連鎖踩踏"

        # (4) 判定市場狀態
        if breadth_pct > 55.0 and tx_net_oi > -35000:
            regime_code = "RISK_ON"
            regime_title = "做多狀態 (Risk-On)"
            exposure_limit = "80% ~ 100%"
            regime_desc = "市場寬度健康擴散，期貨特法籌碼無全面避險跡象，允許做多模組積極開倉。"
            kill_switch = False
        elif breadth_pct < 40.0:
            regime_code = "RISK_OFF"
            regime_title = "做空狀態 (Risk-Off / Short Regime)"
            exposure_limit = "0% (全面防禦避險 / 啟動放空)"
            regime_desc = "市場寬度跌破 40% 警戒線，全體均線架構轉弱，多單全面強制清倉熔斷，僅允許反向做空。"
            kill_switch = True
        else:
            regime_code = "NEUTRAL"
            regime_title = "防禦警戒狀態 (Neutral / De-grossing)"
            exposure_limit = "30% 以下"
            regime_desc = "市場寬度處於 40%~55% 震盪中樞，停止盲目追高，現有多單收緊動態停利線，持股降至 30% 以下。"
            kill_switch = False
            
        module_1 = {
            'date': latest_date,
            'regime_code': regime_code,
            'regime_title': regime_title,
            'exposure_limit': exposure_limit,
            'regime_desc': regime_desc,
            'kill_switch': kill_switch,
            'breadth_pct': breadth_pct,
            'above_60ma_count': above_60ma_count,
            'valid_stocks_count': valid_stocks_count,
            'tx_net_oi': tx_net_oi,
            'tx_details': tx_details,
            'margin': margin_stats,
            'margin_status_desc': margin_status_desc,
            'total_margin_chg': margin_stats['total_chg_yi']
        }
        
        # 4. 全市場權證多空買賣總額分析 & 個股權證彙整
        conn_twse = sqlite3.connect(self.twse_db)
        conn_tpex = sqlite3.connect(self.tpex_db)
        
        latest_warrant_date = conn_twse.cursor().execute("SELECT MAX(date) FROM daily_warrants").fetchone()[0]
        
        total_call_amount = 0.0
        total_put_amount = 0.0
        total_call_lots = 0
        total_put_lots = 0
        call_count = 0
        put_count = 0
        
        # stock_id -> {'call_amt': x, 'put_amt': x, 'call_lots': x, 'put_lots': x, 'call_cnt': x, 'put_cnt': x}
        stock_warrants = defaultdict(lambda: {'call_amt': 0.0, 'put_amt': 0.0, 'call_lots': 0, 'put_lots': 0, 'call_cnt': 0, 'put_cnt': 0})
        
        for conn in [conn_twse, conn_tpex]:
            c_cur = conn.cursor()
            for r in c_cur.execute(
                f"SELECT warrant_name, trade_amount, trade_lots, underlying_stock_id "
                f"FROM daily_warrants WHERE date = '{latest_warrant_date}'"
            ).fetchall():
                w_name, amt, lots, s_id = r
                amt = amt or 0.0
                lots = lots or 0
                
                is_call = ('購' in w_name or '牛' in w_name)
                is_put = ('售' in w_name or '熊' in w_name)
                
                is_index_warrant = any(k in w_name for k in ['台灣50', '臺股指', '群臺', 'T50正2'])
                
                if is_call:
                    if is_index_warrant:
                        total_call_amount += amt
                        total_call_lots += lots
                        call_count += 1
                    if s_id:
                        stock_warrants[s_id]['call_amt'] += amt
                        stock_warrants[s_id]['call_lots'] += lots
                        stock_warrants[s_id]['call_cnt'] += 1
                elif is_put:
                    if is_index_warrant:
                        total_put_amount += amt
                        total_put_lots += lots
                        put_count += 1
                    if s_id:
                        stock_warrants[s_id]['put_amt'] += amt
                        stock_warrants[s_id]['put_lots'] += lots
                        stock_warrants[s_id]['put_cnt'] += 1
                        
        conn_twse.close()
        conn_tpex.close()
        
        tot_warrant_amt = total_call_amount + total_put_amount
        call_ratio = (total_call_amount / tot_warrant_amt * 100) if tot_warrant_amt > 0 else 0.0
        put_ratio = (total_put_amount / tot_warrant_amt * 100) if tot_warrant_amt > 0 else 0.0
        pc_ratio = (total_put_amount / total_call_amount) if total_call_amount > 0 else 0.0
        
        # 權證情緒評分 (0 ~ 100)
        if call_ratio >= 96.0:
            warrant_score = 90.0
            warrant_sentiment = "游資狂熱看漲 (認購佔比 > 96%)"
        elif call_ratio >= 90.0:
            warrant_score = 80.0
            warrant_sentiment = "游資積極做多 (認購佔比 90%~96%)"
        elif call_ratio >= 80.0:
            warrant_score = 65.0
            warrant_sentiment = "多方偏多震盪 (認購佔比 80%~90%)"
        elif call_ratio >= 70.0:
            warrant_score = 50.0
            warrant_sentiment = "多空中性平衡 (認購佔比 70%~80%)"
        elif call_ratio >= 55.0:
            warrant_score = 35.0
            warrant_sentiment = "避險放空加劇 (認售佔比上升至 30%~45%)"
        else:
            warrant_score = 20.0
            warrant_sentiment = "恐慌拋售放空 (認售佔比 > 45%)"
            
        warrant_market_metrics = {
            'date': latest_warrant_date,
            'total_amount_yi': round(tot_warrant_amt / 1e8, 2),
            'call_amount_yi': round(total_call_amount / 1e8, 2),
            'put_amount_yi': round(total_put_amount / 1e8, 2),
            'call_ratio': round(call_ratio, 1),
            'put_ratio': round(put_ratio, 1),
            'pc_ratio': round(pc_ratio, 4),
            'call_count': call_count,
            'put_count': put_count,
            'warrant_score': warrant_score,
            'warrant_sentiment': warrant_sentiment
        }
        
        # 5. 抓取法人 5 日買賣超
        inst_5d = {} # s -> (f_5d, t_5d, tot_5d)
        for db_path in [self.twse_db, self.tpex_db]:
            conn = sqlite3.connect(db_path)
            for r in conn.cursor().execute(
                f"SELECT stock_id, SUM(foreign_net_lots), SUM(trust_net_lots), SUM(total_net_lots) "
                f"FROM daily_institutional WHERE date >= '{d_5d}' AND date <= '{latest_date}' GROUP BY stock_id"
            ).fetchall():
                s, f, t, tot = r
                inst_5d[s] = (f or 0, t or 0, tot or 0)
            conn.close()
            
        # 6. 抓取融資 5 日增減
        conn_m = sqlite3.connect(self.margin_db)
        margin_5d = {} # s -> (m_chg5, s_chg5)
        for r in conn_m.cursor().execute(
            f"SELECT stock_id, SUM(margin_change), SUM(short_change) "
            f"FROM daily_margin_trading WHERE date >= '{d_5d}' AND date <= '{latest_date}' GROUP BY stock_id"
        ).fetchall():
            s, mc, sc = r
            margin_5d[s] = (mc or 0, sc or 0)
        conn_m.close()
        
        # 7. 抓取借券賣出
        conn_s = sqlite3.connect(self.sbl_db)
        latest_sbl_date = conn_s.cursor().execute("SELECT MAX(date) FROM daily_sbl_short").fetchone()[0]
        sbl_dates = [r[0] for r in conn_s.cursor().execute(
            "SELECT DISTINCT date FROM daily_sbl_short ORDER BY date DESC LIMIT 6"
        ).fetchall()][::-1]
        sbl_start_date = sbl_dates[0]
        
        sbl_dict = {}
        for r in conn_s.cursor().execute(
            f"SELECT date, stock_id, sbl_sell, sbl_bal FROM daily_sbl_short WHERE date >= '{sbl_start_date}'"
        ).fetchall():
            d, s, sell, bal = r
            if s not in sbl_dict:
                sbl_dict[s] = {'sell_today': 0, 'bal_today': 0, 'bal_5d_ago': 0}
            if d == latest_sbl_date:
                sbl_dict[s]['sell_today'] = (sell or 0) / 1000.0
                sbl_dict[s]['bal_today'] = (bal or 0) / 1000.0
            elif d == sbl_start_date:
                sbl_dict[s]['bal_5d_ago'] = (bal or 0) / 1000.0
        conn_s.close()
        
        # 8. 計算臺股立體籌碼多空溫度計 (整合權證為 6 大維度)
        radar_metrics = self._calc_integrated_radar(latest_date, warrant_score, warrant_market_metrics)
        
        # 9. 個股技術與指標統整
        stats = []
        for s, hist in quotes_history.items():
            if len(s) != 4 or not s.isdigit():
                continue
            if len(hist) < 50 or hist[-1][0] != latest_date:
                continue
                
            c_today = hist[-1][4]
            v_today = hist[-1][5]
            h_today = hist[-1][2]
            l_today = hist[-1][3]
            o_today = hist[-1][1]
            
            if c_today < 15.0:
                continue
                
            closes = [x[4] for x in hist]
            vols = [x[5] for x in hist]
            highs = [x[2] for x in hist]
            lows = [x[3] for x in hist]
            
            ma5 = sum(closes[-5:]) / 5.0
            ma20 = sum(closes[-20:]) / 20.0
            ma60 = sum(closes[-60:]) / len(closes[-60:])
            vol20 = sum(vols[-20:]) / 20.0
            
            if vol20 < 500:
                continue
                
            p_20d_ago = closes[-20]
            ret_20d = (c_today - p_20d_ago) / p_20d_ago if p_20d_ago > 0 else 0
            
            # ATR(14)
            tr_list = []
            for i in range(len(closes)-14, len(closes)):
                tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                tr_list.append(tr)
            atr14 = sum(tr_list) / len(tr_list)
            
            f_5, t_5, tot_5 = inst_5d.get(s, (0, 0, 0))
            m_chg5, s_chg5 = margin_5d.get(s, (0, 0))
            
            sinfo = sbl_dict.get(s, {})
            sbl_sell_today = sinfo.get('sell_today', 0)
            sbl_bal_today = sinfo.get('bal_today', 0)
            sbl_bal_5d = sinfo.get('bal_5d_ago', sbl_bal_today)
            sbl_chg5 = sbl_bal_today - sbl_bal_5d
            sbl_ratio_today = (sbl_sell_today / v_today * 100) if v_today > 0 else 0
            
            prev_high = hist[-2][2] if len(hist) >= 2 else h_today
            prev_low = hist[-2][3] if len(hist) >= 2 else l_today
            
            # 取得個股權證指標
            winfo = stock_warrants.get(s, None)
            if winfo and (winfo['call_amt'] > 0 or winfo['put_amt'] > 0):
                w_tot = winfo['call_amt'] + winfo['put_amt']
                w_call_pct = round(winfo['call_amt'] / w_tot * 100, 1) if w_tot > 0 else 0.0
                w_put_pct = round(winfo['put_amt'] / w_tot * 100, 1) if w_tot > 0 else 0.0
                if w_call_pct >= 85.0:
                    w_tag = "🔴 認購主力壓倒性重押"
                elif w_call_pct >= 65.0:
                    w_tag = "🔴 認購明顯佔優"
                elif w_call_pct <= 25.0:
                    w_tag = "🟢 認售避險放空大增"
                elif w_call_pct <= 45.0:
                    w_tag = "🟢 認售偏空"
                else:
                    w_tag = "🟡 多空勢均力敵"
                warrant_stock_data = {
                    'has_warrants': True,
                    'tot_amt_wan': round(w_tot / 10000.0, 1),
                    'call_amt_wan': round(winfo['call_amt'] / 10000.0, 1),
                    'put_amt_wan': round(winfo['put_amt'] / 10000.0, 1),
                    'call_pct': w_call_pct,
                    'put_pct': w_put_pct,
                    'call_cnt': winfo['call_cnt'],
                    'put_cnt': winfo['put_cnt'],
                    'sentiment': w_tag
                }
            else:
                warrant_stock_data = {
                    'has_warrants': False,
                    'tot_amt_wan': 0.0,
                    'call_amt_wan': 0.0,
                    'put_amt_wan': 0.0,
                    'call_pct': 0.0,
                    'put_pct': 0.0,
                    'call_cnt': 0,
                    'put_cnt': 0,
                    'sentiment': "⚪ 本標的尚無活絡權證交易 (主力以現貨/個股期為主)"
                }
                
            stats.append({
                'stock_id': s,
                'name': stock_names[s],
                'market': stock_markets[s],
                'close': c_today,
                'open': o_today,
                'high': h_today,
                'low': l_today,
                'volume': v_today,
                'vol20': vol20,
                'ma5': ma5,
                'ma20': ma20,
                'ma60': ma60,
                'ret_20d': ret_20d,
                'atr14': atr14,
                'f_5d': f_5,
                't_5d': t_5,
                'tot_5d': tot_5,
                'm_chg5': m_chg5,
                's_chg5': s_chg5,
                'sbl_chg5': sbl_chg5,
                'sbl_sell_today': sbl_sell_today,
                'sbl_ratio_today': sbl_ratio_today,
                'prev_high': prev_high,
                'prev_low': prev_low,
                'warrant': warrant_stock_data
            })
            
        # 10. 依大盤多空位階動態決定選股配額 (偏多: 多方Top10/空方0; 震盪: 各Top5; 偏空: 空方Top10/多方0)
        target_longs = radar_metrics.get('target_longs', 5)
        target_shorts = radar_metrics.get('target_shorts', 5)

        all_rets = sorted([x['ret_20d'] for x in stats])
        top_20_pct_ret = all_rets[int(len(all_rets) * 0.8)] if all_rets else 0.10
        
        long_candidates = []
        for x in stats:
            if x['close'] > x['ma60'] and x['ret_20d'] >= top_20_pct_ret:
                if x['tot_5d'] >= 300 and (x['t_5d'] >= 30 or x['f_5d'] >= 300):
                    if x['sbl_chg5'] <= 300:
                        score = (x['tot_5d'] / x['vol20']) * 45 + (x['ret_20d'] * 30)
                        if x['m_chg5'] <= 0:
                            score += 15
                        if x['warrant']['has_warrants'] and x['warrant']['call_pct'] >= 80.0:
                            score += 15
                        x['score'] = score
                        long_candidates.append(x)
                        
        long_candidates.sort(key=lambda k: k['score'], reverse=True)
        top_longs = []
        if target_longs > 0:
            for x in long_candidates:
                # 必須具備權證標的且有成交金額，無權證者不排入並依序向下遞補
                if not x['warrant']['has_warrants'] or x['warrant']['tot_amt_wan'] <= 0:
                    continue
                    
                # 計算 60~120 天之 Volume Profile (成交量分佈圖 / 交易密集區 / POC)
                vp = self.calculate_volume_profile(quotes_history[x['stock_id']], lookback=90)
                if vp:
                    if vp['relation'] == 'SUPPORT_ABOVE':
                        entry_p = vp['va_high']
                        entry_desc = f"回測 90日密集區上緣 {vp['va_high']:.2f}元 守穩進場 (避免追高雙巴)"
                        stop_loss = round(min(vp['va_low'], entry_p - 1.5 * x['atr14']), 2)
                    elif vp['relation'] == 'INSIDE_POC':
                        entry_p = vp['va_high']
                        entry_desc = f"突破 90日密集區上緣 {vp['va_high']:.2f}元 確認轉強開倉"
                        stop_loss = round(min(vp['va_low'], entry_p - 1.5 * x['atr14']), 2)
                    else: # RESISTANCE_BELOW
                        entry_p = vp['va_high']
                        entry_desc = f"強勢站上籌碼密集壓力區 {vp['va_high']:.2f}元 方可開倉"
                        stop_loss = round(vp['va_low'], 2)
                else:
                    entry_p = max(x['close'], round(x['prev_high'] + 0.05, 2))
                    entry_desc = f"站穩前高 {x['prev_high']:.2f} 開倉"
                    stop_loss = round(entry_p - (2.0 * x['atr14']), 2)

                take_profit = round(entry_p + max(2.5 * x['atr14'], (entry_p - stop_loss) * 1.5), 2)
                stop_pct = round((entry_p - stop_loss) / entry_p * 100, 1) if entry_p > 0 else 0.0
                profit_pct = round((take_profit - entry_p) / entry_p * 100, 1) if entry_p > 0 else 0.0
                rr = round((take_profit - entry_p) / max(0.01, entry_p - stop_loss), 2)
                
                # 權證小哥 5 大指標嚴選 Top 3 認購權證 (元大權證網每日盤後直連)
                xiaoge_w = self.xiaoge_screener.screen_top3_warrants(x['stock_id'], option_type='CALL', top_n=3)

                top_longs.append({
                    'id': x['stock_id'],
                    'name': x['name'],
                    'market': x['market'],
                    'close': x['close'],
                    'ret_20d': round(x['ret_20d'] * 100, 1),
                    'ma5': round(x['ma5'], 2),
                    'ma20': round(x['ma20'], 2),
                    'ma60': round(x['ma60'], 2),
                    'f_5d': x['f_5d'],
                    't_5d': x['t_5d'],
                    'm_chg5': x['m_chg5'],
                    'sbl_chg5': int(x['sbl_chg5']),
                    'atr14': round(x['atr14'], 2),
                    'entry_price': entry_p,
                    'entry_desc': entry_desc,
                    'prev_high': x['prev_high'],
                    'stop_loss': stop_loss,
                    'stop_pct': stop_pct,
                    'take_profit': take_profit,
                    'profit_pct': profit_pct,
                    'rr_ratio': rr,
                    'volume_profile': vp,
                    'warrant': x['warrant'],
                    'xiaoge_warrants': xiaoge_w,
                    'exit_rule': f"收盤跌破 20MA ({x['ma20']:.2f}元) 或 跌破密集區下緣 ({vp['va_low']:.2f}元) 即無條件出場" if vp else f"收盤跌破 20MA ({x['ma20']:.2f}元) 或 法人連 3 賣即刻無條件出場"
                })
                if len(top_longs) == target_longs:
                    break
            
        # 11. 篩選反向做空標的 (依據大盤多空位階配額 target_shorts)
        top_shorts = []
        if target_shorts > 0:
            short_candidates = []
            for x in stats:
                if x['vol20'] >= 800 and x['close'] < x['ma60'] and x['close'] < x['ma20']:
                    if x['tot_5d'] <= -600 and x['m_chg5'] > 0:
                        if x['sbl_ratio_today'] >= 2.0 or x['sbl_sell_today'] >= 150:
                            score = (-x['tot_5d'] / x['vol20']) * 45 + x['sbl_ratio_today'] * 25 + (x['m_chg5'] / x['vol20']) * 15
                            if x['warrant']['has_warrants'] and x['warrant']['put_pct'] >= 5.0:
                                score += 15
                            x['score'] = score
                            short_candidates.append(x)
                            
            short_candidates.sort(key=lambda k: k['score'], reverse=True)
            for x in short_candidates:
                # 必須具備權證標的且有成交金額，無權證者不排入並依序向下遞補
                if not x['warrant']['has_warrants'] or x['warrant']['tot_amt_wan'] <= 0:
                    continue
                    
                # 計算 60~120 天之 Volume Profile (成交量分佈圖 / 交易密集區 / POC)
                vp = self.calculate_volume_profile(quotes_history[x['stock_id']], lookback=90)
                if vp:
                    if vp['relation'] == 'RESISTANCE_BELOW':
                        short_p = vp['va_low']
                        short_desc = f"反彈遇 90日密集區下緣 {vp['va_low']:.2f}元 承壓不過順勢放空"
                        stop_loss = round(max(vp['va_high'], short_p + 1.5 * x['atr14']), 2)
                    elif vp['relation'] == 'INSIDE_POC':
                        short_p = vp['va_low']
                        short_desc = f"跌破 90日密集區下緣 {vp['va_low']:.2f}元 確認破位打入空單"
                        stop_loss = round(max(vp['va_high'], short_p + 1.5 * x['atr14']), 2)
                    else: # SUPPORT_ABOVE
                        short_p = vp['va_low']
                        short_desc = f"失守下方強支撐密集區 {vp['va_low']:.2f}元 轉弱順勢放空"
                        stop_loss = round(vp['va_high'], 2)
                else:
                    short_p = min(x['close'], round(x['prev_low'] - 0.05, 2))
                    short_desc = f"跌破前低 {x['prev_low']:.2f} 打入空單"
                    stop_loss = round(short_p + (2.0 * x['atr14']), 2)

                take_profit = round(short_p - max(2.5 * x['atr14'], (stop_loss - short_p) * 1.5), 2)
                stop_pct = round((stop_loss - short_p) / short_p * 100, 1) if short_p > 0 else 0.0
                profit_pct = round((short_p - take_profit) / short_p * 100, 1) if short_p > 0 else 0.0
                rr = round((short_p - take_profit) / max(0.01, stop_loss - short_p), 2)
                
                # 權證小哥 5 大指標嚴選 Top 3 認售權證 (元大權證網每日盤後直連)
                xiaoge_w = self.xiaoge_screener.screen_top3_warrants(x['stock_id'], option_type='PUT', top_n=3)

                top_shorts.append({
                    'id': x['stock_id'],
                    'name': x['name'],
                    'market': x['market'],
                    'close': x['close'],
                    'ma5': round(x['ma5'], 2),
                    'ma20': round(x['ma20'], 2),
                    'ma60': round(x['ma60'], 2),
                    'f_5d': x['f_5d'],
                    'm_chg5': x['m_chg5'],
                    'sbl_ratio': round(x['sbl_ratio_today'], 1),
                    'sbl_sell_today': int(x['sbl_sell_today']),
                    'atr14': round(x['atr14'], 2),
                    'short_entry': short_p,
                    'short_desc': short_desc,
                    'prev_low': x['prev_low'],
                    'stop_loss': stop_loss,
                    'stop_pct': stop_pct,
                    'take_profit': take_profit,
                    'profit_pct': profit_pct,
                    'rr_ratio': rr,
                    'volume_profile': vp,
                    'warrant': x['warrant'],
                    'xiaoge_warrants': xiaoge_w,
                    'exit_rule': f"盤中強勢站回密集區上緣 ({vp['va_high']:.2f}元) 即無條件空單停損" if vp else f"盤中強勢站回 20MA ({x['ma20']:.2f}元) 即無條件空單停損"
                })

                if len(top_shorts) == target_shorts:
                    break
            
        return {
            'module_1': module_1,
            'radar': radar_metrics,
            'warrant_market': warrant_market_metrics,
            'top_longs': top_longs,
            'top_shorts': top_shorts
        }

    def calculate_volume_profile(self, hist, lookback=90, num_bins=40):
        """
        計算個股過去 60~120 天之 Volume Profile (成交量分佈圖 / POC / Value Area)
        純 Python 演算法，零外部套件依賴
        """
        bars = hist[-lookback:]
        if len(bars) < 20:
            return None

        highs = [b[2] for b in bars]
        lows = [b[3] for b in bars]
        closes = [b[4] for b in bars]
        vols = [b[5] for b in bars]

        min_p = min(lows)
        max_p = max(highs)
        if max_p <= min_p:
            return None

        step = (max_p - min_p) / float(num_bins)
        bin_edges = [min_p + i * step for i in range(num_bins + 1)]
        bin_volumes = [0.0] * num_bins

        # 將每根K棒成交量依價格區間均勻分攤 (Volume-at-Price)
        for b in bars:
            h, l, c, v = b[2], b[3], b[4], b[5]
            if h <= l:
                idx = min(int((c - min_p) / step), num_bins - 1)
                bin_volumes[idx] += v
                continue

            b_start = max(0, min(int((l - min_p) / step), num_bins - 1))
            b_end = max(0, min(int((h - min_p) / step), num_bins - 1))
            span = max(1, b_end - b_start + 1)
            v_per_bin = v / float(span)
            for bi in range(b_start, b_end + 1):
                bin_volumes[bi] += v_per_bin

        # 找出 POC (Point of Control / 最大成交量價格)
        poc_idx = bin_volumes.index(max(bin_volumes))
        poc_price = round((bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2.0, 2)

        # 計算 70% 價值區間 (Value Area: VAL 下緣 ~ VAH 上緣)
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
        current_close = closes[-1]

        # 多空位階判定
        if current_close >= va_high:
            relation = "SUPPORT_ABOVE"
            relation_label = "站穩密集區之上 (轉為強支撐)"
            pos_desc = f"現價突破站穩 {len(bars)}日密集區 ({va_low:.2f}~{va_high:.2f}元)，密集區形成強支撐底座。回測密集區上緣防守開倉，杜絕盲目追高被雙巴。"
        elif current_close <= va_low:
            relation = "RESISTANCE_BELOW"
            relation_label = "跌破密集區之下 (視為沉重套牢壓力)"
            pos_desc = f"現價跌破 {len(bars)}日密集區 ({va_low:.2f}~{va_high:.2f}元)，密集區累積大量套牢賣壓。反彈遇阻不過順勢放空，避免低接遭遇多殺多。"
        else:
            relation = "INSIDE_POC"
            relation_label = "處於密集區內部 (籌碼震盪換手帶)"
            pos_desc = f"現價處於 {len(bars)}日密集換手區間 ({va_low:.2f}~{va_high:.2f}元)，POC核心密集價為 {poc_price:.2f}元，等待突破/跌破邊緣再行動態進場。"

        return {
            "lookback_days": len(bars),
            "current_close": current_close,
            "poc_price": poc_price,
            "va_low": va_low,
            "va_high": va_high,
            "relation": relation,
            "relation_label": relation_label,
            "pos_desc": pos_desc
        }

    def _calc_integrated_radar(self, latest_date, warrant_score, warrant_market_metrics):
        """計算立體籌碼多空溫度計 (六大維度: 期貨、現貨法人、融資、借券、CB、全市場權證)"""
        # 期貨特法得分
        conn_fut = sqlite3.connect(self.taifex_db)
        r_fut = conn_fut.cursor().execute(
            f"SELECT net_top10_spec FROM futures_large_traders WHERE date = '{latest_date}' AND contract_code = 'TX' AND contract_type = '所有契約'"
        ).fetchone()
        conn_fut.close()
        tx_net = r_fut[0] if r_fut and r_fut[0] is not None else 0
        p_taifex_score = 50.0 + (tx_net / 1000.0) * 2.0
        p_taifex_score = max(0.0, min(100.0, p_taifex_score))
        
        # 現貨法人得分 (近 5 日三大法人買超動能)
        conn_twse = sqlite3.connect(self.twse_db)
        dates_5d = [r[0] for r in conn_twse.cursor().execute("SELECT DISTINCT date FROM daily_quotes ORDER BY date DESC LIMIT 5").fetchall()]
        start_d = dates_5d[-1]
        
        inst_sum = conn_twse.cursor().execute(
            f"SELECT SUM(foreign_net_lots), SUM(trust_net_lots) FROM daily_institutional WHERE date >= '{start_d}'"
        ).fetchone()
        conn_twse.close()
        f_lots = inst_sum[0] or 0
        t_lots = inst_sum[1] or 0
        p_inst_score = 50.0 + (f_lots / 5000.0) * 1.5 + (t_lots / 1000.0) * 2.5
        p_inst_score = max(0.0, min(100.0, p_inst_score))
        
        # 散戶融資得分 (結合全市場融資增減金額與大盤融資維持率)
        conn_m = sqlite3.connect(self.margin_db)
        cur_m = conn_m.cursor()
        m_row = cur_m.execute("SELECT total_margin_chg_yi, total_maint_ratio FROM market_margin_summary WHERE date = ?", (latest_date,)).fetchone()
        if not m_row:
            m_row = cur_m.execute("SELECT total_margin_chg_yi, total_maint_ratio FROM market_margin_summary ORDER BY date DESC LIMIT 1").fetchone()
        conn_m.close()
        if m_row and m_row[1] is not None:
            tot_chg_yi, maint = m_row
            # 維持率 > 170% 安全健康 (基準 65 分)，維持率 < 140% 恐慌扣分；增減金額適度微調
            p_margin_score = 65.0 + (maint - 165.0) * 0.3 - (tot_chg_yi / 50.0) * 4.0
            p_margin_score = max(10.0, min(95.0, p_margin_score))
        else:
            p_margin_score = 60.0
        
        # 外資借券得分
        conn_s = sqlite3.connect(self.sbl_db)
        s_date = conn_s.cursor().execute("SELECT MAX(date) FROM daily_sbl_short").fetchone()[0]
        s_sum = conn_s.cursor().execute(f"SELECT SUM(sbl_sell) FROM daily_sbl_short WHERE date = '{s_date}'").fetchone()
        conn_s.close()
        sbl_sell_lots = (s_sum[0] or 0) / 1000.0
        p_sbl_score = 50.0 - (sbl_sell_lots / 3000.0) * 1.5
        p_sbl_score = max(0.0, min(100.0, p_sbl_score))
        
        # 可轉債保底得分
        p_cb_score = 65.0
        
        # 六大維度加權總評分 (期貨20%, 法人20%, 融資15%, 借券15%, CB 15%, 權證 15%)
        composite = (
            p_taifex_score * 0.20 +
            p_inst_score * 0.20 +
            p_margin_score * 0.15 +
            p_sbl_score * 0.15 +
            p_cb_score * 0.15 +
            warrant_score * 0.15
        )
        composite = round(max(0.0, min(100.0, composite)), 1)
        
        # 依大盤立體多空溫度計判定多空位階與選股動態配額 (Dynamic Regime Stock Allocation)
        # 規則：
        # 1. 偏多位階 (>= 55.0分)：選股選多方 Top 10 檔，空方 0 檔 (順勢集中做多，暫停放空)
        # 2. 震盪位階 (45.0 ~ 55.0分)：多空各 Top 5 檔 (多空拉鋸，對沖平衡佈局)
        # 3. 偏空格局 (< 45.0分)：選股選空方 Top 10 檔，多方 0 檔 (空方主導破位，全面避險防禦)
        if composite >= 75.0:
            regime = "偏多攻擊 (Bullish)"
            color = "#ef4444"
            desc = "各路多方與游資期權買盤共振，多頭主控"
            target_longs = 10
            target_shorts = 0
            allocation_mode = "BULL_FOCUS"
            allocation_label = "多方聚焦模式 (多方 Top 10 ｜ 空方 0 檔)"
            allocation_desc = "大盤處於偏多攻擊位階，順勢集中火力做多，暫停逆勢放空"
        elif composite >= 55.0:
            regime = "中性偏多 (Moderate Bull)"
            color = "#f59e0b"
            desc = "籌碼整體偏多，但仍須防範結構分化"
            target_longs = 10
            target_shorts = 0
            allocation_mode = "BULL_FOCUS"
            allocation_label = "多方聚焦模式 (多方 Top 10 ｜ 空方 0 檔)"
            allocation_desc = "大盤處於中性偏多位階，順勢集中火力做多，暫停逆勢放空"
        elif composite >= 45.0:
            regime = "中性震盪 (Neutral)"
            color = "#3b82f6"
            desc = "多空勢均力敵，箱型整理觀望"
            target_longs = 5
            target_shorts = 5
            allocation_mode = "NEUTRAL_HEDGE"
            allocation_label = "多空對沖平衡模式 (多方 Top 5 ｜ 空方 Top 5)"
            allocation_desc = "大盤處於多空拉鋸震盪，多空雙向對沖佈局"
        else:
            regime = "空方主導 (Bearish)"
            color = "#10b981"
            desc = "法人空單壓制，防範下行破位"
            target_longs = 0
            target_shorts = 10
            allocation_mode = "BEAR_DEFENSE"
            allocation_label = "空方避險防禦模式 (空方 Top 10 ｜ 多方 0 檔)"
            allocation_desc = "大盤破位偏空，嚴禁逆勢接刀做多，全面聚焦避險放空"
            
        return {
            'composite_score': composite,
            'regime': regime,
            'color': color,
            'desc': desc,
            'target_longs': target_longs,
            'target_shorts': target_shorts,
            'allocation_mode': allocation_mode,
            'allocation_label': allocation_label,
            'allocation_desc': allocation_desc,
            'p_taifex': round(p_taifex_score, 1),
            'p_inst': round(p_inst_score, 1),
            'p_margin': round(p_margin_score, 1),
            'p_sbl': round(p_sbl_score, 1),
            'p_cb': round(p_cb_score, 1),
            'p_warrant': round(warrant_score, 1)
        }


def run_screener():
    engine = QuantRegimeScreener()
    return engine.run_analysis()
