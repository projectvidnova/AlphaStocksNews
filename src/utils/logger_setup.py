import logging
import os
from logging.handlers import TimedRotatingFileHandler
import json
from pathlib import Path
import functools
import inspect

# Try to import colorama for colored console output
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback to no colors if colorama not available
    class Fore:
        RED = ''
        YELLOW = ''
        WHITE = ''
        RESET = ''
    
    class Style:
        RESET_ALL = ''


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds color coding to log levels and includes method names:
    - INFO: No color (white/default)
    - WARNING: Amber/Yellow
    - ERROR: Red
    - CRITICAL: Red
    - DEBUG: Default (for debugging)
    """
    
    # Color mapping for different log levels
    COLORS = {
        'DEBUG': Fore.WHITE,
        'INFO': Fore.WHITE,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED,
    }
    
    def format(self, record):
        # Add method name to the record if not already set
        if not hasattr(record, 'method_name') or not record.method_name:
            # Try to extract method name from the call stack
            method_name = self._get_method_name()
            if method_name:
                record.method_name = method_name
            else:
                # Fallback: try to get class name from module path
                record.method_name = self._fallback_method_name(record)
        
        # Get the original formatted message
        log_message = super().format(record)
        
        # Add color to the log level in console output
        if COLORAMA_AVAILABLE:
            color = self.COLORS.get(record.levelname, Fore.WHITE)
            # Color the entire message for warnings and errors
            if record.levelname in ['WARNING', 'ERROR', 'CRITICAL']:
                return f"{color}{log_message}{Style.RESET_ALL}"
            else:
                # For INFO and DEBUG, keep default color
                return log_message
        
        return log_message
    
    def _get_method_name(self):
        """Extract method name from call stack."""
        try:
            # Walk up the stack to find the calling method (skip logging internals)
            frame = inspect.currentframe()
            
            # Skip frames until we find user code (not in logging module)
            for _ in range(20):  # Check up to 20 frames
                if frame is None:
                    break
                frame = frame.f_back
                if frame is None:
                    break
                
                # Get the code object
                code = frame.f_code
                filename = code.co_filename
                func_name = code.co_name
                
                # Skip logging module internals and our formatter
                if 'logging' in filename.lower():
                    continue
                if 'logger_setup' in filename:
                    continue
                    
                # Skip common wrapper functions
                if func_name in ('wrapper', 'process', 'format', '_log', 'emit'):
                    continue
                
                # Found user code!
                # Check if it's a method (has 'self' or 'cls' in locals)
                if 'self' in frame.f_locals:
                    class_name = frame.f_locals['self'].__class__.__name__
                    return f"{class_name}.{func_name}"
                elif 'cls' in frame.f_locals:
                    class_name = frame.f_locals['cls'].__name__
                    return f"{class_name}.{func_name}"
                else:
                    # Standalone function
                    return func_name
        except Exception as e:
            pass
        
        return ""
    
    def _fallback_method_name(self, record):
        """Fallback to extract method name from record."""
        try:
            # Use funcName from the record
            func_name = record.funcName
            
            # Try to find the calling frame to get class name
            frame = inspect.currentframe()
            for _ in range(10):
                if frame is None:
                    break
                frame = frame.f_back
                if frame is None:
                    break
                
                # Check if this frame has the matching function name
                if frame.f_code.co_name == func_name:
                    if 'self' in frame.f_locals:
                        class_name = frame.f_locals['self'].__class__.__name__
                        return f"{class_name}.{func_name}"
                    elif 'cls' in frame.f_locals:
                        class_name = frame.f_locals['cls'].__name__
                        return f"{class_name}.{func_name}"
            
            # Just return the function name
            return func_name
        except:
            return record.funcName


def setup_logger(config=None, name=None, level="INFO"):
    """
    Set up logging with configuration
    Supports both legacy (config dict) and new (name, level) signatures
    """
    # Handle new signature (name, level)
    if config is None or isinstance(config, str):
        # If config is a string, it's actually the name parameter
        if isinstance(config, str):
            name = config
        
        # Create a simple logger for the named component
        logger = logging.getLogger(name or "AlphaStock")
        
        # Only configure if not already configured
        if not logger.handlers:
            log_level = getattr(logging, level.upper() if isinstance(level, str) else "INFO")
            logger.setLevel(log_level)
            
            # Create console handler with colored formatter (includes method name)
            # Use UTF-8 encoding to support Unicode characters (₹, ✅, etc.)
            import sys
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_format = ColoredFormatter('%(asctime)s - %(name)s - %(method_name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_format)
            # Force UTF-8 encoding on Windows
            if hasattr(sys.stdout, 'reconfigure'):
                try:
                    sys.stdout.reconfigure(encoding='utf-8')
                except Exception:
                    pass
            logger.addHandler(console_handler)
            
            # Create logs directory
            logs_dir = Path(__file__).parent.parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            # Create file handler
            log_file = logs_dir / f"{name or 'agent'}.log"
            file_handler = TimedRotatingFileHandler(
                str(log_file),
                when="midnight",
                interval=1,
                backupCount=30,
                encoding='utf-8'  # Use UTF-8 encoding for Unicode characters
            )
            file_handler.setLevel(log_level)
            file_format = logging.Formatter('%(asctime)s - %(name)s - %(method_name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        
        return logger
    
    # Handle legacy signature (config dict)
    # Get log level from config
    log_level_str = config["logging"]["level"]
    log_level = getattr(logging, log_level_str)
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with colored formatter (includes method name)
    # Use UTF-8 encoding to support Unicode characters (₹, ✅, etc.)
    import sys
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = ColoredFormatter('%(asctime)s - %(name)s - %(method_name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    # Force UTF-8 encoding on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    root_logger.addHandler(console_handler)
    
    # Create file handler with rotation
    log_file = os.path.join(logs_dir, "agent.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # Keep logs for 30 days
        encoding='utf-8'  # Use UTF-8 encoding for Unicode characters
    )
    file_handler.setLevel(log_level)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(method_name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # Create specific loggers for components
    components = ["mstock_api", "orchestrator", "strategy_factory", "market_data_runner", "signal_manager"]
    
    for component in components:
        logger = logging.getLogger(component)
        logger.setLevel(log_level)
        
        # Create component-specific log file
        component_log_file = os.path.join(logs_dir, f"{component}.log")
        component_handler = TimedRotatingFileHandler(
            component_log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding='utf-8'  # Use UTF-8 encoding for Unicode characters
        )
        component_handler.setLevel(log_level)
        component_handler.setFormatter(file_format)
        logger.addHandler(component_handler)
    
    return root_logger


def log_method(func):
    """
    Decorator to automatically add method name to log messages.
    
    Usage:
        @log_method
        def my_method(self):
            self.logger.info("This will include method name automatically")
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Try to get the logger from self or cls
        logger = None
        if args and hasattr(args[0], 'logger'):
            logger = args[0].logger
        
        if logger:
            # Create a custom adapter that adds method name
            class MethodAdapter(logging.LoggerAdapter):
                def process(self, msg, kwargs):
                    # Add method name to extra
                    if 'extra' not in kwargs:
                        kwargs['extra'] = {}
                    kwargs['extra']['method_name'] = f"{args[0].__class__.__name__}.{func.__name__}"
                    return msg, kwargs
            
            # Temporarily replace the logger
            original_logger = args[0].logger
            args[0].logger = MethodAdapter(logger, {})
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore original logger
                args[0].logger = original_logger
        else:
            # No logger found, just call the function
            return func(*args, **kwargs)
    
    return wrapper


def get_method_logger(logger, class_name, method_name):
    """
    Get a logger adapter that includes method name.
    
    Usage:
        logger = get_method_logger(self.logger, self.__class__.__name__, 'my_method')
        logger.info("This will include the method name")
    
    Args:
        logger: The base logger instance
        class_name: Name of the class
        method_name: Name of the method
        
    Returns:
        LoggerAdapter with method name included
    """
    class MethodAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra']['method_name'] = f"{class_name}.{method_name}"
            return msg, kwargs
    
    return MethodAdapter(logger, {})