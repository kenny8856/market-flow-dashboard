import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from .config import DB_DIR

TWSE_DB_PATH = DB_DIR / "twse_market.db"
TPEX_DB_PATH = DB_DIR / "tpex_market.db"

class MarketDatabase:
    """
    上市 (TWSE) 與 上櫃 (TPEx) 獨立市場資料庫管理模組。
    實現嚴格之每日資料冪等性 (By-Date Delete-Then-Insert) 事務控制。
    """

    def __init__(self, market: str = "TWSE"):
        self.market = market.upper()
        self.db_path = TWSE_DB_PATH if self.market == "TWSE" else TPEX_DB_PATH
        self.init_tables()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """初始化資料表結構與索引"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 每日個股行情表 (開高低收量、金額、筆數)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_quotes (
                date TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                change_price REAL,
                volume_shares INTEGER,
                volume_lots INTEGER,
                amount INTEGER,
                transaction_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, stock_id)
            );
            """)

            # 2. 每日三大法人買賣超明細表 (外陸資、投信、自營商自行買賣與避險)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_institutional (
                date TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                foreign_buy INTEGER DEFAULT 0,
                foreign_sell INTEGER DEFAULT 0,
                foreign_net INTEGER DEFAULT 0,
                trust_buy INTEGER DEFAULT 0,
                trust_sell INTEGER DEFAULT 0,
                trust_net INTEGER DEFAULT 0,
                dealer_net INTEGER DEFAULT 0,
                dealer_self_buy INTEGER DEFAULT 0,
                dealer_self_sell INTEGER DEFAULT 0,
                dealer_self_net INTEGER DEFAULT 0,
                dealer_hedge_buy INTEGER DEFAULT 0,
                dealer_hedge_sell INTEGER DEFAULT 0,
                dealer_hedge_net INTEGER DEFAULT 0,
                total_net INTEGER DEFAULT 0,
                foreign_net_lots INTEGER DEFAULT 0,
                trust_net_lots INTEGER DEFAULT 0,
                total_net_lots INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, stock_id)
            );
            """)

            # 3. 每日權證交易明細表 (含標的個股關聯)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_warrants (
                date TEXT NOT NULL,
                warrant_id TEXT NOT NULL,
                warrant_name TEXT NOT NULL,
                trade_amount REAL DEFAULT 0.0,
                trade_volume INTEGER DEFAULT 0,
                trade_lots INTEGER DEFAULT 0,
                underlying_stock_id TEXT,
                underlying_stock_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, warrant_id)
            );
            """)

            # 4. 同步進度與狀態追蹤表 (用於斷點續傳)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_progress (
                date TEXT PRIMARY KEY,
                quotes_synced INTEGER DEFAULT 0,
                inst_synced INTEGER DEFAULT 0,
                quotes_count INTEGER DEFAULT 0,
                inst_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 建立常用查詢索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_stock_date ON daily_quotes(stock_id, date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_date ON daily_quotes(date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_stock_date ON daily_institutional(stock_id, date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_date ON daily_institutional(date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warrants_underlying ON daily_warrants(underlying_stock_id, date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warrants_date ON daily_warrants(date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warrants_id ON daily_warrants(warrant_id);")
            conn.commit()

    def save_daily_data(self, date_str: str, quotes: List[Dict[str, Any]], institutional: List[Dict[str, Any]]):
        """
        原子性保存特定交易日資料。
        嚴格執行「同日多次執行先刪除舊資料再寫入」機制，避免任何重複紀錄。
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. 先清除該日期之既有紀錄 (冪等性保證)
            cursor.execute("DELETE FROM daily_quotes WHERE date = ?;", (date_str,))
            cursor.execute("DELETE FROM daily_institutional WHERE date = ?;", (date_str,))

            # 2. 寫入行情資料
            if quotes:
                cursor.executemany("""
                INSERT INTO daily_quotes (
                    date, stock_id, stock_name, open_price, high_price, low_price, close_price,
                    change_price, volume_shares, volume_lots, amount, transaction_count, created_at
                ) VALUES (
                    :date, :stock_id, :stock_name, :open_price, :high_price, :low_price, :close_price,
                    :change_price, :volume_shares, :volume_lots, :amount, :transaction_count, :created_at
                );
                """, [dict(q, created_at=now) for q in quotes])

            # 3. 寫入法人資料
            if institutional:
                cursor.executemany("""
                INSERT INTO daily_institutional (
                    date, stock_id, stock_name, foreign_buy, foreign_sell, foreign_net,
                    trust_buy, trust_sell, trust_net, dealer_net, dealer_self_buy, dealer_self_sell,
                    dealer_self_net, dealer_hedge_buy, dealer_hedge_sell, dealer_hedge_net,
                    total_net, foreign_net_lots, trust_net_lots, total_net_lots, created_at
                ) VALUES (
                    :date, :stock_id, :stock_name, :foreign_buy, :foreign_sell, :foreign_net,
                    :trust_buy, :trust_sell, :trust_net, :dealer_net, :dealer_self_buy, :dealer_self_sell,
                    :dealer_self_net, :dealer_hedge_buy, :dealer_hedge_sell, :dealer_hedge_net,
                    :total_net, :foreign_net_lots, :trust_net_lots, :total_net_lots, :created_at
                );
                """, [dict(ins, created_at=now) for ins in institutional])

            # 4. 更新進度表
            cursor.execute("""
            INSERT INTO sync_progress (date, quotes_synced, inst_synced, quotes_count, inst_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                quotes_synced = excluded.quotes_synced,
                inst_synced = excluded.inst_synced,
                quotes_count = excluded.quotes_count,
                inst_count = excluded.inst_count,
                updated_at = excluded.updated_at;
            """, (date_str, 1 if quotes else 0, 1 if institutional else 0, len(quotes), len(institutional), now))

            conn.commit()

    def save_daily_warrants(self, date_str: str, warrants: List[Dict[str, Any]]):
        """
        原子性保存特定交易日之權證交易資料（含標的個股關聯）。
        嚴格執行 Delete-Then-Insert 先刪後存。
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. 先清除該日期之既有權證紀錄 (冪等性)
            cursor.execute("DELETE FROM daily_warrants WHERE date = ?;", (date_str,))

            # 2. 寫入權證資料
            if warrants:
                cursor.executemany("""
                INSERT INTO daily_warrants (
                    date, warrant_id, warrant_name, trade_amount, trade_volume, trade_lots,
                    underlying_stock_id, underlying_stock_name, created_at
                ) VALUES (
                    :date, :warrant_id, :warrant_name, :trade_amount, :trade_volume, :trade_lots,
                    :underlying_stock_id, :underlying_stock_name, :created_at
                );
                """, [dict(w, created_at=now) for w in warrants])

            conn.commit()

    def append_daily_warrants(self, warrants: List[Dict[str, Any]]) -> int:
        """
        冪等性增量寫入權證交易資料 (使用 INSERT OR REPLACE，不刪除當日其他權證)
        """
        if not warrants:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.executemany("""
            INSERT OR REPLACE INTO daily_warrants (
                date, warrant_id, warrant_name, trade_amount, trade_volume, trade_lots,
                underlying_stock_id, underlying_stock_name, created_at
            ) VALUES (
                :date, :warrant_id, :warrant_name, :trade_amount, :trade_volume, :trade_lots,
                :underlying_stock_id, :underlying_stock_name, :created_at
            );
            """, [dict(w, created_at=w.get('created_at', now)) for w in warrants])
            conn.commit()
            return len(warrants)

    def get_synced_dates(self) -> set:
        """取得已完整同步之日期集合"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT date FROM sync_progress WHERE quotes_synced = 1 OR quotes_count > 0;")
            return {row[0] for row in cursor.fetchall()}

    def get_latest_date(self) -> Optional[str]:
        """取得資料庫中最新收錄之交易日期 (YYYY-MM-DD)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM daily_quotes WHERE volume_shares > 0;")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def get_market_stats(self) -> Dict[str, Any]:
        """取得市場資料庫統計資訊"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            quotes_total = cursor.execute("SELECT COUNT(*) FROM daily_quotes;").fetchone()[0]
            inst_total = cursor.execute("SELECT COUNT(*) FROM daily_institutional;").fetchone()[0]
            warrants_total = cursor.execute("SELECT COUNT(*) FROM daily_warrants;").fetchone()[0]
            unique_stocks = cursor.execute("SELECT COUNT(DISTINCT stock_id) FROM daily_quotes;").fetchone()[0]
            date_range = cursor.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM daily_quotes;").fetchone()
            return {
                "market": self.market,
                "db_path": str(self.db_path),
                "quotes_count": quotes_total,
                "institutional_count": inst_total,
                "warrants_count": warrants_total,
                "stocks_count": unique_stocks,
                "start_date": date_range[0],
                "end_date": date_range[1],
                "trading_days": date_range[2] if date_range else 0
            }
