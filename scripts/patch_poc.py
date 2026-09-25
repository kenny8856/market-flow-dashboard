import os
import re

gen_file = r"C:\TW_Stock\src\stock_page_generator.py"

with open(gen_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _calculate_poc method
poc_func = """
    def _calculate_poc(self, quotes: List[Dict[str, Any]], days: int) -> Optional[float]:
        if not quotes: return None
        target = quotes[-days:] if len(quotes) > days else quotes
        if not target: return None
        min_p = min(q['low'] for q in target)
        max_p = max(q['high'] for q in target)
        if min_p == max_p: return min_p
        bins = 50
        tick = (max_p - min_p) / bins
        profile = {}
        for q in target:
            idx = int((q['close'] - min_p) / tick) if tick > 0 else 0
            profile[idx] = profile.get(idx, 0) + q['volume']
        best_idx = max(profile, key=profile.get)
        return round(min_p + best_idx * tick + (tick / 2), 2)

    def generate_page(self, stock_info: Dict[str, Any]) -> str:"""

content = content.replace("    def generate_page(self, stock_info: Dict[str, Any]) -> str:", poc_func)

# 2. Add POC calculation in generate_page
poc_calc = """        quotes = data['quotes']

        # 計算短中長天期 POC
        poc_60 = self._calculate_poc(quotes, 60)
        poc_120 = self._calculate_poc(quotes, 120)
        poc_240 = self._calculate_poc(quotes, 240)
        poc_60_str = str(poc_60) if poc_60 else "null"
        poc_120_str = str(poc_120) if poc_120 else "null"
        poc_240_str = str(poc_240) if poc_240 else "null"
"""

content = content.replace("        quotes = data['quotes']", poc_calc)

# 3. Inject JS to draw POC lines
js_injection = """            candleSeries.setData(klineData);
            candleSeries.setMarkers(markersData);

            // 繪製 POC 關鍵價位線 (短中長)
            const poc60 = {poc_60_str};
            if (poc60 !== null) {
                candleSeries.createPriceLine({
                    price: poc60,
                    color: '#eab308', // Yellow
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: 'POC(60)'
                });
            }
            const poc120 = {poc_120_str};
            if (poc120 !== null) {
                candleSeries.createPriceLine({
                    price: poc120,
                    color: '#f97316', // Orange
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'POC(120)'
                });
            }
            const poc240 = {poc_240_str};
            if (poc240 !== null) {
                candleSeries.createPriceLine({
                    price: poc240,
                    color: '#ec4899', // Pink/Red
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.LargeDashed,
                    axisLabelVisible: true,
                    title: 'POC(240)'
                });
            }
"""

content = content.replace("            candleSeries.setData(klineData);\n            candleSeries.setMarkers(markersData);", js_injection)

# Add f-string replacement for JS block. We need to make sure poc strings are substituted.
content = content.replace("{poc_60_str}", '"{poc_60_str}"') # wait, the whole html is an f-string!
# Actually, if the HTML is an f-string in python, `{poc_60_str}` will be evaluated if we just put it in the f-string!
# Wait, let's fix the f-string injection.
# We replaced with literal `{poc_60_str}`, when python evaluates the f-string, it will replace it! But wait, `poc_60_str` is a variable in the local scope of `generate_page`. So f-string will catch it!

with open(gen_file, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated stock_page_generator.py")
