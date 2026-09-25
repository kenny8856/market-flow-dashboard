import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix Y-axis formatting for institutional amounts
content = re.sub(
    r"// 3\. 初.*?外資與投信多空金額.*\n\s*const instContainer = document.getElementById\('inst-chart-container'\);",
    r"// 3. 繪製副圖 2\n            const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));\n            const unitName = isIndex ? '億' : '萬';\n            const instContainer = document.getElementById('inst-chart-container');",
    content
)

# Replace ' 萬' with ' ' + unitName in foreignSeries and trustSeries
content = re.sub(
    r"formatter: function\(val\) \{\s*return Number\(val\)\.toFixed\(1\) \+ ' 萬';\s*\}\s*\},",
    r"formatter: function(val) {\n                        return Number(val).toFixed(1) + ' ' + (typeof unitName !== 'undefined' ? unitName : '萬');\n                    }\n                },",
    content
)

# 2. Remove [← 返回市場全域儀表板] button
content = re.sub(r'<a href="index\.html" class="btn-back">← 返回市場全域儀表板</a>', '', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched stock_page_generator.py for Y-axis units and back button")
