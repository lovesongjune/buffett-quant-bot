import requests
import re
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get('https://finance.naver.com/item/main.naver?code=005930', headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
scripts = soup.find_all('script')
print(f"Total scripts: {len(scripts)}")
for s in scripts:
    src = s.get('src')
    if src:
        print("script src:", src)
    elif s.string and ('api' in s.string.lower() or 'finance' in s.string.lower() or 'stock' in s.string.lower()):
        print("inline script preview:", s.string[:200])
