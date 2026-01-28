#!/usr/bin/env python3
"""
AlphaStock Automated Deployment Guide

🎯 SYSTEM ARCHITECTURE OVERVIEW:
=================================

Your AlphaStock system has 3 key components:

1. main.py              ← 🎯 THE ACTUAL TRADING SYSTEM (what runs 9:15-3:30 daily)
2. scheduler.py         ← 🤖 AUTOMATION CONTROLLER (manages when things run)  
3. complete_workflow.py ← 🔧 SETUP/VALIDATION TOOL (runs once for health checks)

IMPORTANT: complete_workflow.py is NOT your trading system!
It's a diagnostic tool that validates everything is working properly.

🚀 DEPLOYMENT STRATEGY:
======================

Your laptop will automatically:
• 8:15 AM: Wake up, validate 1-year Bank Nifty data, fix any gaps
• 9:15 AM: Start main.py (your actual trading system)  
• 3:30 PM: Stop main.py gracefully
• 4:00 PM: Run post-market analysis

🔧 SETUP INSTRUCTIONS:
=====================

1. Run the automated setup:
   cd /Users/adithyasaladi/Personal/AlphaStock
   ./setup_automation.sh

2. This will:
   ✅ Install all dependencies (schedule, etc.)
   ✅ Setup databases automatically  
   ✅ Run complete system validation
   ✅ Install macOS LaunchAgent for auto-start
   ✅ Configure market hours scheduling

3. Your system starts automatically next trading day at 8:15 AM

📊 MONITORING YOUR SYSTEM:
=========================

• tail -f logs/scheduler.log     ← Automation controller logs
• tail -f logs/orchestrator.log  ← Trading system logs  
• tail -f logs/analysis.log      ← Technical analysis logs

🔧 MANUAL CONTROLS (for testing):
================================

• python3 scheduler.py --manual-start  ← Start full system now
• python3 scheduler.py --manual-stop   ← Stop system + analysis
• python3 scheduler.py --validate      ← Run data validation only
• python3 complete_workflow.py         ← Interactive health check

🛠️ macOS SERVICE MANAGEMENT:
============================

• launchctl list | grep alphastock              ← Check if running
• launchctl stop com.alphastock.scheduler       ← Stop automation  
• launchctl start com.alphastock.scheduler      ← Start automation
• launchctl unload ~/Library/LaunchAgents/com.alphastock.scheduler.plist  ← Disable

⚠️ IMPORTANT SAFETY NOTES:
==========================

• System runs in PAPER TRADING mode by default
• All trades are simulated - no real money involved
• Bank Nifty is prioritized with 1-year historical data
• MA Crossover strategy runs every 15 minutes
• Data collected every 5 seconds during market hours

🎯 WHAT HAPPENS DAILY:
=====================

8:15 AM (Pre-Market):
├── Scheduler wakes up your laptop  
├── Runs complete_workflow.py --silent --fix-gaps
├── Validates Bank Nifty 1-year data exists
├── Updates missing data if needed
└── Confirms system ready for trading

9:15 AM (Market Open):
├── Scheduler launches main.py
├── main.py starts orchestrator
├── Orchestrator initializes all components:
│   ├── Data layer (ClickHouse/PostgreSQL/Redis)
│   ├── Historical data manager  
│   ├── Analysis engine
│   ├── Kite Connect API
│   └── MA Crossover strategy
└── Real-time trading begins

9:15 AM - 3:30 PM (Trading Hours):
├── Bank Nifty data collected every 5 seconds
├── MA Crossover analysis every 15 minutes
├── Buy/sell signals generated when criteria met
├── All positions executed in paper trading mode
└── Everything logged for review

3:30 PM (Market Close):
├── Scheduler sends graceful stop signal to main.py
├── Orchestrator saves all session data
├── Database connections closed cleanly
└── System shuts down properly

4:00 PM (Post-Market):
├── Analysis engine generates daily report
├── Performance metrics calculated
├── Trading session summary created
└── Temporary files cleaned up

🚀 READY TO GO LIVE:
===================

After testing in paper trading mode:
1. Update config/production.json 
2. Set "paper_trading": false
3. Add real API credentials
4. System will trade with real money

Your laptop is now a fully automated trading server! 📈

"""

import sys
from pathlib import Path

def show_status():
    """Show current system status."""
    import subprocess
    import json
    
    print("🔍 CURRENT SYSTEM STATUS:")
    print("=" * 40)
    
    # Check if LaunchAgent is loaded
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.alphastock.scheduler"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Automation service: ACTIVE")
        else:
            print("❌ Automation service: NOT ACTIVE")
    except:
        print("⚠️ Automation service: UNKNOWN")
    
    # Check config
    config_path = Path("config/production.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            paper_mode = config.get("paper_trading", True)
            if paper_mode:
                print("📊 Trading mode: PAPER TRADING (Safe)")
            else:
                print("💰 Trading mode: REAL TRADING")
    else:
        print("⚠️ Configuration: NOT FOUND")
    
    # Check logs
    log_files = ["scheduler.log", "orchestrator.log"]
    for log_file in log_files:
        log_path = Path("logs") / log_file
        if log_path.exists():
            print(f"📋 {log_file}: Available")
        else:
            print(f"❌ {log_file}: Missing")

def main():
    """Main deployment guide."""
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_status()
        return
    
    print(__doc__)
    
    print("\n🎯 NEXT STEPS:")
    print("=============")
    print("1. Run: ./setup_automation.sh")
    print("2. Test: python3 scheduler.py --manual-start")
    print("3. Monitor: tail -f logs/scheduler.log")
    print("4. Your system will auto-start tomorrow at 8:15 AM!")
    
    print(f"\n📁 Current directory: {Path.cwd()}")
    print("💡 Run with --status to see current system status")

if __name__ == "__main__":
    main()
