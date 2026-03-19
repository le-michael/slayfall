# Slayfall Telegram Bot

A lightweight Telegram bot that listens for message mentions of Slay the Spire 2 cards and automatically grabs the high-resolution images from this repository to send directly to your group chats.

---

## 🛠 Local Development

The bot uses the standard `pyTelegramBotAPI` wrapper, alongside `Pillow` for image processing.

### Prerequisites
1. Python 3.11+
2. A Telegram Bot Token from **@BotFather** on Telegram.

### Instructions

1. **Clone the repository and enter the directory**:
```bash
git clone https://github.com/le-michael/slayfall.git
cd slayfall
```

2. **[Optional but recommended] Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies:**
```bash
pip install -r requirements.txt
```

4. **Environment Variables:**
Create a `.env` file in the root directory and add your bot token:
```ini
TELEGRAM_BOT_TOKEN="your_token_goes_here"
```

5. **Run the bot!**
```bash
python bot.py
```
*Note: Make sure your bot has Privacy Mode disabled in BotFather if you want it to passively read group messages!*

---

## 🚀 Deployment (Fly.io)

This bot is fully Dockerized and optimized for deployment to [Fly.io](https://fly.io), falling completely within their free tier boundaries.

1. **Install Flyctl** and login:
```bash
# MacOS/Linux
curl -L https://fly.io/install.sh | sh

fly auth login
```

2. **Launch the App**:
```bash
fly launch
```
*(Say `Yes` when it asks if you want to copy the configuration and deploy later, but don't deploy yet!)*

3. **Set your Secrets**:
Securely upload your bot token so it's not checked into Git:
```bash
fly secrets set TELEGRAM_BOT_TOKEN="your_token_here"
```

4. **Deploy**:
Because this bot uses "long polling" (constantly checking Telegram for messages), **you can ONLY run exactly 1 machine at a time**. If you run 2 machines, they will crash each other with 409 API Conflicts.
Run this command to strictly deploy a single instance:
```bash
fly deploy --ha=false
```

5. **Scaling & Managing**:
- See logs: `fly logs`
- Bring down the bot entirely: `fly scale count 0`
- Restart the bot: `fly apps restart`
