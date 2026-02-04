import pytz
from datetime import datetime, time, timedelta
import json
from pathlib import Path

def is_market_open(config=None):
    """
    Standalone function to check if market is open.
    If config is not provided, loads from config/production.json
    """
    if config is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "production.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
    
    market_hours = MarketHours(config)
    return market_hours.is_market_open()

class MarketHours:
    """
    Utility class to check market hours
    """
    
    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config
        self.timezone = pytz.timezone(config["market"]["timezone"])
        
        # Parse market hours
        open_time_str = config["market"]["open_time"]
        close_time_str = config["market"]["close_time"]
        
        open_hour, open_minute = map(int, open_time_str.split(":"))
        close_hour, close_minute = map(int, close_time_str.split(":"))
        
        self.open_time = time(open_hour, open_minute)
        self.close_time = time(close_hour, close_minute)
        
        # Trading days (0=Monday, 6=Sunday)
        self.trading_days = config["market"]["trading_days"]
    
    def is_market_open(self):
        """Check if the market is currently open"""
        # Get current time in the configured timezone
        now = datetime.now(self.timezone)
        
        # Check if it's a trading day
        if now.weekday() not in self.trading_days:
            return False
        
        # Check if within market hours
        current_time = now.time()
        return self.open_time <= current_time <= self.close_time
    
    def time_to_market_open(self):
        """Get time until market opens (in seconds)"""
        now = datetime.now(self.timezone)
        
        # If it's already open today, return 0
        if self.is_market_open():
            return 0
        
        # If it's before market open today
        if now.time() < self.open_time and now.weekday() in self.trading_days:
            market_open = datetime.combine(now.date(), self.open_time)
            market_open = self.timezone.localize(market_open)
            return (market_open - now).total_seconds()
        
        # Find the next trading day
        days_ahead = 1
        while True:
            next_day = (now + timedelta(days=days_ahead)).weekday()
            if next_day in self.trading_days:
                break
            days_ahead += 1
        
        # Calculate time until market opens on the next trading day
        next_open = datetime.combine((now + timedelta(days=days_ahead)).date(), self.open_time)
        next_open = self.timezone.localize(next_open)
        return (next_open - now).total_seconds()
    
    def time_to_market_close(self):
        """Get time until market closes (in seconds)"""
        now = datetime.now(self.timezone)
        
        # If market is not open, return 0
        if not self.is_market_open():
            return 0
        
        # Calculate time until market closes today
        market_close = datetime.combine(now.date(), self.close_time)
        market_close = self.timezone.localize(market_close)
        return (market_close - now).total_seconds()