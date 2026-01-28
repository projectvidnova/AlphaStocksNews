"""
Secrets Manager for AlphaStock Trading System
Handles loading and managing API credentials and secrets.
"""

import os
import logging
from typing import Dict, Optional
from pathlib import Path

from .logger_setup import setup_logger


class SecretsManager:
    """
    Manages API credentials and secrets for the trading system.
    Loads from .env files and environment variables.
    """
    
    def __init__(self, env_file: str = ".env.dev"):
        """
        Initialize the secrets manager.
        
        Args:
            env_file: Path to the environment file containing secrets
        """
        self.env_file = env_file
        self.secrets: Dict[str, str] = {}
        self.logger = setup_logger("secrets_manager")
        
        # Load secrets from file and environment
        self._load_secrets()
    
    def _load_secrets(self):
        """Load secrets from environment file and system environment."""
        try:
            # First try to load from .env file
            env_path = Path(self.env_file)
            if env_path.exists():
                self._load_from_file(env_path)
                self.logger.info(f"Loaded secrets from {self.env_file}")
            else:
                self.logger.warning(f"Environment file {self.env_file} not found")
            
            # Override with system environment variables
            self._load_from_environment()
            
            # Validate required secrets
            self._validate_secrets()
            
        except Exception as e:
            self.logger.error(f"Error loading secrets: {e}")
            raise
    
    def _load_from_file(self, env_path: Path):
        """Load secrets from environment file."""
        try:
            with open(env_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')  # Remove quotes
                        if value:  # Only store non-empty values
                            self.secrets[key] = value
        except Exception as e:
            self.logger.error(f"Error reading env file: {e}")
            raise
    
    def _load_from_environment(self):
        """Load secrets from system environment variables."""
        env_keys = [
            'KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN',
            'KITE_REQUEST_TOKEN', 'KITE_USER_ID', 'DEBUG_MODE',
            'LOG_LEVEL', 'PAPER_TRADING', 'PAPER_CAPITAL'
        ]
        
        for key in env_keys:
            value = os.getenv(key)
            if value:
                self.secrets[key] = value
    
    def _validate_secrets(self):
        """Validate that required secrets are present."""
        required_keys = ['KITE_API_KEY']
        missing_keys = []
        
        for key in required_keys:
            if not self.get(key):
                missing_keys.append(key)
        
        if missing_keys:
            self.logger.warning(f"Missing required secrets: {missing_keys}")
            self.logger.info("Please add these keys to your .env.dev file")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value by key.
        
        Args:
            key: The secret key to retrieve
            default: Default value if key not found
        
        Returns:
            Secret value or default
        """
        return self.secrets.get(key, default)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Get a boolean secret value.
        
        Args:
            key: The secret key to retrieve
            default: Default boolean value
        
        Returns:
            Boolean value
        """
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        Get an integer secret value.
        
        Args:
            key: The secret key to retrieve  
            default: Default integer value
        
        Returns:
            Integer value
        """
        try:
            return int(self.get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        Get a float secret value.
        
        Args:
            key: The secret key to retrieve
            default: Default float value
        
        Returns:
            Float value  
        """
        try:
            return float(self.get(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    def has_key(self, key: str) -> bool:
        """Check if a secret key exists and has a non-empty value."""
        return bool(self.get(key))
    
    def get_kite_credentials(self) -> Dict[str, str]:
        """
        Get Kite Connect API credentials.
        
        Returns:
            Dictionary with Kite credentials
        """
        return {
            'api_key': self.get('KITE_API_KEY', ''),
            'api_secret': self.get('KITE_API_SECRET', ''),
            'access_token': self.get('KITE_ACCESS_TOKEN', ''),
            'request_token': self.get('KITE_REQUEST_TOKEN', ''),
            'user_id': self.get('KITE_USER_ID', '')
        }
    
    def is_authenticated(self) -> bool:
        """Check if we have sufficient credentials for API access."""
        creds = self.get_kite_credentials()
        return bool(creds['api_key'] and (creds['access_token'] or creds['request_token']))
    
    def get_trading_config(self) -> Dict[str, any]:
        """
        Get trading configuration settings.
        
        Returns:
            Dictionary with trading settings
        """
        return {
            'paper_trading': self.get_bool('PAPER_TRADING', True),
            'paper_capital': self.get_int('PAPER_CAPITAL', 100000),
            'debug_mode': self.get_bool('DEBUG_MODE', True),
            'log_level': self.get('LOG_LEVEL', 'INFO'),
            'max_positions_per_day': self.get_int('MAX_POSITIONS_PER_DAY', 3),
            'max_loss_per_day': self.get_int('MAX_LOSS_PER_DAY', 5000),
            'max_position_size': self.get_int('MAX_POSITION_SIZE', 10000)
        }
    
    def update_access_token(self, access_token: str):
        """
        Update the access token (useful after OAuth flow).
        
        Args:
            access_token: New access token
        """
        self.secrets['KITE_ACCESS_TOKEN'] = access_token
        self.logger.info("Access token updated")
    
    def list_available_keys(self) -> list:
        """List all available secret keys (for debugging)."""
        return list(self.secrets.keys())
    
    def get_masked_secrets(self) -> Dict[str, str]:
        """Get secrets with masked values (for safe logging)."""
        masked = {}
        for key, value in self.secrets.items():
            if value and len(value) > 4:
                masked[key] = value[:4] + '*' * (len(value) - 4)
            else:
                masked[key] = '*' * len(value) if value else 'Not set'
        return masked


# Global secrets manager instance
_secrets_manager = None

def get_secrets_manager(env_file: str = ".env.dev") -> SecretsManager:
    """
    Get the global secrets manager instance.
    
    Args:
        env_file: Environment file path
    
    Returns:
        SecretsManager instance
    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(env_file)
    return _secrets_manager


# Convenience functions
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret value."""
    return get_secrets_manager().get(key, default)

def get_kite_credentials() -> Dict[str, str]:
    """Get Kite Connect credentials."""
    return get_secrets_manager().get_kite_credentials()

def is_authenticated() -> bool:
    """Check if authenticated with Kite."""
    return get_secrets_manager().is_authenticated()


if __name__ == "__main__":
    # Test the secrets manager
    import logging
    logging.basicConfig(level=logging.INFO)
    
    secrets = SecretsManager()
    print("Available secrets:")
    for key in secrets.list_available_keys():
        print(f"  {key}")
    
    print("\nMasked secrets:")
    masked = secrets.get_masked_secrets()
    for key, value in masked.items():
        print(f"  {key}: {value}")
    
    print(f"\nAuthenticated: {secrets.is_authenticated()}")
    print(f"Trading config: {secrets.get_trading_config()}")
