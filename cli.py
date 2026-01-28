#!/usr/bin/env python3
"""
AlphaStock CLI - Command Line Interface
Simple CLI for interacting with the AlphaStock trading system.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Optional

import click
from tabulate import tabulate

from src.api_wrapper import AlphaStockAPI
from src.utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class AlphaStockCLI:
    """Command line interface for AlphaStock."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/production.json"
        self.api = AlphaStockAPI(self.config_path)
        self._running = False
    
    async def initialize(self):
        """Initialize the API."""
        await self.api.initialize()
        click.echo("✅ AlphaStock CLI initialized")
    
    async def start_system(self):
        """Start the trading system."""
        click.echo("🚀 Starting AlphaStock trading system...")
        await self.api.start_system()
        click.echo("✅ Trading system started")
    
    async def stop_system(self):
        """Stop the trading system."""
        click.echo("🛑 Stopping trading system...")
        await self.api.stop_system()
        click.echo("✅ Trading system stopped")
    
    def show_status(self):
        """Display system status."""
        try:
            status = self.api.get_system_status()
            
            # System overview
            click.echo("\n📊 System Status")
            click.echo("=" * 50)
            
            status_color = "green" if status.running else "red"
            status_text = "RUNNING" if status.running else "STOPPED"
            
            click.echo(f"Status: {click.style(status_text, fg=status_color, bold=True)}")
            click.echo(f"Uptime: {status.uptime_seconds / 3600:.1f} hours")
            click.echo(f"Market Open: {'Yes' if status.market_open else 'No'}")
            click.echo(f"Total Signals: {status.total_signals}")
            click.echo(f"Executions: {status.total_executions}")
            click.echo(f"Errors: {status.errors}")
            
            # Strategy status
            if status.strategies:
                click.echo(f"\n📈 Active Strategies ({len(status.strategies)})")
                click.echo("-" * 50)
                
                strategy_data = []
                for strategy in status.strategies:
                    last_exec = "Never"
                    if strategy.last_execution:
                        last_exec = datetime.fromisoformat(strategy.last_execution).strftime("%H:%M:%S")
                    
                    strategy_data.append([
                        strategy.name,
                        "✅" if strategy.enabled else "❌",
                        len(strategy.symbols),
                        strategy.signals_generated,
                        last_exec
                    ])
                
                headers = ["Strategy", "Enabled", "Symbols", "Signals", "Last Run"]
                click.echo(tabulate(strategy_data, headers=headers, tablefmt="grid"))
            
        except Exception as e:
            click.echo(f"❌ Error getting status: {e}")
    
    def show_signals(self, symbol: Optional[str] = None, strategy: Optional[str] = None, limit: int = 20):
        """Display recent signals."""
        try:
            signals = self.api.get_latest_signals(symbol=symbol, strategy=strategy, limit=limit)
            
            if not signals:
                click.echo("📭 No signals found")
                return
            
            click.echo(f"\n📡 Recent Signals ({len(signals)})")
            click.echo("=" * 80)
            
            signal_data = []
            for signal in signals:
                timestamp = datetime.fromisoformat(signal.timestamp).strftime("%H:%M:%S")
                
                # Color code actions
                action_color = "green" if signal.action == "BUY" else "red" if signal.action == "SELL" else "yellow"
                action_text = click.style(signal.action, fg=action_color, bold=True)
                
                signal_data.append([
                    timestamp,
                    signal.symbol,
                    signal.strategy,
                    action_text,
                    f"{signal.price:.2f}",
                    f"{signal.confidence:.2f}"
                ])
            
            headers = ["Time", "Symbol", "Strategy", "Action", "Price", "Confidence"]
            click.echo(tabulate(signal_data, headers=headers, tablefmt="grid"))
            
        except Exception as e:
            click.echo(f"❌ Error getting signals: {e}")
    
    def show_performance(self, strategy: str, days: int = 7):
        """Show strategy performance."""
        try:
            perf = self.api.get_strategy_performance(strategy, days)
            
            if "error" in perf:
                click.echo(f"❌ {perf['error']}")
                return
            
            click.echo(f"\n📈 Performance: {strategy} (Last {days} days)")
            click.echo("=" * 60)
            click.echo(f"Total Signals: {perf['total_signals']}")
            click.echo(f"Buy Signals: {perf['buy_signals']}")
            click.echo(f"Sell Signals: {perf['sell_signals']}")
            click.echo(f"Average Confidence: {perf['avg_confidence']}")
            click.echo(f"Active Symbols: {perf['symbols_active']}")
            
            if perf.get('symbol_breakdown'):
                click.echo(f"\n📊 Symbol Breakdown:")
                for symbol, data in perf['symbol_breakdown'].items():
                    click.echo(f"  {symbol}: {data['count']} signals")
            
        except Exception as e:
            click.echo(f"❌ Error getting performance: {e}")
    
    def show_summary(self):
        """Show quick system summary."""
        try:
            summary = self.api.get_quick_status()
            
            if "error" in summary:
                click.echo(f"❌ {summary['error']}")
                return
            
            click.echo(f"\n⚡ Quick Summary")
            click.echo("=" * 40)
            
            status_color = "green" if summary["system_running"] else "red"
            status_text = "RUNNING" if summary["system_running"] else "STOPPED"
            
            click.echo(f"System: {click.style(status_text, fg=status_color, bold=True)}")
            click.echo(f"Uptime: {summary['uptime_hours']:.1f}h")
            click.echo(f"Signals Today: {summary['total_signals_today']}")
            click.echo(f"Strategies: {summary['active_strategies']}")
            click.echo(f"Errors: {summary['errors']}")
            
            if summary.get('latest_signals'):
                click.echo(f"\n🎯 Last 3 Signals:")
                for signal in summary['latest_signals'][:3]:
                    action_color = "green" if signal['action'] == "BUY" else "red"
                    action = click.style(signal['action'], fg=action_color, bold=True)
                    click.echo(f"  {signal['symbol']}: {action} @ {signal['price']:.2f}")
            
        except Exception as e:
            click.echo(f"❌ Error getting summary: {e}")
    
    async def monitor(self, refresh_seconds: int = 30):
        """Monitor the system with live updates."""
        click.echo(f"🔍 Monitoring system (refreshing every {refresh_seconds}s)")
        click.echo("Press Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                # Clear screen
                click.clear()
                
                # Show header with timestamp
                now = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                click.echo(f"🚀 AlphaStock Monitor - {now}")
                
                # Show summary
                self.show_summary()
                
                # Show recent signals
                self.show_signals(limit=5)
                
                # Wait for next refresh
                await asyncio.sleep(refresh_seconds)
                
        except KeyboardInterrupt:
            click.echo("\n👋 Monitoring stopped")


# CLI Commands

@click.group()
@click.option('--config', '-c', help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """AlphaStock Trading System CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        cli_obj.show_status()
    
    asyncio.run(run())


@cli.command()
@click.option('--symbol', '-s', help='Filter by symbol')
@click.option('--strategy', help='Filter by strategy')
@click.option('--limit', '-l', default=20, help='Number of signals to show')
@click.pass_context
def signals(ctx, symbol, strategy, limit):
    """Show recent signals"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        cli_obj.show_signals(symbol=symbol, strategy=strategy, limit=limit)
    
    asyncio.run(run())


@cli.command()
@click.argument('strategy')
@click.option('--days', '-d', default=7, help='Number of days to analyze')
@click.pass_context
def performance(ctx, strategy, days):
    """Show strategy performance"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        cli_obj.show_performance(strategy, days)
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def summary(ctx):
    """Show quick system summary"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        cli_obj.show_summary()
    
    asyncio.run(run())


@cli.command()
@click.option('--refresh', '-r', default=30, help='Refresh interval in seconds')
@click.pass_context
def monitor(ctx, refresh):
    """Monitor system with live updates"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        await cli_obj.monitor(refresh)
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def start(ctx):
    """Start the trading system"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        await cli_obj.start_system()
        
        # Keep running until interrupted
        try:
            click.echo("System is running. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await cli_obj.stop_system()
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def stop(ctx):
    """Stop the trading system"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        await cli_obj.stop_system()
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def strategies(ctx):
    """List available strategies"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        
        available = cli_obj.api.list_available_strategies()
        
        click.echo("\n📈 Available Strategies")
        click.echo("=" * 40)
        
        for strategy in available:
            config = cli_obj.api.get_strategy_config(strategy)
            status = "✅ Enabled" if config and config.get("enabled") else "❌ Disabled"
            click.echo(f"{strategy}: {status}")
    
    asyncio.run(run())


@cli.command()
@click.argument('query')
@click.option('--field', default='symbol', help='Field to search in (symbol, strategy, action)')
@click.pass_context
def search(ctx, query, field):
    """Search signals"""
    async def run():
        cli_obj = AlphaStockCLI(ctx.obj['config'])
        await cli_obj.initialize()
        
        results = cli_obj.api.search_signals(query, field)
        
        if not results:
            click.echo(f"🔍 No results found for '{query}' in {field}")
            return
        
        click.echo(f"\n🔍 Search Results: '{query}' in {field} ({len(results)} found)")
        cli_obj.show_signals()  # This will show the results from the search
    
    asyncio.run(run())


@cli.command()
@click.option('--validate-only', is_flag=True, help='Only validate existing token')
@click.pass_context
def auth(ctx, validate_only):
    """Authenticate with Kite Connect (integrated OAuth flow)"""
    async def run():
        from src.auth import get_auth_manager
        
        click.echo("🔑 Kite Connect Authentication")
        click.echo("=" * 60)
        
        auth_manager = get_auth_manager()
        
        if validate_only:
            # Just validate existing token
            if await auth_manager.ensure_authenticated(interactive=False):
                profile = auth_manager.get_profile()
                if profile:
                    click.echo(f"\n✅ Token is valid")
                    click.echo(f"   User: {profile.get('user_name', 'Unknown')}")
                    click.echo(f"   Email: {profile.get('email', 'Unknown')}")
                    click.echo(f"   User ID: {profile.get('user_id', 'Unknown')}")
                else:
                    click.echo("\n❌ Token validation failed")
            else:
                click.echo("\n❌ Not authenticated. Run without --validate-only to authenticate")
        else:
            # Full authentication flow
            if await auth_manager.ensure_authenticated(interactive=True):
                click.echo("\n✅ Authentication successful! You can now run the trading system.")
            else:
                click.echo("\n❌ Authentication failed. Please check your credentials.")
    
    asyncio.run(run())


if __name__ == '__main__':
    cli()
