import os

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Inst calculation
target1 = """            # 計算多空金額 (萬元): 淨買賣股數 * 當日收盤價 / 10000
            inst_info['foreign_amt_wan'] = round((inst_info['foreign_net_shares'] * close_p) / 10000.0, 1)
            inst_info['trust_amt_wan'] = round((inst_info['trust_net_shares'] * close_p) / 10000.0, 1)"""

replacement1 = """            # 計算多空金額
            if stock_id in ['TAIEX', 'TPEx']:
                # 指數的大盤金額已經在資料庫中是「元」，我們除以一億換算成「億元」
                inst_info['foreign_amt_wan'] = round(inst_info['foreign_net_shares'] / 100000000.0, 1)
                inst_info['trust_amt_wan'] = round(inst_info['trust_net_shares'] / 100000000.0, 1)
            else:
                # 個股: 淨買賣股數 * 當日收盤價 / 10000 = 萬元
                inst_info['foreign_amt_wan'] = round((inst_info['foreign_net_shares'] * close_p) / 10000.0, 1)
                inst_info['trust_amt_wan'] = round((inst_info['trust_net_shares'] * close_p) / 10000.0, 1)"""

content = content.replace(target1, replacement1)

# Fix 2: Chart title
target2 = """            // 3. 繪製副圖2：外資與投信多空金額 (萬)
            const instContainer = document.getElementById('inst-chart-container');
            const instChart = LightweightCharts.createChart(instContainer, Object.assign({}, commonChartOptions, {
                width: instContainer.clientWidth,
                height: instContainer.clientHeight,
            }));

            const foreignSeries = instChart.addHistogramSeries({
                priceFormat: {
                    type: 'custom',
                    formatter: function(val) {
                        return Number(val).toFixed(1) + ' 萬';
                    }
                },
                title: '外資多空金額'
            });"""

replacement2 = """            // 3. 繪製副圖2：外資與投信多空金額
            const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));
            const unitName = isIndex ? '億' : '萬';
            
            const instContainer = document.getElementById('inst-chart-container');
            const instChart = LightweightCharts.createChart(instContainer, Object.assign({}, commonChartOptions, {
                width: instContainer.clientWidth,
                height: instContainer.clientHeight,
            }));

            const foreignSeries = instChart.addHistogramSeries({
                priceFormat: {
                    type: 'custom',
                    formatter: function(val) {
                        return Number(val).toFixed(1) + ' ' + unitName;
                    }
                },
                title: '外資多空金額'
            });"""

content = content.replace(target2, replacement2)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated stock_page_generator.py for institutional units")
