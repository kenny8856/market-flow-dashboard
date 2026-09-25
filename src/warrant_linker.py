import sqlite3
import re
from typing import Tuple, Dict
from .config import DB_DIR

GEO_DB_PATH = DB_DIR / "stock_geography.db"

class WarrantLinker:
    """
    權證名稱與上市/上櫃個股資料庫之智慧關聯引擎。
    根據臺灣權證命名慣例：[標的名稱][發行券商簡稱][到期年月][購/售][期數]
    自動自權證名稱中提取對應之標的個股，並關聯補齊【個股代號】與【個股名稱】。
    """

    def __init__(self):
        self.stock_map: Dict[str, Tuple[str, str]] = {}
        self.sorted_names = []
        self._load_stock_index()

    def _load_stock_index(self):
        """從 stock_geography.db 載入全市場上市與上櫃股票代號與簡稱"""
        if not GEO_DB_PATH.exists():
            return

        with sqlite3.connect(str(GEO_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT stock_id, stock_name FROM stocks;")
            rows = cursor.fetchall()

        for r in rows:
            sid = r["stock_id"].strip()
            sname = r["stock_name"].strip()
            if not sid or not sname:
                continue

            self.stock_map[sname] = (sid, sname)

            # 處理 -KY 境外公司簡稱變體 (例如: jpp-KY -> jpp, 貿聯-KY -> 貿聯)
            if "-KY" in sname:
                base = sname.replace("-KY", "").strip()
                if base and base not in self.stock_map:
                    self.stock_map[base] = (sid, sname)

            # 處理彈性面額 * 標記變體 (例如: 長科* -> 長科, 矽力*-KY -> 矽力)
            if "*" in sname:
                base = sname.replace("*", "").replace("-KY", "").strip()
                if base and base not in self.stock_map:
                    self.stock_map[base] = (sid, sname)

        # 依詞長降冪排序，長詞優先匹配 (避免 "力積" 誤攔截 "力積電")
        self.sorted_names = sorted(self.stock_map.keys(), key=lambda x: len(x), reverse=True)

    def link(self, warrant_name: str) -> Tuple[str, str]:
        """
        給定權證名稱 (如 '前鼎統一5C購01', '台積電元大61購01', 'M31統一61購01')，
        回傳 (標的個股代號, 標的個股名稱)。若未匹配則回傳 ('', '')。
        """
        if not warrant_name:
            return "", ""

        w_clean = warrant_name.strip()
        for name in self.sorted_names:
            if w_clean.startswith(name):
                return self.stock_map[name]

        return "", ""
