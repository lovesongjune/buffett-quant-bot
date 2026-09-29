import FinanceDataReader as fdr
import pandas as pd
import requests
import json
import time
import os

print("=== 1. Downloading Price History ===")
universe = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})
codes = universe['Code'].tolist()

price_dict = {}
# Also download KOSPI index KS11
df_kospi = fdr.DataReader('KS11', '2020-01-01')
price_dict['KOSPI'] = df_kospi['Close']

t0 = time.time()
success_count = 0
for i, code in enumerate(codes):
    try:
        df = fdr.DataReader(code, '2020-01-01')
        if not df.empty and 'Close' in df.columns:
            price_dict[code] = df['Close']
            success_count += 1
    except Exception as e:
        print(f"Error fetching price for {code}: {e}")
    if (i + 1) % 20 == 0:
        print(f"Prices fetched: {i+1}/{len(codes)} ({time.time()-t0:.1f}s)")

df_prices = pd.DataFrame(price_dict)
df_prices.to_csv('d:/lsj/antigravity/data/prices_top100.csv', encoding='utf-8-sig')
print(f"Price data saved: {df_prices.shape} in {time.time()-t0:.1f}s")

print("\n=== 2. Downloading Fundamentals from Naver API ===")
headers = {'User-Agent': 'Mozilla/5.0'}
session = requests.Session()
fund_data = {}

t0 = time.time()
for i, code in enumerate(codes):
    try:
        url = f'https://m.stock.naver.com/api/stock/{code}/finance/annual'
        r = session.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            fund_data[code] = r.json()
    except Exception as e:
        print(f"Error fetching fundamentals for {code}: {e}")
    if (i + 1) % 25 == 0:
        print(f"Fundamentals fetched: {i+1}/{len(codes)} ({time.time()-t0:.1f}s)")

with open('d:/lsj/antigravity/data/fundamentals_top100.json', 'w', encoding='utf-8') as f:
    json.dump(fund_data, f, ensure_ascii=False, indent=2)

print(f"Fundamentals saved for {len(fund_data)} stocks in {time.time()-t0:.1f}s")
