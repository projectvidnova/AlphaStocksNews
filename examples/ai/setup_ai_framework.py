#!/usr/bin/env python3
"""
AlphaStock AI Framework Setup
Installs dependencies and configures the AI framework for production use
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_setup")


def run_command(command, check=True):
    """Run a shell command and return the result."""
    logger.info(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=check, 
                              capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout.strip())
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if e.stderr:
            logger.error(e.stderr.strip())
        return False


def check_python_version():
    """Check if Python version is compatible."""
    logger.info("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error("❌ Python 3.8+ required. Current version: {}.{}.{}".format(
            version.major, version.minor, version.micro))
        return False
    
    logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def create_virtual_environment():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path(".venv")
    
    if venv_path.exists():
        logger.info("✅ Virtual environment already exists")
        return True
    
    logger.info("📦 Creating virtual environment...")
    
    if not run_command(f"{sys.executable} -m venv .venv"):
        logger.error("❌ Failed to create virtual environment")
        return False
    
    logger.info("✅ Virtual environment created")
    return True


def install_ai_dependencies():
    """Install AI/ML dependencies."""
    logger.info("📦 Installing AI/ML dependencies...")
    
    # Core ML packages
    packages = [
        "scikit-learn>=1.3.0",
        "xgboost>=1.7.0", 
        "numpy>=1.21.0",
        "pandas>=1.5.0",
        "joblib>=1.2.0"
    ]
    
    # Optional advanced packages
    optional_packages = [
        "lightgbm>=3.3.0",
        "catboost>=1.2.0",
        "optuna>=3.0.0",  # Hyperparameter optimization
        "shap>=0.41.0",   # Model explainability
        "plotly>=5.0.0",  # Visualization
        "dash>=2.10.0",   # Dashboard
    ]
    
    # Install core packages
    for package in packages:
        logger.info(f"Installing {package}...")
        if not run_command(f"python -m pip install {package}"):
            logger.error(f"❌ Failed to install {package}")
            return False
    
    # Install optional packages (don't fail if they can't be installed)
    logger.info("📦 Installing optional ML packages...")
    for package in optional_packages:
        logger.info(f"Installing {package}...")
        if not run_command(f"python -m pip install {package}", check=False):
            logger.warning(f"⚠️ Failed to install optional package {package}")
    
    logger.info("✅ AI dependencies installation completed")
    return True


def setup_ai_directories():
    """Create necessary directories for AI framework."""
    logger.info("📁 Setting up AI directories...")
    
    directories = [
        "data/ai_models",
        "data/feature_cache",
        "logs/ai",
        "data/experiments",
        "data/model_registry"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Created directory: {directory}")
    
    return True


def create_ai_config():
    """Create AI configuration file."""
    logger.info("⚙️ Creating AI configuration...")
    
    config_content = '''"""
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
'''
    
    config_path = Path("src/ai/config.py")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    logger.info("✅ AI configuration created")
    return True


def create_ai_requirements():
    """Create requirements file for AI dependencies."""
    logger.info("📄 Creating AI requirements file...")
    
    requirements = [
        "# Core AI/ML Dependencies",
        "scikit-learn>=1.3.0",
        "xgboost>=1.7.0",
        "numpy>=1.21.0", 
        "pandas>=1.5.0",
        "joblib>=1.2.0",
        "",
        "# Optional Advanced ML",
        "lightgbm>=3.3.0",
        "catboost>=1.2.0",
        "optuna>=3.0.0",
        "",
        "# Model Explainability",
        "shap>=0.41.0",
        "",
        "# Visualization and Dashboards",
        "plotly>=5.0.0",
        "dash>=2.10.0",
        "",
        "# Time Series",
        "statsmodels>=0.14.0",
        "",
        "# Deep Learning (Optional)",
        "# tensorflow>=2.12.0",
        "# torch>=2.0.0"
    ]
    
    with open("requirements-ai.txt", 'w') as f:
        f.write('\n'.join(requirements))
    
    logger.info("✅ AI requirements file created")
    return True


def validate_installation():
    """Validate that AI framework is properly installed."""
    logger.info("🔍 Validating AI framework installation...")
    
    try:
        # Test core imports
        import sklearn
        import numpy as np
        import pandas as pd
        import joblib
        
        logger.info(f"✅ scikit-learn: {sklearn.__version__}")
        logger.info(f"✅ numpy: {np.__version__}")
        logger.info(f"✅ pandas: {pd.__version__}")
        logger.info(f"✅ joblib: {joblib.__version__}")
        
        # Test optional imports
        try:
            import xgboost
            logger.info(f"✅ xgboost: {xgboost.__version__}")
        except ImportError:
            logger.warning("⚠️ xgboost not available")
        
        try:
            import lightgbm
            logger.info(f"✅ lightgbm: {lightgbm.__version__}")
        except ImportError:
            logger.warning("⚠️ lightgbm not available")
        
        # Test AI framework imports
        sys.path.append("src")
        from ai import AIDecisionEngine, FeatureStore
        logger.info("✅ AI framework imports successful")
        
        # Test basic functionality
        ai_engine = AIDecisionEngine()
        logger.info("✅ AI engine initialization successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return False


def create_ai_examples():
    """Create example scripts for AI usage."""
    logger.info("📝 Creating AI example scripts...")
    
    # Create examples directory
    examples_dir = Path("examples/ai")
    examples_dir.mkdir(parents=True, exist_ok=True)
    
    # Basic AI usage example
    basic_example = '''#!/usr/bin/env python3
"""
Basic AI Framework Usage Example
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ai import AIDecisionEngine

async def main():
    """Basic AI framework demonstration."""
    
    print("🧠 AlphaStock AI Framework - Basic Example")
    print("="*50)
    
    # Initialize AI engine
    ai_engine = AIDecisionEngine(confidence_threshold=0.85)
    
    # Create sample market data
    dates = pd.date_range(start=datetime.now() - timedelta(days=1), 
                         end=datetime.now(), freq='1min')
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': [50000 + i for i in range(len(dates))],
        'high': [50010 + i for i in range(len(dates))],
        'low': [49990 + i for i in range(len(dates))],
        'close': [50005 + i for i in range(len(dates))],
        'volume': [1000] * len(dates)
    })
    
    # Create sample signal
    sample_signal = {
        'symbol': 'BANKNIFTY',
        'strategy': 'Example',
        'signal_type': 'BUY',
        'timestamp': datetime.now()
    }
    
    # Test AI validation
    print("📡 Testing AI signal validation...")
    ai_signal = await ai_engine.validate_signal(sample_signal, sample_data)
    
    print(f"Signal: {ai_signal.signal_type}")
    print(f"Confidence: {ai_signal.confidence:.2%}")
    print(f"Execute: {'Yes' if ai_signal.execution_recommendation else 'No'}")
    
    # Test risk assessment
    print("\\n⚠️ Testing risk assessment...")
    risk_result = await ai_engine.assess_risk('BANKNIFTY', sample_data)
    print(f"Risk Score: {risk_result['risk_score']:.3f}")
    print(f"Recommendation: {risk_result['recommendation']}")
    
    print("\\n✅ Basic example completed!")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open(examples_dir / "basic_usage.py", 'w') as f:
        f.write(basic_example)
    
    # Model training example
    training_example = '''#!/usr/bin/env python3
"""
AI Model Training Example
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path  
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ai import AIDecisionEngine

async def main():
    """AI model training demonstration."""
    
    print("🎯 AI Model Training Example")
    print("="*40)
    
    # Create synthetic training data
    np.random.seed(42)
    n_samples = 1000
    
    dates = pd.date_range(start=datetime.now() - timedelta(days=30),
                         periods=n_samples, freq='1min')
    
    # Generate realistic market data with trends
    base_price = 50000
    trend = np.cumsum(np.random.normal(0, 0.001, n_samples))
    noise = np.random.normal(0, 0.01, n_samples)
    
    close_prices = base_price + trend * 100 + noise * 100
    
    training_data = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices * (1 + np.random.normal(0, 0.001, n_samples)),
        'high': close_prices * (1 + np.abs(np.random.normal(0, 0.002, n_samples))),
        'low': close_prices * (1 - np.abs(np.random.normal(0, 0.002, n_samples))),
        'close': close_prices,
        'volume': np.random.randint(500, 2000, n_samples)
    })
    
    print(f"📊 Generated {len(training_data)} training samples")
    
    # Initialize AI engine
    ai_engine = AIDecisionEngine(confidence_threshold=0.85)
    
    # Train models
    print("🎯 Training AI models...")
    await ai_engine.train_models(training_data)
    
    # Check model status
    status = ai_engine.get_model_status()
    print("\\n📈 Model Training Results:")
    
    for model_name, model_status in status.items():
        print(f"\\n{model_name}:")
        print(f"  Trained: {'Yes' if model_status['is_trained'] else 'No'}")
        if model_status['metrics']:
            print(f"  Accuracy: {model_status['metrics']['accuracy']:.3f}")
            print(f"  Samples: {model_status['metrics']['samples_trained']}")
    
    print("\\n✅ Training example completed!")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open(examples_dir / "model_training.py", 'w') as f:
        f.write(training_example)
    
    logger.info("✅ AI example scripts created")
    return True


def main():
    """Main setup function."""
    logger.info("🚀 AlphaStock AI Framework Setup Starting...")
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Create virtual environment (optional but recommended)
    # if not create_virtual_environment():
    #     success = False
    
    # Install AI dependencies
    if success and not install_ai_dependencies():
        success = False
    
    # Setup directories
    if success and not setup_ai_directories():
        success = False
    
    # Create configuration
    if success and not create_ai_config():
        success = False
    
    # Create requirements file
    if success and not create_ai_requirements():
        success = False
    
    # Create examples
    if success and not create_ai_examples():
        success = False
    
    # Validate installation
    if success and not validate_installation():
        success = False
    
    if success:
        logger.info("🎉 AI Framework Setup Completed Successfully!")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Run the basic example: python examples/ai/basic_usage.py")
        logger.info("2. Try model training: python examples/ai/model_training.py")
        logger.info("3. Run the full demo: python ai_integration_demo.py")
        logger.info("4. Integration with your trading strategy in main.py")
        logger.info("")
        logger.info("📚 Configuration file created: src/ai/config.py")
        logger.info("📦 AI requirements file: requirements-ai.txt")
        logger.info("📁 AI data directories created in data/")
    else:
        logger.error("❌ AI Framework Setup Failed!")
        logger.error("Please check the error messages above and resolve issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()
