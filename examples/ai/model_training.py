#!/usr/bin/env python3
"""
AI Model Training Example
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path  
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ai import AIDecisionEngine

async def main():
    """AI model training demonstration."""
    
    print("🎯 AI Model Training Example")
    print("="*40)
    
    # Create synthetic training data
    np.random.seed(42)
    n_samples = 1000
    
    dates = pd.date_range(start=datetime.now() - timedelta(days=30),
                         periods=n_samples, freq='1min')
    
    # Generate realistic market data with trends
    base_price = 50000
    trend = np.cumsum(np.random.normal(0, 0.001, n_samples))
    noise = np.random.normal(0, 0.01, n_samples)
    
    close_prices = base_price + trend * 100 + noise * 100
    
    training_data = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices * (1 + np.random.normal(0, 0.001, n_samples)),
        'high': close_prices * (1 + np.abs(np.random.normal(0, 0.002, n_samples))),
        'low': close_prices * (1 - np.abs(np.random.normal(0, 0.002, n_samples))),
        'close': close_prices,
        'volume': np.random.randint(500, 2000, n_samples)
    })
    
    print(f"📊 Generated {len(training_data)} training samples")
    
    # Initialize AI engine
    ai_engine = AIDecisionEngine(confidence_threshold=0.85)
    
    # Train models
    print("🎯 Training AI models...")
    await ai_engine.train_models(training_data)
    
    # Check model status
    status = ai_engine.get_model_status()
    print("\n📈 Model Training Results:")
    
    for model_name, model_status in status.items():
        print(f"\n{model_name}:")
        print(f"  Trained: {'Yes' if model_status['is_trained'] else 'No'}")
        if model_status['metrics']:
            print(f"  Accuracy: {model_status['metrics']['accuracy']:.3f}")
            print(f"  Samples: {model_status['metrics']['samples_trained']}")
    
    print("\n✅ Training example completed!")

if __name__ == "__main__":
    asyncio.run(main())
