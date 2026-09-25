import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from .config import DB_PATH

class DatabaseManager:
    """
    SQLite 資料庫管理模組，負責建立資料表結構、批次寫入、增量更新及地緣關聯查詢。
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DB_PATH)
        self.init_tables()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """初始化資料表結構"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 個股公司資料表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                stock_id TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                market_type TEXT NOT NULL,
                industry TEXT,
                address TEXT,
                city TEXT,
                district TEXT,
                park TEXT,
                tel TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. 券商分點基本資料表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS broker_branches (
                broker_id TEXT PRIMARY KEY,
                broker_name TEXT NOT NULL,
                address TEXT,
                city TEXT,
                district TEXT,
                park TEXT,
                tel TEXT,
                is_headquarter INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. 個股與地緣券商關聯表 (核心查詢表)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_geo_brokers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                broker_id TEXT NOT NULL,
                broker_name TEXT NOT NULL,
                geo_level INTEGER NOT NULL,
                match_reason TEXT NOT NULL,
                company_address TEXT,
                broker_address TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_id, broker_id)
            );
            """)

            # 4. 同步更新日誌表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stocks_count INTEGER,
                brokers_count INTEGER,
                geo_relations_count INTEGER,
                status TEXT,
                duration_sec REAL
            );
            """)

            # 建立索引以加速查詢
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_stock_id ON stock_geo_brokers(stock_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_level ON stock_geo_brokers(geo_level);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_broker_id ON stock_geo_brokers(broker_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_city ON stocks(city, district);")
            conn.commit()

    def upsert_stocks(self, stocks: List[Dict[str, Any]]):
        """批次新增或更新個股資料"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.executemany("""
            INSERT INTO stocks (stock_id, stock_name, market_type, industry, address, city, district, park, tel, updated_at)
            VALUES (:stock_id, :stock_name, :market_type, :industry, :address, :city, :district, :park, :tel, ?)
            ON CONFLICT(stock_id) DO UPDATE SET
                stock_name = excluded.stock_name,
                market_type = excluded.market_type,
                industry = excluded.industry,
                address = excluded.address,
                city = excluded.city,
                district = excluded.district,
                park = excluded.park,
                tel = excluded.tel,
                updated_at = ?;
            """, [(s["stock_id"], s["stock_name"], s["market_type"], s["industry"], s["address"],
                   s.get("city", ""), s.get("district", ""), s.get("park", ""), s.get("tel", ""), now, now) for s in stocks])
            conn.commit()

    def upsert_brokers(self, brokers: List[Dict[str, Any]]):
        """批次新增或更新券商分點資料"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.executemany("""
            INSERT INTO broker_branches (broker_id, broker_name, address, city, district, park, tel, is_headquarter, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(broker_id) DO UPDATE SET
                broker_name = excluded.broker_name,
                address = excluded.address,
                city = excluded.city,
                district = excluded.district,
                park = excluded.park,
                tel = excluded.tel,
                is_headquarter = excluded.is_headquarter,
                updated_at = ?;
            """, [(b["broker_id"], b["broker_name"], b["address"], b.get("city", ""),
                   b.get("district", ""), b.get("park", ""), b.get("tel", ""), b.get("is_headquarter", 0), now, now) for b in brokers])
            conn.commit()

    def rebuild_geo_relations(self, relations: List[Dict[str, Any]]):
        """重構地緣券商對照表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stock_geo_brokers;")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.executemany("""
            INSERT INTO stock_geo_brokers (stock_id, stock_name, broker_id, broker_name, geo_level, match_reason, company_address, broker_address, updated_at)
            VALUES (:stock_id, :stock_name, :broker_id, :broker_name, :geo_level, :match_reason, :company_address, :broker_address, ?)
            ON CONFLICT(stock_id, broker_id) DO UPDATE SET
                geo_level = excluded.geo_level,
                match_reason = excluded.match_reason,
                company_address = excluded.company_address,
                broker_address = excluded.broker_address,
                updated_at = ?;
            """, [(r["stock_id"], r["stock_name"], r["broker_id"], r["broker_name"],
                   r["geo_level"], r["match_reason"], r["company_address"], r["broker_address"], now, now) for r in relations])
            conn.commit()

    def record_sync_log(self, stocks_count: int, brokers_count: int, geo_count: int, status: str, duration_sec: float):
        """寫入同步作業紀錄"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO sync_logs (stocks_count, brokers_count, geo_relations_count, status, duration_sec)
            VALUES (?, ?, ?, ?, ?);
            """, (stocks_count, brokers_count, geo_count, status, duration_sec))
            conn.commit()

    def get_stock_geo_brokers(self, stock_id: str, level_limit: int = 1) -> List[Dict[str, Any]]:
        """查詢特定個股的地緣券商清單"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT stock_id, stock_name, broker_id, broker_name, geo_level, match_reason, company_address, broker_address
            FROM stock_geo_brokers
            WHERE stock_id = ? AND geo_level <= ?
            ORDER BY geo_level ASC, broker_id ASC;
            """, (stock_id, level_limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_stock_info(self, stock_id: str) -> Optional[Dict[str, Any]]:
        """查詢個股基本資訊"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stocks WHERE stock_id = ?;", (stock_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_summary_stats(self) -> Dict[str, Any]:
        """取得資料庫現有統計摘要"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            stocks_cnt = cursor.execute("SELECT COUNT(*) FROM stocks;").fetchone()[0]
            brokers_cnt = cursor.execute("SELECT COUNT(*) FROM broker_branches;").fetchone()[0]
            geo_cnt = cursor.execute("SELECT COUNT(*) FROM stock_geo_brokers;").fetchone()[0]
            core_geo_cnt = cursor.execute("SELECT COUNT(*) FROM stock_geo_brokers WHERE geo_level = 1;").fetchone()[0]
            last_sync = cursor.execute("SELECT sync_time FROM sync_logs ORDER BY id DESC LIMIT 1;").fetchone()
            return {
                "stocks_count": stocks_cnt,
                "brokers_count": brokers_cnt,
                "geo_relations_count": geo_cnt,
                "core_geo_relations_count": core_geo_cnt,
                "last_sync_time": last_sync[0] if last_sync else "尚未執行"
            }
