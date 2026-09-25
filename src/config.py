import os
from pathlib import Path

# 專案基礎路徑
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "stock_geography.db"

# 確保 DB 目錄存在
os.makedirs(DB_DIR, exist_ok=True)

# 官方 API 端點
TWSE_API_URLS = {
    # 上市公司基本資料 (包含中文地址、產業、成立/上市日)
    "listed_companies": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
    # 證券商分公司基本資料 (816+ 家分點完整中文名稱、代號、地址、電話)
    "broker_branches": "https://openapi.twse.com.tw/v1/opendata/OpenData_BRK02",
    # 證券商總公司基本資料
    "broker_headquarters": "https://openapi.twse.com.tw/v1/opendata/t187ap18",
}

TPEX_API_URLS = {
    # 上櫃公司基本資料
    "otc_companies": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
}

# 臺灣特殊科技/產業園區與核心行政區映射表（別名只使用園區專屬特徵詞，不使用常見普遍街路名）
PARK_DISTRICT_MAP = {
    "新竹科學園區": {
        "city": "新竹市",
        "district": "東區",
        "alias": ["新竹科學園區", "科學工業園區", "竹科", "力行路", "篤行路", "研發路", "創新路", "展業路", "園區一路", "園區二路"]
    },
    "竹南科學園區": {
        "city": "苗栗縣",
        "district": "竹南鎮",
        "alias": ["竹南科學園區", "竹南園區", "科研路"]
    },
    "中部科學園區": {
        "city": "台中市",
        "district": "西屯區",
        "alias": ["中部科學園區", "中科", "中科路", "科園路"]
    },
    "南部科學園區": {
        "city": "台南市",
        "district": "新市區",
        "alias": ["南部科學園區", "南科", "南科三路", "南科七路", "善化區"]
    },
    "內湖科技園區": {
        "city": "台北市",
        "district": "內湖區",
        "alias": ["內湖科技園區", "內科", "瑞光路", "基湖路", "洲子街", "港墘路"]
    },
    "南港軟體園區": {
        "city": "台北市",
        "district": "南港區",
        "alias": ["南港軟體園區", "南軟", "園區街", "經貿二路"]
    },
    "土城工業區": {
        "city": "新北市",
        "district": "土城區",
        "alias": ["土城工業區"]
    },
    "華亞科技園區": {
        "city": "桃園市",
        "district": "龜山區",
        "alias": ["華亞科技園區", "華亞園區", "科技二路"]
    },
    "楠梓科技產業園區": {
        "city": "高雄市",
        "district": "楠梓區",
        "alias": ["楠梓科技產業園區", "楠梓加工出口區", "加昌路"]
    },
}

# 請求標頭
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
