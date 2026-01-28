# AlphaStock Trading System - New Architecture

A modern, modular trading system for automated strategy execution and signal generation using **Kite Connect API** (Zerodha).

## 🏗️ Architecture Overview

The new AlphaStock system follows a clean, modular architecture:

```
📦 AlphaStock
├── 🧠 Orchestrator - Coordinates all system components
├── 📈 Strategy Factory - Creates and manages trading strategies
├── 📊 Market Data Runner - Collects real-time market data via Kite API
├── 💾 Data Cache - In-memory data storage with TTL
├── 🎯 Signal Manager - Manages trading signals
├── 🔌 API Wrapper - Simple interface for external consumption
└── 🔑 Kite Connect Integration - Official Zerodha API client
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone and navigate to the project
cd AlphaStock

# Install dependencies (including kiteconnect)
pip install -r requirements.txt
```

### 2. API Setup

**Get Kite Connect API credentials:**
1. Visit [Kite Connect Developer Console](https://developers.kite.trade/)
2. Create an app and get your API key and secret
3. Add credentials to `.env.dev` file

### 3. Authentication

**First-time setup:**
```bash
# Add your credentials to .env.dev
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here

# Run authentication helper
python auth_helper.py auth

# Test your connection
python auth_helper.py test
```

### 4. Run the System

#### Option A: Using the CLI (Recommended)
```bash
# Start the system
python cli.py start

# Monitor in real-time
python cli.py monitor

# Check system status
python cli.py status

# View recent signals
python cli.py signals --limit 10

# Get strategy performance
python cli.py performance ma_crossover --days 7
```

#### Option B: Using the API directly
```python
from src.api_wrapper import AlphaStockAPI

# Create and start the API
api = AlphaStockAPI("config/production.json")
await api.initialize()
await api.start_system()

# Get system status
status = api.get_system_status()
print(f"System running: {status.running}")

# Get latest signals
signals = api.get_latest_signals(limit=10)
for signal in signals:
    print(f"{signal.symbol}: {signal.action} @ {signal.price}")
```

#### Option C: Run Examples
```bash
# Run all example usage patterns
python examples.py
```

## 🔑 API Authentication

### Kite Connect Setup

1. **Get API Credentials:**
   - Visit [Kite Developer Console](https://developers.kite.trade/)
   - Create a new app
   - Note down your API Key and API Secret

2. **Configure Secrets:**
   ```bash
   # Edit .env.dev file
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
   PAPER_TRADING=True  # Set to False for live trading
   ```

3. **Authenticate:**
   ```bash
   # Run authentication helper
   python auth_helper.py auth
   
   # This will:
   # - Open browser for OAuth login
   # - Generate access token
   # - Save token automatically
   ```

4. **Test Connection:**
   ```bash
   # Test API connection
   python auth_helper.py test
   
   # Show account details
   python auth_helper.py account
   ```

### Paper Trading vs Live Trading

**Paper Trading (Default):**
- No real money involved
- All trades are simulated
- Perfect for testing strategies
- Set `PAPER_TRADING=True` in `.env.dev`

**Live Trading:**
- Real money and actual trades
- Requires sufficient account balance
- Set `PAPER_TRADING=False` in `.env.dev`
- **Use with extreme caution!**

## 📈 Strategies

### Currently Implemented:
- **Moving Average Crossover**: EMA/SMA crossover signals with confidence scoring

### Available for Implementation:
- Mean Reversion (Bollinger Bands + RSI)
- Breakout Momentum (Volume + Price action)
- VWAP Strategy (Volume Weighted Average Price)
- Pairs Trading (Correlation-based)

### Adding New Strategies:

1. Create a new strategy class inheriting from `BaseStrategy`:
```python
from src.core.base_strategy import BaseStrategy

class MyNewStrategy(BaseStrategy):
    def analyze(self, data: pd.DataFrame) -> Optional[TradingSignal]:
        # Your strategy logic here
        pass
```

2. Register it in the factory:
```python
from src.core.strategy_factory import StrategyFactory
StrategyFactory.register_strategy("my_new_strategy", MyNewStrategy)
```

3. Add configuration in `config/production.json`:
```json
{
  "strategies": {
    "my_new_strategy": {
      "enabled": true,
      "symbols": ["BANKNIFTY"],
      "parameters": {
        "param1": "value1"
      }
    }
  }
}
```

## 🔧 CLI Commands

### System Management
```bash
python cli.py start          # Start the trading system
python cli.py stop           # Stop the trading system
python cli.py status         # Show detailed system status
python cli.py summary        # Show quick system overview
```

### Signal Analysis
```bash
python cli.py signals                    # Show recent signals
python cli.py signals -s BANKNIFTY       # Filter by symbol
python cli.py signals --strategy ma_crossover  # Filter by strategy
python cli.py search "SBIN" --field symbol     # Search signals
```

### Strategy Management
```bash
python cli.py strategies                 # List all strategies
python cli.py performance ma_crossover   # Show strategy performance
```

### Monitoring
```bash
python cli.py monitor                    # Live system monitoring
python cli.py monitor --refresh 10       # Custom refresh rate
```

## 🔌 API Usage

### Basic API Operations

```python
from src.api_wrapper import AlphaStockAPI

# Initialize
api = AlphaStockAPI("config/production.json")
await api.initialize()

# System control
await api.start_system()
status = api.get_system_status()
await api.stop_system()

# Get signals
latest_signals = api.get_latest_signals(limit=20)
banknifty_signals = api.get_latest_signals(symbol="BANKNIFTY")
strategy_signals = api.get_latest_signals(strategy="ma_crossover")

# Performance analysis
performance = api.get_strategy_performance("ma_crossover", days=7)
summary = api.get_signals_summary(groupby="symbol", since_hours=24)

# Search and filter
results = api.search_signals("BUY", field="action")
market_data = api.get_latest_market_data("BANKNIFTY")
```

### Response Objects

```python
# SignalResponse
signal = SignalResponse(
    symbol="BANKNIFTY",
    strategy="ma_crossover", 
    action="BUY",
    price=45250.50,
    confidence=0.85,
    timestamp="2024-01-01T10:30:00",
    target=46000.0,
    stop_loss=44500.0
)

# SystemStatus
status = SystemStatus(
    running=True,
    uptime_seconds=3600,
    market_open=True,
    total_signals=25,
    total_executions=150,
    errors=0,
    strategies=[...]
)
```

## 📊 Configuration

### Key Configuration Sections:

```json
{
  "api": {
    "credentials": {
      "api_key": "your_api_key",
      "username": "your_username", 
      "password": "your_password"
    }
  },
  "stocks": [
    {"symbol": "BANKNIFTY", "name": "Bank Nifty", "token": 26009},
    {"symbol": "NSE:SBIN", "name": "State Bank", "token": 3045}
  ],
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "symbols": ["BANKNIFTY", "NSE:SBIN"],
      "parameters": {
        "fast_period": 9,
        "slow_period": 21,
        "ma_type": "EMA"
      }
    }
  },
  "system": {
    "max_concurrent_strategies": 10,
    "data_cache_ttl": 300
  }
}
```

## 🔍 Monitoring & Debugging

### System Health Checks:
- API connection status
- Market data collection status
- Strategy execution frequency
- Error rates and logging

### Log Levels:
```python
# In config/production.json
"logging": {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "log_to_console": true,
    "log_to_file": true
}
```

### Performance Metrics:
- Signals generated per strategy
- Execution times
- Cache hit rates
- Error frequencies

## 🛠️ Development

### Running Tests:
```bash
pytest tests/
```

### Code Structure:
```
src/
├── core/              # Core system components
│   ├── base_strategy.py     # Strategy base class
│   ├── strategy_factory.py  # Strategy factory
│   ├── market_data_runner.py # Data collection
│   └── data_cache.py        # Caching system
├── strategies/        # Trading strategies
│   └── ma_crossover_strategy.py
├── api/              # External API integrations
├── trading/          # Trading and signal management
└── utils/            # Utilities and helpers
```

### Adding Features:
1. Implement new strategies in `src/strategies/`
2. Add API endpoints in `src/api_wrapper.py`
3. Update CLI commands in `cli.py`
4. Add configuration options in `config/production.json`

## 📈 Production Deployment

### Environment Setup:
```bash
# Production configuration
cp config/production.json config/prod.json
# Edit prod.json with production settings

# Start with production config
python cli.py -c config/prod.json start
```

### Monitoring:
- Use `python cli.py monitor` for live monitoring
- Check logs for errors and performance
- Monitor API rate limits and connection health

### Scaling:
- Increase `max_concurrent_strategies` for more parallel processing
- Adjust `data_cache_ttl` based on memory constraints
- Use multiple instances for different symbol sets

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests
5. Update documentation
6. Submit a pull request

## 📝 License

This project is for educational and personal use only.

## 🆘 Support

For questions or issues:
1. Check the logs for error details
2. Use `python cli.py status` to verify system health
3. Run `python examples.py` to test API functionality
4. Review configuration settings in `config/production.json`
