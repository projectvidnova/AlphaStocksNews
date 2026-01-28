#!/usr/bin/env python3
"""
AlphaStock Trading System - Main Entry Point
New modular architecture with orchestrator-based design.
"""

import asyncio
import sys
from src.orchestrator import AlphaStockOrchestrator


async def main():
    """Main entry point for AlphaStock trading system."""
    print("🚀 Starting AlphaStock Trading System (New Architecture)")
    print("=" * 60)
    
    # Create orchestrator with production config
    orchestrator = AlphaStockOrchestrator("config/production.json")
    
    try:
        # Initialize all components
        print("Initializing system components...")
        await orchestrator.initialize()
        print("✅ System initialized successfully")
        
        # Start the trading system
        print("Starting trading system...")
        await orchestrator.start()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        try:
            await orchestrator.stop()
            print("✅ System stopped cleanly")
        except Exception as e:
            print(f"⚠️ Error during shutdown: {e}")


if __name__ == "__main__":
    print("AlphaStock Trading System")
    print("For more control, use: python cli.py --help")
    print("For examples, run: python examples.py")
    print("-" * 40)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)