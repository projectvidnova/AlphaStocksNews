# NewsAgent - Automated Stock Market News Analysis System

A standalone news analysis agent that monitors RSS feeds from Indian stock market sources, analyzes news articles using AI, and sends alerts via Telegram.

## Features

- 🔄 **Automated RSS Monitoring**: Fetches news from MoneyControl, Economic Times, and other Indian market sources
- 🤖 **AI-Powered Analysis**: Uses Azure AI Foundry (DeepSeek/Llama) for intelligent news analysis
- 📊 **Impact Assessment**: Categorizes news by impact level (high/medium/low)
- 📱 **Telegram Alerts**: Real-time notifications for significant market news
- ⏰ **Market Hours Aware**: Respects Indian market trading hours (9:15 AM - 3:30 PM IST)
- 💾 **Smart Caching**: Deduplicates news to avoid redundant alerts

## Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required for Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional: Azure AI Foundry for AI analysis
AZURE_AI_ENDPOINT=https://your-endpoint.services.ai.azure.com
AZURE_AI_API_KEY=your_api_key_here
```

### 3. Running the Agent

**One-time run:**
```bash
python run_news_agent.py
```

**Continuous monitoring (recommended):**
```bash
python run_news_agent_continuous.py
```

## Configuration

Edit `config/news_agent.json` to customize:

```json
{
  "fetch_interval_minutes": 5,
  "market_hours_only": true,
  "min_impact_level": "medium",
  "max_news_age_hours": 2,
  "scrape_full_articles": false
}
```

### Configuration Options

- `fetch_interval_minutes`: How often to check for new news (default: 5 minutes)
- `market_hours_only`: Only run during market hours (9:15 AM - 3:30 PM IST)
- `min_impact_level`: Minimum impact level to alert ("low", "medium", "high")
- `max_news_age_hours`: Only process news within this many hours old
- `scrape_full_articles`: Whether to scrape full article content (slower but more detailed)

## Project Structure

```
NewsAgent/
├── src/
│   ├── news/               # Core news agent modules
│   │   ├── news_agent.py   # Main orchestrator
│   │   ├── rss_fetcher.py  # RSS feed fetching
│   │   ├── news_analyzer.py # AI-powered analysis
│   │   ├── telegram_notifier.py # Telegram alerts
│   │   └── models.py       # Data models
│   └── utils/              # Utility modules
│       ├── logger_setup.py
│       └── timezone_utils.py
├── config/
│   └── news_agent.json     # Configuration
├── logs/                   # Application logs
├── data/                   # Cache and data files
├── run_news_agent.py       # One-time execution
├── run_news_agent_continuous.py # Continuous monitoring
└── requirements.txt
```

## How It Works

1. **RSS Fetching**: Monitors configured RSS feeds every N minutes
2. **Deduplication**: Checks cache to avoid processing duplicate news
3. **AI Analysis**: Sends news to AI model for:
   - Sentiment analysis (bullish/bearish/neutral)
   - Impact level assessment (high/medium/low)
   - Affected stocks/sectors identification
4. **Telegram Alert**: Sends formatted alerts for significant news
5. **Caching**: Stores processed news to prevent duplicates

## Example Alert

```
🔔 High Impact News

Title: RBI announces policy rate change
Sentiment: Bearish 📉
Impact: High 🔴

Summary: Reserve Bank of India announces unexpected policy rate hike affecting banking sector

Affected: Banking, Finance
Source: MoneyControl
Time: 2026-02-04 10:30 IST

🔗 Read more: [link]
```

## Logs

All logs are stored in `logs/agent.log.YYYY-MM-DD`

## Troubleshooting

**No alerts received:**
- Check `.env` file has correct Telegram credentials
- Verify `market_hours_only` setting in config
- Check logs for errors

**AI analysis not working:**
- Verify Azure AI Foundry credentials in `.env`
- Check `config/news_agent.json` has correct model settings

**Duplicate alerts:**
- News cache at `data/news_cache.json` - delete to reset

## License

MIT License

## Support

For issues or questions, check the logs directory or review the configuration files.
