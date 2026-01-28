#!/usr/bin/env python3
"""
AlphaStock Demo Script
Demonstrates the new specialized runner architecture.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from src.orchestrator import AlphaStockOrchestrator


async def demo_runners():
    """Demonstrate the specialized runners functionality."""
    print("=" * 60)
    print("AlphaStock Trading System - Specialized Runners Demo")
    print("=" * 60)
    
    # Initialize orchestrator
    orchestrator = AlphaStockOrchestrator()
    
    try:
        print("\n1. Initializing system components...")
        await orchestrator.initialize()
        print("✅ System initialized successfully")
        
        # Start the system briefly
        print("\n2. Starting runners for data collection...")
        
        # Create a background task to run the orchestrator
        orchestrator_task = asyncio.create_task(orchestrator.start())
        
        # Wait a bit for data to be collected
        await asyncio.sleep(10)
        
        print("\n3. Getting runner status...")
        runner_status = orchestrator.get_runner_status()
        print_runner_status(runner_status)
        
        print("\n4. Getting comprehensive market data...")
        market_data = orchestrator.get_comprehensive_market_data()
        print_market_summary(market_data)
        
        print("\n5. Identifying trading opportunities...")
        opportunities = orchestrator.get_trading_opportunities()
        print_opportunities(opportunities)
        
        print("\n6. Getting system status...")
        system_status = orchestrator.get_status()
        print_system_status(system_status)
        
        # Stop the orchestrator
        print("\n7. Stopping system...")
        orchestrator_task.cancel()
        await orchestrator.stop()
        print("✅ System stopped successfully")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        await orchestrator.stop()


def print_runner_status(status):
    """Print runner status in a formatted way."""
    print(f"Runner Manager Active: {status['runner_manager_active']}")
    print("\nIndividual Runners:")
    
    for runner_name, runner_info in status['runners'].items():
        print(f"  {runner_name.title()}:")
        print(f"    Active: {runner_info['active']}")
        print(f"    Symbols: {runner_info['symbols_count']}")
        print(f"    Last Update: {runner_info.get('last_update', 'Never')}")
        print(f"    Errors: {runner_info.get('error_count', 0)}")


def print_market_summary(market_data):
    """Print market data summary."""
    print("Market Data Summary:")
    
    # Equities
    if 'equities' in market_data and market_data['equities']:
        equity_summary = market_data['equities'].get('summary', {})
        print(f"  Equities: {equity_summary.get('active_stocks', 0)} active stocks")
        print(f"    Gainers: {equity_summary.get('gainers_count', 0)}")
        print(f"    Losers: {equity_summary.get('losers_count', 0)}")
    
    # Indices
    if 'indices' in market_data and market_data['indices']:
        indices_overview = market_data['indices'].get('overview', {})
        print(f"  Indices: Market sentiment - {indices_overview.get('market_sentiment', 'UNKNOWN')}")
        print(f"    Volatility: {indices_overview.get('volatility_level', 'UNKNOWN')}")
    
    # Commodities
    if 'commodities' in market_data and market_data['commodities']:
        commodity_summary = market_data['commodities'].get('summary', {})
        print(f"  Commodities: {commodity_summary.get('total_commodities', 0)} tracked")
        alerts = market_data['commodities'].get('alerts', [])
        print(f"    Active Alerts: {len(alerts)}")
    
    # Futures
    if 'futures' in market_data and market_data['futures']:
        futures_summary = market_data['futures'].get('summary', {})
        print(f"  Futures: {futures_summary.get('total_contracts', 0)} contracts")
        expiry_dist = futures_summary.get('expiry_distribution', {})
        close_expiry = expiry_dist.get('very_close', 0) + expiry_dist.get('close', 0)
        print(f"    Near Expiry: {close_expiry} contracts")


def print_opportunities(opportunities):
    """Print trading opportunities."""
    print("Trading Opportunities:")
    
    # High momentum
    high_momentum = opportunities.get('high_momentum', [])
    if high_momentum:
        print(f"  High Momentum ({len(high_momentum)} found):")
        for opp in high_momentum[:3]:  # Show top 3
            print(f"    {opp['symbol']}: +{opp['change_pct']:.2f}% ({opp['asset_type']})")
    
    # Commodity alerts
    commodity_alerts = opportunities.get('commodity_alerts', [])
    if commodity_alerts:
        print(f"  Commodity Alerts ({len(commodity_alerts)} active):")
        for alert in commodity_alerts[:3]:  # Show top 3
            print(f"    {alert['symbol']}: {alert['message']} ({alert['severity']})")
    
    # Futures rollover
    futures_rollover = opportunities.get('futures_rollover', [])
    if futures_rollover:
        print(f"  Futures Rollover ({len(futures_rollover)} recommendations):")
        for rollover in futures_rollover[:3]:
            print(f"    {rollover['symbol']}: {rollover['action']}")


def print_system_status(status):
    """Print system status."""
    print("System Status:")
    print(f"  Uptime: {status.get('uptime', 'Unknown')}")
    print(f"  Strategies Executed: {status.get('strategies_executed', 0)}")
    print(f"  Signals Generated: {status.get('signals_generated', 0)}")
    print(f"  API Calls: {status.get('api_calls', 0)}")
    print(f"  Errors: {status.get('errors', 0)}")
    print(f"  Cache Size: {status.get('cache_size', 0)}")


def print_system_architecture():
    """Print the system architecture overview."""
    print("\n" + "=" * 60)
    print("ALPHASTOCK SYSTEM ARCHITECTURE")
    print("=" * 60)
    
    architecture = """
┌─────────────────────────────────────────────────────────────┐
│                    AlphaStock Orchestrator                 │
│                 (Main Coordination Layer)                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          v               v               v
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Kite API Client│ │ Strategy Factory│ │  Signal Manager │
│                 │ │                 │ │                 │
│ • Authentication│ │ • MA Crossover  │ │ • Signal Queue  │
│ • Rate Limiting │ │ • Mean Reversion│ │ • Risk Checks   │
│ • Paper Trading │ │ • Breakout      │ │ • Order Mgmt    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │
          v
┌─────────────────────────────────────────────────────────────┐
│                     Runner Manager                         │
│                  (Coordinates All Runners)                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    v                 v                 v
┌─────────┐    ┌─────────────┐    ┌─────────────┐
│ Equity  │    │   Options   │    │    Index    │
│ Runner  │    │   Runner    │    │   Runner    │
│         │    │             │    │             │
│• OHLC   │    │• Greeks     │    │• Nifty 50   │
│• Volume │    │• Chains     │    │• Bank Nifty │
│• Sectors│    │• Strategies │    │• Sectoral   │
└─────────┘    └─────────────┘    └─────────────┘

┌─────────────┐              ┌─────────────┐
│ Commodity   │              │   Futures   │
│   Runner    │              │   Runner    │
│             │              │             │
│• Precious   │              │• Index Fut  │
│• Energy     │              │• Stock Fut  │
│• Seasonality│              │• Expiry Mgmt│
└─────────────┘              └─────────────┘
"""
    
    print(architecture)
    
    features = """
KEY FEATURES:
• Specialized Runners: Each asset type has dedicated processing logic
• Real-time Data: Continuous market data collection and analysis
• Strategy Support: Multiple trading strategies across asset classes
• Risk Management: Built-in position sizing and risk controls
• Paper Trading: Safe testing environment before live trading
• Comprehensive Monitoring: System health and performance tracking

SUPPORTED INSTRUMENTS:
• Equities: NSE/BSE listed stocks with sector analysis
• Options: CE/PE contracts with Greeks calculation
• Indices: Market indices with correlation analysis
• Commodities: Precious metals, energy, agricultural products
• Futures: All futures contracts with rollover management
"""
    
    print(features)


async def main():
    """Main demo function."""
    print_system_architecture()
    
    print("\n" + "=" * 60)
    print("LIVE SYSTEM DEMONSTRATION")
    print("=" * 60)
    
    response = input("\nWould you like to run a live demo with real data? (y/N): ")
    if response.lower() in ['y', 'yes']:
        await demo_runners()
    else:
        print("\nDemo skipped. Architecture overview completed.")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("1. Set up your Kite API credentials in .env.dev")
    print("2. Configure your symbols in config/production.json")
    print("3. Run: python src/orchestrator.py")
    print("4. Monitor your strategies and signals")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo error: {e}")
