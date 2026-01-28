# AlphaStock Trading System - New Architecture

## Overview
AlphaStock is a comprehensive trading system designed for production-scale algorithmic trading across multiple asset classes. The system features a modular monolithic architecture with specialized runners for different instrument types.

## 🏗️ Architecture

### Core Components

```
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
```

### Specialized Runners

#### 1. Equity Runner (`src/runners/equity_runner.py`)
- **Purpose**: Handles NSE/BSE equity stocks
- **Features**:
  - OHLC data collection
  - Volume analysis
  - Sector classification
  - Top gainers/losers tracking
  - Market sentiment analysis

#### 2. Options Runner (`src/runners/options_runner.py`)
- **Purpose**: Manages options contracts (CE/PE)
- **Features**:
  - Greeks calculation (Delta, Gamma, Theta, Vega)
  - Options chain management
  - Strike selection algorithms
  - Moneyness calculation
  - Expiry management

#### 3. Index Runner (`src/runners/index_runner.py`)
- **Purpose**: Tracks market indices
- **Features**:
  - Index values (Nifty50, Bank Nifty, etc.)
  - Sectoral indices performance
  - Market sentiment analysis
  - Correlation tracking
  - Support/resistance levels

#### 4. Commodity Runner (`src/runners/commodity_runner.py`)
- **Purpose**: Handles commodity instruments
- **Features**:
  - Precious metals (Gold, Silver)
  - Energy commodities (Crude Oil, Natural Gas)
  - Seasonal analysis
  - Margin requirement calculation
  - Technical indicators (RSI, Moving Averages)

#### 5. Futures Runner (`src/runners/futures_runner.py`)
- **Purpose**: Manages futures contracts
- **Features**:
  - Stock futures and index futures
  - Basis calculation (premium/discount)
  - Rollover analysis
  - Cost of carry calculation
  - Expiry proximity tracking

### Base Runner Framework (`src/runners/base_runner.py`)
- **Abstract base class** for all specialized runners
- **Common functionality**:
  - Threading and concurrent execution
  - Data caching with TTL
  - Error handling and retry logic
  - Callback system for real-time updates
  - Health monitoring and statistics

## 🚀 Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy environment template
cp .env.dev .env

# Edit with your Kite API credentials
vim .env

# Configure symbols and strategies
vim config/production.json
```

### 3. Run Demo
```bash
python demo_runners.py
```

### 4. Start Production System
```bash
python src/orchestrator.py
```

## 📊 Supported Instruments

### Equities
- NSE/BSE listed stocks
- Sector-wise analysis
- Volume and price momentum
- Technical indicators

### Options
- Call (CE) and Put (PE) options
- Weekly and monthly expiries
- Greeks calculation and analysis
- Options chain visualization

### Indices
- Nifty50, Bank Nifty, Fin Nifty
- Sectoral indices
- Index futures and options
- Market sentiment indicators

### Commodities
- **Precious Metals**: Gold, Silver
- **Energy**: Crude Oil, Natural Gas
- **Base Metals**: Copper, Zinc, Aluminum
- **Agricultural**: Wheat, Rice, Sugar (planned)

### Futures
- Index futures (Nifty, Bank Nifty)
- Stock futures
- Commodity futures
- Currency futures (planned)

## 🔧 Configuration

### Symbol Configuration (`config/production.json`)
```json
{
  "symbols": {
    "equities": ["SBIN", "INFY", "RELIANCE", "TCS", "HDFC"],
    "options": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
    "indices": ["NIFTY50", "BANKNIFTY", "FINNIFTY"],
    "commodities": ["GOLD", "SILVER", "CRUDEOIL"],
    "futures": ["NIFTY_FUT", "BANKNIFTY_FUT"]
  }
}
```

### Strategy Configuration
```json
{
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "symbols": ["NIFTYBANK", "SBIN", "RELIANCE"],
      "supported_asset_types": ["EQUITY", "INDEX", "FUTURES"],
      "parameters": {
        "fast_period": 9,
        "slow_period": 21,
        "ma_type": "EMA"
      }
    }
  }
}
```

## 📈 Trading Strategies

### 1. Moving Average Crossover
- **Assets**: Equities, Indices, Futures
- **Logic**: EMA/SMA crossover signals
- **Risk Management**: Built-in stop loss and target

### 2. Mean Reversion (Planned)
- **Assets**: Equities, Commodities
- **Logic**: Bollinger Bands + RSI
- **Features**: Oversold/Overbought detection

### 3. Breakout Momentum (Planned)
- **Assets**: All asset types
- **Logic**: Volume-confirmed breakouts
- **Features**: ATR-based position sizing

## 🔐 Security & Risk Management

### API Security
- Kite Connect integration with OAuth 2.0
- Environment-based credential management
- Rate limiting and retry mechanisms

### Risk Controls
- Paper trading mode for testing
- Position sizing based on volatility
- Maximum drawdown limits
- Real-time risk monitoring

### Data Security
- Encrypted API communications
- No credentials stored in code
- Secure environment variable handling

## 📊 Monitoring & Analytics

### System Health
```python
# Get runner status
runner_status = orchestrator.get_runner_status()

# Get comprehensive market data
market_data = orchestrator.get_comprehensive_market_data()

# Identify trading opportunities
opportunities = orchestrator.get_trading_opportunities()
```

### Performance Metrics
- Strategy execution statistics
- Signal generation rates
- API call efficiency
- Error tracking and alerting

## 🔄 Data Flow

1. **Market Data Collection**: Each runner continuously collects data for its asset type
2. **Data Processing**: Raw data is cleaned and enriched with technical indicators
3. **Strategy Execution**: Strategies analyze processed data and generate signals
4. **Signal Management**: Signals are queued, validated, and risk-checked
5. **Order Management**: Approved signals are converted to orders (paper/live)
6. **Monitoring**: All activities are logged and monitored for performance

## 🚦 System Status

### Health Checks
- API connectivity status
- Runner operational status
- Data collection rates
- Error rates and types

### Performance Metrics
- Latency measurements
- Memory and CPU usage
- Cache hit rates
- Signal generation efficiency

## 🛠️ Development

### Adding New Runners
1. Inherit from `BaseRunner`
2. Implement required methods:
   - `get_asset_type()`
   - `fetch_market_data()`
   - `process_data()`
3. Add to orchestrator initialization
4. Update configuration

### Adding New Strategies
1. Inherit from `BaseStrategy`
2. Implement `analyze()` method
3. Register with `StrategyFactory`
4. Add configuration parameters

## 📚 API Reference

### Orchestrator Methods
- `initialize()`: Initialize all components
- `start()`: Start data collection and strategy execution
- `stop()`: Graceful shutdown
- `get_status()`: System health and performance
- `get_comprehensive_market_data()`: All market data
- `get_trading_opportunities()`: Identified opportunities

### Runner Interface
- `start()`: Begin data collection
- `stop()`: Stop data collection
- `get_latest_data(symbol)`: Latest data for symbol
- `add_callback(callback)`: Register data callback

## 🔮 Roadmap

### Phase 1 (Current)
- ✅ Core architecture with specialized runners
- ✅ Equity, Options, Index, Commodity, Futures runners
- ✅ Kite API integration
- ✅ Basic strategy framework

### Phase 2 (Planned)
- [ ] Advanced strategy implementations
- [ ] Real-time WebSocket data feeds
- [ ] Enhanced options strategies
- [ ] Currency futures support

### Phase 3 (Future)
- [ ] Machine learning integration
- [ ] Portfolio optimization
- [ ] Multi-broker support
- [ ] Web-based dashboard

## 📞 Support

For questions, issues, or contributions:
1. Check the documentation
2. Review existing issues
3. Create detailed bug reports
4. Submit feature requests

## ⚖️ License

This project is for educational and research purposes. Please ensure compliance with all applicable regulations for algorithmic trading in your jurisdiction.

---

**Note**: This system is designed for paper trading by default. Always test thoroughly before considering live trading.
