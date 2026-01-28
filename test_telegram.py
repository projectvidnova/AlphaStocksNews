"""
Test Telegram Notifier
Quick test to verify Telegram integration works.
"""

import asyncio
from datetime import datetime
from src.news.telegram_notifier import TelegramNotifier
from src.news.models import NewsAlert, NewsAnalysis, NewsImpactLevel, NewsSentiment
from src.utils.timezone_utils import get_current_time


async def test_telegram_notification():
    """Test sending a sample news alert to Telegram."""
    
    print("=" * 60)
    print("TELEGRAM NOTIFICATION TEST")
    print("=" * 60)
    
    # Load config
    import json
    with open("config/news_agent.json", "r") as f:
        config = json.load(f)
    
    telegram_config = config.get("telegram", {})
    
    if not telegram_config.get("enabled"):
        print("\n⚠️  Telegram is disabled in config/news_agent.json")
        print("To test: Set 'telegram.enabled' to true and add your bot_token and chat_id")
        return
    
    # Create notifier
    notifier = TelegramNotifier(
        bot_token=telegram_config.get("bot_token", ""),
        chat_id=telegram_config.get("chat_id", ""),
        enabled=True,
        parse_mode=telegram_config.get("parse_mode", "HTML")
    )
    
    # Create sample analysis
    analysis = NewsAnalysis(
        news_id="test_123",
        analysis_summary="The RBI announced a 25 bps rate cut, signaling a shift to accommodative policy. This is expected to boost consumer spending and corporate borrowing.",
        impact_level=NewsImpactLevel.HIGH,
        affected_stocks=["NIFTY", "BANKNIFTY", "HDFC", "ICICIBANK"],
        affected_sectors=["Banking", "NBFC", "Real Estate"],
        sentiment=NewsSentiment.POSITIVE,
        expected_direction="UP",
        expected_move_pct=2.5,
        signal_strength=0.85,
        key_insights=[
            "First rate cut in 18 months",
            "Banking stocks likely to benefit",
            "Real estate sector to see increased demand"
        ],
        analyzed_at=get_current_time(),
        analyzer_model="gemma3:4b",
        raw_analysis="Detailed LLM analysis output..."
    )
    
    # Create sample alert
    alert = NewsAlert(
        alert_id="test_alert_001",
        news_id="test_123",
        symbol="NIFTY",
        alert_type="opportunity",
        priority="high",
        news_title="RBI Cuts Repo Rate by 25 bps, Signals Accommodative Stance",
        news_summary="Reserve Bank of India announced a 25 basis points cut in repo rate to 6.25%...",
        news_link="https://example.com/rbi-rate-cut",
        sentiment=NewsSentiment.POSITIVE,
        expected_direction="UP",
        expected_move_pct=2.5,
        current_price=24500.50,
        recommended_action="BUY",
        entry_price=24500.00,
        stop_loss=24200.00,
        target=25100.00,
        impact_level=NewsImpactLevel.HIGH,
        trading_recommendation="Consider buying banking and NBFC stocks. Target 2-3% upside in next 2 days.",
        created_at=get_current_time(),
        valid_until=get_current_time()
    )
    
    print(f"\n📱 Sending test notification to Telegram...")
    print(f"   Bot Token: {telegram_config.get('bot_token', '')[:20]}...")
    print(f"   Chat ID: {telegram_config.get('chat_id', '')}")
    
    # Send notification
    success = await notifier.send_news_alert(alert, analysis)
    
    if success:
        print("\n✅ Telegram notification sent successfully!")
        print(f"   Check your Telegram chat: {telegram_config.get('chat_id', '')}")
    else:
        print("\n❌ Failed to send Telegram notification")
        print("   Check:")
        print("   - Bot token is correct")
        print("   - Chat ID is correct")
        print("   - Bot has permission to send messages to the chat")
    
    # Show stats
    stats = notifier.get_stats()
    print(f"\n📊 Notifier Stats:")
    print(f"   Messages Sent: {stats['messages_sent']}")
    print(f"   Messages Failed: {stats['messages_failed']}")
    print(f"   API Errors: {stats['api_errors']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_telegram_notification())
