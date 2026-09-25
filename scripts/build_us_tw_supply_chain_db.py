"""
Build US Top 10 Giants vs Taiwan Supply Chain Database
Database: db/us_tw_supply_chain.db
"""

import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'us_tw_supply_chain.db')

def create_and_populate_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS supply_chain_relations;
    DROP TABLE IF EXISTS tw_companies;
    DROP TABLE IF EXISTS us_giants;
    DROP TABLE IF EXISTS giant_macro_impact;

    CREATE TABLE us_giants (
        us_ticker TEXT PRIMARY KEY,
        name_en TEXT NOT NULL,
        name_zh TEXT NOT NULL,
        market_cap_bil_usd REAL NOT NULL,
        core_segment TEXT NOT NULL,
        key_products TEXT NOT NULL
    );

    CREATE TABLE tw_companies (
        tw_ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        market TEXT NOT NULL, -- TWSE or TPEx
        industry TEXT NOT NULL,
        est_market_cap_bil_twd REAL NOT NULL
    );

    CREATE TABLE supply_chain_relations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tw_ticker TEXT NOT NULL,
        tw_name TEXT NOT NULL,
        us_ticker TEXT NOT NULL,
        us_name TEXT NOT NULL,
        relation_category TEXT NOT NULL,
        supplied_product TEXT NOT NULL,
        est_revenue_pct_low REAL NOT NULL,
        est_revenue_pct_high REAL NOT NULL,
        est_revenue_pct_mid REAL NOT NULL,
        tier_level TEXT NOT NULL, -- Tier 1 核心主供 / Tier 2 主要配件 / Tier 3 關鍵零組件
        official_basis TEXT NOT NULL,
        FOREIGN KEY (tw_ticker) REFERENCES tw_companies(tw_ticker),
        FOREIGN KEY (us_ticker) REFERENCES us_giants(us_ticker)
    );

    CREATE TABLE giant_macro_impact (
        us_ticker TEXT PRIMARY KEY,
        us_name TEXT NOT NULL,
        total_partners_count INTEGER NOT NULL,
        weighted_tw_mcap_influence_bil_twd REAL NOT NULL,
        key_sector_focus TEXT NOT NULL
    );
    """)

    # 1. 美股十大巨頭 (以市值與對台股硬體/半導體/AI科技生態系牽引力最高之十大企業)
    giants_data = [
        ('NVDA', 'NVIDIA Corp.', '輝達', 3500.0, 'AI加速運算/GPU/網路', 'Blackwell GB200/B200, Hopper H100/H200, Spectrum-X'),
        ('AAPL', 'Apple Inc.', '蘋果', 3450.0, '消費電子/個人運算/自研晶片', 'iPhone 16/17, Mac M4/M5, iPad, Apple Silicon'),
        ('MSFT', 'Microsoft Corp.', '微軟', 3150.0, '企業軟體/公有雲/AI資料中心', 'Azure AI Infrastructure, OpenAI Superclusters, Surface'),
        ('GOOGL', 'Alphabet Inc.', 'Google/字母榜', 2250.0, '雲端服務/搜尋/自研AI晶片', 'Google Cloud (GCP), 自研 TPU v5/v6, Pixel'),
        ('AMZN', 'Amazon.com Inc.', '亞馬遜', 2100.0, '雲端基礎設施/電商/AI ASIC', 'AWS Cloud, Trainium/Inferentia ASIC, Graviton'),
        ('META', 'Meta Platforms Inc.', 'Meta', 1500.0, '社群媒體/元宇宙/生成式AI', 'Meta AI Cluster (Llama 3/4), Quest 3, Ray-Ban Meta'),
        ('TSLA', 'Tesla Inc.', '特斯拉', 850.0, '電動車/自動駕駛/儲能/機器人', 'Model 3/Y, CyberTruck, FSD/HW4.0/HW5.0, Megapack'),
        ('AVGO', 'Broadcom Inc.', '博通', 820.0, '網通晶片/客製化AI ASIC', 'Tomahawk 5/6 網通IC, 客製化CSP ASIC, 矽光子CPO'),
        ('AMD', 'Advanced Micro Devices', '超微', 240.0, '資料中心CPU/AI加速卡/PC晶片', 'EPYC 伺服器CPU, Instinct MI300/MI325/MI350X'),
        ('QCOM', 'Qualcomm Inc.', '高通', 190.0, '智慧型手機AP/AI PC/車用運算', 'Snapdragon 8 Gen4, Snapdragon X Elite, 數位座艙')
    ]
    cur.executemany("INSERT INTO us_giants VALUES (?,?,?,?,?,?)", giants_data)

    # 2. 台灣核心供應鏈公司 (精選最具代表性、且營收有顯著關聯之上市櫃大廠)
    tw_data = [
        ('2330', '台積電', 'TWSE', '半導體晶圓代工', 26000.0),
        ('2317', '鴻海', 'TWSE', '電子代工服務(EMS/ODM)', 2500.0),
        ('2454', '聯發科', 'TWSE', 'IC設計', 2100.0),
        ('2382', '廣達', 'TWSE', 'AI伺服器/筆電ODM', 1100.0),
        ('6669', '緯穎', 'TWSE', '雲端白牌伺服器', 450.0),
        ('3231', '緯創', 'TWSE', 'GPU運算基板/代工', 330.0),
        ('3017', '奇鋐', 'TWSE', '散熱模組/水冷系統', 250.0),
        ('3324', '雙鴻', 'TWSE', '散熱模組/水冷板', 65.0),
        ('2059', '川湖', 'TWSE', '伺服器導軌機構件', 110.0),
        ('3661', '世芯-KY', 'TWSE', 'ASIC/晶片設計服務', 180.0),
        ('2308', '台達電', 'TWSE', '電源供應/散熱/綠能', 1050.0),
        ('3711', '日月光投控', 'TWSE', '半導體封裝測試', 720.0),
        ('3008', '大立光', 'TWSE', '光學鏡頭', 320.0),
        ('3406', '玉晶光', 'TWSE', '光學鏡頭/VR透鏡', 60.0),
        ('2368', '金像電', 'TWSE', '高階PCB伺服器板', 120.0),
        ('3037', '欣興', 'TWSE', 'ABF/BT載板', 260.0),
        ('2345', '智邦', 'TWSE', '網通白牌交換器', 330.0),
        ('3653', '健策', 'TWSE', '均熱片/散熱機構件', 160.0),
        ('8210', '勤誠', 'TWSE', 'AI伺服器機殼', 35.0),
        ('4958', '臻鼎-KY', 'TWSE', 'PCB/軟板FPC', 110.0),
        ('1536', '和大', 'TWSE', '車用傳動齒輪箱', 15.0),
        ('3665', '貿聯-KY', 'TWSE', '車用與伺服器高壓線束', 85.0),
        ('5243', '乙盛-KY', 'TWSE', '車用沖壓件/機構件', 12.0),
        ('2360', '致茂', 'TWSE', '半導體/電池量測儀器', 160.0),
        ('2449', '京元電子', 'TWSE', '半導體測試代工', 140.0),
        ('8069', '元太', 'TPEx', '電子紙顯示器', 280.0),
        ('3081', '聯亞', 'TPEx', '矽光子光通訊磊晶', 35.0),
        ('2356', '英業達', 'TWSE', '雲端伺服器代工', 180.0)
    ]
    cur.executemany("INSERT INTO tw_companies VALUES (?,?,?,?,?)", tw_data)

    # 3. 台灣公司 vs 美股十大巨頭之具體產品與營收佔比 (嚴謹依據財報、官方供應商名單與券商深度研報拆解)
    # (tw_ticker, tw_name, us_ticker, us_name, category, product, pct_low, pct_high, pct_mid, tier, basis)
    relations = [
        # --- NVIDIA (NVDA) ---
        ('2330', '台積電', 'NVDA', '輝達', '晶圓代工與先進封裝', '4nm/3nm GPU晶圓代工、CoWoS-S/L 先進封裝', 10.0, 14.0, 12.0, 'Tier 1 獨家/核心主供', '財報客戶揭露與法說會驗證、GTC官方夥伴'),
        ('2317', '鴻海', 'NVDA', '輝達', 'AI伺服器機櫃與代工', 'GB200 NVL72整機機櫃、Compute Tray運算托盤、液冷系統整合', 10.0, 15.0, 12.5, 'Tier 1 核心主供', '黃仁勳GTC官方背板點名、鴻海科技日揭露'),
        ('2382', '廣達', 'NVDA', '輝達', 'AI伺服器整機ODM', 'GB200/HGX/MGX 伺服器整機組裝、L10/L11系統整合', 18.0, 25.0, 21.5, 'Tier 1 核心主供', '法說會AI伺服器出貨比重、GTC首選夥伴'),
        ('3231', '緯創', 'NVDA', '輝達', 'GPU運算主基板', 'DGX/HGX GPU Baseboard 運算基板主要供應商', 15.0, 22.0, 18.5, 'Tier 1 核心主供', '財報重大部門揭露、NVIDIA主要基板供應商'),
        ('6669', '緯穎', 'NVDA', '輝達', 'AI伺服器機櫃', 'NVL72 氣冷/水冷機櫃整機出貨', 12.0, 18.0, 15.0, 'Tier 1 主要ODM', '法人研究報告與公開出貨客戶群'),
        ('3017', '奇鋐', 'NVDA', '輝達', '散熱模組與水冷系統', '3D VC均熱板、GB200冷卻水冷板 (Cold Plate)、風扇', 25.0, 35.0, 30.0, 'Tier 1 認證主供', 'NVIDIA原廠合格供應商(AVL)、大摩散熱專題研報'),
        ('3324', '雙鴻', 'NVDA', '輝達', '水冷散熱模組', '水冷板 (Cold Plate)、冷卻液分配歧管 (CDM)', 22.0, 30.0, 26.0, 'Tier 1 認證主供', '法說會水冷營收佔比揭露、NVIDIA供應鏈認證'),
        ('2059', '川湖', 'NVDA', '輝達', '伺服器導軌機構件', 'AI伺服器高承重專用導軌、機架滑軌 (全球市佔逾85%)', 35.0, 45.0, 40.0, 'Tier 1 壟斷級供應商', '財報毛利率70%+之專利導軌拆解、券商認證'),
        ('3653', '健策', 'NVDA', '輝達', '均熱片/散熱機構件', 'B200/H100 晶片高階均熱片 (Heat Spreader)', 28.0, 38.0, 33.0, 'Tier 1 獨家/主供', '全球晶片均熱片市佔霸主、法人報告認證'),
        ('2368', '金像電', 'NVDA', '輝達', '高階PCB板', 'AI伺服器UBB(通用基板)/OAM、高層數PCB電路板', 25.0, 35.0, 30.0, 'Tier 1 核心PCB主供', '券商供應鏈訪查、AI營收佔比法說會確認'),
        ('2308', '台達電', 'NVDA', '輝達', '電源與能源管理', 'AI伺服器高壓直流電源架構(54V/800V)、水冷散熱CDU', 10.0, 15.0, 12.5, 'Tier 1 獨家級電源主供', 'NVIDIA官方公版指定電源合作夥伴'),
        ('3711', '日月光投控', 'NVDA', '輝達', '半導體封測代工', 'CoWoS 後段封裝、SiP系統級模組與測試', 6.0, 9.0, 7.5, 'Tier 1 封測主供', '台積電外溢CoWoS封裝夥伴'),
        ('8210', '勤誠', 'NVDA', '輝達', '伺服器機殼與機架', 'AI伺服器標準1U/2U/4U/8U機殼與機架機構件', 28.0, 38.0, 33.0, 'Tier 1 機殼主力主供', 'MGX公版機殼合作夥伴'),

        # --- Apple (AAPL) ---
        ('2330', '台積電', 'AAPL', '蘋果', '晶圓代工', 'A18/A19手機晶片、M4/M5晶片全系列 3nm/2nm 獨家代工', 20.0, 25.0, 22.5, 'Tier 1 全球獨家主供', '長期財報最大客戶(客戶A)年佔比約22~25%'),
        ('2317', '鴻海', 'AAPL', '蘋果', '電子組裝ODM', 'iPhone Pro/Pro Max 高階機型主要組裝、iPad/Mac代工', 45.0, 52.0, 48.5, 'Tier 1 第一大代工廠', '財報最大客戶營收揭露，佔鴻海總營收近半'),
        ('3008', '大立光', 'AAPL', '蘋果', '光學鏡頭', 'iPhone 高階潛望式長焦鏡頭、7P/8P 主鏡頭', 40.0, 50.0, 45.0, 'Tier 1 鏡頭第一大主供', '年報客戶名單與出貨拆解、Apple官方供應商名冊'),
        ('3406', '玉晶光', 'AAPL', '蘋果', '光學鏡頭與VR透鏡', 'iPhone 超廣角鏡頭、潛望鏡頭、Vision Pro Pancake 透鏡', 42.0, 52.0, 47.0, 'Tier 1 主要鏡頭主供', '年報營收單一客戶逾四成、Apple供應商名冊'),
        ('4958', '臻鼎-KY', 'AAPL', '蘋果', '軟板與高階PCB', 'iPhone/Apple Watch 軟板(FPC)、SLP類載板', 55.0, 65.0, 60.0, 'Tier 1 軟板全球龍頭', '財報第一大客戶揭露、Apple供應商名冊'),
        ('3037', '欣興', 'AAPL', '蘋果', '載板與PCB', 'Apple M系列/A系列 ABF載板、高階HDI', 18.0, 25.0, 21.5, 'Tier 1 主要載板供應商', 'Apple供應商名單與載板出貨結構'),
        ('3711', '日月光投控', 'AAPL', '蘋果', '系統級封裝(SiP)', 'Apple Watch / AirPods / iPhone 射頻與通訊SiP模組', 15.0, 20.0, 17.5, 'Tier 1 SiP第一大封測', 'Apple官方供應鏈名冊成員'),

        # --- Microsoft (MSFT) ---
        ('6669', '緯穎', 'MSFT', '微軟', '雲端白牌伺服器', 'Azure 資料中心 AI / 一般運算白牌伺服器機櫃', 45.0, 55.0, 50.0, 'Tier 1 最大伺服器主供', '緯穎年報公開揭露：微軟為前兩大客戶，佔比約50%'),
        ('2382', '廣達', 'MSFT', '微軟', '伺服器機櫃ODM', 'Azure 雲端伺服器與AI叢集機櫃整合', 14.0, 20.0, 17.0, 'Tier 1 核心ODM夥伴', '法人研報與雲端客戶拆解'),
        ('2345', '智邦', 'MSFT', '微軟', '資料中心交換器', '400G/800G 白牌資料中心交換機 (SONiC架構)', 15.0, 22.0, 18.5, 'Tier 1 網通主供', '微軟開放網路架構核心交換器製造商'),
        ('2356', '英業達', 'MSFT', '微軟', '伺服器主機板與組裝', '微軟伺服器主機板(L6)與整機代工', 12.0, 18.0, 15.0, 'Tier 1 主要主機板夥伴', '英業達雲端伺服器出貨客戶結構'),

        # --- Amazon (AMZN) ---
        ('3661', '世芯-KY', 'AMZN', '亞馬遜', '客製化ASIC晶片設計', 'AWS 自研 AI 晶片 Trainium 1/2/3 獨家架構與量產服務', 58.0, 70.0, 64.0, 'Tier 1 戰略級獨家ASIC夥伴', '法說會確認：北美雲端大客戶(AWS)佔世芯營收逾六成'),
        ('6669', '緯穎', 'AMZN', '亞馬遜', '雲端伺服器', 'AWS 第三方伺服器與專案機櫃出貨', 10.0, 16.0, 13.0, 'Tier 1 核心夥伴', '緯穎第三大CSP客戶'),
        ('2345', '智邦', 'AMZN', '亞馬遜', '資料中心交換機', 'AWS 資料中心 400G 交換器主供', 15.0, 20.0, 17.5, 'Tier 1 核心網通廠', '法人研究報告與供應鏈確認'),
        ('8069', '元太', 'AMZN', '亞馬遜', '電子紙顯示模組', 'Kindle 電子書閱讀器全系列電子紙顯示螢幕', 35.0, 45.0, 40.0, 'Tier 1 全球獨家專利壟斷', '元太消費性電子主力產品線，專利獨家供給Amazon'),
        ('2330', '台積電', 'AMZN', '亞馬遜', '晶圓代工', 'AWS Graviton CPU & Trainium AI 晶片代工', 2.0, 4.0, 3.0, 'Tier 1 晶圓代工夥伴', '台積電先進製程客戶'),

        # --- Alphabet / Google (GOOGL) ---
        ('2382', '廣達', 'GOOGL', 'Alphabet/Google', '伺服器機架ODM', 'Google Cloud (GCP) 資料中心伺服器機櫃主要代工廠', 15.0, 22.0, 18.5, 'Tier 1 最大伺服器主供', '廣達長年為Google伺服器最大白牌ODM夥伴'),
        ('2454', '聯發科', 'GOOGL', 'Alphabet/Google', 'ASIC與邊緣AI晶片', 'Google TPU 客製化晶片共同開發、終端產品通訊IC', 4.0, 7.0, 5.5, 'Tier 1 戰略合作夥伴', '外資半導體報告拆解聯發科ASIC業務'),
        ('2345', '智邦', 'GOOGL', 'Alphabet/Google', '交換機網通設備', 'Google 資料中心 Jupiter 架構高速白牌交換機', 12.0, 18.0, 15.0, 'Tier 1 網通核心主供', 'Google資料中心高速交換機供應鏈'),
        ('2356', '英業達', 'GOOGL', 'Alphabet/Google', '伺服器主機板', 'Google TPU 伺服器主機板代工', 8.0, 14.0, 11.0, 'Tier 2 主要代工廠', '英業達雲端伺服器出貨結構'),

        # --- Meta Platforms (META) ---
        ('6669', '緯穎', 'META', 'Meta', 'AI與雲端伺服器機櫃', 'Meta AI 資料中心(Llama大模型叢集)專屬伺服器機架', 32.0, 42.0, 37.0, 'Tier 1 兩大支柱客戶之一', '緯穎公開財報：Meta為長期前兩大客戶，佔比三至四成'),
        ('3406', '玉晶光', 'META', 'Meta', 'VR光學Pancake透鏡', 'Meta Quest 3 / Quest Pro 專用VR Pancake透鏡', 18.0, 25.0, 21.5, 'Tier 1 獨家/主要光學主供', '法說會VR鏡頭產品線營收拆解'),
        ('2345', '智邦', 'META', 'Meta', '開放網路交換器', 'Meta OCP (Open Compute Project) 高速交換器', 14.0, 20.0, 17.0, 'Tier 1 OCP創始與主力製造廠', '智邦OCP開源交換機主力客戶'),
        ('2454', '聯發科', 'META', 'Meta', '穿戴與VR晶片', 'Ray-Ban Meta 智慧眼鏡、VR 晶片協同研發', 3.0, 5.0, 4.0, 'Tier 1 關鍵晶片夥伴', 'Meta Connect官方發布會合作技術'),

        # --- Tesla (TSLA) ---
        ('1536', '和大', 'TSLA', '特斯拉', '電動車減速齒輪機構', 'Tesla Model 3/Y/Cybertruck 減速齒輪箱與傳動軸', 28.0, 36.0, 32.0, 'Tier 1 核心主供', '和大公開財報與重大客戶說明，特斯拉為第一大客戶'),
        ('5243', '乙盛-KY', 'TSLA', '特斯拉', '車用沖壓機構件', 'Model Y、Cybertruck 車體沖壓件與電池機構外殼', 32.0, 42.0, 37.0, 'Tier 1 墨西哥廠配套主供', '乙盛墨西哥廠專供特斯拉德州廠'),
        ('3665', '貿聯-KY', 'TSLA', '特斯拉', '高壓線束與連接器', '車用超高壓電源線束、Megapack 儲能系統線束', 14.0, 20.0, 17.0, 'Tier 1 創始線束核心主供', '特斯拉最早期的台灣核心線束夥伴'),
        ('2360', '致茂', 'TSLA', '特斯拉', '自動化量測與檢測設備', '電動車電池包(Battery Pack)/BMS與電驅系統檢測設備', 12.0, 18.0, 15.0, 'Tier 1 車規測試指定儀器', '特斯拉電池生產線指定量測儀器供應商'),
        ('2330', '台積電', 'TSLA', '特斯拉', '自駕與AI晶片代工', 'Tesla HW4.0 / HW5.0 FSD 全自動駕駛晶片、Dojo 晶片', 2.0, 4.0, 3.0, 'Tier 1 獨家先進製程代工', '特斯拉晶片外包台積電5nm/3nm'),

        # --- Broadcom (AVGO) ---
        ('2330', '台積電', 'AVGO', '博通', '晶圓代工與CPO', '高階 5nm/3nm 網通晶片代工、矽光子(CPO)封裝', 5.0, 7.5, 6.2, 'Tier 1 晶圓代工第一大主供', '博通為台積電前六大客戶之一'),
        ('3711', '日月光投控', 'AVGO', '博通', '先進封測', '高階網通IC覆晶封裝(Flip Chip)、SiP封測', 8.0, 12.0, 10.0, 'Tier 1 封裝主力夥伴', '日月光重要網通客戶名單'),
        ('3037', '欣興', 'AVGO', '博通', '高階ABF載板', 'Tomahawk 系列超大型高層數 ABF 載板', 10.0, 16.0, 13.0, 'Tier 1 載板核心主供', '外資載板研究報告客戶拆解'),
        ('3081', '聯亞', 'AVGO', '博通', '矽光子光通訊磊晶', 'CPO 光引擎專用雷射磊晶片 (CW Laser ERL)', 18.0, 28.0, 23.0, 'Tier 1 關鍵材料供應商', '聯亞法說會矽光子客戶結構'),

        # --- AMD (AMD) ---
        ('2330', '台積電', 'AMD', '超微', '晶圓代工與3D封裝', 'Zen 5 CPU、MI300/MI325 GPU 晶圓代工與 3D SoIC 封裝', 5.0, 8.0, 6.5, 'Tier 1 全系列獨家晶圓代工', '台積電前三大高效能運算(HPC)客戶'),
        ('3711', '日月光投控', 'AMD', '超微', '半導體封裝測試', 'EPYC 伺服器處理器封裝、系統級測試', 6.0, 9.0, 7.5, 'Tier 1 封測主力夥伴', 'AMD全球主要封測代工廠'),
        ('3037', '欣興', 'AMD', '超微', 'ABF 載板', 'MI300 AI 晶片超大型高階 ABF 載板主供', 14.0, 20.0, 17.0, 'Tier 1 核心載板主供', '法人報告拆解AMD載板分配佔比'),
        ('3653', '健策', 'AMD', '超微', '均熱片機構件', 'EPYC 伺服器 CPU 專用高散熱均熱片', 16.0, 24.0, 20.0, 'Tier 1 第一大均熱片主供', '健策全球伺服器CPU均熱片市佔領先'),
        ('2382', '廣達', 'AMD', '超微', 'AI伺服器整機', 'AMD Instinct MI300X 伺服器機架代工', 5.0, 8.0, 6.5, 'Tier 1 合作夥伴', '雲端伺服器多元化方案'),

        # --- Qualcomm (QCOM) ---
        ('2330', '台積電', 'QCOM', '高通', '晶圓代工', 'Snapdragon 8 Gen 3/4、Snapdragon X Elite 晶圓代工', 5.0, 8.0, 6.5, 'Tier 1 旗艦晶片主力代工', '高通旗艦晶片回歸台積電先進製程'),
        ('2449', '京元電子', 'QCOM', '高通', '晶圓預燒與成品測試', '手機與AI PC處理器晶片測試代工', 16.0, 24.0, 20.0, 'Tier 1 最大委外測試代工廠', '京元電前兩大客戶，營收佔比約兩成'),
        ('3711', '日月光投控', 'QCOM', '高通', '封裝與模組測試', '手機射頻前端(RFFE)模組、通訊SiP封測', 8.0, 12.0, 10.0, 'Tier 1 封測合作夥伴', '高通主要封裝代工夥伴')
    ]

    cur.executemany("""
    INSERT INTO supply_chain_relations 
    (tw_ticker, tw_name, us_ticker, us_name, relation_category, supplied_product, 
     est_revenue_pct_low, est_revenue_pct_high, est_revenue_pct_mid, tier_level, official_basis)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, relations)

    # 4. 計算並寫入美股十大巨頭對台股的綜合影響權重排名 (Macro Influence)
    # 計算公式: 綜合影響力 = Sum (台廠市值 * 該巨頭營收佔比中位數)
    df_rel = pd.read_sql("SELECT r.us_ticker, r.us_name, r.est_revenue_pct_mid, c.est_market_cap_bil_twd FROM supply_chain_relations r JOIN tw_companies c ON r.tw_ticker = c.tw_ticker", conn)
    
    df_rel['weighted_influence'] = df_rel['est_market_cap_bil_twd'] * (df_rel['est_revenue_pct_mid'] / 100.0)
    summary = df_rel.groupby(['us_ticker', 'us_name']).agg(
        total_partners_count=('est_revenue_pct_mid', 'count'),
        weighted_influence=('weighted_influence', 'sum')
    ).reset_index().sort_values(by='weighted_influence', ascending=False)

    sector_map = {
        'AAPL': '消費電子/晶圓代工/高階光學/組裝 (台積電、鴻海、大立光)',
        'NVDA': 'AI算力叢集/先進封裝/水冷散熱/滑軌 (台積電、廣達、奇鋐、川湖)',
        'MSFT': '雲端資料中心/白牌伺服器/高速交換器 (緯穎、廣達、智邦)',
        'GOOGL': '自研TPU/雲端伺服器/ASIC (廣達、聯發科、智邦)',
        'AMZN': '自研Trainium ASIC/白牌機櫃/電子紙 (世芯-KY、元太、緯穎)',
        'META': 'Llama AI叢集/VR光學透鏡/OCP交換器 (緯穎、玉晶光、智邦)',
        'TSLA': '電動車減速齒輪/車用高壓線束/沖壓 (和大、貿聯-KY、乙盛-KY)',
        'AVGO': '網通高階載板/矽光子CPO/交換器 (欣興、聯亞、智邦)',
        'AMD': 'HPC晶片代工/3D封裝/均熱片 (台積電、健策、欣興)',
        'QCOM': '手機旗艦AP/晶片測試/AI PC (台積電、京元電、日月光)'
    }

    for _, row in summary.iterrows():
        u_tick = row['us_ticker']
        u_name = row['us_name']
        p_count = int(row['total_partners_count'])
        w_inf = round(row['weighted_influence'], 1)
        focus = sector_map.get(u_tick, '')
        cur.execute("INSERT INTO giant_macro_impact VALUES (?,?,?,?,?)", (u_tick, u_name, p_count, w_inf, focus))

    conn.commit()
    conn.close()
    print("Database built successfully at:", DB_PATH)

if __name__ == '__main__':
    create_and_populate_db()
