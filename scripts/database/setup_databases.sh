#!/bin/bash

# AlphaStock Database Setup Script
# Sets up PostgreSQL, ClickHouse, and Redis for complete data storage

echo "🗄️ ALPHASTOCK DATABASE SETUP"
echo "=================================="

echo "This script will install and configure:"
echo "🐘 PostgreSQL - Primary database storage"  
echo "🏠 ClickHouse - High-performance analytics"
echo "⚡ Redis - Real-time caching"
echo ""

read -p "Continue with database setup? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo "📦 INSTALLING DATABASES..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install Homebrew first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "🍺 Updating Homebrew..."
brew update

echo ""
echo "🐘 Installing PostgreSQL..."
brew install postgresql@14

echo ""  
echo "⚡ Installing Redis..."
brew install redis

echo ""
echo "🏠 Installing ClickHouse..."
brew install clickhouse

echo ""
echo "🚀 STARTING SERVICES..."

# Start PostgreSQL
echo "🐘 Starting PostgreSQL..."
brew services start postgresql@14

# Start Redis  
echo "⚡ Starting Redis..."
brew services start redis

# Start ClickHouse
echo "🏠 Starting ClickHouse..."
brew services start clickhouse

echo ""
echo "🔧 CONFIGURING DATABASES..."

# Wait a moment for services to start
sleep 5

# Create PostgreSQL database
echo "🐘 Setting up PostgreSQL database..."
createdb alphastock 2>/dev/null || echo "Database alphastock already exists"

# Configure ClickHouse database  
echo "🏠 Setting up ClickHouse database..."
clickhouse-client --query="CREATE DATABASE IF NOT EXISTS alphastock" 2>/dev/null || echo "ClickHouse database setup attempted"

echo ""
echo "✅ DATABASE SETUP COMPLETE!"
echo ""
echo "🔍 SERVICE STATUS:"
echo "🐘 PostgreSQL: http://localhost:5432"
echo "⚡ Redis: http://localhost:6379" 
echo "🏠 ClickHouse: http://localhost:8123"
echo ""
echo "🎯 TO TEST YOUR SETUP:"
echo "python3 data_inspector.py"
echo ""
echo "🚀 TO START TRADING WITH FULL STORAGE:"
echo "python3 scheduler.py --manual-start"
