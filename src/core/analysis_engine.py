"""
Market Analysis Engine for AlphaStock Trading System

Provides comprehensive market analysis capabilities for strategy decision making.
Includes technical analysis, pattern recognition, and market condition assessment.
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
import warnings
warnings.filterwarnings('ignore')

from ..core.historical_data_manager import HistoricalDataManager
from ..data import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class MarketAnalysisEngine:
    """
    Advanced market analysis engine for strategy decision making.
    
    Features:
    - Technical indicator calculations
    - Pattern recognition
    - Market condition assessment
    - Risk analysis
    - Strategy optimization insights
    """
    
    def __init__(self, historical_data_manager: HistoricalDataManager, data_layer: DataLayerInterface):
        """
        Initialize Market Analysis Engine.
        
        Args:
            historical_data_manager: Historical data manager instance
            data_layer: Data storage layer
        """
        self.historical_manager = historical_data_manager
        self.data_layer = data_layer
        self.logger = setup_logger("MarketAnalysisEngine")
        
        # Analysis cache
        self.analysis_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def analyze_market_conditions(self, symbol: str, timeframe: str = '15minute') -> Dict[str, Any]:
        """
        Comprehensive market condition analysis for a symbol.
        
        Args:
            symbol: Symbol to analyze
            timeframe: Analysis timeframe
            
        Returns:
            Market condition analysis results
        """
        cache_key = f"{symbol}_{timeframe}_{int(get_current_time().timestamp() / self.cache_ttl)}"
        
        if cache_key in self.analysis_cache:
            return self.analysis_cache[cache_key]
        
        try:
            self.logger.info(f"Analyzing market conditions for {symbol} ({timeframe})")
            
            # Get analysis data (30 days for comprehensive analysis)
            data = await self.historical_manager.get_analysis_data(symbol, timeframe, days_back=30)
            
            if data is None or len(data) < 50:
                self.logger.warning(f"Insufficient data for analysis: {symbol}")
                return {'error': 'insufficient_data'}
            
            analysis = {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': get_current_time().isoformat(),
                'data_points': len(data),
                'trend_analysis': self._analyze_trend(data),
                'volatility_analysis': self._analyze_volatility(data),
                'volume_analysis': self._analyze_volume(data),
                'support_resistance': self._find_support_resistance(data),
                'momentum_indicators': self._calculate_momentum_indicators(data),
                'pattern_recognition': self._detect_patterns(data),
                'risk_metrics': self._calculate_risk_metrics(data),
                'strategy_signals': self._generate_strategy_signals(data)
            }
            
            # Calculate overall market condition score
            analysis['market_condition'] = self._assess_market_condition(analysis)
            
            # Cache the results
            self.analysis_cache[cache_key] = analysis
            
            self.logger.info(f"Analysis completed for {symbol}: {analysis['market_condition']['condition']}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return {'error': str(e)}
    
    def _analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze price trend characteristics."""
        try:
            latest_price = data['close'].iloc[-1]
            
            # Trend strength using multiple EMAs
            ema_short = data['close'].ewm(span=9).mean().iloc[-1]
            ema_medium = data['close'].ewm(span=21).mean().iloc[-1]
            ema_long = data['close'].ewm(span=50).mean().iloc[-1]
            
            # Trend direction
            trend_direction = 'neutral'
            if ema_short > ema_medium > ema_long:
                trend_direction = 'bullish'
            elif ema_short < ema_medium < ema_long:
                trend_direction = 'bearish'
            
            # Trend strength (0-1)
            price_range = data['high'].max() - data['low'].min()
            ema_spread = abs(ema_short - ema_long)
            trend_strength = min(1.0, ema_spread / (price_range * 0.1)) if price_range > 0 else 0
            
            # Recent trend change detection
            ema_short_prev = data['close'].ewm(span=9).mean().iloc[-5]
            ema_medium_prev = data['close'].ewm(span=21).mean().iloc[-5]
            
            trend_change_detected = False
            if trend_direction == 'bullish' and ema_short_prev <= ema_medium_prev:
                trend_change_detected = True
            elif trend_direction == 'bearish' and ema_short_prev >= ema_medium_prev:
                trend_change_detected = True
            
            # Price position relative to EMAs
            price_position = 'above_all' if latest_price > max(ema_short, ema_medium, ema_long) else \
                           'below_all' if latest_price < min(ema_short, ema_medium, ema_long) else \
                           'mixed'
            
            return {
                'direction': trend_direction,
                'strength': round(trend_strength, 3),
                'ema_short': round(ema_short, 2),
                'ema_medium': round(ema_medium, 2),
                'ema_long': round(ema_long, 2),
                'price_position': price_position,
                'trend_change_detected': trend_change_detected,
                'latest_price': round(latest_price, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error in trend analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_volatility(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze price volatility characteristics."""
        try:
            # Calculate returns
            returns = data['close'].pct_change().dropna()
            
            # Current volatility (10-period rolling)
            current_volatility = returns.tail(10).std() * np.sqrt(252)  # Annualized
            
            # Historical volatility (full period)
            historical_volatility = returns.std() * np.sqrt(252)
            
            # Volatility regime
            vol_percentile = (returns.tail(10).std() > returns.expanding().std()).sum() / len(returns) * 100
            
            regime = 'low' if vol_percentile < 25 else \
                    'normal' if vol_percentile < 75 else 'high'
            
            # Bollinger Bands for volatility context
            bb_window = 20
            bb_std = 2
            bb_middle = data['close'].rolling(window=bb_window).mean()
            bb_upper = bb_middle + (data['close'].rolling(window=bb_window).std() * bb_std)
            bb_lower = bb_middle - (data['close'].rolling(window=bb_window).std() * bb_std)
            
            latest_price = data['close'].iloc[-1]
            bb_position = 'upper' if latest_price > bb_upper.iloc[-1] else \
                         'lower' if latest_price < bb_lower.iloc[-1] else \
                         'middle'
            
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1] * 100
            
            return {
                'current_volatility': round(current_volatility, 4),
                'historical_volatility': round(historical_volatility, 4),
                'regime': regime,
                'percentile': round(vol_percentile, 1),
                'bollinger_bands': {
                    'position': bb_position,
                    'width_pct': round(bb_width, 2),
                    'upper': round(bb_upper.iloc[-1], 2),
                    'middle': round(bb_middle.iloc[-1], 2),
                    'lower': round(bb_lower.iloc[-1], 2)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in volatility analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_volume(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volume characteristics and patterns."""
        try:
            latest_volume = data['volume'].iloc[-1]
            avg_volume_20 = data['volume'].rolling(window=20).mean().iloc[-1]
            
            # Volume ratio
            volume_ratio = latest_volume / avg_volume_20 if avg_volume_20 > 0 else 1
            
            # Volume trend (increasing/decreasing)
            recent_volumes = data['volume'].tail(5)
            volume_trend = 'increasing' if recent_volumes.iloc[-1] > recent_volumes.iloc[0] else 'decreasing'
            
            # Volume breakout detection
            volume_breakout = volume_ratio > 1.5  # 50% above average
            
            # Price-volume relationship
            price_changes = data['close'].pct_change().tail(10)
            volume_changes = data['volume'].pct_change().tail(10)
            
            pv_correlation = price_changes.corr(volume_changes)
            
            return {
                'latest_volume': int(latest_volume),
                'average_volume_20': int(avg_volume_20),
                'volume_ratio': round(volume_ratio, 2),
                'volume_trend': volume_trend,
                'volume_breakout': volume_breakout,
                'price_volume_correlation': round(pv_correlation, 3) if not np.isnan(pv_correlation) else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error in volume analysis: {e}")
            return {'error': str(e)}
    
    def _find_support_resistance(self, data: pd.DataFrame, window: int = 10) -> Dict[str, Any]:
        """Identify key support and resistance levels."""
        try:
            # Local maxima and minima
            highs = data['high'].rolling(window=window, center=True).max()
            lows = data['low'].rolling(window=window, center=True).min()
            
            # Find peaks and troughs
            resistance_levels = []
            support_levels = []
            
            for i in range(window, len(data) - window):
                if data['high'].iloc[i] == highs.iloc[i]:
                    resistance_levels.append(data['high'].iloc[i])
                
                if data['low'].iloc[i] == lows.iloc[i]:
                    support_levels.append(data['low'].iloc[i])
            
            # Cluster levels (remove levels too close to each other)
            def cluster_levels(levels, min_distance_pct=0.5):
                if not levels:
                    return []
                
                levels = sorted(levels)
                clustered = [levels[0]]
                
                for level in levels[1:]:
                    if abs(level - clustered[-1]) / clustered[-1] * 100 > min_distance_pct:
                        clustered.append(level)
                
                return clustered
            
            resistance_levels = cluster_levels(resistance_levels)[-3:]  # Top 3
            support_levels = cluster_levels(support_levels)[-3:]  # Bottom 3
            
            current_price = data['close'].iloc[-1]
            
            # Find nearest levels
            nearest_resistance = min(resistance_levels, key=lambda x: abs(x - current_price)) if resistance_levels else None
            nearest_support = min(support_levels, key=lambda x: abs(x - current_price)) if support_levels else None
            
            return {
                'resistance_levels': [round(r, 2) for r in resistance_levels],
                'support_levels': [round(s, 2) for s in support_levels],
                'nearest_resistance': round(nearest_resistance, 2) if nearest_resistance else None,
                'nearest_support': round(nearest_support, 2) if nearest_support else None,
                'current_price': round(current_price, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error finding support/resistance: {e}")
            return {'error': str(e)}
    
    def _calculate_momentum_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate momentum-based technical indicators."""
        try:
            # RSI (Relative Strength Index)
            def calculate_rsi(prices, window=14):
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
                rs = gain / loss
                return 100 - (100 / (1 + rs))
            
            rsi = calculate_rsi(data['close']).iloc[-1]
            
            # MACD (Moving Average Convergence Divergence)
            ema_12 = data['close'].ewm(span=12).mean()
            ema_26 = data['close'].ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9).mean()
            macd_histogram = macd_line - signal_line
            
            # Stochastic Oscillator
            def calculate_stochastic(data, window=14):
                low_min = data['low'].rolling(window=window).min()
                high_max = data['high'].rolling(window=window).max()
                k_percent = 100 * (data['close'] - low_min) / (high_max - low_min)
                d_percent = k_percent.rolling(window=3).mean()
                return k_percent, d_percent
            
            stoch_k, stoch_d = calculate_stochastic(data)
            
            return {
                'rsi': round(rsi, 2) if not np.isnan(rsi) else 50,
                'rsi_signal': 'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral',
                'macd': {
                    'line': round(macd_line.iloc[-1], 4),
                    'signal': round(signal_line.iloc[-1], 4),
                    'histogram': round(macd_histogram.iloc[-1], 4),
                    'signal_status': 'bullish' if macd_line.iloc[-1] > signal_line.iloc[-1] else 'bearish'
                },
                'stochastic': {
                    'k': round(stoch_k.iloc[-1], 2) if not np.isnan(stoch_k.iloc[-1]) else 50,
                    'd': round(stoch_d.iloc[-1], 2) if not np.isnan(stoch_d.iloc[-1]) else 50,
                    'signal': 'oversold' if stoch_k.iloc[-1] < 20 else 'overbought' if stoch_k.iloc[-1] > 80 else 'neutral'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum indicators: {e}")
            return {'error': str(e)}
    
    def _detect_patterns(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Detect common chart patterns."""
        try:
            patterns = {
                'double_top': False,
                'double_bottom': False,
                'head_shoulders': False,
                'triangle': False,
                'flag': False,
                'breakout': False
            }
            
            # Simple pattern detection (can be enhanced with more sophisticated algorithms)
            recent_data = data.tail(20)
            highs = recent_data['high']
            lows = recent_data['low']
            
            # Breakout detection (price breaking recent high/low)
            recent_high = highs.max()
            recent_low = lows.min()
            current_price = data['close'].iloc[-1]
            
            if current_price > recent_high * 1.001:  # 0.1% above recent high
                patterns['breakout'] = 'upward'
            elif current_price < recent_low * 0.999:  # 0.1% below recent low
                patterns['breakout'] = 'downward'
            
            # Flag pattern (trending price with consolidation)
            price_range = recent_data['high'].max() - recent_data['low'].min()
            recent_range = recent_data.tail(5)['high'].max() - recent_data.tail(5)['low'].min()
            
            if recent_range / price_range < 0.3:  # Recent range is less than 30% of total range
                patterns['flag'] = True
            
            return {
                'detected_patterns': [k for k, v in patterns.items() if v and v != False],
                'pattern_details': patterns,
                'confidence': 'low'  # Simple patterns have low confidence
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting patterns: {e}")
            return {'error': str(e)}
    
    def _calculate_risk_metrics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate risk-related metrics."""
        try:
            returns = data['close'].pct_change().dropna()
            
            # Value at Risk (VaR) - 95% confidence
            var_95 = np.percentile(returns, 5)
            
            # Maximum Drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Sharpe Ratio (assuming 0% risk-free rate)
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # Downside volatility
            negative_returns = returns[returns < 0]
            downside_volatility = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
            
            return {
                'var_95': round(var_95 * 100, 2),  # Convert to percentage
                'max_drawdown': round(max_drawdown * 100, 2),
                'sharpe_ratio': round(sharpe_ratio, 3),
                'downside_volatility': round(downside_volatility, 4),
                'positive_days_pct': round(len(returns[returns > 0]) / len(returns) * 100, 1)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
            return {'error': str(e)}
    
    def _generate_strategy_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate signals for different strategy types."""
        try:
            signals = {
                'ma_crossover': self._ma_crossover_signal(data),
                'momentum': self._momentum_signal(data),
                'mean_reversion': self._mean_reversion_signal(data),
                'breakout': self._breakout_signal(data)
            }
            
            # Aggregate signal strength
            signal_scores = []
            for strategy_signals in signals.values():
                if 'signal' in strategy_signals and strategy_signals['signal'] != 'neutral':
                    strength = strategy_signals.get('strength', 0)
                    direction = 1 if strategy_signals['signal'] == 'buy' else -1
                    signal_scores.append(strength * direction)
            
            overall_signal = 'neutral'
            overall_strength = 0
            
            if signal_scores:
                overall_strength = sum(signal_scores) / len(signal_scores)
                if overall_strength > 0.3:
                    overall_signal = 'buy'
                elif overall_strength < -0.3:
                    overall_signal = 'sell'
            
            return {
                'individual_strategies': signals,
                'overall_signal': overall_signal,
                'overall_strength': round(overall_strength, 3)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating strategy signals: {e}")
            return {'error': str(e)}
    
    def _ma_crossover_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate Moving Average Crossover signals."""
        try:
            ema_9 = data['close'].ewm(span=9).mean()
            ema_21 = data['close'].ewm(span=21).mean()
            
            current_fast = ema_9.iloc[-1]
            current_slow = ema_21.iloc[-1]
            prev_fast = ema_9.iloc[-2]
            prev_slow = ema_21.iloc[-2]
            
            signal = 'neutral'
            strength = 0
            
            # Golden Cross (bullish)
            if prev_fast <= prev_slow and current_fast > current_slow:
                signal = 'buy'
                strength = min(1.0, abs(current_fast - current_slow) / current_slow * 10)
            
            # Death Cross (bearish)
            elif prev_fast >= prev_slow and current_fast < current_slow:
                signal = 'sell'
                strength = min(1.0, abs(current_fast - current_slow) / current_slow * 10)
            
            return {
                'signal': signal,
                'strength': round(strength, 3),
                'ema_9': round(current_fast, 2),
                'ema_21': round(current_slow, 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _momentum_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate momentum-based signals."""
        try:
            # RSI-based signal
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            signal = 'neutral'
            strength = 0
            
            if current_rsi < 30:  # Oversold
                signal = 'buy'
                strength = (30 - current_rsi) / 30
            elif current_rsi > 70:  # Overbought
                signal = 'sell'
                strength = (current_rsi - 70) / 30
            
            return {
                'signal': signal,
                'strength': round(strength, 3),
                'rsi': round(current_rsi, 2) if not np.isnan(current_rsi) else 50
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _mean_reversion_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate mean reversion signals."""
        try:
            # Bollinger Bands mean reversion
            bb_window = 20
            bb_std = 2
            bb_middle = data['close'].rolling(window=bb_window).mean()
            bb_upper = bb_middle + (data['close'].rolling(window=bb_window).std() * bb_std)
            bb_lower = bb_middle - (data['close'].rolling(window=bb_window).std() * bb_std)
            
            current_price = data['close'].iloc[-1]
            
            signal = 'neutral'
            strength = 0
            
            if current_price < bb_lower.iloc[-1]:  # Below lower band
                signal = 'buy'
                strength = min(1.0, (bb_lower.iloc[-1] - current_price) / bb_lower.iloc[-1])
            elif current_price > bb_upper.iloc[-1]:  # Above upper band
                signal = 'sell'
                strength = min(1.0, (current_price - bb_upper.iloc[-1]) / bb_upper.iloc[-1])
            
            return {
                'signal': signal,
                'strength': round(strength, 3),
                'bb_position': round((current_price - bb_middle.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]), 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _breakout_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate breakout signals."""
        try:
            # 20-period high/low breakout
            lookback = 20
            recent_data = data.tail(lookback + 1)
            
            current_price = data['close'].iloc[-1]
            highest_high = recent_data['high'].iloc[:-1].max()  # Exclude current candle
            lowest_low = recent_data['low'].iloc[:-1].min()
            
            signal = 'neutral'
            strength = 0
            
            if current_price > highest_high:  # Upward breakout
                signal = 'buy'
                strength = min(1.0, (current_price - highest_high) / highest_high * 10)
            elif current_price < lowest_low:  # Downward breakout
                signal = 'sell'
                strength = min(1.0, (lowest_low - current_price) / lowest_low * 10)
            
            return {
                'signal': signal,
                'strength': round(strength, 3),
                'breakout_high': round(highest_high, 2),
                'breakout_low': round(lowest_low, 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _assess_market_condition(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall market condition from analysis components."""
        try:
            scores = []
            
            # Trend score
            trend = analysis.get('trend_analysis', {})
            if trend.get('direction') == 'bullish':
                scores.append(trend.get('strength', 0))
            elif trend.get('direction') == 'bearish':
                scores.append(-trend.get('strength', 0))
            else:
                scores.append(0)
            
            # Momentum score
            momentum = analysis.get('momentum_indicators', {})
            rsi = momentum.get('rsi', 50)
            if rsi < 30:
                scores.append(0.5)  # Oversold - potential buy
            elif rsi > 70:
                scores.append(-0.5)  # Overbought - potential sell
            else:
                scores.append(0)
            
            # Volume score
            volume = analysis.get('volume_analysis', {})
            if volume.get('volume_breakout', False):
                scores.append(0.3)  # Volume confirmation
            else:
                scores.append(0)
            
            # Overall score
            overall_score = sum(scores) / len(scores) if scores else 0
            
            # Condition classification
            if overall_score > 0.3:
                condition = 'bullish'
                confidence = 'high' if overall_score > 0.6 else 'medium'
            elif overall_score < -0.3:
                condition = 'bearish'
                confidence = 'high' if overall_score < -0.6 else 'medium'
            else:
                condition = 'neutral'
                confidence = 'low'
            
            return {
                'condition': condition,
                'confidence': confidence,
                'score': round(overall_score, 3),
                'recommendation': self._generate_recommendation(condition, confidence, analysis)
            }
            
        except Exception as e:
            self.logger.error(f"Error assessing market condition: {e}")
            return {'error': str(e)}
    
    def _generate_recommendation(self, condition: str, confidence: str, analysis: Dict[str, Any]) -> str:
        """Generate trading recommendation based on analysis."""
        try:
            risk_metrics = analysis.get('risk_metrics', {})
            volatility = analysis.get('volatility_analysis', {})
            
            high_vol = volatility.get('regime') == 'high'
            high_risk = risk_metrics.get('var_95', 0) < -3  # More than 3% daily VaR
            
            if condition == 'bullish' and confidence == 'high' and not high_risk:
                return "Strong buy signal with good risk profile. Consider position entry."
            elif condition == 'bullish' and confidence == 'medium':
                return "Moderate buy signal. Consider smaller position or wait for confirmation."
            elif condition == 'bearish' and confidence == 'high' and not high_risk:
                return "Strong sell signal. Consider position exit or short entry."
            elif condition == 'bearish' and confidence == 'medium':
                return "Moderate sell signal. Consider reducing position or protective stops."
            elif high_vol or high_risk:
                return "High volatility/risk detected. Consider reducing position sizes or waiting."
            else:
                return "Neutral market conditions. Consider range trading or wait for clear signals."
                
        except Exception as e:
            return "Unable to generate recommendation due to analysis error."
    
    async def generate_comprehensive_report(self, symbol: str, timeframe: str = '15minute') -> Dict[str, Any]:
        """Generate a comprehensive analysis report for a symbol."""
        try:
            analysis = await self.analyze_market_conditions(symbol, timeframe)
            
            if 'error' in analysis:
                return analysis
            
            # Enhanced report with additional insights
            report = {
                'executive_summary': {
                    'symbol': symbol,
                    'analysis_date': get_current_time().isoformat(),
                    'market_condition': analysis['market_condition']['condition'],
                    'confidence': analysis['market_condition']['confidence'],
                    'recommendation': analysis['market_condition']['recommendation']
                },
                'detailed_analysis': analysis,
                'key_levels': {
                    'current_price': analysis['trend_analysis']['latest_price'],
                    'support_levels': analysis['support_resistance']['support_levels'],
                    'resistance_levels': analysis['support_resistance']['resistance_levels']
                },
                'risk_assessment': {
                    'risk_level': 'high' if analysis['risk_metrics']['var_95'] < -3 else 
                                 'medium' if analysis['risk_metrics']['var_95'] < -2 else 'low',
                    'volatility_regime': analysis['volatility_analysis']['regime'],
                    'max_drawdown': analysis['risk_metrics']['max_drawdown']
                },
                'strategy_recommendations': analysis['strategy_signals']
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating comprehensive report: {e}")
            return {'error': str(e)}
