import requests
import json
import time

codes = ['005930', '000660', '005380', '000270', '005490', '035420', '051910', '006400', '068270', '035720']
headers = {'User-Agent': 'Mozilla/5.0'}
session = requests.Session()

t0 = time.time()
results = []
for c in codes:
    try:
        url = f'https://m.stock.naver.com/api/stock/{c}/finance/annual'
        r = session.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            data = r.json()
            results.append(c)
    except Exception as e:
        print(f"Error {c}: {e}")

print(f"Fetched {len(results)} stocks in {time.time()-t0:.2f} seconds")
