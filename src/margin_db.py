import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "margin_trading.db")

class MarginDatabase:
    """
    管理全市場個股融資融券資料庫 (margin_trading.db)
    包含：
    1. daily_margin_trading: 上市與上櫃每日個股信用交易全量數據
    2. sync_progress: 歷史同步進度與斷點續傳紀錄
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            c = conn.cursor()

            c.execute("""
            CREATE TABLE IF NOT EXISTS daily_margin_trading (
                date TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market_type TEXT NOT NULL,
                -- 融資部分 (張)
                margin_buy INTEGER DEFAULT 0,
                margin_sell INTEGER DEFAULT 0,
                margin_cash_redemption INTEGER DEFAULT 0,
                margin_prev_bal INTEGER DEFAULT 0,
                margin_today_bal INTEGER DEFAULT 0,
                margin_change INTEGER DEFAULT 0,
                margin_limit INTEGER DEFAULT 0,
                margin_utilization_rate REAL DEFAULT 0.0,
                -- 融券部分 (張)
                short_buy INTEGER DEFAULT 0,
                short_sell INTEGER DEFAULT 0,
                short_cash_redemption INTEGER DEFAULT 0,
                short_prev_bal INTEGER DEFAULT 0,
                short_today_bal INTEGER DEFAULT 0,
                short_change INTEGER DEFAULT 0,
                short_limit INTEGER DEFAULT 0,
                short_utilization_rate REAL DEFAULT 0.0,
                -- 多空指標
                short_margin_ratio REAL DEFAULT 0.0,
                offset_shares INTEGER DEFAULT 0,
                note TEXT,
                PRIMARY KEY (date, stock_id)
            )
            """)

            c.execute("CREATE INDEX IF NOT EXISTS idx_margin_date ON daily_margin_trading(date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_margin_stock ON daily_margin_trading(stock_id, date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_margin_name ON daily_margin_trading(stock_name)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_margin_ratio ON daily_margin_trading(date, short_margin_ratio DESC)")

            c.execute("""
            CREATE TABLE IF NOT EXISTS sync_progress (
                date TEXT PRIMARY KEY,
                twse_count INTEGER DEFAULT 0,
                tpex_count INTEGER DEFAULT 0,
                updated_at TEXT
            )
            """)

            conn.commit()

    def save_margin_data(self, date_str: str, rows: List[Dict[str, Any]]) -> int:
        """先刪後存寫入每日融資融券全市場明細"""
        if not rows:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM daily_margin_trading WHERE date = ?", (date_str,))
            insert_sql = """
            INSERT OR REPLACE INTO daily_margin_trading (
                date, stock_id, stock_name, market_type,
                margin_buy, margin_sell, margin_cash_redemption, margin_prev_bal, margin_today_bal, margin_change, margin_limit, margin_utilization_rate,
                short_buy, short_sell, short_cash_redemption, short_prev_bal, short_today_bal, short_change, short_limit, short_utilization_rate,
                short_margin_ratio, offset_shares, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            batch = [
                (
                    r["date"], r["stock_id"], r["stock_name"], r["market_type"],
                    r["margin_buy"], r["margin_sell"], r["margin_cash_redemption"], r["margin_prev_bal"], r["margin_today_bal"], r["margin_change"], r["margin_limit"], r["margin_utilization_rate"],
                    r["short_buy"], r["short_sell"], r["short_cash_redemption"], r["short_prev_bal"], r["short_today_bal"], r["short_change"], r["short_limit"], r["short_utilization_rate"],
                    r["short_margin_ratio"], r["offset_shares"], r["note"]
                )
                for r in rows
            ]
            c.executemany(insert_sql, batch)
            conn.commit()
            return len(batch)

    def record_sync_progress(self, date_str: str, twse_count: int, tpex_count: int):
        """記錄同步進度"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
            INSERT OR REPLACE INTO sync_progress (date, twse_count, tpex_count, updated_at)
            VALUES (?, ?, ?, ?)
            """, (date_str, twse_count, tpex_count, now_str))
            conn.commit()

    def get_synced_dates(self) -> Set[str]:
        """取得已完整收錄之交易日清單 (上市 >= 1000 且 上櫃 >= 700)"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT date FROM sync_progress WHERE twse_count >= 1000 AND tpex_count >= 700")
            return set(r[0] for r in c.fetchall())

    def get_latest_date(self) -> Optional[str]:
        """取得最新收錄日期"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(date) FROM daily_margin_trading")
            row = c.fetchone()
            return row[0] if row and row[0] else None

    def query_stock_margin(self, query_term: str, days: int = 30) -> Tuple[Optional[Dict[str, str]], List[Dict[str, Any]]]:
        """
        以股票代號或名稱查詢該個股最近 N 天的融資融券數據
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
            SELECT stock_id, stock_name, market_type 
            FROM daily_margin_trading 
            WHERE stock_id = ? OR stock_name = ? OR stock_name LIKE ?
            ORDER BY date DESC LIMIT 1
            """, (query_term, query_term, f"%{query_term}%"))
            match = c.fetchone()
            if not match:
                return None, []

            stock_info = {
                "stock_id": match["stock_id"],
                "stock_name": match["stock_name"],
                "market_type": match["market_type"]
            }

            c.execute("""
            SELECT * FROM daily_margin_trading
            WHERE stock_id = ?
            ORDER BY date DESC
            LIMIT ?
            """, (stock_info["stock_id"], days))
            rows = [dict(r) for r in c.fetchall()]
            return stock_info, rows

    def query_top_ratio(self, date_str: Optional[str] = None, limit: int = 20, min_margin: int = 500) -> Tuple[str, List[Dict[str, Any]]]:
        """
        查詢特定日期（預設最新一日）高券資比排行 (潛在軋空股)
        min_margin: 融資餘額門檻 (預設 500 張)，過濾因融資極少造成的極端百分比
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return "", []

            c.execute("""
            SELECT * FROM daily_margin_trading
            WHERE date = ? AND margin_today_bal >= ?
            ORDER BY short_margin_ratio DESC
            LIMIT ?
            """, (date_str, min_margin, limit))
            return date_str, [dict(r) for r in c.fetchall()]

    def query_top_margin_buy(self, date_str: Optional[str] = None, limit: int = 20) -> Tuple[str, List[Dict[str, Any]]]:
        """查詢特定日期融資買超增額前 20 大個股"""
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return "", []

            c.execute("""
            SELECT * FROM daily_margin_trading
            WHERE date = ?
            ORDER BY margin_change DESC
            LIMIT ?
            """, (date_str, limit))
            return date_str, [dict(r) for r in c.fetchall()]

    def query_top_short_sell(self, date_str: Optional[str] = None, limit: int = 20) -> Tuple[str, List[Dict[str, Any]]]:
        """查詢特定日期融券放空增額前 20 大個股"""
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return "", []

            c.execute("""
            SELECT * FROM daily_margin_trading
            WHERE date = ?
            ORDER BY short_change DESC
            LIMIT ?
            """, (date_str, limit))
            return date_str, [dict(r) for r in c.fetchall()]

    def get_market_stats(self) -> Dict[str, Any]:
        """取得融資融券資料庫統計摘要"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*), COUNT(DISTINCT date), COUNT(DISTINCT stock_id), MIN(date), MAX(date) FROM daily_margin_trading")
            total_records, total_days, total_stocks, min_date, max_date = c.fetchone()

            c.execute("SELECT COUNT(*) FROM daily_margin_trading WHERE market_type = '上市'")
            twse_records = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM daily_margin_trading WHERE market_type = '上櫃'")
            tpex_records = c.fetchone()[0]

            return {
                "total_records": total_records or 0,
                "twse_records": twse_records or 0,
                "tpex_records": tpex_records or 0,
                "trading_days": total_days or 0,
                "stocks_count": total_stocks or 0,
                "min_date": min_date,
                "max_date": max_date,
            }
