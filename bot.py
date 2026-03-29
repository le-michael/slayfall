import os
import re
import json
import logging
import difflib
import telebot
from telebot.types import InputMediaPhoto
import requests
import io
from PIL import Image
from dotenv import load_dotenv
from flask import Flask, request

# Load .env variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to load datasets for quick O(1) lookup
VALID_ITEMS = {}

if os.path.exists('cards.json'):
    try:
        with open('cards.json', 'r') as f:
            cards_data = json.load(f)
            for c in cards_data:
                name = c.get('card_name', '')
                if name:
                    VALID_ITEMS[name] = {'type': 'card', 'effect': c.get('effect', '')}
        logger.info(f"Loaded {len(cards_data)} valid cards")
    except Exception as e:
        logger.error(f"Failed to load cards.json: {e}")

if os.path.exists('relics.json'):
    try:
        with open('relics.json', 'r') as f:
            relics_data = json.load(f)
            for r in relics_data:
                name = r.get('relic_name', '')
                if name:
                    VALID_ITEMS[name] = {'type': 'relic', 'effect': r.get('effect', '')}
        logger.info(f"Loaded {len(relics_data)} valid relics")
    except Exception as e:
        logger.error(f"Failed to load relics.json: {e}")

# Fetch the Telegram bot token from the environment variable
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN environment variable found. Please set it before running.")
    exit(1)

# Initialize the bot
bot = telebot.TeleBot(BOT_TOKEN)

# Base URLs for the github raw content
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/le-michael/slayfall/refs/heads/main/"
CARD_BASE_URL = f"{GITHUB_RAW_BASE}card_images_full/"
RELIC_BASE_URL = f"{GITHUB_RAW_BASE}relic_images_full/"

# Regex pattern to match [[ card name ]] or [[ card name+ ]]
# Examples: 
# "Check out [[ abrasive ]]"
# "Multiple [[strike]] and [[defend+]]"
CARD_PATTERN = re.compile(r'\[\[(.*?)\]\]')

def normalize_card_name(raw_name: str, has_plus: bool) -> str:
    """
    Normalizes the user input from [[ raw_name ]] into the format matching the GitHub image slug.
    """
    # 1. Strip leading/trailing whitespaces
    # 2. Lowercase the name
    name = raw_name.strip().lower()

    # 3. Remove apostrophes (e.g., "ascender's bane" -> "ascenders bane")
    name = name.replace("'", "")

    # 4. Replace spaces with hyphens (e.g., "adaptive strike" -> "adaptive-strike")
    name = re.sub(r'\s+', '-', name)

    return name

def fetch_and_process_image(url: str) -> io.BytesIO:
    """
    Downloads the transparent PNG from the URL, pastes it over a black background, 
    and returns a BytesIO stream ready to be sent to Telegram.
    """
    response = requests.get(url)
    response.raise_for_status()

    # Open image and ensure it has an alpha channel
    img = Image.open(io.BytesIO(response.content)).convert("RGBA")
    
    # Create solid black background of the same size
    bg = Image.new("RGBA", img.size, "BLACK")
    
    # Paste transparent image onto the black background using itself as mask
    bg.paste(img, (0, 0), img)
    
    # Convert to RGB (removing alpha) to force black background saving
    bg = bg.convert("RGB")
    
    buffer = io.BytesIO()
    bg.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    if not text:
        return

    # Find all matches for [[ ... ]]
    matches = CARD_PATTERN.findall(text)
    if not matches:
        return
    
    # Process each embedded [[ card name ]] request
    media_group = []
    
    for match in matches:
        match_str = match.strip()
        
        # Check if the text inside the brackets explicitly ends with '+'
        is_upgraded = match_str.endswith('+')
        if is_upgraded:
            # Strip the plus sign for name formatting
            raw_name = match_str[:-1].strip()
        else:
            raw_name = match_str
        
        # Normalize to internal representation
        slug = normalize_card_name(raw_name, is_upgraded)

        # Validate against known items
        if VALID_ITEMS and slug not in VALID_ITEMS:
            matches_found = difflib.get_close_matches(slug, VALID_ITEMS.keys(), n=1, cutoff=0.6)
            if not matches_found:
                bot.reply_to(message, f"Item not found: `{slug}`", parse_mode='Markdown')
                continue
            else:
                slug = matches_found[0]

        item = VALID_ITEMS.get(slug) if VALID_ITEMS else None
        item_type = item['type'] if item else 'card' # default fallback
        effect = item['effect'] if item else ''
        
        caption = None
        if item_type == 'relic':
            image_url = f"{RELIC_BASE_URL}{slug}.png" # Relics do not use upgraded suffix
            caption = effect
            logger.info(f"Adding relic: {slug} to media group.")
        else:
            suffix = "-upgraded" if is_upgraded else ""
            image_url = f"{CARD_BASE_URL}{slug}{suffix}.png"
            logger.info(f"Adding card: {slug} (Upgraded: {is_upgraded}) to media group.")
        
        try:
            processed_image = fetch_and_process_image(image_url)
            # InputMediaPhoto requires the name or bytes stream
            media_group.append(
                InputMediaPhoto(media=processed_image, caption=caption)
            )
        except Exception as e:
            logger.error(f"Failed to process image for {slug}: {e}")
            bot.reply_to(message, f"Failed to retrieve image for {slug}. It may not exist on GitHub.")
            
        # Telegram limits media groups to 10 items
        if len(media_group) == 10:
            break

    if media_group:
        try:
            bot.send_media_group(chat_id=message.chat.id, media=media_group)
        except Exception as e:
            logger.error(f"Failed to send media group: {e}")
            bot.reply_to(message, "Failed to send the group of images.")

# Webhook endpoint receiving updates from Telegram
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Unsupported Media Type', 415

if __name__ == '__main__':
    fly_app = os.environ.get('FLY_APP_NAME')
    
    if fly_app:
        # Fly.io webhook deployment
        webhook_url = f"https://{fly_app}.fly.dev/{BOT_TOKEN}"
        logger.info(f"Detected Fly environment. Setting webhook URL to: {webhook_url}")
        
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        
        # Start Flask server
        app.run(host='0.0.0.0', port=8080)
    else:
        # Local development fallback
        logger.info("No FLY_APP_NAME detected. Starting local infinity polling...")
        bot.remove_webhook()
        bot.infinity_polling()
