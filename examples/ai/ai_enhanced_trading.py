#!/usr/bin/env python3
"""
AI-Enhanced AlphaStock Trading System
Production-ready trading system with AI validation, risk assessment, and anomaly detection
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ai_enhanced_trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("ai_enhanced_trading")

# Import AlphaStock components
from src.data.clickhouse_data_layer import ClickHouseDataLayer
from src.strategies.ma_crossover_strategy import MovingAverageCrossoverStrategy
from src.trading.signal_executor import SignalExecutor

# Import AI components
try:
    from src.ai import AIDecisionEngine, FeatureStore
    AI_AVAILABLE = True
    logger.info("🧠 AI framework loaded successfully")
except ImportError as e:
    AI_AVAILABLE = False
    logger.warning(f"⚠️ AI framework not available: {e}")
    logger.info("💡 Run 'python setup_ai_framework.py' to install AI dependencies")


class AIEnhancedTradingSystem:
    """Production trading system with AI enhancement."""
    
    def __init__(self, ai_confidence_threshold: float = 0.75):
        self.data_layer = ClickHouseDataLayer()
        self.strategy = MovingAverageCrossoverStrategy()
        self.signal_executor = SignalExecutor()
        
        # AI components (optional)
        if AI_AVAILABLE:
            self.ai_engine = AIDecisionEngine(confidence_threshold=ai_confidence_threshold)
            self.feature_store = FeatureStore(self.data_layer)
            self.ai_enabled = True
            logger.info(f"🧠 AI engine initialized with {ai_confidence_threshold:.1%} confidence threshold")
        else:
            self.ai_engine = None
            self.feature_store = None
            self.ai_enabled = False
            logger.info("📊 Running in traditional mode (no AI)")
        
        self.running = False
        self.processed_signals = []
        self.ai_stats = {
            'total_signals': 0,
            'ai_approved': 0,
            'ai_rejected': 0,
            'high_risk_blocked': 0,
            'anomaly_blocked': 0
        }
    
    async def initialize_ai_models(self):
        """Initialize and train AI models if available."""
        
        if not self.ai_enabled:
            logger.info("⏭️ Skipping AI model initialization (AI not available)")
            return
        
        logger.info("🎯 Initializing AI models...")
        
        try:
            # Check if we have historical data for training
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            historical_data = await self.data_layer.get_historical_data(
                "BANKNIFTY", start_date, end_date, "1m"
            )
            
            if not historical_data.empty and len(historical_data) > 100:
                logger.info(f"📊 Training AI models with {len(historical_data)} historical data points...")
                await self.ai_engine.train_models(historical_data)
                
                # Check model status
                model_status = self.ai_engine.get_model_status()
                for model_name, status in model_status.items():
                    if status['is_trained']:
                        logger.info(f"✅ {model_name} model trained successfully")
                        if status['metrics']:
                            logger.info(f"   Accuracy: {status['metrics']['accuracy']:.3f}")
                    else:
                        logger.warning(f"⚠️ {model_name} model training failed")
            else:
                logger.warning("⚠️ Insufficient historical data for AI training")
                logger.info("💡 AI will operate in default mode with baseline confidence")
        
        except Exception as e:
            logger.error(f"❌ AI model initialization failed: {e}")
            # Continue without AI models
    
    async def process_signal_with_ai(self, signal: dict, market_data):
        """Process trading signal with AI enhancement."""
        
        self.ai_stats['total_signals'] += 1
        
        if not self.ai_enabled:
            # Traditional processing without AI
            logger.info(f"📈 Traditional signal: {signal['signal_type']} for {signal['symbol']}")
            return {
                'execute': True,
                'confidence': 0.5,
                'risk_score': 0.5,
                'reasoning': ['Traditional mode - no AI validation'],
                'ai_enhanced': False
            }
        
        logger.info(f"🧠 Processing {signal['signal_type']} signal for {signal['symbol']} with AI...")
        
        try:
            # AI Signal Validation
            ai_signal = await self.ai_engine.validate_signal(signal, market_data)
            
            logger.info(f"🎯 AI Confidence: {ai_signal.confidence:.2%}")
            logger.info(f"⚖️ Risk Score: {ai_signal.risk_score:.3f}")
            
            # Risk Assessment
            risk_assessment = await self.ai_engine.assess_risk(
                signal['symbol'], market_data, position_size=1.0
            )
            
            logger.info(f"⚠️ Risk Level: {risk_assessment['recommendation']}")
            
            # Anomaly Detection
            anomaly_result = await self.ai_engine.detect_anomalies(
                signal['symbol'], market_data
            )
            
            logger.info(f"🚨 Market Status: {anomaly_result['status']}")
            
            # Make final decision
            execute_decision = self._make_trading_decision(
                ai_signal, risk_assessment, anomaly_result
            )
            
            # Update statistics
            if execute_decision['execute']:
                self.ai_stats['ai_approved'] += 1
            else:
                self.ai_stats['ai_rejected'] += 1
                
                # Track rejection reasons
                if 'high risk' in ' '.join(execute_decision['reasoning']).lower():
                    self.ai_stats['high_risk_blocked'] += 1
                if 'anomaly' in ' '.join(execute_decision['reasoning']).lower():
                    self.ai_stats['anomaly_blocked'] += 1
            
            return execute_decision
        
        except Exception as e:
            logger.error(f"❌ AI processing failed: {e}")
            # Fall back to traditional mode
            return {
                'execute': False,
                'confidence': 0.0,
                'risk_score': 1.0,
                'reasoning': [f'AI processing error: {str(e)}'],
                'ai_enhanced': True
            }
    
    def _make_trading_decision(self, ai_signal, risk_assessment, anomaly_result) -> dict:
        """Make final trading decision based on AI analysis."""
        
        reasoning = []
        
        # Check AI signal confidence
        if ai_signal.execution_recommendation:
            reasoning.append(f"AI approves with {ai_signal.confidence:.2%} confidence")
        else:
            reasoning.append(f"AI rejects - low confidence ({ai_signal.confidence:.2%})")
        
        # Check risk level
        risk_acceptable = risk_assessment['risk_score'] < 0.7
        if risk_acceptable:
            reasoning.append(f"Risk acceptable ({risk_assessment['recommendation']})")
        else:
            reasoning.append(f"Risk too high ({risk_assessment['recommendation']})")
        
        # Check for anomalies
        anomaly_acceptable = anomaly_result['status'] != 'ANOMALY'
        if anomaly_acceptable:
            reasoning.append(f"Market normal ({anomaly_result['status']})")
        else:
            reasoning.append(f"Market anomaly detected ({anomaly_result['status']})")
        
        # Final decision logic
        execute = (
            ai_signal.execution_recommendation and 
            risk_acceptable and 
            anomaly_acceptable
        )
        
        return {
            'execute': execute,
            'confidence': ai_signal.confidence,
            'risk_score': ai_signal.risk_score,
            'position_size': risk_assessment.get('adjusted_position_size', 1.0),
            'reasoning': reasoning,
            'ai_enhanced': True,
            'ai_signal': ai_signal,
            'risk_assessment': risk_assessment,
            'anomaly_result': anomaly_result
        }
    
    async def run_trading_cycle(self, symbol: str = "BANKNIFTY", duration_minutes: int = 60):
        """Run a complete trading cycle with AI enhancement."""
        
        logger.info(f"🚀 Starting AI-enhanced trading cycle for {symbol}")
        logger.info(f"⏱️ Duration: {duration_minutes} minutes")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Initialize AI models
        await self.initialize_ai_models()
        
        self.running = True
        cycle_count = 0
        
        while self.running and datetime.now() < end_time:
            cycle_count += 1
            cycle_start = datetime.now()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Trading Cycle #{cycle_count} - {cycle_start.strftime('%H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            try:
                # Get latest market data
                data_end = datetime.now()
                data_start = data_end - timedelta(hours=2)  # 2 hours of data for analysis
                
                market_data = await self.data_layer.get_historical_data(
                    symbol, data_start, data_end, "1m"
                )
                
                if market_data.empty:
                    logger.warning("⚠️ No market data available")
                    await asyncio.sleep(60)  # Wait 1 minute before next cycle
                    continue
                
                logger.info(f"📥 Retrieved {len(market_data)} data points")
                
                # Generate trading signal using strategy
                signal = await self.strategy.generate_signal(symbol, market_data)
                
                if signal:
                    logger.info(f"📡 Strategy signal: {signal['signal_type']} at {signal.get('price', 'N/A')}")
                    
                    # Process signal with AI enhancement
                    ai_decision = await self.process_signal_with_ai(signal, market_data)
                    
                    # Log decision details
                    logger.info("\n🎯 AI-Enhanced Trading Decision:")
                    logger.info(f"Execute: {'✅ YES' if ai_decision['execute'] else '❌ NO'}")
                    logger.info(f"Confidence: {ai_decision['confidence']:.2%}")
                    logger.info(f"Risk Score: {ai_decision['risk_score']:.3f}")
                    
                    if 'position_size' in ai_decision:
                        logger.info(f"Position Size: {ai_decision['position_size']:.2f}")
                    
                    logger.info("Reasoning:")
                    for reason in ai_decision['reasoning']:
                        logger.info(f"  • {reason}")
                    
                    # Execute trade if approved
                    if ai_decision['execute']:
                        logger.info("💼 Executing trade...")
                        
                        # Prepare enhanced signal with AI insights
                        enhanced_signal = signal.copy()
                        enhanced_signal['ai_confidence'] = ai_decision['confidence']
                        enhanced_signal['ai_risk_score'] = ai_decision['risk_score']
                        enhanced_signal['position_size'] = ai_decision.get('position_size', 1.0)
                        
                        # Store signal for tracking
                        enhanced_signal['processed_at'] = datetime.now()
                        enhanced_signal['ai_reasoning'] = ai_decision['reasoning']
                        self.processed_signals.append(enhanced_signal)
                        
                        logger.info("✅ Trade signal processed and logged")
                        
                        # In a real system, this would execute actual trades
                        # await self.signal_executor.execute_signal(enhanced_signal)
                    else:
                        logger.info("🛑 Trade blocked by AI system")
                
                else:
                    logger.info("📉 No trading signal generated")
                
                # Print AI statistics
                if self.ai_enabled and cycle_count % 5 == 0:  # Every 5 cycles
                    self._print_ai_statistics()
            
            except Exception as e:
                logger.error(f"❌ Trading cycle error: {e}")
                import traceback
                traceback.print_exc()
            
            # Wait before next cycle
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            wait_time = max(60 - cycle_duration, 10)  # At least 10 seconds between cycles
            
            logger.info(f"⏳ Cycle completed in {cycle_duration:.1f}s. Waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
        
        logger.info(f"\n🏁 Trading cycle completed after {cycle_count} iterations")
        
        # Final statistics
        if self.ai_enabled:
            self._print_ai_statistics()
        
        logger.info(f"📊 Total signals processed: {len(self.processed_signals)}")
    
    def _print_ai_statistics(self):
        """Print AI performance statistics."""
        
        if not self.ai_enabled or self.ai_stats['total_signals'] == 0:
            return
        
        stats = self.ai_stats
        total = stats['total_signals']
        
        logger.info("\n📊 AI Enhancement Statistics:")
        logger.info(f"  Total Signals Analyzed: {total}")
        logger.info(f"  AI Approved: {stats['ai_approved']} ({stats['ai_approved']/total:.1%})")
        logger.info(f"  AI Rejected: {stats['ai_rejected']} ({stats['ai_rejected']/total:.1%})")
        
        if stats['ai_rejected'] > 0:
            logger.info(f"  Blocked - High Risk: {stats['high_risk_blocked']}")
            logger.info(f"  Blocked - Anomalies: {stats['anomaly_blocked']}")
    
    def stop(self):
        """Stop the trading system."""
        self.running = False
        logger.info("🛑 Trading system stop requested")


async def main():
    """Main function to demonstrate AI-enhanced trading."""
    
    logger.info("🚀 AlphaStock AI-Enhanced Trading System")
    logger.info("="*50)
    
    # Create trading system
    trading_system = AIEnhancedTradingSystem(ai_confidence_threshold=0.75)
    
    try:
        # Run trading cycle for 15 minutes (demo)
        await trading_system.run_trading_cycle(
            symbol="BANKNIFTY", 
            duration_minutes=15
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ User interrupted - shutting down...")
        trading_system.stop()
    
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("👋 AI-Enhanced Trading System shutdown complete")


if __name__ == "__main__":
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    
    # Run the system
    asyncio.run(main())
