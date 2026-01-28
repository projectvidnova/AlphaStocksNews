# Telegram Notification Setup Guide

The News Agent can send alerts to Telegram channels/groups/users with formatted messages containing news title and AI analysis.

## Features

- **Rich Formatting**: HTML-formatted messages with emojis and structure
- **Complete Information**: News title, analysis summary, key insights, affected stocks/sectors
- **Trading Context**: Signal strength, sentiment, price validation status
- **Direct Links**: Click-through to original news articles
- **Lock-Free**: Async notifications without blocking news analysis

## Quick Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts to name your bot
4. Copy the **Bot Token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

**Option A: For Personal Chat**
1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":<YOUR_CHAT_ID>}` in the response

**Option B: For Groups**
1. Add your bot to the group
2. Send a message in the group
3. Visit the same URL as above
4. Find the chat ID (will be negative for groups)

**Option C: For Channels**
1. Add your bot as an admin to the channel
2. Post a message
3. Use `@userinfobot` or similar to get channel ID

### 3. Configure News Agent

Edit `config/news_agent.json`:

```json
{
    "telegram": {
        "enabled": true,
        "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "chat_id": "123456789",
        "parse_mode": "HTML",
        "timeout_seconds": 10
    }
}
```

### 4. Test the Integration

Run the news agent:
```bash
python run_news_agent.py
```

When high-impact news is detected, you'll receive a formatted message in Telegram.

## Message Format

Each alert includes:

```
🔴 NEWS ALERT - HIGH

📰 Stock Market Rallies on Positive GDP Data

🔍 Analysis:
The GDP growth of 7.2% exceeded market expectations, indicating strong economic momentum...

💡 Key Insights:
• Strong consumer spending driving growth
• Manufacturing sector shows recovery
• Inflation remains under control

📊 Affected Stocks:
NIFTY, BANKNIFTY, RELIANCE, INFY

🏭 Affected Sectors:
Banking, IT, Auto

Sentiment: 📈 Positive

Signal Strength: ████████░░ 80.0%

💼 Recommendation:
Consider buying IT sector stocks on dips...

📅 Published: 2026-01-28 14:30 IST
🔗 Source: Read Full Article

Alert ID: a1b2c3d4
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable/disable Telegram notifications |
| `bot_token` | string | - | Your Telegram Bot API token |
| `chat_id` | string | - | Target chat/group/channel ID |
| `parse_mode` | string | `"HTML"` | Message format (`"HTML"` or `"Markdown"`) |
| `timeout_seconds` | integer | `10` | API request timeout |

## Troubleshooting

### Bot not responding
- Verify bot token is correct
- Ensure bot is not blocked by user/group

### Messages not arriving
- Check chat ID is correct
- For groups: Ensure bot is added as member
- For channels: Ensure bot is added as admin

### Formatting issues
- Use `"HTML"` parse mode (default)
- Special characters are auto-escaped

### Rate limiting
- Telegram allows 30 messages/second
- News Agent respects rate limits automatically

## Security Best Practices

1. **Never commit bot tokens** to version control
2. Use environment variables for sensitive data:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token_here"
   export TELEGRAM_CHAT_ID="your_chat_id"
   ```
3. Load from environment in config:
   ```python
   import os
   config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
   config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
   ```

## Advanced Usage

### Multiple Recipients

Send to multiple chats by creating separate TelegramNotifier instances:

```python
notifiers = [
    TelegramNotifier(bot_token=token, chat_id=chat1, enabled=True),
    TelegramNotifier(bot_token=token, chat_id=chat2, enabled=True),
]

for notifier in notifiers:
    await notifier.send_news_alert(alert, analysis)
```

### Custom Formatting

Use `send_custom_message()` for custom formats:

```python
message = f"""
<b>🚨 BREAKING NEWS</b>

{alert.news_title}

{analysis.summary}
"""
await telegram.send_custom_message(message)
```

### Statistics

Track notification performance:

```python
stats = telegram.get_stats()
print(f"Sent: {stats['messages_sent']}")
print(f"Failed: {stats['messages_failed']}")
```

## Integration with Event Bus

Telegram notifications are automatically sent when:
1. High-impact news is analyzed
2. Trading opportunities are identified
3. Price validation shows remaining upside

The notification is sent **after** alert generation and **before** event publishing, ensuring alerts are logged even if Telegram fails.

## Testing

Run tests to verify Telegram integration:

```bash
pytest tests/test_news_agent/test_telegram_notifier.py -v
```

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [HTML Formatting](https://core.telegram.org/bots/api#html-style)
- [Markdown Formatting](https://core.telegram.org/bots/api#markdown-style)
