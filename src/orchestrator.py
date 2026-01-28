"""
Alpha Stock Trading System - Main Orchestrator
Coordinates all system components and manages the trading lifecycle.
"""

import asyncio
import json
import logging
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

from src.api.kite_client import KiteAPIClient
from src.core.strategy_factory import StrategyFactory
from src.core.market_data_runner import MarketDataRunner
from src.core.data_cache import SimpleDataCache
from src.trading.signal_manager import SignalManager
from src.utils.logger_setup import setup_logger
from src.utils.market_hours import is_market_open

# Import specialized runners
from src.runners.base_runner import RunnerManager
from src.runners.equity_runner import EquityRunner
from src.runners.options_runner import OptionsRunner
from src.runners.index_runner import IndexRunner
from src.runners.commodity_runner import CommodityRunner
from src.runners.futures_runner import FuturesRunner

# Import data layer components
from src.data.data_layer_factory import DataLayerFactory, data_layer_factory
from src.data import DataLayerInterface

# Import historical data and analysis components
from src.core.historical_data_manager import HistoricalDataManager
from src.core.analysis_engine import MarketAnalysisEngine

# Import new data pipeline components
from src.core.candle_aggregator import CandleAggregator
from src.core.historical_data_cache import HistoricalDataCache
from src.core.strategy_data_manager import StrategyDataManager

# Import options trading components
from src.trading.options_trade_executor import OptionsTradeExecutor
from src.utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

# Import news agent components
from src.news import NewsAgent


class AlphaStockOrchestrator:
    """
    Main orchestrator that coordinates all system components.
    
    This class manages:
    - Market data collection
    - Strategy execution
    - Signal generation and management
    - Options trading decisions
    - System lifecycle and error handling
    """
    
    def __init__(self, config_path: str = None, database_config_path: str = None):
        """Initialize the orchestrator with configuration."""
        self.config_path = config_path or "config/production.json"
        self.database_config_path = database_config_path or "config/database.json"
        self.config = self._load_config()
        self.database_config = self._load_database_config()
        
        # Setup logging
        self.logger = setup_logger(
            name="AlphaStockOrchestrator",
            level=self.config["logging"]["level"]
        )
        
        # Core components
        self.api_client = None
        self.data_layer: Optional[DataLayerInterface] = None
        self.historical_data_manager: Optional[HistoricalDataManager] = None
        self.analysis_engine: Optional[MarketAnalysisEngine] = None
        self.data_cache = SimpleDataCache(
            default_ttl=self.config["data_collection"]["realtime"]["cache_ttl"]
        )
        self.market_data_runner = None
        self.strategy_factory = StrategyFactory()
        self.signal_manager = None
        
        # New data pipeline components
        self.candle_aggregator: Optional[CandleAggregator] = None
        self.historical_cache: Optional[HistoricalDataCache] = None
        self.strategy_data_manager: Optional[StrategyDataManager] = None
        
        # Options trading executor
        self.options_trade_executor: Optional[OptionsTradeExecutor] = None
        
        # News agent for market news analysis
        self.news_agent: Optional[NewsAgent] = None
        
        # Specialized runners
        self.runner_manager = None
        self.equity_runner = None
        self.options_runner = None
        self.index_runner = None
        self.commodity_runner = None
        self.futures_runner = None
        
        # State management
        self.active_strategies: Dict[str, Any] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(
            max_workers=self.config["system"]["max_concurrent_strategies"]
        )
        
        # Performance tracking
        self.start_time = None
        self.stats = {
            "signals_generated": 0,
            "strategies_executed": 0,
            "api_calls": 0,
            "errors": 0
        }
        
        self.logger.info("AlphaStock Orchestrator initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            # Return minimal default config
            return {
                "api": {"timeout": 15},
                "system": {"max_concurrent_strategies": 5},
                "logging": {"level": "INFO"},
                "data_collection": {"realtime": {"cache_ttl": 300}},
                "strategies": {}
            }
    
    def _load_database_config(self) -> Dict[str, Any]:
        """Load database configuration from JSON file."""
        try:
            with open(self.database_config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            # Can't use self.logger here as it's not set up yet
            print(f"Warning: Error loading database config from {self.database_config_path}: {e}")
            print("Using development default config")
            # Return development default config
            return data_layer_factory.get_development_config()
    
    async def initialize(self):
        """Initialize all system components."""
        try:
            self.logger.info("Initializing system components...")
            
            # Initialize data layer first
            await self._initialize_data_layer()
            
            # Initialize API client
            await self._initialize_api_client()
            
            # Initialize historical data manager and analysis engine
            await self._initialize_analysis_components()
            
            # Initialize new data pipeline components
            await self._initialize_data_pipeline()
            
            # Ensure historical data for priority symbols
            await self._ensure_priority_historical_data()
            
            # Initialize specialized runners
            self._initialize_runners()
            
            # Initialize market data runner (legacy support)
            self._initialize_market_data_runner()
            
            # Initialize signal manager
            await self._initialize_signal_manager()
            
            # Initialize options trade executor (if enabled)
            await self._initialize_options_trade_executor()
            
            # Initialize news agent (if enabled)
            await self._initialize_news_agent()
            
            # Initialize strategies
            await self._initialize_strategies()
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            raise
    
    async def _initialize_data_layer(self):
        """Initialize the data storage layer."""
        try:
            self.logger.info("Initializing data layer...")
            
            # Create data layer from configuration
            # Get the environment config (development or production)
            env = self.database_config.get('default', 'development')
            storage_config = self.database_config.get(env, self.database_config.get('storage', {}))
            self.data_layer = data_layer_factory.create_from_config(storage_config)
            
            # Initialize the data layer
            success = await self.data_layer.initialize()
            if not success:
                raise Exception("Failed to initialize data layer")
            
            # Test the connection
            health = await self.data_layer.health_check()
            if health.get('overall_status') not in ['healthy', 'active']:
                self.logger.warning(f"Data layer health check failed: {health}")
            else:
                self.logger.info(f"Data layer initialized successfully: {health.get('overall_status')}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize data layer: {e}")
            # Try fallback to development config
            try:
                self.logger.info("Attempting fallback to development configuration...")
                dev_config = data_layer_factory.get_development_config()
                self.data_layer = data_layer_factory.create_from_config(dev_config)
                success = await self.data_layer.initialize()
                if success:
                    self.logger.info("Data layer initialized with development configuration")
                else:
                    raise Exception("Fallback initialization also failed")
            except Exception as fallback_error:
                self.logger.error(f"Fallback initialization failed: {fallback_error}")
                raise Exception("Could not initialize any data storage backend")
    
    async def _initialize_analysis_components(self):
        """Initialize historical data manager and analysis engine."""
        try:
            self.logger.info("Initializing analysis components...")
            
            # Initialize historical data manager
            self.historical_data_manager = HistoricalDataManager(
                api_client=self.api_client,
                data_layer=self.data_layer,
                config=self.config
            )
            
            # Initialize market analysis engine
            self.analysis_engine = MarketAnalysisEngine(
                historical_data_manager=self.historical_data_manager,
                data_layer=self.data_layer
            )
            
            self.logger.info("Analysis components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize analysis components: {e}")
            raise Exception("Could not initialize analysis components")
    
    async def _initialize_data_pipeline(self):
        """Initialize new data pipeline components (CandleAggregator, Cache, StrategyDataManager)."""
        try:
            self.logger.info("Initializing data pipeline components...")
            
            # Determine primary timeframe from enabled strategies
            primary_timeframe = self._determine_primary_timeframe()
            
            # Initialize CandleAggregator for real-time tick-to-candle conversion
            self.candle_aggregator = CandleAggregator(timeframe=primary_timeframe)
            self.logger.info(f"CandleAggregator initialized for {primary_timeframe} timeframe")
            
            # Initialize HistoricalDataCache with 5-minute refresh interval
            cache_refresh_interval = self.config.get("data_collection", {}).get("cache_refresh_interval", 300)
            self.historical_cache = HistoricalDataCache(
                data_layer=self.data_layer,
                refresh_interval_seconds=cache_refresh_interval
            )
            self.logger.info(f"HistoricalDataCache initialized with {cache_refresh_interval}s refresh interval")
            
            # Initialize StrategyDataManager to coordinate historical + real-time data
            self.strategy_data_manager = StrategyDataManager(
                config=self.config,
                data_layer=self.data_layer,
                candle_aggregator=self.candle_aggregator,
                historical_cache=self.historical_cache
            )
            self.logger.info("StrategyDataManager initialized successfully")
            
            # Preload historical data for enabled strategies
            await self._preload_strategy_data()
            
            self.logger.info("Data pipeline components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize data pipeline: {e}")
            self.logger.warning("Continuing without data pipeline - strategies will use legacy data flow")
            # Set to None to indicate failure - legacy flow will be used
            self.candle_aggregator = None
            self.historical_cache = None
            self.strategy_data_manager = None
    
    def _determine_primary_timeframe(self) -> str:
        """
        Determine the primary timeframe from enabled strategies.
        Returns the most common timeframe, or '15minute' as default.
        """
        timeframes = []
        for strategy_name, strategy_config in self.config.get("strategies", {}).items():
            if strategy_config.get("enabled", False):
                timeframe = strategy_config.get("timeframe", "15minute")
                timeframes.append(timeframe)
        
        if not timeframes:
            return "15minute"  # Default
        
        # Return most common timeframe
        from collections import Counter
        most_common = Counter(timeframes).most_common(1)[0][0]
        return most_common
    
    async def _preload_strategy_data(self):
        """Preload historical data for all enabled strategies."""
        if not self.strategy_data_manager:
            return
        
        try:
            self.logger.info("Preloading historical data for strategies...")
            
            # Get all symbols from stocks and enabled strategies
            symbols = [stock["symbol"] for stock in self.config.get("stocks", [])]
            
            # Get enabled strategies
            enabled_strategies = {
                name: config for name, config in self.config.get("strategies", {}).items()
                if config.get("enabled", False)
            }
            
            if not enabled_strategies or not symbols:
                self.logger.warning("No enabled strategies or symbols found for preload")
                return
            
            # Preload using StrategyDataManager
            self.strategy_data_manager.preload_strategies(enabled_strategies, symbols)
            
            # Log cache statistics
            stats = self.strategy_data_manager.get_cache_statistics()
            self.logger.info(f"Historical data preload complete: {stats}")
            
        except Exception as e:
            self.logger.error(f"Error preloading strategy data: {e}")
            self.logger.warning("Continuing without preload - data will be fetched on demand")
    
    async def _ensure_priority_historical_data(self):
        """Ensure historical data exists for priority symbols."""
        try:
            self.logger.info("Checking and ensuring priority historical data...")
            
            if not self.historical_data_manager:
                self.logger.warning("Historical data manager not available, skipping data check")
                return
            
            # Initialize historical data for priority symbols (Bank Nifty, etc.)
            results = await self.historical_data_manager.initialize_priority_symbols()
            
            # Log results
            successful_symbols = []
            failed_symbols = []
            
            for symbol, symbol_results in results.items():
                if isinstance(symbol_results, dict) and 'error' not in symbol_results:
                    success_count = sum(1 for success in symbol_results.values() if success)
                    total_count = len(symbol_results)
                    
                    if success_count == total_count:
                        successful_symbols.append(symbol)
                    else:
                        failed_symbols.append(f"{symbol} ({success_count}/{total_count})")
                else:
                    failed_symbols.append(symbol)
            
            if successful_symbols:
                self.logger.info(f"Historical data ready for: {', '.join(successful_symbols)}")
            
            if failed_symbols:
                self.logger.warning(f"Historical data issues for: {', '.join(failed_symbols)}")
            
            # Generate data report
            if self.historical_data_manager:
                report = await self.historical_data_manager.generate_data_report()
                data_quality = report['summary']['data_quality_score']
                self.logger.info(f"Overall data quality score: {data_quality:.2f}")
                
                if data_quality < 0.8:
                    self.logger.warning("Low data quality detected. Consider running data collection during market hours.")
            
        except Exception as e:
            self.logger.error(f"Error ensuring historical data: {e}")
            # Don't raise - system can continue without historical data
    
    async def _initialize_api_client(self):
        """Initialize the Kite API client."""
        try:
            self.api_client = KiteAPIClient()
            await self.api_client.initialize()
            self.logger.info("Kite API client connected successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite API client: {e}")
            self.logger.warning("Continuing without API client - some features may not work")
            # Don't raise to allow system to continue without API
    
    def _initialize_runners(self):
        """Initialize specialized market data runners."""
        try:
            # Get symbols from config, organized by asset type
            config_symbols = self.config.get("symbols", {})
            
            # Initialize Equity Runner
            equities = config_symbols.get("equities", [])
            if equities:
                self.equity_runner = EquityRunner(
                    api_client=self.api_client,
                    data_cache=self.data_cache,
                    symbols=equities,
                    interval_seconds=5
                )
                self.logger.info(f"Equity runner initialized for {len(equities)} stocks")
            
            # Initialize Options Runner
            options = config_symbols.get("options", [])
            if options:
                self.options_runner = OptionsRunner(
                    api_client=self.api_client,
                    data_cache=self.data_cache,
                    underlying_symbols=options,
                    interval_seconds=3
                )
                self.logger.info(f"Options runner initialized for {len(options)} underlyings")
            
            # Initialize Index Runner
            indices = config_symbols.get("indices", [])
            if indices:
                self.index_runner = IndexRunner(
                    api_client=self.api_client,
                    data_cache=self.data_cache,
                    indices=indices,
                    interval_seconds=5
                )
                self.logger.info(f"Index runner initialized for {len(indices)} indices")
            
            # Initialize Commodity Runner
            commodities = config_symbols.get("commodities", [])
            if commodities:
                self.commodity_runner = CommodityRunner(
                    api_client=self.api_client,
                    data_cache=self.data_cache,
                    commodities=commodities,
                    interval_seconds=10
                )
                self.logger.info(f"Commodity runner initialized for {len(commodities)} commodities")
            
            # Initialize Futures Runner
            futures = config_symbols.get("futures", [])
            if futures:
                self.futures_runner = FuturesRunner(
                    api_client=self.api_client,
                    data_cache=self.data_cache,
                    futures=futures,
                    interval_seconds=5
                )
                self.logger.info(f"Futures runner initialized for {len(futures)} contracts")
            
            # Initialize Runner Manager to coordinate all runners
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
                self.runner_manager = RunnerManager(active_runners)
                self.logger.info(f"Runner manager initialized with {len(active_runners)} runners")
                
                # Set up unified callback for new data from all runners
                for runner in active_runners:
                    runner.add_callback(self._on_new_runner_data)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize runners: {e}")
            self.logger.warning("Continuing without specialized runners - using legacy market data runner")
    
    def _initialize_market_data_runner(self):
        """Initialize the market data collection runner."""
        try:
            symbols = [stock["symbol"] for stock in self.config["stocks"]]
            
            self.market_data_runner = MarketDataRunner(
                api_client=self.api_client,
                data_cache=self.data_cache,
                data_layer=self.data_layer,  # Pass data_layer for database storage
                symbols=symbols,
                interval_seconds=self.config["data_collection"]["realtime"]["interval_seconds"]
            )
            
            # Set up callback for new data
            self.market_data_runner.add_callback(self._on_new_market_data)
            
            self.logger.info(f"Market data runner initialized for {len(symbols)} symbols with database storage")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize market data runner: {e}")
            raise
    
    async def _initialize_signal_manager(self):
        """Initialize the signal manager."""
        try:
            # Import and initialize signal manager with trading config and data layer
            from src.trading.signal_manager import SignalManager
            
            self.signal_manager = SignalManager(
                config=self.config.get("trading", {}),
                api_client=self.api_client,
                data_layer=self.data_layer
            )
            
            # Initialize the signal manager (load existing signals)
            await self.signal_manager.initialize()
            
            self.logger.info("Signal manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize signal manager: {e}")
            # Create a mock signal manager for now
    
    async def _initialize_options_trade_executor(self):
        """Initialize the options trade executor."""
        try:
            # Check if options trading is enabled
            options_config = self.config.get("options_trading", {})
            if not options_config.get("enabled", False):
                self.logger.info("Options trading is disabled in configuration")
                return
            
            self.logger.info("Initializing Options Trade Executor...")
            
            # Create the executor
            self.options_trade_executor = OptionsTradeExecutor(
                api_client=self.api_client,
                signal_manager=self.signal_manager,
                config=options_config,
                data_layer=self.data_layer
            )
            
            # Start the executor (begins listening for signals)
            await self.options_trade_executor.start()
            
            mode = options_config.get('mode', 'BALANCED')
            paper_trading = options_config.get('paper_trading', True)
            
            self.logger.info(
                f"[SUCCESS] Options Trade Executor started successfully!"
            )
            self.logger.info(f"   Mode: {mode}")
            self.logger.info(f"   Paper Trading: {paper_trading}")
            self.logger.info(f"   Listening for signals...")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize options trade executor: {e}", exc_info=True)
            self.logger.warning("System will continue without options trading")
            self.signal_manager = MockSignalManager()
    
    async def _initialize_news_agent(self):
        """Initialize the news analysis agent."""
        try:
            # Load news agent config if available
            news_config = {}
            news_config_path = Path("config/news_agent.json")
            if news_config_path.exists():
                with open(news_config_path, 'r') as f:
                    news_config = json.load(f)
            
            # Check if news agent is enabled
            if not news_config.get("enabled", False):
                self.logger.info("News Agent is disabled in configuration")
                return
            
            self.logger.info("Initializing News Agent...")
            
            # Create the news agent
            self.news_agent = NewsAgent(
                event_bus=None,  # Will use internal event handling
                data_layer=self.data_layer,
                kite_client=self.api_client,
                config=news_config,
                historical_cache=self.historical_cache
            )
            
            # Initialize the agent
            await self.news_agent.initialize()
            
            fetch_interval = news_config.get("fetch_interval_seconds", 300)
            market_hours_only = news_config.get("market_hours_only", True)
            
            self.logger.info("[SUCCESS] News Agent initialized successfully!")
            self.logger.info(f"   Fetch Interval: {fetch_interval}s")
            self.logger.info(f"   Market Hours Only: {market_hours_only}")
            self.logger.info(f"   RSS Feeds: {self.news_agent.rss_fetcher.get_feed_count()}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize news agent: {e}", exc_info=True)
            self.logger.warning("System will continue without news analysis")
            self.news_agent = None
    
    async def _initialize_strategies(self):
        """Initialize all enabled strategies."""
        try:
            strategies_config = self.config.get("strategies", {})
            
            for strategy_name, strategy_config in strategies_config.items():
                if strategy_config.get("enabled", False):
                    await self._initialize_strategy(strategy_name, strategy_config)
            
            self.logger.info(f"Initialized {len(self.active_strategies)} strategies")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize strategies: {e}")
            raise
    
    async def _initialize_strategy(self, strategy_name: str, strategy_config: Dict[str, Any]):
        """Initialize a specific strategy."""
        try:
            # Create strategy instances for each symbol
            symbols = strategy_config.get("symbols", [])
            parameters = strategy_config.get("parameters", {})
            
            strategy_instances = {}
            
            for symbol in symbols:
                try:
                    # Build config for this strategy instance
                    strategy_config_instance = {
                        'symbol': symbol,
                        **parameters  # Merge strategy parameters
                    }
                    strategy = self.strategy_factory.create_strategy(
                        strategy_name=strategy_name,
                        config=strategy_config_instance
                    )
                    strategy_instances[symbol] = strategy
                    self.logger.info(f"Created {strategy_name} strategy for {symbol}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to create {strategy_name} for {symbol}: {e}")
            
            if strategy_instances:
                self.active_strategies[strategy_name] = {
                    "instances": strategy_instances,
                    "config": strategy_config,
                    "last_execution": None,
                    "signals_count": 0
                }
                
        except Exception as e:
            self.logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
    
    def _on_new_market_data(self, symbol: str, data: pd.DataFrame):
        """Callback for when new market data is received."""
        try:
            # Feed tick data to CandleAggregator if pipeline is enabled
            if self.candle_aggregator and not data.empty:
                # Convert latest tick to dictionary format
                latest_tick = data.iloc[-1].to_dict()
                latest_tick['symbol'] = symbol
                latest_tick['asset_type'] = latest_tick.get('asset_type', 'EQUITY')
                
                # Add tick to aggregator (returns completed candle if any)
                completed_candle = self.candle_aggregator.add_tick(symbol, latest_tick)
                
                if completed_candle:
                    self.logger.info(f"✅ {self.candle_aggregator.timeframe} candle completed for {symbol} - executing strategies")
                    # Only execute strategies when a complete candle is formed
                    self._execute_strategies_for_symbol(symbol, data)
                else:
                    self.logger.debug(f"Tick received for {symbol} - waiting for {self.candle_aggregator.timeframe} candle completion")
            else:
                # Fallback: If aggregator not available, execute on every tick (legacy behavior)
                self.logger.debug(f"CandleAggregator not available - executing strategies immediately for {symbol}")
                self._execute_strategies_for_symbol(symbol, data)
            
        except Exception as e:
            self.logger.error(f"Error processing market data for {symbol}: {e}")
            self.stats["errors"] += 1
    
    def _on_new_runner_data(self, runner_name: str, symbol: str, data: pd.DataFrame):
        """Callback for when new data is received from specialized runners."""
        try:
            # Log data receipt
            asset_type = data.iloc[-1]['asset_type'] if not data.empty else 'UNKNOWN'
            self.logger.debug(f"Received {asset_type} data for {symbol} from {runner_name}")
            
            # Feed tick data to CandleAggregator if pipeline is enabled
            if self.candle_aggregator and not data.empty:
                # Convert latest tick to dictionary format
                latest_tick = data.iloc[-1].to_dict()
                latest_tick['symbol'] = symbol
                latest_tick['asset_type'] = asset_type
                
                # Add tick to aggregator (returns completed candle if any)
                completed_candle = self.candle_aggregator.add_tick(symbol, latest_tick)
                
                if completed_candle:
                    self.logger.info(f"✅ {self.candle_aggregator.timeframe} candle completed for {symbol} ({asset_type}) - executing strategies")
                    # Only execute strategies when a complete candle is formed
                    self._execute_strategies_for_symbol_with_type(symbol, data, asset_type, runner_name)
                else:
                    self.logger.debug(f"Tick received for {symbol} ({asset_type}) - waiting for {self.candle_aggregator.timeframe} candle completion")
            else:
                # Fallback: If aggregator not available, execute on every tick (legacy behavior)
                self.logger.debug(f"CandleAggregator not available - executing strategies immediately for {symbol} ({asset_type})")
                self._execute_strategies_for_symbol_with_type(symbol, data, asset_type, runner_name)
            
            # Update statistics
            self.stats["api_calls"] += 1
            
        except Exception as e:
            self.logger.error(f"Error processing runner data for {symbol} from {runner_name}: {e}")
            self.stats["errors"] += 1
    
    def _execute_strategies_for_symbol(self, symbol: str, data: pd.DataFrame):
        """Execute all strategies for a given symbol."""
        for strategy_name, strategy_info in self.active_strategies.items():
            strategy_instances = strategy_info["instances"]
            
            if symbol in strategy_instances:
                try:
                    strategy = strategy_instances[symbol]
                    
                    # Log strategy execution
                    self.logger.info(f"Running strategy '{strategy_name}' on stock '{symbol}' with {len(data)} data points")
                    
                    # Submit strategy execution to thread pool
                    future = self.executor.submit(
                        self._run_strategy,
                        strategy_name,
                        strategy,
                        symbol,
                        data
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error submitting {strategy_name} for {symbol}: {e}")
                    self.stats["errors"] += 1
    
    def _execute_strategies_for_symbol_with_type(self, symbol: str, data: pd.DataFrame, 
                                               asset_type: str, runner_name: str):
        """Execute strategies for a symbol with asset type awareness."""
        for strategy_name, strategy_info in self.active_strategies.items():
            strategy_instances = strategy_info["instances"]
            strategy_config = strategy_info["config"]
            
            # Check if strategy is configured for this asset type
            supported_assets = strategy_config.get("supported_asset_types", ["EQUITY"])
            if asset_type not in supported_assets:
                continue
            
            if symbol in strategy_instances:
                try:
                    strategy = strategy_instances[symbol]
                    
                    # Log strategy execution with asset type context
                    self.logger.info(f"Running strategy '{strategy_name}' on {asset_type} '{symbol}' "
                                   f"with {len(data)} data points (from {runner_name})")
                    
                    # Submit strategy execution to thread pool with asset type context
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
                    self.stats["errors"] += 1
    
    def _validate_strategy_data(self, data: pd.DataFrame, symbol: str, strategy_name: str, 
                               expected_timeframe: str, min_periods: int) -> bool:
        """
        Validate that data is suitable for strategy execution.
        Prevents strategies from executing with wrong timeframe data.
        
        Args:
            data: DataFrame to validate
            symbol: Trading symbol
            strategy_name: Name of strategy
            expected_timeframe: Expected timeframe (e.g., '15minute')
            min_periods: Minimum required data points
            
        Returns:
            True if data is valid, False otherwise
        """
        if data.empty:
            self.logger.error(
                f"🚨 DATA VALIDATION FAILED for {strategy_name} on {symbol}:\n"
                f"  ❌ DataFrame is EMPTY\n"
                f"  Expected: {expected_timeframe} candles with {min_periods}+ periods\n"
                f"  Action: SKIPPING strategy execution"
            )
            return False
        
        if len(data) < min_periods:
            self.logger.error(
                f"🚨 DATA VALIDATION FAILED for {strategy_name} on {symbol}:\n"
                f"  ❌ Insufficient data: {len(data)} rows < {min_periods} required\n"
                f"  Expected: {expected_timeframe} candles\n"
                f"  Action: SKIPPING strategy execution"
            )
            return False
        
        # Check if data has proper OHLCV columns
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            self.logger.error(
                f"🚨 DATA VALIDATION FAILED for {strategy_name} on {symbol}:\n"
                f"  ❌ Missing columns: {missing_columns}\n"
                f"  Available columns: {list(data.columns)}\n"
                f"  Action: SKIPPING strategy execution"
            )
            return False
        
        return True
    
    def _run_strategy(self, strategy_name: str, strategy, symbol: str, data: pd.DataFrame):
        """Run a strategy and handle the results."""
        try:
            # Get strategy configuration
            strategy_config = self.active_strategies[strategy_name]["config"]
            expected_timeframe = strategy_config.get('timeframe', '15minute')
            min_periods = strategy_config.get('historical_lookback', {}).get('min_periods', 50)
            
            # Use StrategyDataManager if available, otherwise use legacy data
            if self.strategy_data_manager:
                # Get proper historical + real-time data from StrategyDataManager
                strategy_data = self.strategy_data_manager.get_strategy_data(
                    symbol=symbol,
                    strategy_config=strategy_config,
                    asset_type='EQUITY'
                )
                
                # CRITICAL FIX: Validate data quality - DO NOT fall back silently to wrong timeframe
                if strategy_data.empty:
                    self.logger.error(
                        f"🚨 CRITICAL: StrategyDataManager returned EMPTY data for {symbol}\n"
                        f"  Strategy: {strategy_name}\n"
                        f"  Expected: {expected_timeframe} candles with {min_periods}+ periods\n"
                        f"  ❌ CANNOT use fallback (would be 5-second ticks, not {expected_timeframe})\n"
                        f"  Action: SKIPPING strategy execution to prevent incorrect signals\n"
                        f"  Fix: Ensure historical data is downloaded via complete_workflow.py"
                    )
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return  # FAIL LOUDLY - do not execute strategy with wrong data
                
                # Validate data quality before execution
                if not self._validate_strategy_data(strategy_data, symbol, strategy_name, 
                                                   expected_timeframe, min_periods):
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return  # Data validation failed, skip execution
                    
            else:
                # Legacy data flow - log strong warning
                self.logger.warning(
                    f"⚠️ Using legacy data path for {strategy_name} on {symbol}\n"
                    f"  StrategyDataManager not available - data may not match timeframe!\n"
                    f"  Expected: {expected_timeframe}, Actual: unknown (cache data)\n"
                    f"  Recommendation: Initialize StrategyDataManager"
                )
                strategy_data = data
                
                # Still validate the legacy data
                if not self._validate_strategy_data(strategy_data, symbol, strategy_name, 
                                                   expected_timeframe, min_periods):
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return
            
            # Execute strategy with validated data
            signal = strategy.analyze(symbol=symbol, historical_data=strategy_data)
            self.stats["strategies_executed"] += 1
            
            # Update last execution time
            self.active_strategies[strategy_name]["last_execution"] = get_current_time()
            
            # Log strategy result
            if signal:
                # Convert dict to object if needed (for attribute access)
                if isinstance(signal, dict):
                    from types import SimpleNamespace
                    # Normalize field names for consistency (different strategies use different field names)
                    normalized_signal = {
                        'action': signal.get('action') or signal.get('signal_type'),
                        'price': signal.get('price') or signal.get('entry_price'),
                        'stop_loss': signal.get('stop_loss') or signal.get('stop_loss_price'),
                        'target': signal.get('target') or signal.get('target_price'),
                        'confidence': signal.get('confidence', 0.5),
                        'symbol': signal.get('symbol'),
                        'strategy': signal.get('strategy'),
                        'timestamp': signal.get('timestamp'),
                        'metadata': signal.get('metadata', {})
                    }
                    signal = SimpleNamespace(**normalized_signal)
                
                if signal.action != "HOLD":
                    self.logger.info(f"Strategy '{strategy_name}' generated {signal.action} signal for '{symbol}' "
                                   f"at price {signal.price:.2f} (confidence: {signal.confidence:.2%}) "
                                   f"[analyzed {len(strategy_data)} candles]")
                    
                    # Process signal async
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.create_task(self._process_signal(strategy_name, signal, symbol))
                    except RuntimeError:
                        # No running loop - create one
                        asyncio.run(self._process_signal(strategy_name, signal, symbol))
                    
                    self.stats["signals_generated"] += 1
                    self.active_strategies[strategy_name]["signals_count"] += 1
                else:
                    self.logger.debug(f"Strategy '{strategy_name}' analyzed '{symbol}': HOLD (no action) "
                                    f"[{len(strategy_data)} candles]")
            else:
                self.logger.debug(f"Strategy '{strategy_name}' returned no signal for '{symbol}'")
                
        except Exception as e:
            self.logger.error(f"Error running {strategy_name} for {symbol}: {e}")
            self.stats["errors"] += 1
    
    def _run_strategy_with_context(self, strategy_name: str, strategy, symbol: str, 
                                 data: pd.DataFrame, asset_type: str, runner_name: str):
        """Run a strategy with asset type context and handle the results."""
        try:
            # Get strategy configuration
            strategy_config = self.active_strategies[strategy_name]["config"]
            expected_timeframe = strategy_config.get('timeframe', '15minute')
            min_periods = strategy_config.get('historical_lookback', {}).get('min_periods', 50)
            
            # Use StrategyDataManager if available, otherwise use legacy data
            if self.strategy_data_manager:
                # Get proper historical + real-time data from StrategyDataManager
                strategy_data = self.strategy_data_manager.get_strategy_data(
                    symbol=symbol,
                    strategy_config=strategy_config,
                    asset_type=asset_type
                )
                
                # CRITICAL FIX: Validate data quality - DO NOT fall back silently to wrong timeframe
                if strategy_data.empty:
                    self.logger.error(
                        f"🚨 CRITICAL: StrategyDataManager returned EMPTY data for {symbol}\n"
                        f"  Strategy: {strategy_name}\n"
                        f"  Asset Type: {asset_type}\n"
                        f"  Expected: {expected_timeframe} candles with {min_periods}+ periods\n"
                        f"  ❌ CANNOT use fallback (would be 5-second ticks, not {expected_timeframe})\n"
                        f"  Action: SKIPPING strategy execution to prevent incorrect signals\n"
                        f"  Fix: Ensure historical data is downloaded via complete_workflow.py"
                    )
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return  # FAIL LOUDLY - do not execute strategy with wrong data
                
                # Validate data quality before execution
                if not self._validate_strategy_data(strategy_data, symbol, strategy_name, 
                                                   expected_timeframe, min_periods):
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return  # Data validation failed, skip execution
                    
            else:
                # Legacy data flow - log strong warning
                self.logger.warning(
                    f"⚠️ Using legacy data path for {strategy_name} on {symbol}\n"
                    f"  Asset Type: {asset_type}\n"
                    f"  StrategyDataManager not available - data may not match timeframe!\n"
                    f"  Expected: {expected_timeframe}, Actual: unknown (cache data)\n"
                    f"  Recommendation: Initialize StrategyDataManager"
                )
                strategy_data = data
                
                # Still validate the legacy data
                if not self._validate_strategy_data(strategy_data, symbol, strategy_name, 
                                                   expected_timeframe, min_periods):
                    self.stats["data_errors"] = self.stats.get("data_errors", 0) + 1
                    return
            
            # Execute strategy with validated data and asset type awareness
            if hasattr(strategy, 'analyze_with_context'):
                signal = strategy.analyze_with_context(symbol=symbol, historical_data=strategy_data, asset_type=asset_type)
            else:
                signal = strategy.analyze(symbol=symbol, historical_data=strategy_data)
                
            self.stats["strategies_executed"] += 1
            
            # Update last execution time
            self.active_strategies[strategy_name]["last_execution"] = get_current_time()
            
            # Log strategy result with context
            if signal:
                # Convert dict to object if needed (for attribute access)
                if isinstance(signal, dict):
                    from types import SimpleNamespace
                    # Normalize field names for consistency (different strategies use different field names)
                    normalized_signal = {
                        'action': signal.get('action') or signal.get('signal_type'),
                        'price': signal.get('price') or signal.get('entry_price'),
                        'stop_loss': signal.get('stop_loss') or signal.get('stop_loss_price'),
                        'target': signal.get('target') or signal.get('target_price'),
                        'confidence': signal.get('confidence', 0.5),
                        'symbol': signal.get('symbol'),
                        'strategy': signal.get('strategy'),
                        'timestamp': signal.get('timestamp'),
                        'metadata': signal.get('metadata', {})
                    }
                    signal = SimpleNamespace(**normalized_signal)
                
                if signal.action != "HOLD":
                    self.logger.info(f"Strategy '{strategy_name}' generated {signal.action} signal for "
                                   f"{asset_type} '{symbol}' at price {signal.price:.2f} "
                                   f"(confidence: {signal.confidence:.2%}, source: {runner_name}) "
                                   f"[analyzed {len(strategy_data)} candles]")
                    self._process_signal_with_context(strategy_name, signal, symbol, asset_type, runner_name)
                    self.stats["signals_generated"] += 1
                    self.active_strategies[strategy_name]["signals_count"] += 1
                else:
                    self.logger.debug(f"Strategy '{strategy_name}' analyzed {asset_type} '{symbol}': HOLD (no action) "
                                    f"[{len(strategy_data)} candles]")
            else:
                self.logger.debug(f"Strategy '{strategy_name}' returned no signal for {asset_type} '{symbol}'")
                
        except Exception as e:
            self.logger.error(f"Error running {strategy_name} for {symbol} ({asset_type}): {e}")
            self.stats["errors"] += 1
    
    async def _process_signal(self, strategy_name: str, signal, symbol: str):
        """Process a trading signal (now async)."""
        try:
            self.logger.info(
                f"Signal from {strategy_name} for {symbol}: "
                f"{signal.action} at {signal.price:.2f} "
                f"(confidence: {signal.confidence:.2f})"
            )
            
            # Store signal using adapter method
            if self.signal_manager and hasattr(self.signal_manager, 'add_signal_from_strategy'):
                try:
                    created_signal = await self.signal_manager.add_signal_from_strategy(
                        strategy_name=strategy_name,
                        symbol=symbol,
                        strategy_signal=signal
                    )
                    self.logger.info(f"Signal {created_signal.id} stored successfully")
                    
                except Exception as e:
                    self.logger.error(f"Failed to store signal: {e}", exc_info=True)
            
            # Log signal details
            signal_data = {
                "timestamp": get_current_time().isoformat(),
                "strategy": strategy_name,
                "symbol": symbol,
                "action": signal.action,
                "price": signal.price,
                "confidence": signal.confidence,
                "target": getattr(signal, 'target', None),
                "stop_loss": getattr(signal, 'stop_loss', None)
            }
            
            self.logger.info(f"Signal processed: {signal_data}")
            
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}", exc_info=True)
            self.stats["errors"] += 1
    
    def _process_signal_with_context(self, strategy_name: str, signal, symbol: str, 
                                   asset_type: str, runner_name: str):
        """Process a trading signal with asset type context."""
        try:
            self.logger.info(
                f"Signal from {strategy_name} for {symbol} ({asset_type}): "
                f"{signal.action} at {signal.price:.2f} "
                f"(confidence: {signal.confidence:.2f}) via {runner_name}"
            )
            
            # Add signal to signal manager with context
            if self.signal_manager and hasattr(self.signal_manager, 'add_signal_with_context'):
                self.signal_manager.add_signal_with_context(
                    strategy=strategy_name,
                    symbol=symbol,
                    signal=signal,
                    asset_type=asset_type,
                    runner_name=runner_name
                )
            elif self.signal_manager and hasattr(self.signal_manager, 'add_signal'):
                # Fallback to legacy method
                self.signal_manager.add_signal(
                    strategy=strategy_name,
                    symbol=symbol,
                    signal=signal
                )
            
            # Enhanced signal data with context
            signal_data = {
                "timestamp": get_current_time().isoformat(),
                "strategy": strategy_name,
                "symbol": symbol,
                "asset_type": asset_type,
                "runner": runner_name,
                "action": signal.action,
                "price": signal.price,
                "confidence": signal.confidence,
                "target": getattr(signal, 'target', None),
                "stop_loss": getattr(signal, 'stop_loss', None)
            }
            
            self.logger.info(f"Enhanced signal processed: {signal_data}")
            
        except Exception as e:
            self.logger.error(f"Error processing signal with context: {e}")
            self.stats["errors"] += 1
    
    async def start(self):
        """Start the orchestrator."""
        try:
            if self.running:
                self.logger.warning("Orchestrator is already running")
                return
            
            self.logger.info("Starting AlphaStock Orchestrator...")
            self.running = True
            self.start_time = get_current_time()
            
            # Start market data collection
            if self.market_data_runner:
                self.market_data_runner.start()
                self.logger.info("Market data collection started")
            
            # Start specialized runners
            if self.runner_manager:
                self.runner_manager.start_all()
                self.logger.info("Specialized runners started")
            
            # Start news agent
            if self.news_agent:
                await self.news_agent.start()
                self.logger.info("News agent started")
            
            # Start main loop
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting orchestrator: {e}")
            await self.stop()
            raise
    
    async def _main_loop(self):
        """Main orchestrator loop."""
        self.logger.info("Entering main orchestration loop")
        
        while self.running:
            try:
                # Check if market is open
                if not is_market_open():
                    self.logger.info("Market is closed, waiting...")
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Periodic health checks
                await self._health_check()
                
                # Log statistics
                self._log_statistics()
                
                # Sleep for main loop interval
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(10)
    
    async def _health_check(self):
        """Perform system health checks."""
        try:
            # Check API connection (not async, don't await)
            if self.api_client and hasattr(self.api_client, 'health_check'):
                self.api_client.health_check()
            
            # Check market data runner
            if self.market_data_runner and not self.market_data_runner.is_running:
                self.logger.warning("Market data runner stopped, restarting...")
                self.market_data_runner.start()
            
            # Check strategy performance
            self._check_strategy_health()
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
    
    def _check_strategy_health(self):
        """Check if strategies are executing properly."""
        current_time = get_current_time()
        
        for strategy_name, strategy_info in self.active_strategies.items():
            last_execution = strategy_info.get("last_execution")
            
            if last_execution:
                time_since_execution = current_time - last_execution
                if time_since_execution > timedelta(minutes=10):
                    self.logger.warning(
                        f"Strategy {strategy_name} hasn't executed in "
                        f"{time_since_execution.total_seconds():.0f} seconds"
                    )
    
    def _log_statistics(self):
        """Log system statistics."""
        if self.start_time:
            uptime = get_current_time() - self.start_time
            
            stats_message = (
                f"System Stats - Uptime: {uptime.total_seconds():.0f}s, "
                f"Signals: {self.stats['signals_generated']}, "
                f"Executions: {self.stats['strategies_executed']}, "
                f"Errors: {self.stats['errors']}, "
                f"Cache Size: {len(self.data_cache._cache) if self.data_cache else 0}"
            )
            
            self.logger.info(stats_message)
    
    async def stop(self):
        """Stop the orchestrator and cleanup resources."""
        try:
            self.logger.info("Stopping AlphaStock Orchestrator...")
            self.running = False
            
            # Stop market data collection
            if self.market_data_runner:
                self.market_data_runner.stop()
                self.logger.info("Market data collection stopped")
            
            # Stop specialized runners
            if self.runner_manager:
                self.runner_manager.stop_all()
                self.logger.info("Specialized runners stopped")
            
            # Stop news agent
            if self.news_agent:
                await self.news_agent.stop()
                self.logger.info("News agent stopped")
            
            # Close data layer connections
            if self.data_layer:
                await self.data_layer.close()
                self.logger.info("Data layer connections closed")
            
            # Shutdown thread pool
            self.executor.shutdown(wait=True)
            self.logger.info("Thread pool shutdown complete")
            
            # Final statistics
            self._log_final_statistics()
            
            self.logger.info("AlphaStock Orchestrator stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def _log_final_statistics(self):
        """Log final system statistics."""
        if self.start_time:
            uptime = get_current_time() - self.start_time
            
            final_stats = {
                "session_duration": uptime.total_seconds(),
                "signals_generated": self.stats["signals_generated"],
                "strategies_executed": self.stats["strategies_executed"],
                "total_errors": self.stats["errors"],
                "strategies_active": len(self.active_strategies)
            }
            
            self.logger.info(f"Final Statistics: {final_stats}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            "running": self.running,
            "uptime_seconds": (get_current_time() - self.start_time).total_seconds() if self.start_time else 0,
            "statistics": self.stats.copy(),
            "active_strategies": {
                name: {
                    "symbols": list(info["instances"].keys()),
                    "signals_count": info["signals_count"],
                    "last_execution": info["last_execution"].isoformat() if info["last_execution"] else None
                }
                for name, info in self.active_strategies.items()
            },
            "market_data_active": self.market_data_runner.is_running if self.market_data_runner else False,
            "cache_size": len(self.data_cache._cache) if self.data_cache else 0
        }
    
    def get_runner_status(self) -> Dict[str, Any]:
        """Get status of all specialized runners."""
        status = {
            "timestamp": get_current_time().isoformat(),
            "runner_manager_active": self.runner_manager.is_running if self.runner_manager else False,
            "runners": {}
        }
        
        # Individual runner status
        runners = [
            ("equity", self.equity_runner),
            ("options", self.options_runner),
            ("index", self.index_runner),
            ("commodity", self.commodity_runner),
            ("futures", self.futures_runner)
        ]
        
        for runner_name, runner in runners:
            if runner:
                status["runners"][runner_name] = {
                    "active": runner.is_running,
                    "symbols_count": len(runner.symbols),
                    "last_update": runner.last_update.isoformat() if hasattr(runner, 'last_update') and runner.last_update else None,
                    "error_count": getattr(runner, 'error_count', 0)
                }
        
        return status
    
    def get_comprehensive_market_data(self) -> Dict[str, Any]:
        """Get comprehensive market data from all runners."""
        market_data = {
            "timestamp": get_current_time().isoformat(),
            "equities": {},
            "options": {},
            "indices": {},
            "commodities": {},
            "futures": {}
        }
        
        # Collect data from each runner
        if self.equity_runner:
            try:
                market_data["equities"] = {
                    "summary": self.equity_runner.get_equity_summary(),
                    "top_movers": self.equity_runner.get_top_movers(),
                    "sector_performance": self.equity_runner.get_sector_performance()
                }
            except Exception as e:
                self.logger.error(f"Error getting equity data: {e}")
        
        if self.options_runner:
            try:
                market_data["options"] = {
                    "summary": self.options_runner.get_options_summary(),
                    "chains": self.options_runner.get_options_chains_summary()
                }
            except Exception as e:
                self.logger.error(f"Error getting options data: {e}")
        
        if self.index_runner:
            try:
                market_data["indices"] = {
                    "overview": self.index_runner.get_market_overview(),
                    "sectoral_performance": self.index_runner.get_sectoral_performance()
                }
            except Exception as e:
                self.logger.error(f"Error getting index data: {e}")
        
        if self.commodity_runner:
            try:
                market_data["commodities"] = {
                    "summary": self.commodity_runner.get_commodity_summary(),
                    "seasonality": self.commodity_runner.get_commodity_seasonality(),
                    "alerts": self.commodity_runner.get_commodity_alerts()
                }
            except Exception as e:
                self.logger.error(f"Error getting commodity data: {e}")
        
        if self.futures_runner:
            try:
                market_data["futures"] = {
                    "summary": self.futures_runner.get_futures_summary(),
                    "chain_analysis": self.futures_runner.get_futures_chain_analysis(),
                    "rollover_analysis": self.futures_runner.get_rollover_analysis()
                }
            except Exception as e:
                self.logger.error(f"Error getting futures data: {e}")
        
        return market_data
    
    def get_trading_opportunities(self) -> Dict[str, Any]:
        """Identify trading opportunities across all asset classes."""
        opportunities = {
            "timestamp": get_current_time().isoformat(),
            "high_momentum": [],
            "oversold_opportunities": [],
            "breakout_candidates": [],
            "options_opportunities": [],
            "commodity_alerts": [],
            "futures_rollover": []
        }
        
        # Analyze equity opportunities
        if self.equity_runner:
            try:
                top_movers = self.equity_runner.get_top_movers()
                for mover in top_movers.get("gainers", [])[:5]:
                    if mover.get("change_pct", 0) > 3:  # High momentum threshold
                        opportunities["high_momentum"].append({
                            "symbol": mover["symbol"],
                            "change_pct": mover["change_pct"],
                            "asset_type": "EQUITY"
                        })
            except Exception as e:
                self.logger.error(f"Error analyzing equity opportunities: {e}")
        
        # Analyze commodity alerts
        if self.commodity_runner:
            try:
                alerts = self.commodity_runner.get_commodity_alerts()
                opportunities["commodity_alerts"] = alerts[:10]  # Top 10 alerts
            except Exception as e:
                self.logger.error(f"Error getting commodity alerts: {e}")
        
        # Analyze futures rollover opportunities
        if self.futures_runner:
            try:
                rollover_analysis = self.futures_runner.get_rollover_analysis()
                opportunities["futures_rollover"] = rollover_analysis.get("rollover_recommendations", [])
            except Exception as e:
                self.logger.error(f"Error analyzing futures rollover: {e}")
        
        return opportunities


class MockSignalManager:
    """Mock signal manager for testing."""
    
    def __init__(self):
        self.signals = []
    
    def add_signal(self, strategy: str, symbol: str, signal):
        """Add a signal to the mock manager."""
        self.signals.append({
            "timestamp": get_current_time(),
            "strategy": strategy,
            "symbol": symbol,
            "signal": signal
        })


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    sys.exit(0)


async def main():
    """Main entry point."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start orchestrator
    orchestrator = AlphaStockOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)
