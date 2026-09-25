import os
import sqlite3
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db", "taifex_large_trader.db"))

class TaifexLargeTraderDB:
    """期交所大額交易人未沖銷部位結構資料庫管理器"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化資料庫表格與索引"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS futures_large_traders (
            date TEXT NOT NULL,
            contract_code TEXT NOT NULL,
            contract_name TEXT NOT NULL,
            contract_type TEXT NOT NULL,
            expiry_month TEXT,
            buy_top5 INTEGER DEFAULT 0,
            buy_top5_spec INTEGER DEFAULT 0,
            buy_top10 INTEGER DEFAULT 0,
            buy_top10_spec INTEGER DEFAULT 0,
            sell_top5 INTEGER DEFAULT 0,
            sell_top5_spec INTEGER DEFAULT 0,
            sell_top10 INTEGER DEFAULT 0,
            sell_top10_spec INTEGER DEFAULT 0,
            market_oi INTEGER DEFAULT 0,
            net_top5 INTEGER DEFAULT 0,
            net_top5_spec INTEGER DEFAULT 0,
            net_top10 INTEGER DEFAULT 0,
            net_top10_spec INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, contract_code, contract_type)
        );
        """
        create_index_date = """
        CREATE INDEX IF NOT EXISTS idx_large_trader_date 
        ON futures_large_traders(date);
        """
        create_index_contract = """
        CREATE INDEX IF NOT EXISTS idx_large_trader_contract 
        ON futures_large_traders(contract_code, contract_type);
        """
        create_index_name = """
        CREATE INDEX IF NOT EXISTS idx_large_trader_name 
        ON futures_large_traders(contract_name);
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            cursor.execute(create_index_date)
            cursor.execute(create_index_contract)
            cursor.execute(create_index_name)
            conn.commit()

    def insert_records(self, records: List[Dict[str, Any]]) -> int:
        """
        批次寫入或更新紀錄 (支援冪等寫入 INSERT OR REPLACE)
        """
        if not records:
            return 0

        insert_sql = """
        INSERT OR REPLACE INTO futures_large_traders (
            date, contract_code, contract_name, contract_type, expiry_month,
            buy_top5, buy_top5_spec, buy_top10, buy_top10_spec,
            sell_top5, sell_top5_spec, sell_top10, sell_top10_spec,
            market_oi, net_top5, net_top5_spec, net_top10, net_top10_spec,
            updated_at
        ) VALUES (
            :date, :contract_code, :contract_name, :contract_type, :expiry_month,
            :buy_top5, :buy_top5_spec, :buy_top10, :buy_top10_spec,
            :sell_top5, :sell_top5_spec, :sell_top10, :sell_top10_spec,
            :market_oi, :net_top5, :net_top5_spec, :net_top10, :net_top10_spec,
            CURRENT_TIMESTAMP
        );
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(insert_sql, records)
            conn.commit()
            return cursor.rowcount

    def get_latest_date(self) -> Optional[str]:
        """取得資料庫中最新交易日期"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM futures_large_traders")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def get_earliest_date(self) -> Optional[str]:
        """取得資料庫中最舊交易日期"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(date) FROM futures_large_traders")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def get_date_count(self) -> int:
        """取得資料庫中獨立交易日總數"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT date) FROM futures_large_traders")
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_records(
        self,
        contract_code: Optional[str] = None,
        contract_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        order_desc: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查詢特定條件之大額交易人歷史紀錄
        """
        conditions = []
        params = {}

        if contract_code:
            conditions.append("contract_code = :contract_code")
            params["contract_code"] = contract_code

        if contract_type:
            conditions.append("contract_type = :contract_type")
            params["contract_type"] = contract_type

        if start_date:
            conditions.append("date >= :start_date")
            params["start_date"] = start_date

        if end_date:
            conditions.append("date <= :end_date")
            params["end_date"] = end_date

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_direction = "DESC" if order_desc else "ASC"
        limit_clause = f"LIMIT {int(limit)}" if limit else ""

        sql = f"""
        SELECT * FROM futures_large_traders
        {where_clause}
        ORDER BY date {order_direction}, contract_code ASC, 
                 CASE contract_type 
                     WHEN '當月' THEN 1 
                     WHEN '遠月' THEN 2 
                     WHEN '所有契約' THEN 3 
                     WHEN '週契約' THEN 4 
                     ELSE 5 
                 END ASC
        {limit_clause}
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def search_contracts(self, keyword: str) -> List[Dict[str, Any]]:
        """依代碼或中文名稱搜尋商品"""
        kw = f"%{keyword.strip()}%"
        sql = """
        SELECT contract_code, contract_name, COUNT(DISTINCT date) as days, MAX(date) as latest_date
        FROM futures_large_traders
        WHERE contract_code LIKE ? OR contract_name LIKE ?
        GROUP BY contract_code, contract_name
        ORDER BY days DESC, contract_code ASC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (kw, kw))
            return [dict(r) for r in cursor.fetchall()]

    def get_all_contracts(self) -> List[Dict[str, Any]]:
        """取得資料庫中所有商品代碼與名稱"""
        sql = """
        SELECT contract_code, contract_name, COUNT(DISTINCT date) as days, MAX(date) as latest_date
        FROM futures_large_traders
        GROUP BY contract_code, contract_name
        ORDER BY days DESC, contract_code ASC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            return [dict(r) for r in cursor.fetchall()]

