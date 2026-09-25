import os

file_path = r"C:\TW_Stock\src\stock_page_generator.py"

with open(file_path, 'r', encoding='latin-1') as f:
    content = f.read()

# 1. Inject _calculate_poc
target_1 = '''    def generate_page(self, stock_info: Dict[str, Any]) -> str:'''
replacement_1 = '''    def _calculate_poc(self, quotes, days: int):
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

    def generate_page(self, stock_info: Dict[str, Any]) -> str:'''
content = content.replace(target_1, replacement_1)

# 2. Inject POC values inside generate_page
target_2 = '''        quotes = data['quotes']'''
replacement_2 = '''        quotes = data['quotes']
        poc_60 = self._calculate_poc(quotes, 60)
        poc_120 = self._calculate_poc(quotes, 120)
        poc_240 = self._calculate_poc(quotes, 240)
        poc_60_str = str(poc_60) if poc_60 else "null"
        poc_120_str = str(poc_120) if poc_120 else "null"
        poc_240_str = str(poc_240) if poc_240 else "null"'''
content = content.replace(target_2, replacement_2)

# 3. Inject JS
target_3 = '''            candleSeries.setData(klineData);
            candleSeries.setMarkers(markersData);'''
replacement_3 = '''            candleSeries.setData(klineData);
            candleSeries.setMarkers(markersData);
            
            const poc60 = {poc_60_str};
            if (poc60 !== null) {
                candleSeries.createPriceLine({
                    price: poc60,
                    color: '#eab308',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'POC(60)'
                });
            }
            const poc120 = {poc_120_str};
            if (poc120 !== null) {
                candleSeries.createPriceLine({
                    price: poc120,
                    color: '#f97316',
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
                    color: '#ec4899',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.LargeDashed,
                    axisLabelVisible: true,
                    title: 'POC(240)'
                });
            }'''
content = content.replace(target_3, replacement_3)

# Note: Since the HTML string in the original file might be an f-string or .format(), 
# wait, if it's an f-string, inserting `{poc_60_str}` into the literal will interpolate it because it's part of the f-string in the python code!
# Let's ensure this works.

with open(file_path, 'w', encoding='latin-1') as f:
    f.write(content)

print("Patch applied using latin-1")
