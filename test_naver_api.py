import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get('https://m.stock.naver.com/api/stock/005930/finance/annual', headers=headers)
data = r.json()
periods = [p['title'] for p in data['financeInfo']['trTitleList']]
print("Periods:", periods)
print("\nAvailable Metrics:")
for row in data['financeInfo']['rowList']:
    title = row['title']
    cols = [row['columns'].get(p['key'], {}).get('value', 'N/A') for p in data['financeInfo']['trTitleList']]
    print(f"- {title:15s}: {cols}")
