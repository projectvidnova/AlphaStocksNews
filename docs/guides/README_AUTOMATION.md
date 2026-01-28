# 🚀 AlphaStock Automated Trading System - Complete Setup Guide

## 🎯 **SYSTEM ARCHITECTURE - CRYSTAL CLEAR**

Your AlphaStock system has **3 distinct components**:

```
📁 AlphaStock/
├── main.py                    ← 🎯 MAIN TRADING SYSTEM (runs 9:15 AM - 3:30 PM daily)
├── scheduler.py               ← 🤖 AUTOMATION CONTROLLER (manages when things run)  
├── complete_workflow.py       ← 🔧 DIAGNOSTIC TOOL (validates system health)
└── src/orchestrator.py        ← 💼 CORE ENGINE (called by main.py)
```

### **IMPORTANT CLARIFICATION:**
- **`main.py`** = Your actual trading system that makes money
- **`scheduler.py`** = The automation that starts/stops main.py at market hours  
- **`complete_workflow.py`** = A health checker tool (NOT the trading system!)

---

## 🚀 **ONE-COMMAND SETUP**

```bash
cd /Users/adithyasaladi/Personal/AlphaStock
./setup_automation.sh
```

This single command will:
- ✅ Install all Python dependencies (`schedule`, etc.)
- ✅ Setup ClickHouse/PostgreSQL/Redis databases
- ✅ Validate complete system (including 1-year Bank Nifty data)
- ✅ Install macOS LaunchAgent for automatic startup
- ✅ Configure market hours scheduling (8:15 AM - 4:00 PM)
- ✅ Set up comprehensive logging

---

## 📅 **YOUR DAILY AUTOMATED WORKFLOW**

### **🌅 8:15 AM - Pre-Market (Automatic)**
```
Scheduler → complete_workflow.py --silent --fix-gaps
├── Validates Bank Nifty 1-year historical data exists
├── Downloads any missing data gaps
├── Verifies all system components working
└── Confirms system ready for trading
```

### **🚀 9:15 AM - Market Open (Automatic)**
```
Scheduler → main.py → orchestrator.py
├── Initializes data layer (ClickHouse/PostgreSQL/Redis)
├── Starts historical data manager
├── Activates analysis engine (RSI, MACD, Bollinger Bands)
├── Connects to Kite Connect API
├── Loads MA Crossover strategy
└── Begins real-time Bank Nifty monitoring (5-second intervals)
```

### **📈 9:15 AM - 3:30 PM - Trading Hours (Automatic)**
```
Orchestrator runs continuously:
├── Collects Bank Nifty data every 5 seconds
├── Runs MA Crossover analysis every 15 minutes  
├── Generates buy/sell signals when criteria met
├── Executes all trades in PAPER TRADING mode (safe!)
├── Logs everything for your review
└── Updates Redis cache for real-time performance
```

### **🛑 3:30 PM - Market Close (Automatic)**
```
Scheduler → graceful shutdown of main.py
├── Saves all trading session data
├── Closes database connections cleanly
├── Archives log files
└── Stops orchestrator safely
```

### **📊 4:00 PM - Post-Market Analysis (Automatic)**
```
Scheduler → analysis_engine.generate_daily_report()
├── Analyzes day's Bank Nifty performance
├── Calculates strategy effectiveness
├── Generates performance metrics (Sharpe ratio, VaR, etc.)
├── Creates daily summary report
└── Cleans up temporary files
```

---

## 🔧 **MANUAL CONTROLS** (For Testing)

```bash
# Test the complete flow manually:
python3 scheduler.py --manual-start    # Pre-market validation + start trading
python3 scheduler.py --manual-stop     # Stop trading + post-market analysis
python3 scheduler.py --validate        # Run data validation only

# Diagnostic tools:
python3 complete_workflow.py           # Interactive system health check
python3 DEPLOYMENT_GUIDE.py --status   # Check current system status
```

---

## 📊 **MONITORING YOUR AUTOMATED SYSTEM**

```bash
# Real-time monitoring:
tail -f logs/scheduler.log              # Automation controller logs
tail -f logs/orchestrator.log           # Trading system logs
tail -f logs/analysis.log               # Technical analysis logs

# macOS service status:
launchctl list | grep alphastock        # Check if automation is running
```

---

## 🛠️ **SYSTEM MANAGEMENT**

```bash
# Start/stop automation service:
launchctl stop com.alphastock.scheduler     # Stop automation
launchctl start com.alphastock.scheduler    # Start automation

# Disable automation completely:
launchctl unload ~/Library/LaunchAgents/com.alphastock.scheduler.plist

# Re-enable automation:
launchctl load ~/Library/LaunchAgents/com.alphastock.scheduler.plist
```

---

## ⚠️ **SAFETY FEATURES**

- **Paper Trading Default**: All trades simulated by default (no real money risk)
- **Bank Nifty Priority**: Focuses on Bank Nifty with complete 1-year historical data
- **Graceful Shutdown**: System stops cleanly if anything goes wrong  
- **Comprehensive Logging**: Every action logged for debugging
- **Pre-Market Validation**: Ensures data quality before trading starts

---

## 🎯 **WHAT YOUR LAPTOP DOES AUTOMATICALLY**

1. **Monday-Friday 8:15 AM**: Wakes up, validates Bank Nifty data, fixes gaps
2. **Monday-Friday 9:15 AM**: Starts trading system automatically
3. **Monday-Friday 3:30 PM**: Stops trading system gracefully  
4. **Monday-Friday 4:00 PM**: Runs analysis, generates reports
5. **Weekends**: System remains dormant

---

## 🚀 **GOING FROM PAPER TO REAL TRADING**

After testing successfully in paper mode:

1. Edit `config/production.json`:
```json
{
    \"paper_trading\": false,
    \"kite_api_key\": \"your_real_api_key\",
    \"kite_api_secret\": \"your_real_secret\"
}
```

2. Restart the system:
```bash
python3 scheduler.py --manual-stop
python3 scheduler.py --manual-start
```

**Your laptop is now a fully automated trading server! 📈**

---

## 🔥 **KEY BENEFITS**

- **Fully Automated**: Runs without your intervention
- **Bank Nifty Focus**: Complete 1-year data + priority analysis  
- **Risk-Free Testing**: Paper trading by default
- **Professional Grade**: ClickHouse performance, Redis caching
- **Comprehensive**: Pre-market validation + post-market analysis
- **macOS Integrated**: Uses native LaunchAgent for reliability

Your trading system will now run automatically every trading day while you sleep! 🌙→📈
