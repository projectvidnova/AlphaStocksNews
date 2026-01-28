#!/usr/bin/env python3
"""
Kite Connect Authentication Helper
Generates login URL and helps you get the request token
"""

import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load environment
load_dotenv('.env.dev')

# Get your API key
api_key = os.getenv('KITE_API_KEY')
print(f"Using API Key: {api_key[:4]}...{api_key[-4:]}")

# Create Kite Connect instance
kite = KiteConnect(api_key=api_key)

# Generate login URL
login_url = kite.login_url()

print("\n" + "="*80)
print("🔑 KITE CONNECT AUTHENTICATION - GET REQUEST TOKEN")
print("="*80)
print("\n📋 STEP-BY-STEP INSTRUCTIONS:")
print("\n1. 🌐 OPEN THIS URL IN YOUR BROWSER:")
print(f"   {login_url}")
print("\n2. 🔐 LOGIN with your Zerodha credentials (User ID + Password + 2FA)")
print("\n3. ✅ After successful login, you'll be redirected to a URL that looks like:")
print("   https://127.0.0.1:8080/?request_token=XXXXXXXXXXXXXXXXXXXXXX&action=login&status=success")
print("\n4. 📋 COPY the 'request_token' value from that URL")
print("   (It's the long string after 'request_token=')")
print("\n5. 🎯 PASTE that token when prompted by the test script")
print("\n" + "="*80)
print("💡 TIP: The request token is valid for only a few minutes, so use it quickly!")
print("="*80)

# Also show what the redirect URL will look like
print("\n🔍 WHAT TO LOOK FOR IN THE REDIRECT URL:")
print("The browser will redirect to something like:")
print("https://127.0.0.1:8080/?request_token=abcd1234efgh5678ijkl&action=login&status=success")
print("                                     ^^^^^^^^^^^^^^^^^^^^^^^^")
print("                                     THIS IS YOUR REQUEST TOKEN")
