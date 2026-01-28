"""
Strategy Factory for AlphaStock Trading System

This module provides a factory pattern implementation for creating strategy instances.
It manages strategy registration and instantiation in a centralized manner.
"""

import logging
from typing import Dict, Any, List, Optional

from ..utils.logger_setup import setup_logger

logger = setup_logger("strategy_factory")


class StrategyFactory:
    """
    Factory for creating and managing trading strategy instances.
    
    Provides centralized strategy registration and creation capabilities
    following the factory pattern for loose coupling and extensibility.
    """
    
    # Registry of available strategies
    STRATEGIES = {}
    
    @classmethod
    def register_strategy(cls, name: str, strategy_class):
        """
        Register a new strategy class.
        
        Args:
            name: Strategy name identifier
            strategy_class: Strategy class to register
        """
        cls.STRATEGIES[name] = strategy_class
        logger.info(f"Registered strategy: {name}")
    
    @classmethod
    def create_strategy(cls, strategy_name: str, config: Dict[str, Any]):
        """
        Create a strategy instance by name.
        
        Args:
            strategy_name: Name of the strategy to create
            config: Configuration dictionary for the strategy
            
        Returns:
            Strategy instance
            
        Raises:
            ValueError: If strategy name is not registered
        """
        if strategy_name not in cls.STRATEGIES:
            available = list(cls.STRATEGIES.keys())
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {available}")
        
        try:
            strategy_class = cls.STRATEGIES[strategy_name]
            strategy_instance = strategy_class(config)
            logger.info(f"Created strategy instance: {strategy_name}")
            return strategy_instance
            
        except Exception as e:
            logger.error(f"Error creating strategy {strategy_name}: {e}")
            raise
    
    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """
        Get list of available strategy names.
        
        Returns:
            List of registered strategy names
        """
        return list(cls.STRATEGIES.keys())
    
    @classmethod
    def get_strategy_info(cls, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Strategy information dictionary or None if not found
        """
        if strategy_name not in cls.STRATEGIES:
            return None
        
        strategy_class = cls.STRATEGIES[strategy_name]
        
        # Try to get strategy info from class attributes or docstring
        info = {
            'name': strategy_name,
            'class': strategy_class.__name__,
            'module': strategy_class.__module__,
            'description': strategy_class.__doc__ or 'No description available'
        }
        
        return info
    
    @classmethod
    def create_multiple_strategies(cls, strategy_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create multiple strategy instances from configuration.
        
        Args:
            strategy_configs: Dictionary of strategy name -> config mappings
            
        Returns:
            Dictionary of strategy name -> strategy instance mappings
        """
        strategies = {}
        errors = []
        
        for strategy_name, config in strategy_configs.items():
            if not config.get('enabled', False):
                logger.info(f"Skipping disabled strategy: {strategy_name}")
                continue
            
            try:
                strategy = cls.create_strategy(strategy_name, config)
                strategies[strategy_name] = strategy
            except Exception as e:
                error_msg = f"Failed to create strategy {strategy_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        if errors:
            logger.warning(f"Strategy creation completed with {len(errors)} errors")
        
        return strategies
    
    @classmethod
    def initialize_strategies_for_symbol(cls, symbol: str, config: Dict[str, Any]) -> List[Any]:
        """
        Initialize all applicable strategies for a specific symbol.
        
        Args:
            symbol: Trading symbol
            config: Complete configuration dictionary
            
        Returns:
            List of strategy instances applicable to the symbol
        """
        strategies = []
        strategy_configs = config.get('strategies', {})
        
        for strategy_name, strategy_config in strategy_configs.items():
            # Check if strategy is enabled
            if not strategy_config.get('enabled', False):
                continue
            
            # Check if symbol is in strategy's symbol list
            strategy_symbols = strategy_config.get('symbols', [])
            if strategy_symbols and symbol not in strategy_symbols:
                continue
            
            try:
                strategy = cls.create_strategy(strategy_name, strategy_config)
                strategies.append(strategy)
                logger.info(f"Initialized strategy {strategy_name} for symbol {symbol}")
            except Exception as e:
                logger.error(f"Failed to initialize strategy {strategy_name} for {symbol}: {e}")
        
        return strategies


# Auto-register built-in strategies
def _register_builtin_strategies():
    """Register all built-in strategies with the factory."""
    try:
        # Import and register MA Crossover Strategy
        from ..strategies.ma_crossover_strategy import MovingAverageCrossoverStrategy
        StrategyFactory.register_strategy('ma_crossover', MovingAverageCrossoverStrategy)
        
        # Import and register EMA 5 Alert Candle Strategy
        from ..strategies.ema_5_alert_candle_strategy import EMA5AlertCandleStrategy
        StrategyFactory.register_strategy('ema_5_alert_candle', EMA5AlertCandleStrategy)
        
        logger.info("Built-in strategies registered successfully")
        
    except Exception as e:
        logger.error(f"Error registering built-in strategies: {e}")


# Register strategies on module import
_register_builtin_strategies()
