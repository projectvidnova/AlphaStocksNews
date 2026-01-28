#!/usr/bin/env python3
"""
MStock Strategy Backtester

This script runs backtests for trading strategies on historical data.
It is independent of the main agent workflow and can be triggered separately.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta

# Add the Agent directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Agent modules
from src.api.mstock_api import MStockAPI
from src.data_manager.historical_manager import HistoricalDataManager
from src.strategies.rsi_divergence import RSIDivergenceStrategy
from src.strategies.final_ema_scalping_strategy import OptimizedHighQualityScalping
from src.strategies.niftybank_ema_scalping import NiftyBankEMAScalpingStrategy
from src.trading.backtest_manager import BacktestManager
from src.utils.logger_setup import setup_logger

def load_config():
    """Load configuration from file"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
    
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

def load_strategy(strategy_name, config):
    """Load a strategy by name"""
    if strategy_name == "rsi_divergence":
        return RSIDivergenceStrategy(config)
    elif strategy_name == "ema_scalping":
        return OptimizedHighQualityScalping()
    elif strategy_name == "niftybank_ema_scalping":
        return NiftyBankEMAScalpingStrategy(config)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")

def run_backtest(args):
    """Run a backtest with the specified parameters"""
    # Load configuration
    config = load_config()
    
    # Set up logging
    logger = setup_logger(config)
    logger.info("Starting backtest")
    
    # Initialize API client (needed for historical data)
    api_client = MStockAPI(config)
    
    # Initialize historical data manager
    historical_manager = HistoricalDataManager(api_client, config)
    
    # Initialize backtest manager
    backtest_manager = BacktestManager(config, historical_manager)
    
    # Load strategy
    strategy = load_strategy(args.strategy, config)
    
    # Run backtest
    results = backtest_manager.run_backtest(
        strategy=strategy,
        symbol=args.symbol,
        start_date=args.start_date,
        end_date=args.end_date,
        backtest_id=args.id
    )
    
    if results:
        # Print summary
        summary = results["summary"]
        print("\nBacktest Summary:")
        print(f"Backtest ID: {results['backtest_id']}")
        print(f"Strategy: {args.strategy}")
        print(f"Symbol: {args.symbol}")
        print(f"Period: {args.start_date} to {args.end_date}")
        print(f"Total Signals: {summary['total_signals']}")
        print(f"Completed Signals: {summary['completed_signals']}")
        print(f"Win Rate: {summary['win_rate']:.2f}%")
        print(f"Average Profit/Loss: {summary['avg_profit_loss']:.2f}%")
        print(f"Total Profit/Loss: {summary['total_profit_loss']:.2f}%")
        print(f"Maximum Profit: {summary['max_profit']:.2f}%")
        print(f"Maximum Loss: {summary['max_loss']:.2f}%")
        print(f"Average Holding Time: {summary['avg_holding_time']:.2f} hours")
        
        print(f"\nDetailed results saved to: data/backtest/{results['backtest_id']}.json")
    else:
        print("Backtest failed. Check logs for details.")

def list_backtests(args):
    """List all available backtests"""
    # Load configuration
    config = load_config()
    
    # Initialize API client (needed for historical data)
    api_client = MStockAPI(config)
    
    # Initialize historical data manager
    historical_manager = HistoricalDataManager(api_client, config)
    
    # Initialize backtest manager
    backtest_manager = BacktestManager(config, historical_manager)
    
    # Get backtest IDs
    backtest_ids = backtest_manager.get_backtest_results()
    
    if backtest_ids:
        print("\nAvailable Backtests:")
        for backtest_id in backtest_ids:
            print(f"- {backtest_id}")
    else:
        print("No backtests found.")

def show_backtest(args):
    """Show details of a specific backtest"""
    # Load configuration
    config = load_config()
    
    # Initialize API client (needed for historical data)
    api_client = MStockAPI(config)
    
    # Initialize historical data manager
    historical_manager = HistoricalDataManager(api_client, config)
    
    # Initialize backtest manager
    backtest_manager = BacktestManager(config, historical_manager)
    
    # Get backtest results
    results = backtest_manager.get_backtest_results(args.id)
    
    if results:
        # Print summary
        summary = results["summary"]
        print("\nBacktest Summary:")
        print(f"Backtest ID: {args.id}")
        print(f"Strategy: {results['strategy']}")
        print(f"Symbol: {results['symbol']}")
        print(f"Period: {results['start_date']} to {results['end_date']}")
        print(f"Total Signals: {summary['total_signals']}")
        print(f"Completed Signals: {summary['completed_signals']}")
        print(f"Win Rate: {summary['win_rate']:.2f}%")
        print(f"Average Profit/Loss: {summary['avg_profit_loss']:.2f}%")
        print(f"Total Profit/Loss: {summary['total_profit_loss']:.2f}%")
        print(f"Maximum Profit: {summary['max_profit']:.2f}%")
        print(f"Maximum Loss: {summary['max_loss']:.2f}%")
        print(f"Average Holding Time: {summary['avg_holding_time']:.2f} hours")
        
        # Print signals if requested
        if args.signals:
            print("\nSignals:")
            for i, signal in enumerate(results["signals"]):
                print(f"\nSignal {i+1}:")
                print(f"  Type: {signal['signal_type']}")
                print(f"  Entry Price: {signal['entry_price']}")
                print(f"  Stop Loss: {signal['stop_loss']}")
                print(f"  Target: {signal['target']}")
                print(f"  Status: {signal['status']}")
                if signal['status'] == "COMPLETED":
                    print(f"  Exit Price: {signal['exit_price']}")
                    print(f"  Exit Reason: {signal['exit_reason']}")
                    print(f"  Profit/Loss: {signal['profit_loss']:.2f}%")
    else:
        print(f"Backtest {args.id} not found.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MStock Strategy Backtester")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run backtest command
    run_parser = subparsers.add_parser("run", help="Run a backtest")
    run_parser.add_argument("--strategy", required=True, help="Strategy to backtest")
    run_parser.add_argument("--symbol", required=True, help="Symbol to backtest (e.g., NSE:INFY)")
    run_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    run_parser.add_argument("--id", help="Backtest ID (generated if not provided)")
    
    # List backtests command
    list_parser = subparsers.add_parser("list", help="List available backtests")
    
    # Show backtest command
    show_parser = subparsers.add_parser("show", help="Show backtest details")
    show_parser.add_argument("id", help="Backtest ID")
    show_parser.add_argument("--signals", action="store_true", help="Show signals")
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_backtest(args)
    elif args.command == "list":
        list_backtests(args)
    elif args.command == "show":
        show_backtest(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()