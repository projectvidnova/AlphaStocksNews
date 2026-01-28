#!/usr/bin/env python3
"""Test data layer initialization"""
import json
import asyncio
from src.data.data_layer_factory import data_layer_factory

with open('config/database.json', 'r') as f:
    db_config = json.load(f)
    
env = db_config.get('default', 'development')
storage_config = db_config.get(env, {})

try:
    data_layer = data_layer_factory.create_from_config(storage_config)
    print(f'✅ Data layer created: {type(data_layer).__name__}')
    
    async def test():
        success = await data_layer.initialize()
        print(f'Initialization: {"✅ Success" if success else "❌ Failed"}')
        if success:
            health = await data_layer.health_check()
            print(f'Health status: {health.get("overall_status")}')
            print(f'ClickHouse connected: {health.get("clickhouse", {}).get("status")}')
            await data_layer.close()
        return success
    
    result = asyncio.run(test())
    print(f'\n{"🎉 AlphaStock data layer is ready!" if result else "⚠️  Data layer initialization failed"}')
except Exception as e:
    import traceback
    print(f'❌ Error: {e}')
    traceback.print_exc()
