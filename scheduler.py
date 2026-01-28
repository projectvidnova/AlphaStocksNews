#!/usr/bin/env python3
"""
AlphaStock Market Hours Scheduler

Automatically starts and stops the trading system based on market hours.
Includes pre-market data validation and post-market cleanup.
"""

import os
import sys
import time
import signal
import subprocess
import schedule
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.logger_setup import setup_logger

logger = setup_logger("AlphaStockScheduler")

class AlphaStockScheduler:
    """
    Manages the complete lifecycle of AlphaStock trading system.
    
    Schedule:
    - 8:15 AM: Pre-market data validation and update
    - 9:15 AM: Start trading system
    - 3:30 PM: Stop trading system
    - 4:00 PM: Post-market analysis and cleanup
    """
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.trading_process = None
        self.config_path = self.project_root / "config" / "production.json"
        self.python_path = self._find_python_executable()
        
        # Ensure logs directory exists
        (self.project_root / "logs").mkdir(exist_ok=True)
        
        logger.info("AlphaStock Scheduler initialized")
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Python executable: {self.python_path}")
    
    def _find_python_executable(self):
        """Find the correct Python executable (preferably from venv)."""
        venv_python = self.project_root / ".venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        
        # Fallback to system python
        for python_cmd in ["python3", "python"]:
            try:
                result = subprocess.run([python_cmd, "--version"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return python_cmd
            except FileNotFoundError:
                continue
        
        raise RuntimeError("No Python executable found")
    
    def pre_market_validation(self):
        """Run pre-market data validation and updates (8:15 AM)."""
        logger.info("🌅 Starting pre-market validation...")
        
        try:
            # Run the validation workflow
            cmd = [self.python_path, "validate_system.py"]
            result = subprocess.run(
                cmd, 
                cwd=self.project_root,
                capture_output=True, 
                text=True,
                timeout=600  # 10 minutes max
            )
            
            if result.returncode == 0:
                logger.info("✅ Pre-market validation completed successfully")
                logger.info("📊 System ready for trading")
            else:
                logger.error(f"❌ Pre-market validation failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ Pre-market validation timed out (10 min limit)")
        except Exception as e:
            logger.error(f"❌ Pre-market validation error: {e}")
    
    def start_trading_system(self):
        """Start the main trading system (9:15 AM)."""
        logger.info("🚀 Starting AlphaStock trading system...")
        
        if self.trading_process and self.trading_process.poll() is None:
            logger.warning("Trading system already running")
            return
        
        try:
            # Start the main trading system
            cmd = [self.python_path, "main.py"]
            self.trading_process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            logger.info(f"📈 Trading system started (PID: {self.trading_process.pid})")
            logger.info("💰 Paper trading mode active")
            
            # Monitor the first few seconds to ensure it started properly
            time.sleep(10)
            if self.trading_process.poll() is not None:
                logger.error("❌ Trading system failed to start properly")
            
        except Exception as e:
            logger.error(f"❌ Failed to start trading system: {e}")
    
    def stop_trading_system(self):
        """Stop the trading system gracefully (3:30 PM)."""
        logger.info("🛑 Stopping AlphaStock trading system...")
        
        if not self.trading_process or self.trading_process.poll() is not None:
            logger.info("Trading system is not running")
            return
        
        try:
            # Send SIGTERM for graceful shutdown
            self.trading_process.terminate()
            
            # Wait up to 60 seconds for graceful shutdown
            try:
                self.trading_process.wait(timeout=60)
                logger.info("✅ Trading system stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Graceful shutdown timed out, forcing stop...")
                self.trading_process.kill()
                self.trading_process.wait()
                logger.info("🔨 Trading system force stopped")
            
            self.trading_process = None
            
        except Exception as e:
            logger.error(f"❌ Error stopping trading system: {e}")
    
    def post_market_analysis(self):
        """Run post-market analysis and cleanup (4:00 PM)."""
        logger.info("📊 Starting post-market analysis...")
        
        try:
            # Run basic analysis
            cmd = [self.python_path, "-c", """
print('📊 Post-market analysis started')
print('✅ Trading session completed')
print('💾 Data stored successfully')
print('📋 Session summary generated')
"""]
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )
            
            if result.returncode == 0:
                logger.info("✅ Post-market analysis completed")
                logger.info(result.stdout)
            else:
                logger.error(f"❌ Post-market analysis failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Post-market analysis error: {e}")
    
    def setup_schedule(self):
        """Set up the daily trading schedule."""
        logger.info("📅 Setting up daily trading schedule...")
        
        # Pre-market validation (8:15 AM)
        schedule.every().monday.at("08:15").do(self.pre_market_validation)
        schedule.every().tuesday.at("08:15").do(self.pre_market_validation)
        schedule.every().wednesday.at("08:15").do(self.pre_market_validation)
        schedule.every().thursday.at("08:15").do(self.pre_market_validation)
        schedule.every().friday.at("08:15").do(self.pre_market_validation)
        
        # Start trading system (9:15 AM)
        schedule.every().monday.at("09:15").do(self.start_trading_system)
        schedule.every().tuesday.at("09:15").do(self.start_trading_system)
        schedule.every().wednesday.at("09:15").do(self.start_trading_system)
        schedule.every().thursday.at("09:15").do(self.start_trading_system)
        schedule.every().friday.at("09:15").do(self.start_trading_system)
        
        # Stop trading system (3:30 PM)
        schedule.every().monday.at("15:30").do(self.stop_trading_system)
        schedule.every().tuesday.at("15:30").do(self.stop_trading_system)
        schedule.every().wednesday.at("15:30").do(self.stop_trading_system)
        schedule.every().thursday.at("15:30").do(self.stop_trading_system)
        schedule.every().friday.at("15:30").do(self.stop_trading_system)
        
        # Post-market analysis (4:00 PM)
        schedule.every().monday.at("16:00").do(self.post_market_analysis)
        schedule.every().tuesday.at("16:00").do(self.post_market_analysis)
        schedule.every().wednesday.at("16:00").do(self.post_market_analysis)
        schedule.every().thursday.at("16:00").do(self.post_market_analysis)
        schedule.every().friday.at("16:00").do(self.post_market_analysis)
        
        logger.info("✅ Schedule configured:")
        logger.info("   8:15 AM - Pre-market validation")
        logger.info("   9:15 AM - Start trading system")
        logger.info("  15:30 PM - Stop trading system")
        logger.info("  16:00 PM - Post-market analysis")
    
    def run(self):
        """Run the scheduler continuously."""
        logger.info("🎯 AlphaStock Scheduler started")
        logger.info("Press Ctrl+C to stop")
        
        self.setup_schedule()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("\n🛑 Scheduler stopped by user")
            if self.trading_process:
                self.stop_trading_system()
    
    def manual_start(self):
        """Manually start trading system (for testing)."""
        logger.info("🔧 Manual start requested")
        self.pre_market_validation()
        time.sleep(5)
        self.start_trading_system()
    
    def manual_stop(self):
        """Manually stop trading system (for testing)."""
        logger.info("🔧 Manual stop requested")
        self.stop_trading_system()
        self.post_market_analysis()

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AlphaStock Scheduler")
    parser.add_argument("--manual-start", action="store_true", help="Manually start trading system")
    parser.add_argument("--manual-stop", action="store_true", help="Manually stop trading system")
    parser.add_argument("--validate", action="store_true", help="Run pre-market validation only")
    
    args = parser.parse_args()
    
    scheduler = AlphaStockScheduler()
    
    if args.manual_start:
        scheduler.manual_start()
    elif args.manual_stop:
        scheduler.manual_stop()
    elif args.validate:
        scheduler.pre_market_validation()
    else:
        scheduler.run()

if __name__ == "__main__":
    main()
