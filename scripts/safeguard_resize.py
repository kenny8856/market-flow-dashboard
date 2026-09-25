import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = "instChart.applyOptions({ width: instContainer.clientWidth });"
replacement = "if(instChart) instChart.applyOptions({ width: instContainer.clientWidth });"

content = content.replace(target, replacement)

# We should also filter out nulls in allCharts just to be safe
content = content.replace(
    "const allCharts = [klineChart, volumeChart, instChart, warrantChart];",
    "const allCharts = [klineChart, volumeChart, instChart, warrantChart].filter(c => c !== null);"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Safeguarded resize and allCharts")
