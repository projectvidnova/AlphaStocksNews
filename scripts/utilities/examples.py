#!/usr/bin/env python3
"""
AlphaStock API Usage Examples
This script demonstrates how to use the AlphaStock API wrapper.
"""

import asyncio
import json
import time
from datetime import datetime
from src.api_wrapper import AlphaStockAPI


async def example_basic_usage():
    """Basic usage example."""
    print("🚀 AlphaStock API - Basic Usage Example")
    print("=" * 50)
    
    # Create API client
    api = AlphaStockAPI("config/production.json")
    
    try:
        # Initialize the API
        print("Initializing API...")
        await api.initialize()
        print("✅ API initialized")
        
        # Start the system (this runs the orchestrator in background)
        print("Starting trading system...")
        await api.start_system()
        print("✅ System started")
        
        # Wait a moment for the system to collect some data
        print("Waiting for system to collect data...")
        await asyncio.sleep(15)
        
        # Get system status
        print("\n📊 System Status:")
        status = api.get_system_status()
        print(f"  Running: {status.running}")
        print(f"  Uptime: {status.uptime_seconds:.1f} seconds")
        print(f"  Active Strategies: {len(status.strategies)}")
        print(f"  Total Signals: {status.total_signals}")
        
        # List strategies
        print(f"\n📈 Strategy Details:")
        for strategy in status.strategies:
            print(f"  {strategy.name}:")
            print(f"    Enabled: {strategy.enabled}")
            print(f"    Symbols: {strategy.symbols}")
            print(f"    Signals Generated: {strategy.signals_generated}")
        
        # Get latest signals
        print(f"\n📡 Latest Signals:")
        signals = api.get_latest_signals(limit=5)
        if signals:
            for signal in signals:
                print(f"  {signal.timestamp}: {signal.symbol} - {signal.action} @ {signal.price:.2f} (confidence: {signal.confidence:.2f})")
        else:
            print("  No signals yet")
        
        # Get quick status
        print(f"\n⚡ Quick Summary:")
        quick_status = api.get_quick_status()
        for key, value in quick_status.items():
            if key != "latest_signals":
                print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Stop the system
        print(f"\n🛑 Stopping system...")
        await api.stop_system()
        print("✅ System stopped")


async def example_strategy_management():
    """Example of managing strategies."""
    print("\n🔧 Strategy Management Example")
    print("=" * 50)
    
    api = AlphaStockAPI("config/production.json")
    
    try:
        await api.initialize()
        
        # List available strategies
        available = api.list_available_strategies()
        print(f"Available strategies: {available}")
        
        # Get configuration for a specific strategy
        config = api.get_strategy_config("ma_crossover")
        print(f"MA Crossover config: {json.dumps(config, indent=2)}")
        
        # Enable a new strategy (example)
        success = await api.enable_strategy(
            strategy_name="ma_crossover",
            symbols=["BANKNIFTY"],
            parameters={
                "fast_period": 5,
                "slow_period": 10,
                "ma_type": "SMA"
            }
        )
        print(f"Strategy enabled: {success}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def example_signal_analysis():
    """Example of analyzing signals."""
    print("\n📊 Signal Analysis Example")
    print("=" * 50)
    
    api = AlphaStockAPI("config/production.json")
    
    try:
        await api.initialize()
        await api.start_system()
        
        # Wait for some signals to be generated
        print("Waiting for signals to be generated...")
        await asyncio.sleep(30)
        
        # Get signals summary
        summary = api.get_signals_summary(groupby="symbol", since_hours=1)
        print("Signals by symbol:")
        for symbol, stats in summary.items():
            print(f"  {symbol}: {stats['total_signals']} total, {stats['buy_signals']} buy, {stats['sell_signals']} sell")
        
        # Get strategy performance
        perf = api.get_strategy_performance("ma_crossover", days=1)
        if "error" not in perf:
            print(f"\nMA Crossover Performance (1 day):")
            print(f"  Total signals: {perf['total_signals']}")
            print(f"  Average confidence: {perf['avg_confidence']}")
        
        # Search for specific signals
        bank_nifty_signals = api.search_signals("BANKNIFTY", field="symbol")
        print(f"\nBANKNIFTY signals found: {len(bank_nifty_signals)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await api.stop_system()


async def example_market_data():
    """Example of accessing market data."""
    print("\n📈 Market Data Example")
    print("=" * 50)
    
    api = AlphaStockAPI("config/production.json")
    
    try:
        await api.initialize()
        await api.start_system()
        
        # Wait for data collection
        await asyncio.sleep(10)
        
        # Get latest market data
        symbols = ["BANKNIFTY", "NSE:SBIN"]
        for symbol in symbols:
            data = api.get_latest_market_data(symbol)
            if data:
                print(f"{symbol} latest: Open={data.get('open', 'N/A')}, Close={data.get('close', 'N/A')}")
            else:
                print(f"{symbol}: No data available")
        
        # Get historical data (if available)
        historical = api.get_historical_data("BANKNIFTY", days=1)
        if historical:
            print(f"Historical data points: {len(historical)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await api.stop_system()


async def example_monitoring():
    """Example of monitoring the system."""
    print("\n🔍 Monitoring Example")
    print("=" * 50)
    
    api = AlphaStockAPI("config/production.json")
    
    try:
        await api.initialize()
        await api.start_system()
        
        # Monitor for 2 minutes
        end_time = time.time() + 120  # 2 minutes
        
        while time.time() < end_time:
            # Get quick status
            status = api.get_quick_status()
            
            print(f"\r⏰ {datetime.now().strftime('%H:%M:%S')} - "
                  f"Running: {status.get('system_running', False)}, "
                  f"Signals: {status.get('total_signals_today', 0)}, "
                  f"Errors: {status.get('errors', 0)}", end="")
            
            await asyncio.sleep(5)
        
        print("\n✅ Monitoring complete")
        
    except KeyboardInterrupt:
        print("\n🛑 Monitoring interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        await api.stop_system()


async def main():
    """Run all examples."""
    print("🚀 AlphaStock API Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Usage", example_basic_usage),
        ("Strategy Management", example_strategy_management),
        ("Signal Analysis", example_signal_analysis),
        ("Market Data", example_market_data),
        ("Monitoring", example_monitoring)
    ]
    
    for name, example_func in examples:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            await example_func()
        except KeyboardInterrupt:
            print("\n🛑 Example interrupted by user")
            break
        except Exception as e:
            print(f"❌ Example failed: {e}")
        
        # Small pause between examples
        await asyncio.sleep(2)
    
    print(f"\n🎉 Examples completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
