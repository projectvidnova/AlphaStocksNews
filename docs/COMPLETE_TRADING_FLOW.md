# AlphaStocks Complete Trading Flow Analysis

## 📊 Complete Flow: From Index Fetch to Order Placement

This document provides a comprehensive analysis of how the AlphaStocks system works from data collection to trade execution.

---

## 🔄 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MAIN ORCHESTRATOR                            │
│                        (src/orchestrator.py)                         │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ├─── 1. API CLIENT (Kite Connect)
               ├─── 2. DATA LAYER (ClickHouse/PostgreSQL)
               ├─── 3. RUNNERS (Index, Equity, Options, Futures)
               ├─── 4. STRATEGY FACTORY & STRATEGIES
               ├─── 5. SIGNAL MANAGER
               ├─── 6. OPTIONS TRADE EXECUTOR
               └─── 7. POSITION MANAGER
```

---

## 📈 PHASE 1: INDEX DATA COLLECTION

### 1.1 Index Runner Initialization

**File**: `src/runners/index_runner.py`

```python
class IndexRunner(BaseRunner):
    """Handles market indices data collection"""
    
    def __init__(self, api_client, data_cache, indices: List[str], interval_seconds: int = 5):
        # Indices: ['NIFTY50', 'BANKNIFTY', 'FINNIFTY', etc.]
        self.symbols = indices
        self.interval_seconds = 5  # Collect every 5 seconds
        self.sectoral_indices = ['NIFTYBANK', 'NIFTYIT', 'NIFTYFMCG', etc.]
```

**Configuration**: `config/production.json`

```json
{
  "data_collection": {
    "runners": {
      "index": {
        "enabled": true,
        "symbols": ["NIFTY50", "BANKNIFTY"],
        "interval_seconds": 5
      }
    }
  }
}
```

### 1.2 Index Data Fetching Process

**Step-by-Step Flow**:

```
1. IndexRunner.start() called by Orchestrator
   ↓
2. Every 5 seconds: fetch_market_data() is called
   ↓
3. IndexRunner.fetch_market_data(symbols=['BANKNIFTY'])
   ├─ api_client.get_ohlc(['BANKNIFTY'])  # Get OHLC data
   └─ api_client.get_ltp(['BANKNIFTY'])   # Get Last Traded Price
   ↓
4. Data combined and processed
   ↓
5. process_data() creates DataFrame with:
   - timestamp
   - symbol (BANKNIFTY)
   - asset_type (INDEX)
   - open, high, low, close
   - ltp (Last Traded Price)
   - volume, turnover
   - price_change, price_change_pct
   - volatility (calculated)
   ↓
6. Data stored in ClickHouse database via data_layer
   ↓
7. Callback triggered: _on_new_runner_data()
```

**Code Example** (`src/runners/index_runner.py`):

```python
def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
    """Fetch index data from Kite API"""
    try:
        # Get OHLC data (Open, High, Low, Close)
        ohlc_data = self.api_client.get_ohlc(symbols)
        
        # Get Last Traded Price
        ltp_data = self.api_client.get_ltp(symbols)
        
        # Combine data
        combined_data = {}
        for symbol in symbols:
            if symbol in ohlc_data:
                data = ohlc_data[symbol].copy()
                
                if symbol in ltp_data:
                    data['ltp'] = ltp_data[symbol]
                
                # Add metadata
                data['index_type'] = self._get_index_type(symbol)
                data['sector'] = self._get_index_sector(symbol)
                
                combined_data[symbol] = data
        
        return combined_data
        
    except Exception as e:
        self.logger.error(f"Error fetching index data: {e}")
        return {}
```

### 1.3 Kite API Connection

**File**: `src/api/kite_client.py`

```python
# Actual API call to Zerodha
def get_ohlc(self, symbols: Union[str, List[str]]) -> Dict[str, Dict[str, float]]:
    """Get OHLC data for symbols"""
    try:
        self._rate_limit()  # Rate limiting to avoid API throttling
        
        # Convert single symbol to list
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Get instrument tokens for symbols
        instruments = []
        for symbol in symbols:
            exchange = "NSE"  # Default exchange
            instruments.append(f"{exchange}:{symbol}")
        
        # Call Kite Connect API
        ohlc_data = self.kite.ohlc(instruments)
        
        # Parse and return data
        result = {}
        for symbol in symbols:
            key = f"NSE:{symbol}"
            if key in ohlc_data:
                result[symbol] = ohlc_data[key]['ohlc']
        
        return result
        
    except Exception as e:
        self.logger.error(f"Error fetching OHLC: {e}")
        return {}
```

**Real API Call Flow**:
```
Python Application
    ↓
KiteAPIClient.get_ohlc()
    ↓
self.kite.ohlc()  (Official KiteConnect SDK)
    ↓
HTTPS Request to: https://api.kite.trade/
    ↓
Zerodha Kite Servers
    ↓
Response: JSON with OHLC data
    ↓
Parsed and returned to application
```

### 1.4 Data Storage

**File**: `src/data/clickhouse_data_layer.py`

```python
async def store_market_data(self, symbol: str, asset_type: str, data: pd.DataFrame) -> bool:
    """Store market data in ClickHouse"""
    try:
        data_copy = data.copy()
        data_copy['symbol'] = symbol
        data_copy['asset_type'] = asset_type
        
        # Insert into ClickHouse
        self.client.insert_df('market_data', data_copy)
        
        return True
        
    except Exception as e:
        self.logger.error(f"Error storing market data: {e}")
        return False
```

**Database Table Structure** (ClickHouse):

```sql
CREATE TABLE market_data (
    timestamp DateTime64(3),
    date Date MATERIALIZED toDate(timestamp),
    symbol String,              -- 'BANKNIFTY'
    asset_type String,          -- 'INDEX'
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    ltp Float64,                -- Last Traded Price
    volume UInt64,
    price_change Float64,
    price_change_pct Float64,
    volatility Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (symbol, asset_type, timestamp);
```

---

## 🎯 PHASE 2: STRATEGY EXECUTION

### 2.1 Strategy Initialization

**File**: `src/orchestrator.py`

```python
async def _initialize_strategies(self):
    """Initialize all enabled strategies"""
    strategies_config = self.config.get("strategies", {})
    
    for strategy_name, strategy_config in strategies_config.items():
        if strategy_config.get("enabled", False):
            await self._initialize_strategy(strategy_name, strategy_config)
```

**Configuration**: `config/production.json`

```json
{
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "symbols": ["BANKNIFTY"],
      "execution_timeframe": "15minute",
      "parameters": {
        "fast_period": 9,
        "slow_period": 21,
        "ma_type": "EMA",
        "min_trend_strength": 0.5,
        "volume_confirmation": true,
        "target_pct": 2.0,
        "stop_loss_pct": 1.0
      }
    }
  }
}
```

### 2.2 Strategy Execution Trigger

**When new data arrives** → Orchestrator calls:

```python
def _on_new_runner_data(self, runner_name: str, symbol: str, data: pd.DataFrame):
    """Called when new index data arrives"""
    # Execute strategies for this symbol
    self._execute_strategies_for_symbol(symbol, data)

def _execute_strategies_for_symbol(self, symbol: str, data: pd.DataFrame):
    """Execute all strategies for a given symbol"""
    for strategy_name, strategy_info in self.active_strategies.items():
        strategy_instances = strategy_info["instances"]
        
        if symbol in strategy_instances:
            strategy = strategy_instances[symbol]
            
            # Get historical data for analysis
            historical_data = await self.historical_data_manager.get_analysis_data(
                symbol, '15minute', days_back=30
            )
            
            # Run strategy analysis
            signal = strategy.analyze(symbol, historical_data, data)
            
            if signal:
                # Add signal to signal manager
                await self.signal_manager.add_signal(
                    symbol=signal['symbol'],
                    strategy=signal['strategy'],
                    signal_type=signal['signal_type'],
                    entry_price=signal['entry_price'],
                    target_price=signal['target_price'],
                    stop_loss_price=signal['stop_loss_price'],
                    confidence=signal['confidence'],
                    metadata=signal['metadata']
                )
```

### 2.3 MA Crossover Strategy Analysis

**File**: `src/strategies/ma_crossover_strategy.py`

```python
def analyze(self, symbol: str, historical_data: pd.DataFrame, 
            realtime_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
    """Main analysis method for MA Crossover Strategy"""
    
    # Step 1: Combine historical and real-time data
    combined_data = self.combine_data(historical_data, realtime_data)
    
    # Step 2: Calculate moving averages
    combined_data = self.calculate_moving_averages(combined_data)
    # Adds 'fast_ma' (9-period EMA) and 'slow_ma' (21-period EMA) columns
    
    # Step 3: Detect crossovers
    golden_cross, death_cross = self.detect_crossovers(combined_data)
    # Golden Cross: Fast MA crosses ABOVE Slow MA (Bullish)
    # Death Cross: Fast MA crosses BELOW Slow MA (Bearish)
    
    if not (golden_cross or death_cross):
        return None  # No signal
    
    # Step 4: Calculate trend strength
    trend_strength = self.calculate_trend_strength(combined_data)
    # Based on MA separation and price momentum
    
    if trend_strength < self.min_trend_strength:
        return None  # Trend too weak
    
    # Step 5: Volume confirmation
    volume_confirmed = self.check_volume_confirmation(combined_data)
    
    if self.volume_confirmation and not volume_confirmed:
        return None  # Volume not supporting signal
    
    # Step 6: Determine signal type
    signal_type = 'BUY' if golden_cross else 'SELL'
    current_price = combined_data['close'].iloc[-1]
    
    # Step 7: Calculate targets and stops
    target_price, stop_loss_price = self.calculate_targets_and_stops(
        current_price, signal_type
    )
    # BUY: target = price * 1.02, stop = price * 0.99 (default 2% target, 1% stop)
    
    # Step 8: Calculate confidence (0-100)
    confidence = self.calculate_confidence(
        combined_data, trend_strength, volume_confirmed
    )
    
    # Step 9: Create signal data
    signal_data = {
        'symbol': symbol,
        'strategy': 'ma_crossover',
        'signal_type': signal_type,  # 'BUY' or 'SELL'
        'entry_price': current_price,
        'target_price': target_price,
        'stop_loss_price': stop_loss_price,
        'confidence': confidence,
        'timestamp': datetime.now(),
        'metadata': {
            'fast_ma': combined_data['fast_ma'].iloc[-1],
            'slow_ma': combined_data['slow_ma'].iloc[-1],
            'trend_strength': trend_strength,
            'volume_confirmed': volume_confirmed,
            'crossover_type': 'golden_cross' if golden_cross else 'death_cross'
        }
    }
    
    return signal_data
```

**Crossover Detection Logic**:

```python
def detect_crossovers(self, data: pd.DataFrame) -> Tuple[bool, bool]:
    """Detect golden cross and death cross patterns"""
    
    # Get current and previous MA values
    fast_current = data['fast_ma'].iloc[-1]
    fast_previous = data['fast_ma'].iloc[-2]
    slow_current = data['slow_ma'].iloc[-1]
    slow_previous = data['slow_ma'].iloc[-2]
    
    # Golden Cross (Bullish) - Fast MA crosses above Slow MA
    golden_cross = (fast_current > slow_current and 
                   fast_previous <= slow_previous)
    
    # Death Cross (Bearish) - Fast MA crosses below Slow MA
    death_cross = (fast_current < slow_current and 
                  fast_previous >= slow_previous)
    
    return golden_cross, death_cross
```

**Example Signal Generated**:

```python
{
    'symbol': 'BANKNIFTY',
    'strategy': 'ma_crossover',
    'signal_type': 'BUY',
    'entry_price': 50000.0,
    'target_price': 51000.0,  # +2%
    'stop_loss_price': 49500.0,  # -1%
    'confidence': 75,
    'timestamp': datetime(2025, 10, 7, 10, 15, 30),
    'metadata': {
        'fast_ma': 50050.0,
        'slow_ma': 49980.0,
        'trend_strength': 0.65,
        'volume_confirmed': True,
        'crossover_type': 'golden_cross'
    }
}
```

---

## 🔔 PHASE 3: SIGNAL MANAGEMENT

### 3.1 Signal Storage

**File**: `src/trading/signal_manager.py`

```python
async def add_signal(self, symbol: str, strategy: str, signal_type: str,
                    entry_price: float, target_price: float, stop_loss_price: float,
                    confidence: int, metadata: Dict = None) -> str:
    """Add new trading signal"""
    
    signal_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    signal = TradingSignal(
        signal_id=signal_id,
        symbol=symbol,
        strategy=strategy,
        signal_type=signal_type,
        entry_price=entry_price,
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        confidence=confidence,
        timestamp=datetime.now(),
        status='PENDING',
        metadata=metadata or {}
    )
    
    # Store in database
    await self.data_layer.store_signal({
        'signal_id': signal_id,
        'symbol': symbol,
        'strategy': strategy,
        'action': signal_type,
        'price': entry_price,
        'target': target_price,
        'stop_loss': stop_loss_price,
        'confidence': confidence / 100,
        'timestamp': datetime.now(),
        'metadata': json.dumps(metadata)
    })
    
    # Add to active signals
    self.active_signals[signal_id] = signal
    
    logger.info(f"✅ Signal created: {signal_type} {symbol} @ {entry_price}")
    
    return signal_id
```

---

## 🎲 PHASE 4: OPTIONS STRIKE SELECTION

### 4.1 Options Trade Executor Listening

**File**: `src/trading/options_trade_executor.py`

```python
async def _listen_for_signals(self):
    """Listen for new signals and execute trades"""
    logger.info("Started listening for trading signals...")
    
    while self.enabled:
        try:
            # Check for new signals every 5 seconds
            await asyncio.sleep(5)
            
            # Process new signals
            await self._process_new_signals()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in signal listener: {e}")
            await asyncio.sleep(10)

async def _process_new_signals(self):
    """Process new signals from signal manager"""
    
    # Get recent unprocessed signals
    signals = await self._get_recent_signals()
    
    for signal in signals:
        # Check if already processed
        if await self._is_signal_processed(signal['signal_id']):
            continue
        
        # Execute trade based on signal
        await self._execute_signal_trade(signal)
```

### 4.2 Strike Selection Process

**File**: `src/trading/strike_selector.py`

```python
async def _execute_signal_trade(self, signal: Dict):
    """Execute trade based on signal"""
    
    underlying = signal['symbol']  # 'BANKNIFTY'
    signal_type = signal['signal_type']  # 'BUY' or 'SELL'
    entry_price = signal['entry_price']  # 50000.0
    target_price = signal['target_price']  # 51000.0
    
    # Calculate expected move percentage
    expected_move_pct = abs(target_price - entry_price) / entry_price * 100
    # expected_move_pct = 2.0%
    
    # Get signal strength (normalized confidence)
    signal_strength = signal['confidence'] / 100  # 0.75
    
    logger.info(f"Processing signal: {signal_type} {underlying} @ {entry_price}")
    logger.info(f"Expected move: {expected_move_pct:.2f}%, Target: {target_price}")
    
    # SELECT BEST STRIKE
    selected_option = self.strike_selector.select_best_strike(
        underlying_symbol=underlying,
        current_price=entry_price,
        signal_type=signal_type,
        expected_move_pct=expected_move_pct,
        signal_strength=signal_strength
    )
    
    if not selected_option:
        logger.warning(f"No suitable option found for {underlying}")
        return
```

### 4.3 Strike Selection Algorithm

**File**: `src/trading/strike_selector.py`

```python
def select_best_strike(
    self,
    underlying_symbol: str,    # 'BANKNIFTY'
    current_price: float,      # 50000.0
    signal_type: str,          # 'BUY'
    expected_move_pct: float,  # 2.0
    signal_strength: float     # 0.75
) -> Optional[Dict]:
    """Select the best strike based on mode and signal"""
    
    # Step 1: Fetch options chain from NFO segment
    options_chain = self._get_options_chain(underlying_symbol)
    # Returns all BANKNIFTY options (CE and PE) from Kite API
    
    # Step 2: Determine option type
    option_type = "CE" if signal_type == "BUY" else "PE"
    # For BUY signal: Select Call Options (CE)
    # For SELL signal: Select Put Options (PE)
    
    # Step 3: Calculate target strike
    target_strike = self._calculate_target_strike(
        current_price, expected_move_pct, signal_strength
    )
    # Based on mode configuration:
    # - CONSERVATIVE: ATM (50000)
    # - BALANCED: 1% OTM (50500) if move > 1.5%
    # - AGGRESSIVE: 2% OTM (51000)
    
    # Step 4: Filter options
    filtered_options = self._filter_options(
        options_chain, option_type, current_price, target_strike
    )
    # Filters by:
    # - Option type (CE or PE)
    # - Liquidity: min_open_interest=100, min_volume=50
    # - Premium range: 10 ≤ premium ≤ 300
    # - Days to expiry: 2 ≤ days ≤ 30
    # - Strike within ±10% of target
    
    # Step 5: Rank and select best
    best_option = self._rank_and_select_best(
        filtered_options, current_price, expected_move_pct
    )
    
    return best_option
```

**Ranking Algorithm**:

```python
def _rank_and_select_best(
    self,
    options: List[Dict],
    current_price: float,
    expected_move_pct: float
) -> Optional[Dict]:
    """Rank options and select the best one"""
    
    for option in options:
        score = 0
        
        # Factor 1: Liquidity (30% weight)
        oi = option.get('open_interest', 0)
        volume = option.get('volume', 0)
        liquidity_score = min((oi / 1000 + volume / 100) / 2, 1) * 30
        score += liquidity_score
        
        # Factor 2: Delta (30% weight)
        delta = option.get('estimated_delta', 0)
        if 0.30 <= delta <= 0.60:  # Optimal delta range
            delta_score = min(delta / 0.60, 1) * 30
        score += delta_score
        
        # Factor 3: Days to expiry (20% weight)
        days = option['days_to_expiry']
        optimal_days = 7  # Weekly options preferred
        days_score = (1 - min(abs(days - optimal_days) / optimal_days, 1)) * 20
        score += days_score
        
        # Factor 4: Strike interval (10% weight)
        strike = option['strike']
        strike_interval = 100  # Bank Nifty strikes are in 100s
        if strike % strike_interval == 0:
            score += 10
        
        # Factor 5: Moneyness (10% weight)
        moneyness_pct = option.get('moneyness_pct', 0)
        if -2 <= moneyness_pct <= 2:  # Near ATM preferred
            score += 10
        
        option['selection_score'] = score
    
    # Sort by score and return the best
    options.sort(key=lambda x: x.get('selection_score', 0), reverse=True)
    best = options[0]
    
    return {
        'symbol': best.get('tradingsymbol'),     # 'BANKNIFTY25OCT50500CE'
        'instrument_token': best.get('instrument_token'),
        'strike': best.get('strike'),            # 50500
        'option_type': best.get('instrument_type'),  # 'CE'
        'expiry': best.get('expiry'),            # '2025-10-24'
        'lot_size': best.get('lot_size', 25),
        'delta': best.get('estimated_delta'),    # 0.35
        'moneyness_pct': best.get('moneyness_pct'),
        'score': best.get('selection_score'),
        'exchange': 'NFO'
    }
```

### 4.4 Options Chain Fetching

**File**: `src/trading/strike_selector.py`

```python
def _get_options_chain(self, underlying_symbol: str) -> Optional[List[Dict]]:
    """Fetch options chain from API"""
    
    # Get all instruments from NFO (Futures & Options) segment
    instruments = self.api_client.get_instruments("NFO")
    
    # Normalize symbol names
    symbol_mapping = {
        "BANKNIFTY": "NIFTY BANK",
        "NIFTY": "NIFTY 50",
        "FINNIFTY": "NIFTY FIN SERVICE"
    }
    
    search_symbol = symbol_mapping.get(underlying_symbol, underlying_symbol)
    
    # Filter options for this underlying
    options = [
        inst for inst in instruments
        if inst.get('name', '').upper() in [underlying_symbol.upper(), search_symbol.upper()]
        and inst.get('instrument_type') in ['CE', 'PE']
    ]
    
    logger.info(f"Found {len(options)} options for {underlying_symbol}")
    return options
```

**Example Options Chain Data** (from Kite API):

```python
[
    {
        'tradingsymbol': 'BANKNIFTY25OCT50000CE',
        'instrument_token': '12345678',
        'name': 'NIFTY BANK',
        'strike': 50000.0,
        'expiry': datetime(2025, 10, 24),
        'instrument_type': 'CE',
        'lot_size': 25,
        'open_interest': 15000,
        'volume': 5000,
        'last_price': 280.0
    },
    {
        'tradingsymbol': 'BANKNIFTY25OCT50500CE',
        'instrument_token': '12345679',
        'name': 'NIFTY BANK',
        'strike': 50500.0,
        'expiry': datetime(2025, 10, 24),
        'instrument_type': 'CE',
        'lot_size': 25,
        'open_interest': 12000,
        'volume': 3500,
        'last_price': 150.0
    },
    # ... more options
]
```

**Selected Option Example**:

```python
{
    'symbol': 'BANKNIFTY25OCT50500CE',
    'instrument_token': '12345679',
    'strike': 50500,
    'option_type': 'CE',
    'expiry': '2025-10-24',
    'lot_size': 25,
    'delta': 0.35,
    'moneyness_pct': 1.0,  # 1% OTM
    'score': 85.5,
    'exchange': 'NFO'
}
```

---

## 🎲 PHASE 5: GREEKS CALCULATION & RISK ASSESSMENT

### 5.1 Options Greeks Calculation

**File**: `src/trading/options_greeks.py`

```python
greeks = self.greeks_calculator.calculate_greeks(
    underlying_price=50000.0,
    strike_price=50500.0,
    time_to_expiry_days=7,
    volatility=0.15,  # 15% IV
    risk_free_rate=0.065,
    option_type='CE'
)
```

**Greeks Output**:

```python
{
    'delta': 0.35,           # Option moves ₹35 for ₹100 move in underlying
    'gamma': 0.000015,       # Delta change rate
    'theta': -15.0,          # Daily decay: -₹15/day
    'vega': 25.0,            # IV sensitivity: +₹25 per 1% IV increase
    'rho': 0.08,             # Interest rate sensitivity
    'theoretical_premium': 125.0,
    'moneyness': 'OTM',
    'probability_of_profit': 35.0,
    'expected_premium_at_target': 200.0,  # When BANKNIFTY hits 51000
    'breakeven_underlying_price': 50625.0
}
```

### 5.2 Risk Calculation

**File**: `src/trading/options_trade_executor.py`

```python
# Calculate position size based on risk
quantity = self._calculate_position_size(
    capital=100000,              # ₹1,00,000
    risk_per_trade_pct=2.0,      # Risk 2% per trade
    entry_premium=125.0,         # Option premium
    lot_size=25
)

# Risk calculation:
# max_loss = capital * risk_per_trade_pct / 100 = 2000
# lots = max_loss / (entry_premium * lot_size) = 2000 / (125 * 25) = 0.64
# lots = floor(0.64) = 0 → Adjust to 1 lot (minimum)
# quantity = 1 * 25 = 25 units

# With 1 lot (25 units):
# Total investment = 125 * 25 = ₹3,125
# Max loss = ₹3,125 (if premium goes to 0)
# Max gain = unlimited (theoretically)
```

---

## 📋 PHASE 6: ORDER PLACEMENT

### 6.1 Order Execution Modes

The system has **3 execution modes**:

1. **LOGGING_ONLY** - No orders placed, just logs
2. **PAPER_TRADING** - Simulated orders
3. **LIVE_TRADING** - Real orders with real money

### 6.2 Order Placement Process

**File**: `src/trading/options_trade_executor.py`

```python
async def _place_entry_order(
    self,
    option: Dict,
    quantity: int,
    premium: float
) -> Optional[str]:
    """Place entry order to buy the option"""
    
    order_params = {
        'symbol': option['symbol'],           # 'BANKNIFTY25OCT50500CE'
        'exchange': 'NFO',
        'transaction_type': 'BUY',
        'quantity': quantity,                 # 25 units
        'order_type': 'LIMIT',
        'price': premium,                     # 125.0
        'product': 'MIS',                     # Intraday
        'validity': 'DAY'
    }
    
    # MODE 1: LOGGING ONLY
    if self.logging_only_mode:
        order_id = f"LOG_{uuid.uuid4().hex[:8]}"
        logger.info("="*80)
        logger.info("🔍 LOGGING ONLY MODE - ORDER NOT PLACED")
        logger.info("="*80)
        logger.info(f"📋 Order Details:")
        logger.info(f"   Symbol: {option['symbol']}")
        logger.info(f"   Strike: {option['strike']}")
        logger.info(f"   Quantity: {quantity} units")
        logger.info(f"   Price: ₹{premium:.2f}")
        logger.info(f"   Total Value: ₹{premium * quantity:.2f}")
        logger.info("="*80)
        return order_id
    
    # MODE 2: PAPER TRADING
    elif self.paper_trading:
        order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        logger.info("="*60)
        logger.info(f"📄 Paper Trade Order: BUY {option['symbol']} x {quantity} @ ₹{premium}")
        logger.info(f"   Paper Order ID: {order_id}")
        logger.info("="*60)
        return order_id
    
    # MODE 3: LIVE TRADING
    else:
        logger.warning("="*80)
        logger.warning("💰 LIVE TRADING - PLACING REAL ORDER WITH REAL MONEY!")
        logger.warning("="*80)
        
        # Call Kite API to place order
        order_id = self.api_client.place_order(**order_params)
        
        logger.info(f"✅ Real order placed: {order_id}")
        logger.info(f"   Symbol: {option['symbol']}")
        logger.info(f"   Quantity: {quantity} units")
        logger.info(f"   Price: ₹{premium}")
        logger.info(f"   Total: ₹{premium * quantity:.2f}")
        logger.warning("="*80)
        
        return order_id
```

### 6.3 Kite API Order Placement

**File**: `src/api/kite_client.py`

```python
def place_order(
    self,
    symbol: str,
    transaction_type: str,  # 'BUY' or 'SELL'
    quantity: int,
    order_type: str = "MARKET",
    product: str = "CNC",
    variety: str = "regular",
    price: float = None,
    trigger_price: float = None,
    validity: str = "DAY",
    tag: str = "AlphaStock"
) -> OrderResponse:
    """Place an order via Kite Connect API"""
    
    if self.paper_trading:
        return self._place_paper_order(symbol, transaction_type, quantity, order_type, price)
    
    try:
        self._rate_limit()  # Rate limiting
        
        order_params = {
            'tradingsymbol': symbol,           # 'BANKNIFTY25OCT50500CE'
            'exchange': 'NFO',                 # Options segment
            'transaction_type': transaction_type.upper(),  # 'BUY'
            'quantity': quantity,              # 25
            'order_type': order_type.upper(),  # 'LIMIT'
            'product': product.upper(),        # 'MIS'
            'variety': variety.lower(),        # 'regular'
            'validity': validity.upper(),      # 'DAY'
            'tag': tag                         # 'AlphaStock'
        }
        
        if price:
            order_params['price'] = price      # 125.0
        if trigger_price:
            order_params['trigger_price'] = trigger_price
        
        # Place order via official Kite Connect SDK
        order_id = self.kite.place_order(**order_params)
        
        self.logger.info(f"Order placed: {order_id} for {symbol}")
        
        return OrderResponse(
            order_id=order_id,
            status="SUCCESS",
            message="Order placed successfully",
            data=order_params
        )
        
    except Exception as e:
        self.logger.error(f"Error placing order: {e}")
        return OrderResponse(
            order_id="",
            status="ERROR",
            message=str(e)
        )
```

**Actual Kite API Call**:

```
Python Application
    ↓
self.kite.place_order(
    tradingsymbol='BANKNIFTY25OCT50500CE',
    exchange='NFO',
    transaction_type='BUY',
    quantity=25,
    order_type='LIMIT',
    price=125.0,
    product='MIS',
    variety='regular',
    validity='DAY'
)
    ↓
HTTPS POST to: https://api.kite.trade/orders/regular
Headers: {
    'Authorization': 'token api_key:access_token',
    'X-Kite-Version': '3'
}
Body: {
    "tradingsymbol": "BANKNIFTY25OCT50500CE",
    "exchange": "NFO",
    "transaction_type": "BUY",
    "quantity": 25,
    "order_type": "LIMIT",
    "price": 125.0,
    "product": "MIS",
    "variety": "regular",
    "validity": "DAY"
}
    ↓
Zerodha Kite Servers
    ↓
Response: {
    "status": "success",
    "data": {
        "order_id": "241007000123456"
    }
}
    ↓
Order placed on NSE NFO Exchange
```

---

## 📊 PHASE 7: POSITION MONITORING & EXIT

### 7.1 Position Manager

**File**: `src/trading/options_position_manager.py`

```python
async def add_position(
    self,
    symbol: str,
    strike: float,
    option_type: str,
    entry_premium: float,
    quantity: int,
    lot_size: int,
    target_premium: float,
    stop_loss_premium: float,
    greeks: Dict,
    signal_data: Dict
) -> str:
    """Add new position for monitoring"""
    
    position = OptionsPosition(
        position_id=f"POS_{uuid.uuid4().hex[:8]}",
        symbol=symbol,                    # 'BANKNIFTY25OCT50500CE'
        strike=strike,                    # 50500
        option_type=option_type,          # 'CE'
        entry_premium=entry_premium,      # 125.0
        entry_time=datetime.now(),
        quantity=quantity,                # 25
        lot_size=lot_size,                # 25
        target_premium=target_premium,    # 200.0 (60% gain)
        stop_loss_premium=stop_loss_premium,  # 100.0 (20% loss)
        trailing_stop_enabled=True,
        greeks=greeks,
        signal_data=signal_data
    )
    
    self.active_positions[position.position_id] = position
    
    logger.info(f"✅ Position added: {symbol} - {quantity} units @ ₹{entry_premium}")
    
    return position.position_id
```

### 7.2 Position Monitoring Loop

**Every 5 seconds**, the Position Manager checks all active positions:

```python
async def _monitor_positions_loop(self):
    """Monitor all active positions"""
    
    while self.monitoring:
        try:
            # Check each active position
            for position_id, position in list(self.active_positions.items()):
                await self._check_position_exit_conditions(position)
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(10)

async def _check_position_exit_conditions(self, position: OptionsPosition):
    """Check if position should be exited"""
    
    # Get current premium
    current_premium = await self._get_current_premium(position.symbol)
    
    if not current_premium:
        return
    
    # Calculate P&L
    pnl_per_lot = (current_premium - position.entry_premium) * position.lot_size
    pnl_pct = (current_premium - position.entry_premium) / position.entry_premium * 100
    
    logger.debug(
        f"{position.symbol}: Current=₹{current_premium:.2f}, "
        f"Entry=₹{position.entry_premium:.2f}, P&L={pnl_pct:.2f}%"
    )
    
    # Exit Condition 1: Target Hit
    if current_premium >= position.target_premium:
        logger.info(f"🎯 TARGET HIT for {position.symbol}!")
        await self._execute_exit(
            position, current_premium, "TARGET_HIT", position.quantity
        )
        return
    
    # Exit Condition 2: Stop Loss Hit
    if current_premium <= position.stop_loss_premium:
        logger.warning(f"🛑 STOP LOSS HIT for {position.symbol}!")
        await self._execute_exit(
            position, current_premium, "STOP_LOSS", position.quantity
        )
        return
    
    # Exit Condition 3: Trailing Stop
    if position.trailing_stop_enabled:
        if position.highest_premium and current_premium < position.trailing_stop_price:
            logger.info(f"📉 TRAILING STOP HIT for {position.symbol}!")
            await self._execute_exit(
                position, current_premium, "TRAILING_STOP", position.quantity
            )
            return
    
    # Exit Condition 4: Time Decay (Theta risk)
    if self._should_exit_due_to_theta_decay(position, current_premium):
        logger.info(f"⏰ THETA DECAY EXIT for {position.symbol}")
        await self._execute_exit(
            position, current_premium, "THETA_DECAY", position.quantity
        )
        return
    
    # Update trailing stop if position is profitable
    if current_premium > position.entry_premium:
        if current_premium > position.highest_premium:
            position.highest_premium = current_premium
            
            # Update trailing stop (e.g., 50% of profit)
            profit = current_premium - position.entry_premium
            position.trailing_stop_price = position.entry_premium + (profit * 0.5)
            
            logger.debug(
                f"Updated trailing stop for {position.symbol}: ₹{position.trailing_stop_price:.2f}"
            )
```

### 7.3 Exit Order Placement

```python
async def _execute_exit(
    self,
    position: OptionsPosition,
    exit_premium: float,
    exit_reason: str,
    quantity: int
):
    """Execute exit order for position"""
    
    logger.info(
        f"Executing exit for {position.symbol}: {quantity} units @ ₹{exit_premium}, "
        f"Reason: {exit_reason}"
    )
    
    # Place exit order (SELL for long options)
    order_id = await self._place_exit_order(
        position.symbol, quantity, exit_premium
    )
    
    if order_id:
        # Calculate P&L
        pnl_per_lot = (exit_premium - position.entry_premium) * position.lot_size
        pnl = pnl_per_lot * (quantity / position.lot_size)
        
        position.realized_pnl += pnl
        position.remaining_quantity -= quantity
        
        # Record exit
        position.partial_exits.append({
            'quantity': quantity,
            'exit_premium': exit_premium,
            'exit_time': datetime.now(),
            'exit_reason': exit_reason,
            'pnl': pnl,
            'order_id': order_id
        })
        
        # If fully exited, move to closed positions
        if position.remaining_quantity == 0:
            position.exit_premium = exit_premium
            position.exit_time = datetime.now()
            position.exit_reason = exit_reason
            
            self.closed_positions.append(position)
            del self.active_positions[position.position_id]
            
            logger.info(f"✅ Position closed: {position.symbol}, P&L: ₹{pnl:.2f}")

async def _place_exit_order(
    self,
    symbol: str,
    quantity: int,
    premium: float
) -> Optional[str]:
    """Place exit order via API"""
    
    order_params = {
        'symbol': symbol,
        'exchange': 'NFO',
        'transaction_type': 'SELL',  # Exit long position
        'quantity': quantity,
        'order_type': 'LIMIT',
        'price': premium,
        'product': 'MIS',
        'validity': 'DAY'
    }
    
    # Same execution modes as entry order
    # LOGGING_ONLY, PAPER_TRADING, or LIVE_TRADING
    
    order_id = f"EXIT_{symbol}_{quantity}"
    
    logger.info("="*60)
    logger.info(f"🚪 EXIT ORDER:")
    logger.info(f"   Symbol: {symbol}")
    logger.info(f"   Action: SELL")
    logger.info(f"   Quantity: {quantity} units")
    logger.info(f"   Price: ₹{premium:.2f}")
    logger.info(f"   Total: ₹{premium * quantity:.2f}")
    logger.info("="*60)
    
    return order_id
```

---

## 📊 COMPLETE FLOW EXAMPLE

### Real-World Scenario: Bank Nifty Trade

**Time**: 10:15 AM, October 7, 2025

#### Step 1: Index Data Collection (10:15:00 AM)
```
IndexRunner fetches BANKNIFTY data:
- Current Price: 50,000
- Open: 49,950
- High: 50,050
- Low: 49,900
- Volume: 125,000
- Change: +0.10%
```

#### Step 2: Strategy Analysis (10:15:15 AM)
```
MA Crossover Strategy analyzes:
- Fast MA (9-EMA): 50,050
- Slow MA (21-EMA): 49,980
- Detection: Golden Cross! (Fast crossed above Slow)
- Trend Strength: 0.65 (Good)
- Volume Confirmation: Yes
- Confidence: 75%

SIGNAL GENERATED:
- Type: BUY
- Entry: 50,000
- Target: 51,000 (+2%)
- Stop: 49,500 (-1%)
```

#### Step 3: Signal Storage (10:15:20 AM)
```
Signal Manager stores signal:
- ID: ma_crossover_BANKNIFTY_20251007101520
- Status: PENDING
- Stored in ClickHouse database
```

#### Step 4: Options Trade Executor (10:15:25 AM)
```
Trade Executor processes signal:
- Expected Move: 2.0%
- Signal Strength: 0.75
- Mode: BALANCED

Strike Selector searches options chain:
- Found 150 BANKNIFTY CE options
- Filtered to 12 candidates
- Target Strike: 50,500 (1% OTM)

SELECTED OPTION:
- Symbol: BANKNIFTY25OCT50500CE
- Strike: 50,500
- Expiry: Oct 24, 2025 (7 days)
- Delta: 0.35
- Current Premium: ₹125
- Selection Score: 85.5
```

#### Step 5: Risk Calculation (10:15:30 AM)
```
Greeks Calculator:
- Delta: 0.35
- Theta: -₹15/day
- Expected Premium at Target: ₹200 (+60%)
- Breakeven: 50,625

Position Sizer:
- Capital: ₹1,00,000
- Risk: 2% = ₹2,000
- Quantity: 25 units (1 lot)
- Investment: ₹3,125
- Max Loss: ₹3,125
```

#### Step 6: Order Placement (10:15:35 AM)
```
[PAPER TRADING MODE]

Order Placed:
- Symbol: BANKNIFTY25OCT50500CE
- Action: BUY
- Quantity: 25 units
- Price: ₹125 (LIMIT order)
- Order ID: PAPER_a7f3c912
- Total: ₹3,125
```

#### Step 7: Position Monitoring (10:15:40 AM onwards)

**10:16:40 AM** (65 seconds later):
```
BANKNIFTY: 50,175 (+175 points)
Option Premium: 150 (+25, +20%)
P&L: (150 - 125) * 25 = +₹625
Status: Continue monitoring
```

**10:18:15 AM** (2 minutes later):
```
BANKNIFTY: 50,335 (+335 points)
Option Premium: 175 (+50, +40%)
P&L: (175 - 125) * 25 = +₹1,250
Status: 62% of target reached
```

**10:23:45 AM** (8 minutes later):
```
BANKNIFTY: 50,850 (+850 points)
Option Premium: 205 (+80, +64%)
P&L: (205 - 125) * 25 = +₹2,000

🎯 TARGET HIT! (Target was ₹200)

EXIT ORDER PLACED:
- Symbol: BANKNIFTY25OCT50500CE
- Action: SELL
- Quantity: 25 units
- Price: ₹205
- Order ID: EXIT_a7f3c912
- Total: ₹5,125

FINAL P&L: ₹2,000 (+64% return)
Position closed
```

---

## 🎯 KEY FILES REFERENCE

### Data Collection
- `src/runners/index_runner.py` - Fetches index data
- `src/api/kite_client.py` - Kite API wrapper
- `src/data/clickhouse_data_layer.py` - Database storage

### Strategy Execution
- `src/strategies/ma_crossover_strategy.py` - MA Crossover logic
- `src/core/strategy_factory.py` - Strategy creation
- `src/orchestrator.py` - Main coordinator

### Signal Management
- `src/trading/signal_manager.py` - Signal storage and retrieval

### Options Trading
- `src/trading/strike_selector.py` - Strike selection algorithm
- `src/trading/options_greeks.py` - Greeks calculation
- `src/trading/options_trade_executor.py` - Trade execution
- `src/trading/options_position_manager.py` - Position monitoring

### Configuration
- `config/production.json` - Main configuration
- `config/database.json` - Database settings

---

## 🔒 Trading Modes

### 1. LOGGING_ONLY Mode
- **Purpose**: Development/Testing
- **Behavior**: No orders placed, everything logged
- **Risk**: Zero (no real money)
- **Usage**: Default for testing

### 2. PAPER_TRADING Mode
- **Purpose**: Strategy validation
- **Behavior**: Simulated orders, simulated P&L
- **Risk**: Zero (no real money)
- **Usage**: Strategy testing with realistic flow

### 3. LIVE_TRADING Mode
- **Purpose**: Real trading
- **Behavior**: Real orders with real money
- **Risk**: High (actual money at risk)
- **Usage**: Production trading

---

## 📊 Summary

The complete flow is:

1. **IndexRunner** fetches BANKNIFTY data every 5 seconds from Kite API
2. **Data** is stored in ClickHouse database
3. **Orchestrator** triggers **MA Crossover Strategy** analysis
4. **Strategy** detects golden/death cross and generates signal
5. **Signal Manager** stores signal in database
6. **Options Trade Executor** picks up signal
7. **Strike Selector** chooses optimal option strike from NFO options chain
8. **Greeks Calculator** computes risk metrics
9. **Order** is placed via Kite API (or logged/simulated)
10. **Position Manager** monitors position every 5 seconds
11. **Exit** happens when target/stop-loss/trailing-stop is hit

The entire system is event-driven and asynchronous, with multiple safety layers and configurable risk management.

---

*Last Updated: October 7, 2025*
