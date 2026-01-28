#!/bin/bash

# AlphaStock Temporary Files Cleanup Script
# Removes temporary files created during testing and execution

echo "🧹 AlphaStock Cleanup - Removing Temporary Files"
echo "================================================="
echo ""

DELETED_COUNT=0

# 1. Remove workflow output files (can be regenerated)
echo "📄 Cleaning workflow output files..."
if [ -f "workflow_output.log" ]; then
    rm workflow_output.log
    echo "   ✓ Deleted: workflow_output.log"
    ((DELETED_COUNT++))
fi

if [ -f "workflow_results.json" ]; then
    rm workflow_results.json
    echo "   ✓ Deleted: workflow_results.json"
    ((DELETED_COUNT++))
fi

# 2. Remove Python cache directories (__pycache__)
echo ""
echo "🐍 Cleaning Python cache files..."
PYCACHE_COUNT=$(find ./src ./tests -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    find ./src ./tests -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    echo "   ✓ Deleted: $PYCACHE_COUNT __pycache__ directories"
    ((DELETED_COUNT+=$PYCACHE_COUNT))
fi

# 3. Remove .pyc files
echo ""
echo "🔧 Cleaning compiled Python files..."
PYC_COUNT=$(find ./src ./tests -type f -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYC_COUNT" -gt 0 ]; then
    find ./src ./tests -type f -name "*.pyc" -delete 2>/dev/null
    echo "   ✓ Deleted: $PYC_COUNT .pyc files"
    ((DELETED_COUNT+=$PYC_COUNT))
fi

# 4. Remove .DS_Store files (macOS)
echo ""
echo "🍎 Cleaning macOS system files..."
DS_COUNT=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DS_COUNT" -gt 0 ]; then
    find . -name ".DS_Store" -delete 2>/dev/null
    echo "   ✓ Deleted: $DS_COUNT .DS_Store files"
    ((DELETED_COUNT+=$DS_COUNT))
fi

# 5. List what we're keeping (important files)
echo ""
echo "📋 Keeping important files:"
echo "   ✓ .env.dev (API credentials)"
echo "   ✓ config/ (configuration files)"
echo "   ✓ logs/ (system logs for debugging)"
echo "   ✓ venv/ (Python virtual environment)"
echo "   ✓ src/ (source code)"
echo "   ✓ data/ (historical data in ClickHouse)"

echo ""
echo "================================================="
echo "✅ Cleanup Complete!"
echo "   Removed: $DELETED_COUNT temporary files/directories"
echo "================================================="
echo ""
