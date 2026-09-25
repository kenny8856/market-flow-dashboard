"""
SQLite Database Manager for TAIFEX Options Market
Stores:
1. txo_pc_ratio (臺指選擇權買賣權比率)
2. txo_strike_quotes (臺指選擇權各履約價行情與未沖銷契約數)
3. txo_institutional (三大法人選擇權未平倉與契約金額)
4. txo_large_trader (選擇權大額交易人與特法部位)
Provides Max Pain (最大痛點) & Strike Wall (支撐壓力牆) calculation.
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "taifex_options.db")

class TaifexOptionsDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            # 1. Put/Call Ratio
            c.execute("""
                CREATE TABLE IF NOT EXISTS txo_pc_ratio (
                    date TEXT PRIMARY KEY,
                    put_volume INTEGER,
                    call_volume INTEGER,
                    pc_ratio_volume REAL,
                    put_oi INTEGER,
                    call_oi INTEGER,
                    pc_ratio_oi REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Strike Quotes & Open Interest
            c.execute("""
                CREATE TABLE IF NOT EXISTS txo_strike_quotes (
                    date TEXT,
                    commodity_id TEXT,
                    expiry_month TEXT,
                    strike_price REAL,
                    call_put TEXT,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    close_price REAL,
                    settle_price REAL,
                    volume INTEGER,
                    open_interest INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, expiry_month, strike_price, call_put)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_txo_sq_date_exp ON txo_strike_quotes (date, expiry_month)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_txo_sq_date_strike ON txo_strike_quotes (date, strike_price)")

            # 3. 三大法人選擇權交易與未平倉
            c.execute("""
                CREATE TABLE IF NOT EXISTS txo_institutional (
                    date TEXT,
                    commodity_name TEXT,
                    call_put TEXT,
                    institution_type TEXT,
                    buy_lots INTEGER,
                    buy_amount REAL,
                    sell_lots INTEGER,
                    sell_amount REAL,
                    net_lots INTEGER,
                    net_amount REAL,
                    buy_oi_lots INTEGER,
                    buy_oi_amount REAL,
                    sell_oi_lots INTEGER,
                    sell_oi_amount REAL,
                    net_oi_lots INTEGER,
                    net_oi_amount REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, commodity_name, call_put, institution_type)
                )
            """)

            # 4. 選擇權大額交易人
            c.execute("""
                CREATE TABLE IF NOT EXISTS txo_large_trader (
                    date TEXT,
                    contract_code TEXT,
                    contract_name TEXT,
                    call_put TEXT,
                    expiry_month TEXT,
                    trader_type INTEGER,
                    top5_buy INTEGER,
                    top5_sell INTEGER,
                    top10_buy INTEGER,
                    top10_sell INTEGER,
                    total_oi INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, contract_code, call_put, expiry_month, trader_type)
                )
            """)

            # 5. 同步進度表
            c.execute("""
                CREATE TABLE IF NOT EXISTS sync_progress (
                    module_name TEXT PRIMARY KEY,
                    last_synced_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # =========================================================================
    # 寫入方法 (Idempotent 先刪後存 / REPLACE)
    # =========================================================================
    def insert_pc_ratios(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            c.executemany("""
                INSERT OR REPLACE INTO txo_pc_ratio
                (date, put_volume, call_volume, pc_ratio_volume, put_oi, call_oi, pc_ratio_oi)
                VALUES (:date, :put_volume, :call_volume, :pc_ratio_volume, :put_oi, :call_oi, :pc_ratio_oi)
            """, records)
            conn.commit()
            return len(records)

    def insert_strike_quotes(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            # 依日期分組刪除舊資料後再插入
            dates = set(r["date"] for r in records)
            for d in dates:
                c.execute("DELETE FROM txo_strike_quotes WHERE date = ?", (d,))

            c.executemany("""
                INSERT INTO txo_strike_quotes
                (date, commodity_id, expiry_month, strike_price, call_put,
                 open_price, high_price, low_price, close_price, settle_price,
                 volume, open_interest)
                VALUES (:date, :commodity_id, :expiry_month, :strike_price, :call_put,
                        :open_price, :high_price, :low_price, :close_price, :settle_price,
                        :volume, :open_interest)
            """, records)
            conn.commit()
            return len(records)

    def insert_institutional(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            dates = set(r["date"] for r in records)
            for d in dates:
                c.execute("DELETE FROM txo_institutional WHERE date = ?", (d,))

            c.executemany("""
                INSERT INTO txo_institutional
                (date, commodity_name, call_put, institution_type,
                 buy_lots, buy_amount, sell_lots, sell_amount, net_lots, net_amount,
                 buy_oi_lots, buy_oi_amount, sell_oi_lots, sell_oi_amount, net_oi_lots, net_oi_amount)
                VALUES (:date, :commodity_name, :call_put, :institution_type,
                        :buy_lots, :buy_amount, :sell_lots, :sell_amount, :net_lots, :net_amount,
                        :buy_oi_lots, :buy_oi_amount, :sell_oi_lots, :sell_oi_amount, :net_oi_lots, :net_oi_amount)
            """, records)
            conn.commit()
            return len(records)

    def insert_large_trader(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            dates = set(r["date"] for r in records)
            for d in dates:
                c.execute("DELETE FROM txo_large_trader WHERE date = ?", (d,))

            c.executemany("""
                INSERT INTO txo_large_trader
                (date, contract_code, contract_name, call_put, expiry_month, trader_type,
                 top5_buy, top5_sell, top10_buy, top10_sell, total_oi)
                VALUES (:date, :contract_code, :contract_name, :call_put, :expiry_month, :trader_type,
                        :top5_buy, :top5_sell, :top10_buy, :top10_sell, :total_oi)
            """, records)
            conn.commit()
            return len(records)

    # =========================================================================
    # 查詢與統計方法
    # =========================================================================
    def get_latest_date(self) -> Optional[str]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(date) FROM txo_pc_ratio")
            r = c.fetchone()
            return r[0] if r and r[0] else None

    def get_earliest_date(self) -> Optional[str]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT MIN(date) FROM txo_pc_ratio")
            r = c.fetchone()
            return r[0] if r and r[0] else None

    def get_date_count(self) -> int:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(DISTINCT date) FROM txo_pc_ratio")
            r = c.fetchone()
            return r[0] if r else 0

    def get_pc_ratio_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """查詢近 N 天 Put/Call Ratio"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT date, put_volume, call_volume, pc_ratio_volume, put_oi, call_oi, pc_ratio_oi
                FROM txo_pc_ratio
                ORDER BY date DESC LIMIT ?
            """, (days,))
            rows = c.fetchall()
            return [dict(r) for r in reversed(rows)]

    def get_available_expiries(self, date_str: str) -> List[str]:
        """查詢指定日期存在的所有到期月份/週別，依遠近排序"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT DISTINCT expiry_month FROM txo_strike_quotes
                WHERE date = ? ORDER BY expiry_month ASC
            """, (date_str,))
            return [r[0] for r in c.fetchall()]

    def calculate_max_pain(self, date_str: str, expiry_month: Optional[str] = None) -> Dict[str, Any]:
        """
        計算指定日期（與特定到期契約）之 Max Pain (最大痛點)：
        使全市場買權與賣權買方總獲利最小（即選擇權莊家賣方賠付金額最小）之履約價點位。
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            if not expiry_month:
                # 預設選取當月/近月契約 (排除週別，選擇第一個合約)
                expiries = self.get_available_expiries(date_str)
                if not expiries:
                    return {"date": date_str, "max_pain": None, "error": "無履約價數據"}
                # 優先挑選標準月合約 (例如 202609) 或第一個近月
                monthly_exp = [e for e in expiries if "W" not in e]
                expiry_month = monthly_exp[0] if monthly_exp else expiries[0]

            c.execute("""
                SELECT strike_price, call_put, open_interest
                FROM txo_strike_quotes
                WHERE date = ? AND expiry_month = ? AND open_interest > 0
            """, (date_str, expiry_month))
            rows = c.fetchall()

            if not rows:
                return {"date": date_str, "expiry_month": expiry_month, "max_pain": None, "pain_curve": []}

            strikes = sorted(list(set(r["strike_price"] for r in rows)))
            calls: Dict[float, int] = {}
            puts: Dict[float, int] = {}

            for r in rows:
                k = float(r["strike_price"])
                oi = int(r["open_interest"])
                if r["call_put"] == "CALL":
                    calls[k] = calls.get(k, 0) + oi
                else:
                    puts[k] = puts.get(k, 0) + oi

            min_pain = float("inf")
            max_pain_strike = strikes[0]
            pain_curve = []

            for s in strikes:
                # 若結算在 s:
                # CALL 買方獲利 = max(0, s - K) * OI
                # PUT 買方獲利 = max(0, K - s) * OI
                call_pain = sum(max(0.0, s - k) * oi * 50 for k, oi in calls.items()) # 臺指每點 50 元
                put_pain = sum(max(0.0, k - s) * oi * 50 for k, oi in puts.items())
                total_pain = call_pain + put_pain
                pain_curve.append({
                    "strike": s,
                    "call_pain": call_pain,
                    "put_pain": put_pain,
                    "total_pain": total_pain,
                    "call_oi": calls.get(s, 0),
                    "put_oi": puts.get(s, 0)
                })
                if total_pain < min_pain:
                    min_pain = total_pain
                    max_pain_strike = s

            # 找出 Call 與 Put 未平倉最大的履約價 (天花板與地板支撐壓力牆)
            top_call_strike = max(calls.items(), key=lambda x: x[1])[0] if calls else None
            top_put_strike = max(puts.items(), key=lambda x: x[1])[0] if puts else None

            return {
                "date": date_str,
                "expiry_month": expiry_month,
                "max_pain_strike": max_pain_strike,
                "min_pain_amount": min_pain,
                "top_call_resistance_strike": top_call_strike,
                "top_call_oi": calls.get(top_call_strike, 0) if top_call_strike else 0,
                "top_put_support_strike": top_put_strike,
                "top_put_oi": puts.get(top_put_strike, 0) if top_put_strike else 0,
                "pain_curve": pain_curve
            }

    def get_institutional_summary(self, date_str: str) -> List[Dict[str, Any]]:
        """查詢指定日期三大法人選擇權未平倉淨部位"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT commodity_name, call_put, institution_type,
                       buy_oi_lots, sell_oi_lots, net_oi_lots,
                       buy_oi_amount, sell_oi_amount, net_oi_amount
                FROM txo_institutional
                WHERE date = ? AND commodity_name = '臺指選擇權'
                ORDER BY call_put ASC, institution_type ASC
            """, (date_str,))
            return [dict(r) for r in c.fetchall()]
