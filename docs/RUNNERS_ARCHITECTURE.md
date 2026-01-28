# Runners Architecture in AlphaStocks

## 📊 Overview

The **Runners** are specialized components that collect and process market data for different asset types. They work alongside the `MarketDataRunner` (which handles general symbol data) but provide **asset-specific intelligence** for indices, equities, options, futures, and commodities.

---

## 🏗️ Architecture Hierarchy

```
┌────────────────────────────────────────────────────────────┐
│                    Orchestrator                             │
│              (src/orchestrator.py)                          │
│                                                             │
│  - Initializes all runners                                  │
│  - Coordinates data flow                                    │
│  - Executes strategies                                      │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ↓
┌────────────────────────────────────────────────────────────┐
│                 RunnerManager                               │
│           (src/runners/base_runner.py)                      │
│                                                             │
│  - Manages all specialized runners                          │
│  - Starts/stops all runners                                 │
│  - Provides health checks                                   │
└─────────┬───────────────┬───────────────┬───────────┬──────┘
          │               │               │           │
          ↓               ↓               ↓           ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│IndexRunner  │  │EquityRunner │  │OptionsRunner│  │FuturesRunner│
│             │  │             │  │             │  │             │
│BANKNIFTY    │  │RELIANCE     │  │NIFTY CE/PE  │  │BANKNIFTY FUT│
│NIFTY50      │  │TCS          │  │BANKNIFTY OPT│  │NIFTY FUT    │
│NIFTYBANK    │  │INFY         │  │EQUITY OPT   │  │COMMODITY FUT│
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
      │                │                │                │
      └────────────────┴────────────────┴────────────────┘
                       │
                       ↓ Callbacks
┌────────────────────────────────────────────────────────────┐
│          _on_new_runner_data() callback                     │
│                                                             │
│  - Receives data from all runners                           │
│  - Routes to appropriate strategies                         │
│  - Considers asset type in strategy execution               │
└────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Flow: From Runner to Strategy Execution

### Step 1: Orchestrator Initialization

**File**: `src/orchestrator.py`

```python
async def initialize(self):
    """Initialize the orchestrator and all components."""
    
    # ... other initializations ...
    
    # Initialize specialized runners
    self._initialize_runners()
    
    # Initialize strategies
    await self._initialize_strategies()
```

### Step 2: Initialize Runners

**File**: `src/orchestrator.py` → `_initialize_runners()`

```python
def _initialize_runners(self):
    """Initialize specialized market data runners."""
    
    # Get symbols from config, organized by asset type
    config_symbols = self.config.get("symbols", {})
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. INITIALIZE INDEX RUNNER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    indices = config_symbols.get("indices", [])
    # Example: ["NIFTY50", "BANKNIFTY", "NIFTYBANK"]
    
    if indices:
        self.index_runner = IndexRunner(
            api_client=self.api_client,
            data_layer=self.data_layer,
            indices=indices,
            interval_seconds=5  # Fetch every 5 seconds
        )
        self.logger.info(f"Index runner initialized for {len(indices)} indices")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. INITIALIZE EQUITY RUNNER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    equities = config_symbols.get("equities", [])
    # Example: ["RELIANCE", "TCS", "INFY", "SBIN"]
    
    if equities:
        self.equity_runner = EquityRunner(
            api_client=self.api_client,
            data_layer=self.data_layer,
            equities=equities,
            interval_seconds=5  # Fetch every 5 seconds
        )
        self.logger.info(f"Equity runner initialized for {len(equities)} stocks")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. INITIALIZE OPTIONS RUNNER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    options = config_symbols.get("options", [])
    # Example: ["NIFTY", "BANKNIFTY", "RELIANCE"]  # Underlying assets
    
    if options:
        self.options_runner = OptionsRunner(
            api_client=self.api_client,
            data_layer=self.data_layer,
            underlyings=options,
            interval_seconds=3  # Faster - every 3 seconds (options need real-time)
        )
        self.logger.info(f"Options runner initialized for {len(options)} underlyings")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. INITIALIZE FUTURES RUNNER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    futures = config_symbols.get("futures", [])
    # Example: ["BANKNIFTY25OCTFUT", "NIFTY25OCTFUT"]
    
    if futures:
        self.futures_runner = FuturesRunner(
            api_client=self.api_client,
            data_layer=self.data_layer,
            futures=futures,
            interval_seconds=5  # Fetch every 5 seconds
        )
        self.logger.info(f"Futures runner initialized for {len(futures)} contracts")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. INITIALIZE COMMODITY RUNNER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    commodities = config_symbols.get("commodities", [])
    # Example: ["GOLD", "SILVER", "CRUDEOIL"]
    
    if commodities:
        self.commodity_runner = CommodityRunner(
            api_client=self.api_client,
            data_layer=self.data_layer,
            commodities=commodities,
            interval_seconds=10  # Slower - every 10 seconds
        )
        self.logger.info(f"Commodity runner initialized for {len(commodities)} commodities")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. CREATE RUNNER MANAGER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Collect all active runners
    active_runners = []
    if self.equity_runner:
        active_runners.append(self.equity_runner)
    if self.options_runner:
        active_runners.append(self.options_runner)
    if self.index_runner:
        active_runners.append(self.index_runner)
    if self.commodity_runner:
        active_runners.append(self.commodity_runner)
    if self.futures_runner:
        active_runners.append(self.futures_runner)
    
    if active_runners:
        # Create manager to coordinate all runners
        self.runner_manager = RunnerManager(active_runners)
        self.logger.info(f"Runner manager initialized with {len(active_runners)} runners")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. SET UP CALLBACKS - CRUCIAL!
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Each runner will call this callback when new data arrives
        for runner in active_runners:
            runner.add_callback(self._on_new_runner_data)
            #                   ^^^^^^^^^^^^^^^^^^^^^^^^
            #                   This is the bridge to strategies!
```

**Configuration Example** (`config/production.json`):

```json
{
  "symbols": {
    "indices": ["NIFTY50", "BANKNIFTY", "NIFTYBANK"],
    "equities": ["RELIANCE", "TCS", "INFY", "SBIN"],
    "options": ["NIFTY", "BANKNIFTY"],
    "futures": ["BANKNIFTY25OCTFUT", "NIFTY25OCTFUT"],
    "commodities": ["GOLD", "SILVER"]
  }
}
```

---

### Step 3: Start All Runners

**File**: `src/orchestrator.py` → `start()`

```python
async def start(self):
    """Start the orchestrator."""
    
    self.logger.info("Starting AlphaStock Orchestrator...")
    self.running = True
    self.start_time = datetime.now()
    
    # Start legacy market data collection (if configured)
    if self.market_data_runner:
        self.market_data_runner.start()
        self.logger.info("Market data collection started")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # START ALL SPECIALIZED RUNNERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if self.runner_manager:
        self.runner_manager.start_all()
        #                   ^^^^^^^^^^^
        #                   Starts IndexRunner, EquityRunner, etc.
        self.logger.info("Specialized runners started")
    
    # Start main orchestration loop
    await self._main_loop()
```

**What happens in `runner_manager.start_all()`**:

**File**: `src/runners/base_runner.py`

```python
class RunnerManager:
    """Manages multiple runners for different asset types."""
    
    def start_all(self):
        """Start all runners."""
        for name, runner in self.runners.items():
            try:
                runner.start()  # Each runner starts in separate thread
                self.logger.info(f"Started runner: {name}")
            except Exception as e:
                self.logger.error(f"Error starting runner {name}: {e}")
```

---

### Step 4: Runner Data Collection Loop

Each runner inherits from `BaseRunner` which provides a common collection mechanism.

**File**: `src/runners/base_runner.py`

```python
class BaseRunner:
    """Base class for all specialized runners."""
    
    def start(self):
        """Start the data collection process."""
        
        if self.is_running:
            self.logger.warning(f"{self.runner_name} is already running")
            return
        
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        # Start in a SEPARATE THREAD (non-blocking)
        self.runner_thread = threading.Thread(
            target=self._run_collection_loop,
            daemon=True
        )
        self.runner_thread.start()
        
        self.logger.info(f"{self.runner_name} started")
    
    def _run_collection_loop(self):
        """Main collection loop that runs in a separate thread."""
        
        self.logger.info(f"{self.runner_name} collection loop started")
        
        while self.is_running:
            start_time = time.time()
            
            try:
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # COLLECT DATA FOR ALL SYMBOLS
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                self._collect_batch_data()
                
                # Update statistics
                self.stats['total_updates'] += 1
                self.stats['successful_updates'] += 1
                
            except Exception as e:
                self.logger.error(f"Error in {self.runner_name} collection loop: {e}")
                self.stats['failed_updates'] += 1
            
            # Calculate sleep time to maintain frequency
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.interval_seconds - elapsed_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)  # Wait before next iteration
    
    def _collect_batch_data(self):
        """Collect data for all symbols in batch."""
        
        if not self.symbols:
            return
        
        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # STEP 1: FETCH RAW DATA (implemented by child class)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            raw_data = self.fetch_market_data(self.symbols)
            #            ^^^^^^^^^^^^^^^^^^^^
            #            Each runner implements this differently
            #            - IndexRunner: fetches index values + sentiment
            #            - EquityRunner: fetches stock prices + fundamentals
            #            - OptionsRunner: fetches option chain + greeks
            #            - FuturesRunner: fetches futures prices + open interest
            
            if not raw_data:
                self.logger.warning(f"No data received from API for {self.runner_name}")
                return
            
            current_time = datetime.now()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # STEP 2: PROCESS EACH SYMBOL
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            for symbol, symbol_data in raw_data.items():
                try:
                    # Process data (implemented by child class)
                    processed_df = self.process_data(symbol, symbol_data)
                    #              ^^^^^^^^^^^^^^^^^^
                    #              Each runner adds asset-specific intelligence
                    
                    if processed_df is None or processed_df.empty:
                        continue
                    
                    # Store in data cache
                    cache_key = f"{self.get_asset_type()}:{symbol}"
                    # Example: "INDEX:BANKNIFTY" or "EQUITY:RELIANCE"
                    
                    # Get existing data and append
                    existing_data = self.data_cache.get(cache_key)
                    if existing_data is not None and isinstance(existing_data, pd.DataFrame):
                        combined_data = pd.concat([existing_data, processed_df], ignore_index=True)
                        if len(combined_data) > 100:
                            combined_data = combined_data.tail(100)
                    else:
                        combined_data = processed_df
                    
                    # Update cache
                    self.data_cache.set(cache_key, combined_data, ttl=300)
                    
                    # Update statistics
                    self.last_update_time[symbol] = current_time
                    self.error_counts[symbol] = 0
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # STEP 3: NOTIFY CALLBACKS - TRIGGER STRATEGIES!
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    for callback in self.callbacks:
                        try:
                            # Call orchestrator's _on_new_runner_data()
                            callback(self.runner_name, symbol, combined_data)
                            #        ^^^^^^^^^^^^^^^^  ^^^^^^  ^^^^^^^^^^^^^
                            #        "IndexRunner"     "NIFTY"  DataFrame with data
                        except Exception as e:
                            self.logger.error(f"Error in callback for {symbol}: {e}")
                    
                    self.stats['successful_requests'] += 1
                
                except Exception as e:
                    self.logger.error(f"Error processing data for {symbol}: {e}")
            
            self.stats['last_success_time'] = current_time
            
        except Exception as e:
            self.logger.error(f"Error in batch data collection: {e}")
            self.stats['failed_requests'] += 1
```

---

### Step 5: IndexRunner Specific Implementation

**File**: `src/runners/index_runner.py`

```python
class IndexRunner(BaseRunner):
    """Handles market indices data collection."""
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return "INDEX"
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch index data.
        
        Returns data like:
        {
            "BANKNIFTY": {
                "open": 45000.00,
                "high": 45200.00,
                "low": 44800.00,
                "close": 45100.00,
                "last_price": 45150.00,
                "volume": 1234567,
                "index_type": "SECTORAL",
                "sector": "BANKING"
            },
            "NIFTY50": { ... }
        }
        """
        try:
            # Get OHLC data for indices
            ohlc_data = self.api_client.get_ohlc(symbols)
            
            # Get LTP data
            ltp_data = self.api_client.get_ltp(symbols)
            
            # Combine data
            combined_data = {}
            
            for symbol in symbols:
                if symbol in ohlc_data:
                    data = ohlc_data[symbol].copy()
                    
                    if symbol in ltp_data:
                        data['ltp'] = ltp_data[symbol]
                    
                    # Add index-specific metadata
                    data['index_type'] = self._get_index_type(symbol)
                    data['sector'] = self._get_index_sector(symbol)
                    
                    combined_data[symbol] = data
            
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching index data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw index data and add intelligence.
        
        Returns DataFrame with:
        - Basic OHLC data
        - Price change and %
        - Volatility
        - Support/Resistance levels
        - Market sentiment
        """
        try:
            # Extract basic data
            open_price = raw_data.get('open', 0)
            high_price = raw_data.get('high', 0)
            low_price = raw_data.get('low', 0)
            close_price = raw_data.get('close', 0)
            ltp = raw_data.get('ltp', raw_data.get('last_price', close_price))
            volume = raw_data.get('volume', 0)
            
            # Calculate index-specific metrics
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Calculate volatility
            volatility = self._calculate_volatility(symbol, ltp)
            
            # Calculate support/resistance levels
            support_resistance = self._calculate_support_resistance(symbol, high_price, low_price)
            
            # Create DataFrame with INDEX-SPECIFIC fields
            df = pd.DataFrame([{
                'timestamp': datetime.now(),
                'symbol': symbol,
                'asset_type': 'INDEX',  # ← IMPORTANT: Asset type tag
                'index_type': raw_data.get('index_type', 'UNKNOWN'),
                'sector': raw_data.get('sector', 'BROAD_MARKET'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'volatility': volatility,
                'support_level': support_resistance.get('support', 0),
                'resistance_level': support_resistance.get('resistance', 0),
                'market_sentiment': self._get_market_sentiment(price_change_pct, volatility),
                'is_trading': self._is_trading_hours(),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing index data for {symbol}: {e}")
            return pd.DataFrame()
```

---

### Step 6: Callback to Orchestrator

When IndexRunner (or any runner) has new data, it calls the registered callback:

**File**: `src/orchestrator.py`

```python
def _on_new_runner_data(self, runner_name: str, symbol: str, data: pd.DataFrame):
    """
    Callback for when new data is received from specialized runners.
    
    Args:
        runner_name: "IndexRunner", "EquityRunner", etc.
        symbol: "BANKNIFTY", "RELIANCE", etc.
        data: DataFrame with processed data
    """
    try:
        # Extract asset type from data
        asset_type = data.iloc[-1]['asset_type'] if not data.empty else 'UNKNOWN'
        # Example: asset_type = 'INDEX' for BANKNIFTY
        
        self.logger.debug(f"Received {asset_type} data for {symbol} from {runner_name}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # EXECUTE STRATEGIES FOR THIS SYMBOL
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self._execute_strategies_for_symbol_with_type(
            symbol, 
            data, 
            asset_type, 
            runner_name
        )
        
        # Update statistics
        self.stats["api_calls"] += 1
        
    except Exception as e:
        self.logger.error(f"Error processing runner data for {symbol}: {e}")
        self.stats["errors"] += 1
```

---

### Step 7: Strategy Execution with Asset Type

**File**: `src/orchestrator.py`

```python
def _execute_strategies_for_symbol_with_type(
    self, 
    symbol: str, 
    data: pd.DataFrame, 
    asset_type: str, 
    runner_name: str
):
    """Execute strategies for a symbol with asset type awareness."""
    
    # Loop through all active strategies
    for strategy_name, strategy_info in self.active_strategies.items():
        strategy_instances = strategy_info["instances"]
        strategy_config = strategy_info["config"]
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # CHECK IF STRATEGY SUPPORTS THIS ASSET TYPE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        supported_assets = strategy_config.get("supported_asset_types", ["EQUITY"])
        # Example: ["INDEX", "EQUITY"] or ["OPTIONS"]
        
        if asset_type not in supported_assets:
            continue  # Skip this strategy for this asset type
        
        # Check if strategy instance exists for this symbol
        if symbol in strategy_instances:
            try:
                strategy = strategy_instances[symbol]
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # SUBMIT STRATEGY EXECUTION TO THREAD POOL
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                future = self.executor.submit(
                    self._run_strategy_with_context,
                    strategy_name,
                    strategy,
                    symbol,
                    data,
                    asset_type,
                    runner_name
                )
                
            except Exception as e:
                self.logger.error(f"Error submitting {strategy_name} for {symbol} ({asset_type}): {e}")
```

**Strategy Configuration Example** (`config/production.json`):

```json
{
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "symbols": ["BANKNIFTY", "NIFTY50", "RELIANCE"],
      "supported_asset_types": ["INDEX", "EQUITY"],
      "parameters": {
        "short_window": 5,
        "long_window": 15
      }
    },
    "rsi_strategy": {
      "enabled": true,
      "symbols": ["RELIANCE", "TCS", "INFY"],
      "supported_asset_types": ["EQUITY"],
      "parameters": {
        "period": 14,
        "overbought": 70,
        "oversold": 30
      }
    }
  }
}
```

---

## 📊 Data Flow Timeline

Here's a complete timeline showing how data flows from runners to strategies:

```
TIME         EVENT                                           COMPONENT
───────────────────────────────────────────────────────────────────────────
10:15:00.000 System starts                                   main.py
10:15:00.100 Initialize Orchestrator                         orchestrator.py
10:15:00.200 Initialize IndexRunner for BANKNIFTY            index_runner.py
10:15:00.250 Initialize EquityRunner for RELIANCE            equity_runner.py
10:15:00.300 Initialize OptionsRunner for NIFTY              options_runner.py
10:15:00.400 Set callbacks: _on_new_runner_data()            orchestrator.py
10:15:01.000 Start all runners via RunnerManager             base_runner.py
10:15:01.050 IndexRunner starts thread                       index_runner.py
10:15:01.100 EquityRunner starts thread                      equity_runner.py
10:15:01.150 OptionsRunner starts thread                     options_runner.py

───────────── COLLECTION CYCLE 1 ──────────────────────────────────────────
10:15:05.000 IndexRunner: fetch BANKNIFTY data               index_runner.py
10:15:05.100 ↳ Call api_client.get_ohlc(['BANKNIFTY'])      kite_client.py
10:15:05.300 ↳ Receive: {open:45000, high:45200, ...}       
10:15:05.350 ↳ Process data: add volatility, sentiment       index_runner.py
10:15:05.400 ↳ Store in cache: "INDEX:BANKNIFTY"            
10:15:05.450 ↳ Trigger callback: _on_new_runner_data()       orchestrator.py
10:15:05.500   ↳ Extract asset_type='INDEX'                  
10:15:05.550   ↳ Execute strategies for BANKNIFTY            
10:15:05.600     ↳ Check: ma_crossover supports INDEX? ✓     
10:15:05.650     ↳ Submit to thread pool                     
10:15:05.700     ↳ Strategy analyzes data                    ma_crossover.py
10:15:05.800     ↳ Generate signal: BUY BANKNIFTY            
10:15:05.850     ↳ Store signal in signal_manager            signal_manager.py

───────────── COLLECTION CYCLE 2 ──────────────────────────────────────────
10:15:10.000 IndexRunner: fetch BANKNIFTY data (again)       index_runner.py
10:15:10.450 ↳ Trigger callback: _on_new_runner_data()       
10:15:10.700     ↳ Strategy analyzes updated data            
10:15:10.800     ↳ No new signal (existing signal still valid)

───────────── PARALLEL: EQUITY RUNNER ─────────────────────────────────────
10:15:05.000 EquityRunner: fetch RELIANCE data               equity_runner.py
10:15:05.200 ↳ Call api_client.get_ohlc(['RELIANCE'])       kite_client.py
10:15:05.400 ↳ Process data: add fundamentals                
10:15:05.500 ↳ Store in cache: "EQUITY:RELIANCE"            
10:15:05.550 ↳ Trigger callback: _on_new_runner_data()       orchestrator.py
10:15:05.600   ↳ Extract asset_type='EQUITY'                 
10:15:05.650   ↳ Execute strategies for RELIANCE             
```

---

## 🎯 Key Differences: Runners vs MarketDataRunner

| Feature | **MarketDataRunner** (Legacy) | **Specialized Runners** (New) |
|---------|------------------------------|-------------------------------|
| **Scope** | Generic data collection | Asset-specific intelligence |
| **Data** | Basic OHLC + LTP | OHLC + asset-specific metrics |
| **Processing** | Minimal | Rich (volatility, sentiment, greeks) |
| **Asset Types** | Mixed (all in one) | Separated (INDEX, EQUITY, OPTIONS) |
| **Callback** | `_on_new_market_data()` | `_on_new_runner_data()` |
| **Strategy Routing** | No asset type awareness | Asset type-aware routing |
| **Frequency** | One for all symbols | Different per asset type |
| **Example** | All symbols every 5 sec | INDEX:5s, EQUITY:5s, OPTIONS:3s |

---

## 🔍 Why Use Specialized Runners?

### 1. **Asset-Specific Intelligence**

**IndexRunner** adds:
- Volatility calculation
- Support/resistance levels
- Market sentiment (bullish/bearish)
- Sector classification

**EquityRunner** adds:
- Fundamental ratios (P/E, P/B)
- Market cap classification
- Sector categorization
- Trading volume analysis

**OptionsRunner** adds:
- Greeks (Delta, Gamma, Theta, Vega)
- Implied volatility
- Strike price analysis
- Time to expiry tracking

### 2. **Different Update Frequencies**

```python
IndexRunner:    interval_seconds=5   # Standard
EquityRunner:   interval_seconds=5   # Standard
OptionsRunner:  interval_seconds=3   # Faster (time-sensitive)
FuturesRunner:  interval_seconds=5   # Standard
CommodityRunner: interval_seconds=10 # Slower (less volatile)
```

### 3. **Strategy Asset Type Filtering**

Strategies can specify which asset types they support:

```python
# MA Crossover works for indices and equities
"supported_asset_types": ["INDEX", "EQUITY"]

# Options strategy only works for options
"supported_asset_types": ["OPTIONS"]
```

This prevents running equity strategies on options data (which would be incorrect).

---

## 📈 Statistics & Monitoring

Each runner tracks its own statistics:

```python
runner_stats = index_runner.get_stats()

# Returns:
{
    'runner_name': 'IndexRunner',
    'asset_type': 'INDEX',
    'symbols_count': 3,
    'total_updates': 720,
    'successful_updates': 718,
    'failed_updates': 2,
    'success_rate': 0.997,
    'is_running': True,
    'start_time': datetime(2025, 10, 7, 10, 15, 0),
    'uptime_seconds': 3600,
    'last_success_time': datetime(2025, 10, 7, 11, 15, 0),
    'interval_seconds': 5
}
```

Get all runners' stats via RunnerManager:

```python
all_stats = runner_manager.get_stats()

# Returns:
{
    'IndexRunner': { ... },
    'EquityRunner': { ... },
    'OptionsRunner': { ... }
}
```

---

## 🔧 Configuration

**File**: `config/production.json`

```json
{
  "symbols": {
    "indices": ["NIFTY50", "BANKNIFTY", "NIFTYBANK"],
    "equities": ["RELIANCE", "TCS", "INFY", "SBIN", "HDFCBANK"],
    "options": ["NIFTY", "BANKNIFTY"],
    "futures": ["BANKNIFTY25OCTFUT", "NIFTY25OCTFUT"],
    "commodities": ["GOLD", "SILVER", "CRUDEOIL"]
  },
  
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "symbols": ["BANKNIFTY", "NIFTY50", "RELIANCE", "TCS"],
      "supported_asset_types": ["INDEX", "EQUITY"],
      "parameters": {
        "short_window": 5,
        "long_window": 15
      }
    },
    
    "options_strategy": {
      "enabled": true,
      "symbols": ["NIFTY", "BANKNIFTY"],
      "supported_asset_types": ["OPTIONS"],
      "parameters": {
        "delta_threshold": 0.5,
        "max_greeks_exposure": 1000
      }
    }
  }
}
```

---

## 🎯 Summary

### How Runners Work:

1. **Orchestrator initializes** all runners based on config
2. **RunnerManager coordinates** starting/stopping all runners
3. **Each runner runs in separate thread** collecting data at its own frequency
4. **Runners fetch data** via `fetch_market_data()` (REST API calls)
5. **Runners process data** via `process_data()` (add asset-specific intelligence)
6. **Runners store data** in cache with asset type prefix (`INDEX:`, `EQUITY:`, etc.)
7. **Runners trigger callbacks** → `_on_new_runner_data()` in Orchestrator
8. **Orchestrator routes data to strategies** based on asset type compatibility
9. **Strategies analyze data** and generate signals
10. **Signals stored** in SignalManager for execution

### Key Components:

- **BaseRunner**: Common logic for all runners (threading, callbacks, caching)
- **IndexRunner**: Handles indices (NIFTY, BANKNIFTY) with market sentiment
- **EquityRunner**: Handles stocks with fundamentals
- **OptionsRunner**: Handles options with Greeks
- **FuturesRunner**: Handles futures with open interest
- **RunnerManager**: Coordinates all runners (start/stop/stats)
- **Orchestrator**: Routes data from runners to strategies

### Data Flow:

```
Runner Thread → Fetch Data → Process Data → Cache Storage 
  → Trigger Callback → Orchestrator → Strategy Execution 
  → Signal Generation → SignalManager → Order Placement
```

---

*Last Updated: October 7, 2025*
