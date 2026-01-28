"""
AlphaStock AI Framework Configuration
"""

# AI Model Configuration
AI_CONFIG = {
    # Global AI settings
    "confidence_threshold": 0.85,
    "enable_ai_validation": True,
    "enable_risk_assessment": True,
    "enable_anomaly_detection": True,
    
    # Model training settings
    "training": {
        "min_samples": 100,
        "test_size": 0.2,
        "random_state": 42,
        "cross_validation_folds": 5
    },
    
    # Signal validation model
    "signal_validation": {
        "confidence_threshold": 0.85,
        "ensemble_models": ["random_forest", "xgboost"],
        "feature_selection": "auto",
        "hyperparameters": {
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5
            },
            "xgboost": {
                "n_estimators": 100,
                "max_depth": 6,
                "learning_rate": 0.1
            }
        }
    },
    
    # Risk assessment model
    "risk_assessment": {
        "confidence_threshold": 0.80,
        "risk_factors": ["volatility", "drawdown", "correlation"],
        "position_sizing": {
            "max_risk_per_trade": 0.02,
            "max_portfolio_risk": 0.10
        }
    },
    
    # Anomaly detection model
    "anomaly_detection": {
        "confidence_threshold": 0.90,
        "contamination": 0.1,
        "detection_method": "isolation_forest"
    },
    
    # Feature store configuration
    "feature_store": {
        "cache_enabled": True,
        "cache_ttl": 3600,  # 1 hour
        "default_lookback": 100,
        "feature_categories": {
            "technical": ["rsi", "macd", "bollinger", "stochastic"],
            "price": ["returns", "volatility", "momentum"],
            "volume": ["volume_ratio", "volume_trend"],
            "market": ["market_regime", "correlation"]
        }
    },
    
    # Model registry settings
    "model_registry": {
        "auto_versioning": True,
        "max_versions_per_model": 10,
        "performance_tracking": True,
        "model_validation": True
    },
    
    # Logging and monitoring
    "logging": {
        "level": "INFO",
        "ai_log_file": "logs/ai/ai_framework.log",
        "performance_log_file": "logs/ai/performance.log"
    }
}

# Feature definitions for the feature store
FEATURE_DEFINITIONS = {
    # Price-based features
    "price_change": {
        "description": "Price change from previous period",
        "category": "price",
        "window": 1
    },
    "returns": {
        "description": "Percentage returns",
        "category": "price", 
        "window": 1
    },
    "log_returns": {
        "description": "Logarithmic returns",
        "category": "price",
        "window": 1
    },
    "price_volatility": {
        "description": "Rolling price volatility",
        "category": "price",
        "window": 20
    },
    
    # Technical indicators
    "rsi_14": {
        "description": "14-period RSI",
        "category": "technical",
        "window": 14
    },
    "rsi_9": {
        "description": "9-period RSI", 
        "category": "technical",
        "window": 9
    },
    "macd": {
        "description": "MACD indicator",
        "category": "technical",
        "window": 26
    },
    "bollinger_position": {
        "description": "Position within Bollinger Bands",
        "category": "technical", 
        "window": 20
    },
    
    # Moving averages
    "sma_5": {"description": "5-period SMA", "category": "technical", "window": 5},
    "sma_10": {"description": "10-period SMA", "category": "technical", "window": 10},
    "sma_20": {"description": "20-period SMA", "category": "technical", "window": 20},
    "sma_50": {"description": "50-period SMA", "category": "technical", "window": 50},
    
    # Volume features
    "volume_ratio": {
        "description": "Volume to average ratio",
        "category": "volume",
        "window": 20
    },
    "volume_trend": {
        "description": "Volume trend indicator",
        "category": "volume",
        "window": 10
    }
}

# Export configuration
__all__ = ["AI_CONFIG", "FEATURE_DEFINITIONS"]
