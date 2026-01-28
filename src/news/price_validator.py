"""
Price Validator Module
Validates if stock price has already adjusted to news using Zerodha APIs.

Uses existing Zerodha integration from the codebase for:
- Real-time price (LTP) via Kite client
- Historical prices via HistoricalDataCache
- Volume analysis

THREAD SAFETY: Lock-free design using atomic Counter for statistics
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, is_market_hours
from .models import (
    NewsAnalysis, PriceValidation, PriceAdjustmentStatus,
    NewsSentiment, NewsImpactLevel
)

logger = setup_logger("price_validator")


class PriceValidator:
    """
    Validates if stock prices have adjusted to news impact.
    
    Uses Zerodha APIs (via existing data layer) for:
    - Current price (LTP) - real-time from Kite
    - Historical prices - from HistoricalDataCache
    - Volume analysis - detecting unusual activity
    
    Design:
    - Lock-free using Counter for statistics
    - No shared mutable state
    - Async operations for non-blocking price fetches
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "min_move_for_impact": 0.5,      # Minimum % move to consider price impacted
        "volume_spike_ratio": 2.0,        # Volume spike threshold (2x average)
        "lookback_periods": 20,           # Periods for baseline calculation
        "max_news_age_hours": 4,          # Max age to consider news actionable
        "min_remaining_move_pct": 0.5,    # Minimum remaining move for opportunity
        "sl_pct_of_expected": 0.5,        # Stop loss as % of expected move
        "target_pct_of_expected": 0.8,    # Target as % of expected move
        "max_sl_pct": 1.5,                # Maximum stop loss percentage
    }
    
    def __init__(self, 
                 data_layer=None,
                 historical_cache=None,
                 kite_client=None,
                 config: Optional[Dict] = None):
        """
        Initialize price validator.
        
        Args:
            data_layer: ClickHouse data layer for historical data (optional)
            historical_cache: Historical data cache instance (optional)
            kite_client: Zerodha Kite client for real-time data (optional)
            config: Configuration dictionary (optional)
        """
        self.data_layer = data_layer
        self.historical_cache = historical_cache
        self.kite = kite_client
        
        # Merge config with defaults
        self.config = dict(self.DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        
        # Atomic statistics (lock-free)
        self.stats = Counter({
            "validations_completed": 0,
            "validations_failed": 0,
            "opportunities_found": 0,
            "price_fetch_errors": 0,
        })
        
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
        if not analysis.affected_stocks:
            logger.debug(f"No affected stocks in analysis {analysis.news_id[:8]}")
            return []
        
        validations = []
        
        # Validate each affected stock in parallel
        tasks = [
            self._validate_single_stock(
                symbol=symbol,
                analysis=analysis,
                news_time=news_published_time
            )
            for symbol in analysis.affected_stocks
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, result in zip(analysis.affected_stocks, results):
            if isinstance(result, Exception):
                self.stats["validations_failed"] += 1
                logger.error(f"Failed to validate {symbol}: {result}")
            elif result is not None:
                validations.append(result)
                self.stats["validations_completed"] += 1
                
                if result.is_opportunity:
                    self.stats["opportunities_found"] += 1
                    logger.info(
                        f"OPPORTUNITY: {symbol} - {result.recommended_action} "
                        f"@ ₹{result.entry_price:.2f}, "
                        f"remaining move: {result.remaining_move_pct:.2f}%"
                    )
        
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
            PriceValidation or None if validation fails
        """
        try:
            # Get current price
            current_price = await self._get_current_price(symbol)
            if current_price is None:
                logger.warning(f"Could not get current price for {symbol}")
                return None
            
            # Get price at news time (or closest available)
            price_at_news = await self._get_price_at_time(symbol, news_time)
            if price_at_news is None:
                price_at_news = current_price  # Fallback to current
            
            # Calculate actual price change
            if price_at_news == 0:
                price_change_pct = 0.0
            else:
                price_change_pct = ((current_price - price_at_news) / price_at_news) * 100
            
            # Check volume spike
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
                impact_level=analysis.impact_level,
                confidence=analysis.confidence_score
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
                price_change_pct=round(price_change_pct, 2),
                volume_spike=volume_spike,
                volume_ratio=round(volume_ratio, 2),
                adjustment_status=adjustment_status,
                remaining_move_pct=round(remaining_move, 2) if remaining_move else None,
                is_opportunity=is_opportunity,
                recommended_action=recommended_action,
                entry_price=round(entry_price, 2) if entry_price else None,
                stop_loss=round(stop_loss, 2) if stop_loss else None,
                target=round(target, 2) if target else None,
                validation_timestamp=get_current_time()
            )
            
        except Exception as e:
            logger.error(f"Error validating {symbol}: {e}", exc_info=True)
            self.stats["price_fetch_errors"] += 1
            return None
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current LTP from Zerodha.
        
        Tries Kite client first, falls back to historical cache.
        """
        try:
            if self.kite:
                # Use Kite client for real-time price
                instrument = f"NSE:{symbol}"
                try:
                    quote = self.kite.quote([instrument])
                    if instrument in quote:
                        return float(quote[instrument]["last_price"])
                except Exception as e:
                    logger.debug(f"Kite quote failed for {symbol}: {e}")
            
            # Fallback: get latest from historical cache
            if self.historical_cache:
                df = self.historical_cache.get_historical(
                    symbol=symbol,
                    timeframe="1minute",
                    periods=1
                )
                if df is not None and not df.empty:
                    return float(df.iloc[-1]["close"])
            
            # Final fallback: try data layer directly
            if self.data_layer:
                # Query latest price from database
                df = await self._query_latest_price(symbol)
                if df is not None and not df.empty:
                    return float(df.iloc[-1]["close"])
            
            return None
                
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            self.stats["price_fetch_errors"] += 1
            return None
    
    async def _query_latest_price(self, symbol: str) -> Optional[pd.DataFrame]:
        """Query latest price from data layer."""
        try:
            if hasattr(self.data_layer, 'get_historical_data'):
                return await self.data_layer.get_historical_data(
                    symbol=symbol,
                    interval="1minute",
                    limit=1
                )
            return None
        except Exception:
            return None
    
    async def _get_price_at_time(self, symbol: str, target_time: datetime) -> Optional[float]:
        """
        Get price closest to specified time.
        
        Uses historical cache to find the candle nearest to target time.
        """
        try:
            if not self.historical_cache:
                return None
            
            df = self.historical_cache.get_historical(
                symbol=symbol,
                timeframe="5minute",
                periods=100
            )
            
            if df is None or df.empty:
                return None
            
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                return float(df.iloc[-1]["close"])
            
            # Find candle closest to target time
            # Make target_time timezone-aware if needed
            target_time = to_ist(target_time)
            
            # Calculate time differences
            time_diffs = abs(df.index - target_time)
            closest_idx = time_diffs.argmin()
            
            return float(df.iloc[closest_idx]["close"])
            
        except Exception as e:
            logger.error(f"Error getting historical price for {symbol}: {e}")
            return None
    
    async def _check_volume_spike(self, symbol: str) -> Tuple[bool, float]:
        """
        Check if there's unusual volume activity.
        
        Returns:
            Tuple of (is_spike, volume_ratio)
        """
        try:
            if not self.historical_cache:
                return False, 1.0
            
            df = self.historical_cache.get_historical(
                symbol=symbol,
                timeframe="5minute",
                periods=self.config["lookback_periods"]
            )
            
            if df is None or df.empty or len(df) < 5:
                return False, 1.0
            
            # Check if volume column exists
            if "volume" not in df.columns:
                return False, 1.0
            
            avg_volume = df["volume"].mean()
            current_volume = df.iloc[-1]["volume"]
            
            if avg_volume == 0 or pd.isna(avg_volume):
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
        """
        Determine how much the price has adjusted to the news.
        
        Returns:
            PriceAdjustmentStatus indicating adjustment level
        """
        # Check direction alignment
        direction_match = (
            (expected_direction == "UP" and actual_change > 0) or
            (expected_direction == "DOWN" and actual_change < 0)
        )
        
        # If price moved opposite to expected and significantly
        if not direction_match and abs(actual_change) > self.config["min_move_for_impact"]:
            return PriceAdjustmentStatus.UNCLEAR
        
        # Handle zero expected change
        if expected_change == 0:
            if abs(actual_change) < self.config["min_move_for_impact"]:
                return PriceAdjustmentStatus.FULLY_ADJUSTED
            return PriceAdjustmentStatus.UNCLEAR
        
        # Calculate adjustment percentage
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
        """
        Calculate remaining potential move percentage.
        
        Returns:
            Remaining move percentage or None if no move expected
        """
        if expected_change == 0:
            return None
        
        # Adjust sign based on direction
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
                               impact_level: NewsImpactLevel,
                               confidence: float) -> bool:
        """
        Determine if this represents a valid trading opportunity.
        
        Considers:
        - Adjustment status
        - Remaining move potential
        - News age
        - Impact level
        - Analysis confidence
        """
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
        if remaining_move is None or remaining_move < self.config["min_remaining_move_pct"]:
            return False
        
        # Higher bar for lower impact news
        min_remaining_move = {
            NewsImpactLevel.CRITICAL: 0.5,
            NewsImpactLevel.HIGH: 0.75,
            NewsImpactLevel.MEDIUM: 1.0,
            NewsImpactLevel.LOW: 1.5,
            NewsImpactLevel.NEUTRAL: 2.0,
        }.get(impact_level, 1.0)
        
        if remaining_move < min_remaining_move:
            return False
        
        # Require minimum confidence for actionable signals
        if confidence < 0.4:
            return False
        
        return True
    
    def _get_recommended_action(self, 
                               expected_direction: str,
                               sentiment: NewsSentiment) -> str:
        """
        Get recommended trading action based on analysis.
        
        Returns:
            "BUY", "SELL", or "HOLD"
        """
        if expected_direction == "UP":
            return "BUY"
        elif expected_direction == "DOWN":
            return "SELL"
        return "HOLD"
    
    def _calculate_sl_target(self,
                            entry_price: float,
                            direction: str,
                            expected_move_pct: float) -> Tuple[float, float]:
        """
        Calculate stop loss and target prices.
        
        Args:
            entry_price: Entry price
            direction: Expected direction ("UP" or "DOWN")
            expected_move_pct: Expected move percentage
            
        Returns:
            Tuple of (stop_loss, target)
        """
        # SL = percentage of expected move, capped at max
        sl_pct = min(
            expected_move_pct * self.config["sl_pct_of_expected"],
            self.config["max_sl_pct"]
        )
        
        # Target = percentage of expected move
        target_pct = expected_move_pct * self.config["target_pct_of_expected"]
        
        if direction == "UP":
            stop_loss = entry_price * (1 - sl_pct / 100)
            target = entry_price * (1 + target_pct / 100)
        else:
            stop_loss = entry_price * (1 + sl_pct / 100)
            target = entry_price * (1 - target_pct / 100)
        
        return round(stop_loss, 2), round(target, 2)
    
    async def validate_single_symbol(self,
                                    symbol: str,
                                    expected_direction: str = "UP",
                                    expected_move_pct: float = 1.0) -> Optional[PriceValidation]:
        """
        Standalone validation for a single symbol (for testing).
        
        Args:
            symbol: Stock symbol
            expected_direction: Expected price direction
            expected_move_pct: Expected move percentage
            
        Returns:
            PriceValidation or None
        """
        # Create a mock analysis
        from .models import NewsAnalysis
        
        mock_analysis = NewsAnalysis(
            news_id="test",
            impact_level=NewsImpactLevel.HIGH,
            sentiment=NewsSentiment.BULLISH if expected_direction == "UP" else NewsSentiment.BEARISH,
            confidence_score=0.8,
            affected_industries=[],
            affected_stocks=[symbol],
            affected_indices=[],
            expected_direction=expected_direction,
            expected_move_pct=expected_move_pct,
            time_horizon="intraday",
            analysis_summary="Test validation",
            key_points=[],
            model_used="test",
            analysis_timestamp=get_current_time()
        )
        
        return await self._validate_single_stock(
            symbol=symbol,
            analysis=mock_analysis,
            news_time=get_current_time() - timedelta(minutes=30)
        )
    
    def get_stats(self) -> Dict[str, int]:
        """Get validator statistics."""
        return dict(self.stats)
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = Counter({
            "validations_completed": 0,
            "validations_failed": 0,
            "opportunities_found": 0,
            "price_fetch_errors": 0,
        })
