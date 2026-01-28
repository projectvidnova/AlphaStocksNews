"""
Integration Tests for News Agent Module
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.news.news_agent import NewsAgent
from src.news.rss_fetcher import RSSFetcher
from src.news.llama_analyzer import LlamaAnalyzer
from src.news.price_validator import PriceValidator
from src.news.models import (
    NewsItem, NewsAnalysis, NewsAlert,
    NewsImpactLevel, NewsSentiment, PriceAdjustmentStatus
)
from src.utils.timezone_utils import get_current_time


class TestNewsAgentUnit:
    """Unit tests for NewsAgent class."""
    
    @pytest.fixture
    def mock_rss_fetcher(self):
        """Create a mock RSS fetcher."""
        fetcher = MagicMock(spec=RSSFetcher)
        fetcher.fetch_all_feeds = AsyncMock(return_value=[])
        fetcher.get_stats = MagicMock(return_value={"feeds_fetched": 0})
        return fetcher
    
    @pytest.fixture
    def mock_llama_analyzer(self):
        """Create a mock Llama analyzer."""
        analyzer = MagicMock(spec=LlamaAnalyzer)
        analyzer.analyze_batch = AsyncMock(return_value=[])
        analyzer.check_health = AsyncMock(return_value=True)
        analyzer.list_models = AsyncMock(return_value=["llama3.2:latest"])
        return analyzer
    
    @pytest.fixture
    def mock_price_validator(self):
        """Create a mock price validator."""
        validator = MagicMock(spec=PriceValidator)
        validator.validate_impact = AsyncMock(return_value=[])
        return validator
    
    @pytest.fixture
    def agent(self, mock_rss_fetcher, mock_llama_analyzer, mock_price_validator):
        """Create a NewsAgent with mocked dependencies."""
        return NewsAgent(
            event_bus=None,
            data_layer=None,
            kite_client=None,
            config={"enabled": True, "market_hours_only": False},
            rss_fetcher=mock_rss_fetcher,
            llama_analyzer=mock_llama_analyzer,
            price_validator=mock_price_validator
        )
    
    def test_init(self, agent):
        """Test NewsAgent initialization."""
        assert agent is not None
        assert agent.config["enabled"] == True
        assert agent.is_running() == False
    
    def test_default_config(self):
        """Test default configuration is applied."""
        agent = NewsAgent()
        assert agent.config["fetch_interval_seconds"] == 300
        assert agent.config["market_hours_only"] == True
    
    def test_custom_config(self):
        """Test custom configuration is merged."""
        config = {"fetch_interval_seconds": 60}
        agent = NewsAgent(config=config)
        assert agent.config["fetch_interval_seconds"] == 60
        assert "market_hours_only" in agent.config  # Default still present
    
    def test_stats_initial(self, agent):
        """Test initial statistics."""
        stats = agent.get_stats()
        assert stats["cycles_completed"] == 0
        assert stats["news_fetched"] == 0
        assert stats["alerts_generated"] == 0
    
    def test_reset_stats(self, agent):
        """Test resetting statistics."""
        agent.stats["cycles_completed"] = 10
        agent.reset_stats()
        assert agent.stats["cycles_completed"] == 0
    
    def test_get_recent_alerts_empty(self, agent):
        """Test getting alerts when none exist."""
        alerts = agent.get_recent_alerts()
        assert alerts == []
    
    def test_get_valid_alerts_empty(self, agent):
        """Test getting valid alerts when none exist."""
        alerts = agent.get_valid_alerts()
        assert alerts == []
    
    def test_get_impact_levels_high(self, agent):
        """Test getting impact levels at HIGH threshold."""
        levels = agent._get_impact_levels("high")
        assert NewsImpactLevel.CRITICAL in levels
        assert NewsImpactLevel.HIGH in levels
        assert NewsImpactLevel.MEDIUM not in levels
    
    def test_get_impact_levels_medium(self, agent):
        """Test getting impact levels at MEDIUM threshold."""
        levels = agent._get_impact_levels("medium")
        assert NewsImpactLevel.CRITICAL in levels
        assert NewsImpactLevel.HIGH in levels
        assert NewsImpactLevel.MEDIUM in levels


@pytest.mark.asyncio
class TestNewsAgentAsync:
    """Async tests for NewsAgent class."""
    
    @pytest.fixture
    def mock_rss_fetcher(self):
        """Create a mock RSS fetcher."""
        fetcher = MagicMock(spec=RSSFetcher)
        fetcher.fetch_all_feeds = AsyncMock(return_value=[])
        fetcher.get_stats = MagicMock(return_value={})
        return fetcher
    
    @pytest.fixture
    def mock_llama_analyzer(self):
        """Create a mock Llama analyzer."""
        analyzer = MagicMock(spec=LlamaAnalyzer)
        analyzer.analyze_batch = AsyncMock(return_value=[])
        analyzer.check_health = AsyncMock(return_value=True)
        analyzer.list_models = AsyncMock(return_value=[])
        return analyzer
    
    @pytest.fixture
    def mock_price_validator(self):
        """Create a mock price validator."""
        validator = MagicMock(spec=PriceValidator)
        validator.validate_impact = AsyncMock(return_value=[])
        return validator
    
    @pytest.fixture
    def agent(self, mock_rss_fetcher, mock_llama_analyzer, mock_price_validator):
        """Create a NewsAgent with mocked dependencies."""
        return NewsAgent(
            event_bus=None,
            data_layer=None,
            config={"enabled": True, "market_hours_only": False},
            rss_fetcher=mock_rss_fetcher,
            llama_analyzer=mock_llama_analyzer,
            price_validator=mock_price_validator
        )
    
    async def test_initialize(self, agent):
        """Test agent initialization."""
        await agent.initialize()
        assert agent.is_initialized() == True
    
    async def test_start_stop(self, agent):
        """Test starting and stopping agent."""
        await agent.initialize()
        await agent.start()
        assert agent.is_running() == True
        
        await agent.stop()
        assert agent.is_running() == False
    
    async def test_start_disabled(self):
        """Test starting disabled agent does nothing."""
        agent = NewsAgent(config={"enabled": False})
        await agent.start()
        assert agent.is_running() == False
    
    async def test_run_cycle_no_news(self, agent, mock_rss_fetcher):
        """Test running cycle with no news."""
        mock_rss_fetcher.fetch_all_feeds = AsyncMock(return_value=[])
        
        await agent.initialize()
        result = await agent.run_once()
        
        assert result["fetched"] == 0
        assert result["new"] == 0
    
    async def test_run_cycle_with_news(self, agent, mock_rss_fetcher, mock_llama_analyzer):
        """Test running cycle with news items."""
        sample_news = [
            NewsItem(
                news_id="test1",
                title="Test News 1",
                description="Description 1",
                link="https://example.com/1",
                published_date=get_current_time(),
                source_feed="test"
            ),
            NewsItem(
                news_id="test2",
                title="Test News 2",
                description="Description 2",
                link="https://example.com/2",
                published_date=get_current_time(),
                source_feed="test"
            )
        ]
        mock_rss_fetcher.fetch_all_feeds = AsyncMock(return_value=sample_news)
        mock_llama_analyzer.analyze_batch = AsyncMock(return_value=[])
        
        await agent.initialize()
        result = await agent.run_once()
        
        assert result["fetched"] == 2
        mock_llama_analyzer.analyze_batch.assert_called_once()
    
    async def test_run_cycle_with_high_impact_news(
        self, agent, mock_rss_fetcher, mock_llama_analyzer, mock_price_validator
    ):
        """Test running cycle with high-impact news triggers price validation."""
        news_time = get_current_time()
        sample_news = [
            NewsItem(
                news_id="test1",
                title="HDFC Bank Q3 Results",
                description="Strong earnings report",
                link="https://example.com/1",
                published_date=news_time,
                source_feed="banking"
            )
        ]
        
        sample_analysis = [
            NewsAnalysis(
                news_id="test1",
                impact_level=NewsImpactLevel.HIGH,
                sentiment=NewsSentiment.BULLISH,
                confidence_score=0.9,
                affected_industries=["banking"],
                affected_stocks=["HDFCBANK"],
                affected_indices=["NIFTY BANK"],
                expected_direction="UP",
                expected_move_pct=1.5,
                time_horizon="intraday",
                analysis_summary="Strong results",
                key_points=["Profit growth"],
                model_used="llama3.2",
                analysis_timestamp=news_time
            )
        ]
        
        mock_rss_fetcher.fetch_all_feeds = AsyncMock(return_value=sample_news)
        mock_llama_analyzer.analyze_batch = AsyncMock(return_value=sample_analysis)
        mock_price_validator.validate_impact = AsyncMock(return_value=[])
        
        await agent.initialize()
        result = await agent.run_once()
        
        assert result["high_impact"] == 1
        mock_price_validator.validate_impact.assert_called_once()
    
    async def test_fetch_feeds_only(self, agent, mock_rss_fetcher):
        """Test fetching feeds without analysis."""
        sample_news = [
            NewsItem(
                news_id="test",
                title="Test",
                description="Test",
                link="https://example.com",
                published_date=get_current_time(),
                source_feed="test"
            )
        ]
        mock_rss_fetcher.fetch_all_feeds = AsyncMock(return_value=sample_news)
        
        result = await agent.fetch_feeds_only()
        
        assert len(result) == 1
        mock_rss_fetcher.fetch_all_feeds.assert_called_once()


class TestNewsAgentIntegration:
    """Integration tests (with real components but mocked external services)."""
    
    @pytest.fixture
    def agent_with_real_components(self):
        """Create agent with real components but no external connections."""
        return NewsAgent(
            event_bus=None,
            data_layer=None,
            config={
                "enabled": True,
                "market_hours_only": False,
                "llama_url": "http://localhost:11434",
                "max_news_age_hours": 24
            }
        )
    
    def test_agent_components_initialized(self, agent_with_real_components):
        """Test that real components are initialized."""
        agent = agent_with_real_components
        assert agent.rss_fetcher is not None
        assert agent.llama_analyzer is not None
        assert isinstance(agent.rss_fetcher, RSSFetcher)
        assert isinstance(agent.llama_analyzer, LlamaAnalyzer)
    
    def test_rss_fetcher_has_all_feeds(self, agent_with_real_components):
        """Test RSS fetcher has all 13 feeds configured."""
        agent = agent_with_real_components
        assert agent.rss_fetcher.get_feed_count() == 13


class TestNewsAlert:
    """Test NewsAlert functionality."""
    
    @pytest.fixture
    def sample_alert(self):
        """Create a sample alert."""
        return NewsAlert(
            alert_id="alert123",
            news_id="news123",
            symbol="HDFCBANK",
            alert_type="opportunity",
            priority="high",
            news_title="HDFC Bank Q3 Results",
            news_summary="Strong quarterly performance",
            sentiment=NewsSentiment.BULLISH,
            expected_direction="UP",
            expected_move_pct=1.5,
            current_price=1650.0,
            recommended_action="BUY",
            entry_price=1650.0,
            stop_loss=1635.0,
            target=1675.0,
            created_at=get_current_time(),
            valid_until=get_current_time() + timedelta(hours=2)
        )
    
    def test_alert_is_valid(self, sample_alert):
        """Test valid alert."""
        assert sample_alert.is_valid() == True
    
    def test_alert_is_expired(self, sample_alert):
        """Test expired alert."""
        sample_alert.valid_until = get_current_time() - timedelta(hours=1)
        assert sample_alert.is_valid() == False
    
    def test_alert_to_dict(self, sample_alert):
        """Test alert serialization."""
        d = sample_alert.to_dict()
        assert d["alert_id"] == "alert123"
        assert d["symbol"] == "HDFCBANK"
        assert d["recommended_action"] == "BUY"
    
    def test_alert_format_message(self, sample_alert):
        """Test alert message formatting."""
        msg = sample_alert.format_alert_message()
        assert "TRADING ALERT" in msg
        assert "BUY" in msg
        assert "HDFCBANK" in msg
        assert "1650" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
