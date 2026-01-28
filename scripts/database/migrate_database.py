#!/usr/bin/env python3
"""
Database Schema Migration Script

Creates the necessary database schemas and tables for AlphaStock.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.data_layer_factory import data_layer_factory
from src.utils.logger_setup import setup_logger


class DatabaseMigration:
    """Database migration manager."""
    
    def __init__(self, config_path=None):
        self.logger = setup_logger("DatabaseMigration")
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "database.json"
        self.data_layer = None
    
    async def load_config_and_create_data_layer(self):
        """Load configuration and create data layer."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            storage_config = config.get('storage', {})
            self.data_layer = data_layer_factory.create_from_config(storage_config)
            
            success = await self.data_layer.initialize()
            if not success:
                raise Exception("Failed to initialize data layer")
            
            self.logger.info("Data layer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize data layer: {e}")
            return False
    
    async def run_migration(self):
        """Run database migration."""
        print("🗄️  AlphaStock Database Migration")
        print("=" * 40)
        
        # Load configuration and initialize data layer
        if not await self.load_config_and_create_data_layer():
            print("❌ Failed to initialize database connection")
            return False
        
        try:
            # Test connection
            health = await self.data_layer.health_check()
            if health.get('overall_status') not in ['healthy', 'active']:
                print(f"❌ Database health check failed: {health}")
                return False
            
            print("✅ Database connection established")
            
            # Run schema creation
            print("\n📋 Creating database schema...")
            
            # The data layer initialization should create tables automatically
            # but we can verify they exist by running a simple query
            
            try:
                # Try to get symbols (this will create tables if they don't exist)
                symbols = await self.data_layer.get_symbols_by_asset_type('EQUITY')
                print("✅ Database schema verified")
                
                if symbols:
                    print(f"Found {len(symbols)} existing equity symbols")
                else:
                    print("No existing data found (fresh installation)")
                
                # Test other core functionality
                print("\n🔍 Testing core functionality...")
                
                # Test market data storage
                import pandas as pd
                import numpy as np
                from datetime import datetime
                
                test_data = pd.DataFrame({
                    'timestamp': [datetime.now()],
                    'symbol': ['TEST'],
                    'open': [100.0],
                    'high': [105.0],
                    'low': [99.0],
                    'close': [102.0],
                    'volume': [1000],
                    'asset_type': ['EQUITY']
                })
                
                # Store test data
                success = await self.data_layer.store_market_data('TEST', 'EQUITY', test_data, 'migration_test')
                if success:
                    print("✅ Market data storage: OK")
                else:
                    print("⚠️  Market data storage: Failed")
                
                # Test signal storage
                test_signal = {
                    'id': 'test-signal-1',
                    'symbol': 'TEST',
                    'strategy': 'migration_test',
                    'signal_type': 'BUY',
                    'entry_price': 102.0,
                    'stop_loss': 98.0,
                    'target': 108.0,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'NEW',
                    'metadata': {'test': True}
                }
                
                success = await self.data_layer.store_signal(test_signal)
                if success:
                    print("✅ Signal storage: OK")
                else:
                    print("⚠️  Signal storage: Failed")
                
                # Clean up test data
                try:
                    await self.data_layer.execute_query("DELETE FROM market_data WHERE symbol = 'TEST'")
                    await self.data_layer.execute_query("DELETE FROM signals WHERE symbol = 'TEST'")
                    print("✅ Test data cleaned up")
                except:
                    print("⚠️  Could not clean up test data (may not be supported)")
                
                print("\n🎉 Migration completed successfully!")
                return True
                
            except Exception as e:
                print(f"❌ Schema verification failed: {e}")
                return False
        
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            print(f"❌ Migration failed: {e}")
            return False
        
        finally:
            if self.data_layer:
                await self.data_layer.close()
    
    async def verify_installation(self):
        """Verify that the database is properly set up."""
        print("🔍 AlphaStock Database Verification")
        print("=" * 40)
        
        if not await self.load_config_and_create_data_layer():
            print("❌ Failed to connect to database")
            return False
        
        try:
            # Check health
            health = await self.data_layer.health_check()
            print(f"Database status: {health.get('overall_status', 'unknown')}")
            
            # Check primary storage
            if 'primary_storage' in health:
                primary = health['primary_storage']
                print(f"Primary storage: {primary.get('type', 'unknown')} - {primary.get('status', 'unknown')}")
            
            # Check cache
            if 'cache_layer' in health and health['cache_layer']:
                cache = health['cache_layer']
                print(f"Cache layer: {cache.get('status', 'unknown')}")
            
            # Check basic functionality
            symbols = await self.data_layer.get_symbols_by_asset_type('EQUITY')
            print(f"Equity symbols in database: {len(symbols) if symbols else 0}")
            
            signals = await self.data_layer.get_signals()
            print(f"Signals in database: {len(signals) if signals else 0}")
            
            print("✅ Database verification completed")
            return True
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False
        
        finally:
            if self.data_layer:
                await self.data_layer.close()


async def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AlphaStock Database Migration")
    parser.add_argument('--config', '-c', help='Database configuration file path')
    parser.add_argument('--verify', '-v', action='store_true', help='Verify installation instead of running migration')
    
    args = parser.parse_args()
    
    migration = DatabaseMigration(config_path=args.config)
    
    try:
        if args.verify:
            success = await migration.verify_installation()
        else:
            success = await migration.run_migration()
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
