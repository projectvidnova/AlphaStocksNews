#!/usr/bin/env python3
"""Quick test of integrated authentication"""

import asyncio
from src.auth import get_auth_manager

async def test_auth():
    print("\n🔍 Testing Integrated Authentication System...")
    print("=" * 60)
    
    auth = get_auth_manager()
    
    # Test authentication
    authenticated = await auth.ensure_authenticated(interactive=False)
    
    if authenticated:
        profile = auth.get_profile()
        print("\n✅ AUTHENTICATION SUCCESSFUL!")
        print("=" * 60)
        print(f"👤 User: {profile['user_name']}")
        print(f"📧 Email: {profile['email']}")
        print(f"🆔 User ID: {profile['user_id']}")
        print(f"🏢 Broker: {profile['broker']}")
        print(f"📱 User Type: {profile.get('user_type', 'N/A')}")
        print("=" * 60)
        print("\n✨ You're all set! Run 'python main.py' to start trading.")
    else:
        print("\n❌ Not authenticated")
        print("Run: python cli.py auth")

if __name__ == "__main__":
    asyncio.run(test_auth())
