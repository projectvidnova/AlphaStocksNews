"""
AI Feature Store
Centralized feature management and caching system for ML models
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import json
import sqlite3
from pathlib import Path

from ..utils.logger_setup import setup_logger
import hashlib

from src.data.clickhouse_data_layer import ClickHouseDataLayer
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


@dataclass
class FeatureDefinition:
    """Definition of a feature for the feature store."""
    name: str
    description: str
    data_type: str  # float, int, string, boolean
    calculation_window: Optional[int] = None  # lookback window in minutes
    dependencies: List[str] = None  # dependent features
    category: str = "technical"  # technical, fundamental, market, sentiment
    update_frequency: str = "realtime"  # realtime, daily, hourly
    created_at: datetime = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.created_at is None:
            self.created_at = get_current_time()


@dataclass 
class FeatureValue:
    """A computed feature value with metadata."""
    feature_name: str
    symbol: str
    value: Union[float, int, str, bool]
    timestamp: datetime
    confidence: float = 1.0
    data_source: str = "computed"


class FeatureCalculator:
    """Feature calculation engine with caching."""
    
    def __init__(self):
        self.calculators = {}
        self.logger = setup_logger("ai.feature_calculator")
        self._register_default_features()
    
    def _register_default_features(self):
        """Register built-in feature calculators."""
        
        # Price-based features
        self.calculators['price_change'] = self._calc_price_change
        self.calculators['price_volatility'] = self._calc_price_volatility
        self.calculators['returns'] = self._calc_returns
        self.calculators['log_returns'] = self._calc_log_returns
        
        # Moving averages
        for period in [5, 10, 20, 50, 200]:
            self.calculators[f'sma_{period}'] = lambda df, p=period: self._calc_sma(df, p)
            self.calculators[f'ema_{period}'] = lambda df, p=period: self._calc_ema(df, p)
            self.calculators[f'price_to_sma_{period}'] = lambda df, p=period: self._calc_price_to_ma(df, p)
        
        # Technical indicators
        self.calculators['rsi_14'] = lambda df: self._calc_rsi(df, 14)
        self.calculators['rsi_9'] = lambda df: self._calc_rsi(df, 9)
        self.calculators['macd'] = self._calc_macd
        self.calculators['bollinger_position'] = self._calc_bollinger_position
        self.calculators['stochastic_k'] = lambda df: self._calc_stochastic(df)[0]
        self.calculators['stochastic_d'] = lambda df: self._calc_stochastic(df)[1]
        
        # Volume features
        self.calculators['volume_sma_20'] = lambda df: self._calc_volume_sma(df, 20)
        self.calculators['volume_ratio'] = self._calc_volume_ratio
        self.calculators['volume_price_trend'] = self._calc_volume_price_trend
        
        # Market microstructure
        self.calculators['bid_ask_spread'] = self._calc_bid_ask_spread
        self.calculators['high_low_ratio'] = self._calc_high_low_ratio
        self.calculators['close_open_ratio'] = self._calc_close_open_ratio
        
        # Volatility features
        self.calculators['realized_volatility_5m'] = lambda df: self._calc_realized_vol(df, 5)
        self.calculators['realized_volatility_1h'] = lambda df: self._calc_realized_vol(df, 60)
        self.calculators['volatility_ratio'] = self._calc_volatility_ratio
        
        # Pattern recognition
        self.calculators['higher_highs'] = self._calc_higher_highs
        self.calculators['lower_lows'] = self._calc_lower_lows
        self.calculators['consolidation'] = self._calc_consolidation
        
        self.logger.info(f"Registered {len(self.calculators)} feature calculators")
    
    def calculate_feature(self, feature_name: str, data: pd.DataFrame, symbol: str = "UNKNOWN") -> List[FeatureValue]:
        """Calculate a specific feature."""
        
        if feature_name not in self.calculators:
            self.logger.warning(f"Unknown feature: {feature_name}")
            return []
        
        try:
            calculator = self.calculators[feature_name]
            values = calculator(data)
            
            if isinstance(values, pd.Series):
                feature_values = []
                for idx, val in values.items():
                    if not pd.isna(val) and idx in data.index:
                        timestamp = data.loc[idx, 'timestamp'] if 'timestamp' in data.columns else get_current_time()
                        feature_values.append(FeatureValue(
                            feature_name=feature_name,
                            symbol=symbol,
                            value=float(val) if isinstance(val, (int, float, np.number)) else val,
                            timestamp=timestamp,
                            confidence=1.0,
                            data_source="calculated"
                        ))
                return feature_values
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"Error calculating {feature_name}: {e}")
            return []
    
    # Price-based calculators
    def _calc_price_change(self, df: pd.DataFrame) -> pd.Series:
        return df['close'].diff()
    
    def _calc_price_volatility(self, df: pd.DataFrame) -> pd.Series:
        returns = df['close'].pct_change()
        return returns.rolling(20).std()
    
    def _calc_returns(self, df: pd.DataFrame) -> pd.Series:
        return df['close'].pct_change()
    
    def _calc_log_returns(self, df: pd.DataFrame) -> pd.Series:
        return np.log(df['close'] / df['close'].shift(1))
    
    # Moving average calculators
    def _calc_sma(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df['close'].rolling(period).mean()
    
    def _calc_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df['close'].ewm(span=period).mean()
    
    def _calc_price_to_ma(self, df: pd.DataFrame, period: int) -> pd.Series:
        ma = df['close'].rolling(period).mean()
        return df['close'] / ma
    
    # Technical indicator calculators
    def _calc_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calc_macd(self, df: pd.DataFrame) -> pd.Series:
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        return exp1 - exp2
    
    def _calc_bollinger_position(self, df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.Series:
        ma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        upper_band = ma + (std * std_dev)
        lower_band = ma - (std * std_dev)
        return (df['close'] - lower_band) / (upper_band - lower_band)
    
    def _calc_stochastic(self, df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series]:
        lowest_low = df['low'].rolling(window=period).min()
        highest_high = df['high'].rolling(window=period).max()
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(3).mean()
        return k_percent, d_percent
    
    # Volume calculators
    def _calc_volume_sma(self, df: pd.DataFrame, period: int) -> pd.Series:
        if 'volume' in df.columns:
            return df['volume'].rolling(period).mean()
        return pd.Series(index=df.index, dtype=float)
    
    def _calc_volume_ratio(self, df: pd.DataFrame) -> pd.Series:
        if 'volume' in df.columns:
            volume_ma = df['volume'].rolling(20).mean()
            return df['volume'] / volume_ma
        return pd.Series(index=df.index, dtype=float)
    
    def _calc_volume_price_trend(self, df: pd.DataFrame) -> pd.Series:
        if 'volume' in df.columns:
            price_change = df['close'].diff()
            return (price_change * df['volume']).rolling(10).sum()
        return pd.Series(index=df.index, dtype=float)
    
    # Market microstructure calculators
    def _calc_bid_ask_spread(self, df: pd.DataFrame) -> pd.Series:
        if 'bid' in df.columns and 'ask' in df.columns:
            return (df['ask'] - df['bid']) / df['ask']
        return pd.Series(index=df.index, dtype=float)
    
    def _calc_high_low_ratio(self, df: pd.DataFrame) -> pd.Series:
        return df['high'] / df['low']
    
    def _calc_close_open_ratio(self, df: pd.DataFrame) -> pd.Series:
        return df['close'] / df['open']
    
    # Volatility calculators
    def _calc_realized_vol(self, df: pd.DataFrame, window_minutes: int) -> pd.Series:
        returns = df['close'].pct_change()
        return returns.rolling(window_minutes).std() * np.sqrt(252 * 24 * 60 / window_minutes)
    
    def _calc_volatility_ratio(self, df: pd.DataFrame) -> pd.Series:
        short_vol = df['close'].pct_change().rolling(5).std()
        long_vol = df['close'].pct_change().rolling(20).std()
        return short_vol / long_vol
    
    # Pattern calculators
    def _calc_higher_highs(self, df: pd.DataFrame, lookback: int = 5) -> pd.Series:
        rolling_max = df['high'].rolling(lookback).max()
        return (df['high'] > rolling_max.shift(1)).astype(int)
    
    def _calc_lower_lows(self, df: pd.DataFrame, lookback: int = 5) -> pd.Series:
        rolling_min = df['low'].rolling(lookback).min()
        return (df['low'] < rolling_min.shift(1)).astype(int)
    
    def _calc_consolidation(self, df: pd.DataFrame, lookback: int = 10) -> pd.Series:
        high_low_range = df['high'].rolling(lookback).max() - df['low'].rolling(lookback).min()
        average_range = high_low_range.rolling(lookback).mean()
        return (high_low_range < average_range * 0.5).astype(int)


class FeatureStore:
    """Centralized feature store with caching and persistence."""
    
    def __init__(self, data_layer: ClickHouseDataLayer, cache_path: str = "data/feature_cache.db"):
        self.data_layer = data_layer
        self.cache_path = Path(cache_path)
        self.calculator = FeatureCalculator()
        self.feature_definitions = {}
        self.cache = {}  # In-memory cache
        self.logger = setup_logger("ai.feature_store")
        
        # Initialize SQLite cache
        self._init_cache_db()
        
        # Register default feature definitions
        self._register_default_features()
    
    def _init_cache_db(self):
        """Initialize SQLite database for feature caching."""
        
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    value REAL,
                    timestamp TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    data_hash TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(feature_name, symbol, timestamp)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feature_symbol_time 
                ON feature_cache(feature_name, symbol, timestamp)
            """)
    
    def _register_default_features(self):
        """Register default feature definitions."""
        
        # Price features
        price_features = [
            FeatureDefinition("price_change", "Price change from previous period", "float", 1),
            FeatureDefinition("returns", "Percentage returns", "float", 1),
            FeatureDefinition("log_returns", "Log returns", "float", 1),
            FeatureDefinition("price_volatility", "Rolling price volatility", "float", 20),
        ]
        
        # Technical indicators
        technical_features = [
            FeatureDefinition("rsi_14", "14-period Relative Strength Index", "float", 14),
            FeatureDefinition("rsi_9", "9-period Relative Strength Index", "float", 9),
            FeatureDefinition("macd", "MACD indicator", "float", 26),
            FeatureDefinition("bollinger_position", "Position within Bollinger Bands", "float", 20),
            FeatureDefinition("stochastic_k", "Stochastic %K", "float", 14),
            FeatureDefinition("stochastic_d", "Stochastic %D", "float", 14),
        ]
        
        # Moving averages
        ma_features = []
        for period in [5, 10, 20, 50, 200]:
            ma_features.extend([
                FeatureDefinition(f"sma_{period}", f"{period}-period Simple Moving Average", "float", period),
                FeatureDefinition(f"ema_{period}", f"{period}-period Exponential Moving Average", "float", period),
                FeatureDefinition(f"price_to_sma_{period}", f"Price to {period}-period SMA ratio", "float", period),
            ])
        
        # Volume features
        volume_features = [
            FeatureDefinition("volume_sma_20", "20-period Volume Moving Average", "float", 20, category="volume"),
            FeatureDefinition("volume_ratio", "Volume to average volume ratio", "float", 20, category="volume"),
            FeatureDefinition("volume_price_trend", "Volume-weighted price trend", "float", 10, category="volume"),
        ]
        
        # Volatility features
        volatility_features = [
            FeatureDefinition("realized_volatility_5m", "5-minute realized volatility", "float", 5, category="volatility"),
            FeatureDefinition("realized_volatility_1h", "1-hour realized volatility", "float", 60, category="volatility"),
            FeatureDefinition("volatility_ratio", "Short to long volatility ratio", "float", 20, category="volatility"),
        ]
        
        # Pattern features
        pattern_features = [
            FeatureDefinition("higher_highs", "Higher highs pattern", "int", 5, category="pattern"),
            FeatureDefinition("lower_lows", "Lower lows pattern", "int", 5, category="pattern"),
            FeatureDefinition("consolidation", "Price consolidation indicator", "int", 10, category="pattern"),
        ]
        
        # Register all features
        all_features = (
            price_features + technical_features + ma_features + 
            volume_features + volatility_features + pattern_features
        )
        
        for feature_def in all_features:
            self.feature_definitions[feature_def.name] = feature_def
        
        self.logger.info(f"Registered {len(all_features)} feature definitions")
    
    async def get_features(self, symbol: str, feature_names: List[str], 
                          start_time: datetime, end_time: datetime = None) -> pd.DataFrame:
        """Get feature values for specified time range."""
        
        if end_time is None:
            end_time = get_current_time()
        
        self.logger.info(f"Getting features {feature_names} for {symbol} from {start_time} to {end_time}")
        
        # Check cache first
        cached_features = self._get_cached_features(symbol, feature_names, start_time, end_time)
        
        # Identify missing features
        missing_features = []
        for feature_name in feature_names:
            if feature_name not in cached_features or len(cached_features[feature_name]) == 0:
                missing_features.append(feature_name)
        
        if missing_features:
            # Calculate missing features
            await self._calculate_missing_features(symbol, missing_features, start_time, end_time)
            
            # Retrieve from cache again
            cached_features = self._get_cached_features(symbol, feature_names, start_time, end_time)
        
        # Convert to DataFrame
        feature_df = self._features_to_dataframe(cached_features)
        
        return feature_df
    
    async def _calculate_missing_features(self, symbol: str, feature_names: List[str], 
                                        start_time: datetime, end_time: datetime):
        """Calculate and cache missing features."""
        
        # Get historical data with some buffer for indicators
        buffer_time = start_time - timedelta(days=30)  # Buffer for technical indicators
        
        try:
            historical_data = await self.data_layer.get_historical_data(
                symbol, buffer_time, end_time, "1m"
            )
            
            if historical_data.empty:
                self.logger.warning(f"No historical data available for {symbol}")
                return
            
            # Calculate each feature
            for feature_name in feature_names:
                feature_values = self.calculator.calculate_feature(
                    feature_name, historical_data, symbol
                )
                
                # Filter to requested time range and cache
                filtered_values = [
                    fv for fv in feature_values 
                    if start_time <= fv.timestamp <= end_time
                ]
                
                if filtered_values:
                    self._cache_features(filtered_values)
                    self.logger.debug(f"Calculated {len(filtered_values)} values for {feature_name}")
        
        except Exception as e:
            self.logger.error(f"Error calculating features for {symbol}: {e}")
    
    def _get_cached_features(self, symbol: str, feature_names: List[str], 
                           start_time: datetime, end_time: datetime) -> Dict[str, List[FeatureValue]]:
        """Retrieve features from cache."""
        
        cached_features = {}
        
        with sqlite3.connect(self.cache_path) as conn:
            for feature_name in feature_names:
                cursor = conn.execute("""
                    SELECT feature_name, symbol, value, timestamp, confidence
                    FROM feature_cache
                    WHERE feature_name = ? AND symbol = ? 
                    AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                """, (feature_name, symbol, start_time.isoformat(), end_time.isoformat()))
                
                feature_values = []
                for row in cursor.fetchall():
                    feature_values.append(FeatureValue(
                        feature_name=row[0],
                        symbol=row[1],
                        value=row[2],
                        timestamp=datetime.fromisoformat(row[3]),
                        confidence=row[4],
                        data_source="cache"
                    ))
                
                cached_features[feature_name] = feature_values
        
        return cached_features
    
    def _cache_features(self, feature_values: List[FeatureValue]):
        """Cache feature values to database."""
        
        with sqlite3.connect(self.cache_path) as conn:
            for fv in feature_values:
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO feature_cache 
                        (feature_name, symbol, value, timestamp, confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        fv.feature_name, fv.symbol, fv.value, 
                        fv.timestamp.isoformat(), fv.confidence,
                        get_current_time().isoformat()
                    ))
                except sqlite3.Error as e:
                    self.logger.error(f"Error caching feature {fv.feature_name}: {e}")
    
    def _features_to_dataframe(self, feature_dict: Dict[str, List[FeatureValue]]) -> pd.DataFrame:
        """Convert cached features to pandas DataFrame."""
        
        # Collect all data
        data_rows = []
        for feature_name, feature_values in feature_dict.items():
            for fv in feature_values:
                data_rows.append({
                    'timestamp': fv.timestamp,
                    feature_name: fv.value,
                    f'{feature_name}_confidence': fv.confidence
                })
        
        if not data_rows:
            return pd.DataFrame()
        
        # Convert to DataFrame and pivot
        df = pd.DataFrame(data_rows)
        
        if 'timestamp' in df.columns:
            df = df.set_index('timestamp').sort_index()
            
            # Combine rows with same timestamp
            df = df.groupby(df.index).first()
        
        return df
    
    def get_feature_definition(self, feature_name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name."""
        return self.feature_definitions.get(feature_name)
    
    def list_available_features(self, category: str = None) -> List[str]:
        """List all available features, optionally filtered by category."""
        
        if category:
            return [
                name for name, definition in self.feature_definitions.items()
                if definition.category == category
            ]
        else:
            return list(self.feature_definitions.keys())
    
    def register_custom_feature(self, feature_def: FeatureDefinition, calculator_func):
        """Register a custom feature with its calculator function."""
        
        self.feature_definitions[feature_def.name] = feature_def
        self.calculator.calculators[feature_def.name] = calculator_func
        
        self.logger.info(f"Registered custom feature: {feature_def.name}")
    
    async def refresh_features(self, symbol: str, feature_names: List[str]):
        """Force refresh of cached features."""
        
        # Clear cache for specified features
        with sqlite3.connect(self.cache_path) as conn:
            for feature_name in feature_names:
                conn.execute("""
                    DELETE FROM feature_cache 
                    WHERE feature_name = ? AND symbol = ?
                """, (feature_name, symbol))
        
        # Recalculate features
        end_time = get_current_time()
        start_time = end_time - timedelta(days=1)
        
        await self._calculate_missing_features(symbol, feature_names, start_time, end_time)
        
        self.logger.info(f"Refreshed features {feature_names} for {symbol}")


# Export main classes
__all__ = [
    'FeatureDefinition',
    'FeatureValue', 
    'FeatureCalculator',
    'FeatureStore'
]
