"""
News Analysis Agent - Main Orchestrator
Coordinates RSS fetching, analysis, and alerting in event-driven manner.

THREAD SAFETY: Lock-free design following AlphaStocks architecture
- Uses Counter for atomic statistics
- Database for deduplication (no in-memory sets)
- Event-driven communication via EventBus
- Independent tasks for parallel processing
"""

import asyncio
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, is_market_hours
from .rss_fetcher import RSSFetcher
from .llama_analyzer import LlamaAnalyzer
from .price_validator import PriceValidator
from .telegram_notifier import TelegramNotifier
from .news_data_helper import NewsDataHelper
from .models import (
    NewsItem, NewsAnalysis, PriceValidation, NewsAlert,
    NewsImpactLevel, PriceAdjustmentStatus, NewsSentiment
)

logger = setup_logger("news_agent")


class NewsAgent:
    """
    Main News Analysis Agent that orchestrates:
    1. RSS feed fetching (every 5 minutes by default)
    2. News analysis via local Llama model
    3. Price validation via Zerodha APIs
    4. Alert generation for trading opportunities
    
    Design Principles:
    - Lock-free using Counter for stats
    - Database for deduplication (no in-memory sets)
    - Event-driven communication via EventBus
    - Independent tasks for parallel processing
    - Fully testable with dependency injection
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "enabled": True,
        "fetch_interval_seconds": 300,  # 5 minutes
        "market_hours_only": True,
        "min_impact_level": "high",     # Minimum impact to validate prices
        "alert_valid_hours": 2,
        
        # RSS settings
        "rss_timeout": 30,
        "rss_max_concurrent": 5,
        
        # Llama settings
        "llama_url": "http://localhost:11434",
        "llama_model": "llama3.2:latest",
        "llama_timeout": 60,
        "llama_max_concurrent": 3,
        
        # Analysis settings
        "analyze_all_news": False,      # If True, analyze all news, not just new
        "max_news_age_hours": 24,       # Max age of news to process
        "validate_price_impact": True,  # If False, skip price validation step
    }
    
    def __init__(self,
                 event_bus=None,
                 data_layer=None,
                 kite_client=None,
                 config: Optional[Dict] = None,
                 rss_fetcher: Optional[RSSFetcher] = None,
                 llama_analyzer: Optional[LlamaAnalyzer] = None,
                 price_validator: Optional[PriceValidator] = None,
                 telegram_notifier: Optional[TelegramNotifier] = None):
        """
        Initialize News Agent.
        
        Args:
            event_bus: EventBus for publishing events (optional)
            data_layer: Database layer for persistence (optional)
            kite_client: Zerodha Kite client (optional)
            config: Configuration dictionary (optional)
            rss_fetcher: Custom RSS fetcher (for testing)
            llama_analyzer: Custom Llama analyzer (for testing)
            price_validator: Custom price validator (for testing)
            telegram_notifier: Custom Telegram notifier (for testing)
        """
        self.event_bus = event_bus
        self.data_layer = data_layer
        self.kite = kite_client
        
        # Merge config with defaults
        self.config = dict(self.DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        
        # Initialize or use provided components
        # Get RSS feeds from config
        rss_config = self.config.get("rss", {})
        rss_feeds = rss_config.get("feeds", {})
        
        if not rss_feeds:
            raise ValueError("No RSS feeds configured in config['rss']['feeds']")
        
        self.rss_fetcher = rss_fetcher or RSSFetcher(
            feeds=rss_feeds,
            timeout_seconds=rss_config.get("timeout_seconds", 30),
            max_concurrent=rss_config.get("max_concurrent_feeds", 5),
            user_agent=rss_config.get("user_agent"),
            scrape_full_articles=self.config.get("scrape_full_articles", False)
        )
        
        # Get Llama config
        llama_config = self.config.get("llama", {})
        self.llama_analyzer = llama_analyzer or LlamaAnalyzer(
            base_url=llama_config.get("base_url", "http://localhost:11434"),
            model_name=llama_config.get("model_name", "llama3.2:latest"),
            timeout_seconds=llama_config.get("timeout_seconds", 60),
            max_concurrent=llama_config.get("max_concurrent_analyses", 3),
            temperature=llama_config.get("temperature", 0.3),
            api_type=llama_config.get("api_type", "ollama"),
            api_key=llama_config.get("api_key", None),
            rate_limit_delay=llama_config.get("rate_limit_delay_seconds", 0.0)
        )
        
        self.price_validator = price_validator  # Initialized later with historical cache
        
        # Initialize Telegram notifier
        telegram_config = self.config.get("telegram", {})
        self.telegram = telegram_notifier or TelegramNotifier(
            bot_token=telegram_config.get("bot_token", ""),
            chat_id=telegram_config.get("chat_id", ""),
            enabled=telegram_config.get("enabled", False),
            parse_mode=telegram_config.get("parse_mode", "HTML"),
            timeout_seconds=telegram_config.get("timeout_seconds", 10)
        )
        
        # News data helper for deduplication and storage
        self.news_data_helper = NewsDataHelper(data_layer=data_layer)
        
        # Atomic statistics (lock-free)
        self.stats = Counter({
            "cycles_completed": 0,
            "news_fetched": 0,
            "news_new": 0,
            "news_analyzed": 0,
            "high_impact_news": 0,
            "opportunities_found": 0,
            "alerts_generated": 0,
            "errors": 0,
        })
        
        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._initialized = False
        
        # Alerts storage (for retrieval)
        self._recent_alerts: List[NewsAlert] = []
        self._max_alerts = 100
        
        logger.info("NewsAgent created")
    
    async def initialize(self, historical_cache=None):
        """
        Initialize components that require async setup.
        
        Args:
            historical_cache: HistoricalDataCache instance (optional)
        """
        if self._initialized:
            logger.debug("NewsAgent already initialized")
            return
        
        # Initialize price validator if not provided
        if self.price_validator is None:
            self.price_validator = PriceValidator(
                data_layer=self.data_layer,
                historical_cache=historical_cache,
                kite_client=self.kite,
                config=self.config.get("price_validation", {})
            )
        
        # Check Llama health
        llama_healthy = await self.llama_analyzer.check_health()
        if llama_healthy:
            logger.info("Llama server is healthy")
            models = await self.llama_analyzer.list_models()
            logger.info(f"Available models: {models}")
        else:
            logger.warning("Llama server not responding - news analysis will use fallback")
        
        # Initialize news data helper
        await self.news_data_helper.initialize()
        logger.info("News data helper initialized")
        
        self._initialized = True
        logger.info("NewsAgent initialization complete")
    
    async def start(self):
        """Start the news agent background task."""
        if self._running:
            logger.warning("NewsAgent already running")
            return
        
        if not self.config.get("enabled", True):
            logger.info("NewsAgent disabled in config")
            return
        
        if not self._initialized:
            await self.initialize()
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        
        fetch_interval = self.config.get("fetch_interval_seconds", 300)
        logger.info(f"NewsAgent started - fetching every {fetch_interval}s")
    
    async def stop(self):
        """Stop the news agent."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("NewsAgent stopped")
    
    async def _run_loop(self):
        """Main agent loop - runs every fetch_interval seconds."""
        fetch_interval = self.config.get("fetch_interval_seconds", 300)
        
        while self._running:
            try:
                # Check market hours if configured
                if self.config.get("market_hours_only", True) and not is_market_hours():
                    current_time = get_current_time()
                    market_open = get_today_market_open()
                    market_close = get_today_market_close()
                    logger.info(f"Outside market hours (Current: {current_time.strftime('%H:%M')}, Market: {market_open.strftime('%H:%M')}-{market_close.strftime('%H:%M')}), checking again in 60s")
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Run one cycle
                await self._run_cycle()
                self.stats["cycles_completed"] += 1
                
                # Wait for next cycle
                await asyncio.sleep(fetch_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error in news agent loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
    
    async def _run_cycle(self) -> Dict[str, Any]:
        """
        Run one complete news analysis cycle.
        
        Returns:
            Dict with cycle results
        """
        cycle_start = get_current_time()
        cycle_results = {
            "fetched": 0,
            "new": 0,
            "analyzed": 0,
            "high_impact": 0,
            "opportunities": 0,
            "alerts": 0,
            "duration_seconds": 0,
        }
        
        logger.info("Starting news analysis cycle")
        
        try:
            # Step 1: Fetch all RSS feeds
            news_items = await self.rss_fetcher.fetch_all_feeds()
            cycle_results["fetched"] = len(news_items)
            self.stats["news_fetched"] += len(news_items)
            
            if not news_items:
                logger.info("No news items fetched")
                return cycle_results
            
            # Step 2: Filter new news (not already processed)
            new_items = await self._filter_new_news(news_items)
            cycle_results["new"] = len(new_items)
            self.stats["news_new"] += len(new_items)
            
            logger.info(f"Found {len(new_items)} new news items out of {len(news_items)}")
            
            if not new_items:
                return cycle_results
            
            # Step 2.5: Scrape full articles for NEW news only (if enabled)
            if self.config.get("scrape_full_articles", False):
                logger.info(f"Scraping {len(new_items)} new articles...")
                scrape_tasks = []
                for item in new_items:
                    if not item.raw_content:  # Only scrape if no content yet
                        scrape_tasks.append(self._scrape_and_update(item))
                
                if scrape_tasks:
                    await asyncio.gather(*scrape_tasks, return_exceptions=True)
            
            # Step 3: Filter by age
            max_age_hours = self.config.get("max_news_age_hours", 24)
            cutoff_time = get_current_time() - timedelta(hours=max_age_hours)
            
            # Log date range before filtering
            items_before_filter = len(new_items)
            if new_items:
                dates = [n.published_date for n in new_items]
                oldest = min(dates)
                newest = max(dates)
                logger.info(f"News date range: {oldest.strftime('%Y-%m-%d %H:%M')} to {newest.strftime('%Y-%m-%d %H:%M')}")
                logger.info(f"Cutoff time: {cutoff_time.strftime('%Y-%m-%d %H:%M')} (max age: {max_age_hours}h)")
            
            new_items = [n for n in new_items if n.published_date >= cutoff_time]
            
            if not new_items:
                logger.info(f"No recent news to analyze (all {items_before_filter} items older than {max_age_hours}h)")
                return cycle_results
            
            logger.info(f"Filtered to {len(new_items)} news items within {max_age_hours}h age limit")
            
            # Step 4: Process each news item immediately after analysis
            # This ensures real-time alerting without waiting for batch completion
            min_impact = self.config.get("min_impact_level", "high")
            impact_levels = self._get_impact_levels(min_impact)
            
            # Process news items concurrently but with immediate alerting
            tasks = [
                self._analyze_and_alert(news_item, impact_levels, cycle_results)
                for news_item in new_items
            ]
            
            # Run all analyses in parallel, each will alert immediately when done
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark news as processed (store in DB)
            await self._mark_news_processed(new_items)
            # Run all analyses in parallel, each will alert immediately when done
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark news as processed (store in DB)
            await self._mark_news_processed(new_items)
            
            cycle_duration = (get_current_time() - cycle_start).total_seconds()
            cycle_results["duration_seconds"] = round(cycle_duration, 2)
            
            logger.info(
                f"News cycle completed in {cycle_duration:.2f}s: "
                f"fetched={cycle_results['fetched']}, new={cycle_results['new']}, "
                f"analyzed={cycle_results['analyzed']}, high_impact={cycle_results['high_impact']}, "
                f"opportunities={cycle_results['opportunities']}, alerts={cycle_results['alerts']}"
            )
            
            return cycle_results
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in news cycle: {e}", exc_info=True)
            raise
    
    def _get_impact_levels(self, min_level: str) -> List[NewsImpactLevel]:
        """Get impact levels at or above minimum."""
        level_order = [
            NewsImpactLevel.CRITICAL,
            NewsImpactLevel.HIGH,
            NewsImpactLevel.MEDIUM,
            NewsImpactLevel.LOW,
            NewsImpactLevel.NEUTRAL,
        ]
        
        try:
            min_idx = next(
                i for i, l in enumerate(level_order) 
                if l.value == min_level.lower()
            )
            return level_order[:min_idx + 1]
        except StopIteration:
            return [NewsImpactLevel.CRITICAL, NewsImpactLevel.HIGH]
    
    async def _analyze_and_alert(self, 
                                 news_item: NewsItem, 
                                 impact_levels: List[NewsImpactLevel],
                                 cycle_results: Dict) -> None:
        """
        Analyze a single news item and immediately generate alerts if high-impact.
        This enables real-time alerting without waiting for batch completion.
        
        Args:
            news_item: News item to analyze
            impact_levels: Impact levels to filter (e.g., [HIGH, CRITICAL])
            cycle_results: Shared results dict for tracking
        """
        try:
            # Step 1: Analyze with Llama
            analysis = await self.llama_analyzer.analyze_news(news_item)
            
            if not analysis:
                return
            
            # Update stats
            cycle_results["analyzed"] += 1
            self.stats["news_analyzed"] += 1
            
            # Step 2: Store analysis in database
            await self.news_data_helper.store_news_analysis(analysis.to_dict())
            
            # Step 3: Check if high-impact
            if analysis.impact_level not in impact_levels or not analysis.affected_stocks:
                return
            
            cycle_results["high_impact"] += 1
            self.stats["high_impact_news"] += 1
            
            logger.info(
                f"High-impact news detected: {news_item.title[:50]}... "
                f"(impact={analysis.impact_level.value}, stocks={len(analysis.affected_stocks)})"
            )
            
            # Step 4: Validate prices and generate alerts (if enabled)
            if self.config.get("validate_price_impact", True):
                if self.price_validator:
                    validations = await self.price_validator.validate_impact(
                        analysis=analysis,
                        news_published_time=news_item.published_date
                    )
                    
                    # Generate alerts for opportunities
                    for validation in validations:
                        if validation.is_opportunity:
                            cycle_results["opportunities"] += 1
                            self.stats["opportunities_found"] += 1
                            
                            alert = await self._generate_alert(
                                news_item, analysis, validation
                            )
                            if alert:
                                cycle_results["alerts"] += 1
            else:
                # Generate alert directly without price validation
                alert = await self._generate_alert_without_validation(
                    news_item, analysis
                )
                if alert:
                    cycle_results["alerts"] += 1
                    
        except Exception as e:
            logger.error(f"Error analyzing news {news_item.news_id}: {e}", exc_info=True)
    
    async def _filter_new_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """
        Filter out already processed news using database/helper.
        
        NOTE: Uses NewsDataHelper for deduplication (lock-free principle)
        """
        if self.config.get("analyze_all_news", False):
            return news_items
        
        try:
            # Filter using news data helper
            new_items = []
            for item in news_items:
                is_processed = await self.news_data_helper.is_news_processed(item.news_id)
                if not is_processed:
                    new_items.append(item)
            
            return new_items
            
        except Exception as e:
            logger.warning(f"Error checking processed news, returning all: {e}")
            return news_items
    
    async def _scrape_and_update(self, news_item: NewsItem):
        """Scrape article content and update the news item."""
        try:
            content = await self.rss_fetcher.scrape_article(news_item)
            if content:
                # Create new NewsItem with scraped content (NewsItem is immutable)
                updated_item = NewsItem(
                    news_id=news_item.news_id,
                    title=news_item.title,
                    description=news_item.description,
                    link=news_item.link,
                    published_date=news_item.published_date,
                    source_feed=news_item.source_feed,
                    raw_content=content,
                    fetch_timestamp=news_item.fetch_timestamp
                )
                logger.info(f"Scraped article: {news_item.link[:60]}... ({len(content)} chars)")
                return updated_item
        except Exception as e:
            logger.warning(f"Failed to scrape article {news_item.link[:60]}: {e}")
        return news_item
    
    async def _mark_news_processed(self, news_items: List[NewsItem]):
        """Mark news items as processed using data helper."""
        try:
            for item in news_items:
                await self.news_data_helper.mark_news_processed(
                    news_id=item.news_id,
                    news_data={
                        "title": item.title,
                        "source_feed": item.source_feed,
                        "published_date": item.published_date,
                        "link": item.link
                    }
                )
        except Exception as e:
            logger.error(f"Error marking news as processed: {e}")
    
    async def _store_analyses(self, analyses: List[NewsAnalysis]):
        """Store news analyses using data helper."""
        try:
            for analysis in analyses:
                await self.news_data_helper.store_news_analysis({
                    "news_id": analysis.news_id,
                    "impact_level": analysis.impact_level.value,
                    "sentiment": analysis.sentiment.value,
                    "confidence_score": analysis.confidence_score,
                    "affected_stocks": analysis.affected_stocks,
                    "expected_direction": analysis.expected_direction,
                    "expected_move_pct": analysis.expected_move_pct,
                    "analysis_timestamp": analysis.analysis_timestamp
                })
        except Exception as e:
            logger.error(f"Error storing analyses: {e}")
    
    async def _generate_alert(self,
                              news_item: NewsItem,
                              analysis: NewsAnalysis,
                              validation: PriceValidation) -> Optional[NewsAlert]:
        """Generate and publish trading opportunity alert."""
        
        try:
            alert = NewsAlert(
                alert_id=str(uuid4())[:16],
                news_id=news_item.news_id,
                symbol=validation.symbol,
                alert_type="opportunity",
                priority="critical" if analysis.impact_level == NewsImpactLevel.CRITICAL else "high",
                news_title=news_item.title,
                news_summary=analysis.analysis_summary or news_item.description[:200],
                sentiment=analysis.sentiment,
                expected_direction=analysis.expected_direction,
                expected_move_pct=analysis.expected_move_pct,
                current_price=validation.current_price,
                recommended_action=validation.recommended_action or "HOLD",
                entry_price=validation.entry_price or validation.current_price,
                stop_loss=validation.stop_loss or 0.0,
                target=validation.target or 0.0,
                created_at=get_current_time(),
                valid_until=get_current_time() + timedelta(
                    hours=self.config.get("alert_valid_hours", 2)
                )
            )
            
            self.stats["alerts_generated"] += 1
            
            # Store in recent alerts
            self._recent_alerts.append(alert)
            if len(self._recent_alerts) > self._max_alerts:
                self._recent_alerts = self._recent_alerts[-self._max_alerts:]
            
            # Log the alert prominently
            logger.warning(alert.format_alert_message())
            
            # Send Telegram notification
            await self._send_telegram_notification(alert, analysis)
            
            # Publish event for other components (notifications, order execution)
            await self._publish_alert_event(alert)
            
            # Store alert in database
            await self._store_alert(alert)
            
            return alert
            
        except Exception as e:
            logger.error(f"Error generating alert: {e}")
            return None
    
    async def _generate_alert_without_validation(self,
                                                  news_item: NewsItem,
                                                  analysis: NewsAnalysis) -> Optional[NewsAlert]:
        """Generate alert without price validation (for news-only mode)."""
        
        try:
            # Use first affected stock for alert
            symbol = analysis.affected_stocks[0] if analysis.affected_stocks else "MARKET"
            
            alert = NewsAlert(
                alert_id=str(uuid4())[:16],
                news_id=news_item.news_id,
                symbol=symbol,
                alert_type="news_impact",
                priority="critical" if analysis.impact_level == NewsImpactLevel.CRITICAL else "high",
                news_title=news_item.title,
                news_summary=analysis.analysis_summary or news_item.description[:200],
                sentiment=analysis.sentiment,
                expected_direction=analysis.expected_direction,
                expected_move_pct=analysis.expected_move_pct,
                current_price=0.0,  # Unknown without validation
                recommended_action="WATCH" if analysis.expected_direction == "SIDEWAYS" else (
                    "BUY" if analysis.expected_direction == "UP" else "SELL"
                ),
                entry_price=0.0,
                stop_loss=0.0,
                target=0.0,
                created_at=get_current_time(),
                valid_until=get_current_time() + timedelta(
                    hours=self.config.get("alert_valid_hours", 2)
                )
            )
            
            self.stats["alerts_generated"] += 1
            
            # Store in recent alerts
            self._recent_alerts.append(alert)
            if len(self._recent_alerts) > self._max_alerts:
                self._recent_alerts = self._recent_alerts[-self._max_alerts:]
            
            # Log the alert prominently
            logger.warning(alert.format_alert_message())
            
            # Send Telegram notification
            await self._send_telegram_notification(alert, analysis)
            
            # Publish event
            await self._publish_alert_event(alert)
            
            # Store in database
            await self.news_data_helper.store_news_alert(alert.to_dict())
            
            return alert
            
        except Exception as e:
            logger.error(f"Error generating alert without validation: {e}")
            return None
    
    async def _send_telegram_notification(self, alert: NewsAlert, analysis: NewsAnalysis):
        """Send Telegram notification for news alert."""
        try:
            if self.telegram.enabled:
                success = await self.telegram.send_news_alert(alert, analysis)
                if success:
                    logger.info(f"Telegram notification sent for alert {alert.alert_id[:8]}")
                else:
                    logger.warning(f"Failed to send Telegram notification for alert {alert.alert_id[:8]}")
            else:
                logger.debug("Telegram notifications disabled")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", exc_info=True)
    
    async def _publish_alert_event(self, alert: NewsAlert):
        """Publish alert event to EventBus."""
        if not self.event_bus:
            return
        
        try:
            # Import here to avoid circular imports
            from ..events.event_bus import Event, EventType, EventPriority
            
            # Check if NEWS_ALERT_GENERATED exists in EventType
            event_type = getattr(EventType, 'NEWS_ALERT_GENERATED', None)
            if event_type is None:
                logger.debug("NEWS_ALERT_GENERATED event type not found")
                return
            
            event = Event(
                event_type=event_type,
                data=alert.to_dict(),
                priority=EventPriority.HIGH,
                source="news_agent"
            )
            
            await self.event_bus.publish(event)
            logger.debug(f"Published alert event: {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error publishing alert event: {e}")
    
    async def _store_alert(self, alert: NewsAlert):
        """Store alert in database for history."""
        if not self.data_layer:
            return
        
        if not hasattr(self.data_layer, 'store_news_alert'):
            return
        
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
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = Counter({
            "cycles_completed": 0,
            "news_fetched": 0,
            "news_new": 0,
            "news_analyzed": 0,
            "high_impact_news": 0,
            "opportunities_found": 0,
            "alerts_generated": 0,
            "errors": 0,
        })
    
    def get_recent_alerts(self, limit: int = 10) -> List[NewsAlert]:
        """
        Get recent alerts.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent NewsAlert objects
        """
        return self._recent_alerts[-limit:]
    
    def get_valid_alerts(self) -> List[NewsAlert]:
        """
        Get currently valid alerts.
        
        Returns:
            List of valid (not expired) NewsAlert objects
        """
        return [a for a in self._recent_alerts if a.is_valid()]
    
    async def run_once(self) -> Dict[str, Any]:
        """
        Run a single analysis cycle (for testing or manual trigger).
        
        Returns:
            Dict with cycle results
        """
        if not self._initialized:
            await self.initialize()
        
        return await self._run_cycle()
    
    async def analyze_news_item(self, news_item: NewsItem) -> Optional[NewsAnalysis]:
        """
        Analyze a single news item (for testing).
        
        Args:
            news_item: NewsItem to analyze
            
        Returns:
            NewsAnalysis or None
        """
        return await self.llama_analyzer.analyze_news(news_item)
    
    async def fetch_feeds_only(self) -> List[NewsItem]:
        """
        Fetch news without analyzing (for testing).
        
        Returns:
            List of NewsItem objects
        """
        return await self.rss_fetcher.fetch_all_feeds()
    
    def is_running(self) -> bool:
        """Check if agent is currently running."""
        return self._running
    
    def is_initialized(self) -> bool:
        """Check if agent is initialized."""
        return self._initialized
    
    @classmethod
    def from_config_file(cls, 
                         config_path: str,
                         event_bus=None,
                         data_layer=None,
                         kite_client=None) -> 'NewsAgent':
        """
        Create NewsAgent from configuration file.
        
        Args:
            config_path: Path to JSON config file
            event_bus: EventBus instance
            data_layer: Database layer
            kite_client: Zerodha Kite client
            
        Returns:
            NewsAgent instance
        """
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            config = {}
        
        return cls(
            event_bus=event_bus,
            data_layer=data_layer,
            kite_client=kite_client,
            config=config
        )
