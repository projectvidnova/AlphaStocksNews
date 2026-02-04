# Quick Setup Guide

## Step 1: Environment Setup

```bash
# Navigate to NewsAgent folder
cd d:\Project\AlphaStocksNews1\NewsAgent

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configuration

1. **Copy environment template:**
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` file** with your credentials:
   - Get Telegram Bot Token from [@BotFather](https://t.me/botfather)
   - Get your Chat ID from [@userinfobot](https://t.me/userinfobot)
   - (Optional) Add Azure AI Foundry credentials for AI analysis

3. **Customize `config/news_agent.json`** (optional):
   - Adjust fetch interval (default: 5 minutes)
   - Set market hours preference
   - Configure impact level threshold

## Step 3: Test Run

```bash
# Run once to test
python run_news_agent.py

# Check logs for any errors
type logs\agent.log.2026-02-04
```

## Step 4: Production Run

```bash
# Run continuously (monitors news every 5 minutes)
python run_news_agent_continuous.py
```

The agent will:
- ✅ Fetch news from RSS feeds
- ✅ Analyze with AI (if configured)
- ✅ Send Telegram alerts for significant news
- ✅ Cache processed news to avoid duplicates

## Telegram Bot Setup

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow instructions
3. Copy the bot token to `.env` file
4. Start your bot and send it a message
5. Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
6. Find your `chat_id` in the response
7. Add `chat_id` to `.env` file

## Troubleshooting

**Import errors:**
```bash
# Ensure you're in the NewsAgent directory
cd d:\Project\AlphaStocksNews1\NewsAgent

# Reinstall dependencies
pip install -r requirements.txt
```

**No Telegram alerts:**
- Verify bot token and chat ID in `.env`
- Check that you've sent at least one message to your bot
- Review logs for errors

**Permission errors:**
- Ensure logs/ and data/ directories exist and are writable
