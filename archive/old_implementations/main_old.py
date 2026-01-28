#!/usr/bin/env python3
"""
MStock Trading Agent
Continuously runs during market hours to collect data and analyze stocks
"""

import os
import sys
import json
import time
import logging
import threading
import schedule
from datetime import datetime, timedelta

# Add the Agent directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Agent modules
from src.api.mstock_api import MStockAPI
from src.data_manager.historical_manager import HistoricalDataManager
from src.data_manager.realtime_manager import RealtimeDataManager
from src.strategies.rsi_divergence import RSIDivergenceStrategy
from src.strategies.ema_scalping import EMAScalpingStrategy
from src.strategies.niftybank_ema_scalping import NiftyBankEMAScalpingStrategy
from src.strategies.final_ema_scalping_wrapper import FinalEMAScalpingStrategy
from src.trading.signal_manager import SignalManager
from src.trading.order_executor import OrderExecutor
from src.trading.order_tracker import OrderTracker
from src.utils.market_hours import MarketHours
from src.utils.logger_setup import setup_logger

# Global variables
config = None
api_client = None
historical_manager = None
realtime_manager = None
market_hours = None
signal_manager = None
order_executor = None
order_tracker = None
strategies = {}
is_running = False
analysis_threads = {}

def load_config():
    """Load configuration from file"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
    
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

def initialize():
    """Initialize the agent"""
    global config, api_client, historical_manager, realtime_manager, market_hours
    global signal_manager, order_executor, order_tracker, strategies
    
    # Load configuration
    config = load_config()
    
    # Set up logging
    logger = setup_logger(config)
    logger.info("Initializing MStock Trading Agent")
    
    # Initialize API client
    api_client = MStockAPI(config)
    
    # Initialize data managers
    historical_manager = HistoricalDataManager(api_client, config)
    realtime_manager = RealtimeDataManager(api_client, config)
    
    # Initialize market hours checker
    market_hours = MarketHours(config)
    
    # Initialize signal manager
    signal_manager = SignalManager(config)
    
    # Initialize order executor and tracker
    order_executor = OrderExecutor(api_client, config, signal_manager)
    order_tracker = OrderTracker(api_client, config, signal_manager)
    
    # Initialize strategies
    if config["strategies"]["rsi_divergence"]["enabled"]:
        strategies["rsi_divergence"] = RSIDivergenceStrategy(config)
        strategies["rsi_divergence"].set_signal_manager(signal_manager)
    
    if config["strategies"]["ema_scalping"]["enabled"]:
        strategies["ema_scalping"] = EMAScalpingStrategy(config)
        strategies["ema_scalping"].set_signal_manager(signal_manager)
    
    if config["strategies"]["final_ema_scalping"]["enabled"]:
        strategies["final_ema_scalping"] = FinalEMAScalpingStrategy(config)
        strategies["final_ema_scalping"].set_signal_manager(signal_manager)
    
    if config["strategies"]["niftybank_ema_scalping"]["enabled"]:
        strategies["niftybank_ema_scalping"] = NiftyBankEMAScalpingStrategy(config)
        strategies["niftybank_ema_scalping"].set_signal_manager(signal_manager)
    
    logger.info("Initialization complete")

def authenticate():
    """Authenticate with the API"""
    logger = logging.getLogger()
    
    try:
        # Login to get request token
        login_response = api_client.login()
        logger.info("Login successful")
        request_token = input("Please enter the request token: ")
        # Generate session
        if request_token:
            session_response = api_client.generate_session(request_token)
            logger.info("Session generated successfully")
        else:
            logger.error("Request token not available")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return False

def update_historical_data():
    """Update historical data for all stocks"""
    logger = logging.getLogger()
    logger.info("Running scheduled historical data validation and update")
    
    try:
        validation_result = historical_manager.validate_and_update_all_data()
        
        if validation_result["errors"] > 0:
            logger.warning(f"Scheduled historical data update completed with {validation_result['errors']} errors")
        else:
            logger.info("Scheduled historical data update completed successfully")
            
    except Exception as e:
        logger.error(f"Error in scheduled historical data update: {e}")

def cleanup_realtime_data():
    """Clean up previous day's real-time data"""
    logger = logging.getLogger()
    logger.info("Cleaning up previous day's real-time data")
    
    try:
        realtime_manager.cleanup_old_data()
        logger.info("Real-time data cleanup complete")
    except Exception as e:
        logger.error(f"Error cleaning up real-time data: {e}")

def analyze_stock(symbol, strategy_name, strategy):
    """Analyze a stock using a strategy"""
    logger = logging.getLogger()
    
    try:
        # Load historical data
        historical_data = historical_manager.load_historical_data(symbol)
        
        # Load real-time data
        realtime_data = realtime_manager.load_realtime_data(symbol)
        
        # Run analysis
        result = strategy.analyze(symbol, historical_data, realtime_data)
        
        if result:
            if result.get("bullish_divergence") or result.get("bearish_divergence"):
                logger.info(f"Strategy {strategy_name} generated signal for {symbol}: {result}")
    except Exception as e:
        logger.error(f"Error analyzing {symbol} with {strategy_name}: {e}")

def run_analysis():
    """Run analysis for all stocks using symbol-appropriate strategies"""
    logger = logging.getLogger()
    logger.info("Running analysis")
    
    # Get list of symbols
    symbols = [stock["symbol"] for stock in config["stocks"]]
    
    # Define symbol-specific strategy mapping
    strategy_mapping = {
        "NIFTYBANK": ["niftybank_ema_scalping"],  # Use optimized strategy for NiftyBank
        "NIFTYFINSERVICE": ["final_ema_scalping", "rsi_divergence"],  # Use proven final strategy for FinService
        "NSE:SBIN": ["rsi_divergence"],  # Use RSI for individual stocks
        "NSE:INFY": ["rsi_divergence"],
        "NSE:RELIANCE": ["rsi_divergence"]
    }
    
    # Run analysis for each symbol with its appropriate strategies
    for symbol in symbols:
        # Get strategies for this symbol (default to all if not specified)
        symbol_strategies = strategy_mapping.get(symbol, list(strategies.keys()))
        
        for strategy_name in symbol_strategies:
            if strategy_name in strategies:
                strategy = strategies[strategy_name]
                
                # Run in a separate thread to avoid blocking
                thread_name = f"{symbol}_{strategy_name}"
                
                # Skip if already running
                if thread_name in analysis_threads and analysis_threads[thread_name].is_alive():
                    logger.debug(f"Analysis for {symbol} with {strategy_name} is already running")
                    continue
                
                thread = threading.Thread(
                    target=analyze_stock,
                    args=(symbol, strategy_name, strategy),
                    name=thread_name
                )
                thread.daemon = True
                thread.start()
                
                analysis_threads[thread_name] = thread
                logger.debug(f"Started analysis for {symbol} with {strategy_name}")
    
    logger.info("Analysis started")

def schedule_tasks():
    """Schedule recurring tasks"""
    logger = logging.getLogger()
    logger.info("Scheduling tasks")
    
    # Schedule historical data update (early morning before market opens)
    update_time = config["data_collection"]["historical"]["update_time"]
    schedule.every().day.at(update_time).do(update_historical_data)
    logger.info(f"Scheduled historical data update at {update_time}")
    
    # Schedule real-time data cleanup (early morning before market opens)
    cleanup_time = config["data_collection"]["realtime"]["cleanup_time"]
    schedule.every().day.at(cleanup_time).do(cleanup_realtime_data)
    logger.info(f"Scheduled real-time data cleanup at {cleanup_time}")
    
    # Schedule analysis for each strategy
    for strategy_name, strategy_config in config["strategies"].items():
        if strategy_config["enabled"]:
            interval_minutes = strategy_config["analysis_interval_minutes"]
            schedule.every(interval_minutes).minutes.do(run_analysis)
            logger.info(f"Scheduled {strategy_name} analysis every {interval_minutes} minutes")

def start_agent():
    """Start the agent"""
    global is_running
    
    logger = logging.getLogger()
    logger.info("Starting agent")
    
    # Initialize
    initialize()
    
    # Authenticate
    if not authenticate():
        logger.error("Authentication failed, exiting")
        return
    
    # Validate and update historical data for all stocks and indices
    logger.info("Validating and updating historical data for all symbols...")
    validation_result = historical_manager.validate_and_update_all_data()
    
    if validation_result["errors"] > 0:
        logger.warning(f"Historical data validation completed with {validation_result['errors']} errors")
    else:
        logger.info("Historical data validation completed successfully")
    
    # Schedule tasks
    schedule_tasks()
    
    # Start real-time data collection
    realtime_manager.start_collection()
    
    # Start order executor and tracker if trading is enabled
    if config["trading"]["enabled"]:
        order_executor.start()
        order_tracker.start()
        logger.info("Trading functionality enabled")
    else:
        logger.info("Trading functionality disabled (signals will be generated but not executed)")
    
    is_running = True
    
    # Main loop
    try:
        while is_running:
            # Run pending scheduled tasks
            schedule.run_pending()
            
            # Check if market is open
            if market_hours.is_market_open():
                # Market is open, ensure real-time data collection is running
                if not realtime_manager.is_collecting:
                    logger.info("Market is open, starting real-time data collection")
                    realtime_manager.start_collection()
            else:
                # Market is closed, stop real-time data collection
                if realtime_manager.is_collecting:
                    logger.info("Market is closed, stopping real-time data collection")
                    realtime_manager.stop_collection()
            
            # Sleep for a short time
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping agent")
        stop_agent()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        stop_agent()

def stop_agent():
    """Stop the agent"""
    global is_running
    
    logger = logging.getLogger()
    logger.info("Stopping agent")
    
    # Stop real-time data collection
    if realtime_manager and realtime_manager.is_collecting:
        realtime_manager.stop_collection()
    
    # Stop order executor and tracker
    if order_executor:
        order_executor.stop()
    
    if order_tracker:
        order_tracker.stop()
    
    is_running = False
    logger.info("Agent stopped")

if __name__ == "__main__":
    start_agent()