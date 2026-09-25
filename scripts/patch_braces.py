import os

file_path = r"C:\TW_Stock\src\stock_page_generator.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the single braces to double braces for JS blocks
old_js = """            const poc60 = {poc_60_str};
            if (poc60 !== null) {
                candleSeries.createPriceLine({
                    price: poc60,
                    color: '#eab308',
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
            }"""

new_js = """            const poc60 = {poc_60_str};
            if (poc60 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc60,
                    color: '#eab308',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: 'POC(60)'
                }});
            }}
            const poc120 = {poc_120_str};
            if (poc120 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc120,
                    color: '#f97316',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'POC(120)'
                }});
            }}
            const poc240 = {poc_240_str};
            if (poc240 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc240,
                    color: '#ec4899',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.LargeDashed,
                    axisLabelVisible: true,
                    title: 'POC(240)'
                }});
            }}"""

content = content.replace(old_js, new_js)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed braces in JS injection")
