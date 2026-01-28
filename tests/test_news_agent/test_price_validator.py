"""
Tests for Price Validator Module
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.news.price_validator import PriceValidator
from src.news.models import (
    NewsAnalysis, PriceValidation, PriceAdjustmentStatus,
    NewsImpactLevel, NewsSentiment
)
from src.utils.timezone_utils import get_current_time


class TestPriceValidator:
    """Test cases for PriceValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a fresh PriceValidator instance."""
        return PriceValidator()
    
    @pytest.fixture
    def sample_analysis(self):
        """Create a sample news analysis."""
        return NewsAnalysis(
            news_id="test123",
            impact_level=NewsImpactLevel.HIGH,
            sentiment=NewsSentiment.BULLISH,
            confidence_score=0.85,
            affected_industries=["banking"],
            affected_stocks=["HDFCBANK", "ICICIBANK"],
            affected_indices=["NIFTY BANK"],
            expected_direction="UP",
            expected_move_pct=1.5,
            time_horizon="intraday",
            analysis_summary="Strong quarterly results",
            key_points=["Profit growth"],
            model_used="llama3.2:latest",
            analysis_timestamp=get_current_time()
        )
    
    def test_init(self, validator):
        """Test PriceValidator initialization."""
        assert validator is not None
        assert validator.config is not None
        assert "min_move_for_impact" in validator.config
    
    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = {"min_move_for_impact": 1.0}
        validator = PriceValidator(config=config)
        assert validator.config["min_move_for_impact"] == 1.0
    
    def test_determine_adjustment_not_adjusted(self, validator):
        """Test detecting NOT_ADJUSTED status."""
        status = validator._determine_adjustment_status(
            actual_change=0.1,
            expected_change=2.0,
            expected_direction="UP",
            sentiment=NewsSentiment.BULLISH
        )
        assert status == PriceAdjustmentStatus.NOT_ADJUSTED
    
    def test_determine_adjustment_partially_adjusted(self, validator):
        """Test detecting PARTIALLY_ADJUSTED status."""
        status = validator._determine_adjustment_status(
            actual_change=1.0,
            expected_change=2.0,
            expected_direction="UP",
            sentiment=NewsSentiment.BULLISH
        )
        assert status == PriceAdjustmentStatus.PARTIALLY_ADJUSTED
    
    def test_determine_adjustment_fully_adjusted(self, validator):
        """Test detecting FULLY_ADJUSTED status."""
        status = validator._determine_adjustment_status(
            actual_change=1.8,
            expected_change=2.0,
            expected_direction="UP",
            sentiment=NewsSentiment.BULLISH
        )
        assert status == PriceAdjustmentStatus.FULLY_ADJUSTED
    
    def test_determine_adjustment_unclear_opposite_direction(self, validator):
        """Test detecting UNCLEAR status when price moved opposite."""
        status = validator._determine_adjustment_status(
            actual_change=-1.0,  # Went down
            expected_change=2.0,
            expected_direction="UP",  # Expected up
            sentiment=NewsSentiment.BULLISH
        )
        assert status == PriceAdjustmentStatus.UNCLEAR
    
    def test_calculate_remaining_move_up(self, validator):
        """Test calculating remaining move for UP direction."""
        remaining = validator._calculate_remaining_move(
            actual_change=0.5,
            expected_change=2.0,
            expected_direction="UP"
        )
        assert remaining == 1.5
    
    def test_calculate_remaining_move_down(self, validator):
        """Test calculating remaining move for DOWN direction."""
        remaining = validator._calculate_remaining_move(
            actual_change=-0.5,
            expected_change=2.0,
            expected_direction="DOWN"
        )
        assert remaining == 1.5
    
    def test_calculate_remaining_move_overshot(self, validator):
        """Test remaining move when price overshot expected."""
        remaining = validator._calculate_remaining_move(
            actual_change=3.0,
            expected_change=2.0,
            expected_direction="UP"
        )
        # Price already moved more than expected, no remaining
        assert remaining is None
    
    def test_is_trading_opportunity_valid(self, validator):
        """Test identifying valid trading opportunity."""
        is_opp = validator._is_trading_opportunity(
            adjustment_status=PriceAdjustmentStatus.NOT_ADJUSTED,
            remaining_move=1.5,
            news_time=get_current_time() - timedelta(hours=1),
            impact_level=NewsImpactLevel.HIGH,
            confidence=0.8
        )
        assert is_opp == True
    
    def test_is_trading_opportunity_old_news(self, validator):
        """Test rejecting opportunity for old news."""
        is_opp = validator._is_trading_opportunity(
            adjustment_status=PriceAdjustmentStatus.NOT_ADJUSTED,
            remaining_move=1.5,
            news_time=get_current_time() - timedelta(hours=10),  # Too old
            impact_level=NewsImpactLevel.HIGH,
            confidence=0.8
        )
        assert is_opp == False
    
    def test_is_trading_opportunity_fully_adjusted(self, validator):
        """Test rejecting opportunity when fully adjusted."""
        is_opp = validator._is_trading_opportunity(
            adjustment_status=PriceAdjustmentStatus.FULLY_ADJUSTED,
            remaining_move=0.1,
            news_time=get_current_time() - timedelta(hours=1),
            impact_level=NewsImpactLevel.HIGH,
            confidence=0.8
        )
        assert is_opp == False
    
    def test_is_trading_opportunity_low_confidence(self, validator):
        """Test rejecting opportunity with low confidence."""
        is_opp = validator._is_trading_opportunity(
            adjustment_status=PriceAdjustmentStatus.NOT_ADJUSTED,
            remaining_move=1.5,
            news_time=get_current_time() - timedelta(hours=1),
            impact_level=NewsImpactLevel.HIGH,
            confidence=0.2  # Too low
        )
        assert is_opp == False
    
    def test_get_recommended_action_up(self, validator):
        """Test recommended action for UP direction."""
        action = validator._get_recommended_action("UP", NewsSentiment.BULLISH)
        assert action == "BUY"
    
    def test_get_recommended_action_down(self, validator):
        """Test recommended action for DOWN direction."""
        action = validator._get_recommended_action("DOWN", NewsSentiment.BEARISH)
        assert action == "SELL"
    
    def test_get_recommended_action_sideways(self, validator):
        """Test recommended action for SIDEWAYS direction."""
        action = validator._get_recommended_action("SIDEWAYS", NewsSentiment.NEUTRAL)
        assert action == "HOLD"
    
    def test_calculate_sl_target_buy(self, validator):
        """Test SL/target calculation for buy trade."""
        sl, target = validator._calculate_sl_target(
            entry_price=100.0,
            direction="UP",
            expected_move_pct=2.0
        )
        
        assert sl < 100.0  # SL below entry
        assert target > 100.0  # Target above entry
    
    def test_calculate_sl_target_sell(self, validator):
        """Test SL/target calculation for sell trade."""
        sl, target = validator._calculate_sl_target(
            entry_price=100.0,
            direction="DOWN",
            expected_move_pct=2.0
        )
        
        assert sl > 100.0  # SL above entry
        assert target < 100.0  # Target below entry
    
    def test_calculate_sl_respects_max(self, validator):
        """Test SL doesn't exceed maximum percentage."""
        validator.config["max_sl_pct"] = 1.0
        
        sl, target = validator._calculate_sl_target(
            entry_price=100.0,
            direction="UP",
            expected_move_pct=5.0  # Would give SL of 2.5% without cap
        )
        
        # SL should be capped at 1%
        assert sl >= 99.0
    
    def test_stats_initial(self, validator):
        """Test initial statistics."""
        stats = validator.get_stats()
        assert stats["validations_completed"] == 0
        assert stats["opportunities_found"] == 0
    
    def test_reset_stats(self, validator):
        """Test resetting statistics."""
        validator.stats["validations_completed"] = 10
        validator.reset_stats()
        assert validator.stats["validations_completed"] == 0


@pytest.mark.asyncio
class TestPriceValidatorAsync:
    """Async test cases for PriceValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create a fresh PriceValidator instance."""
        return PriceValidator()
    
    @pytest.fixture
    def sample_analysis(self):
        """Create a sample news analysis."""
        return NewsAnalysis(
            news_id="test123",
            impact_level=NewsImpactLevel.HIGH,
            sentiment=NewsSentiment.BULLISH,
            confidence_score=0.85,
            affected_industries=["banking"],
            affected_stocks=["HDFCBANK"],
            affected_indices=[],
            expected_direction="UP",
            expected_move_pct=1.5,
            time_horizon="intraday",
            analysis_summary="Test",
            key_points=[],
            model_used="test",
            analysis_timestamp=get_current_time()
        )
    
    async def test_validate_impact_no_stocks(self, validator):
        """Test validation with no affected stocks returns empty list."""
        analysis = NewsAnalysis(
            news_id="test",
            impact_level=NewsImpactLevel.HIGH,
            sentiment=NewsSentiment.BULLISH,
            confidence_score=0.8,
            affected_industries=[],
            affected_stocks=[],  # No stocks
            affected_indices=[],
            expected_direction="UP",
            expected_move_pct=1.0,
            time_horizon="intraday",
            analysis_summary="Test",
            key_points=[],
            model_used="test",
            analysis_timestamp=get_current_time()
        )
        
        result = await validator.validate_impact(
            analysis=analysis,
            news_published_time=get_current_time()
        )
        
        assert result == []
    
    async def test_validate_impact_no_price_data(self, validator, sample_analysis):
        """Test validation when price data is not available."""
        # No kite client or historical cache configured
        result = await validator.validate_impact(
            analysis=sample_analysis,
            news_published_time=get_current_time() - timedelta(hours=1)
        )
        
        # Should return empty or handle gracefully
        assert isinstance(result, list)
    
    async def test_get_current_price_no_sources(self, validator):
        """Test getting price with no data sources returns None."""
        price = await validator._get_current_price("HDFCBANK")
        assert price is None
    
    async def test_check_volume_spike_no_cache(self, validator):
        """Test volume check with no cache returns default."""
        is_spike, ratio = await validator._check_volume_spike("HDFCBANK")
        assert is_spike == False
        assert ratio == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
