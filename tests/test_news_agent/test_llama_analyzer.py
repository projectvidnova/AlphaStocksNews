"""
Tests for Llama Analyzer Module
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.news.llama_analyzer import (
    LlamaAnalyzer, 
    INDUSTRY_KEYWORDS, 
    MAJOR_STOCKS,
    INDEX_KEYWORDS
)
from src.news.models import (
    NewsItem, NewsAnalysis, 
    NewsImpactLevel, NewsSentiment
)
from src.utils.timezone_utils import get_current_time


class TestLlamaAnalyzer:
    """Test cases for LlamaAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a fresh LlamaAnalyzer instance."""
        return LlamaAnalyzer(
            base_url="http://localhost:11434",
            model_name="llama3.2:latest",
            timeout_seconds=30,
            max_concurrent=2
        )
    
    @pytest.fixture
    def sample_news_item(self):
        """Create a sample news item for testing."""
        return NewsItem(
            news_id="test123",
            title="HDFC Bank reports 20% growth in Q3 profit",
            description="HDFC Bank reported a strong quarterly performance with 20% year-on-year growth in net profit.",
            link="https://example.com/news/1",
            published_date=get_current_time(),
            source_feed="banking"
        )
    
    def test_init(self, analyzer):
        """Test LlamaAnalyzer initialization."""
        assert analyzer is not None
        assert analyzer.model_name == "llama3.2:latest"
        assert analyzer.base_url == "http://localhost:11434"
    
    def test_build_analysis_prompt(self, analyzer, sample_news_item):
        """Test prompt building for analysis."""
        prompt = analyzer._build_analysis_prompt(sample_news_item)
        
        assert "HDFC Bank" in prompt
        assert "20% growth" in prompt
        assert "JSON format" in prompt
        assert "impact_level" in prompt
        assert "affected_stocks" in prompt
    
    def test_parse_valid_json_response(self, analyzer, sample_news_item):
        """Test parsing a valid JSON response."""
        response = json.dumps({
            "impact_level": "high",
            "sentiment": "bullish",
            "confidence_score": 0.85,
            "affected_industries": ["banking"],
            "affected_stocks": ["HDFCBANK"],
            "affected_indices": ["NIFTY BANK"],
            "expected_direction": "UP",
            "expected_move_pct": 1.5,
            "time_horizon": "intraday",
            "analysis_summary": "Strong quarterly results",
            "key_points": ["20% profit growth", "Strong retail loan book"]
        })
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        
        assert analysis is not None
        assert analysis.impact_level == NewsImpactLevel.HIGH
        assert analysis.sentiment == NewsSentiment.BULLISH
        assert analysis.confidence_score == 0.85
        assert "HDFCBANK" in analysis.affected_stocks
        assert analysis.expected_direction == "UP"
    
    def test_parse_response_normalizes_stocks(self, analyzer, sample_news_item):
        """Test that stock symbols are normalized to uppercase."""
        response = json.dumps({
            "impact_level": "high",
            "sentiment": "bullish",
            "confidence_score": 0.8,
            "affected_industries": ["banking"],
            "affected_stocks": ["hdfcbank", "IciciBank", "SBIN"],
            "affected_indices": [],
            "expected_direction": "UP",
            "expected_move_pct": 1.0,
            "time_horizon": "intraday",
            "analysis_summary": "Test",
            "key_points": []
        })
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        
        assert "HDFCBANK" in analysis.affected_stocks
        assert "ICICIBANK" in analysis.affected_stocks
        assert "SBIN" in analysis.affected_stocks
    
    def test_parse_invalid_json_uses_fallback(self, analyzer, sample_news_item):
        """Test that invalid JSON triggers fallback analysis."""
        response = "This is not valid JSON"
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        
        assert analysis is not None
        assert "(fallback)" in analysis.model_used
        assert analysis.confidence_score < 0.5
    
    def test_parse_json_with_markdown_wrapper(self, analyzer, sample_news_item):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = '''```json
        {
            "impact_level": "medium",
            "sentiment": "neutral",
            "confidence_score": 0.7,
            "affected_industries": [],
            "affected_stocks": [],
            "affected_indices": [],
            "expected_direction": "SIDEWAYS",
            "expected_move_pct": 0.5,
            "time_horizon": "short_term",
            "analysis_summary": "Test",
            "key_points": []
        }
        ```'''
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        
        assert analysis is not None
        assert analysis.impact_level == NewsImpactLevel.MEDIUM
    
    def test_fallback_analysis_extracts_industries(self, analyzer):
        """Test fallback analysis extracts industries from keywords."""
        news_item = NewsItem(
            news_id="test",
            title="RBI cuts interest rates, banking stocks rally",
            description="The Reserve Bank of India announced a rate cut benefiting banking sector.",
            link="https://example.com",
            published_date=get_current_time(),
            source_feed="market_news"
        )
        
        analysis = analyzer._fallback_analysis(news_item, "test error")
        
        assert "banking" in analysis.affected_industries
    
    def test_fallback_analysis_extracts_stocks(self, analyzer):
        """Test fallback analysis extracts stock symbols from keywords."""
        news_item = NewsItem(
            news_id="test",
            title="Infosys wins major contract worth $500 million",
            description="Infosys announced a significant deal with a global client.",
            link="https://example.com",
            published_date=get_current_time(),
            source_feed="it"
        )
        
        analysis = analyzer._fallback_analysis(news_item, "test error")
        
        assert "INFY" in analysis.affected_stocks
    
    def test_fallback_sentiment_bullish(self, analyzer):
        """Test fallback analysis detects bullish sentiment."""
        news_item = NewsItem(
            news_id="test",
            title="Stock surges on strong growth and profit beat",
            description="Company reported strong earnings with significant profit growth.",
            link="https://example.com",
            published_date=get_current_time(),
            source_feed="market_news"
        )
        
        analysis = analyzer._fallback_analysis(news_item, "test")
        
        assert analysis.sentiment == NewsSentiment.BULLISH
        assert analysis.expected_direction == "UP"
    
    def test_fallback_sentiment_bearish(self, analyzer):
        """Test fallback analysis detects bearish sentiment."""
        news_item = NewsItem(
            news_id="test",
            title="Stock crashes on weak earnings and revenue decline",
            description="Company reported major loss with plunging revenues.",
            link="https://example.com",
            published_date=get_current_time(),
            source_feed="market_news"
        )
        
        analysis = analyzer._fallback_analysis(news_item, "test")
        
        assert analysis.sentiment == NewsSentiment.BEARISH
        assert analysis.expected_direction == "DOWN"
    
    def test_stats_initial(self, analyzer):
        """Test initial statistics."""
        stats = analyzer.get_stats()
        assert stats["analyses_completed"] == 0
        assert stats["analyses_failed"] == 0
        assert stats["fallback_used"] == 0
    
    def test_reset_stats(self, analyzer):
        """Test resetting statistics."""
        analyzer.stats["analyses_completed"] = 10
        analyzer.reset_stats()
        assert analyzer.stats["analyses_completed"] == 0
    
    def test_confidence_score_clamping(self, analyzer, sample_news_item):
        """Test confidence score is clamped between 0 and 1."""
        response = json.dumps({
            "impact_level": "high",
            "sentiment": "bullish",
            "confidence_score": 1.5,  # Invalid, should be clamped
            "affected_industries": [],
            "affected_stocks": [],
            "affected_indices": [],
            "expected_direction": "UP",
            "expected_move_pct": 1.0,
            "time_horizon": "intraday",
            "analysis_summary": "Test",
            "key_points": []
        })
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        assert analysis.confidence_score == 1.0
    
    def test_expected_move_clamping(self, analyzer, sample_news_item):
        """Test expected move percentage is clamped."""
        response = json.dumps({
            "impact_level": "high",
            "sentiment": "bullish",
            "confidence_score": 0.8,
            "affected_industries": [],
            "affected_stocks": [],
            "affected_indices": [],
            "expected_direction": "UP",
            "expected_move_pct": 15.0,  # Should be clamped to 10
            "time_horizon": "intraday",
            "analysis_summary": "Test",
            "key_points": []
        })
        
        analysis = analyzer._parse_analysis_response(sample_news_item, response)
        assert analysis.expected_move_pct == 10.0


class TestKeywordMappings:
    """Test keyword mapping dictionaries."""
    
    def test_industry_keywords_coverage(self):
        """Test all major industries have keywords."""
        expected_industries = [
            "banking", "auto", "it", "pharma", "aviation",
            "oil_gas", "metal", "fmcg", "telecom", "realty"
        ]
        
        for industry in expected_industries:
            assert industry in INDUSTRY_KEYWORDS
            assert len(INDUSTRY_KEYWORDS[industry]) > 0
    
    def test_major_stocks_coverage(self):
        """Test major stocks are mapped."""
        expected_stocks = [
            "HDFCBANK", "ICICIBANK", "SBIN", "TCS", "INFY",
            "RELIANCE", "TATAMOTORS", "MARUTI"
        ]
        
        for stock in expected_stocks:
            assert stock in MAJOR_STOCKS
    
    def test_index_keywords_coverage(self):
        """Test index keywords are mapped."""
        expected_indices = ["NIFTY 50", "NIFTY BANK", "SENSEX"]
        
        for index in expected_indices:
            assert index in INDEX_KEYWORDS


@pytest.mark.asyncio
class TestLlamaAnalyzerAsync:
    """Async test cases for LlamaAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a fresh LlamaAnalyzer instance."""
        return LlamaAnalyzer(timeout_seconds=5)
    
    @pytest.fixture
    def sample_news_item(self):
        """Create a sample news item."""
        return NewsItem(
            news_id="test123",
            title="Test News",
            description="Test description",
            link="https://example.com",
            published_date=get_current_time(),
            source_feed="test"
        )
    
    async def test_analyze_batch_empty(self, analyzer):
        """Test analyzing empty batch returns empty list."""
        result = await analyzer.analyze_batch([])
        assert result == []
    
    async def test_health_check_failure(self, analyzer):
        """Test health check when server is not running."""
        # This will fail because there's no actual server
        result = await analyzer.check_health()
        assert result == False
    
    async def test_list_models_failure(self, analyzer):
        """Test listing models when server is not running."""
        result = await analyzer.list_models()
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
