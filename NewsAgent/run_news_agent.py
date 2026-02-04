"""
Run News Agent - One-time execution script
Fetches news, analyzes with Azure AI Foundry, and generates alerts.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.news import NewsAgent


async def main():
    """Run the news agent once."""
    print("=" * 60)
    print("NEWS ANALYSIS AGENT - Single Run")
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
    
    # Override specific settings for this test run
    config["market_hours_only"] = False  # Run anytime for testing
    config["validate_price_impact"] = False  # Skip price validation
    config["min_impact_level"] = "medium"  # Include medium impact news
    config["max_news_age_hours"] = 12  # Recent news only
    config["scrape_full_articles"] = True  # Enable article scraping for testing
    
    print("\n🔍 Article scraping ENABLED for this test run")
    
    # Update llama config to use Azure AI Foundry
    if "llama" not in config:
        config["llama"] = {}
    
    # Configure Azure AI Foundry settings (override for this run)
    # Base URL without /models/chat/completions - that's added by the API handler
    config["llama"]["base_url"] = "https://adithyasaisaladi-1060-resource.services.ai.azure.com"
    config["llama"]["model_name"] = "DeepSeek-V3.2"
    config["llama"]["api_type"] = "openai"
    
    # Use API key from config file if present, otherwise check environment
    if not config["llama"].get("api_key"):
        azure_api_key = os.getenv("AZURE_API_KEY")
        if not azure_api_key:
            print("\n⚠️  WARNING: AZURE_API_KEY not found in config or environment!")
            print("   Set it with: export AZURE_API_KEY='your-api-key-here'")
            print("   Or add it to config/news_agent.json")
        config["llama"]["api_key"] = azure_api_key
    else:
        print(f"\n✓ Using API key from config (length: {len(config['llama']['api_key'])} chars)")
    
    # Create agent
    agent = NewsAgent(config=config)
    
    # Initialize
    print("\n[1/4] Initializing agent...")
    await agent.initialize()
    
    # Run one cycle
    print("\n[2/4] Fetching RSS feeds...")
    result = await agent.run_once()
    
    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  News Fetched:    {result.get('fetched', 0)}")
    print(f"  New Items:       {result.get('new', 0)}")
    print(f"  Analyzed:        {result.get('analyzed', 0)}")
    print(f"  High Impact:     {result.get('high_impact', 0)}")
    print(f"  Alerts:          {result.get('alerts', 0)}")
    print(f"  Duration:        {result.get('duration_seconds', 0):.2f}s")
    
    # Show alerts
    alerts = agent.get_recent_alerts()
    if alerts:
        print("\n" + "=" * 60)
        print(f"ALERTS ({len(alerts)} total)")
        print("=" * 60)
        for i, alert in enumerate(alerts[:10], 1):
            print(f"\n[{i}] {alert.symbol} - {alert.recommended_action}")
            print(f"    Title: {alert.news_title[:80]}...")
            print(f"    Sentiment: {alert.sentiment.value}")
            print(f"    Direction: {alert.expected_direction}")
            print(f"    Expected Move: {alert.expected_move_pct:.1f}%")
    else:
        print("\nNo alerts generated.")
    
    # Show stats
    print("\n" + "=" * 60)
    print("AGENT STATS")
    print("=" * 60)
    stats = agent.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
