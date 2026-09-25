"""
Dashboard Engine for Taiwan Stock Market
Aggregates cross-market metrics from SQLite databases:
1. taifex_large_trader.db
2. twse_market.db & tpex_market.db
3. margin_trading.db
4. stock_sbl.db
5. cb_market.db

Computes Market Regime Radar (0-100 Score) and 4 Tactical Stock Strategies.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")

class DashboardEngine:
    def __init__(self, db_dir: str = DB_DIR):
        self.db_dir = db_dir
        self.db_taifex = os.path.join(db_dir, "taifex_large_trader.db")
        self.db_twse = os.path.join(db_dir, "twse_market.db")
        self.db_tpex = os.path.join(db_dir, "tpex_market.db")
        self.db_margin = os.path.join(db_dir, "margin_trading.db")
        self.db_sbl = os.path.join(db_dir, "stock_sbl.db")
        self.db_cb = os.path.join(db_dir, "cb_market.db")

    def _get_conn(self, db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # 1. 大盤多空溫度計 (Market Regime Radar)
    # =========================================================================
    def compute_market_regime(self) -> Dict[str, Any]:
        """計算大盤多空溫度計五大維度與綜合評分"""
        p1 = self._calc_taifex_pillar()
        p2 = self._calc_institutional_pillar()
        p3 = self._calc_margin_pillar()
        p4 = self._calc_sbl_pillar()
        p5 = self._calc_cb_pillar()

        # 加權綜合評分 (0 ~ 100)
        # 權重: 期貨 25%, 現貨法人 25%, 融資 20%, 借券 15%, 可轉債 15%
        composite = (
            p1["score"] * 0.25 +
            p2["score"] * 0.25 +
            p3["score"] * 0.20 +
            p4["score"] * 0.15 +
            p5["score"] * 0.15
        )
        composite = round(max(0.0, min(100.0, composite)), 1)

        if composite >= 80:
            regime = "強烈多頭 (Strong Bull)"
            badge_color = "#10b981"  # Emerald green
            allocation = "建議持股水位 80% ~ 100%"
            action_desc = "主力法人現期貨同步強攻，散戶融資沉澱乾淨。適合順勢積極加碼權值股與強勢突破族群。"
        elif composite >= 65:
            regime = "偏多攻擊 (Bullish)"
            badge_color = "#3b82f6"  # Blue
            allocation = "建議持股水位 60% ~ 80%"
            action_desc = "多方動能佔優勢，法人偏多籌碼穩健。可布局強勢題材股與潛在軋空標的，嚴設移動停利點。"
        elif composite >= 46:
            regime = "中性震盪 / 保守觀望 (Neutral)"
            badge_color = "#f59e0b"  # Amber
            allocation = "建議持股水位 30% ~ 50%"
            action_desc = "多空訊號分歧對立（如土洋對作或期現貨避險）。宜降低操作頻率、保留高現金部位或逢低佈局低溢價可轉債保底。"
        elif composite >= 30:
            regime = "偏空防禦 (Cautious)"
            badge_color = "#f97316"  # Orange
            allocation = "建議持股水位 20% 以下"
            action_desc = "特法期貨轉巨額淨空單或外資借券持續施壓。宜逢高減碼獲利了結，提防融資多殺多骨牌效應。"
        else:
            regime = "強烈空頭 (Bearish)"
            badge_color = "#ef4444"  # Red
            allocation = "建議空手或反向避險"
            action_desc = "全市場籌碼極度渙散，融資斷頭與法人倒貨風險高企。切忌逢低猜底接刀，嚴守風險控管。"

        # 取得最新基準日期
        as_of_date = max(
            [p1.get("date", ""), p2.get("date", ""), p3.get("date", ""), p4.get("date", ""), p5.get("date", "")]
        )

        # 過去 30 天多空歷史趨勢
        history_30d = self._calc_history_trend(days=30)

        return {
            "as_of_date": as_of_date,
            "composite_score": composite,
            "regime": regime,
            "badge_color": badge_color,
            "allocation": allocation,
            "action_desc": action_desc,
            "pillars": {
                "taifex": p1,
                "institutional": p2,
                "margin": p3,
                "sbl": p4,
                "cb": p5
            },
            "history_trend": history_30d
        }

    def _calc_taifex_pillar(self) -> Dict[str, Any]:
        """維度 1: 期交所大額交易人淨部位 (TX 特法淨口數)"""
        if not os.path.exists(self.db_taifex):
            return {"score": 50, "desc": "資料庫不存在", "value": 0, "date": ""}

        with self._get_conn(self.db_taifex) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, net_top10_spec, market_oi 
                FROM futures_large_traders 
                WHERE contract_code = 'TX' AND contract_type = '所有契約'
                ORDER BY date DESC LIMIT 2
            """)
            rows = cur.fetchall()

        if not rows:
            return {"score": 50, "desc": "無期貨資料", "value": 0, "date": ""}

        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else rows[0]

        net_spec = latest["net_top10_spec"]
        net_diff = net_spec - prev["net_top10_spec"]
        date_str = latest["date"]

        # 評分階梯
        if net_spec >= 15000:
            base_score = 95
        elif net_spec >= 10000:
            base_score = 85
        elif net_spec >= 5000:
            base_score = 75
        elif net_spec >= 0:
            base_score = 60
        elif net_spec >= -5000:
            base_score = 45
        elif net_spec >= -10000:
            base_score = 30
        elif net_spec >= -15000:
            base_score = 20
        else:
            base_score = 10

        # 單日增減微調
        if net_diff >= 2000:
            base_score = min(100, base_score + 8)
        elif net_diff <= -2000:
            base_score = max(0, base_score - 8)

        status_text = f"前十大特定法人淨部位: {net_spec:+,} 口 (較前日 {net_diff:+,} 口)"
        return {
            "name": "期貨特法淨未沖銷",
            "weight": 25,
            "score": base_score,
            "value": net_spec,
            "diff": net_diff,
            "date": date_str,
            "status_text": status_text
        }

    def _calc_institutional_pillar(self) -> Dict[str, Any]:
        """維度 2: 現貨三大法人金流動能 (5日累計)"""
        if not os.path.exists(self.db_twse):
            return {"score": 50, "desc": "資料庫不存在", "value": 0, "date": ""}

        with self._get_conn(self.db_twse) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, 
                       SUM(foreign_net) as f_net, 
                       SUM(trust_net) as t_net, 
                       SUM(dealer_net) as d_net
                FROM daily_institutional
                GROUP BY date
                ORDER BY date DESC LIMIT 5
            """)
            rows = cur.fetchall()

        if not rows:
            return {"score": 50, "desc": "無法人資料", "value": 0, "date": ""}

        latest_date = rows[0]["date"]
        # 換算為約當億元 (股數乘上平均價約值或直接以張數/筆數衡量動能)
        latest_net_shares = (rows[0]["f_net"] or 0) + (rows[0]["t_net"] or 0)
        sum_5d_shares = sum((r["f_net"] or 0) + (r["t_net"] or 0) for r in rows)
        latest_net_lots = latest_net_shares // 1000
        sum_5d_lots = sum_5d_shares // 1000

        if sum_5d_lots >= 100000:
            score = 90
        elif sum_5d_lots >= 40000:
            score = 75
        elif sum_5d_lots >= -20000:
            score = 55
        elif sum_5d_lots >= -80000:
            score = 35
        else:
            score = 15

        status_text = f"外資+投信 5 日累計: {sum_5d_lots:+,} 張 (今日 {latest_net_lots:+,} 張)"
        return {
            "name": "三大法人現貨動能",
            "weight": 25,
            "score": score,
            "value": sum_5d_lots,
            "diff": latest_net_lots,
            "date": latest_date,
            "status_text": status_text
        }

    def _calc_margin_pillar(self) -> Dict[str, Any]:
        """維度 3: 全市場信用融資槓桿 (散戶沉澱或浮額暴增)"""
        if not os.path.exists(self.db_margin):
            return {"score": 50, "desc": "無融資資料", "value": 0, "date": ""}

        with self._get_conn(self.db_margin) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, 
                       SUM(margin_today_bal) as total_bal, 
                       SUM(margin_change) as total_diff
                FROM daily_margin_trading
                GROUP BY date
                ORDER BY date DESC LIMIT 5
            """)
            rows = cur.fetchall()

        if not rows:
            return {"score": 50, "desc": "無融資資料", "value": 0, "date": ""}

        latest_date = rows[0]["date"]
        latest_diff = rows[0]["total_diff"] or 0
        sum_5d_diff = sum(r["total_diff"] or 0 for r in rows)
        total_bal = rows[0]["total_bal"] or 0

        # 融資減少通常代表籌碼沉澱(健康偏多)；暴增代表散戶浮額(偏空)
        if latest_diff < -15000:
            score = 85  # 融資大清洗，籌碼變乾淨
        elif latest_diff < 0:
            score = 70  # 溫和減碼
        elif latest_diff < 15000:
            score = 55  # 正常變動
        elif latest_diff < 35000:
            score = 40  # 散戶追價增多
        else:
            score = 20  # 散戶爆量槓桿接刀，警惕多殺多

        status_text = f"全市場融資當日增減: {latest_diff:+,} 張 (近5日累計 {sum_5d_diff:+,} 張)"
        return {
            "name": "全市場散戶融資槓桿",
            "weight": 20,
            "score": score,
            "value": total_bal,
            "diff": latest_diff,
            "date": latest_date,
            "status_text": status_text
        }

    def _calc_sbl_pillar(self) -> Dict[str, Any]:
        """維度 4: 全市場借券賣出放空壓力"""
        if not os.path.exists(self.db_sbl):
            return {"score": 50, "desc": "無借券資料", "value": 0, "date": ""}

        with self._get_conn(self.db_sbl) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, 
                       SUM(sbl_sell) / 1000 as total_sell, 
                       SUM(sbl_bal) / 1000 as total_bal
                FROM daily_sbl_short
                GROUP BY date
                ORDER BY date DESC LIMIT 2
            """)
            rows = cur.fetchall()

        if not rows:
            return {"score": 50, "desc": "無借券資料", "value": 0, "date": ""}

        latest_date = rows[0]["date"]
        latest_sell = rows[0]["total_sell"] or 0
        latest_bal = rows[0]["total_bal"] or 0
        prev_bal = rows[1]["total_bal"] or latest_bal if len(rows) > 1 else latest_bal
        bal_change = latest_bal - prev_bal

        if bal_change < -20000:
            score = 85  # 外資空單大舉停損回補
        elif bal_change < 0:
            score = 70  # 借券賣出餘額微幅下滑
        elif bal_change < 15000:
            score = 50  # 借券持平
        elif bal_change < 30000:
            score = 35  # 外資借券放空增加
        else:
            score = 15  # 外資大舉借券放空避險

        status_text = f"借券賣出存量變化: {bal_change:+,} 張 (當日借賣量 {latest_sell:,} 張)"
        return {
            "name": "外資借券賣出放空壓力",
            "weight": 15,
            "score": score,
            "value": latest_bal,
            "diff": bal_change,
            "date": latest_date,
            "status_text": status_text
        }

    def _calc_cb_pillar(self) -> Dict[str, Any]:
        """維度 5: 櫃買可轉債市場風險偏好 (中位數折溢價率)"""
        if not os.path.exists(self.db_cb):
            return {"score": 50, "desc": "無可轉債資料", "value": 0, "date": ""}

        with self._get_conn(self.db_cb) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, premium_rate, close_price 
                FROM daily_cb_quotes 
                WHERE date = (SELECT MAX(date) FROM daily_cb_quotes)
                  AND premium_rate IS NOT NULL
            """)
            rows = cur.fetchall()

        if not rows:
            return {"score": 50, "desc": "無可轉債資料", "value": 0, "date": ""}

        latest_date = rows[0]["date"]
        premiums = sorted([float(r["premium_rate"]) for r in rows if r["premium_rate"] is not None])
        below_par = sum(1 for r in rows if r["close_price"] is not None and float(r["close_price"]) < 100.0)
        total_cb = len(rows)

        median_prem = premiums[len(premiums)//2] if premiums else 0.0
        below_ratio = (below_par / total_cb * 100) if total_cb else 0.0

        if median_prem >= 12.0 and below_ratio < 6.0:
            score = 85  # 風險偏好積極
        elif median_prem >= 8.0:
            score = 70  # 風險偏好溫和
        elif median_prem >= 4.0:
            score = 50  # 中性
        elif median_prem >= 0.0:
            score = 35  # 保守，溢價萎縮
        else:
            score = 15  # 折價嚴重，市場信用收縮

        status_text = f"CB 溢價率中位數: {median_prem:.1f}% (百元以下折價債: {below_par} 檔 / {below_ratio:.1f}%)"
        return {
            "name": "可轉債市場風險偏好",
            "weight": 15,
            "score": score,
            "value": round(median_prem, 1),
            "diff": round(below_ratio, 1),
            "date": latest_date,
            "status_text": status_text
        }

    def _calc_history_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """回溯過去 N 天的大盤多空溫度趨勢走勢"""
        if not os.path.exists(self.db_taifex):
            return []

        with self._get_conn(self.db_taifex) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, net_top10_spec 
                FROM futures_large_traders 
                WHERE contract_code = 'TX' AND contract_type = '所有契約'
                ORDER BY date DESC LIMIT ?
            """, (days,))
            tx_rows = {r["date"]: r["net_top10_spec"] for r in cur.fetchall()}

        dates = sorted(list(tx_rows.keys()))
        history = []

        for d in dates:
            tx_net = tx_rows.get(d, 0)
            # 簡易估算過去日期的多空分數 (基於期貨部位為基準)
            if tx_net >= 15000: s = 88
            elif tx_net >= 10000: s = 78
            elif tx_net >= 5000: s = 68
            elif tx_net >= 0: s = 58
            elif tx_net >= -5000: s = 48
            elif tx_net >= -10000: s = 38
            else: s = 25

            history.append({
                "date": d,
                "score": s,
                "tx_net": tx_net
            })

        return history

    # =========================================================================
    # 2. 四大實戰策略選股器
    # =========================================================================
    def get_strategy_1_squeeze(self, limit: int = 25) -> List[Dict[str, Any]]:
        """策略 1: 🚀 黃金主力軋空股 (券資比 >= 25% + 融資 >= 300張)"""
        if not os.path.exists(self.db_margin):
            return []

        with self._get_conn(self.db_margin) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, stock_id, stock_name, market_type, 
                       short_margin_ratio, margin_today_bal, short_today_bal, 
                       short_change, margin_change
                FROM daily_margin_trading
                WHERE date = (SELECT MAX(date) FROM daily_margin_trading)
                  AND short_margin_ratio >= 20.0
                  AND margin_today_bal >= 300
                ORDER BY short_margin_ratio DESC
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]

        # 補充借券賣出使用率 (若有 stock_sbl.db)
        if os.path.exists(self.db_sbl) and rows:
            with self._get_conn(self.db_sbl) as conn_sbl:
                cur_s = conn_sbl.cursor()
                for r in rows:
                    cur_s.execute("""
                        SELECT sbl_bal, sbl_next_limit, sbl_sell 
                        FROM daily_sbl_short 
                        WHERE date = ? AND stock_id = ?
                    """, (r["date"], r["stock_id"]))
                    sr = cur_s.fetchone()
                    if sr and (sr["sbl_bal"] + sr["sbl_next_limit"]) > 0:
                        r["sbl_utilization"] = round(sr["sbl_bal"] / (sr["sbl_bal"] + sr["sbl_next_limit"]) * 100, 1)
                        r["sbl_sell_lots"] = sr["sbl_sell"] // 1000
                    else:
                        r["sbl_utilization"] = 0.0
                        r["sbl_sell_lots"] = 0

        return rows

    def get_strategy_2_distribution(self, limit: int = 25) -> List[Dict[str, Any]]:
        """策略 2: ⚠️ 高檔籌碼出貨預警股 (融資大增 + 借券賣出大增)"""
        if not os.path.exists(self.db_margin) or not os.path.exists(self.db_sbl):
            return []

        conn = self._get_conn(self.db_margin)
        conn.execute(f"ATTACH DATABASE '{self.db_sbl}' AS sbl")
        cur = conn.cursor()

        cur.execute("""
            SELECT m.date, m.stock_id, m.stock_name, m.market_type,
                   m.margin_change, m.margin_today_bal,
                   (s.sbl_sell / 1000) AS sbl_sell_lots,
                   (s.sbl_bal / 1000) AS sbl_bal_lots
            FROM daily_margin_trading m
            JOIN sbl.daily_sbl_short s ON m.date = s.date AND m.stock_id = s.stock_id
            WHERE m.date = (SELECT MAX(date) FROM daily_margin_trading)
              AND m.margin_change >= 80
              AND s.sbl_sell >= 80000
            ORDER BY (m.margin_change + s.sbl_sell / 1000) DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_strategy_3_cb_safe(self, limit: int = 25) -> List[Dict[str, Any]]:
        """策略 3: 🛡️ 可轉債不對稱保底安全牌 (CB 價格 100~112 元 + 低折溢價)"""
        if not os.path.exists(self.db_cb):
            return []

        with self._get_conn(self.db_cb) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, cb_id, cb_name, underlying_id, underlying_name,
                       close_price, conversion_price, underlying_close_price,
                       conversion_value, premium_rate, volume_lots, outstanding_lots
                FROM daily_cb_quotes
                WHERE date = (SELECT MAX(date) FROM daily_cb_quotes)
                  AND close_price BETWEEN 100.0 AND 112.0
                  AND premium_rate <= 10.0
                ORDER BY premium_rate ASC
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]

        return rows

    def get_strategy_4_futures_whales(self, limit: int = 25) -> List[Dict[str, Any]]:
        """策略 4: 🐋 個股期貨主力大額重押股 (特法淨多空排序)"""
        if not os.path.exists(self.db_taifex):
            return []

        with self._get_conn(self.db_taifex) as conn:
            cur = conn.cursor()
            # 排除指數期貨，聚焦個股期
            cur.execute("""
                SELECT date, contract_code, contract_name,
                       buy_top10_spec, sell_top10_spec, net_top10_spec, market_oi
                FROM futures_large_traders
                WHERE date = (SELECT MAX(date) FROM futures_large_traders)
                  AND contract_type = '所有契約'
                  AND contract_code NOT IN ('TX', 'TE', 'TF', 'MTX', 'MX4', 'XIF')
                ORDER BY ABS(net_top10_spec) DESC
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]

        return rows

    def get_all_dashboard_data(self) -> Dict[str, Any]:
        """統一匯總網頁儀表板所需之所有結構化數據"""
        regime = self.compute_market_regime()
        s1 = self.get_strategy_1_squeeze()
        s2 = self.get_strategy_2_distribution()
        s3 = self.get_strategy_3_cb_safe()
        s4 = self.get_strategy_4_futures_whales()

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "regime": regime,
            "strategies": {
                "squeeze": s1,
                "distribution": s2,
                "cb_safe": s3,
                "futures_whales": s4
            }
        }
