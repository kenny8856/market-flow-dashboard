"""
Convertible Bond (CB) Database Module
Manages SQLite database for Taiwan Convertible Bonds market data.
Database: db/cb_market.db
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")
DB_PATH = os.path.join(DB_DIR, "cb_market.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get database connection with row factory configured."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database tables and indices."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. 每日可轉債行情與指標表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_cb_quotes (
            date TEXT NOT NULL,
            cb_id TEXT NOT NULL,
            cb_name TEXT,
            underlying_id TEXT,
            underlying_name TEXT,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            reference_price REAL,
            volume_lots INTEGER DEFAULT 0,
            trade_amount INTEGER DEFAULT 0,
            conversion_price REAL,
            underlying_close_price REAL,
            conversion_value REAL,
            premium_rate REAL,
            issue_lots INTEGER,
            outstanding_lots INTEGER,
            listing_date TEXT,
            maturity_date TEXT,
            PRIMARY KEY (date, cb_id)
        )
    """)

    # 2. 可轉債基本資料表 (Master table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cb_basic_info (
            cb_id TEXT PRIMARY KEY,
            cb_name TEXT,
            underlying_id TEXT,
            underlying_name TEXT,
            issue_date TEXT,
            listing_date TEXT,
            maturity_date TEXT,
            issue_amount INTEGER,
            issue_lots INTEGER,
            initial_conversion_price REAL,
            updated_at TEXT
        )
    """)

    # 3. 同步進度表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_progress (
            date TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            record_count INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)

    # 索引建立
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cb_quotes_date ON daily_cb_quotes(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cb_quotes_cb_id ON daily_cb_quotes(cb_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cb_quotes_underlying ON daily_cb_quotes(underlying_id)")

    conn.commit()
    conn.close()


def save_basic_info(records: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Save or update CB basic profiles."""
    if not records:
        return 0

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inserted = 0
    for r in records:
        cursor.execute("""
            INSERT INTO cb_basic_info (
                cb_id, cb_name, underlying_id, underlying_name,
                issue_date, listing_date, maturity_date,
                issue_amount, issue_lots, initial_conversion_price, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cb_id) DO UPDATE SET
                cb_name = excluded.cb_name,
                underlying_id = excluded.underlying_id,
                underlying_name = excluded.underlying_name,
                issue_date = excluded.issue_date,
                listing_date = excluded.listing_date,
                maturity_date = excluded.maturity_date,
                issue_amount = excluded.issue_amount,
                issue_lots = excluded.issue_lots,
                initial_conversion_price = excluded.initial_conversion_price,
                updated_at = excluded.updated_at
        """, (
            r.get("cb_id"),
            r.get("cb_name"),
            r.get("underlying_id"),
            r.get("underlying_name"),
            r.get("issue_date"),
            r.get("listing_date"),
            r.get("maturity_date"),
            r.get("issue_amount"),
            r.get("issue_lots"),
            r.get("initial_conversion_price"),
            now_str,
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted


def save_daily_quotes(date_str: str, quotes: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Save daily quotes and update sync progress."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute("DELETE FROM daily_cb_quotes WHERE date = ?", (date_str,))

        for q in quotes:
            cursor.execute("""
                INSERT INTO daily_cb_quotes (
                    date, cb_id, cb_name, underlying_id, underlying_name,
                    open_price, high_price, low_price, close_price, reference_price,
                    volume_lots, trade_amount, conversion_price, underlying_close_price,
                    conversion_value, premium_rate, issue_lots, outstanding_lots,
                    listing_date, maturity_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                q.get("cb_id"),
                q.get("cb_name"),
                q.get("underlying_id"),
                q.get("underlying_name"),
                q.get("open_price"),
                q.get("high_price"),
                q.get("low_price"),
                q.get("close_price"),
                q.get("reference_price"),
                q.get("volume_lots", 0),
                q.get("trade_amount", 0),
                q.get("conversion_price"),
                q.get("underlying_close_price"),
                q.get("conversion_value"),
                q.get("premium_rate"),
                q.get("issue_lots"),
                q.get("outstanding_lots"),
                q.get("listing_date"),
                q.get("maturity_date"),
            ))

        status = "success" if quotes else "no_data"
        cursor.execute("""
            INSERT INTO sync_progress (date, status, record_count, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                status = excluded.status,
                record_count = excluded.record_count,
                updated_at = excluded.updated_at
        """, (date_str, status, len(quotes), now_str))

        conn.commit()
        return len(quotes)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def mark_no_data_date(date_str: str, db_path: str = DB_PATH) -> None:
    """Record non-trading day (weekend/holiday)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO sync_progress (date, status, record_count, updated_at)
        VALUES (?, 'no_data', 0, ?)
        ON CONFLICT(date) DO UPDATE SET
            status = 'no_data',
            record_count = 0,
            updated_at = excluded.updated_at
    """, (date_str, now_str))
    conn.commit()
    conn.close()


def get_synced_dates(db_path: str = DB_PATH) -> set:
    """Get all dates that have already been synced or checked."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM sync_progress")
    dates = {r[0] for r in cursor.fetchall()}
    conn.close()
    return dates


def get_latest_date(db_path: str = DB_PATH) -> Optional[str]:
    """取得可轉債資料庫最新收錄之交易日"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM daily_cb_quotes")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def query_cb_by_date(date_str: str, sort_by: str = "volume", limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Query CB market data on a specific date."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    sort_clause = "volume_lots DESC, trade_amount DESC"
    if sort_by == "premium":
        sort_clause = "premium_rate ASC"
    elif sort_by == "conv_value":
        sort_clause = "conversion_value DESC"
    elif sort_by == "close":
        sort_clause = "close_price DESC"

    cursor.execute(f"""
        SELECT * FROM daily_cb_quotes
        WHERE date = ?
        ORDER BY {sort_clause}
        LIMIT ?
    """, (date_str, limit))

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def query_cb_history(cb_id: str, limit: int = 30, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Query history of a specific CB."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM daily_cb_quotes
        WHERE cb_id = ?
        ORDER BY date DESC
        LIMIT ?
    """, (cb_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def query_cb_by_stock(stock_id: str, limit: int = 30, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Query CBs associated with a specific underlying stock ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM daily_cb_quotes
        WHERE underlying_id = ?
        ORDER BY date DESC, cb_id ASC
        LIMIT ?
    """, (stock_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
