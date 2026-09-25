import re
from typing import Dict, Tuple, Optional
from .config import PARK_DISTRICT_MAP

# 臺灣縣市名稱統一字典
CITY_NORMALIZATION = {
    "臺北市": "台北市", "臺中市": "台中市", "臺南市": "台南市", "臺東縣": "台東縣",
    "Taipei City": "台北市", "New Taipei City": "新北市", "Taoyuan City": "桃園市",
    "Hsinchu City": "新竹市", "Hsinchu County": "新竹縣", "Miaoli County": "苗栗縣",
    "Taichung City": "台中市", "Changhua County": "彰化縣", "Nantou County": "南投縣",
    "Yunlin County": "雲林縣", "Chiayi City": "嘉義市", "Chiayi County": "嘉義縣",
    "Tainan City": "台南市", "Kaohsiung City": "高雄市", "Pingtung County": "屏東縣",
    "Yilan County": "宜蘭縣", "Hualien County": "花蓮縣", "Taitung County": "台東縣",
    "Penghu County": "澎湖縣", "Kinmen County": "金門縣", "Lienchiang County": "連江縣",
    "Keelung City": "基隆市"
}

# 英文行政區對應中文常用行政區
EN_DISTRICT_MAP = {
    "Zhongzheng": "中正區", "Zhongshan": "中山區", "Daan": "大安區", "Songshan": "松山區",
    "Neihu": "內湖區", "Nangang": "南港區", "Xinyi": "信義區", "Wanhua": "萬華區",
    "Shilin": "士林區", "Beitou": "北投區", "Datong": "大同區", "Wenshan": "文山區",
    "Banqiao": "板橋區", "Zhonghe": "中和區", "Yonghe": "永和區", "Xinzhuang": "新莊區",
    "Xindian": "新店區", "Tucheng": "土城區", "Sanchong": "三重區", "Luzhou": "蘆洲區",
    "Xizhi": "汐止區", "Hsi Chih": "汐止區", "Shulin": "樹林區", "Wugu": "五股區",
    "Linkou": "林口區", "Bali": "八里區", "Ba-Li": "八里區", "Danshui": "淡水區", "Tamsui": "淡水區",
    "Zhubei": "竹北市", "Hukou": "湖口鄉", "Zhudong": "竹東鎮", "Baoshan": "寶山鄉",
    "Guishan": "龜山區", "Zhongli": "中壢區", "Chungli": "中壢區", "Bade": "八德區",
    "Pingzhen": "平鎮區", "Dayuan": "大園區", "Luzhu": "蘆竹區", "Yangmei": "楊梅區",
    "Xitun": "西屯區", "Nantun": "南屯區", "Beitun": "北屯區", "Daya": "大雅區",
    "Tanzi": "潭子區", "Dali": "大里區", "Wufeng": "霧峰區", "Taiping": "太平區",
    "Zhunan": "竹南鎮", "Toufen": "頭份市", "Tongluo": "銅鑼鄉",
    "Xihu": "溪湖鎮", "Yuanlin": "員林市", "Lugang": "鹿港鎮", "Hemei": "和美鎮",
    "Xinshi": "新市區", "Shanhua": "善化區", "Yongkang": "永康區", "Anping": "安平區",
    "Qianzhen": "前鎮區", "Lingya": "苓雅區", "Sanmin": "三民區", "Nanzi": "楠梓區",
    "Nanzih": "楠梓區", "Daliao": "大寮區", "Xiaogang": "小港區",
}

# 單字泛用方位名（不可單獨用於分點模糊匹配）
GENERIC_DISTRICT_WORDS = {"東", "西", "南", "北", "中"}

class GeoEngine:
    """
    地理空間與行政區解析比對引擎，用於精準判定公司與券商分點間的地緣關係。
    """

    @staticmethod
    def parse_address(addr: str) -> Dict[str, str]:
        """
        將中文或英文地址解析出：縣市 (city)、行政區 (district)、特殊園區 (park)。
        """
        if not addr:
            return {"city": "", "district": "", "park": "", "normalized_addr": ""}

        normalized = addr.replace("臺", "台").strip()
        detected_city = ""
        detected_dist = ""
        detected_park = ""

        # 1. 優先辨識真實縣市名稱
        m_city = re.search(r'(台北市|新北市|桃園市|台中市|台南市|高雄市|基隆市|新竹市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義市|嘉義縣|屏東縣|宜蘭縣|花蓮縣|台東縣|澎湖縣|金門縣|連江縣)', normalized)
        if m_city:
            detected_city = m_city.group(1)

        # 2. 檢查是否明確標註特殊科技園區或工業區
        for park_name, info in PARK_DISTRICT_MAP.items():
            park_matched = False
            if park_name in normalized:
                park_matched = True
            else:
                for alias in info["alias"]:
                    if alias in normalized:
                        # 若已偵測到縣市，必須與園區所在縣市一致，避免同路名跨縣市誤判 (如 高雄市大寮區力行路)
                        if not detected_city or detected_city == info["city"] or (info["city"] in ["新竹市", "新竹縣"] and detected_city in ["新竹市", "新竹縣"]):
                            park_matched = True
                            break
            if park_matched:
                detected_park = park_name
                if not detected_city:
                    detected_city = info["city"]
                if not detected_dist:
                    detected_dist = info["district"]
                break

        # 3. 中文行政區比對 (如 中山區、竹北市、土城區、新市區、員林市、大寮區)
        if not detected_dist:
            # 優先搜尋特定行政區
            m_dist = re.search(r'(?:台北市|新北市|桃園市|台中市|台南市|高雄市|基隆市|新竹市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義市|嘉義縣|屏東縣|宜蘭縣|花蓮縣|台東縣)?([^\d\s號路街段]{1,4}(?:市|區|鄉|鎮))', normalized)
            if m_dist:
                d_candidate = m_dist.group(1)
                if d_candidate not in ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", "新竹市", "嘉義市", "基隆市"]:
                    detected_dist = d_candidate

        # 4. 英文地址比對 (TPEx 上櫃公司)
        if not detected_city or not detected_dist:
            for en_city, tw_city in CITY_NORMALIZATION.items():
                if en_city.lower() in normalized.lower():
                    if not detected_city:
                        detected_city = tw_city
                    break
            for en_dist, tw_dist in EN_DISTRICT_MAP.items():
                if en_dist.lower() in normalized.lower():
                    if not detected_dist:
                        detected_dist = tw_dist
                    break

        return {
            "city": detected_city,
            "district": detected_dist,
            "park": detected_park,
            "normalized_addr": normalized
        }

    @classmethod
    def evaluate_geo_relation(cls, company_geo: Dict[str, str], broker_geo: Dict[str, str], broker_name: str) -> Optional[Tuple[int, str]]:
        """
        評估公司與特定券商分點的地緣關係：
        回傳: (geo_level, match_reason) 或 None (無地緣關係)
        - Level 1: 核心地緣（同行政區、同園區、或分點名稱直接帶公司所在在地行政區）
        - Level 2: 近鄰地緣（同縣市生活圈）
        """
        c_city = company_geo.get("city", "")
        c_dist = company_geo.get("district", "")
        c_park = company_geo.get("park", "")

        b_city = broker_geo.get("city", "")
        b_dist = broker_geo.get("district", "")
        b_park = broker_geo.get("park", "")

        if not c_city:
            return None

        # Level 1 判定 A: 特殊科學園區聚落 (如 竹科、南科、中科)
        if c_park == "新竹科學園區":
            if b_city in ["新竹市", "新竹縣"] and any(k in broker_name for k in ["竹科", "新竹", "竹北", "關東"]):
                return (1, f"核心地緣：新竹科學園區半導體重鎮專屬分點")
        elif c_park and (b_park == c_park or any(c_park.replace("科學園區", "").replace("科技產業園區", "") in broker_name for _ in [1])):
            if c_city == b_city or not b_city:
                return (1, f"核心地緣：同屬【{c_park}】專用園區分點")

        # Level 1 判定 B: 分點名稱直接冠有該公司的核心鄉鎮區名稱（排除單純的「東西南北中」）
        if c_dist:
            dist_short = c_dist.rstrip("區市鄉鎮")
            if len(dist_short) >= 2 and dist_short not in GENERIC_DISTRICT_WORDS:
                if dist_short in broker_name and (c_city == b_city or not b_city):
                    return (1, f"核心地緣：分點名稱冠名在地【{c_dist}】")

        # Level 1 判定 C: 同行政區 (兩者皆在同縣市同區，如 新北市土城區、台北市內湖區)
        if c_city == b_city and c_dist and b_dist and c_dist == b_dist:
            return (1, f"核心地緣：同行政區【{c_city}{c_dist}】營業處所")

        # Level 2 判定：同縣市生活圈 (同在台南市、同在台中市、同在彰化縣、同在高雄市)
        if c_city == b_city:
            return (2, f"近鄰地緣：同屬【{c_city}】生活圈分支機構")

        return None
