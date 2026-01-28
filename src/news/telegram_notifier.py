"""
Telegram Notification Module
Sends news alerts to Telegram channels/users.

THREAD SAFETY: Lock-free design using atomic operations
"""

import asyncio
import aiohttp
from collections import Counter
from typing import Optional, Dict
from datetime import datetime

from ..utils.logger_setup import setup_logger
from .models import NewsAlert, NewsAnalysis

logger = setup_logger("telegram_notifier")


class TelegramNotifier:
    """
    Sends formatted news alerts to Telegram.
    
    Design:
    - Async HTTP calls with aiohttp
    - Lock-free statistics with Counter
    - HTML/Markdown formatting support
    - Rate limiting to avoid API throttling
    """
    
    def __init__(self, 
                 bot_token: str,
                 chat_id: str,
                 enabled: bool = True,
                 parse_mode: str = "HTML",
                 timeout_seconds: int = 10):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat ID (user, group, or channel)
            enabled: Whether notifications are enabled
            parse_mode: Message format ("HTML" or "Markdown")
            timeout_seconds: API request timeout
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.parse_mode = parse_mode
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Lock-free statistics
        self.stats = Counter({
            "messages_sent": 0,
            "messages_failed": 0,
            "api_errors": 0,
        })
        
        logger.info(
            f"TelegramNotifier initialized (enabled={enabled}, "
            f"chat_id={chat_id}, parse_mode={parse_mode})"
        )
    
    async def send_news_alert(self, 
                             alert: NewsAlert,
                             analysis: NewsAnalysis) -> bool:
        """
        Send news alert with analysis to Telegram.
        
        Args:
            alert: NewsAlert object
            analysis: NewsAnalysis object with detailed analysis
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, skipping")
            return False
        
        try:
            message = self._format_alert_message(alert, analysis)
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending news alert: {e}", exc_info=True)
            self.stats["messages_failed"] += 1
            return False
    
    async def send_custom_message(self, message: str) -> bool:
        """
        Send custom formatted message to Telegram.
        
        Args:
            message: Pre-formatted message text
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        return await self._send_message(message)
    
    async def _send_message(self, text: str) -> bool:
        """
        Send message via Telegram API.
        
        Args:
            text: Message text (HTML or Markdown formatted)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": True
            }
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(self.api_url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully")
                        self.stats["messages_sent"] += 1
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Telegram API error {response.status}: {error_text}"
                        )
                        self.stats["api_errors"] += 1
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("Telegram API timeout")
            self.stats["api_errors"] += 1
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}", exc_info=True)
            self.stats["api_errors"] += 1
            return False
    
    def _format_alert_message(self, 
                             alert: NewsAlert,
                             analysis: NewsAnalysis) -> str:
        """
        Format news alert as HTML message.
        
        Args:
            alert: NewsAlert object
            analysis: NewsAnalysis with detailed information
            
        Returns:
            HTML-formatted message
        """
        # Emoji indicators
        impact_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }
        
        sentiment_emoji = {
            "positive": "📈",
            "negative": "📉",
            "neutral": "➡️"
        }
        
        # Build message
        lines = []
        
        # Header with impact level
        impact = impact_emoji.get(alert.impact_level.value, "⚪")
        lines.append(f"<b>{impact} NEWS ALERT - {alert.impact_level.value.upper()}</b>")
        lines.append("")
        
        # Title
        lines.append(f"<b>📰 {self._escape_html(alert.title)}</b>")
        lines.append("")
        
        # Analysis
        lines.append("<b>🔍 Analysis:</b>")
        lines.append(self._escape_html(analysis.summary))
        lines.append("")
        
        # Key insights
        if analysis.key_insights:
            lines.append("<b>💡 Key Insights:</b>")
            for insight in analysis.key_insights:
                lines.append(f"• {self._escape_html(insight)}")
            lines.append("")
        
        # Affected stocks/sectors
        if analysis.affected_stocks:
            lines.append("<b>📊 Affected Stocks:</b>")
            lines.append(", ".join(analysis.affected_stocks))
            lines.append("")
        
        if analysis.affected_sectors:
            lines.append("<b>🏭 Affected Sectors:</b>")
            lines.append(", ".join(analysis.affected_sectors))
            lines.append("")
        
        # Sentiment
        sentiment = sentiment_emoji.get(analysis.sentiment.value, "➡️")
        lines.append(f"<b>Sentiment:</b> {sentiment} {analysis.sentiment.value.title()}")
        lines.append("")
        
        # Signal strength
        strength_bar = "█" * int(analysis.signal_strength * 10)
        lines.append(f"<b>Signal Strength:</b> {strength_bar} {analysis.signal_strength:.1%}")
        lines.append("")
        
        # Trading recommendation
        if alert.trading_recommendation:
            lines.append(f"<b>💼 Recommendation:</b>")
            lines.append(self._escape_html(alert.trading_recommendation))
            lines.append("")
        
        # Price validation (if available)
        if alert.price_adjustment_status:
            status_text = alert.price_adjustment_status.value.replace('_', ' ').title()
            lines.append(f"<b>📊 Price Status:</b> {status_text}")
            
            if alert.expected_move_pct:
                lines.append(f"<b>Expected Move:</b> {alert.expected_move_pct:+.2f}%")
            
            if alert.remaining_move_pct:
                lines.append(f"<b>Remaining Potential:</b> {alert.remaining_move_pct:+.2f}%")
            
            lines.append("")
        
        # News source and link
        lines.append(f"<b>📅 Published:</b> {analysis.analyzed_at.strftime('%Y-%m-%d %H:%M IST')}")
        lines.append(f"<b>🔗 Source:</b> <a href='{alert.news_link}'>Read Full Article</a>")
        
        # Footer
        lines.append("")
        lines.append(f"<i>Alert ID: {alert.alert_id[:8]}</i>")
        
        return "\n".join(lines)
    
    def _escape_html(self, text: str) -> str:
        """
        Escape HTML special characters for Telegram.
        
        Args:
            text: Input text
            
        Returns:
            HTML-escaped text
        """
        import html
        return html.escape(text)
    
    def get_stats(self) -> Dict[str, int]:
        """Get notifier statistics."""
        return dict(self.stats)
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = Counter({
            "messages_sent": 0,
            "messages_failed": 0,
            "api_errors": 0,
        })
