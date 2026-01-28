# AlphaStock Project Structure Guide
# Run ./cleanup_project.sh if files get disorganized

## 🎯 CORE FILES (Keep at Root)
- main.py                 # Main application entry point
- complete_workflow.py    # Complete trading workflow  
- scheduler.py           # Automated task scheduler
- cli.py                 # Command line interface
- requirements.txt       # Python dependencies
- README.md             # Project documentation
- cleanup_project.sh    # Project organization script

## 📁 ORGANIZED FOLDERS

### scripts/database/
- setup_clickhouse.sh
- setup_clickhouse_docker.sh  
- setup_databases.sh
- setup_database.py
- migrate_database.py
- clickhouse_queries.sql

### scripts/utilities/
- All helper scripts, tests, and tools
- Data analysis and import utilities
- Authentication helpers
- System validation tools

### docs/guides/
- All documentation and implementation guides
- Architecture documentation
- Deployment guides

### archive/old_implementations/
- Deprecated code versions
- Old implementations for reference

## 🚀 USAGE

If files get disorganized, run:
```bash
./cleanup_project.sh
```

This will automatically reorganize everything according to the proper structure!
