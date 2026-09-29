import requests
import json

headers = {'User-Agent': 'Mozilla/5.0'}
r = requests.get('https://m.stock.naver.com/api/stock/005930/finance/annual', headers=headers)
data = r.json()
print("trTitleList:", data['financeInfo']['trTitleList'])
print("\nRow titles:")
for row in data['financeInfo']['rowList']:
    print(row['title'], "->", row['columns'])
