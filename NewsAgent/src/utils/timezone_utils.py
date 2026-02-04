"""
Centralized Timezone Management for AlphaStocks Trading System

This module provides consistent timezone handling across the entire application.
All timestamps should use IST (Indian Standard Time - Asia/Kolkata) for consistency.

Usage:
    from src.utils.timezone_utils import get_current_time, get_timezone, to_ist, to_utc
    
    # Get current time in IST
    now = get_current_time()
    
    # Convert UTC to IST
    ist_time = to_ist(utc_timestamp)
    
    # Convert IST to UTC
    utc_time = to_utc(ist_timestamp)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

# Application-wide timezone configuration
# This is the single source of truth for timezone handling
APP_TIMEZONE_NAME = "Asia/Kolkata"  # IST
APP_TIMEZONE = pytz.timezone(APP_TIMEZONE_NAME)

# Alternative using zoneinfo (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
    APP_TIMEZONE_ZONEINFO = ZoneInfo(APP_TIMEZONE_NAME)
except ImportError:
    # Fallback for older Python versions
    APP_TIMEZONE_ZONEINFO = None


def get_timezone() -> pytz.timezone:
    """
    Get the application's configured timezone (IST).
    
    Returns:
        pytz.timezone: Asia/Kolkata timezone
    """
    return APP_TIMEZONE


def get_timezone_name() -> str:
    """
    Get the application's timezone name.
    
    Returns:
        str: "Asia/Kolkata"
    """
    return APP_TIMEZONE_NAME


def get_current_time() -> datetime:
    """
    Get current time in IST.
    
    This should be used instead of datetime.now() or datetime.utcnow()
    to ensure consistency across the application.
    
    Returns:
        datetime: Current time in IST (timezone-aware)
    
    Example:
        >>> now = get_current_time()
        >>> print(now.tzinfo)  # Asia/Kolkata
    """
    if APP_TIMEZONE_ZONEINFO:
        return datetime.now(APP_TIMEZONE_ZONEINFO)
    else:
        return datetime.now(APP_TIMEZONE)


def get_current_time_naive() -> datetime:
    """
    Get current time in IST as naive datetime (no timezone info).
    
    Use this only when you need to store in systems that don't support timezones.
    Prefer get_current_time() for timezone-aware operations.
    
    Returns:
        datetime: Current time in IST (timezone-naive)
    """
    aware_time = get_current_time()
    return aware_time.replace(tzinfo=None)


def to_ist(dt: datetime) -> datetime:
    """
    Convert any datetime to IST.
    
    Args:
        dt: Datetime to convert (can be naive or timezone-aware)
    
    Returns:
        datetime: Converted datetime in IST (timezone-aware)
    
    Example:
        >>> utc_time = datetime.now(timezone.utc)
        >>> ist_time = to_ist(utc_time)
    """
    if dt is None:
        return None
    
    # If naive, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # Convert to IST
    return dt.astimezone(APP_TIMEZONE)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC.
    
    Args:
        dt: Datetime to convert (can be naive or timezone-aware)
    
    Returns:
        datetime: Converted datetime in UTC (timezone-aware)
    
    Example:
        >>> ist_time = get_current_time()
        >>> utc_time = to_utc(ist_time)
    """
    if dt is None:
        return None
    
    # If naive, assume it's IST
    if dt.tzinfo is None:
        dt = APP_TIMEZONE.localize(dt)
    
    # Convert to UTC
    return dt.astimezone(pytz.utc)


def make_aware(dt: datetime, assume_timezone: str = "IST") -> datetime:
    """
    Convert naive datetime to timezone-aware datetime.
    
    Args:
        dt: Naive datetime
        assume_timezone: Timezone to assume ("IST" or "UTC")
    
    Returns:
        datetime: Timezone-aware datetime
    
    Example:
        >>> naive_dt = datetime(2025, 11, 7, 10, 30)
        >>> aware_dt = make_aware(naive_dt, assume_timezone="IST")
    """
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        # Already aware
        return dt
    
    if assume_timezone == "IST":
        return APP_TIMEZONE.localize(dt)
    elif assume_timezone == "UTC":
        return pytz.utc.localize(dt)
    else:
        raise ValueError(f"Unknown timezone: {assume_timezone}")


def get_today_start() -> datetime:
    """
    Get start of today (00:00:00) in IST.
    
    Returns:
        datetime: Today's start time in IST
    """
    now = get_current_time()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_today_market_open() -> datetime:
    """
    Get today's market opening time (9:15 AM IST).
    
    Returns:
        datetime: Today's 9:15 AM IST
    """
    now = get_current_time()
    return now.replace(hour=9, minute=15, second=0, microsecond=0)


def get_today_market_close() -> datetime:
    """
    Get today's market closing time (3:30 PM IST).
    
    Returns:
        datetime: Today's 3:30 PM IST
    """
    now = get_current_time()
    return now.replace(hour=15, minute=30, second=0, microsecond=0)


def is_market_hours() -> bool:
    """
    Check if current time is within market trading hours (9:15 AM - 3:30 PM IST).
    
    Returns:
        bool: True if within market hours
    """
    now = get_current_time()
    market_open = get_today_market_open()
    market_close = get_today_market_close()
    
    # Check if today is a weekday (Monday=0, Sunday=6)
    if now.weekday() > 4:  # Saturday or Sunday
        return False
    
    return market_open <= now <= market_close


def format_ist_time(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """
    Format datetime in IST for display.
    
    Args:
        dt: Datetime to format (defaults to current time)
        format_str: Format string
    
    Returns:
        str: Formatted time string
    
    Example:
        >>> formatted = format_ist_time()
        >>> print(formatted)  # "2025-11-07 14:30:00 IST"
    """
    if dt is None:
        dt = get_current_time()
    else:
        dt = to_ist(dt)
    
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str, input_timezone: str = "IST") -> datetime:
    """
    Parse timestamp string to timezone-aware datetime.
    
    Args:
        timestamp_str: Timestamp string (ISO format)
        input_timezone: Timezone of the input ("IST" or "UTC")
    
    Returns:
        datetime: Parsed timezone-aware datetime in IST
    
    Example:
        >>> dt = parse_timestamp("2025-11-07 14:30:00", input_timezone="IST")
    """
    # Try parsing with timezone info first
    try:
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            # No timezone info, make it aware
            dt = make_aware(dt, assume_timezone=input_timezone)
        # Convert to IST
        return to_ist(dt)
    except ValueError:
        # Try other formats
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                dt = make_aware(dt, assume_timezone=input_timezone)
                return to_ist(dt)
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse timestamp: {timestamp_str}")


# Convenience functions for common operations
def now() -> datetime:
    """Alias for get_current_time()"""
    return get_current_time()


def now_naive() -> datetime:
    """Alias for get_current_time_naive()"""
    return get_current_time_naive()


def today_start() -> datetime:
    """Alias for get_today_start()"""
    return get_today_start()


def market_open() -> datetime:
    """Alias for get_today_market_open()"""
    return get_today_market_open()


def market_close() -> datetime:
    """Alias for get_today_market_close()"""
    return get_today_market_close()


# Migration helper - for detecting and reporting timezone inconsistencies
def detect_timezone(dt: datetime) -> str:
    """
    Detect the timezone of a datetime object.
    
    Args:
        dt: Datetime to check
    
    Returns:
        str: "naive", "UTC", "IST", or timezone name
    """
    if dt is None:
        return "None"
    
    if dt.tzinfo is None:
        return "naive"
    
    if dt.tzinfo == pytz.utc:
        return "UTC"
    
    if dt.tzinfo == APP_TIMEZONE or str(dt.tzinfo) == "Asia/Kolkata":
        return "IST"
    
    return str(dt.tzinfo)
