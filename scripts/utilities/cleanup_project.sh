#!/bin/bash
# AlphaStock Project Cleanup Script
# Run this to maintain clean project structure

set -e

echo "🧹 ALPHASTOCK PROJECT CLEANUP"
echo "=============================="

# Create directories if they don't exist
mkdir -p scripts/database
mkdir -p scripts/utilities  
mkdir -p docs/guides
mkdir -p archive/old_implementations

echo "📦 Moving database scripts..."
[ -f setup_clickhouse.sh ] && mv setup_clickhouse.sh scripts/database/
[ -f setup_clickhouse_docker.sh ] && mv setup_clickhouse_docker.sh scripts/database/
[ -f setup_databases.sh ] && mv setup_databases.sh scripts/database/
[ -f setup_database.py ] && mv setup_database.py scripts/database/
[ -f migrate_database.py ] && mv migrate_database.py scripts/database/
[ -f clickhouse_queries.sql ] && mv clickhouse_queries.sql scripts/database/

echo "🔧 Moving utility scripts..."
[ -f fix_and_import.py ] && mv fix_and_import.py scripts/utilities/
[ -f import_signals.py ] && mv import_signals.py scripts/utilities/
[ -f import_signals_fixed.py ] && mv import_signals_fixed.py scripts/utilities/
[ -f analytics_demo.sh ] && mv analytics_demo.sh scripts/utilities/
[ -f data_inspector.py ] && mv data_inspector.py scripts/utilities/
[ -f data_viewer.py ] && mv data_viewer.py scripts/utilities/
[ -f daily_summary_example.py ] && mv daily_summary_example.py scripts/utilities/

echo "🧪 Moving test and validation files..."
[ -f test_api_pipeline.py ] && mv test_api_pipeline.py scripts/utilities/
[ -f test_complete_system.py ] && mv test_complete_system.py scripts/utilities/
[ -f test_current_system.py ] && mv test_current_system.py scripts/utilities/
[ -f validate_system.py ] && mv validate_system.py scripts/utilities/
[ -f demo_runners.py ] && mv demo_runners.py scripts/utilities/
[ -f examples.py ] && mv examples.py scripts/utilities/

echo "🔑 Moving helper scripts..."
[ -f get_auth_url.py ] && mv get_auth_url.py scripts/utilities/
[ -f check_permissions.py ] && mv check_permissions.py scripts/utilities/
[ -f auth_helper.py ] && mv auth_helper.py scripts/utilities/

echo "📚 Moving documentation..."
[ -f COMPLETE_WORKFLOW_GUIDE.md ] && mv COMPLETE_WORKFLOW_GUIDE.md docs/guides/
[ -f DATA_STORAGE_GUIDE.md ] && mv DATA_STORAGE_GUIDE.md docs/guides/
[ -f README_AUTOMATION.md ] && mv README_AUTOMATION.md docs/guides/
[ -f NEW_ARCHITECTURE_COMPLETE.md ] && mv NEW_ARCHITECTURE_COMPLETE.md docs/guides/
[ -f NEW_ARCHITECTURE_README.md ] && mv NEW_ARCHITECTURE_README.md docs/guides/
[ -f IMPLEMENTATION_COMPLETE.md ] && mv IMPLEMENTATION_COMPLETE.md docs/guides/
[ -f DEPLOYMENT_GUIDE.py ] && mv DEPLOYMENT_GUIDE.py docs/guides/

echo "🗂️ Moving old implementations..."
[ -f backtest_old.py ] && mv backtest_old.py archive/old_implementations/
[ -f main_old.py ] && mv main_old.py archive/old_implementations/

echo "🗑️ Removing temporary files..."
[ -f import_to_clickhouse.sh ] && rm -f import_to_clickhouse.sh
[ -f trading_signals_import.csv ] && rm -f trading_signals_import.csv

echo "🧹 Cleaning data directory..."
[ -f data/historical/fixed_*.csv ] && rm -f data/historical/fixed_*.csv

echo ""
echo "✅ PROJECT CLEANUP COMPLETE!"
echo ""
echo "📂 Clean Structure Maintained:"
echo "  Root: Core application files only"
echo "  scripts/database/: Database setup scripts"
echo "  scripts/utilities/: Helper scripts and tools"
echo "  docs/guides/: Documentation and guides"
echo "  archive/: Old implementations preserved"
echo ""
echo "🚀 Ready for development and deployment!"
