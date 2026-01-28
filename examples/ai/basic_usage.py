#!/usr/bin/env python3
"""
Basic AI Framework Usage Example
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ai import AIDecisionEngine

async def main():
    """Basic AI framework demonstration."""
    
    print("🧠 AlphaStock AI Framework - Basic Example")
    print("="*50)
    
    # Initialize AI engine
    ai_engine = AIDecisionEngine(confidence_threshold=0.85)
    
    # Create sample market data
    dates = pd.date_range(start=datetime.now() - timedelta(days=1), 
                         end=datetime.now(), freq='1min')
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': [50000 + i for i in range(len(dates))],
        'high': [50010 + i for i in range(len(dates))],
        'low': [49990 + i for i in range(len(dates))],
        'close': [50005 + i for i in range(len(dates))],
        'volume': [1000] * len(dates)
    })
    
    # Create sample signal
    sample_signal = {
        'symbol': 'BANKNIFTY',
        'strategy': 'Example',
        'signal_type': 'BUY',
        'timestamp': datetime.now()
    }
    
    # Test AI validation
    print("📡 Testing AI signal validation...")
    ai_signal = await ai_engine.validate_signal(sample_signal, sample_data)
    
    print(f"Signal: {ai_signal.signal_type}")
    print(f"Confidence: {ai_signal.confidence:.2%}")
    print(f"Execute: {'Yes' if ai_signal.execution_recommendation else 'No'}")
    
    # Test risk assessment
    print("\n⚠️ Testing risk assessment...")
    risk_result = await ai_engine.assess_risk('BANKNIFTY', sample_data)
    print(f"Risk Score: {risk_result['risk_score']:.3f}")
    print(f"Recommendation: {risk_result['recommendation']}")
    
    print("\n✅ Basic example completed!")

if __name__ == "__main__":
    asyncio.run(main())
