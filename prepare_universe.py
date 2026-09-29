import FinanceDataReader as fdr
import pandas as pd
import os
import time

os.makedirs('d:/lsj/antigravity/data', exist_ok=True)

# 1. Get KOSPI listing sorted by market cap
krx = fdr.StockListing('KRX')
kospi = krx[krx['Market'] == 'KOSPI'].sort_values(by='Marcap', ascending=False)

# Exclude preferred stocks (ending with 5, 7, etc. or Name containing '우') and ETFs
valid_stocks = []
for _, row in kospi.iterrows():
    code = str(row['Code'])
    name = str(row['Name'])
    # Skip preferred stocks and SPACs
    if code.endswith('0') and not name.endswith('우') and not name.endswith('우B') and '스팩' not in name:
        valid_stocks.append((code, name, row['Marcap']))
    if len(valid_stocks) >= 100:
        break

print(f"Selected Top {len(valid_stocks)} KOSPI Common Stocks.")
print("Top 10:", valid_stocks[:10])

# Save universe metadata
df_universe = pd.DataFrame(valid_stocks, columns=['Code', 'Name', 'Marcap'])
df_universe.to_csv('d:/lsj/antigravity/data/universe_top100.csv', index=False, encoding='utf-8-sig')
print("Saved universe_top100.csv")
