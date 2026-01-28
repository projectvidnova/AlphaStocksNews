# AlphaStock - Quick Reference Guide

## 📁 Project Structure

```
AlphaStocks/
├── main.py                      # 🚀 Main trading system entry point
├── complete_workflow.py         # ✅ Full system validation & data download
├── cli.py                       # 💻 Command-line interface
├── scheduler.py                 # ⏰ Task scheduling
├── dashboard.py                 # 📊 Trading dashboard
│
├── README.md                    # 📖 Main documentation
├── SETUP_CREDENTIALS.md         # 🔐 Credential setup guide
│
├── src/                         # 🧩 Source code
│   ├── api/                     # Kite Connect API client
│   ├── core/                    # Core trading engine
│   ├── data/                    # Data layers
│   ├── strategies/              # Trading strategies
│   ├── trading/                 # Order execution
│   └── utils/                   # Utilities
│
├── config/                      # ⚙️ Configuration
│   ├── database.json            # Database settings
│   └── production.json          # Trading parameters
│
├── scripts/                     # 🛠️ Utility & deployment scripts
│   ├── utilities/               # Helper scripts
│   │   ├── test_system.sh            # ✓ System health check
│   │   ├── monitor_workflow.sh       # 📈 Monitor progress
│   │   └── cleanup_temp.sh           # 🧹 Clean temp files
│   │
│   ├── deployment/              # Deployment automation
│   │   ├── start_alphastock.sh
│   │   ├── stop_alphastock.sh
│   │   └── deploy_local.sh
│   │
│   └── database/                # Database setup scripts
│
├── test_auth.py                 # 🔑 Quick authentication test
│
├── data/                        # 📦 Data storage
│   ├── historical/              # Historical market data
│   ├── signals/                 # Trading signals
│   └── backtest/                # Backtest results
│
├── logs/                        # 📝 System logs
├── tests/                       # 🧪 Test suite
└── examples/                    # 📚 Example scripts
```

## 🚀 Common Commands

### Daily Routine (Before Market Hours)
```bash
# 1. Authenticate with Zerodha (auto-launches browser)
python cli.py auth

# 2. Start trading system
python main.py

# Alternative: Quick test authentication
python test_auth.py
```

### First-Time Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup database (Docker)
docker run -d --name alphastock-clickhouse \
  -p 8123:8123 clickhouse/clickhouse-server

# 3. Configure credentials
# Edit .env.dev with your Kite API keys (key and secret)

# 4. Authenticate (auto-launches browser)
python cli.py auth

# 5. Download historical data
python complete_workflow.py
```

### Monitoring & Debugging
```bash
# Check system health
python scripts/utilities/test_system.sh

# Monitor running workflow
scripts/utilities/monitor_workflow.sh

# View live logs
tail -f logs/AlphaStockOrchestrator.log

# Clean temporary files
scripts/utilities/cleanup_temp.sh
```

## 🔑 Key Concepts

### Access Token (IMPORTANT!)
- **Expires daily** - regenerate every morning before 9:15 AM IST
- Use: `python cli.py auth` (auto-launches browser, auto-saves token)
- Stored in: `.env.dev` (never commit!)
- See: **[AUTHENTICATION.md](AUTHENTICATION.md)** for detailed guide

### Paper Trading
- **Enabled by default** - no real money at risk
- Test strategies safely with ₹100,000 virtual capital
- Disable only when ready: set `PAPER_TRADING=false` in `.env.dev`

### Data Download
- First run downloads 3 years of Bank Nifty data
- Takes ~10-15 minutes (rate limited)
- Cached in ClickHouse - subsequent runs are instant

### Trading Strategies
All strategies in `src/strategies/`:
- MA Crossover (`ma_crossover.py`)
- Momentum (`momentum_strategy.py`)
- RSI (`rsi_strategy.py`)

Configure in: `config/production.json`

## 📖 Documentation

- **README.md** - Project overview and setup
- **AUTHENTICATION.md** - Complete authentication guide
- **SETUP_CREDENTIALS.md** - Detailed credential setup
- **docs/** - Additional guides and documentation

## 🆘 Troubleshooting

### Authentication Failed
```bash
# Authenticate (auto-launches browser)
python cli.py auth

# Or test current token
python test_auth.py
```

### Database Connection Error
```bash
# Check ClickHouse is running
docker ps | grep clickhouse

# Restart if needed
docker restart alphastock-clickhouse
```

### No Historical Data
```bash
# Download data
python complete_workflow.py
```

## 🔒 Security Notes

- Never commit `.env.dev` (contains API credentials)
- Access tokens expire daily - regenerate before market
- Paper trading enabled by default for safety
- Review all trades in logs before going live

## 👥 Team Collaboration

### Before Committing
```bash
# Clean temporary files
scripts/utilities/cleanup_temp.sh

# Ensure .env.dev is not staged
git status
```

### Getting Latest Changes
```bash
git pull
pip install -r requirements.txt  # Update dependencies if changed
```

### File Organization
- Root: Only essential entry points and docs
- Scripts: All utilities in `scripts/`
- Source: All code in `src/`
- Tests: All tests in `tests/`

---

**Quick Start:** `python scripts/utilities/generate_access_token.py` → `python main.py`

**Need Help?** Check `README.md` or `SETUP_CREDENTIALS.md`
