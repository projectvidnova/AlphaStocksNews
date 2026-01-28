"""
Complete Workflow Runner for AlphaStock Trading System

Implements the complete end-to-end workflow with Bank Nifty focus:
1. Data availability check and collection
2. Analysis engine validation
3. Strategy execution testing
4. Gap identification and recommendations
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.orchestrator import AlphaStockOrchestrator
from src.core.workflow_validator import StrategyWorkflowValidator
from src.utils.logger_setup import setup_logger
from src.utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class CompleteWorkflowRunner:
    """
    Comprehensive workflow runner that ensures complete end-to-end functionality.
    
    Workflow Steps:
    1. Initialize system components
    2. Validate Bank Nifty historical data (1 year)
    3. Run comprehensive analysis
    4. Execute strategy validation
    5. Identify and report gaps
    6. Provide actionable recommendations
    """
    
    def __init__(self):
        self.logger = setup_logger("CompleteWorkflowRunner")
        self.orchestrator = None
        self.validator = None
        self.results = {}
    
    async def run_complete_workflow(self) -> Dict[str, Any]:
        """Execute the complete workflow validation and setup."""
        self.logger.info("🚀 Starting Complete AlphaStock Workflow")
        self.logger.info("=" * 60)
        
        workflow_results = {
            'start_time': get_current_time().isoformat(),
            'phases': {},
            'overall_status': 'unknown',
            'recommendations': [],
            'next_steps': []
        }
        
        try:
            # Phase 1: System Initialization
            workflow_results['phases']['initialization'] = await self._phase_1_initialization()
            
            # Phase 2: Historical Data Validation
            workflow_results['phases']['historical_data'] = await self._phase_2_historical_data()
            
            # Phase 3: Analysis Engine Testing
            workflow_results['phases']['analysis_engine'] = await self._phase_3_analysis_engine()
            
            # Phase 4: Strategy Workflow Validation
            workflow_results['phases']['strategy_validation'] = await self._phase_4_strategy_validation()
            
            # Phase 5: Complete System Validation
            workflow_results['phases']['system_validation'] = await self._phase_5_system_validation()
            
            # Phase 6: Generate Recommendations
            workflow_results['recommendations'] = self._generate_comprehensive_recommendations(workflow_results)
            workflow_results['next_steps'] = self._generate_next_steps(workflow_results)
            workflow_results['overall_status'] = self._calculate_overall_status(workflow_results)
            
            # Final Report
            await self._generate_final_report(workflow_results)
            
            return workflow_results
            
        except Exception as e:
            self.logger.error(f"Critical error in workflow: {e}")
            workflow_results['error'] = str(e)
            workflow_results['overall_status'] = 'failed'
            return workflow_results
        
        finally:
            # Cleanup
            if self.orchestrator:
                await self.orchestrator.stop()
    
    async def _phase_1_initialization(self) -> Dict[str, Any]:
        """Phase 1: Initialize all system components."""
        self.logger.info("📋 Phase 1: System Initialization")
        
        phase_result = {
            'status': 'unknown',
            'components_initialized': [],
            'failures': [],
            'duration_seconds': 0
        }
        
        start_time = get_current_time()
        
        try:
            # Initialize orchestrator
            self.logger.info("Initializing orchestrator...")
            self.orchestrator = AlphaStockOrchestrator()
            
            # Initialize all components
            await self.orchestrator.initialize()
            
            # Check what got initialized
            components = {
                'api_client': self.orchestrator.api_client is not None,
                'data_layer': self.orchestrator.data_layer is not None,
                'historical_data_manager': self.orchestrator.historical_data_manager is not None,
                'analysis_engine': self.orchestrator.analysis_engine is not None,
                'signal_manager': self.orchestrator.signal_manager is not None,
                'runners': self.orchestrator.runner_manager is not None
            }
            
            for component, initialized in components.items():
                if initialized:
                    phase_result['components_initialized'].append(component)
                else:
                    phase_result['failures'].append(f"Failed to initialize {component}")
            
            success_rate = len(phase_result['components_initialized']) / len(components)
            
            if success_rate >= 0.8:
                phase_result['status'] = 'success'
                self.logger.info("✅ System initialization successful")
            elif success_rate >= 0.5:
                phase_result['status'] = 'partial'
                self.logger.warning("⚠️ Partial system initialization")
            else:
                phase_result['status'] = 'failed'
                self.logger.error("❌ System initialization failed")
            
            phase_result['success_rate'] = success_rate
            
        except Exception as e:
            phase_result['status'] = 'failed'
            phase_result['error'] = str(e)
            self.logger.error(f"❌ Phase 1 failed: {e}")
        
        finally:
            phase_result['duration_seconds'] = (get_current_time() - start_time).total_seconds()
        
        return phase_result
    
    async def _phase_2_historical_data(self) -> Dict[str, Any]:
        """Phase 2: Validate Bank Nifty historical data availability."""
        self.logger.info("📊 Phase 2: Bank Nifty Historical Data Validation")
        
        phase_result = {
            'status': 'unknown',
            'bank_nifty_data_status': {},
            'data_quality_score': 0.0,
            'recommendations': []
        }
        
        try:
            if not self.orchestrator.historical_data_manager:
                phase_result['status'] = 'skipped'
                phase_result['error'] = 'Historical data manager not available'
                return phase_result
            
            # Check Bank Nifty data specifically
            self.logger.info("Checking Bank Nifty historical data...")
            
            bank_nifty_results = await self.orchestrator.historical_data_manager.ensure_historical_data(
                symbol='BANKNIFTY',
                asset_type='INDEX',
                timeframes=['15minute', '1day'],
                years_back=1  # 1 year as requested
            )
            
            phase_result['bank_nifty_data_status'] = bank_nifty_results
            
            # Test data quality
            analysis_data = await self.orchestrator.historical_data_manager.get_analysis_data(
                'BANKNIFTY', '15minute', days_back=30
            )
            
            if analysis_data is not None and not analysis_data.empty:
                # Calculate data quality score
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                has_required_columns = all(col in analysis_data.columns for col in required_columns)
                data_completeness = len(analysis_data) / (30 * 24 * 4)  # Expected 15min bars in 30 days
                no_missing_values = analysis_data[required_columns].notna().all().all()
                
                quality_score = (
                    (0.4 if has_required_columns else 0) +
                    (0.4 * min(1.0, data_completeness)) +
                    (0.2 if no_missing_values else 0)
                )
                
                phase_result['data_quality_score'] = quality_score
                phase_result['data_points'] = len(analysis_data)
                
                if quality_score >= 0.8:
                    phase_result['status'] = 'success'
                    self.logger.info(f"✅ Bank Nifty data quality: {quality_score:.2f}")
                elif quality_score >= 0.6:
                    phase_result['status'] = 'partial'
                    self.logger.warning(f"⚠️ Bank Nifty data quality: {quality_score:.2f}")
                else:
                    phase_result['status'] = 'poor'
                    self.logger.error(f"❌ Bank Nifty data quality: {quality_score:.2f}")
                
                # Generate recommendations
                if not has_required_columns:
                    phase_result['recommendations'].append("Fix data schema - missing required columns")
                if data_completeness < 0.8:
                    phase_result['recommendations'].append("Improve data collection - significant data gaps detected")
                if not no_missing_values:
                    phase_result['recommendations'].append("Clean data quality - missing values found")
            else:
                phase_result['status'] = 'failed'
                phase_result['error'] = 'No analysis data available'
                phase_result['recommendations'].append("Run historical data collection for Bank Nifty")
        
        except Exception as e:
            phase_result['status'] = 'failed'
            phase_result['error'] = str(e)
            self.logger.error(f"❌ Phase 2 failed: {e}")
        
        return phase_result
    
    async def _phase_3_analysis_engine(self) -> Dict[str, Any]:
        """Phase 3: Test analysis engine functionality."""
        self.logger.info("🔍 Phase 3: Analysis Engine Testing")
        
        phase_result = {
            'status': 'unknown',
            'analysis_results': {},
            'capabilities': []
        }
        
        try:
            if not self.orchestrator.analysis_engine:
                phase_result['status'] = 'skipped'
                phase_result['error'] = 'Analysis engine not available'
                return phase_result
            
            # Test comprehensive market analysis
            self.logger.info("Running Bank Nifty market analysis...")
            
            analysis = await self.orchestrator.analysis_engine.analyze_market_conditions(
                'BANKNIFTY', '15minute'
            )
            
            if analysis and 'error' not in analysis:
                phase_result['analysis_results'] = analysis
                
                # Check analysis capabilities
                capabilities = []
                if 'trend_analysis' in analysis:
                    capabilities.append('Trend Analysis')
                if 'momentum_indicators' in analysis:
                    capabilities.append('Technical Indicators')
                if 'risk_metrics' in analysis:
                    capabilities.append('Risk Analysis')
                if 'pattern_recognition' in analysis:
                    capabilities.append('Pattern Detection')
                if 'strategy_signals' in analysis:
                    capabilities.append('Strategy Signals')
                
                phase_result['capabilities'] = capabilities
                
                # Test comprehensive report generation
                report = await self.orchestrator.analysis_engine.generate_comprehensive_report(
                    'BANKNIFTY', '15minute'
                )
                
                if report and 'error' not in report:
                    phase_result['comprehensive_report_available'] = True
                    phase_result['market_condition'] = report.get('executive_summary', {}).get('market_condition')
                    phase_result['recommendation'] = report.get('executive_summary', {}).get('recommendation')
                
                if len(capabilities) >= 4:
                    phase_result['status'] = 'success'
                    self.logger.info(f"✅ Analysis engine functional: {len(capabilities)} capabilities")
                else:
                    phase_result['status'] = 'partial'
                    self.logger.warning(f"⚠️ Limited analysis capabilities: {len(capabilities)}")
            else:
                phase_result['status'] = 'failed'
                phase_result['error'] = analysis.get('error', 'Analysis failed')
                self.logger.error("❌ Analysis engine test failed")
        
        except Exception as e:
            phase_result['status'] = 'failed'
            phase_result['error'] = str(e)
            self.logger.error(f"❌ Phase 3 failed: {e}")
        
        return phase_result
    
    async def _phase_4_strategy_validation(self) -> Dict[str, Any]:
        """Phase 4: Validate strategy execution workflow."""
        self.logger.info("🎯 Phase 4: Strategy Execution Validation")
        
        phase_result = {
            'status': 'unknown',
            'strategy_tests': {},
            'signals_generated': 0
        }
        
        try:
            # Test MA Crossover strategy with Bank Nifty
            if self.orchestrator.strategy_factory:
                self.logger.info("Testing MA Crossover strategy with Bank Nifty...")
                
                strategy = self.orchestrator.strategy_factory.create_strategy(
                    strategy_name='ma_crossover',
                    config={
                        'symbols': ['BANKNIFTY'],
                        'parameters': {
                            'fast_period': 9,
                            'slow_period': 21,
                            'ma_type': 'EMA'
                        }
                    }
                )
                
                if strategy:
                    # Get test data
                    if self.orchestrator.historical_data_manager:
                        data = await self.orchestrator.historical_data_manager.get_analysis_data(
                            'BANKNIFTY', '15minute', days_back=10
                        )
                        
                        if data is not None and not data.empty:
                            # Run strategy analysis
                            analysis_result = strategy.analyze(data)
                            
                            if analysis_result:
                                phase_result['strategy_tests']['ma_crossover'] = {
                                    'status': 'success',
                                    'signals': len(analysis_result.get('signals', [])),
                                    'analysis_data': analysis_result
                                }
                                
                                signals_count = len(analysis_result.get('signals', []))
                                phase_result['signals_generated'] = signals_count
                                
                                # Test signal creation
                                if signals_count > 0 and self.orchestrator.signal_manager:
                                    sample_signal = analysis_result['signals'][0]
                                    await self.orchestrator.signal_manager.add_signal(
                                        symbol='BANKNIFTY',
                                        strategy='ma_crossover_test',
                                        signal_type=sample_signal.get('type', 'BUY'),
                                        entry_price=sample_signal.get('price', 50000),
                                        stop_loss_pct=2.0,
                                        target_pct=4.0
                                    )
                                    
                                    phase_result['signal_storage_tested'] = True
                                
                                phase_result['status'] = 'success'
                                self.logger.info(f"✅ Strategy validation successful: {signals_count} signals")
                            else:
                                phase_result['status'] = 'failed'
                                phase_result['error'] = 'Strategy analysis failed'
                        else:
                            phase_result['status'] = 'failed'
                            phase_result['error'] = 'No data available for strategy testing'
                    else:
                        phase_result['status'] = 'failed'
                        phase_result['error'] = 'Historical data manager not available'
                else:
                    phase_result['status'] = 'failed'
                    phase_result['error'] = 'Strategy creation failed'
            else:
                phase_result['status'] = 'failed'
                phase_result['error'] = 'Strategy factory not available'
        
        except Exception as e:
            phase_result['status'] = 'failed'
            phase_result['error'] = str(e)
            self.logger.error(f"❌ Phase 4 failed: {e}")
        
        return phase_result
    
    async def _phase_5_system_validation(self) -> Dict[str, Any]:
        """Phase 5: Complete system validation."""
        self.logger.info("🔧 Phase 5: Complete System Validation")
        
        phase_result = {
            'status': 'unknown',
            'validation_results': {}
        }
        
        try:
            if self.orchestrator:
                # Initialize validator
                self.validator = StrategyWorkflowValidator(self.orchestrator)
                
                # Run complete validation
                validation_results = await self.validator.validate_complete_workflow()
                phase_result['validation_results'] = validation_results
                
                overall_status = validation_results.get('overall_status', 'unknown')
                
                if overall_status in ['excellent', 'good']:
                    phase_result['status'] = 'success'
                    self.logger.info(f"✅ Complete system validation: {overall_status}")
                elif overall_status == 'fair':
                    phase_result['status'] = 'partial'
                    self.logger.warning(f"⚠️ System validation: {overall_status}")
                else:
                    phase_result['status'] = 'failed'
                    self.logger.error(f"❌ System validation: {overall_status}")
            else:
                phase_result['status'] = 'failed'
                phase_result['error'] = 'Orchestrator not available'
        
        except Exception as e:
            phase_result['status'] = 'failed'
            phase_result['error'] = str(e)
            self.logger.error(f"❌ Phase 5 failed: {e}")
        
        return phase_result
    
    def _generate_comprehensive_recommendations(self, workflow_results: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations based on all phases."""
        recommendations = []
        
        phases = workflow_results.get('phases', {})
        
        # Initialization recommendations
        init_phase = phases.get('initialization', {})
        if init_phase.get('status') != 'success':
            recommendations.append("🔧 Fix system initialization issues before proceeding")
            recommendations.append("   - Run: python setup_database.py")
            recommendations.append("   - Run: python migrate_database.py")
        
        # Data recommendations
        data_phase = phases.get('historical_data', {})
        if data_phase.get('data_quality_score', 0) < 0.8:
            recommendations.append("📊 Improve Bank Nifty historical data quality")
            recommendations.append("   - Ensure API client is configured correctly")
            recommendations.append("   - Run data collection during market hours")
            recommendations.append("   - Verify database connectivity")
        
        # Analysis recommendations
        analysis_phase = phases.get('analysis_engine', {})
        if analysis_phase.get('status') != 'success':
            recommendations.append("🔍 Fix analysis engine issues")
            recommendations.append("   - Ensure sufficient historical data is available")
            recommendations.append("   - Verify technical indicator calculations")
        
        # Strategy recommendations
        strategy_phase = phases.get('strategy_validation', {})
        if strategy_phase.get('signals_generated', 0) == 0:
            recommendations.append("🎯 Improve strategy signal generation")
            recommendations.append("   - Review strategy parameters")
            recommendations.append("   - Test with different timeframes")
            recommendations.append("   - Validate data quality for strategy analysis")
        
        # System recommendations
        system_phase = phases.get('system_validation', {})
        validation_results = system_phase.get('validation_results', {})
        if validation_results.get('overall_status') not in ['excellent', 'good']:
            system_recommendations = validation_results.get('recommendations', [])
            for rec in system_recommendations:
                recommendations.append(f"🔧 {rec}")
        
        # Priority recommendations
        if not recommendations:
            recommendations.append("✅ System is functioning well!")
            recommendations.append("🚀 Ready to start live trading simulation")
            recommendations.append("📈 Consider enabling paper trading mode")
        else:
            recommendations.insert(0, "🚨 Priority: Address critical issues first")
        
        return recommendations
    
    def _generate_next_steps(self, workflow_results: Dict[str, Any]) -> List[str]:
        """Generate actionable next steps."""
        next_steps = []
        overall_status = workflow_results.get('overall_status', 'unknown')
        
        if overall_status in ['excellent', 'good']:
            next_steps.extend([
                "1. Enable paper trading mode in config/production.json",
                "2. Start the system: python main.py",
                "3. Monitor logs for signal generation",
                "4. Review strategy performance after 1 week",
                "5. Consider adding more strategies or symbols"
            ])
        elif overall_status == 'partial':
            next_steps.extend([
                "1. Fix identified issues from recommendations",
                "2. Re-run workflow validation: python complete_workflow.py",
                "3. Test individual components that failed",
                "4. Start with limited functionality",
                "5. Gradually enable more features as issues are resolved"
            ])
        else:
            next_steps.extend([
                "1. Review logs for detailed error information",
                "2. Ensure database is set up: python setup_database.py",
                "3. Run migration: python migrate_database.py",
                "4. Configure API credentials if needed",
                "5. Re-run complete workflow validation"
            ])
        
        return next_steps
    
    def _calculate_overall_status(self, workflow_results: Dict[str, Any]) -> str:
        """Calculate overall workflow status."""
        phases = workflow_results.get('phases', {})
        
        success_phases = sum(1 for phase in phases.values() if phase.get('status') == 'success')
        partial_phases = sum(1 for phase in phases.values() if phase.get('status') == 'partial')
        total_phases = len(phases)
        
        if total_phases == 0:
            return 'unknown'
        
        success_rate = success_phases / total_phases
        partial_rate = (success_phases + partial_phases) / total_phases
        
        if success_rate >= 0.8:
            return 'excellent'
        elif success_rate >= 0.6:
            return 'good'
        elif partial_rate >= 0.6:
            return 'partial'
        else:
            return 'poor'
    
    async def _generate_final_report(self, workflow_results: Dict[str, Any]):
        """Generate and display final workflow report."""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("🎯 ALPHASTOCK COMPLETE WORKFLOW REPORT")
        self.logger.info("=" * 80)
        
        overall_status = workflow_results.get('overall_status', 'unknown')
        status_emoji = {
            'excellent': '🟢',
            'good': '🟡',
            'partial': '🟠',
            'poor': '🔴',
            'unknown': '⚪'
        }
        
        self.logger.info(f"\nOverall Status: {status_emoji.get(overall_status, '⚪')} {overall_status.upper()}")
        
        # Phase Results
        self.logger.info(f"\n📋 Phase Results:")
        phases = workflow_results.get('phases', {})
        for phase_name, phase_result in phases.items():
            status = phase_result.get('status', 'unknown')
            emoji = '✅' if status == 'success' else '⚠️' if status == 'partial' else '❌'
            self.logger.info(f"   {emoji} {phase_name.replace('_', ' ').title()}: {status}")
        
        # Bank Nifty Data Status
        data_phase = phases.get('historical_data', {})
        if 'data_quality_score' in data_phase:
            quality_score = data_phase['data_quality_score']
            self.logger.info(f"\n📊 Bank Nifty Data Quality: {quality_score:.2f}/1.00")
        
        # Strategy Results
        strategy_phase = phases.get('strategy_validation', {})
        if 'signals_generated' in strategy_phase:
            signals = strategy_phase['signals_generated']
            self.logger.info(f"🎯 Strategy Signals Generated: {signals}")
        
        # Recommendations
        recommendations = workflow_results.get('recommendations', [])
        if recommendations:
            self.logger.info(f"\n💡 Recommendations:")
            for rec in recommendations[:5]:  # Show top 5
                self.logger.info(f"   {rec}")
            
            if len(recommendations) > 5:
                self.logger.info(f"   ... and {len(recommendations) - 5} more")
        
        # Next Steps
        next_steps = workflow_results.get('next_steps', [])
        if next_steps:
            self.logger.info(f"\n🚀 Next Steps:")
            for step in next_steps:
                self.logger.info(f"   {step}")
        
        self.logger.info("\n" + "=" * 80)
        
        # Summary message
        if overall_status == 'excellent':
            self.logger.info("🎉 Congratulations! Your AlphaStock system is ready for trading!")
        elif overall_status == 'good':
            self.logger.info("👍 Your AlphaStock system is mostly ready. Address minor issues and start trading!")
        elif overall_status == 'partial':
            self.logger.info("⚠️ Your AlphaStock system needs some fixes before trading. Please follow recommendations.")
        else:
            self.logger.info("🔧 Your AlphaStock system needs significant fixes. Please address critical issues first.")


async def main():
    """Main function to run the complete workflow."""
    print("🚀 AlphaStock Complete Workflow Runner")
    print("This will validate your entire trading system end-to-end")
    print("=" * 60)
    
    runner = CompleteWorkflowRunner()
    
    try:
        results = await runner.run_complete_workflow()
        
        # Save results to file
        import json
        results_path = Path(__file__).parent / "workflow_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: {results_path}")
        
        return results['overall_status'] in ['excellent', 'good']
        
    except KeyboardInterrupt:
        print("\n\n⏸️ Workflow interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
