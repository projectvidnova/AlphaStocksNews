#!/bin/bash

# AlphaStock - Quick Test Script
# Run this after getting a fresh access token

echo "🚀 AlphaStock Quick Test"
echo "========================"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env.dev exists
if [ ! -f ".env.dev" ]; then
    echo "❌ Error: .env.dev file not found"
    echo "   Please create it with your Kite API credentials"
    exit 1
fi

# Test authentication
echo "🔐 Testing Kite API authentication..."
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv('.env.dev')
from kiteconnect import KiteConnect

api_key = os.getenv('KITE_API_KEY')
access_token = os.getenv('KITE_ACCESS_TOKEN')

if not api_key or not access_token:
    print('❌ Missing credentials in .env.dev')
    exit(1)

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

try:
    profile = kite.profile()
    print('✅ Authentication successful!')
    print(f'   User: {profile.get(\"user_name\")}')
    print(f'   Email: {profile.get(\"email\")}')
except Exception as e:
    print(f'❌ Authentication failed: {e}')
    print('')
    print('💡 To get a fresh access token:')
    print('   1. Run: python3 generate_access_token.py')
    print('   2. Or visit: https://kite.zerodha.com/connect/login?api_key=' + api_key + '&v=3')
    exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo "🗄️  Checking ClickHouse database..."
python3 -c "
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import json

with open('config/database.json') as f:
    db_config = json.load(f)['development']

try:
    db = ClickHouseDataLayer(db_config)
    if db.health_check():
        print('✅ ClickHouse connection successful')
    else:
        print('❌ ClickHouse health check failed')
        exit(1)
except Exception as e:
    print(f'❌ Database error: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo "✅ All preliminary checks passed!"
echo ""
echo "🎯 Ready to run complete workflow"
echo ""
read -p "Run complete workflow now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Running complete workflow..."
    echo "   (This may take 10-15 minutes for historical data download)"
    echo ""
    python3 complete_workflow.py
else
    echo "Skipped. You can run it manually with: python3 complete_workflow.py"
fi
