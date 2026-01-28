# News Analysis Agent - GitHub Copilot Instructions

## System Overview

Create a **modular, event-driven News Analysis Agent** that fetches news from Business Standard RSS feeds every 5 minutes, analyzes them using a local Llama model to identify market impact, and cross-validates with real-time stock prices using the existing Zerodha APIs.

**Key Objectives:**
1. Fetch news from 13 RSS feeds every 5 minutes
2. Analyze news with local Llama model for industry/stock impact
3. Check if price already reflects the news using Zerodha APIs
4. Alert for trading opportunities if price hasn't adjusted
5. Log everything properly for audit and debugging

---

## 🚨 Critical Architecture Rules

**Follow the existing lock-free, event-driven architecture.** See `.copilot-design-principles.md` and `docs/LOCK_FREE_ARCHITECTURE.md`.

### Mandatory Design Principles

1. **No Locks in Event Handlers**: Use `collections.Counter` for stats, `asyncio.Queue` for messaging
2. **Database as Truth**: Store processed news IDs in database, no in-memory tracking like `self.processed_news = set()`
3. **Event-Driven Communication**: Use EventBus for all component communication
4. **IST Timezone**: Use `src.utils.timezone_utils` for ALL time operations
5. **Independent Tasks**: Each handler runs in separate `asyncio.Task`
6. **Handler Isolation**: 30s timeouts, exceptions caught per-handler

---

## 📁 File Structure

Create the following modular structure:

```
src/
├── news/
│   ├── __init__.py
│   ├── rss_fetcher.py              # RSS feed fetching module
│   ├── news_parser.py              # Parse and normalize news items
│   ├── news_deduplicator.py        # Deduplicate news using DB
│   ├── llama_analyzer.py           # Local Llama model integration
│   ├── impact_assessor.py          # Assess industry/stock impact
│   ├── price_validator.py          # Validate if price adjusted using Zerodha
│   ├── news_alerter.py             # Alert system for trading opportunities
│   ├── news_agent.py               # Main orchestrator for news analysis
│   └── models.py                   # Dataclasses for news entities
├── events/
│   └── event_bus.py                # Add new event types (existing file)
tests/
├── test_news_agent/
│   ├── __init__.py
│   ├── test_rss_fetcher.py
│   ├── test_news_parser.py
│   ├── test_llama_analyzer.py
│   ├── test_impact_assessor.py
│   ├── test_price_validator.py
│   └── test_news_agent_integration.py
config/
└── news_agent.json                 # News agent configuration
```

---

## 📰 RSS Feed Configuration

### All Feeds to Monitor (DO NOT SKIP ANY)

```python
RSS_FEEDS = {
    # General News
    "top_stories": "https://www.business-standard.com/rss/home_page_top_stories.rss",
    "latest_news": "https://www.business-standard.com/rss/latest.rss",
    "todays_paper": "https://www.business-standard.com/rss/todays-paper.rss",
    "market_news": "https://www.business-standard.com/rss/markets-106.rss",
    "most_popular": "https://www.business-standard.com/rss/most-viewed.rss",
    "editors_pick": "https://www.business-standard.com/rss/bsrss.xml",
    
    # Industry Specific
    "industry": "https://www.business-standard.com/rss/industry-217.rss",
    "auto": "https://www.business-standard.com/rss/industry/auto-21701.rss",
    "sme": "https://www.business-standard.com/rss/industry/sme-21702.rss",
    "banking": "https://www.business-standard.com/rss/industry/banking-21703.rss",
    "agriculture": "https://www.business-standard.com/rss/industry/agriculture-21704.rss",
    "industry_news": "https://www.business-standard.com/rss/industry/news-21705.rss",
    "aviation": "https://www.business-standard.com/rss/industry/aviation-21706.rss",
}
```

---

## 📋 Module Specifications

### 1. `src/news/models.py` - Data Models

```python
"""
News Agent Data Models
Dataclasses for news entities - immutable for thread safety
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


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
    """Immutable news item from RSS feed"""
    news_id: str                        # Unique hash of title + published_date
    title: str
    description: str
    link: str
    published_date: datetime
    source_feed: str                    # Which RSS feed this came from
    raw_content: Optional[str] = None
    fetch_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NewsAnalysis:
    """Analysis result from Llama model"""
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
    analysis_timestamp: datetime
    processing_time_ms: float


@dataclass
class PriceValidation:
    """Price validation result"""
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
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    
    # Metadata
    validation_timestamp: datetime


@dataclass
class NewsAlert:
    """Alert for trading opportunity"""
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
    created_at: datetime
    valid_until: datetime               # Alert expiry
```

---

### 2. `src/news/rss_fetcher.py` - RSS Feed Fetcher

```python
"""
RSS Feed Fetcher Module
Fetches news from multiple RSS feeds with rate limiting and error handling.

THREAD SAFETY: Lock-free design using atomic operations
"""

import asyncio
import aiohttp
import feedparser
import hashlib
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist
from .models import NewsItem

logger = setup_logger("rss_fetcher")


class RSSFetcher:
    """
    Asynchronous RSS feed fetcher with parallel processing.
    
    Design:
    - Fetches all feeds in parallel using asyncio.gather()
    - Uses atomic Counter for statistics
    - No shared mutable state requiring locks
    """
    
    RSS_FEEDS = {
        # General News
        "top_stories": "https://www.business-standard.com/rss/home_page_top_stories.rss",
        "latest_news": "https://www.business-standard.com/rss/latest.rss",
        "todays_paper": "https://www.business-standard.com/rss/todays-paper.rss",
        "market_news": "https://www.business-standard.com/rss/markets-106.rss",
        "most_popular": "https://www.business-standard.com/rss/most-viewed.rss",
        "editors_pick": "https://www.business-standard.com/rss/bsrss.xml",
        
        # Industry Specific
        "industry": "https://www.business-standard.com/rss/industry-217.rss",
        "auto": "https://www.business-standard.com/rss/industry/auto-21701.rss",
        "sme": "https://www.business-standard.com/rss/industry/sme-21702.rss",
        "banking": "https://www.business-standard.com/rss/industry/banking-21703.rss",
        "agriculture": "https://www.business-standard.com/rss/industry/agriculture-21704.rss",
        "industry_news": "https://www.business-standard.com/rss/industry/news-21705.rss",
        "aviation": "https://www.business-standard.com/rss/industry/aviation-21706.rss",
    }
    
    def __init__(self, 
                 timeout_seconds: int = 30,
                 max_concurrent: int = 5,
                 user_agent: str = "AlphaStocks NewsAgent/1.0"):
        """
        Initialize RSS fetcher.
        
        Args:
            timeout_seconds: Request timeout per feed
            max_concurrent: Max parallel feed fetches
            user_agent: HTTP User-Agent header
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.user_agent = user_agent
        
        # Atomic statistics (lock-free)
        self.stats = Counter({
            "feeds_fetched": 0,
            "feeds_failed": 0,
            "items_parsed": 0,
            "parse_errors": 0,
        })
        
        logger.info(f"RSSFetcher initialized with {len(self.RSS_FEEDS)} feeds")
    
    async def fetch_all_feeds(self) -> List[NewsItem]:
        """
        Fetch all RSS feeds in parallel.
        
        Returns:
            List of NewsItem objects from all feeds
        """
        fetch_start = get_current_time()
        
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent}
        ) as session:
            # Create tasks for all feeds
            tasks = [
                self._fetch_single_feed(session, feed_name, feed_url)
                for feed_name, feed_url in self.RSS_FEEDS.items()
            ]
            
            # Execute all in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results, handling exceptions
        all_items = []
        for feed_name, result in zip(self.RSS_FEEDS.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {feed_name}: {result}")
                self.stats["feeds_failed"] += 1
            else:
                all_items.extend(result)
                self.stats["feeds_fetched"] += 1
        
        fetch_duration = (get_current_time() - fetch_start).total_seconds()
        logger.info(
            f"Fetched {len(all_items)} items from {self.stats['feeds_fetched']} feeds "
            f"in {fetch_duration:.2f}s ({self.stats['feeds_failed']} failed)"
        )
        
        return all_items
    
    async def _fetch_single_feed(self, 
                                  session: aiohttp.ClientSession,
                                  feed_name: str, 
                                  feed_url: str) -> List[NewsItem]:
        """
        Fetch a single RSS feed with rate limiting.
        
        Args:
            session: aiohttp session
            feed_name: Name identifier for the feed
            feed_url: RSS feed URL
            
        Returns:
            List of NewsItem objects
        """
        async with self.semaphore:  # Rate limiting
            try:
                async with session.get(feed_url) as response:
                    if response.status != 200:
                        logger.warning(f"Feed {feed_name} returned status {response.status}")
                        return []
                    
                    content = await response.text()
                    return self._parse_feed(content, feed_name)
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {feed_name}")
                raise
            except Exception as e:
                logger.error(f"Error fetching {feed_name}: {e}")
                raise
    
    def _parse_feed(self, content: str, feed_name: str) -> List[NewsItem]:
        """
        Parse RSS feed content into NewsItem objects.
        
        Args:
            content: Raw RSS XML content
            feed_name: Source feed name
            
        Returns:
            List of NewsItem objects
        """
        items = []
        
        try:
            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                try:
                    # Generate unique ID from title + published date
                    news_id = self._generate_news_id(
                        entry.get('title', ''),
                        entry.get('published', '')
                    )
                    
                    # Parse published date
                    published_date = self._parse_date(entry.get('published'))
                    
                    item = NewsItem(
                        news_id=news_id,
                        title=entry.get('title', '').strip(),
                        description=entry.get('summary', entry.get('description', '')).strip(),
                        link=entry.get('link', ''),
                        published_date=published_date,
                        source_feed=feed_name,
                        raw_content=entry.get('content', [{}])[0].get('value') if entry.get('content') else None,
                        fetch_timestamp=get_current_time()
                    )
                    
                    items.append(item)
                    self.stats["items_parsed"] += 1
                    
                except Exception as e:
                    logger.warning(f"Error parsing entry in {feed_name}: {e}")
                    self.stats["parse_errors"] += 1
                    
        except Exception as e:
            logger.error(f"Error parsing feed {feed_name}: {e}")
            raise
            
        return items
    
    def _generate_news_id(self, title: str, published: str) -> str:
        """Generate unique news ID from title and date."""
        content = f"{title}_{published}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Parse date string to datetime, defaulting to current time."""
        if not date_str:
            return get_current_time()
        
        try:
            from email.utils import parsedate_to_datetime
            return to_ist(parsedate_to_datetime(date_str))
        except Exception:
            return get_current_time()
    
    def get_stats(self) -> Dict[str, int]:
        """Get fetcher statistics."""
        return dict(self.stats)
```

---

### 3. `src/news/llama_analyzer.py` - Local Llama Integration

```python
"""
Llama Model Analyzer
Integrates with locally running Llama model for news analysis.

Supports:
- Ollama (recommended for local deployment)
- llama.cpp server
- vLLM server
"""

import asyncio
import aiohttp
import json
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time
from .models import (
    NewsItem, NewsAnalysis, NewsImpactLevel, 
    NewsSentiment
)

logger = setup_logger("llama_analyzer")


# Stock and Industry mappings for Indian market
INDUSTRY_KEYWORDS = {
    "banking": ["bank", "banking", "npa", "credit", "loan", "rbi", "nbfc", "deposit"],
    "auto": ["auto", "vehicle", "car", "ev", "electric vehicle", "automobile", "scooter", "bike"],
    "it": ["software", "tech", "it", "digital", "saas", "infosys", "tcs", "wipro"],
    "pharma": ["pharma", "drug", "fda", "medicine", "hospital", "healthcare"],
    "aviation": ["aviation", "airline", "aircraft", "airport", "indigo", "spicejet"],
    "oil_gas": ["oil", "gas", "petroleum", "ongc", "reliance", "fuel", "crude"],
    "metal": ["steel", "metal", "iron", "aluminium", "copper", "tata steel"],
    "fmcg": ["fmcg", "consumer", "food", "beverage", "hindustan unilever", "itc"],
    "telecom": ["telecom", "5g", "airtel", "jio", "vodafone", "spectrum"],
    "realty": ["real estate", "realty", "housing", "property", "dlf", "godrej"],
    "agriculture": ["agriculture", "farm", "crop", "fertilizer", "monsoon", "kharif", "rabi"],
    "sme": ["sme", "small business", "msme", "startup"],
}

# Major stock symbols for entity extraction
MAJOR_STOCKS = {
    # Banking
    "hdfcbank": ["hdfc bank", "hdfcbank"],
    "icicibank": ["icici bank", "icicibank"],
    "sbin": ["sbi", "state bank", "sbin"],
    "axisbank": ["axis bank", "axisbank"],
    "kotakbank": ["kotak", "kotakbank"],
    
    # IT
    "tcs": ["tcs", "tata consultancy"],
    "infy": ["infosys", "infy"],
    "wipro": ["wipro"],
    "hcltech": ["hcl tech", "hcltech"],
    "techm": ["tech mahindra", "techm"],
    
    # Auto
    "tatamotors": ["tata motors", "tatamotors"],
    "maruti": ["maruti", "maruti suzuki"],
    "m&m": ["mahindra", "m&m"],
    "bajaj-auto": ["bajaj auto"],
    "heromotoco": ["hero motocorp", "heromotoco"],
    
    # Oil & Gas
    "reliance": ["reliance", "ril"],
    "ongc": ["ongc", "oil and natural gas"],
    "ioc": ["indian oil", "ioc"],
    "bpcl": ["bpcl", "bharat petroleum"],
    
    # Pharma
    "sunpharma": ["sun pharma", "sunpharma"],
    "drreddy": ["dr reddy", "drreddy"],
    "cipla": ["cipla"],
    "divislab": ["divis lab", "divislab"],
    
    # Aviation
    "indigo": ["indigo", "interglobe"],
    "spicejet": ["spicejet"],
    
    # Add more as needed...
}


class LlamaAnalyzer:
    """
    Analyzes news using locally running Llama model.
    
    Supports:
    - Ollama API (default, port 11434)
    - llama.cpp server
    - vLLM server
    """
    
    def __init__(self,
                 base_url: str = "http://localhost:11434",
                 model_name: str = "llama3.2:latest",
                 timeout_seconds: int = 60,
                 max_concurrent: int = 3):
        """
        Initialize Llama analyzer.
        
        Args:
            base_url: Ollama/llama.cpp server URL
            model_name: Model to use (e.g., "llama3.2:latest", "mistral")
            timeout_seconds: Request timeout
            max_concurrent: Max parallel analysis requests
        """
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Atomic statistics
        self.stats = Counter({
            "analyses_completed": 0,
            "analyses_failed": 0,
            "avg_processing_time_ms": 0,
        })
        
        logger.info(f"LlamaAnalyzer initialized with model {model_name} at {base_url}")
    
    async def analyze_news(self, news_item: NewsItem) -> Optional[NewsAnalysis]:
        """
        Analyze a single news item for market impact.
        
        Args:
            news_item: NewsItem to analyze
            
        Returns:
            NewsAnalysis result or None if failed
        """
        start_time = get_current_time()
        
        async with self.semaphore:
            try:
                # Build the analysis prompt
                prompt = self._build_analysis_prompt(news_item)
                
                # Call Llama model
                response = await self._call_llama(prompt)
                
                # Parse the response
                analysis = self._parse_analysis_response(news_item, response)
                
                # Calculate processing time
                processing_time = (get_current_time() - start_time).total_seconds() * 1000
                analysis.processing_time_ms = processing_time
                
                self.stats["analyses_completed"] += 1
                
                logger.info(
                    f"Analyzed news {news_item.news_id[:8]}: "
                    f"impact={analysis.impact_level.value}, "
                    f"sentiment={analysis.sentiment.value}, "
                    f"stocks={analysis.affected_stocks}"
                )
                
                return analysis
                
            except Exception as e:
                self.stats["analyses_failed"] += 1
                logger.error(f"Failed to analyze news {news_item.news_id[:8]}: {e}")
                return None
    
    async def analyze_batch(self, news_items: List[NewsItem]) -> List[NewsAnalysis]:
        """
        Analyze multiple news items in parallel.
        
        Args:
            news_items: List of NewsItem objects
            
        Returns:
            List of successful NewsAnalysis results
        """
        tasks = [self.analyze_news(item) for item in news_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful analyses
        analyses = []
        for result in results:
            if isinstance(result, NewsAnalysis):
                analyses.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Batch analysis error: {result}")
        
        return analyses
    
    def _build_analysis_prompt(self, news_item: NewsItem) -> str:
        """Build the analysis prompt for Llama."""
        
        prompt = f"""You are a financial analyst specializing in Indian stock markets (NSE/BSE).
Analyze the following news article and provide a structured assessment of its market impact.

NEWS TITLE: {news_item.title}

NEWS DESCRIPTION: {news_item.description}

SOURCE: {news_item.source_feed}
PUBLISHED: {news_item.published_date.strftime('%Y-%m-%d %H:%M IST')}

Provide your analysis in the following JSON format ONLY (no additional text):
{{
    "impact_level": "critical|high|medium|low|neutral",
    "sentiment": "very_bullish|bullish|neutral|bearish|very_bearish",
    "confidence_score": 0.0-1.0,
    "affected_industries": ["industry1", "industry2"],
    "affected_stocks": ["SYMBOL1", "SYMBOL2"],
    "affected_indices": ["NIFTY 50", "NIFTY BANK"],
    "expected_direction": "UP|DOWN|SIDEWAYS",
    "expected_move_pct": 0.0-10.0,
    "time_horizon": "immediate|intraday|short_term|medium_term",
    "analysis_summary": "Brief 1-2 sentence summary",
    "key_points": ["point1", "point2", "point3"]
}}

IMPORTANT:
- Use UPPERCASE NSE symbols for stocks (e.g., HDFCBANK, RELIANCE, TCS)
- Be conservative with impact_level - only use "critical" for major events
- confidence_score reflects your certainty in the analysis
- expected_move_pct should be realistic for Indian markets
- Focus on actionable insights for intraday/swing trading
"""
        return prompt
    
    async def _call_llama(self, prompt: str) -> str:
        """
        Call the Llama model API.
        
        Args:
            prompt: The analysis prompt
            
        Returns:
            Model response text
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Ollama API format
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3,  # Low temperature for consistent analysis
                    "top_p": 0.9,
                }
            }
            
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Llama API error {response.status}: {error_text}")
                
                result = await response.json()
                return result.get("response", "")
    
    def _parse_analysis_response(self, news_item: NewsItem, response: str) -> NewsAnalysis:
        """
        Parse Llama response into NewsAnalysis object.
        
        Args:
            news_item: Original news item
            response: Llama model response
            
        Returns:
            NewsAnalysis object
        """
        try:
            # Parse JSON response
            data = json.loads(response)
            
            return NewsAnalysis(
                news_id=news_item.news_id,
                impact_level=NewsImpactLevel(data.get("impact_level", "neutral")),
                sentiment=NewsSentiment(data.get("sentiment", "neutral")),
                confidence_score=float(data.get("confidence_score", 0.5)),
                affected_industries=data.get("affected_industries", []),
                affected_stocks=[s.upper() for s in data.get("affected_stocks", [])],
                affected_indices=data.get("affected_indices", []),
                expected_direction=data.get("expected_direction", "SIDEWAYS"),
                expected_move_pct=float(data.get("expected_move_pct", 0.0)),
                time_horizon=data.get("time_horizon", "intraday"),
                analysis_summary=data.get("analysis_summary", ""),
                key_points=data.get("key_points", []),
                model_used=self.model_name,
                analysis_timestamp=get_current_time(),
                processing_time_ms=0  # Set by caller
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response, using fallback: {e}")
            # Fallback: extract info using keyword matching
            return self._fallback_analysis(news_item, response)
    
    def _fallback_analysis(self, news_item: NewsItem, response: str) -> NewsAnalysis:
        """
        Fallback analysis using keyword extraction when JSON parsing fails.
        """
        # Extract industries from news text
        text = f"{news_item.title} {news_item.description}".lower()
        affected_industries = []
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                affected_industries.append(industry)
        
        # Extract stocks
        affected_stocks = []
        for symbol, keywords in MAJOR_STOCKS.items():
            if any(kw in text for kw in keywords):
                affected_stocks.append(symbol.upper())
        
        return NewsAnalysis(
            news_id=news_item.news_id,
            impact_level=NewsImpactLevel.LOW,
            sentiment=NewsSentiment.NEUTRAL,
            confidence_score=0.3,  # Low confidence for fallback
            affected_industries=affected_industries,
            affected_stocks=affected_stocks,
            affected_indices=[],
            expected_direction="SIDEWAYS",
            expected_move_pct=0.0,
            time_horizon="intraday",
            analysis_summary="Fallback analysis - LLM response parsing failed",
            key_points=["Analysis based on keyword matching only"],
            model_used=f"{self.model_name} (fallback)",
            analysis_timestamp=get_current_time(),
            processing_time_ms=0
        )
    
    async def check_health(self) -> bool:
        """Check if Llama server is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except Exception as e:
            logger.warning(f"Llama health check failed: {e}")
            return False
```

---

### 4. `src/news/price_validator.py` - Price Impact Validation

```python
"""
Price Validator Module
Validates if stock price has already adjusted to news using Zerodha APIs.

Uses existing Zerodha integration from the codebase.
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, is_market_hours
from ..core.historical_data_cache import HistoricalDataCache
from .models import (
    NewsAnalysis, PriceValidation, PriceAdjustmentStatus,
    NewsSentiment
)

logger = setup_logger("price_validator")


class PriceValidator:
    """
    Validates if stock prices have adjusted to news impact.
    
    Uses Zerodha APIs (via existing data layer) for:
    - Current price (LTP)
    - Historical prices
    - Volume analysis
    """
    
    def __init__(self, 
                 data_layer,
                 historical_cache: HistoricalDataCache,
                 kite_client=None):
        """
        Initialize price validator.
        
        Args:
            data_layer: ClickHouse data layer for historical data
            historical_cache: Historical data cache instance
            kite_client: Zerodha Kite client for real-time data
        """
        self.data_layer = data_layer
        self.historical_cache = historical_cache
        self.kite = kite_client
        
        # Atomic statistics
        self.stats = Counter({
            "validations_completed": 0,
            "validations_failed": 0,
            "opportunities_found": 0,
        })
        
        # Price movement thresholds
        self.config = {
            "min_move_for_impact": 0.5,      # Minimum % move to consider impacted
            "volume_spike_ratio": 2.0,        # Volume spike threshold
            "lookback_periods": 20,           # Periods for baseline calculation
            "max_news_age_hours": 4,          # Max age to consider news actionable
        }
        
        logger.info("PriceValidator initialized")
    
    async def validate_impact(self, 
                              analysis: NewsAnalysis,
                              news_published_time: datetime) -> List[PriceValidation]:
        """
        Validate if prices have adjusted to news impact.
        
        Args:
            analysis: NewsAnalysis with affected stocks
            news_published_time: When the news was published
            
        Returns:
            List of PriceValidation for each affected stock
        """
        validations = []
        
        for symbol in analysis.affected_stocks:
            try:
                validation = await self._validate_single_stock(
                    symbol=symbol,
                    analysis=analysis,
                    news_time=news_published_time
                )
                if validation:
                    validations.append(validation)
                    self.stats["validations_completed"] += 1
                    
                    if validation.is_opportunity:
                        self.stats["opportunities_found"] += 1
                        logger.info(
                            f"OPPORTUNITY: {symbol} - {validation.recommended_action} "
                            f"@ {validation.entry_price}, "
                            f"remaining move: {validation.remaining_move_pct:.2f}%"
                        )
                        
            except Exception as e:
                self.stats["validations_failed"] += 1
                logger.error(f"Failed to validate {symbol}: {e}")
        
        return validations
    
    async def _validate_single_stock(self,
                                     symbol: str,
                                     analysis: NewsAnalysis,
                                     news_time: datetime) -> Optional[PriceValidation]:
        """
        Validate price adjustment for a single stock.
        
        Args:
            symbol: Stock symbol (NSE format)
            analysis: News analysis
            news_time: News publish time
            
        Returns:
            PriceValidation or None
        """
        # Get current price and historical data
        current_price = await self._get_current_price(symbol)
        if current_price is None:
            return None
        
        # Get price at news time (or closest available)
        price_at_news = await self._get_price_at_time(symbol, news_time)
        if price_at_news is None:
            price_at_news = current_price  # Fallback
        
        # Calculate actual price change
        price_change_pct = ((current_price - price_at_news) / price_at_news) * 100
        
        # Check volume
        volume_spike, volume_ratio = await self._check_volume_spike(symbol)
        
        # Determine adjustment status
        adjustment_status = self._determine_adjustment_status(
            actual_change=price_change_pct,
            expected_change=analysis.expected_move_pct,
            expected_direction=analysis.expected_direction,
            sentiment=analysis.sentiment
        )
        
        # Calculate remaining move potential
        remaining_move = self._calculate_remaining_move(
            actual_change=price_change_pct,
            expected_change=analysis.expected_move_pct,
            expected_direction=analysis.expected_direction
        )
        
        # Determine if this is a trading opportunity
        is_opportunity = self._is_trading_opportunity(
            adjustment_status=adjustment_status,
            remaining_move=remaining_move,
            news_time=news_time,
            impact_level=analysis.impact_level.value
        )
        
        # Calculate trade parameters if opportunity exists
        recommended_action = None
        entry_price = None
        stop_loss = None
        target = None
        
        if is_opportunity:
            recommended_action = self._get_recommended_action(
                analysis.expected_direction,
                analysis.sentiment
            )
            entry_price = current_price
            stop_loss, target = self._calculate_sl_target(
                entry_price=current_price,
                direction=analysis.expected_direction,
                expected_move_pct=remaining_move or analysis.expected_move_pct
            )
        
        return PriceValidation(
            news_id=analysis.news_id,
            symbol=symbol,
            price_at_news=price_at_news,
            current_price=current_price,
            price_change_pct=price_change_pct,
            volume_spike=volume_spike,
            volume_ratio=volume_ratio,
            adjustment_status=adjustment_status,
            remaining_move_pct=remaining_move,
            is_opportunity=is_opportunity,
            recommended_action=recommended_action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            validation_timestamp=get_current_time()
        )
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current LTP from Zerodha."""
        try:
            if self.kite:
                # Use Kite client for real-time price
                # Format: NSE:SYMBOL
                instrument = f"NSE:{symbol}"
                quote = self.kite.quote([instrument])
                return quote[instrument]["last_price"]
            else:
                # Fallback: get latest from historical data
                df = self.historical_cache.get_historical(
                    symbol=symbol,
                    timeframe="1minute",
                    periods=1
                )
                if not df.empty:
                    return df.iloc[-1]["close"]
                return None
                
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    async def _get_price_at_time(self, symbol: str, target_time: datetime) -> Optional[float]:
        """Get price closest to specified time."""
        try:
            df = self.historical_cache.get_historical(
                symbol=symbol,
                timeframe="5minute",
                periods=100
            )
            
            if df.empty:
                return None
            
            # Find candle closest to target time
            df = df.copy()
            df["time_diff"] = abs(df.index - target_time)
            closest = df.loc[df["time_diff"].idxmin()]
            
            return closest["close"]
            
        except Exception as e:
            logger.error(f"Error getting historical price for {symbol}: {e}")
            return None
    
    async def _check_volume_spike(self, symbol: str) -> Tuple[bool, float]:
        """Check if there's unusual volume activity."""
        try:
            df = self.historical_cache.get_historical(
                symbol=symbol,
                timeframe="5minute",
                periods=self.config["lookback_periods"]
            )
            
            if df.empty or len(df) < 5:
                return False, 1.0
            
            avg_volume = df["volume"].mean()
            current_volume = df.iloc[-1]["volume"]
            
            if avg_volume == 0:
                return False, 1.0
            
            volume_ratio = current_volume / avg_volume
            is_spike = volume_ratio >= self.config["volume_spike_ratio"]
            
            return is_spike, volume_ratio
            
        except Exception as e:
            logger.error(f"Error checking volume for {symbol}: {e}")
            return False, 1.0
    
    def _determine_adjustment_status(self,
                                     actual_change: float,
                                     expected_change: float,
                                     expected_direction: str,
                                     sentiment: NewsSentiment) -> PriceAdjustmentStatus:
        """Determine how much the price has adjusted."""
        
        # Check direction alignment
        direction_match = (
            (expected_direction == "UP" and actual_change > 0) or
            (expected_direction == "DOWN" and actual_change < 0)
        )
        
        if not direction_match and abs(actual_change) > self.config["min_move_for_impact"]:
            return PriceAdjustmentStatus.UNCLEAR
        
        # Calculate adjustment percentage
        if expected_change == 0:
            return PriceAdjustmentStatus.NEUTRAL if abs(actual_change) < self.config["min_move_for_impact"] else PriceAdjustmentStatus.UNCLEAR
        
        adjustment_ratio = abs(actual_change) / abs(expected_change)
        
        if adjustment_ratio < 0.3:
            return PriceAdjustmentStatus.NOT_ADJUSTED
        elif adjustment_ratio < 0.7:
            return PriceAdjustmentStatus.PARTIALLY_ADJUSTED
        else:
            return PriceAdjustmentStatus.FULLY_ADJUSTED
    
    def _calculate_remaining_move(self,
                                  actual_change: float,
                                  expected_change: float,
                                  expected_direction: str) -> Optional[float]:
        """Calculate remaining potential move."""
        
        if expected_change == 0:
            return None
        
        if expected_direction == "DOWN":
            expected_change = -abs(expected_change)
        else:
            expected_change = abs(expected_change)
        
        remaining = expected_change - actual_change
        
        # Only return if move is in expected direction
        if (expected_direction == "UP" and remaining > 0) or \
           (expected_direction == "DOWN" and remaining < 0):
            return abs(remaining)
        
        return None
    
    def _is_trading_opportunity(self,
                               adjustment_status: PriceAdjustmentStatus,
                               remaining_move: Optional[float],
                               news_time: datetime,
                               impact_level: str) -> bool:
        """Determine if this represents a trading opportunity."""
        
        # Check if news is too old
        news_age_hours = (get_current_time() - news_time).total_seconds() / 3600
        if news_age_hours > self.config["max_news_age_hours"]:
            return False
        
        # Only consider unadjusted or partially adjusted
        if adjustment_status not in [
            PriceAdjustmentStatus.NOT_ADJUSTED,
            PriceAdjustmentStatus.PARTIALLY_ADJUSTED
        ]:
            return False
        
        # Need meaningful remaining move
        if remaining_move is None or remaining_move < 0.5:
            return False
        
        # Higher bar for lower impact news
        min_remaining_move = {
            "critical": 0.5,
            "high": 0.75,
            "medium": 1.0,
            "low": 1.5,
        }.get(impact_level, 1.0)
        
        return remaining_move >= min_remaining_move
    
    def _get_recommended_action(self, 
                               expected_direction: str,
                               sentiment: NewsSentiment) -> str:
        """Get recommended trading action."""
        if expected_direction == "UP":
            return "BUY"
        elif expected_direction == "DOWN":
            return "SELL"
        return "HOLD"
    
    def _calculate_sl_target(self,
                            entry_price: float,
                            direction: str,
                            expected_move_pct: float) -> Tuple[float, float]:
        """Calculate stop loss and target prices."""
        
        sl_pct = min(expected_move_pct * 0.5, 1.0)  # SL = 50% of expected move, max 1%
        target_pct = expected_move_pct * 0.8  # Target = 80% of expected move
        
        if direction == "UP":
            stop_loss = entry_price * (1 - sl_pct / 100)
            target = entry_price * (1 + target_pct / 100)
        else:
            stop_loss = entry_price * (1 + sl_pct / 100)
            target = entry_price * (1 - target_pct / 100)
        
        return round(stop_loss, 2), round(target, 2)
```

---

### 5. `src/news/news_agent.py` - Main Orchestrator

```python
"""
News Analysis Agent - Main Orchestrator
Coordinates RSS fetching, analysis, and alerting in event-driven manner.

THREAD SAFETY: Lock-free design following AlphaStocks architecture
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import uuid4

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, is_market_hours
from ..events.event_bus import EventBus, Event, EventType, EventPriority
from .rss_fetcher import RSSFetcher
from .llama_analyzer import LlamaAnalyzer
from .price_validator import PriceValidator
from .models import (
    NewsItem, NewsAnalysis, PriceValidation, NewsAlert,
    NewsImpactLevel, PriceAdjustmentStatus
)

logger = setup_logger("news_agent")


class NewsAgent:
    """
    Main News Analysis Agent that orchestrates:
    1. RSS feed fetching (every 5 minutes)
    2. News analysis via Llama
    3. Price validation via Zerodha
    4. Alert generation for opportunities
    
    Design Principles:
    - Lock-free using Counter for stats
    - Database for deduplication (no in-memory sets)
    - Event-driven communication via EventBus
    - Independent tasks for parallel processing
    """
    
    def __init__(self,
                 event_bus: EventBus,
                 data_layer,
                 kite_client=None,
                 config: Optional[Dict] = None):
        """
        Initialize News Agent.
        
        Args:
            event_bus: EventBus for publishing events
            data_layer: Database layer for persistence
            kite_client: Zerodha Kite client (optional)
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.data_layer = data_layer
        self.kite = kite_client
        
        # Configuration
        self.config = config or {}
        self.fetch_interval = self.config.get("fetch_interval_seconds", 300)  # 5 minutes
        self.enabled = self.config.get("enabled", True)
        self.market_hours_only = self.config.get("market_hours_only", True)
        
        # Initialize components
        self.rss_fetcher = RSSFetcher(
            timeout_seconds=self.config.get("rss_timeout", 30),
            max_concurrent=self.config.get("rss_max_concurrent", 5)
        )
        
        self.llama_analyzer = LlamaAnalyzer(
            base_url=self.config.get("llama_url", "http://localhost:11434"),
            model_name=self.config.get("llama_model", "llama3.2:latest"),
            timeout_seconds=self.config.get("llama_timeout", 60),
            max_concurrent=self.config.get("llama_max_concurrent", 3)
        )
        
        self.price_validator = None  # Initialized after historical cache available
        
        # Atomic statistics (lock-free)
        self.stats = Counter({
            "cycles_completed": 0,
            "news_fetched": 0,
            "news_analyzed": 0,
            "opportunities_found": 0,
            "alerts_generated": 0,
            "errors": 0,
        })
        
        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info("NewsAgent initialized")
    
    async def initialize(self, historical_cache):
        """
        Initialize components that require async setup.
        
        Args:
            historical_cache: HistoricalDataCache instance
        """
        self.price_validator = PriceValidator(
            data_layer=self.data_layer,
            historical_cache=historical_cache,
            kite_client=self.kite
        )
        
        # Check Llama health
        llama_healthy = await self.llama_analyzer.check_health()
        if not llama_healthy:
            logger.warning("Llama server not responding - news analysis will be limited")
        
        logger.info("NewsAgent initialization complete")
    
    async def start(self):
        """Start the news agent background task."""
        if self._running:
            logger.warning("NewsAgent already running")
            return
        
        if not self.enabled:
            logger.info("NewsAgent disabled in config")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"NewsAgent started - fetching every {self.fetch_interval}s")
    
    async def stop(self):
        """Stop the news agent."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("NewsAgent stopped")
    
    async def _run_loop(self):
        """Main agent loop - runs every fetch_interval seconds."""
        while self._running:
            try:
                # Check market hours if configured
                if self.market_hours_only and not is_market_hours():
                    logger.debug("Outside market hours, skipping news fetch")
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Run one cycle
                await self._run_cycle()
                self.stats["cycles_completed"] += 1
                
                # Wait for next cycle
                await asyncio.sleep(self.fetch_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error in news agent loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
    
    async def _run_cycle(self):
        """Run one complete news analysis cycle."""
        cycle_start = get_current_time()
        logger.info("Starting news analysis cycle")
        
        try:
            # Step 1: Fetch all RSS feeds
            news_items = await self.rss_fetcher.fetch_all_feeds()
            self.stats["news_fetched"] += len(news_items)
            
            if not news_items:
                logger.info("No news items fetched")
                return
            
            # Step 2: Filter new news (not already processed)
            new_items = await self._filter_new_news(news_items)
            logger.info(f"Found {len(new_items)} new news items out of {len(news_items)}")
            
            if not new_items:
                return
            
            # Step 3: Analyze with Llama (parallel)
            analyses = await self.llama_analyzer.analyze_batch(new_items)
            self.stats["news_analyzed"] += len(analyses)
            
            # Step 4: Filter high-impact news
            high_impact = [a for a in analyses if a.impact_level in [
                NewsImpactLevel.CRITICAL,
                NewsImpactLevel.HIGH
            ] and a.affected_stocks]
            
            logger.info(f"Found {len(high_impact)} high-impact news with affected stocks")
            
            # Step 5: Validate prices for affected stocks
            for analysis in high_impact:
                news_item = next(
                    (n for n in new_items if n.news_id == analysis.news_id),
                    None
                )
                if not news_item:
                    continue
                
                validations = await self.price_validator.validate_impact(
                    analysis=analysis,
                    news_published_time=news_item.published_date
                )
                
                # Step 6: Generate alerts for opportunities
                for validation in validations:
                    if validation.is_opportunity:
                        self.stats["opportunities_found"] += 1
                        await self._generate_alert(news_item, analysis, validation)
            
            # Step 7: Mark news as processed (store in DB)
            await self._mark_news_processed(new_items)
            
            cycle_duration = (get_current_time() - cycle_start).total_seconds()
            logger.info(
                f"News cycle completed in {cycle_duration:.2f}s: "
                f"fetched={len(news_items)}, new={len(new_items)}, "
                f"analyzed={len(analyses)}, high_impact={len(high_impact)}, "
                f"opportunities={self.stats['opportunities_found']}"
            )
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in news cycle: {e}", exc_info=True)
            raise
    
    async def _filter_new_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """
        Filter out already processed news using database.
        
        NOTE: Uses database query, NOT in-memory set (lock-free principle)
        """
        try:
            # Get processed news IDs from database
            processed_ids = await self.data_layer.get_processed_news_ids(
                [item.news_id for item in news_items]
            )
            processed_set = set(processed_ids)
            
            return [item for item in news_items if item.news_id not in processed_set]
            
        except Exception as e:
            logger.warning(f"Error checking processed news, returning all: {e}")
            return news_items
    
    async def _mark_news_processed(self, news_items: List[NewsItem]):
        """Mark news items as processed in database."""
        try:
            for item in news_items:
                await self.data_layer.store_processed_news(
                    news_id=item.news_id,
                    title=item.title,
                    source_feed=item.source_feed,
                    published_date=item.published_date,
                    processed_date=get_current_time()
                )
        except Exception as e:
            logger.error(f"Error marking news as processed: {e}")
    
    async def _generate_alert(self,
                              news_item: NewsItem,
                              analysis: NewsAnalysis,
                              validation: PriceValidation):
        """Generate and publish trading opportunity alert."""
        
        alert = NewsAlert(
            alert_id=str(uuid4())[:16],
            news_id=news_item.news_id,
            symbol=validation.symbol,
            alert_type="opportunity",
            priority="high" if analysis.impact_level == NewsImpactLevel.CRITICAL else "medium",
            news_title=news_item.title,
            news_summary=analysis.analysis_summary,
            sentiment=analysis.sentiment,
            expected_direction=analysis.expected_direction,
            expected_move_pct=analysis.expected_move_pct,
            current_price=validation.current_price,
            recommended_action=validation.recommended_action,
            entry_price=validation.entry_price,
            stop_loss=validation.stop_loss,
            target=validation.target,
            created_at=get_current_time(),
            valid_until=get_current_time() + timedelta(hours=2)
        )
        
        self.stats["alerts_generated"] += 1
        
        # Log the alert prominently
        logger.warning(
            f"🚨 TRADING ALERT: {alert.recommended_action} {alert.symbol}\n"
            f"   News: {alert.news_title[:80]}...\n"
            f"   Entry: {alert.entry_price}, SL: {alert.stop_loss}, Target: {alert.target}\n"
            f"   Expected Move: {alert.expected_move_pct:.1f}% {alert.expected_direction}\n"
            f"   Sentiment: {alert.sentiment.value}"
        )
        
        # Publish event for other components (notifications, order execution)
        await self.event_bus.publish(Event(
            event_type=EventType.NEWS_ALERT_GENERATED,  # Add to EventType enum
            data={
                "alert_id": alert.alert_id,
                "news_id": alert.news_id,
                "symbol": alert.symbol,
                "action": alert.recommended_action,
                "entry_price": alert.entry_price,
                "stop_loss": alert.stop_loss,
                "target": alert.target,
                "sentiment": alert.sentiment.value,
                "expected_move_pct": alert.expected_move_pct,
                "news_title": alert.news_title,
                "valid_until": alert.valid_until.isoformat(),
            },
            priority=EventPriority.HIGH,
            source="news_agent"
        ))
        
        # Store alert in database
        await self._store_alert(alert)
    
    async def _store_alert(self, alert: NewsAlert):
        """Store alert in database for history."""
        try:
            await self.data_layer.store_news_alert(
                alert_id=alert.alert_id,
                news_id=alert.news_id,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                priority=alert.priority,
                recommended_action=alert.recommended_action,
                entry_price=alert.entry_price,
                stop_loss=alert.stop_loss,
                target=alert.target,
                created_at=alert.created_at,
                valid_until=alert.valid_until
            )
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get agent statistics."""
        return dict(self.stats)
    
    async def run_once(self) -> Dict:
        """
        Run a single analysis cycle (for testing).
        
        Returns:
            Dict with cycle results
        """
        await self._run_cycle()
        return self.get_stats()
```

---

### 6. Event Type Extension

Add to `src/events/event_bus.py` EventType enum:

```python
# Add these to EventType enum:
    
    # News Events
    NEWS_FETCHED = "news.fetched"
    NEWS_ANALYZED = "news.analyzed"
    NEWS_ALERT_GENERATED = "news.alert_generated"
    NEWS_OPPORTUNITY_FOUND = "news.opportunity_found"
```

---

### 7. Database Schema Extension

Add to ClickHouse data layer:

```python
# Tables for news agent

CREATE TABLE IF NOT EXISTS processed_news (
    news_id String,
    title String,
    source_feed String,
    published_date DateTime64(3),
    processed_date DateTime64(3),
    PRIMARY KEY (news_id)
) ENGINE = MergeTree()
ORDER BY (processed_date, news_id);

CREATE TABLE IF NOT EXISTS news_analyses (
    news_id String,
    impact_level String,
    sentiment String,
    confidence_score Float32,
    affected_industries Array(String),
    affected_stocks Array(String),
    expected_direction String,
    expected_move_pct Float32,
    analysis_timestamp DateTime64(3),
    PRIMARY KEY (news_id)
) ENGINE = MergeTree()
ORDER BY (analysis_timestamp, news_id);

CREATE TABLE IF NOT EXISTS news_alerts (
    alert_id String,
    news_id String,
    symbol String,
    alert_type String,
    priority String,
    recommended_action String,
    entry_price Float64,
    stop_loss Float64,
    target Float64,
    created_at DateTime64(3),
    valid_until DateTime64(3),
    executed Boolean DEFAULT false,
    PRIMARY KEY (alert_id)
) ENGINE = MergeTree()
ORDER BY (created_at, alert_id);
```

---

### 8. Configuration File `config/news_agent.json`

```json
{
    "enabled": true,
    "fetch_interval_seconds": 300,
    "market_hours_only": true,
    
    "rss": {
        "timeout_seconds": 30,
        "max_concurrent_feeds": 5,
        "user_agent": "AlphaStocks NewsAgent/1.0"
    },
    
    "llama": {
        "base_url": "http://localhost:11434",
        "model_name": "llama3.2:latest",
        "timeout_seconds": 60,
        "max_concurrent_analyses": 3
    },
    
    "price_validation": {
        "min_move_for_impact_pct": 0.5,
        "volume_spike_ratio": 2.0,
        "lookback_periods": 20,
        "max_news_age_hours": 4
    },
    
    "alerting": {
        "min_impact_level": "high",
        "min_expected_move_pct": 0.5,
        "alert_valid_hours": 2
    },
    
    "logging": {
        "level": "INFO",
        "log_file": "logs/news_agent.log"
    }
}
```

---

## 🧪 Testing Requirements

### Unit Tests

Each module must have comprehensive unit tests:

```python
# tests/test_news_agent/test_rss_fetcher.py
class TestRSSFetcher:
    async def test_fetch_all_feeds_parallel(self):
        """Test that all 13 feeds are fetched in parallel."""
        
    async def test_parse_feed_entries(self):
        """Test RSS entry parsing to NewsItem."""
        
    async def test_generate_unique_news_id(self):
        """Test news ID generation is deterministic."""
        
    async def test_handle_feed_timeout(self):
        """Test graceful handling of feed timeout."""
        
    async def test_handle_malformed_feed(self):
        """Test handling of malformed RSS XML."""


# tests/test_news_agent/test_llama_analyzer.py
class TestLlamaAnalyzer:
    async def test_analyze_news_returns_structured_response(self):
        """Test Llama returns proper NewsAnalysis."""
        
    async def test_fallback_on_json_parse_error(self):
        """Test keyword-based fallback when JSON fails."""
        
    async def test_batch_analysis_parallel(self):
        """Test batch analysis runs in parallel."""
        
    async def test_health_check(self):
        """Test Llama server health check."""


# tests/test_news_agent/test_price_validator.py
class TestPriceValidator:
    async def test_detect_unadjusted_price(self):
        """Test detection of price not yet adjusted to news."""
        
    async def test_detect_fully_adjusted(self):
        """Test detection of already adjusted price."""
        
    async def test_volume_spike_detection(self):
        """Test unusual volume detection."""
        
    async def test_calculate_sl_target(self):
        """Test stop loss and target calculation."""


# tests/test_news_agent/test_news_agent_integration.py
class TestNewsAgentIntegration:
    async def test_full_cycle_end_to_end(self):
        """Test complete news analysis cycle."""
        
    async def test_deduplication_via_database(self):
        """Test news deduplication uses DB, not memory."""
        
    async def test_event_bus_integration(self):
        """Test events are published correctly."""
```

### Running Tests

```bash
# Run all news agent tests
python -m pytest tests/test_news_agent/ -v

# Run with coverage
python -m pytest tests/test_news_agent/ --cov=src/news --cov-report=html

# Run single test file
python -m pytest tests/test_news_agent/test_rss_fetcher.py -v
```

---

## 📊 Logging Standards

### Log Levels

- **ERROR**: Failed operations, exceptions
- **WARNING**: Trading alerts (🚨), degraded functionality
- **INFO**: Cycle starts/completions, statistics
- **DEBUG**: Individual news processing, price checks

### Log Format

```python
# Example log output
2025-01-19 10:15:00 IST | INFO | news_agent | Starting news analysis cycle
2025-01-19 10:15:02 IST | INFO | rss_fetcher | Fetched 47 items from 13 feeds in 1.82s
2025-01-19 10:15:15 IST | INFO | llama_analyzer | Analyzed news abc12345: impact=high, sentiment=bullish, stocks=['HDFCBANK']
2025-01-19 10:15:16 IST | INFO | price_validator | OPPORTUNITY: HDFCBANK - BUY @ 1645.50, remaining move: 1.2%
2025-01-19 10:15:16 IST | WARNING | news_agent | 🚨 TRADING ALERT: BUY HDFCBANK
   News: HDFC Bank reports 20% growth in retail loans...
   Entry: 1645.50, SL: 1637.25, Target: 1665.20
   Expected Move: 1.2% UP
   Sentiment: bullish
```

---

## 🔌 Integration with AlphaStocks

### Orchestrator Integration

Add to `src/orchestrator.py`:

```python
from src.news.news_agent import NewsAgent

class AlphaStockOrchestrator:
    async def initialize(self):
        # ... existing code ...
        
        # Initialize News Agent
        news_config = self._load_news_config()
        self.news_agent = NewsAgent(
            event_bus=self.event_bus,
            data_layer=self.data_layer,
            kite_client=self.kite,
            config=news_config
        )
        await self.news_agent.initialize(self.historical_cache)
    
    async def start(self):
        # ... existing code ...
        
        # Start News Agent
        await self.news_agent.start()
    
    async def stop(self):
        # Stop News Agent
        await self.news_agent.stop()
        
        # ... existing code ...
```

### Alert Subscriber Example

```python
# Subscribe to news alerts for order execution
async def _on_news_alert(self, event: Event):
    """Handle news-based trading opportunities."""
    symbol = event.data["symbol"]
    action = event.data["action"]
    entry_price = event.data["entry_price"]
    
    logger.info(f"Received news alert: {action} {symbol} @ {entry_price}")
    
    # Your order execution logic here
    # await self.place_order(symbol, action, entry_price, ...)

# In initialization:
self.event_bus.subscribe(
    EventType.NEWS_ALERT_GENERATED,
    self._on_news_alert,
    "order_executor"
)
```

---

## 📦 Dependencies

Add to `requirements.txt`:

```
feedparser>=6.0.10
aiohttp>=3.9.0
```

For Llama local server (Ollama recommended):

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Llama model
ollama pull llama3.2:latest

# Start server (default port 11434)
ollama serve
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install feedparser aiohttp

# 2. Start Ollama with Llama model
ollama serve &
ollama pull llama3.2:latest

# 3. Run tests
python -m pytest tests/test_news_agent/ -v

# 4. Start system with news agent
python main.py
```

---

## Pre-Implementation Checklist

- [ ] Read `.copilot-design-principles.md` for lock-free patterns
- [ ] Read `docs/LOCK_FREE_ARCHITECTURE.md` for concurrency guidelines
- [ ] Read `docs/TIMEZONE_STANDARD.md` for IST requirements
- [ ] Ensure Ollama is installed and running locally
- [ ] Verify Zerodha APIs are working (`python cli.py auth`)
- [ ] Create all 13 RSS feed constants (DO NOT SKIP ANY)
- [ ] Implement database schema for news tables
- [ ] Write comprehensive tests for each module

---

**Last Updated**: January 19, 2026  
**Author**: GitHub Copilot Agent Instructions  
**Status**: Ready for Implementation ✅
