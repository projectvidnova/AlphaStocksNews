#!/usr/bin/env python3
"""
Generate Kite Access Token from Request Token
"""
import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load environment variables
load_dotenv('.env.dev')

api_key = os.getenv('KITE_API_KEY')
api_secret = os.getenv('KITE_API_SECRET')

if not api_key or not api_secret:
    print("❌ Error: KITE_API_KEY or KITE_API_SECRET not found in .env.dev")
    exit(1)

print("\n" + "="*80)
print("🔑 GENERATE KITE ACCESS TOKEN")
print("="*80)
print(f"\n✅ Using API Key: {api_key[:8]}...{api_key[-4:]}")

# Get request token from user
print("\n📋 STEP 1: Enter the request_token you copied from the redirect URL")
print("(The long string after 'request_token=' in the browser)")
request_token = input("\nPaste request_token here: ").strip()

if not request_token:
    print("❌ Error: No request token provided")
    exit(1)

print(f"\n✅ Request Token received: {request_token[:10]}...{request_token[-10:]}")

# Generate session
try:
    print("\n⏳ Generating access token...")
    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    
    access_token = data['access_token']
    
    print("\n" + "="*80)
    print("🎉 SUCCESS! ACCESS TOKEN GENERATED")
    print("="*80)
    print(f"\n🔑 Your Access Token:")
    print(f"   {access_token}")
    print("\n📋 NEXT STEPS:")
    print("   1. Copy the access token above")
    print("   2. Open .env.dev file")
    print("   3. Replace 'your_access_token_here' with this token")
    print("   4. Save the file")
    print("\n⚠️  NOTE: This token expires after 24 hours (end of trading day)")
    print("   You'll need to regenerate it tomorrow using the same process")
    print("\n" + "="*80)
    
    # Optionally auto-update .env.dev
    update = input("\n❓ Would you like me to automatically update .env.dev? (y/n): ").strip().lower()
    if update == 'y':
        with open('.env.dev', 'r') as f:
            content = f.read()
        
        # Replace the access token line
        if 'KITE_ACCESS_TOKEN=' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('KITE_ACCESS_TOKEN='):
                    lines[i] = f'KITE_ACCESS_TOKEN={access_token}'
                    break
            
            with open('.env.dev', 'w') as f:
                f.write('\n'.join(lines))
            
            print("\n✅ .env.dev updated successfully!")
            print("🚀 You can now run: python3 complete_workflow.py")
        else:
            print("\n⚠️  Could not find KITE_ACCESS_TOKEN in .env.dev")
            print("   Please update it manually")
    
except Exception as e:
    print(f"\n❌ Error generating access token: {e}")
    print("\n💡 Possible reasons:")
    print("   - Request token has expired (valid for ~5 minutes)")
    print("   - API Secret is incorrect")
    print("   - Request token was already used")
    print("\n🔄 Solution: Get a fresh request token by visiting the login URL again")
    exit(1)
