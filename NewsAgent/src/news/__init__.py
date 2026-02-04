"""
News Analysis Agent Module
Fetches news from RSS feeds, analyzes with LLM, and validates price impact.
"""

from .models import (
    NewsItem,
    NewsAnalysis,
    PriceValidation,
    NewsAlert,
    NewsImpactLevel,
    NewsSentiment,
    PriceAdjustmentStatus,
)
from .rss_fetcher import RSSFetcher
from .news_analyzer import NewsAnalyzer, LlamaAnalyzer  # LlamaAnalyzer is alias for backward compatibility
from .price_validator import PriceValidator
from .telegram_notifier import TelegramNotifier
from .news_agent import NewsAgent
from .news_data_helper import NewsDataHelper

__all__ = [
    "NewsItem",
    "NewsAnalysis", 
    "PriceValidation",
    "NewsAlert",
    "NewsImpactLevel",
    "NewsSentiment",
    "PriceAdjustmentStatus",
    "RSSFetcher",
    "NewsAnalyzer",
    "LlamaAnalyzer",  # Backward compatibility
    "PriceValidator",
    "TelegramNotifier",
    "NewsAgent",
    "NewsDataHelper",
]
