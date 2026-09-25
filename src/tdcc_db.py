"""
SQLite Database Manager for TDCC Equity Distribution (集保戶股權分散表資料庫)
Stores weekly distribution tiers and computes big/retail shareholder concentration.
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "stock_tdcc.db")

class TdccDB:
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
            c.execute("""
                CREATE TABLE IF NOT EXISTS tdcc_distribution (
                    date TEXT,
                    stock_id TEXT,
                    holding_level INTEGER,
                    shareholders INTEGER,
                    shares INTEGER,
                    share_percent REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, stock_id, holding_level)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_tdcc_stock_date ON tdcc_distribution (stock_id, date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tdcc_date ON tdcc_distribution (date)")
            conn.commit()

    def insert_records(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._get_conn() as conn:
            c = conn.cursor()
            # 依 (date, stock_id) 分組刪除舊值防重
            date_stocks = set((r["date"], r["stock_id"]) for r in records)
            for d, sid in date_stocks:
                c.execute("DELETE FROM tdcc_distribution WHERE date = ? AND stock_id = ?", (d, sid))

            c.executemany("""
                INSERT INTO tdcc_distribution
                (date, stock_id, holding_level, shareholders, shares, share_percent)
                VALUES (:date, :stock_id, :holding_level, :shareholders, :shares, :share_percent)
            """, records)
            conn.commit()
            return len(records)

    def get_latest_date(self) -> Optional[str]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(date) FROM tdcc_distribution")
            r = c.fetchone()
            return r[0] if r and r[0] else None

    def get_date_count(self) -> int:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(DISTINCT date) FROM tdcc_distribution")
            r = c.fetchone()
            return r[0] if r else 0

    def get_stock_count(self, date_str: Optional[str] = None) -> int:
        with self._get_conn() as conn:
            c = conn.cursor()
            if date_str:
                c.execute("SELECT COUNT(DISTINCT stock_id) FROM tdcc_distribution WHERE date = ?", (date_str,))
            else:
                c.execute("SELECT COUNT(DISTINCT stock_id) FROM tdcc_distribution")
            r = c.fetchone()
            return r[0] if r else 0

    def get_stock_summary(self, stock_id: str, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        計算單檔個股在特定日期的股權集中度指標：
        - 千張大戶比例 (持股級距 15: >1000張)
        - 400張以上大戶比例 (持股級距 12~15)
        - 散戶比例 (持股級距 1~5: <20張 或 1~3: <10張)
        - 總股東人數
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            if not date_str:
                date_str = self.get_latest_date()
            if not date_str:
                return None

            c.execute("""
                SELECT holding_level, shareholders, shares, share_percent
                FROM tdcc_distribution
                WHERE stock_id = ? AND date = ?
                ORDER BY holding_level ASC
            """, (stock_id, date_str))
            rows = c.fetchall()
            if not rows:
                return None

            total_holders = 0
            total_shares = 0
            pct_over_1000 = 0.0
            pct_over_400 = 0.0
            pct_retail_under_10 = 0.0
            pct_retail_under_50 = 0.0

            for r in rows:
                lvl = int(r["holding_level"])
                pct = float(r["share_percent"])
                holders = int(r["shareholders"])
                shares = int(r["shares"])

                # 排除 16 (差異調整) 與 17 (合計)
                if lvl <= 15:
                    total_holders += holders
                    total_shares += shares

                if lvl == 15:
                    pct_over_1000 += pct
                if lvl >= 12 and lvl <= 15:
                    pct_over_400 += pct
                if lvl <= 3: # 1~999股, 1~5張, 5~10張
                    pct_retail_under_10 += pct
                if lvl <= 8: # 50張以下
                    pct_retail_under_50 += pct

            return {
                "stock_id": stock_id,
                "date": date_str,
                "total_shareholders": total_holders,
                "total_shares": total_shares,
                "pct_over_1000": round(pct_over_1000, 2),
                "pct_over_400": round(pct_over_400, 2),
                "pct_retail_under_10": round(pct_retail_under_10, 2),
                "pct_retail_under_50": round(pct_retail_under_50, 2),
            }

    def get_stock_history(self, stock_id: str, limit_weeks: int = 12) -> List[Dict[str, Any]]:
        """查詢單檔個股近期多週的大戶與散戶持股趨勢"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT DISTINCT date FROM tdcc_distribution
                WHERE stock_id = ? ORDER BY date DESC LIMIT ?
            """, (stock_id, limit_weeks))
            dates = [r[0] for r in c.fetchall()]

            results = []
            for d in reversed(dates):
                s = self.get_stock_summary(stock_id, d)
                if s:
                    results.append(s)
            return results
