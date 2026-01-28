"""
AlphaStock API Wrapper
Simple API interface for consuming trading signals and system status.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict

from src.orchestrator import AlphaStockOrchestrator
from src.utils.logger_setup import setup_logger
from src.utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


@dataclass
class SignalResponse:
    """Response object for trading signals."""
    symbol: str
    strategy: str
    action: str  # BUY, SELL, HOLD
    price: float
    confidence: float
    timestamp: str
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StrategyStatus:
    """Status of a trading strategy."""
    name: str
    enabled: bool
    symbols: List[str]
    signals_generated: int
    last_execution: Optional[str]
    parameters: Dict[str, Any]


@dataclass
class SystemStatus:
    """Overall system status."""
    running: bool
    uptime_seconds: float
    market_open: bool
    total_signals: int
    total_executions: int
    errors: int
    strategies: List[StrategyStatus]


class AlphaStockAPI:
    """
    Main API wrapper for AlphaStock trading system.
    
    This class provides a clean, simple interface for:
    - Getting trading signals
    - Checking system status
    - Managing strategies
    - Retrieving historical data
    """
    
    def __init__(self, config_path: str = None):
        """Initialize the API wrapper."""
        self.orchestrator = AlphaStockOrchestrator(config_path)
        self.logger = setup_logger(name="AlphaStockAPI", level="INFO")
        self._initialized = False
        
        # Cache for recent signals
        self._signal_cache: List[SignalResponse] = []
        self._max_cache_size = 1000
        
        self.logger.info("AlphaStock API initialized")
    
    async def initialize(self):
        """Initialize the underlying orchestrator."""
        if not self._initialized:
            await self.orchestrator.initialize()
            self._initialized = True
            self.logger.info("API ready for requests")
    
    async def start_system(self):
        """Start the trading system."""
        if not self._initialized:
            await self.initialize()
        
        # Start orchestrator in background task
        asyncio.create_task(self.orchestrator.start())
        self.logger.info("Trading system started")
    
    async def stop_system(self):
        """Stop the trading system."""
        await self.orchestrator.stop()
        self.logger.info("Trading system stopped")
    
    # Signal Management
    
    def get_latest_signals(self, 
                          symbol: Optional[str] = None,
                          strategy: Optional[str] = None,
                          limit: int = 50,
                          since_minutes: Optional[int] = None) -> List[SignalResponse]:
        """
        Get latest trading signals with optional filtering.
        
        Args:
            symbol: Filter by symbol (e.g., "BANKNIFTY", "NSE:SBIN")
            strategy: Filter by strategy name (e.g., "ma_crossover")
            limit: Maximum number of signals to return
            since_minutes: Only return signals from last N minutes
        
        Returns:
            List of SignalResponse objects
        """
        try:
            signals = self._signal_cache.copy()
            
            # Apply filters
            if symbol:
                signals = [s for s in signals if s.symbol == symbol]
            
            if strategy:
                signals = [s for s in signals if s.strategy == strategy]
            
            if since_minutes:
                cutoff_time = get_current_time() - timedelta(minutes=since_minutes)
                signals = [
                    s for s in signals 
                    if datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff_time
                ]
            
            # Sort by timestamp (newest first) and limit
            signals.sort(key=lambda x: x.timestamp, reverse=True)
            return signals[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting signals: {e}")
            return []
    
    def get_signal_by_id(self, signal_id: str) -> Optional[SignalResponse]:
        """Get a specific signal by ID."""
        # In a real implementation, you might store signals with unique IDs
        # For now, we'll use timestamp as a simple identifier
        for signal in self._signal_cache:
            if signal.timestamp == signal_id:
                return signal
        return None
    
    def get_signals_summary(self, 
                           groupby: str = "symbol",
                           since_hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics of signals.
        
        Args:
            groupby: Group signals by "symbol", "strategy", or "action"
            since_hours: Look at signals from last N hours
        
        Returns:
            Dictionary with summary statistics
        """
        try:
            cutoff_time = get_current_time() - timedelta(hours=since_hours)
            recent_signals = [
                s for s in self._signal_cache
                if datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff_time
            ]
            
            summary = {}
            
            for signal in recent_signals:
                if groupby == "symbol":
                    key = signal.symbol
                elif groupby == "strategy":
                    key = signal.strategy
                elif groupby == "action":
                    key = signal.action
                else:
                    key = "all"
                
                if key not in summary:
                    summary[key] = {
                        "total_signals": 0,
                        "buy_signals": 0,
                        "sell_signals": 0,
                        "avg_confidence": 0.0,
                        "last_signal": None
                    }
                
                summary[key]["total_signals"] += 1
                if signal.action == "BUY":
                    summary[key]["buy_signals"] += 1
                elif signal.action == "SELL":
                    summary[key]["sell_signals"] += 1
                
                summary[key]["last_signal"] = signal.timestamp
            
            # Calculate average confidence
            for key in summary:
                key_signals = [s for s in recent_signals if getattr(s, groupby.replace("action", "action")) == key]
                if key_signals:
                    summary[key]["avg_confidence"] = sum(s.confidence for s in key_signals) / len(key_signals)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating signals summary: {e}")
            return {}
    
    # System Status
    
    def get_system_status(self) -> SystemStatus:
        """Get current system status."""
        try:
            orchestrator_status = self.orchestrator.get_status()
            
            # Convert strategy info to StrategyStatus objects
            strategies = []
            for name, info in orchestrator_status.get("active_strategies", {}).items():
                strategy_config = self.orchestrator.active_strategies[name]["config"]
                strategies.append(StrategyStatus(
                    name=name,
                    enabled=strategy_config.get("enabled", False),
                    symbols=info["symbols"],
                    signals_generated=info["signals_count"],
                    last_execution=info["last_execution"],
                    parameters=strategy_config.get("parameters", {})
                ))
            
            return SystemStatus(
                running=orchestrator_status["running"],
                uptime_seconds=orchestrator_status["uptime_seconds"],
                market_open=True,  # You might want to implement actual market hours check
                total_signals=orchestrator_status["statistics"]["signals_generated"],
                total_executions=orchestrator_status["statistics"]["strategies_executed"],
                errors=orchestrator_status["statistics"]["errors"],
                strategies=strategies
            )
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return SystemStatus(
                running=False,
                uptime_seconds=0,
                market_open=False,
                total_signals=0,
                total_executions=0,
                errors=1,
                strategies=[]
            )
    
    def get_strategy_performance(self, strategy_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get performance metrics for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            days: Number of days to look back
        
        Returns:
            Performance metrics dictionary
        """
        try:
            # Filter signals for this strategy
            cutoff_time = get_current_time() - timedelta(days=days)
            strategy_signals = [
                s for s in self._signal_cache
                if s.strategy == strategy_name and 
                datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff_time
            ]
            
            if not strategy_signals:
                return {"error": "No signals found for strategy"}
            
            # Calculate metrics
            total_signals = len(strategy_signals)
            buy_signals = len([s for s in strategy_signals if s.action == "BUY"])
            sell_signals = len([s for s in strategy_signals if s.action == "SELL"])
            avg_confidence = sum(s.confidence for s in strategy_signals) / total_signals
            
            # Group by symbol
            symbols = {}
            for signal in strategy_signals:
                if signal.symbol not in symbols:
                    symbols[signal.symbol] = {"count": 0, "avg_confidence": 0}
                symbols[signal.symbol]["count"] += 1
            
            return {
                "strategy": strategy_name,
                "period_days": days,
                "total_signals": total_signals,
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "avg_confidence": round(avg_confidence, 3),
                "symbols_active": len(symbols),
                "symbol_breakdown": symbols
            }
            
        except Exception as e:
            self.logger.error(f"Error getting strategy performance: {e}")
            return {"error": str(e)}
    
    # Strategy Management
    
    def list_available_strategies(self) -> List[str]:
        """List all available strategy types."""
        return list(self.orchestrator.strategy_factory.strategies.keys())
    
    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific strategy."""
        strategies_config = self.orchestrator.config.get("strategies", {})
        return strategies_config.get(strategy_name)
    
    async def enable_strategy(self, strategy_name: str, symbols: List[str], parameters: Dict[str, Any]) -> bool:
        """
        Enable a strategy for specific symbols.
        
        Args:
            strategy_name: Name of the strategy to enable
            symbols: List of symbols to run the strategy on
            parameters: Strategy parameters
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update configuration
            if "strategies" not in self.orchestrator.config:
                self.orchestrator.config["strategies"] = {}
            
            self.orchestrator.config["strategies"][strategy_name] = {
                "enabled": True,
                "symbols": symbols,
                "parameters": parameters
            }
            
            # Initialize the strategy
            await self.orchestrator._initialize_strategy(strategy_name, {
                "enabled": True,
                "symbols": symbols,
                "parameters": parameters
            })
            
            self.logger.info(f"Strategy {strategy_name} enabled for symbols: {symbols}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error enabling strategy {strategy_name}: {e}")
            return False
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """Disable a strategy."""
        try:
            if strategy_name in self.orchestrator.active_strategies:
                del self.orchestrator.active_strategies[strategy_name]
            
            if strategy_name in self.orchestrator.config.get("strategies", {}):
                self.orchestrator.config["strategies"][strategy_name]["enabled"] = False
            
            self.logger.info(f"Strategy {strategy_name} disabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disabling strategy {strategy_name}: {e}")
            return False
    
    # Market Data
    
    def get_latest_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest market data for a symbol."""
        try:
            data = self.orchestrator.data_cache.get(f"market_data:{symbol}")
            if data is not None and hasattr(data, 'to_dict'):
                return data.tail(1).to_dict('records')[0]
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    def get_historical_data(self, 
                           symbol: str, 
                           days: int = 30, 
                           granularity: str = "15minute") -> Optional[List[Dict[str, Any]]]:
        """
        Get historical market data for a symbol.
        
        Args:
            symbol: Symbol to get data for
            days: Number of days of history
            granularity: Data granularity (1minute, 5minute, 15minute, 1hour, 1day)
        
        Returns:
            List of OHLCV dictionaries
        """
        try:
            # This would typically fetch from your data store or API
            # For now, return cached data if available
            cache_key = f"historical:{symbol}:{days}:{granularity}"
            data = self.orchestrator.data_cache.get(cache_key)
            
            if data is not None and hasattr(data, 'to_dict'):
                return data.to_dict('records')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return None
    
    # Convenience Methods
    
    def get_quick_status(self) -> Dict[str, Any]:
        """Get a quick system overview."""
        try:
            status = self.get_system_status()
            latest_signals = self.get_latest_signals(limit=5)
            
            return {
                "system_running": status.running,
                "uptime_hours": round(status.uptime_seconds / 3600, 1),
                "total_signals_today": status.total_signals,
                "active_strategies": len(status.strategies),
                "latest_signals": [asdict(s) for s in latest_signals],
                "errors": status.errors
            }
            
        except Exception as e:
            self.logger.error(f"Error getting quick status: {e}")
            return {"error": str(e)}
    
    def search_signals(self, 
                      query: str,
                      field: str = "symbol") -> List[SignalResponse]:
        """
        Search signals by various criteria.
        
        Args:
            query: Search query
            field: Field to search in ("symbol", "strategy", "action")
        
        Returns:
            Matching signals
        """
        try:
            query = query.upper()
            results = []
            
            for signal in self._signal_cache:
                field_value = getattr(signal, field, "").upper()
                if query in field_value:
                    results.append(signal)
            
            return sorted(results, key=lambda x: x.timestamp, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error searching signals: {e}")
            return []
    
    # Internal methods for signal management
    
    def _add_signal_to_cache(self, signal: SignalResponse):
        """Add a signal to the internal cache."""
        self._signal_cache.append(signal)
        
        # Maintain cache size
        if len(self._signal_cache) > self._max_cache_size:
            self._signal_cache = self._signal_cache[-self._max_cache_size:]
    
    def _convert_to_signal_response(self, 
                                  strategy: str, 
                                  symbol: str, 
                                  raw_signal) -> SignalResponse:
        """Convert internal signal format to SignalResponse."""
        return SignalResponse(
            symbol=symbol,
            strategy=strategy,
            action=raw_signal.action,
            price=raw_signal.price,
            confidence=raw_signal.confidence,
            timestamp=get_current_time().isoformat(),
            target=getattr(raw_signal, 'target', None),
            stop_loss=getattr(raw_signal, 'stop_loss', None),
            metadata=getattr(raw_signal, 'metadata', None)
        )


# Example usage functions

def create_simple_client(config_path: str = None) -> AlphaStockAPI:
    """Create a simple API client instance."""
    return AlphaStockAPI(config_path)


async def example_usage():
    """Example of how to use the API."""
    # Create API client
    api = AlphaStockAPI("config/production.json")
    
    try:
        # Initialize and start
        await api.initialize()
        await api.start_system()
        
        # Wait a bit for data collection
        await asyncio.sleep(10)
        
        # Get system status
        status = api.get_system_status()
        print(f"System running: {status.running}")
        print(f"Active strategies: {len(status.strategies)}")
        
        # Get latest signals
        signals = api.get_latest_signals(limit=10)
        print(f"Latest {len(signals)} signals:")
        for signal in signals:
            print(f"  {signal.symbol}: {signal.action} at {signal.price}")
        
        # Get performance for a strategy
        perf = api.get_strategy_performance("ma_crossover", days=1)
        print(f"MA Crossover performance: {perf}")
        
    finally:
        await api.stop_system()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
