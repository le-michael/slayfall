import json
import time
import requests
import asyncio
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

def scrape_cards_json(json_path="cards.json"):
    base_url = "https://sts2.untapped.gg"
    cards_data = []
    seen_links = set()

    print("Step 1/2: Scraping card links...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Iterate through all 7 pages on untapped.gg
    for page in range(1, 8):
        url = f"{base_url}/en/cards?page={page}"
        print(f"Fetching {url}...")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to fetch page {page}: {e}")
            continue
            
        soup = BeautifulSoup(response.text, 'html.parser')
        anchors = soup.find_all('a', href=True)
        
        for a in anchors:
            href = a['href']
            # Find elements bridging to /en/cards/{cardName}
            if href.startswith('/en/cards/') or href.startswith('en/cards/'):
                prefix = '/en/cards/' if href.startswith('/en/cards/') else 'en/cards/'
                card_name = href[len(prefix):].split('?')[0].split('#')[0]
                if not card_name: 
                    continue
                
                full_link = f"{base_url}{href}" if href.startswith('/') else f"{base_url}/{href}"
                
                if full_link not in seen_links:
                    seen_links.add(full_link)
                    cards_data.append({"link": full_link, "card_name": card_name})
                    
        # Avoid getting rate limited by their backend
        time.sleep(1)

    print("Step 1.5/2: Scraping detailed card info...")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def fetch_card_details(card):
        try:
            res = requests.get(card['link'], headers=headers, timeout=10)
            res.raise_for_status()
            detail_soup = BeautifulSoup(res.text, 'html.parser')
            
            # The effect text is conveniently stored in the meta description
            meta = detail_soup.find('meta', property='og:description') or detail_soup.find('meta', attrs={'name': 'description'})
            desc = meta['content'] if meta else ''
            
            effect = ""
            if ": " in desc:
                effect = desc.split(": ", 1)[1]
            card['effect'] = effect
            
            # Stats like Character, Type, Cost, Rarity are stored under standard labels
            labels = detail_soup.find_all(string=lambda t: t and t.strip() in ['Character', 'Type', 'Cost', 'Rarity'])
            for l in labels:
                sibling = l.parent.find_next_sibling()
                if sibling:
                    key = l.strip().lower()
                    val = sibling.get_text(strip=True).lower()
                    if key == 'cost':
                        val = sibling.get_text(strip=True)  # keep cost casing
                    card[key] = val
                    
            # Upgraded effect details
            upg = detail_soup.find('div', class_=lambda c: c and 'upgradeDetails' in c)
            card['upgraded_effect'] = upg.get_text(separator=' ', strip=True) if upg else ""
            
        except Exception as e:
            print(f"Failed to fetch details for {card['card_name']}: {e}")
        return card

    completed = 0
    total = len(cards_data)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_card_details, card): card for card in cards_data}
        for future in as_completed(futures):
            completed += 1
            c = futures[future]
            if completed % 20 == 0 or completed == total:
                print(f"Fetched details for {c['card_name']} ({completed}/{total})...")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cards_data, f, indent=4)
        
    print(f"Found {len(cards_data)} unique cards! Saved to {json_path}.\n")
    return cards_data

async def download_card(card, output_dir, context, semaphore):
    async with semaphore:
        card_name = card['card_name']
        link = card['link']
        
        base_path = os.path.join(output_dir, f"{card_name}.png")
        upgraded_path = os.path.join(output_dir, f"{card_name}-upgraded.png")
        
        # Fast exit if both images are already downloaded
        if os.path.exists(base_path) and os.path.exists(upgraded_path):
            print(f"[{card_name}] Skipping, both versions already manually downloaded.")
            return

        page = await context.new_page()
        try:
            await page.goto(link, wait_until="networkidle", timeout=20000)
            
            # Subtask 1: Base Form
            if not os.path.exists(base_path):
                try:
                    container = page.locator("[class*='HoverCopyButton']:visible").first
                    await container.hover()
                    await page.wait_for_timeout(1000)
                    
                    button = container.locator("button").nth(1)
                    async with page.expect_download(timeout=15000) as download_info:
                        await button.click(force=True)
                        
                    download = await download_info.value
                    await download.save_as(base_path)
                    print(f"[{card_name}] Base downloaded: {card_name}.png")
                except Exception as e:
                    print(f"[{card_name}] Base failed: {e}")
                
            # Subtask 2: Upgraded Form
            if not os.path.exists(upgraded_path):
                try:
                    # Target both 'button' and 'label' elements containing the 'Upgraded' text specifically
                    upgraded_btn = page.locator("button", has_text="Upgraded")
                    if await upgraded_btn.count() == 0:
                        upgraded_btn = page.get_by_text("Upgraded", exact=True)
                        if await upgraded_btn.count() == 0:
                            upgraded_btn = page.locator("label:has-text('Upgraded')")
                            
                    if await upgraded_btn.count() > 0:
                        await upgraded_btn.first.click(force=True)
                        await page.wait_for_timeout(1000)
                        
                        container = page.locator("[class*='HoverCopyButton']:visible").first
                        await container.hover()
                        await page.wait_for_timeout(1000)
                        
                        button = container.locator("button").nth(1)
                        async with page.expect_download(timeout=15000) as download_info:
                            await button.click(force=True)
                            
                        download = await download_info.value
                        await download.save_as(upgraded_path)
                        print(f"[{card_name}] Upgraded downloaded: {card_name}-upgraded.png")
                except Exception as e:
                    print(f"[{card_name}] Upgraded failed: {e}")
                    
        except Exception as e:
            print(f"[{card_name}] Navigation block failed: {e}")
            
        finally:
            await page.close()

async def download_images_playwright(cards, output_dir="card_images_full", concurrency=5):
    print(f"Step 2/2: Starting mass download of {len(cards)} cards ({concurrency} concurrent tabs)...")
    os.makedirs(output_dir, exist_ok=True)
    
    # Restrict concurrent tabs so laptop memory is contained out of bounds and not blocked by bot tracking
    semaphore = asyncio.Semaphore(concurrency)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # We need accept_downloads=True to allow automated blob parsing via chromium natively without alerts
        context = await browser.new_context(accept_downloads=True)
        
        tasks = [download_card(card, output_dir, context, semaphore) for card in cards]
        await asyncio.gather(*tasks)
        await browser.close()

    print("\n[+] Full Deck Sync Complete!")

def main():
    json_path = "cards.json"
    
    # If a mapping already exists, load and pass. Otherwise, scrape.
    if os.path.exists(json_path):
        print("Found existing cards.json mapped. Fast-forwarding directly to downloading missing images...\n")
        with open(json_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)
    else:
        cards = scrape_cards_json(json_path)

    asyncio.run(download_images_playwright(cards, output_dir="card_images_full", concurrency=5))

if __name__ == "__main__":
    main()
