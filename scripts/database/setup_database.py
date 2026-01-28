#!/usr/bin/env python3
"""
Database Setup Script for AlphaStock Trading System

This script helps you set up the database backend for your AlphaStock system.
It supports PostgreSQL, ClickHouse, and Redis configuration.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.data_layer_factory import DataLayerFactory, data_layer_factory
from src.utils.logger_setup import setup_logger


class DatabaseSetup:
    """Database setup and configuration manager."""
    
    def __init__(self):
        self.logger = setup_logger("DatabaseSetup")
        self.config_dir = Path(__file__).parent.parent / "config"
        self.database_config_path = self.config_dir / "database.json"
    
    def display_welcome(self):
        """Display welcome message and options."""
        print("=" * 60)
        print("🚀 AlphaStock Database Setup")
        print("=" * 60)
        print("\nThis script will help you configure your database backend.")
        print("\nSupported databases:")
        print("1. PostgreSQL (recommended for development)")
        print("2. ClickHouse (recommended for production)")
        print("3. Redis (caching layer)")
        print("\nConfiguration options:")
        print("- Quick setup with defaults")
        print("- Custom configuration")
        print("- Test existing connections")
        print()
    
    def get_user_choice(self, prompt, choices):
        """Get user choice from a list of options."""
        while True:
            print(prompt)
            for i, choice in enumerate(choices, 1):
                print(f"{i}. {choice}")
            
            try:
                choice_num = int(input("\nEnter your choice (number): "))
                if 1 <= choice_num <= len(choices):
                    return choice_num - 1
                else:
                    print(f"Please enter a number between 1 and {len(choices)}")
            except ValueError:
                print("Please enter a valid number")
    
    def get_database_config(self):
        """Get database configuration from user."""
        print("\n" + "=" * 40)
        print("Database Configuration")
        print("=" * 40)
        
        # Choose primary database
        db_choices = [
            "PostgreSQL (easier setup, good for development)",
            "ClickHouse (better performance for time-series data)"
        ]
        
        db_choice = self.get_user_choice(
            "Choose your primary database:",
            db_choices
        )
        
        if db_choice == 0:
            # PostgreSQL setup
            return self.setup_postgresql()
        else:
            # ClickHouse setup
            return self.setup_clickhouse()
    
    def setup_postgresql(self):
        """Setup PostgreSQL configuration."""
        print("\n📊 PostgreSQL Setup")
        print("-" * 20)
        
        setup_choices = [
            "Quick setup (localhost, default settings)",
            "Custom configuration"
        ]
        
        setup_choice = self.get_user_choice(
            "Choose setup type:",
            setup_choices
        )
        
        if setup_choice == 0:
            # Quick setup
            config = {
                "type": "postgresql",
                "postgresql": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "alphastock",
                    "username": "postgres",
                    "password": "",
                    "pool_size": 20,
                    "max_overflow": 30
                },
                "cache": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 6379,
                    "db": 0,
                    "password": None,
                    "max_connections": 20
                }
            }
            
            # Ask for password
            password = input("PostgreSQL password (press Enter if none): ")
            if password:
                config["postgresql"]["password"] = password
            
            return config
        
        else:
            # Custom configuration
            config = {
                "type": "postgresql",
                "postgresql": {
                    "host": input("PostgreSQL host [localhost]: ") or "localhost",
                    "port": int(input("PostgreSQL port [5432]: ") or "5432"),
                    "database": input("Database name [alphastock]: ") or "alphastock",
                    "username": input("Username [postgres]: ") or "postgres",
                    "password": input("Password: "),
                    "pool_size": int(input("Connection pool size [20]: ") or "20"),
                    "max_overflow": int(input("Max overflow connections [30]: ") or "30")
                }
            }
            
            # Redis cache configuration
            cache_enabled = input("Enable Redis caching? [y/N]: ").lower().startswith('y')
            if cache_enabled:
                config["cache"] = {
                    "enabled": True,
                    "host": input("Redis host [localhost]: ") or "localhost",
                    "port": int(input("Redis port [6379]: ") or "6379"),
                    "db": int(input("Redis database [0]: ") or "0"),
                    "password": input("Redis password (press Enter if none): ") or None,
                    "max_connections": int(input("Redis max connections [20]: ") or "20")
                }
            else:
                config["cache"] = {"enabled": False}
            
            return config
    
    def setup_clickhouse(self):
        """Setup ClickHouse configuration."""
        print("\n⚡ ClickHouse Setup")
        print("-" * 20)
        
        setup_choices = [
            "Quick setup (localhost, default settings)",
            "Custom configuration"
        ]
        
        setup_choice = self.get_user_choice(
            "Choose setup type:",
            setup_choices
        )
        
        if setup_choice == 0:
            # Quick setup
            config = {
                "type": "clickhouse",
                "clickhouse": {
                    "host": "localhost",
                    "port": 8123,
                    "database": "alphastock",
                    "username": "default",
                    "password": "",
                    "pool_size": 10
                },
                "cache": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 6379,
                    "db": 0,
                    "password": None,
                    "max_connections": 20
                }
            }
            
            # Ask for password
            password = input("ClickHouse password (press Enter if none): ")
            if password:
                config["clickhouse"]["password"] = password
            
            return config
        
        else:
            # Custom configuration
            config = {
                "type": "clickhouse",
                "clickhouse": {
                    "host": input("ClickHouse host [localhost]: ") or "localhost",
                    "port": int(input("ClickHouse HTTP port [8123]: ") or "8123"),
                    "database": input("Database name [alphastock]: ") or "alphastock",
                    "username": input("Username [default]: ") or "default",
                    "password": input("Password: "),
                    "pool_size": int(input("Connection pool size [10]: ") or "10")
                }
            }
            
            # Redis cache configuration
            cache_enabled = input("Enable Redis caching? [y/N]: ").lower().startswith('y')
            if cache_enabled:
                config["cache"] = {
                    "enabled": True,
                    "host": input("Redis host [localhost]: ") or "localhost",
                    "port": int(input("Redis port [6379]: ") or "6379"),
                    "db": int(input("Redis database [0]: ") or "0"),
                    "password": input("Redis password (press Enter if none): ") or None,
                    "max_connections": int(input("Redis max connections [20]: ") or "20")
                }
            else:
                config["cache"] = {"enabled": False}
            
            return config
    
    async def test_connection(self, config):
        """Test database connection."""
        print("\n🔍 Testing database connection...")
        
        try:
            # Create data layer from config
            data_layer = data_layer_factory.create_from_config(config)
            
            # Test connection
            success = await data_layer_factory.test_connection(data_layer)
            
            if success:
                print("✅ Database connection successful!")
                
                # Get health check info
                health = await data_layer.health_check()
                print(f"Database status: {health.get('overall_status', 'unknown')}")
                
                if 'primary_storage' in health:
                    primary = health['primary_storage']
                    print(f"Primary storage: {primary.get('type', 'unknown')}")
                
                if 'cache_layer' in health and health['cache_layer']:
                    cache = health['cache_layer']
                    if cache.get('status') == 'healthy':
                        print("Cache layer: Active")
                    else:
                        print("Cache layer: Inactive")
                
                await data_layer.close()
                return True
            else:
                print("❌ Database connection failed!")
                return False
                
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
    
    def save_config(self, config):
        """Save configuration to file."""
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(exist_ok=True)
            
            # Add default performance and monitoring settings
            full_config = {
                "storage": config,
                "performance": {
                    "batch_size": 1000,
                    "connection_timeout": 30,
                    "query_timeout": 60,
                    "enable_connection_pooling": True,
                    "enable_query_optimization": True,
                    "enable_compression": True
                },
                "maintenance": {
                    "auto_optimize": True,
                    "optimize_interval_hours": 6,
                    "cleanup_old_data": True,
                    "data_retention_days": 365,
                    "vacuum_interval_hours": 24
                },
                "monitoring": {
                    "enable_health_checks": True,
                    "health_check_interval": 60,
                    "log_slow_queries": True,
                    "slow_query_threshold": 5.0,
                    "enable_metrics": True
                }
            }
            
            with open(self.database_config_path, 'w') as f:
                json.dump(full_config, f, indent=2)
            
            print(f"✅ Configuration saved to {self.database_config_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return False
    
    def display_next_steps(self, config):
        """Display next steps after successful setup."""
        print("\n" + "=" * 50)
        print("🎉 Setup Complete!")
        print("=" * 50)
        
        db_type = config["type"]
        
        print("\nNext steps:")
        print("1. Start your database server")
        
        if db_type == "postgresql":
            print("   - Ensure PostgreSQL is running")
            print("   - Create the database: CREATE DATABASE alphastock;")
            if config.get("cache", {}).get("enabled"):
                print("   - Ensure Redis is running (for caching)")
        
        elif db_type == "clickhouse":
            print("   - Ensure ClickHouse is running")
            print("   - Database and tables will be created automatically")
            if config.get("cache", {}).get("enabled"):
                print("   - Ensure Redis is running (for caching)")
        
        print("\n2. Install required dependencies:")
        print("   pip install -r requirements.txt")
        
        print("\n3. Run the AlphaStock system:")
        print("   python main.py")
        
        print("\n4. Monitor your system:")
        print("   - Check logs for any connection issues")
        print("   - Use the health check endpoint to monitor database status")
        
        print(f"\nConfiguration file: {self.database_config_path}")
        print("You can modify this file later if needed.")
    
    async def run_setup(self):
        """Run the complete setup process."""
        self.display_welcome()
        
        # Check if config already exists
        if self.database_config_path.exists():
            overwrite = input("Database configuration already exists. Overwrite? [y/N]: ")
            if not overwrite.lower().startswith('y'):
                print("Setup cancelled.")
                return
        
        # Get configuration
        config = self.get_database_config()
        
        # Test connection
        connection_ok = await self.test_connection(config)
        
        if not connection_ok:
            retry = input("Connection failed. Save configuration anyway? [y/N]: ")
            if not retry.lower().startswith('y'):
                print("Setup cancelled.")
                return
        
        # Save configuration
        if self.save_config(config):
            self.display_next_steps(config)
        else:
            print("Failed to save configuration.")


def main():
    """Main setup function."""
    setup = DatabaseSetup()
    
    try:
        asyncio.run(setup.run_setup())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nSetup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
