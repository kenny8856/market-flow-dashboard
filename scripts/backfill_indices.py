import sys
import os
import requests
import datetime

from src.market_db import MarketDatabase

def fetch_and_insert_index(market_db: MarketDatabase, data_id: str, stock_name: str, start_date: str):
    print(f"Fetching {data_id} ({stock_name}) from {start_date} to now...")
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": data_id,
        "start_date": start_date
    }
    resp = requests.get(url, params=params).json()
    if resp.get("msg") != "success" or not resp.get("data"):
        print(f"Failed to fetch {data_id} data.")
        return

    data = resp["data"]
    print(f"Fetched {len(data)} records for {data_id}. Inserting to DB...")
    
    with market_db.get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        insert_sql = """
        INSERT INTO daily_quotes (
            date, stock_id, stock_name, open_price, high_price, low_price, close_price,
            change_price, volume_shares, volume_lots, amount, transaction_count, created_at
        ) VALUES (
            :date, :stock_id, :stock_name, :open_price, :high_price, :low_price, :close_price,
            :change_price, :volume_shares, :volume_lots, :amount, :transaction_count, :created_at
        ) ON CONFLICT(date, stock_id) DO UPDATE SET
            open_price=excluded.open_price, high_price=excluded.high_price,
            low_price=excluded.low_price, close_price=excluded.close_price,
            change_price=excluded.change_price, volume_shares=excluded.volume_shares,
            volume_lots=excluded.volume_lots, amount=excluded.amount,
            transaction_count=excluded.transaction_count, created_at=excluded.created_at;
        """
        
        count = 0
        for r in data:
            date_str = r.get("date")
            vol_shares = r.get("Trading_Volume", 0)
            cursor.execute(insert_sql, {
                "date": date_str,
                "stock_id": data_id,
                "stock_name": stock_name,
                "open_price": r.get("open", 0.0),
                "high_price": r.get("max", 0.0),
                "low_price": r.get("min", 0.0),
                "close_price": r.get("close", 0.0),
                "change_price": r.get("spread", 0.0),
                "volume_shares": vol_shares,
                "volume_lots": vol_shares // 1000,
                "amount": r.get("Trading_money", 0),
                "transaction_count": r.get("Trading_turnover", 0),
                "created_at": now
            })
            count += 1
        conn.commit()
    print(f"Done inserting {count} records for {data_id}.")

if __name__ == "__main__":
    twse_db = MarketDatabase(market="TWSE")
    tpex_db = MarketDatabase(market="TPEx")
    
    fetch_and_insert_index(twse_db, "TAIEX", "加權指數", "2020-01-01")
    fetch_and_insert_index(tpex_db, "TPEx", "櫃買指數", "2020-01-01")
