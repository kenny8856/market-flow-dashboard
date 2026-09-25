import os

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add TAIEX and TPEx to the loop
injection = """    # 為加權與櫃買指數產出頁面
    try:
        from src.stock_page_generator import StockPageGenerator
        stock_gen = StockPageGenerator()
        
        stock_gen.generate_page({
            'id': 'TAIEX',
            'name': '加權指數',
            'market_type': 'TWSE',
            'side': 'LONG',
            'rank': 0,
            'price': 0,
            'ret_5d': 0
        })
        
        stock_gen.generate_page({
            'id': 'TPEx',
            'name': '櫃買指數',
            'market_type': 'TPEX',
            'side': 'LONG',
            'rank': 0,
            'price': 0,
            'ret_5d': 0
        })
        
        print("Generated TAIEX and TPEx pages with POC.")
    except Exception as e:
        print(f"Error generating index pages: {e}")

    # 原有的個股產出
    try:"""

content = content.replace("    # 為每檔選出的多方/空方標的自動產出專屬獨立分析頁面 (含K棒/九轉序列/13不連續/權證資金流)\n    try:", injection)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated generate_quant_regime.py")
