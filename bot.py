import os
import re
import json
import logging
import difflib
import telebot
import requests
import io
from PIL import Image
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to load cards.json to validate cards, if available
CARDS_FILE = 'cards.json'
VALID_CARDS = set()

if os.path.exists(CARDS_FILE):
    try:
        with open(CARDS_FILE, 'r') as f:
            cards_data = json.load(f)
            # Add valid card slugs to a set for quick O(1) lookup
            for c in cards_data:
                VALID_CARDS.add(c.get('card_name', ''))
        logger.info(f"Loaded {len(VALID_CARDS)} valid cards from {CARDS_FILE}")
    except Exception as e:
        logger.error(f"Failed to load {CARDS_FILE}: {e}")

# Fetch the Telegram bot token from the environment variable
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN environment variable found. Please set it before running.")
    exit(1)

# Initialize the bot
bot = telebot.TeleBot(BOT_TOKEN)

# Base URL for the github raw content
BASE_URL = "https://raw.githubusercontent.com/le-michael/slayfall/refs/heads/main/card_images_full/"

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

        # Validate against known cards if cards.json is loaded successfully
        if VALID_CARDS and slug not in VALID_CARDS:
            matches = difflib.get_close_matches(slug, VALID_CARDS, n=1, cutoff=0.6)
            if not matches:
                bot.reply_to(message, f"Card not found: `{slug}`", parse_mode='Markdown')
                continue
            else:
                closest_slug = matches[0]
                slug = closest_slug

        # Construct Image URL based on upgraded state
        suffix = "-upgraded" if is_upgraded else ""
        image_url = f"{BASE_URL}{slug}{suffix}.png"
        
        logger.info(f"Sending card: {slug} (Upgraded: {is_upgraded}) to chat {message.chat.id}")
        
        try:
            processed_image = fetch_and_process_image(image_url)
            bot.send_photo(
                chat_id=message.chat.id,
                photo=processed_image,
            )
        except Exception as e:
            logger.error(f"Failed to send image for {slug}: {e}")
            bot.reply_to(message, f"Failed to retrieve image for {slug}. It may not exist on GitHub.")

if __name__ == '__main__':
    logger.info("Bot is starting up and polling for messages...")
    bot.infinity_polling()
