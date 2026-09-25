import yfinance as yf
import pandas as pd
import requests

def get_taiex_yfinance(start_date="2020-01-01", end_date=None):
    """
    使用 Yahoo Finance 取得台灣加權指數 (^TWII)
    """
    print("正在從 Yahoo Finance 下載加權指數資料...")
    # 若 end_date 為 None，預設會抓到最新一個交易日
    df = yf.download("^TWII", start=start_date, end=end_date)
    
    # 整理欄位
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df.columns = ['開盤價', '最高價', '最低價', '收盤價', '成交量']
    return df

def get_index_finmind(index_id, start_date="2020-01-01"):
    """
    使用 FinMind 取得指數資料
    加權指數代碼: '001'
    櫃買指數代碼: '101'
    """
    print(f"正在從 FinMind 下載指數 {index_id} 資料...")
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": index_id,
        "start_date": start_date,
        # 如果你有 FinMind token，可以加在這裡提高呼叫限制
        # "token": "YOUR_TOKEN"
    }
    
    response = requests.get(url, params=parameter)
    data = response.json()
    
    if data['msg'] == 'success':
        df = pd.DataFrame(data['data'])
        # 將日期設為 Index 並轉換型態
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 整理欄位 (保留高開低收與成交量)
        df = df[['open', 'max', 'min', 'close', 'Trading_Volume']]
        df.columns = ['開盤價', '最高價', '最低價', '收盤價', '成交量']
        return df
    else:
        print(f"下載失敗: {data['msg']}")
        return pd.DataFrame()

if __name__ == "__main__":
    start = "2020-01-01"
    
    # 1. 取得加權指數 (使用 Yahoo Finance)
    # yfinance 對於加權指數支援很好，速度快且無限制
    try:
        taiex_df = get_taiex_yfinance(start_date=start)
        print("\n=== 台灣加權指數 (TAIEX) ===")
        print(taiex_df.tail())
        taiex_df.to_csv("TAIEX_2020_to_now.csv", encoding="utf_8_sig")
        print("已儲存至 TAIEX_2020_to_now.csv")
    except Exception as e:
        print(f"加權指數下載失敗: {e}")

    # 2. 取得櫃買指數 (使用 FinMind)
    # Yahoo Finance 比較容易漏櫃買指數，建議用台灣本土的 FinMind API
    try:
        tpex_df = get_index_finmind("101", start_date=start)
        print("\n=== 台灣櫃買指數 (TPEX) ===")
        print(tpex_df.tail())
        tpex_df.to_csv("TPEX_2020_to_now.csv", encoding="utf_8_sig")
        print("已儲存至 TPEX_2020_to_now.csv")
    except Exception as e:
        print(f"櫃買指數下載失敗: {e}")
