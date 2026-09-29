import requests
import re
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get('https://finance.naver.com/item/main.naver?code=005930', headers=headers)
soup = BeautifulSoup(r.content.decode('euc-kr', 'replace'), 'html.parser')

iframes = soup.find_all('iframe')
print(f"Total iframes: {len(iframes)}")
for ifr in iframes:
    print("src:", ifr.get('src'))

# Also check tables
tables = soup.find_all('table')
print(f"Total tables: {len(tables)}")
for i, t in enumerate(tables):
    summary = t.get('summary', '')
    cls = t.get('class', '')
    print(f"Table {i}: class={cls}, summary={summary}")
