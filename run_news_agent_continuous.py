"""
Run News Agent Continuously - Runs every 5 minutes
Fetches news, analyzes with Azure AI Foundry, and generates alerts.
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.news import NewsAgent


# Global agent instance for signal handling
agent = None


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n⚠️  Received interrupt signal, stopping agent...")
    if agent:
        asyncio.create_task(agent.stop())
    sys.exit(0)


async def main():
    """Run the news agent continuously."""
    global agent
    
    print("=" * 60)
    print("NEWS ANALYSIS AGENT - Continuous Mode")
    print("=" * 60)
    
    # Load config from file
    config_path = Path("config/news_agent.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"\nLoaded config from {config_path}")
    else:
        config = {}
        print("\nNo config file found, using defaults")
    
    # Show current configuration
    fetch_interval = config.get("fetch_interval_seconds", 300)
    market_hours_only = config.get("market_hours_only", True)
    min_impact = config.get("min_impact_level", "high")
    scrape_articles = config.get("scrape_full_articles", False)
    
    print(f"\n📋 Configuration:")
    print(f"   Fetch Interval:     {fetch_interval}s ({fetch_interval//60} minutes)")
    print(f"   Market Hours Only:  {market_hours_only}")
    print(f"   Min Impact Level:   {min_impact}")
    print(f"   Scrape Articles:    {scrape_articles}")
    print(f"   Max News Age:       {config.get('max_news_age_hours', 24)}h")
    
    # Check API key (from environment or config)
    api_key = os.getenv("AZURE_API_KEY") or config.get("llama", {}).get("api_key")
    if api_key:
        print(f"   Azure API Key:      ✓ ({len(api_key)} chars)")
        # Set it in config if from environment
        if "llama" not in config:
            config["llama"] = {}
        if not config["llama"].get("api_key"):
            config["llama"]["api_key"] = api_key
    else:
        print(f"   Azure API Key:      ⚠️  Not configured!")
        print(f"   Set with: export AZURE_API_KEY='your-key'")
    
    # Create agent
    agent = NewsAgent(config=config)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize
    print("\n🔧 Initializing agent...")
    await agent.initialize()
    
    # Start continuous mode
    print(f"\n🚀 Starting continuous mode (Ctrl+C to stop)...")
    print(f"📡 Will fetch news every {fetch_interval}s")
    print("-" * 60)
    
    try:
        await agent.start()
        
        # Keep running until stopped
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Keyboard interrupt detected")
    finally:
        print("\n🛑 Stopping agent...")
        await agent.stop()
        
        # Show final stats
        stats = agent.get_stats()
        print("\n" + "=" * 60)
        print("FINAL STATS")
        print("=" * 60)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print("=" * 60)
        print("\n✅ Agent stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
