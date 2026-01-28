#!/usr/bin/env python3
"""
Quick Token Tester - Tests if your current access token is valid
"""
import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load environment variables
load_dotenv('.env.dev')

api_key = os.getenv('KITE_API_KEY')
api_secret = os.getenv('KITE_API_SECRET')
access_token = os.getenv('KITE_ACCESS_TOKEN')

print("\n" + "="*80)
print("🔐 KITE ACCESS TOKEN VALIDATOR")
print("="*80)

# Check credentials exist
if not api_key or not api_secret:
    print("\n❌ Error: Missing API credentials in .env.dev")
    exit(1)

if not access_token:
    print("\n❌ Error: No KITE_ACCESS_TOKEN found in .env.dev")
    print("\n💡 Generate one with: python3 generate_access_token.py")
    exit(1)

# Display info
print(f"\n📋 Current Configuration:")
print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
print(f"   API Secret: {api_secret[:8]}...{api_secret[-4:]}")
print(f"   Access Token: {access_token[:10]}...{access_token[-10:]}")

# Test authentication
print(f"\n⏳ Testing authentication...")
try:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    profile = kite.profile()
    
    print("\n" + "="*80)
    print("✅ AUTHENTICATION SUCCESSFUL!")
    print("="*80)
    print(f"\n👤 Profile Information:")
    print(f"   User ID: {profile.get('user_id')}")
    print(f"   User Name: {profile.get('user_name')}")
    print(f"   Email: {profile.get('email')}")
    print(f"   Broker: {profile.get('broker')}")
    print(f"   User Type: {profile.get('user_type')}")
    print(f"\n🎉 System is ready to use!")
    print("🚀 Run: python3 complete_workflow.py")
    print("="*80 + "\n")
    
except Exception as e:
    print("\n" + "="*80)
    print("❌ AUTHENTICATION FAILED")
    print("="*80)
    print(f"\n🔴 Error: {e}")
    print("\n💡 This usually means:")
    print("   1. Access token has expired (tokens last ~24 hours)")
    print("   2. Invalid request_token was used during generation")
    print("   3. API credentials don't match")
    print("\n🔄 TO FIX:")
    print("   Step 1: Get a fresh request token")
    print(f"           Visit: https://kite.zerodha.com/connect/login?api_key={api_key}&v=3")
    print("   Step 2: Login with your Zerodha credentials")
    print("   Step 3: Copy the request_token from redirect URL")
    print("   Step 4: Run: python3 generate_access_token.py")
    print("   Step 5: Paste the request_token when prompted")
    print("="*80 + "\n")
    exit(1)
