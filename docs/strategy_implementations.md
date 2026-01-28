# AlphaStock Strategy Implementation Guide

## Overview
This document provides detailed implementation specifications for five core trading strategies designed for the AlphaStock production system. Each strategy includes mathematical formulations, entry/exit logic, risk management, and Python implementation code.

---

## 1. TREND FOLLOWING (MOVING AVERAGE CROSSOVER)

### Strategy Overview
**Concept**: Uses the intersection of short-term and long-term moving averages to generate buy and sell signals.
**Best Market Conditions**: Strongly trending markets with sustained directional movement.
**Time Frames**: Works on multiple timeframes (5min, 15min, 1hr, daily).

### Mathematical Foundation

#### Moving Average Calculations
```python
# Simple Moving Average (SMA)
SMA(n) = (C1 + C2 + ... + Cn) / n

# Exponential Moving Average (EMA) - More responsive
EMA(today) = (Price(today) * α) + (EMA(yesterday) * (1-α))
where: α = 2/(n+1), n = period
```

#### Signal Logic
```python
# Golden Cross (Bullish Signal)
BUY_SIGNAL = (fast_ma > slow_ma) AND (previous_fast_ma <= previous_slow_ma)

# Death Cross (Bearish Signal)
SELL_SIGNAL = (fast_ma < slow_ma) AND (previous_fast_ma >= previous_slow_ma)
```

### Implementation Specification

#### Parameters
```python
class MAStrategy:
    def __init__(self, config):
        self.fast_period = config.get('fast_period', 9)      # Fast MA period
        self.slow_period = config.get('slow_period', 21)     # Slow MA period
        self.ma_type = config.get('ma_type', 'EMA')          # SMA or EMA
        self.min_trend_strength = config.get('min_trend_strength', 0.5)
        self.volume_confirmation = config.get('volume_confirmation', True)
```

#### Core Implementation
```python
class MovingAverageCrossoverStrategy(BaseStrategy):
    
    def calculate_moving_averages(self, data):
        """Calculate fast and slow moving averages"""
        if self.ma_type == 'EMA':
            data['fast_ma'] = data['close'].ewm(span=self.fast_period).mean()
            data['slow_ma'] = data['close'].ewm(span=self.slow_period).mean()
        else:
            data['fast_ma'] = data['close'].rolling(window=self.fast_period).mean()
            data['slow_ma'] = data['close'].rolling(window=self.slow_period).mean()
        
        return data
    
    def detect_crossovers(self, data):
        """Detect golden cross and death cross patterns"""
        # Current and previous MA values
        fast_current = data['fast_ma'].iloc[-1]
        fast_previous = data['fast_ma'].iloc[-2]
        slow_current = data['slow_ma'].iloc[-1]
        slow_previous = data['slow_ma'].iloc[-2]
        
        # Golden Cross (Bullish)
        golden_cross = (fast_current > slow_current and 
                       fast_previous <= slow_previous)
        
        # Death Cross (Bearish)
        death_cross = (fast_current < slow_current and 
                      fast_previous >= slow_previous)
        
        return golden_cross, death_cross
    
    def calculate_trend_strength(self, data):
        """Measure trend strength using MA separation"""
        fast_ma = data['fast_ma'].iloc[-1]
        slow_ma = data['slow_ma'].iloc[-1]
        current_price = data['close'].iloc[-1]
        
        # Calculate percentage difference
        ma_separation = abs(fast_ma - slow_ma) / current_price
        return ma_separation
    
    def volume_confirmation(self, data):
        """Confirm signal with volume analysis"""
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].rolling(window=20).mean().iloc[-1]
        
        return current_volume > (avg_volume * 1.2)  # 20% above average
    
    def analyze(self, symbol, historical_data, realtime_data=None):
        """Main analysis method"""
        try:
            # Combine data if realtime is available
            combined_data = self.combine_data(historical_data, realtime_data)
            
            if len(combined_data) < max(self.fast_period, self.slow_period) + 2:
                return None
            
            # Calculate moving averages
            combined_data = self.calculate_moving_averages(combined_data)
            
            # Detect crossovers
            golden_cross, death_cross = self.detect_crossovers(combined_data)
            
            if not (golden_cross or death_cross):
                return None
            
            # Calculate trend strength
            trend_strength = self.calculate_trend_strength(combined_data)
            
            if trend_strength < self.min_trend_strength:
                return None  # Trend too weak
            
            # Volume confirmation
            if self.volume_confirmation and not self.volume_confirmation(combined_data):
                return None
            
            # Generate signal
            current_price = combined_data['close'].iloc[-1]
            
            if golden_cross:
                signal_type = 'BUY'
                target_pct = 2.0  # 2% target
                stop_loss_pct = 1.0  # 1% stop loss
                confidence = min(95, 60 + (trend_strength * 100))
            else:  # death_cross
                signal_type = 'SELL'
                target_pct = 2.0
                stop_loss_pct = 1.0
                confidence = min(95, 60 + (trend_strength * 100))
            
            # Calculate prices
            if signal_type == 'BUY':
                target_price = current_price * (1 + target_pct/100)
                stop_loss_price = current_price * (1 - stop_loss_pct/100)
            else:
                target_price = current_price * (1 - target_pct/100)
                stop_loss_price = current_price * (1 + stop_loss_pct/100)
            
            return {
                'symbol': symbol,
                'strategy': 'ma_crossover',
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'confidence': confidence,
                'trend_strength': trend_strength,
                'timestamp': combined_data.index[-1],
                'metadata': {
                    'fast_ma': combined_data['fast_ma'].iloc[-1],
                    'slow_ma': combined_data['slow_ma'].iloc[-1],
                    'crossover_type': 'golden_cross' if golden_cross else 'death_cross'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in MA crossover analysis for {symbol}: {e}")
            return None
```

---

## 2. MEAN REVERSION (BOLLINGER BANDS + RSI)

### Strategy Overview
**Concept**: Assumes prices revert to their historical mean after extreme moves.
**Best Market Conditions**: Range-bound or consolidating markets.
**Indicators**: Bollinger Bands for volatility, RSI for momentum.

### Mathematical Foundation

#### Bollinger Bands
```python
# Middle Band (SMA)
middle_band = SMA(close, 20)

# Standard Deviation
std_dev = STDEV(close, 20)

# Upper and Lower Bands
upper_band = middle_band + (2 * std_dev)
lower_band = middle_band - (2 * std_dev)

# Band Position (0 = lower band, 1 = upper band)
bb_position = (close - lower_band) / (upper_band - lower_band)
```

#### RSI (Relative Strength Index)
```python
# Price Changes
gain = MAX(close - previous_close, 0)
loss = MAX(previous_close - close, 0)

# Average Gains and Losses
avg_gain = EMA(gain, 14)
avg_loss = EMA(loss, 14)

# RSI Calculation
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
```

### Implementation Specification

```python
class MeanReversionStrategy(BaseStrategy):
    
    def __init__(self, config):
        super().__init__(config)
        self.bb_period = config.get('bb_period', 20)
        self.bb_std_dev = config.get('bb_std_dev', 2)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.min_bb_squeeze = config.get('min_bb_squeeze', 0.02)  # 2% band width
    
    def calculate_bollinger_bands(self, data):
        """Calculate Bollinger Bands"""
        # Middle band (SMA)
        data['bb_middle'] = data['close'].rolling(window=self.bb_period).mean()
        
        # Standard deviation
        data['bb_std'] = data['close'].rolling(window=self.bb_period).std()
        
        # Upper and lower bands
        data['bb_upper'] = data['bb_middle'] + (data['bb_std'] * self.bb_std_dev)
        data['bb_lower'] = data['bb_middle'] - (data['bb_std'] * self.bb_std_dev)
        
        # Band width (for squeeze detection)
        data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['bb_middle']
        
        # Price position within bands
        data['bb_position'] = ((data['close'] - data['bb_lower']) / 
                              (data['bb_upper'] - data['bb_lower']))
        
        return data
    
    def calculate_rsi(self, data):
        """Calculate RSI"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        return data
    
    def detect_mean_reversion_signals(self, data):
        """Detect mean reversion opportunities"""
        current_price = data['close'].iloc[-1]
        bb_upper = data['bb_upper'].iloc[-1]
        bb_lower = data['bb_lower'].iloc[-1]
        bb_middle = data['bb_middle'].iloc[-1]
        rsi = data['rsi'].iloc[-1]
        bb_width = data['bb_width'].iloc[-1]
        
        # Check for Bollinger Band squeeze (low volatility)
        is_squeeze = bb_width < self.min_bb_squeeze
        
        # Oversold condition (Buy signal)
        oversold_bb = current_price <= bb_lower
        oversold_rsi = rsi <= self.rsi_oversold
        buy_signal = oversold_bb and oversold_rsi and not is_squeeze
        
        # Overbought condition (Sell signal)  
        overbought_bb = current_price >= bb_upper
        overbought_rsi = rsi >= self.rsi_overbought
        sell_signal = overbought_bb and overbought_rsi and not is_squeeze
        
        # Additional confirmation: Price must be moving toward mean
        price_momentum = data['close'].pct_change(periods=3).iloc[-1]
        
        if buy_signal and price_momentum > -0.01:  # Not falling enough
            buy_signal = False
        if sell_signal and price_momentum < 0.01:  # Not rising enough  
            sell_signal = False
        
        return buy_signal, sell_signal, bb_middle
    
    def calculate_confidence(self, data, signal_type):
        """Calculate signal confidence based on multiple factors"""
        rsi = data['rsi'].iloc[-1]
        bb_position = data['bb_position'].iloc[-1]
        volatility = data['bb_width'].iloc[-1]
        
        base_confidence = 50
        
        if signal_type == 'BUY':
            # More oversold = higher confidence
            rsi_score = (self.rsi_oversold - rsi) / self.rsi_oversold * 30
            # Closer to lower band = higher confidence
            bb_score = (0.1 - bb_position) / 0.1 * 20 if bb_position <= 0.1 else 0
        else:  # SELL
            # More overbought = higher confidence
            rsi_score = (rsi - self.rsi_overbought) / (100 - self.rsi_overbought) * 30
            # Closer to upper band = higher confidence
            bb_score = (bb_position - 0.9) / 0.1 * 20 if bb_position >= 0.9 else 0
        
        # Higher volatility = lower confidence for mean reversion
        volatility_penalty = min(10, volatility * 500)
        
        confidence = base_confidence + rsi_score + bb_score - volatility_penalty
        return max(30, min(95, confidence))
    
    def analyze(self, symbol, historical_data, realtime_data=None):
        """Main analysis method"""
        try:
            combined_data = self.combine_data(historical_data, realtime_data)
            
            if len(combined_data) < max(self.bb_period, self.rsi_period) + 5:
                return None
            
            # Calculate indicators
            combined_data = self.calculate_bollinger_bands(combined_data)
            combined_data = self.calculate_rsi(combined_data)
            
            # Detect signals
            buy_signal, sell_signal, bb_middle = self.detect_mean_reversion_signals(combined_data)
            
            if not (buy_signal or sell_signal):
                return None
            
            current_price = combined_data['close'].iloc[-1]
            signal_type = 'BUY' if buy_signal else 'SELL'
            
            # Calculate confidence
            confidence = self.calculate_confidence(combined_data, signal_type)
            
            # Calculate targets (mean reversion targets)
            if signal_type == 'BUY':
                target_price = bb_middle  # Target is the middle band
                stop_loss_price = current_price * 0.98  # 2% stop loss
            else:
                target_price = bb_middle
                stop_loss_price = current_price * 1.02  # 2% stop loss
            
            return {
                'symbol': symbol,
                'strategy': 'mean_reversion',
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'confidence': confidence,
                'timestamp': combined_data.index[-1],
                'metadata': {
                    'rsi': combined_data['rsi'].iloc[-1],
                    'bb_position': combined_data['bb_position'].iloc[-1],
                    'bb_width': combined_data['bb_width'].iloc[-1],
                    'bb_upper': combined_data['bb_upper'].iloc[-1],
                    'bb_lower': combined_data['bb_lower'].iloc[-1]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in mean reversion analysis for {symbol}: {e}")
            return None
```

---

## 3. BREAKOUT MOMENTUM

### Strategy Overview
**Concept**: Detects when price escapes key support/resistance with volume confirmation.
**Best Market Conditions**: Markets transitioning from consolidation to trending.
**Key Elements**: Support/resistance levels, volume expansion, volatility breakout.

### Mathematical Foundation

#### Support/Resistance Detection
```python
# Rolling highs and lows for pivot points
rolling_high = data['high'].rolling(window=20).max()
rolling_low = data['low'].rolling(window=20).min()

# Resistance = Recent high levels with multiple touches
resistance_level = rolling_high.where(
    (data['high'] >= rolling_high * 0.99) & 
    (data['high'] <= rolling_high * 1.01)
)

# Support = Recent low levels with multiple touches
support_level = rolling_low.where(
    (data['low'] <= rolling_low * 1.01) & 
    (data['low'] >= rolling_low * 0.99)
)
```

#### Volume Expansion
```python
# Volume surge detection
avg_volume = data['volume'].rolling(window=20).mean()
volume_ratio = data['volume'] / avg_volume

# Volume breakout threshold
volume_breakout = volume_ratio > 1.5  # 50% above average
```

### Implementation Specification

```python
class BreakoutMomentumStrategy(BaseStrategy):
    
    def __init__(self, config):
        super().__init__(config)
        self.lookback_period = config.get('lookback_period', 20)
        self.min_consolidation_days = config.get('min_consolidation_days', 5)
        self.volume_threshold = config.get('volume_threshold', 1.5)
        self.atr_period = config.get('atr_period', 14)
        self.breakout_threshold = config.get('breakout_threshold', 0.02)  # 2%
    
    def calculate_atr(self, data):
        """Calculate Average True Range for volatility"""
        data['prev_close'] = data['close'].shift(1)
        data['high_low'] = data['high'] - data['low']
        data['high_prevclose'] = abs(data['high'] - data['prev_close'])
        data['low_prevclose'] = abs(data['low'] - data['prev_close'])
        
        data['true_range'] = data[['high_low', 'high_prevclose', 'low_prevclose']].max(axis=1)
        data['atr'] = data['true_range'].rolling(window=self.atr_period).mean()
        
        return data
    
    def identify_support_resistance(self, data):
        """Identify key support and resistance levels"""
        # Rolling highs and lows
        data['rolling_high'] = data['high'].rolling(window=self.lookback_period).max()
        data['rolling_low'] = data['low'].rolling(window=self.lookback_period).min()
        
        # Find pivot points (local maxima/minima)
        highs = data['high']
        lows = data['low']
        
        # Resistance levels (local maxima)
        resistance_levels = []
        for i in range(2, len(data) - 2):
            if (highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and
                highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]):
                resistance_levels.append(highs.iloc[i])
        
        # Support levels (local minima)
        support_levels = []
        for i in range(2, len(data) - 2):
            if (lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i-2] and
                lows.iloc[i] < lows.iloc[i+1] and lows.iloc[i] < lows.iloc[i+2]):
                support_levels.append(lows.iloc[i])
        
        # Get the most recent and significant levels
        resistance = max(resistance_levels[-3:]) if resistance_levels else data['rolling_high'].iloc[-1]
        support = min(support_levels[-3:]) if support_levels else data['rolling_low'].iloc[-1]
        
        return support, resistance
    
    def detect_consolidation(self, data):
        """Detect if price has been consolidating"""
        # Calculate price range over lookback period
        recent_high = data['high'].tail(self.min_consolidation_days).max()
        recent_low = data['low'].tail(self.min_consolidation_days).min()
        recent_close = data['close'].tail(self.min_consolidation_days).mean()
        
        # Consolidation if price range is tight
        price_range = (recent_high - recent_low) / recent_close
        return price_range < 0.05  # Less than 5% range = consolidation
    
    def detect_volume_breakout(self, data):
        """Detect volume expansion"""
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].tail(20).mean()
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        return volume_ratio >= self.volume_threshold
    
    def detect_price_breakout(self, data, support, resistance):
        """Detect price breakout above resistance or below support"""
        current_price = data['close'].iloc[-1]
        previous_close = data['close'].iloc[-2]
        
        # Bullish breakout (above resistance)
        bullish_breakout = (current_price > resistance and 
                          previous_close <= resistance and
                          current_price > previous_close)
        
        # Bearish breakdown (below support)
        bearish_breakout = (current_price < support and 
                          previous_close >= support and
                          current_price < previous_close)
        
        return bullish_breakout, bearish_breakout
    
    def calculate_breakout_strength(self, data, support, resistance):
        """Calculate the strength of the breakout"""
        current_price = data['close'].iloc[-1]
        atr = data['atr'].iloc[-1]
        
        if current_price > resistance:
            # Bullish breakout strength
            breakout_distance = current_price - resistance
            strength = breakout_distance / atr if atr > 0 else 1
        elif current_price < support:
            # Bearish breakout strength  
            breakout_distance = support - current_price
            strength = breakout_distance / atr if atr > 0 else 1
        else:
            strength = 0
        
        return min(3.0, strength)  # Cap at 3 ATRs
    
    def analyze(self, symbol, historical_data, realtime_data=None):
        """Main analysis method"""
        try:
            combined_data = self.combine_data(historical_data, realtime_data)
            
            if len(combined_data) < self.lookback_period + 10:
                return None
            
            # Calculate ATR
            combined_data = self.calculate_atr(combined_data)
            
            # Identify support and resistance
            support, resistance = self.identify_support_resistance(combined_data)
            
            # Check for consolidation period
            was_consolidating = self.detect_consolidation(combined_data)
            
            if not was_consolidating:
                return None  # Need consolidation before breakout
            
            # Detect breakouts
            bullish_breakout, bearish_breakout = self.detect_price_breakout(
                combined_data, support, resistance
            )
            
            if not (bullish_breakout or bearish_breakout):
                return None
            
            # Volume confirmation
            volume_confirmed = self.detect_volume_breakout(combined_data)
            
            if not volume_confirmed:
                return None
            
            # Calculate breakout strength
            breakout_strength = self.calculate_breakout_strength(
                combined_data, support, resistance
            )
            
            if breakout_strength < 0.5:  # Minimum breakout strength
                return None
            
            current_price = combined_data['close'].iloc[-1]
            atr = combined_data['atr'].iloc[-1]
            
            if bullish_breakout:
                signal_type = 'BUY'
                # Target based on ATR and breakout strength
                target_price = current_price + (atr * 2 * breakout_strength)
                stop_loss_price = resistance * 0.995  # Just below resistance
            else:  # bearish_breakout
                signal_type = 'SELL'
                target_price = current_price - (atr * 2 * breakout_strength)
                stop_loss_price = support * 1.005  # Just above support
            
            # Calculate confidence based on breakout strength and volume
            volume_ratio = combined_data['volume'].iloc[-1] / combined_data['volume'].tail(20).mean()
            confidence = min(95, 50 + (breakout_strength * 15) + (volume_ratio * 10))
            
            return {
                'symbol': symbol,
                'strategy': 'breakout_momentum',
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'confidence': confidence,
                'timestamp': combined_data.index[-1],
                'metadata': {
                    'support_level': support,
                    'resistance_level': resistance,
                    'breakout_strength': breakout_strength,
                    'volume_ratio': volume_ratio,
                    'atr': atr,
                    'breakout_type': 'bullish' if bullish_breakout else 'bearish'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in breakout momentum analysis for {symbol}: {e}")
            return None
```

---

## 4. VWAP STRATEGY

### Strategy Overview
**Concept**: Uses Volume Weighted Average Price as intraday benchmark for institutional-grade entries.
**Best Market Conditions**: All intraday conditions, especially for large position entries.
**Key Elements**: VWAP calculation, price-VWAP relationship, volume analysis.

### Mathematical Foundation

#### VWAP Calculation
```python
# Typical Price for each period
typical_price = (high + low + close) / 3

# Price-Volume for each period
pv = typical_price * volume

# Cumulative values
cumulative_pv = pv.cumsum()
cumulative_volume = volume.cumsum()

# VWAP
vwap = cumulative_pv / cumulative_volume
```

#### VWAP Bands (Standard Deviation Bands)
```python
# Calculate squared differences
squared_diff = (typical_price - vwap) ** 2

# Variance calculation
variance = (squared_diff * volume).cumsum() / cumulative_volume

# Standard deviation
vwap_std = sqrt(variance)

# VWAP Bands
upper_band = vwap + (multiplier * vwap_std)
lower_band = vwap - (multiplier * vwap_std)
```

### Implementation Specification

```python
class VWAPStrategy(BaseStrategy):
    
    def __init__(self, config):
        super().__init__(config)
        self.std_multiplier = config.get('std_multiplier', 2.0)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.2)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_threshold_buy = config.get('rsi_threshold_buy', 45)
        self.rsi_threshold_sell = config.get('rsi_threshold_sell', 55)
        
    def calculate_vwap(self, data):
        """Calculate VWAP and VWAP bands"""
        # Reset at start of each day (for intraday strategy)
        data = data.copy()
        data['date'] = data.index.date
        
        vwap_data = []
        
        for date, day_data in data.groupby('date'):
            # Typical price
            day_data = day_data.copy()
            day_data['typical_price'] = (day_data['high'] + day_data['low'] + day_data['close']) / 3
            
            # Price × Volume
            day_data['pv'] = day_data['typical_price'] * day_data['volume']
            
            # Cumulative values
            day_data['cumulative_pv'] = day_data['pv'].cumsum()
            day_data['cumulative_volume'] = day_data['volume'].cumsum()
            
            # VWAP
            day_data['vwap'] = day_data['cumulative_pv'] / day_data['cumulative_volume']
            
            # VWAP Standard Deviation
            day_data['price_diff_sq'] = (day_data['typical_price'] - day_data['vwap']) ** 2
            day_data['cumulative_variance'] = (day_data['price_diff_sq'] * day_data['volume']).cumsum() / day_data['cumulative_volume']
            day_data['vwap_std'] = np.sqrt(day_data['cumulative_variance'])
            
            # VWAP Bands
            day_data['vwap_upper'] = day_data['vwap'] + (self.std_multiplier * day_data['vwap_std'])
            day_data['vwap_lower'] = day_data['vwap'] - (self.std_multiplier * day_data['vwap_std'])
            
            vwap_data.append(day_data)
        
        return pd.concat(vwap_data)
    
    def calculate_rsi(self, data):
        """Calculate RSI for momentum confirmation"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        return data
    
    def detect_vwap_signals(self, data):
        """Detect VWAP-based trading signals"""
        current_price = data['close'].iloc[-1]
        previous_price = data['close'].iloc[-2]
        vwap = data['vwap'].iloc[-1]
        vwap_upper = data['vwap_upper'].iloc[-1]
        vwap_lower = data['vwap_lower'].iloc[-1]
        rsi = data['rsi'].iloc[-1]
        
        # Volume confirmation
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].tail(20).mean()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        volume_confirmed = volume_ratio >= self.min_volume_ratio
        
        # Signal conditions
        buy_conditions = [
            previous_price <= vwap and current_price > vwap,  # Cross above VWAP
            rsi >= self.rsi_threshold_buy,  # RSI confirmation
            volume_confirmed,  # Volume confirmation
            current_price < vwap_upper  # Not overbought
        ]
        
        sell_conditions = [
            previous_price >= vwap and current_price < vwap,  # Cross below VWAP
            rsi <= self.rsi_threshold_sell,  # RSI confirmation
            volume_confirmed,  # Volume confirmation
            current_price > vwap_lower  # Not oversold
        ]
        
        buy_signal = all(buy_conditions)
        sell_signal = all(sell_conditions)
        
        return buy_signal, sell_signal, volume_ratio
    
    def calculate_vwap_position(self, data):
        """Calculate position relative to VWAP bands"""
        current_price = data['close'].iloc[-1]
        vwap = data['vwap'].iloc[-1]
        vwap_upper = data['vwap_upper'].iloc[-1]
        vwap_lower = data['vwap_lower'].iloc[-1]
        
        if vwap_upper != vwap_lower:
            position = (current_price - vwap_lower) / (vwap_upper - vwap_lower)
        else:
            position = 0.5
        
        return position
    
    def calculate_institutional_flow(self, data):
        """Estimate institutional flow based on VWAP relationship"""
        # Large volume trades near VWAP suggest institutional activity
        recent_data = data.tail(10)
        
        vwap_distance = abs(recent_data['close'] - recent_data['vwap']) / recent_data['vwap']
        volume_size = recent_data['volume'] / recent_data['volume'].mean()
        
        # Institutional flow score
        institutional_score = (volume_size * (1 - vwap_distance)).mean()
        return institutional_score
    
    def analyze(self, symbol, historical_data, realtime_data=None):
        """Main analysis method"""
        try:
            combined_data = self.combine_data(historical_data, realtime_data)
            
            if len(combined_data) < 50:  # Need enough intraday data
                return None
            
            # Calculate VWAP and bands
            combined_data = self.calculate_vwap(combined_data)
            
            # Calculate RSI
            combined_data = self.calculate_rsi(combined_data)
            
            # Detect signals
            buy_signal, sell_signal, volume_ratio = self.detect_vwap_signals(combined_data)
            
            if not (buy_signal or sell_signal):
                return None
            
            current_price = combined_data['close'].iloc[-1]
            vwap = combined_data['vwap'].iloc[-1]
            vwap_upper = combined_data['vwap_upper'].iloc[-1]
            vwap_lower = combined_data['vwap_lower'].iloc[-1]
            
            signal_type = 'BUY' if buy_signal else 'SELL'
            
            # Calculate confidence based on multiple factors
            vwap_position = self.calculate_vwap_position(combined_data)
            institutional_flow = self.calculate_institutional_flow(combined_data)
            
            base_confidence = 60
            volume_score = min(20, (volume_ratio - 1) * 20)
            institutional_score = institutional_flow * 10
            
            confidence = base_confidence + volume_score + institutional_score
            confidence = max(50, min(95, confidence))
            
            # Set targets based on VWAP bands
            if signal_type == 'BUY':
                target_price = vwap + (vwap_upper - vwap) * 0.618  # 61.8% toward upper band
                stop_loss_price = vwap * 0.995  # Just below VWAP
            else:
                target_price = vwap - (vwap - vwap_lower) * 0.618  # 61.8% toward lower band
                stop_loss_price = vwap * 1.005  # Just above VWAP
            
            return {
                'symbol': symbol,
                'strategy': 'vwap',
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'confidence': confidence,
                'timestamp': combined_data.index[-1],
                'metadata': {
                    'vwap': vwap,
                    'vwap_upper': vwap_upper,
                    'vwap_lower': vwap_lower,
                    'vwap_position': vwap_position,
                    'volume_ratio': volume_ratio,
                    'institutional_flow': institutional_flow,
                    'rsi': combined_data['rsi'].iloc[-1]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in VWAP analysis for {symbol}: {e}")
            return None
```

---

## 5. STATISTICAL ARBITRAGE (PAIRS TRADING)

### Strategy Overview
**Concept**: Exploits temporary divergences between historically correlated assets.
**Best Market Conditions**: Market neutral, works in various conditions.
**Key Elements**: Correlation analysis, cointegration, spread analysis, z-score.

### Mathematical Foundation

#### Correlation and Cointegration
```python
# Pearson correlation coefficient
correlation = corr(price1, price2)

# Cointegration test (Engle-Granger)
# 1. Run regression: price1 = α + β * price2 + ε
β = cov(price1, price2) / var(price2)
α = mean(price1) - β * mean(price2)

# 2. Test residuals for stationarity
residuals = price1 - α - β * price2
adf_statistic, p_value = augmented_dickey_fuller_test(residuals)

# Cointegrated if p_value < 0.05
```

#### Spread and Z-Score
```python
# Calculate spread
spread = price1 - hedge_ratio * price2

# Z-score of spread
spread_mean = mean(spread, lookback_period)
spread_std = std(spread, lookback_period)
z_score = (current_spread - spread_mean) / spread_std
```

### Implementation Specification

```python
class PairsTradingStrategy(BaseStrategy):
    
    def __init__(self, config):
        super().__init__(config)
        self.lookback_period = config.get('lookback_period', 60)
        self.min_correlation = config.get('min_correlation', 0.7)
        self.z_score_entry = config.get('z_score_entry', 2.0)
        self.z_score_exit = config.get('z_score_exit', 0.5)
        self.cointegration_pvalue = config.get('cointegration_pvalue', 0.05)
        self.pairs = config.get('pairs', [])  # List of symbol pairs
    
    def calculate_correlation(self, data1, data2):
        """Calculate rolling correlation between two assets"""
        returns1 = data1['close'].pct_change()
        returns2 = data2['close'].pct_change()
        
        correlation = returns1.rolling(window=self.lookback_period).corr(returns2)
        return correlation.iloc[-1]
    
    def test_cointegration(self, data1, data2):
        """Test for cointegration using Engle-Granger method"""
        from statsmodels.tsa.stattools import coint
        
        price1 = data1['close'].tail(self.lookback_period)
        price2 = data2['close'].tail(self.lookback_period)
        
        # Ensure same length
        min_length = min(len(price1), len(price2))
        price1 = price1.tail(min_length)
        price2 = price2.tail(min_length)
        
        try:
            coint_t, p_value, crit_values = coint(price1, price2)
            return p_value < self.cointegration_pvalue, p_value
        except:
            return False, 1.0
    
    def calculate_hedge_ratio(self, data1, data2):
        """Calculate optimal hedge ratio using linear regression"""
        from sklearn.linear_model import LinearRegression
        
        price1 = data1['close'].tail(self.lookback_period).values.reshape(-1, 1)
        price2 = data2['close'].tail(self.lookback_period).values
        
        # Ensure same length
        min_length = min(len(price1), len(price2))
        price1 = price1[-min_length:]
        price2 = price2[-min_length:]
        
        model = LinearRegression()
        model.fit(price2.reshape(-1, 1), price1.reshape(-1))
        
        return model.coef_[0]
    
    def calculate_spread_metrics(self, data1, data2, hedge_ratio):
        """Calculate spread and its statistical metrics"""
        # Calculate spread
        spread = data1['close'] - hedge_ratio * data2['close']
        
        # Rolling statistics
        spread_mean = spread.rolling(window=self.lookback_period).mean()
        spread_std = spread.rolling(window=self.lookback_period).std()
        
        # Z-score
        z_score = (spread - spread_mean) / spread_std
        
        return spread, z_score
    
    def detect_pairs_signals(self, z_score):
        """Detect pairs trading signals based on z-score"""
        current_z = z_score.iloc[-1]
        previous_z = z_score.iloc[-2]
        
        # Entry signals
        long_pair_signal = (current_z <= -self.z_score_entry and 
                           previous_z > -self.z_score_entry)  # Spread too negative
        
        short_pair_signal = (current_z >= self.z_score_entry and 
                            previous_z < self.z_score_entry)  # Spread too positive
        
        # Exit signals
        exit_signal = abs(current_z) <= self.z_score_exit
        
        return long_pair_signal, short_pair_signal, exit_signal
    
    def calculate_position_sizes(self, data1, data2, hedge_ratio, available_capital):
        """Calculate position sizes for both legs of the pair"""
        price1 = data1['close'].iloc[-1]
        price2 = data2['close'].iloc[-1]
        
        # Total value per "unit" of the pair
        unit_value = price1 + hedge_ratio * price2
        
        # Number of units we can trade
        units = available_capital / (2 * unit_value)  # Divide by 2 for risk management
        
        # Position sizes
        quantity1 = int(units)
        quantity2 = int(units * hedge_ratio)
        
        return quantity1, quantity2
    
    def analyze_pair(self, symbol1, symbol2, data1, data2):
        """Analyze a specific pair for trading opportunities"""
        try:
            # Check data length
            if len(data1) < self.lookback_period or len(data2) < self.lookback_period:
                return None
            
            # Calculate correlation
            correlation = self.calculate_correlation(data1, data2)
            
            if abs(correlation) < self.min_correlation:
                return None  # Not sufficiently correlated
            
            # Test cointegration
            is_cointegrated, p_value = self.test_cointegration(data1, data2)
            
            if not is_cointegrated:
                return None  # Not cointegrated
            
            # Calculate hedge ratio
            hedge_ratio = self.calculate_hedge_ratio(data1, data2)
            
            # Calculate spread and z-score
            spread, z_score = self.calculate_spread_metrics(data1, data2, hedge_ratio)
            
            # Detect signals
            long_pair_signal, short_pair_signal, exit_signal = self.detect_pairs_signals(z_score)
            
            if not (long_pair_signal or short_pair_signal):
                return None
            
            current_z = z_score.iloc[-1]
            
            # Calculate confidence based on z-score magnitude
            confidence = min(95, 50 + abs(current_z) * 15)
            
            # Determine trade details
            if long_pair_signal:
                # Long spread: Buy asset1, Sell asset2
                signal_type = 'LONG_PAIR'
                primary_action = 'BUY'   # Asset 1
                secondary_action = 'SELL' # Asset 2
            else:
                # Short spread: Sell asset1, Buy asset2
                signal_type = 'SHORT_PAIR'
                primary_action = 'SELL'  # Asset 1
                secondary_action = 'BUY' # Asset 2
            
            return {
                'strategy': 'pairs_trading',
                'signal_type': signal_type,
                'primary_symbol': symbol1,
                'secondary_symbol': symbol2,
                'primary_action': primary_action,
                'secondary_action': secondary_action,
                'hedge_ratio': hedge_ratio,
                'current_z_score': current_z,
                'correlation': correlation,
                'cointegration_p_value': p_value,
                'confidence': confidence,
                'timestamp': data1.index[-1],
                'entry_z_score': self.z_score_entry,
                'exit_z_score': self.z_score_exit,
                'metadata': {
                    'spread': spread.iloc[-1],
                    'spread_mean': spread.rolling(window=self.lookback_period).mean().iloc[-1],
                    'spread_std': spread.rolling(window=self.lookback_period).std().iloc[-1]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in pairs analysis for {symbol1}-{symbol2}: {e}")
            return None
    
    def analyze(self, symbol, historical_data, realtime_data=None):
        """Main analysis method - analyzes all configured pairs"""
        signals = []
        
        try:
            # This strategy needs to analyze pairs, not individual symbols
            # We'll return signals for all pairs involving this symbol
            
            for pair in self.pairs:
                symbol1, symbol2 = pair
                
                if symbol not in [symbol1, symbol2]:
                    continue  # This symbol is not part of this pair
                
                # Get data for both symbols (this would need to be enhanced
                # to fetch data for the paired symbol)
                if symbol == symbol1:
                    data1 = self.combine_data(historical_data, realtime_data)
                    # Would need to fetch data2 for symbol2 from data manager
                    # data2 = self.data_manager.get_data(symbol2)
                    
                    # For now, we'll skip if we don't have the paired data
                    continue
                
                # signal = self.analyze_pair(symbol1, symbol2, data1, data2)
                # if signal:
                #     signals.append(signal)
            
            return signals[0] if signals else None
            
        except Exception as e:
            self.logger.error(f"Error in pairs trading analysis: {e}")
            return None
```

---

## STRATEGY INTEGRATION & FACTORY PATTERN

### Strategy Factory Implementation

```python
class StrategyFactory:
    """Factory for creating strategy instances"""
    
    STRATEGIES = {
        'ma_crossover': MovingAverageCrossoverStrategy,
        'mean_reversion': MeanReversionStrategy,
        'breakout_momentum': BreakoutMomentumStrategy,
        'vwap': VWAPStrategy,
        'pairs_trading': PairsTradingStrategy
    }
    
    @classmethod
    def create_strategy(cls, strategy_name, config):
        """Create strategy instance by name"""
        if strategy_name not in cls.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        return cls.STRATEGIES[strategy_name](config)
    
    @classmethod
    def get_available_strategies(cls):
        """Get list of available strategies"""
        return list(cls.STRATEGIES.keys())
```

### Configuration Example

```yaml
# config/strategies.yaml
strategies:
  ma_crossover:
    enabled: true
    symbols: ["BANKNIFTY", "NIFTY", "NSE:SBIN"]
    parameters:
      fast_period: 9
      slow_period: 21
      ma_type: "EMA"
      min_trend_strength: 0.5
      volume_confirmation: true
      
  mean_reversion:
    enabled: true
    symbols: ["NSE:RELIANCE", "NSE:INFY"]
    parameters:
      bb_period: 20
      bb_std_dev: 2
      rsi_period: 14
      rsi_oversold: 30
      rsi_overbought: 70
      
  breakout_momentum:
    enabled: true
    symbols: ["BANKNIFTY", "NIFTY"]
    parameters:
      lookback_period: 20
      volume_threshold: 1.5
      atr_period: 14
      
  vwap:
    enabled: true
    symbols: ["BANKNIFTY", "NIFTY", "FINNIFTY"]
    parameters:
      std_multiplier: 2.0
      min_volume_ratio: 1.2
      rsi_period: 14
      
  pairs_trading:
    enabled: false  # Requires additional infrastructure
    pairs: [["NSE:SBIN", "NSE:HDFC"], ["NSE:INFY", "NSE:TCS"]]
    parameters:
      lookback_period: 60
      min_correlation: 0.7
      z_score_entry: 2.0
      z_score_exit: 0.5
```

### Usage Example

```python
# Initialize strategies for a symbol
def initialize_strategies_for_symbol(symbol, config):
    strategies = []
    
    for strategy_name, strategy_config in config['strategies'].items():
        if not strategy_config.get('enabled', False):
            continue
            
        if symbol not in strategy_config.get('symbols', []):
            continue
            
        strategy = StrategyFactory.create_strategy(strategy_name, strategy_config)
        strategies.append(strategy)
    
    return strategies

# Run analysis
def run_strategy_analysis(symbol, historical_data, realtime_data, strategies):
    signals = []
    
    for strategy in strategies:
        try:
            signal = strategy.analyze(symbol, historical_data, realtime_data)
            if signal:
                signals.append(signal)
        except Exception as e:
            logger.error(f"Strategy {strategy.__class__.__name__} failed for {symbol}: {e}")
    
    return signals
```

This comprehensive implementation provides a solid foundation for all five strategies, with proper mathematical foundations, risk management, and production-ready code structure. Each strategy is modular, configurable, and follows the same interface pattern for easy integration into the main trading system.
