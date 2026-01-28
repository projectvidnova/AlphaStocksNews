#!/usr/bin/env python3
"""
Simple AI Framework Demo
Demonstrates basic AI functionality without external dependencies
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simple_ai_demo")


def create_sample_data():
    """Create realistic sample market data."""
    
    logger.info("📦 Creating sample market data...")
    
    # Generate 30 days of 1-minute data
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=30),
        end=datetime.now(),
        freq='1min'
    )
    
    np.random.seed(42)
    
    # Generate realistic OHLCV data with trend
    base_price = 50000
    trend = np.cumsum(np.random.normal(0.0001, 0.001, len(dates)))
    noise = np.random.normal(0, 0.01, len(dates))
    
    close_prices = base_price + trend * 1000 + noise * 100
    
    # Ensure prices are positive
    close_prices = np.maximum(close_prices, 1000)
    
    data = {
        'timestamp': dates,
        'symbol': ['BANKNIFTY'] * len(dates),
        'open': close_prices * (1 + np.random.normal(0, 0.002, len(dates))),
        'high': close_prices * (1 + np.abs(np.random.normal(0, 0.005, len(dates)))),
        'low': close_prices * (1 - np.abs(np.random.normal(0, 0.005, len(dates)))),
        'close': close_prices,
        'volume': np.random.randint(1000, 10000, len(dates))
    }
    
    df = pd.DataFrame(data)
    
    # Ensure high >= max(open, close) and low <= min(open, close)
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)
    
    logger.info(f"✅ Created {len(df)} data points from {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def generate_sample_signals(data: pd.DataFrame) -> pd.DataFrame:
    """Generate sample trading signals based on simple moving average crossover."""
    
    logger.info("📈 Generating sample signals...")
    
    # Calculate moving averages
    data['ma_fast'] = data['close'].rolling(window=9).mean()
    data['ma_slow'] = data['close'].rolling(window=21).mean()
    
    # Generate signals
    signals = []
    
    for i in range(1, len(data)):
        if pd.isna(data.iloc[i]['ma_fast']) or pd.isna(data.iloc[i]['ma_slow']):
            continue
        
        current_fast = data.iloc[i]['ma_fast']
        current_slow = data.iloc[i]['ma_slow']
        prev_fast = data.iloc[i-1]['ma_fast']
        prev_slow = data.iloc[i-1]['ma_slow']
        
        signal_type = None
        
        # Golden cross (bullish signal)
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal_type = 'BUY'
        # Death cross (bearish signal)
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal_type = 'SELL'
        
        if signal_type:
            signals.append({
                'timestamp': data.iloc[i]['timestamp'],
                'symbol': 'BANKNIFTY',
                'signal_type': signal_type,
                'strategy': 'MA_Crossover',
                'price': data.iloc[i]['close'],
                'ma_fast': current_fast,
                'ma_slow': current_slow
            })
    
    signals_df = pd.DataFrame(signals)
    logger.info(f"✅ Generated {len(signals_df)} trading signals")
    
    return signals_df


async def simulate_ai_validation(signal: dict, market_data: pd.DataFrame) -> dict:
    """Simulate AI signal validation with mock ML models."""
    
    logger.info(f"🧠 AI validating {signal['signal_type']} signal for {signal['symbol']}")
    
    # Extract simple features from recent data
    recent_data = market_data.tail(50)  # Last 50 periods
    
    # Calculate basic features
    returns = recent_data['close'].pct_change().dropna()
    volatility = returns.std()
    momentum = (recent_data['close'].iloc[-1] / recent_data['close'].iloc[-10] - 1)  # 10-period momentum
    
    # Volume analysis
    avg_volume = recent_data['volume'].mean()
    current_volume = recent_data['volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume
    
    # Price position relative to recent range
    recent_high = recent_data['high'].max()
    recent_low = recent_data['low'].min()
    price_position = (recent_data['close'].iloc[-1] - recent_low) / (recent_high - recent_low)
    
    # Simulate AI decision logic
    confidence_factors = []
    
    # Volatility factor (lower volatility = higher confidence)
    vol_score = max(0, 1 - (volatility / 0.05))  # Normalize volatility
    confidence_factors.append(vol_score * 0.3)
    
    # Momentum factor (alignment with signal)
    if signal['signal_type'] == 'BUY' and momentum > 0:
        momentum_score = min(1.0, momentum * 10)  # Positive momentum for buy
    elif signal['signal_type'] == 'SELL' and momentum < 0:
        momentum_score = min(1.0, -momentum * 10)  # Negative momentum for sell
    else:
        momentum_score = 0.3  # Neutral if momentum doesn't align
    
    confidence_factors.append(momentum_score * 0.3)
    
    # Volume factor (higher volume = higher confidence)
    volume_score = min(1.0, volume_ratio / 2.0)  # Higher than average volume
    confidence_factors.append(volume_score * 0.2)
    
    # Price position factor
    if signal['signal_type'] == 'BUY' and price_position < 0.3:
        position_score = 0.8  # Buy near lows
    elif signal['signal_type'] == 'SELL' and price_position > 0.7:
        position_score = 0.8  # Sell near highs
    else:
        position_score = 0.4
    
    confidence_factors.append(position_score * 0.2)
    
    # Calculate final confidence
    ai_confidence = sum(confidence_factors)
    
    # Risk assessment
    risk_score = volatility * 10  # Simple risk based on volatility
    risk_score = min(1.0, risk_score)
    
    # Execution recommendation
    confidence_threshold = 0.65
    risk_threshold = 0.7
    
    execute = (ai_confidence >= confidence_threshold and risk_score <= risk_threshold)
    
    # Generate reasoning
    reasoning = []
    reasoning.append(f"Volatility: {volatility:.4f} ({'Low' if volatility < 0.02 else 'High'})")
    reasoning.append(f"Momentum: {momentum:.3f} ({'Favorable' if momentum_score > 0.5 else 'Unfavorable'})")
    reasoning.append(f"Volume ratio: {volume_ratio:.2f} ({'Above average' if volume_ratio > 1.2 else 'Normal'})")
    reasoning.append(f"Price position: {price_position:.2f} ({'Good entry' if position_score > 0.6 else 'Neutral'})")
    
    result = {
        'symbol': signal['symbol'],
        'strategy': signal['strategy'],
        'signal_type': signal['signal_type'],
        'ai_confidence': ai_confidence,
        'risk_score': risk_score,
        'execution_recommended': execute,
        'features': {
            'volatility': volatility,
            'momentum': momentum,
            'volume_ratio': volume_ratio,
            'price_position': price_position
        },
        'reasoning': reasoning,
        'timestamp': datetime.now()
    }
    
    return result


async def simulate_risk_assessment(symbol: str, market_data: pd.DataFrame) -> dict:
    """Simulate AI risk assessment."""
    
    logger.info(f"⚠️ Assessing risk for {symbol}")
    
    recent_data = market_data.tail(100)
    
    # Calculate risk metrics
    returns = recent_data['close'].pct_change().dropna()
    volatility = returns.std()
    max_drawdown = ((recent_data['close'].cummax() - recent_data['close']) / recent_data['close'].cummax()).max()
    
    # VaR approximation (95% confidence)
    var_95 = np.percentile(returns, 5)
    
    # Risk score (0 = low risk, 1 = high risk)
    vol_risk = min(1.0, volatility / 0.05)
    drawdown_risk = min(1.0, max_drawdown / 0.1)
    var_risk = min(1.0, abs(var_95) / 0.05)
    
    overall_risk = (vol_risk + drawdown_risk + var_risk) / 3.0
    
    # Risk level categorization
    if overall_risk < 0.3:
        risk_level = "LOW"
    elif overall_risk < 0.7:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"
    
    # Position size recommendation
    base_position = 1.0
    risk_adjusted_position = base_position * (1.0 - overall_risk * 0.8)
    
    return {
        'symbol': symbol,
        'overall_risk_score': overall_risk,
        'risk_level': risk_level,
        'volatility': volatility,
        'max_drawdown': max_drawdown,
        'var_95': var_95,
        'recommended_position_size': risk_adjusted_position,
        'confidence': 0.8,
        'timestamp': datetime.now()
    }


async def simulate_anomaly_detection(symbol: str, market_data: pd.DataFrame) -> dict:
    """Simulate market anomaly detection."""
    
    logger.info(f"🚨 Detecting anomalies for {symbol}")
    
    recent_data = market_data.tail(100)
    
    # Calculate anomaly indicators
    returns = recent_data['close'].pct_change().dropna()
    
    # Z-score of latest return
    latest_return = returns.iloc[-1]
    mean_return = returns.mean()
    std_return = returns.std()
    return_zscore = abs((latest_return - mean_return) / std_return) if std_return > 0 else 0
    
    # Volume anomaly
    volumes = recent_data['volume']
    latest_volume = volumes.iloc[-1]
    mean_volume = volumes.mean()
    std_volume = volumes.std()
    volume_zscore = abs((latest_volume - mean_volume) / std_volume) if std_volume > 0 else 0
    
    # Price gap detection
    price_gap = abs(recent_data['open'].iloc[-1] - recent_data['close'].iloc[-2]) / recent_data['close'].iloc[-2]
    
    # Anomaly scoring (higher score = more anomalous)
    return_anomaly = min(1.0, return_zscore / 3.0)  # Beyond 3 standard deviations
    volume_anomaly = min(1.0, volume_zscore / 2.5)  # Beyond 2.5 standard deviations
    gap_anomaly = min(1.0, price_gap / 0.05)  # >5% gap
    
    overall_anomaly = (return_anomaly + volume_anomaly + gap_anomaly) / 3.0
    
    # Anomaly status
    if overall_anomaly < 0.2:
        status = "NORMAL"
    elif overall_anomaly < 0.5:
        status = "UNUSUAL"
    else:
        status = "ANOMALY"
    
    return {
        'symbol': symbol,
        'anomaly_score': overall_anomaly,
        'status': status,
        'return_zscore': return_zscore,
        'volume_zscore': volume_zscore,
        'price_gap': price_gap,
        'confidence': 0.75,
        'timestamp': datetime.now()
    }


async def main():
    """Main demonstration function."""
    
    logger.info("🚀 Starting Simple AI Framework Demo")
    logger.info("="*50)
    
    try:
        # Create sample data
        market_data = create_sample_data()
        
        # Generate signals
        signals = generate_sample_signals(market_data)
        
        if len(signals) == 0:
            logger.warning("⚠️ No signals generated. Using sample signal.")
            signals = pd.DataFrame([{
                'timestamp': datetime.now(),
                'symbol': 'BANKNIFTY',
                'signal_type': 'BUY',
                'strategy': 'MA_Crossover',
                'price': market_data['close'].iloc[-1]
            }])
        
        logger.info(f"📊 Processing {len(signals)} signals...")
        
        # Process each signal with AI validation
        for idx, signal in signals.head(3).iterrows():  # Process first 3 signals
            logger.info(f"\n📈 Processing Signal {idx + 1}")
            logger.info("-" * 40)
            
            signal_dict = signal.to_dict()
            
            # AI Signal Validation
            ai_result = await simulate_ai_validation(signal_dict, market_data)
            
            logger.info("🧠 AI Signal Validation:")
            logger.info(f"  • Symbol: {ai_result['symbol']}")
            logger.info(f"  • Signal: {ai_result['signal_type']}")
            logger.info(f"  • AI Confidence: {ai_result['ai_confidence']:.2%}")
            logger.info(f"  • Risk Score: {ai_result['risk_score']:.3f}")
            logger.info(f"  • Execution: {'✅ Recommended' if ai_result['execution_recommended'] else '❌ Not recommended'}")
            
            logger.info("  • Key Features:")
            for feature, value in ai_result['features'].items():
                logger.info(f"    - {feature}: {value:.4f}")
            
            logger.info("  • AI Reasoning:")
            for reason in ai_result['reasoning']:
                logger.info(f"    - {reason}")
            
            # Risk Assessment
            risk_result = await simulate_risk_assessment(signal['symbol'], market_data)
            
            logger.info("\n⚠️ Risk Assessment:")
            logger.info(f"  • Risk Level: {risk_result['risk_level']}")
            logger.info(f"  • Overall Risk Score: {risk_result['overall_risk_score']:.3f}")
            logger.info(f"  • Volatility: {risk_result['volatility']:.4f}")
            logger.info(f"  • Max Drawdown: {risk_result['max_drawdown']:.2%}")
            logger.info(f"  • VaR (95%): {risk_result['var_95']:.2%}")
            logger.info(f"  • Recommended Position Size: {risk_result['recommended_position_size']:.2f}")
            
            # Anomaly Detection
            anomaly_result = await simulate_anomaly_detection(signal['symbol'], market_data)
            
            logger.info("\n🚨 Anomaly Detection:")
            logger.info(f"  • Status: {anomaly_result['status']}")
            logger.info(f"  • Anomaly Score: {anomaly_result['anomaly_score']:.3f}")
            logger.info(f"  • Return Z-Score: {anomaly_result['return_zscore']:.2f}")
            logger.info(f"  • Volume Z-Score: {anomaly_result['volume_zscore']:.2f}")
            logger.info(f"  • Price Gap: {anomaly_result['price_gap']:.2%}")
            
            # Final Trading Decision
            logger.info("\n" + "="*50)
            logger.info("🎯 FINAL AI-ENHANCED TRADING DECISION")
            logger.info("="*50)
            
            final_decision = (
                ai_result['execution_recommended'] and
                risk_result['overall_risk_score'] < 0.7 and
                anomaly_result['status'] != 'ANOMALY'
            )
            
            if final_decision:
                logger.info("✅ EXECUTE TRADE")
                logger.info(f"   Signal: {ai_result['signal_type']}")
                logger.info(f"   Confidence: {ai_result['ai_confidence']:.2%}")
                logger.info(f"   Risk Level: {risk_result['risk_level']}")
                logger.info(f"   Position Size: {risk_result['recommended_position_size']:.2f}")
                logger.info(f"   Market Status: {anomaly_result['status']}")
            else:
                logger.info("❌ DO NOT EXECUTE TRADE")
                
                reasons = []
                if not ai_result['execution_recommended']:
                    reasons.append(f"Low AI confidence ({ai_result['ai_confidence']:.2%})")
                if risk_result['overall_risk_score'] >= 0.7:
                    reasons.append(f"High risk ({risk_result['risk_level']})")
                if anomaly_result['status'] == 'ANOMALY':
                    reasons.append("Market anomaly detected")
                
                logger.info("   Rejection reasons:")
                for reason in reasons:
                    logger.info(f"     - {reason}")
            
            # Add a separator between signals
            if idx < len(signals.head(3)) - 1:
                logger.info("\n" + "◦" * 60)
        
        # Summary Statistics
        logger.info("\n" + "="*60)
        logger.info("📊 DEMO SUMMARY STATISTICS")
        logger.info("="*60)
        
        logger.info(f"📈 Total Market Data Points: {len(market_data):,}")
        logger.info(f"📡 Total Signals Generated: {len(signals)}")
        logger.info(f"🧠 Signals Processed with AI: {min(3, len(signals))}")
        
        # Signal type distribution
        signal_types = signals['signal_type'].value_counts()
        logger.info(f"📊 Signal Distribution:")
        for signal_type, count in signal_types.items():
            logger.info(f"   • {signal_type}: {count} signals")
        
        logger.info("\n✅ Simple AI Framework Demo Completed Successfully!")
        logger.info("\n🎯 Next Steps:")
        logger.info("   1. Install ML libraries: pip install -r requirements-ai.txt")
        logger.info("   2. Run full demo: python ai_integration_demo.py")
        logger.info("   3. Train real AI models with historical data")
        logger.info("   4. Integrate with live trading system")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
