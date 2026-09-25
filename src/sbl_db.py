import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "stock_sbl.db")

class SBLDatabase:
    """
    管理臺灣證交所與櫃買中心之個股借券資料庫 (stock_sbl.db)
    包含：
    1. daily_sbl_balance: 全市場借券餘額表 (TWT72U)
    2. daily_sbl_short: 全市場借券賣出與融券餘額表 (TWT93U + TPEx margin_sbl)
    3. sync_progress: 歷史同步進度與斷點續傳表
    4. v_stock_sbl_all: 聯合檢視視圖
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

            # 1. 借券餘額表 (TWT72U)
            c.execute("""
            CREATE TABLE IF NOT EXISTS daily_sbl_balance (
                date TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market_type TEXT NOT NULL,
                prev_balance INTEGER DEFAULT 0,
                today_borrow INTEGER DEFAULT 0,
                today_return INTEGER DEFAULT 0,
                today_balance INTEGER DEFAULT 0,
                close_price REAL,
                market_value INTEGER DEFAULT 0,
                PRIMARY KEY (date, stock_id)
            )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_bal_date ON daily_sbl_balance(date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_bal_stock ON daily_sbl_balance(stock_id, date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_bal_name ON daily_sbl_balance(stock_name)")

            # 2. 借券賣出與融券餘額表 (TWT93U + TPEx margin_sbl)
            c.execute("""
            CREATE TABLE IF NOT EXISTS daily_sbl_short (
                date TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market_type TEXT NOT NULL,
                sbl_prev_bal INTEGER DEFAULT 0,
                sbl_sell INTEGER DEFAULT 0,
                sbl_return INTEGER DEFAULT 0,
                sbl_adjust INTEGER DEFAULT 0,
                sbl_bal INTEGER DEFAULT 0,
                sbl_next_limit INTEGER DEFAULT 0,
                margin_prev_bal INTEGER DEFAULT 0,
                margin_sell INTEGER DEFAULT 0,
                margin_buy INTEGER DEFAULT 0,
                margin_cash_redemption INTEGER DEFAULT 0,
                margin_bal INTEGER DEFAULT 0,
                margin_quota INTEGER DEFAULT 0,
                note TEXT,
                PRIMARY KEY (date, stock_id)
            )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_short_date ON daily_sbl_short(date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_short_stock ON daily_sbl_short(stock_id, date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sbl_short_name ON daily_sbl_short(stock_name)")

            # 3. 同步紀錄與斷點續傳表
            c.execute("""
            CREATE TABLE IF NOT EXISTS sync_progress (
                date TEXT PRIMARY KEY,
                balance_count INTEGER DEFAULT 0,
                short_count INTEGER DEFAULT 0,
                updated_at TEXT
            )
            """)

            # 4. 聯合整合視圖 v_stock_sbl_all
            c.execute("DROP VIEW IF EXISTS v_stock_sbl_all")
            c.execute("""
            CREATE VIEW v_stock_sbl_all AS
            SELECT
                COALESCE(s.date, b.date) AS date,
                COALESCE(s.stock_id, b.stock_id) AS stock_id,
                COALESCE(s.stock_name, b.stock_name) AS stock_name,
                COALESCE(s.market_type, b.market_type) AS market_type,
                -- 借券餘額指標
                COALESCE(b.prev_balance, 0) AS sbl_total_prev_bal,
                COALESCE(b.today_borrow, 0) AS sbl_total_borrow,
                COALESCE(b.today_return, 0) AS sbl_total_return,
                COALESCE(b.today_balance, 0) AS sbl_total_bal,
                b.close_price AS close_price,
                COALESCE(b.market_value, 0) AS sbl_total_market_val,
                -- 借券賣出指標
                COALESCE(s.sbl_prev_bal, 0) AS sbl_short_prev_bal,
                COALESCE(s.sbl_sell, 0) AS sbl_short_sell,
                COALESCE(s.sbl_return, 0) AS sbl_short_return,
                COALESCE(s.sbl_adjust, 0) AS sbl_short_adjust,
                COALESCE(s.sbl_bal, 0) AS sbl_short_bal,
                COALESCE(s.sbl_next_limit, 0) AS sbl_short_limit,
                -- 借券賣出使用率 (放空佔借入比例 %)
                CASE
                    WHEN b.today_balance > 0 THEN ROUND(s.sbl_bal * 100.0 / b.today_balance, 2)
                    ELSE 0.0
                END AS sbl_short_utilization_rate,
                -- 融券指標
                COALESCE(s.margin_prev_bal, 0) AS margin_prev_bal,
                COALESCE(s.margin_sell, 0) AS margin_sell,
                COALESCE(s.margin_buy, 0) AS margin_buy,
                COALESCE(s.margin_cash_redemption, 0) AS margin_cash_redemption,
                COALESCE(s.margin_bal, 0) AS margin_bal,
                COALESCE(s.margin_quota, 0) AS margin_quota,
                s.note
            FROM daily_sbl_short s
            LEFT JOIN daily_sbl_balance b ON s.date = b.date AND s.stock_id = b.stock_id
            """)

            conn.commit()

    def save_sbl_balance(self, date_str: str, rows: List[Dict[str, Any]]) -> int:
        """先刪後存寫入每日借券餘額資料"""
        if not rows:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM daily_sbl_balance WHERE date = ?", (date_str,))
            insert_sql = """
            INSERT OR REPLACE INTO daily_sbl_balance (
                date, stock_id, stock_name, market_type,
                prev_balance, today_borrow, today_return, today_balance,
                close_price, market_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            batch = [
                (
                    r["date"], r["stock_id"], r["stock_name"], r["market_type"],
                    r["prev_balance"], r["today_borrow"], r["today_return"], r["today_balance"],
                    r["close_price"], r["market_value"]
                )
                for r in rows
            ]
            c.executemany(insert_sql, batch)
            conn.commit()
            return len(batch)

    def save_sbl_short(self, date_str: str, rows: List[Dict[str, Any]], market_type: Optional[str] = None) -> int:
        """先刪後存寫入每日借券賣出與融券資料 (可指定市場別)"""
        if not rows:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            if market_type:
                c.execute("DELETE FROM daily_sbl_short WHERE date = ? AND market_type = ?", (date_str, market_type))
            else:
                c.execute("DELETE FROM daily_sbl_short WHERE date = ?", (date_str,))
            insert_sql = """
            INSERT OR REPLACE INTO daily_sbl_short (
                date, stock_id, stock_name, market_type,
                sbl_prev_bal, sbl_sell, sbl_return, sbl_adjust, sbl_bal, sbl_next_limit,
                margin_prev_bal, margin_sell, margin_buy, margin_cash_redemption, margin_bal, margin_quota,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            batch = [
                (
                    r["date"], r["stock_id"], r["stock_name"], r["market_type"],
                    r["sbl_prev_bal"], r["sbl_sell"], r["sbl_return"], r["sbl_adjust"], r["sbl_bal"], r["sbl_next_limit"],
                    r["margin_prev_bal"], r["margin_sell"], r["margin_buy"], r["margin_cash_redemption"], r["margin_bal"], r["margin_quota"],
                    r["note"]
                )
                for r in rows
            ]
            c.executemany(insert_sql, batch)
            conn.commit()
            return len(batch)

    def check_date_completeness(self, date_str: str) -> Dict[str, Any]:
        """檢查特定日期各表之完整度"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT count(*) FROM daily_sbl_balance WHERE date = ?", (date_str,))
            bal_cnt = c.fetchone()[0]
            c.execute("SELECT count(*) FROM daily_sbl_short WHERE date = ? AND market_type = '上市'", (date_str,))
            twse_short_cnt = c.fetchone()[0]
            c.execute("SELECT count(*) FROM daily_sbl_short WHERE date = ? AND market_type = '上櫃'", (date_str,))
            tpex_short_cnt = c.fetchone()[0]
            return {
                "has_balance": bal_cnt > 1500,
                "has_twse_short": twse_short_cnt > 800,
                "has_tpex_short": tpex_short_cnt > 700,
                "bal_cnt": bal_cnt,
                "twse_short_cnt": twse_short_cnt,
                "tpex_short_cnt": tpex_short_cnt,
            }

    def record_sync_progress(self, date_str: str, bal_count: int, short_count: int):
        """記錄同步進度"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
            INSERT OR REPLACE INTO sync_progress (date, balance_count, short_count, updated_at)
            VALUES (?, ?, ?, ?)
            """, (date_str, bal_count, short_count, now_str))
            conn.commit()

    def get_synced_dates(self) -> Set[str]:
        """取得已完整同步之交易日清單 (借券餘額與借券賣出皆有完整數據，或標記為休市)"""
        with self._get_conn() as conn:
            c = conn.cursor()
            # 1. 實際兩表皆有充分資料之日期
            c.execute("""
            SELECT b.date 
            FROM (SELECT date, count(*) as cnt FROM daily_sbl_balance GROUP BY date HAVING cnt > 1500) b
            JOIN (SELECT date, count(*) as cnt FROM daily_sbl_short GROUP BY date HAVING cnt > 1800) s
            ON b.date = s.date
            """)
            synced = set(r[0] for r in c.fetchall())
            # 2. sync_progress 中標記為休市(0, 0)之日期
            c.execute("SELECT date FROM sync_progress WHERE balance_count = 0 AND short_count = 0")
            for r in c.fetchall():
                synced.add(r[0])
            return synced

    def get_latest_date(self) -> Optional[str]:
        """取得最新收錄日期"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(date) FROM daily_sbl_short")
            row = c.fetchone()
            return row[0] if row and row[0] else None

    def query_stock_sbl(self, query_term: str, days: int = 30) -> Tuple[Optional[Dict[str, str]], List[Dict[str, Any]]]:
        """
        以股票代號或名稱查詢該個股最近 N 天的借券與借券賣出詳細數據
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            # 尋找匹配個股
            c.execute("""
            SELECT stock_id, stock_name, market_type 
            FROM daily_sbl_short 
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
            SELECT * FROM v_stock_sbl_all
            WHERE stock_id = ?
            ORDER BY date DESC
            LIMIT ?
            """, (stock_info["stock_id"], days))
            rows = [dict(r) for r in c.fetchall()]
            return stock_info, rows

    def query_top_sbl_short(self, date_str: Optional[str] = None, sort_by: str = "sbl_short_bal", limit: int = 20) -> Tuple[str, List[Dict[str, Any]]]:
        """
        查詢特定日期（預設最新一日）借券賣出相關排行
        sort_by:
          - 'sbl_short_bal': 借券賣出餘額排行 (放空存量)
          - 'sbl_short_sell': 當日借券賣出量排行 (當日放空力道)
          - 'sbl_short_utilization_rate': 借券賣出使用率排行
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return "", []

            valid_sort = {
                "sbl_short_bal": "sbl_short_bal DESC",
                "sbl_short_sell": "sbl_short_sell DESC",
                "sbl_short_utilization_rate": "sbl_short_utilization_rate DESC",
            }
            order_clause = valid_sort.get(sort_by, "sbl_short_bal DESC")

            c.execute(f"""
            SELECT * FROM v_stock_sbl_all
            WHERE date = ?
            ORDER BY {order_clause}
            LIMIT ?
            """, (date_str, limit))
            return date_str, [dict(r) for r in c.fetchall()]

    def query_top_sbl_balance(self, date_str: Optional[str] = None, sort_by: str = "sbl_total_bal", limit: int = 20) -> Tuple[str, List[Dict[str, Any]]]:
        """
        查詢特定日期（預設最新一日）借券餘額相關排行
        sort_by:
          - 'sbl_total_bal': 借券總餘額排行
          - 'sbl_total_borrow': 當日借券借入量排行
          - 'sbl_total_market_val': 借券餘額總市值排行
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return "", []

            valid_sort = {
                "sbl_total_bal": "sbl_total_bal DESC",
                "sbl_total_borrow": "sbl_total_borrow DESC",
                "sbl_total_market_val": "sbl_total_market_val DESC",
            }
            order_clause = valid_sort.get(sort_by, "sbl_total_bal DESC")

            c.execute(f"""
            SELECT * FROM v_stock_sbl_all
            WHERE date = ?
            ORDER BY {order_clause}
            LIMIT ?
            """, (date_str, limit))
            return date_str, [dict(r) for r in c.fetchall()]

    def get_market_stats(self) -> Dict[str, Any]:
        """取得資料庫統計摘要"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*), COUNT(DISTINCT date), COUNT(DISTINCT stock_id) FROM daily_sbl_balance")
            bal_count, bal_days, bal_stocks = c.fetchone()

            c.execute("SELECT COUNT(*), COUNT(DISTINCT date), COUNT(DISTINCT stock_id), MIN(date), MAX(date) FROM daily_sbl_short")
            short_count, short_days, short_stocks, min_date, max_date = c.fetchone()

            return {
                "balance_records": bal_count or 0,
                "short_records": short_count or 0,
                "total_records": (bal_count or 0) + (short_count or 0),
                "trading_days": short_days or 0,
                "stocks_count": short_stocks or 0,
                "min_date": min_date,
                "max_date": max_date,
            }
