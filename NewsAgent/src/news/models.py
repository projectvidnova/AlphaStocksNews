"""
News Agent Data Models
Dataclasses for news entities - immutable for thread safety

THREAD SAFETY: All dataclasses are immutable (frozen) for safe concurrent access
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from ..utils.timezone_utils import get_current_time


class NewsImpactLevel(Enum):
    """Impact level of news on stock/industry"""
    CRITICAL = "critical"      # Immediate price impact expected
    HIGH = "high"              # Significant impact within hours
    MEDIUM = "medium"          # Moderate impact, may take days
    LOW = "low"                # Minimal market impact
    NEUTRAL = "neutral"        # No direct market impact


class NewsSentiment(Enum):
    """Sentiment classification"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class PriceAdjustmentStatus(Enum):
    """Whether price has adjusted to news"""
    NOT_ADJUSTED = "not_adjusted"      # Trading opportunity exists
    PARTIALLY_ADJUSTED = "partially"   # Some movement, more expected
    FULLY_ADJUSTED = "fully_adjusted"  # Price already reflects news
    UNCLEAR = "unclear"                # Cannot determine


@dataclass(frozen=True)
class NewsItem:
    """
    Immutable news item from RSS feed.
    
    Frozen dataclass ensures thread-safety for concurrent processing.
    """
    news_id: str                        # Unique hash of title + published_date
    title: str
    description: str
    link: str
    published_date: datetime
    source_feed: str                    # Which RSS feed this came from
    raw_content: Optional[str] = None
    fetch_timestamp: datetime = field(default_factory=get_current_time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "news_id": self.news_id,
            "title": self.title,
            "description": self.description,
            "link": self.link,
            "published_date": self.published_date.isoformat(),
            "source_feed": self.source_feed,
            "raw_content": self.raw_content,
            "fetch_timestamp": self.fetch_timestamp.isoformat(),
        }


@dataclass
class NewsAnalysis:
    """
    Analysis result from Llama model.
    
    Mutable to allow setting processing_time_ms after creation.
    """
    news_id: str
    
    # Impact Assessment
    impact_level: NewsImpactLevel
    sentiment: NewsSentiment
    confidence_score: float             # 0.0 to 1.0
    
    # Affected Entities
    affected_industries: List[str]      # e.g., ["Banking", "NBFC"]
    affected_stocks: List[str]          # e.g., ["HDFCBANK", "ICICIBANK"]
    affected_indices: List[str]         # e.g., ["NIFTY BANK", "NIFTY 50"]
    
    # Expected Movement
    expected_direction: str             # "UP", "DOWN", "SIDEWAYS"
    expected_move_pct: float            # Expected percentage move
    time_horizon: str                   # "immediate", "intraday", "short_term", "medium_term"
    
    # Reasoning
    analysis_summary: str               # Brief summary of analysis
    key_points: List[str]               # Bullet points of key insights
    
    # Metadata
    model_used: str                     # Llama model version
    analysis_timestamp: datetime = field(default_factory=get_current_time)
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "news_id": self.news_id,
            "impact_level": self.impact_level.value,
            "sentiment": self.sentiment.value,
            "confidence_score": self.confidence_score,
            "affected_industries": self.affected_industries,
            "affected_stocks": self.affected_stocks,
            "affected_indices": self.affected_indices,
            "expected_direction": self.expected_direction,
            "expected_move_pct": self.expected_move_pct,
            "time_horizon": self.time_horizon,
            "analysis_summary": self.analysis_summary,
            "key_points": self.key_points,
            "model_used": self.model_used,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
        }
    
    def is_actionable(self) -> bool:
        """Check if this analysis suggests actionable trade."""
        return (
            self.impact_level in [NewsImpactLevel.CRITICAL, NewsImpactLevel.HIGH] and
            len(self.affected_stocks) > 0 and
            self.expected_direction in ["UP", "DOWN"] and
            self.expected_move_pct >= 0.5
        )


@dataclass
class PriceValidation:
    """
    Price validation result - checks if stock price has adjusted to news.
    """
    news_id: str
    symbol: str
    
    # Price Data
    price_at_news: float                # Price when news was published
    current_price: float
    price_change_pct: float
    
    # Volume Analysis
    volume_spike: bool                  # Unusual volume detected
    volume_ratio: float                 # Current vs average volume
    
    # Adjustment Assessment
    adjustment_status: PriceAdjustmentStatus
    remaining_move_pct: Optional[float] # Expected remaining move if not adjusted
    
    # Trading Opportunity
    is_opportunity: bool
    recommended_action: Optional[str]   # "BUY", "SELL", None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    
    # Metadata
    validation_timestamp: datetime = field(default_factory=get_current_time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "news_id": self.news_id,
            "symbol": self.symbol,
            "price_at_news": self.price_at_news,
            "current_price": self.current_price,
            "price_change_pct": self.price_change_pct,
            "volume_spike": self.volume_spike,
            "volume_ratio": self.volume_ratio,
            "adjustment_status": self.adjustment_status.value,
            "remaining_move_pct": self.remaining_move_pct,
            "is_opportunity": self.is_opportunity,
            "recommended_action": self.recommended_action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "validation_timestamp": self.validation_timestamp.isoformat(),
        }


@dataclass
class NewsAlert:
    """
    Alert for trading opportunity based on news analysis.
    """
    alert_id: str
    news_id: str
    symbol: str
    
    # Alert Details
    alert_type: str                     # "opportunity", "warning", "info"
    priority: str                       # "critical", "high", "medium", "low"
    
    # News Context
    news_title: str
    news_summary: str
    
    # Analysis
    sentiment: NewsSentiment
    expected_direction: str
    expected_move_pct: float
    
    # Price Context
    current_price: float
    recommended_action: str
    entry_price: float
    stop_loss: float
    target: float
    
    # Timing
    created_at: datetime = field(default_factory=get_current_time)
    valid_until: datetime = None        # Alert expiry
    
    def __post_init__(self):
        """Set default valid_until if not provided."""
        if self.valid_until is None:
            from datetime import timedelta
            self.valid_until = get_current_time() + timedelta(hours=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "news_id": self.news_id,
            "symbol": self.symbol,
            "alert_type": self.alert_type,
            "priority": self.priority,
            "news_title": self.news_title,
            "news_summary": self.news_summary,
            "sentiment": self.sentiment.value,
            "expected_direction": self.expected_direction,
            "expected_move_pct": self.expected_move_pct,
            "current_price": self.current_price,
            "recommended_action": self.recommended_action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "created_at": self.created_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }
    
    def is_valid(self) -> bool:
        """Check if alert is still valid."""
        return get_current_time() < self.valid_until
    
    def format_alert_message(self) -> str:
        """Format alert for logging/notification."""
        return (
            f"🚨 TRADING ALERT: {self.recommended_action} {self.symbol}\n"
            f"   News: {self.news_title[:80]}{'...' if len(self.news_title) > 80 else ''}\n"
            f"   Entry: ₹{self.entry_price:.2f}, SL: ₹{self.stop_loss:.2f}, Target: ₹{self.target:.2f}\n"
            f"   Expected Move: {self.expected_move_pct:.1f}% {self.expected_direction}\n"
            f"   Sentiment: {self.sentiment.value}\n"
            f"   Valid Until: {self.valid_until.strftime('%H:%M IST')}"
        )
