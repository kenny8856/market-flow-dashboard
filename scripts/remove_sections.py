import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Hide Margin stat box for TAIEX and TPEx
target_margin = """            <div class="stat-item">
                <div class="stat-label">📊 融資 5日增減</div>
                <div class="stat-value" style="color:var(--accent-yellow);">{margin_5d_str}</div>
            </div>"""

replacement_margin = """            {'' if stock_id in ['TAIEX', 'TPEx'] else f'''
            <div class="stat-item">
                <div class="stat-label">📊 融資 5日增減</div>
                <div class="stat-value" style="color:var(--accent-yellow);">{margin_5d_str}</div>
            </div>
            '''}"""

content = content.replace(target_margin, replacement_margin)


# 2. Hide Inst Chart for TPEx
target_inst_title = """<div class="chart-title">🏛️ 外資與投信每日多空金額"""
# Instead of removing the HTML, let's just use CSS display none if it's TPEx
# The container is `<div class="chart-box-sub" style="margin-top: 10px;">`
# Let's dynamically add display none.

# We will replace the entire sub chart div
# 
#         <!-- 副圖2: 法人 -->
#         <div class="chart-box-sub" style="margin-top: 10px;">
#             <div class="chart-title">🏛️ 外資與投信每日多空金額

target_inst_div = """        <div class="chart-box-sub" style="margin-top: 10px;">
            <div class="chart-title">🏛️ 外資與投信每日多空金額"""

replacement_inst_div = """        <div class="chart-box-sub" style="margin-top: 10px; {'''display:none;''' if stock_id == 'TPEx' else ''}">
            <div class="chart-title">🏛️ 外資與投信每日多空金額"""

content = content.replace(target_inst_div, replacement_inst_div)

# 3. We also need to hide the legend for it if it's TPEx
target_inst_legend = """            <div class="chart-legend" style="margin-top: 10px; margin-bottom: 4px;">
                <div class="legend-item" style="font-weight:700; color:var(--text-primary);">🏛️ 外資與投信每日多空金額"""

replacement_inst_legend = """            <div class="chart-legend" style="margin-top: 10px; margin-bottom: 4px; {'''display:none;''' if stock_id == 'TPEx' else ''}">
                <div class="legend-item" style="font-weight:700; color:var(--text-primary);">🏛️ 外資與投信每日多空金額"""

content = content.replace(target_inst_legend, replacement_inst_legend)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed Margin and Inst Chart for index pages")
