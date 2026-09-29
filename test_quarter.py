import requests
import json

headers = {'User-Agent': 'Mozilla/5.0'}
r = requests.get('https://m.stock.naver.com/api/stock/005930/finance/quarter', headers=headers)
data = r.json()
print("Quarter trTitleList:", [p['title'] for p in data['financeInfo']['trTitleList']])
