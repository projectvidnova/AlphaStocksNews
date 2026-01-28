#!/usr/bin/env python3
"""
Authentication Manager for AlphaStock Trading System
Handles Kite Connect OAuth flow with integrated browser-based authentication.
"""

import asyncio
import logging
import webbrowser
from typing import Optional, Dict, Any
from pathlib import Path

from kiteconnect import KiteConnect

from src.utils.secrets_manager import get_secrets_manager
from src.utils.logger_setup import setup_logger


class AuthenticationManager:
    """
    Manages Kite Connect authentication with seamless OAuth flow.
    
    This class provides:
    - Automatic token validation and refresh
    - Integrated browser-based login
    - Silent re-authentication when needed
    - Token persistence to .env.dev
    """
    
    def __init__(self, secrets_manager=None):
        """
        Initialize the authentication manager.
        
        Args:
            secrets_manager: Optional SecretsManager instance
        """
        self.secrets = secrets_manager or get_secrets_manager()
        self.logger = setup_logger("auth_manager")
        
        # Get credentials
        self.creds = self.secrets.get_kite_credentials()
        self.api_key = self.creds['api_key']
        self.api_secret = self.creds['api_secret']
        self.access_token = self.creds['access_token']
        
        # Kite client for auth
        self.kite = None
        self.authenticated = False
        
        # State
        self._auth_in_progress = False
    
    async def ensure_authenticated(self, interactive: bool = True) -> bool:
        """
        Ensure the user is authenticated, prompting if necessary.
        
        Args:
            interactive: If True, will open browser and prompt for token
                        If False, will only use existing token
        
        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Validate credentials
            if not self.api_key or not self.api_secret:
                self.logger.error("Missing API credentials. Please update .env.dev file")
                self._show_setup_instructions()
                return False
            
            # Initialize Kite client if needed
            if not self.kite:
                self.kite = KiteConnect(api_key=self.api_key)
            
            # Try existing access token first
            if self.access_token:
                self.logger.info("Validating existing access token...")
                if await self._validate_token(self.access_token):
                    self.authenticated = True
                    self.logger.info("[SUCCESS] Already authenticated")
                    return True
                else:
                    self.logger.warning("Access token is invalid or expired")
            
            # Need to authenticate
            if not interactive:
                self.logger.error("Authentication required but running in non-interactive mode")
                return False
            
            # Start interactive authentication
            return await self._interactive_authenticate()
            
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    async def _validate_token(self, token: str) -> bool:
        """
        Validate an access token by making a test API call.
        
        Args:
            token: Access token to validate
            
        Returns:
            True if token is valid
        """
        try:
            self.kite.set_access_token(token)
            # Test with profile API call
            profile = self.kite.profile()
            if profile and 'user_id' in profile:
                self.logger.info(f"Token valid for user: {profile.get('user_name', 'Unknown')}")
                return True
            return False
        except Exception as e:
            self.logger.debug(f"Token validation failed: {e}")
            return False
    
    async def _interactive_authenticate(self) -> bool:
        """
        Perform interactive authentication with browser.
        
        Returns:
            True if authentication successful
        """
        if self._auth_in_progress:
            self.logger.warning("Authentication already in progress")
            return False
        
        try:
            self._auth_in_progress = True
            
            # Generate login URL
            login_url = self.kite.login_url()
            
            print("\n" + "=" * 80)
            print("🔑 KITE CONNECT AUTHENTICATION REQUIRED")
            print("=" * 80)
            print("\n📋 Authentication Steps:")
            print("1. Your browser will open with the Kite login page")
            print("2. Login with your Zerodha credentials")
            print("3. After successful login, copy the 'request_token' from the URL")
            print("4. Paste it back here when prompted")
            print("\n" + "-" * 80)
            
            # Open browser automatically
            print("🌐 Opening browser for authentication...")
            opened = webbrowser.open(login_url)
            
            if not opened:
                print("\n⚠️ Could not open browser automatically.")
                print(f"Please manually open this URL:\n{login_url}")
            
            print("\n" + "-" * 80)
            print("After login, the URL will look like:")
            print("https://127.0.0.1:8080/?request_token=XXXXXX&action=login&status=success")
            print("                              ^^^^^^^^^^^^^^^^^^^^^^^^")
            print("                              Copy this part!")
            print("-" * 80)
            
            # Get request token from user
            request_token = await self._prompt_for_token()
            
            if not request_token:
                print("❌ No request token provided. Authentication cancelled.")
                return False
            
            # Generate session
            print("\n🔄 Generating session...")
            session_data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            
            # Store access token
            self.access_token = session_data['access_token']
            self.kite.set_access_token(self.access_token)
            
            # Persist to .env.dev
            await self._save_access_token(self.access_token)
            
            # Update secrets manager
            self.secrets.update_access_token(self.access_token)
            
            self.authenticated = True
            
            # Show success info
            print("\n" + "=" * 80)
            print("✅ AUTHENTICATION SUCCESSFUL!")
            print("=" * 80)
            print(f"✓ User: {session_data.get('user_name', 'Unknown')}")
            print(f"✓ User ID: {session_data.get('user_id', 'Unknown')}")
            print(f"✓ Email: {session_data.get('email', 'Unknown')}")
            print(f"✓ Access token saved to .env.dev")
            print("=" * 80 + "\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Authentication failed: {e}")
            self.logger.error(f"Authentication failed: {e}")
            return False
        finally:
            self._auth_in_progress = False
    
    async def _prompt_for_token(self) -> Optional[str]:
        """
        Prompt user for request token.
        
        Returns:
            Request token or None
        """
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            token = await loop.run_in_executor(
                None,
                lambda: input("\n🔑 Paste the request_token here: ").strip()
            )
            return token if token else None
        except Exception as e:
            self.logger.error(f"Error getting token input: {e}")
            return None
    
    async def _save_access_token(self, access_token: str):
        """
        Save access token to .env.dev file.
        
        Args:
            access_token: Access token to save
        """
        try:
            env_file = Path(".env.dev")
            
            if not env_file.exists():
                self.logger.warning(".env.dev not found, creating new file")
                # Create from template
                template = Path(".env.example")
                if template.exists():
                    with open(template, 'r') as f:
                        content = f.read()
                    with open(env_file, 'w') as f:
                        f.write(content)
            
            # Read current content
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Update or add access token
            token_found = False
            updated_lines = []
            
            for line in lines:
                if line.startswith('KITE_ACCESS_TOKEN='):
                    updated_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                    token_found = True
                else:
                    updated_lines.append(line)
            
            # Add if not found
            if not token_found:
                updated_lines.append(f'\nKITE_ACCESS_TOKEN={access_token}\n')
            
            # Write back
            with open(env_file, 'w') as f:
                f.writelines(updated_lines)
            
            self.logger.info("Access token saved to .env.dev")
            
        except Exception as e:
            self.logger.error(f"Failed to save access token: {e}")
            self.logger.info(f"Please manually add to .env.dev: KITE_ACCESS_TOKEN={access_token}")
    
    def _show_setup_instructions(self):
        """Show setup instructions for missing credentials."""
        print("\n" + "=" * 80)
        print("⚠️ SETUP REQUIRED")
        print("=" * 80)
        print("\n📋 To use AlphaStock, you need to set up Kite Connect credentials:")
        print("\n1. Get API credentials:")
        print("   • Visit: https://kite.zerodha.com/apps")
        print("   • Create a new app or use existing one")
        print("   • Note down your API Key and API Secret")
        print("\n2. Update .env.dev file:")
        print("   • Open .env.dev in project root")
        print("   • Set KITE_API_KEY=your_api_key")
        print("   • Set KITE_API_SECRET=your_api_secret")
        print("\n3. Restart the application")
        print("   • The system will guide you through authentication")
        print("\n" + "=" * 80 + "\n")
    
    def get_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get user profile information.
        
        Returns:
            Profile dict or None if not authenticated
        """
        if not self.authenticated or not self.kite:
            return None
        
        try:
            return self.kite.profile()
        except Exception as e:
            self.logger.error(f"Failed to get profile: {e}")
            return None
    
    def invalidate_token(self):
        """Invalidate the current access token."""
        try:
            if self.kite and self.access_token:
                self.kite.invalidate_access_token(self.access_token)
            self.authenticated = False
            self.access_token = None
            self.logger.info("Access token invalidated")
        except Exception as e:
            self.logger.error(f"Failed to invalidate token: {e}")


# Singleton instance
_auth_manager_instance = None


def get_auth_manager(secrets_manager=None) -> AuthenticationManager:
    """
    Get the singleton authentication manager instance.
    
    Args:
        secrets_manager: Optional SecretsManager instance
        
    Returns:
        AuthenticationManager instance
    """
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthenticationManager(secrets_manager)
    return _auth_manager_instance
