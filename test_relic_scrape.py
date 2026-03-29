import requests
from bs4 import BeautifulSoup
import re

url = 'https://sts2.untapped.gg/en/relics/black-blood'
soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text, 'html.parser')

meta = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
desc = meta['content'] if meta else ''
print("Desc:", desc)

labels = soup.find_all(string=lambda t: t and t.strip() in ['Character', 'Pool', 'Type', 'Cost', 'Rarity'])
parsed_labels = {l.strip().lower(): l.parent.find_next_sibling().get_text(strip=True) if l.parent.find_next_sibling() else None for l in labels}
print("Parsed via labels:", parsed_labels)

# Look for image
img = soup.find('div', class_=lambda c: c and 'RelicImage_container' in c) or soup.find('img', alt=lambda alt: alt and 'Black Blood' in alt)
if img:
    if img.name == 'img':
        print("Img src:", img['src'])
    else:
        i = img.find('img')
        if i: print("Img src:", i['src'])
