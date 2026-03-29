import json
import os
import requests
import urllib.parse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

def scrape_relics_json(json_path="relics.json"):
    base_url = "https://sts2.untapped.gg"
    relics_data = []
    
    print("Step 1/3: Scraping relic links...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    url = f"{base_url}/en/relics"
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch relics page: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    anchors = soup.find_all('a', href=True)
    
    seen_links = set()
    for a in anchors:
        href = a['href']
        if href.startswith('/en/relics/') or href.startswith('en/relics/'):
            prefix = '/en/relics/' if href.startswith('/en/relics/') else 'en/relics/'
            relic_name = href[len(prefix):].split('?')[0].split('#')[0]
            if not relic_name: 
                continue
            
            full_link = f"{base_url}{href}" if href.startswith('/') else f"{base_url}/{href}"
            
            if full_link not in seen_links:
                seen_links.add(full_link)
                relics_data.append({"link": full_link, "relic_name": relic_name})

    print("Step 2/3: Scraping detailed relic info...")
    def fetch_relic_details(relic):
        try:
            res = requests.get(relic['link'], headers=headers, timeout=10)
            res.raise_for_status()
            detail_soup = BeautifulSoup(res.text, 'html.parser')
            
            # Effect from meta description
            meta = detail_soup.find('meta', property='og:description') or detail_soup.find('meta', attrs={'name': 'description'})
            desc = meta['content'] if meta else ''
            
            effect = ""
            if ": " in desc:
                effect = desc.split(": ", 1)[1]
            relic['effect'] = effect
            
            # Parse 'Pool' and 'Rarity'
            labels = detail_soup.find_all(string=lambda t: t and t.strip() in ['Character', 'Pool', 'Type', 'Cost', 'Rarity'])
            for l in labels:
                sibling = l.parent.find_next_sibling()
                if sibling:
                    key = l.strip().lower()
                    val = sibling.get_text(strip=True).lower()
                    relic[key] = val
            
            img = detail_soup.find('div', class_=lambda c: c and 'RelicImage_container' in c) 
            if img:
                inner_img = img.find('img')
                if inner_img and inner_img.get('src'):
                    relic['img_url'] = inner_img['src']
            elif not relic.get('img_url'):
                for i in detail_soup.find_all('img'):
                    src = urllib.parse.unquote(i.get('src', ''))
                    if '/relics/' in src:
                        relic['img_url'] = i.get('src') # preserve original src
                        break

            # Extract underlying raw source if proxied through NextJS
            if relic.get('img_url') and '_next/image?url=' in relic['img_url']:
                parsed = urllib.parse.urlparse(relic['img_url'])
                qs = urllib.parse.parse_qs(parsed.query)
                if 'url' in qs:
                    relic['img_url'] = qs['url'][0]
                    
        except Exception as e:
            print(f"Failed to fetch details for {relic['relic_name']}: {e}")
        return relic

    completed = 0
    total = len(relics_data)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_relic_details, r): r for r in relics_data}
        for future in as_completed(futures):
            completed += 1
            if completed % 20 == 0 or completed == total:
                print(f"Fetched details ({completed}/{total})...")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(relics_data, f, indent=4)
        
    print(f"Found {len(relics_data)} unique relics! Saved to {json_path}.\n")
    return relics_data

def download_images(relics, output_dir="relic_images_full"):
    print("Step 3/3: Downloading relic images...")
    os.makedirs(output_dir, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    def download_image(relic):
        relic_name = relic['relic_name']
        img_url = relic.get('img_url')
        if not img_url:
            print(f"[{relic_name}] No image URL found.")
            return

        if img_url.startswith('//'):
            img_url = "https:" + img_url
        elif img_url.startswith('/'):
            img_url = "https://sts2.untapped.gg" + img_url

        ext = img_url.split('.')[-1].split('?')[0]
        if len(ext) > 4: ext = "png"
        
        file_path = os.path.join(output_dir, f"{relic_name}.{ext}")
        
        if os.path.exists(file_path):
            return
            
        try:
            r = requests.get(img_url, headers=headers, stream=True, timeout=10)
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[{relic_name}] Successfully downloaded.")
        except Exception as e:
            print(f"[{relic_name}] Failed to download: {e}")

    completed = 0
    total = len(relics)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_image, r) for r in relics]
        for future in as_completed(futures):
            completed += 1
            if completed % 20 == 0 or completed == total:
                print(f"Downloaded images ({completed}/{total})...")

    print("\n[+] Relic Sync Complete!")

def main():
    json_path = "relics.json"
    
    if os.path.exists(json_path):
        print("Found existing relics.json. Fast-forwarding directly to downloading missing images...\n")
        with open(json_path, 'r', encoding='utf-8') as f:
            relics = json.load(f)
    else:
        relics = scrape_relics_json(json_path)

    download_images(relics, output_dir="relic_images_full")

if __name__ == "__main__":
    main()
