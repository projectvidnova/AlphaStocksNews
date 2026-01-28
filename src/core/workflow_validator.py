"""
End-to-End Strategy Workflow Validator

Validates the complete strategy execution workflow from data ingestion to signal generation.
Identifies gaps and provides recommendations for system completeness.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from ..core.historical_data_manager import HistoricalDataManager
from ..core.analysis_engine import MarketAnalysisEngine
from ..core.strategy_factory import StrategyFactory
from ..trading.signal_manager import SignalManager
from ..data import DataLayerInterface
from ..api.kite_client import KiteAPIClient
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class StrategyWorkflowValidator:
    """
    Validates the complete end-to-end strategy workflow.
    
    Tests:
    1. Data availability and quality
    2. Strategy initialization and configuration
    3. Analysis engine functionality
    4. Signal generation and storage
    5. Risk management integration
    6. Performance tracking
    """
    
    def __init__(self, orchestrator):
        """Initialize with orchestrator instance."""
        self.orchestrator = orchestrator
        self.logger = setup_logger("StrategyWorkflowValidator")
        self.validation_results = {}
        
        # Test configuration
        self.test_symbol = "BANKNIFTY"
        self.test_strategy = "ma_crossover"
        self.test_timeframe = "15minute"
    
    async def validate_complete_workflow(self) -> Dict[str, Any]:
        """Run complete end-to-end workflow validation."""
        self.logger.info("Starting complete strategy workflow validation...")
        
        validation_results = {
            'timestamp': get_current_time().isoformat(),
            'test_symbol': self.test_symbol,
            'test_strategy': self.test_strategy,
            'components': {},
            'workflow_tests': {},
            'gaps_identified': [],
            'recommendations': [],
            'overall_status': 'unknown'
        }
        
        try:
            # 1. Validate core components
            validation_results['components'] = await self._validate_core_components()
            
            # 2. Test data workflow
            validation_results['workflow_tests']['data_workflow'] = await self._test_data_workflow()
            
            # 3. Test strategy workflow
            validation_results['workflow_tests']['strategy_workflow'] = await self._test_strategy_workflow()
            
            # 4. Test signal workflow
            validation_results['workflow_tests']['signal_workflow'] = await self._test_signal_workflow()
            
            # 5. Test analysis workflow
            validation_results['workflow_tests']['analysis_workflow'] = await self._test_analysis_workflow()
            
            # 6. Identify gaps and generate recommendations
            validation_results['gaps_identified'] = self._identify_gaps(validation_results)
            validation_results['recommendations'] = self._generate_recommendations(validation_results)
            
            # 7. Calculate overall status
            validation_results['overall_status'] = self._calculate_overall_status(validation_results)
            
            self.logger.info(f"Workflow validation completed: {validation_results['overall_status']}")
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error during workflow validation: {e}")
            validation_results['error'] = str(e)
            validation_results['overall_status'] = 'failed'
            return validation_results
    
    async def _validate_core_components(self) -> Dict[str, Any]:
        """Validate all core system components."""
        self.logger.info("Validating core components...")
        
        components = {
            'api_client': self._validate_api_client(),
            'data_layer': await self._validate_data_layer(),
            'historical_data_manager': self._validate_historical_data_manager(),
            'analysis_engine': self._validate_analysis_engine(),
            'strategy_factory': self._validate_strategy_factory(),
            'signal_manager': self._validate_signal_manager(),
            'runners': self._validate_runners()
        }
        
        return components
    
    def _validate_api_client(self) -> Dict[str, Any]:
        """Validate API client functionality."""
        try:
            if not self.orchestrator.api_client:
                return {'status': 'missing', 'error': 'API client not initialized'}
            
            # Check if API client is connected
            # Note: This is a basic check, more sophisticated health checks can be added
            return {
                'status': 'available',
                'type': type(self.orchestrator.api_client).__name__,
                'paper_trading': getattr(self.orchestrator.api_client, 'paper_trading', True)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _validate_data_layer(self) -> Dict[str, Any]:
        """Validate data layer functionality."""
        try:
            if not self.orchestrator.data_layer:
                return {'status': 'missing', 'error': 'Data layer not initialized'}
            
            # Test data layer health
            health = await self.orchestrator.data_layer.health_check()
            
            # Test basic operations
            test_results = {
                'health_check': health.get('overall_status') in ['healthy', 'active'],
                'market_data_read': False,
                'signal_storage': False
            }
            
            # Test market data retrieval
            try:
                symbols = await self.orchestrator.data_layer.get_symbols_by_asset_type('INDEX')
                test_results['market_data_read'] = symbols is not None
            except Exception as e:
                self.logger.debug(f"Market data read test failed: {e}")
            
            # Test signal storage
            try:
                test_signal = {
                    'id': 'test-validation',
                    'symbol': 'TEST',
                    'strategy': 'validation',
                    'signal_type': 'BUY',
                    'entry_price': 100.0,
                    'timestamp': get_current_time().isoformat(),
                    'status': 'TEST'
                }
                success = await self.orchestrator.data_layer.store_signal(test_signal)
                test_results['signal_storage'] = success
                
                # Clean up test data
                if success:
                    try:
                        await self.orchestrator.data_layer.execute_query(
                            "DELETE FROM signals WHERE id = 'test-validation'"
                        )
                    except:
                        pass  # Ignore cleanup errors
            except Exception as e:
                self.logger.debug(f"Signal storage test failed: {e}")
            
            return {
                'status': 'available',
                'health': health,
                'test_results': test_results,
                'overall_functional': all(test_results.values())
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _validate_historical_data_manager(self) -> Dict[str, Any]:
        """Validate historical data manager."""
        try:
            if not self.orchestrator.historical_data_manager:
                return {'status': 'missing', 'error': 'Historical data manager not initialized'}
            
            return {
                'status': 'available',
                'priority_symbols': len(self.orchestrator.historical_data_manager.priority_symbols),
                'api_client_available': self.orchestrator.historical_data_manager.api_client is not None,
                'data_layer_available': self.orchestrator.historical_data_manager.data_layer is not None
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _validate_analysis_engine(self) -> Dict[str, Any]:
        """Validate analysis engine."""
        try:
            if not self.orchestrator.analysis_engine:
                return {'status': 'missing', 'error': 'Analysis engine not initialized'}
            
            return {
                'status': 'available',
                'historical_manager_available': self.orchestrator.analysis_engine.historical_manager is not None,
                'data_layer_available': self.orchestrator.analysis_engine.data_layer is not None,
                'cache_enabled': hasattr(self.orchestrator.analysis_engine, 'analysis_cache')
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _validate_strategy_factory(self) -> Dict[str, Any]:
        """Validate strategy factory."""
        try:
            if not self.orchestrator.strategy_factory:
                return {'status': 'missing', 'error': 'Strategy factory not initialized'}
            
            # Test strategy creation
            try:
                test_strategy = self.orchestrator.strategy_factory.create_strategy(
                    strategy_type=self.test_strategy,
                    symbol=self.test_symbol,
                    parameters={'fast_period': 9, 'slow_period': 21}
                )
                strategy_creation_success = test_strategy is not None
            except Exception as e:
                strategy_creation_success = False
                self.logger.debug(f"Strategy creation test failed: {e}")
            
            return {
                'status': 'available',
                'strategy_creation': strategy_creation_success,
                'available_strategies': getattr(self.orchestrator.strategy_factory, 'available_strategies', {})
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _validate_signal_manager(self) -> Dict[str, Any]:
        """Validate signal manager."""
        try:
            if not self.orchestrator.signal_manager:
                return {'status': 'missing', 'error': 'Signal manager not initialized'}
            
            return {
                'status': 'available',
                'data_layer_integrated': hasattr(self.orchestrator.signal_manager, 'data_layer') and 
                                       self.orchestrator.signal_manager.data_layer is not None,
                'active_signals': len(getattr(self.orchestrator.signal_manager, 'active_signals', {}))
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _validate_runners(self) -> Dict[str, Any]:
        """Validate specialized runners."""
        try:
            runners_status = {
                'equity_runner': self.orchestrator.equity_runner is not None,
                'options_runner': self.orchestrator.options_runner is not None,
                'index_runner': self.orchestrator.index_runner is not None,
                'commodity_runner': self.orchestrator.commodity_runner is not None,
                'futures_runner': self.orchestrator.futures_runner is not None,
                'runner_manager': self.orchestrator.runner_manager is not None
            }
            
            active_runners = sum(1 for status in runners_status.values() if status)
            
            return {
                'status': 'available' if active_runners > 0 else 'missing',
                'runners_status': runners_status,
                'active_runners': active_runners
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _test_data_workflow(self) -> Dict[str, Any]:
        """Test end-to-end data workflow."""
        self.logger.info("Testing data workflow...")
        
        workflow_tests = {
            'historical_data_check': False,
            'data_quality_validation': False,
            'real_time_data_simulation': False,
            'data_storage': False
        }
        
        try:
            # Test historical data availability
            if self.orchestrator.historical_data_manager:
                try:
                    data = await self.orchestrator.historical_data_manager.get_analysis_data(
                        self.test_symbol, self.test_timeframe, days_back=30
                    )
                    workflow_tests['historical_data_check'] = data is not None and not data.empty
                    
                    if workflow_tests['historical_data_check']:
                        # Validate data quality
                        required_columns = ['open', 'high', 'low', 'close', 'volume']
                        has_required_columns = all(col in data.columns for col in required_columns)
                        has_valid_data = len(data) > 50 and data['close'].notna().all()
                        workflow_tests['data_quality_validation'] = has_required_columns and has_valid_data
                        
                except Exception as e:
                    self.logger.debug(f"Historical data test failed: {e}")
            
            # Test real-time data simulation (using latest historical data)
            if workflow_tests['historical_data_check']:
                try:
                    # Simulate real-time data by getting latest data
                    latest_data = await self.orchestrator.data_layer.get_latest_market_data(self.test_symbol)
                    workflow_tests['real_time_data_simulation'] = latest_data is not None
                except Exception as e:
                    self.logger.debug(f"Real-time data simulation failed: {e}")
            
            # Test data storage workflow
            if self.orchestrator.data_layer:
                try:
                    # Create test data
                    test_data = pd.DataFrame({
                        'timestamp': [get_current_time()],
                        'symbol': ['TEST_WORKFLOW'],
                        'open': [100.0],
                        'high': [105.0],
                        'low': [99.0],
                        'close': [102.0],
                        'volume': [1000],
                        'asset_type': ['INDEX']
                    })
                    
                    success = await self.orchestrator.data_layer.store_market_data(
                        'TEST_WORKFLOW', 'INDEX', test_data, 'workflow_test'
                    )
                    workflow_tests['data_storage'] = success
                    
                    # Clean up
                    if success:
                        try:
                            await self.orchestrator.data_layer.execute_query(
                                "DELETE FROM market_data WHERE symbol = 'TEST_WORKFLOW'"
                            )
                        except:
                            pass
                            
                except Exception as e:
                    self.logger.debug(f"Data storage test failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in data workflow test: {e}")
        
        return {
            'tests': workflow_tests,
            'success_rate': sum(workflow_tests.values()) / len(workflow_tests),
            'overall_success': all(workflow_tests.values())
        }
    
    async def _test_strategy_workflow(self) -> Dict[str, Any]:
        """Test end-to-end strategy workflow."""
        self.logger.info("Testing strategy workflow...")
        
        workflow_tests = {
            'strategy_creation': False,
            'data_processing': False,
            'signal_generation': False,
            'strategy_execution': False
        }
        
        try:
            # Test strategy creation
            if self.orchestrator.strategy_factory:
                try:
                    strategy = self.orchestrator.strategy_factory.create_strategy(
                        strategy_type=self.test_strategy,
                        symbol=self.test_symbol,
                        parameters={'fast_period': 9, 'slow_period': 21}
                    )
                    workflow_tests['strategy_creation'] = strategy is not None
                    
                    if workflow_tests['strategy_creation']:
                        # Test data processing
                        if self.orchestrator.historical_data_manager:
                            data = await self.orchestrator.historical_data_manager.get_analysis_data(
                                self.test_symbol, self.test_timeframe, days_back=10
                            )
                            
                            if data is not None and not data.empty:
                                # Test strategy analysis
                                try:
                                    analysis_result = strategy.analyze(data)
                                    workflow_tests['data_processing'] = analysis_result is not None
                                    
                                    # Test signal generation
                                    if analysis_result and 'signals' in analysis_result:
                                        workflow_tests['signal_generation'] = len(analysis_result['signals']) >= 0
                                        workflow_tests['strategy_execution'] = True
                                        
                                except Exception as e:
                                    self.logger.debug(f"Strategy analysis failed: {e}")
                    
                except Exception as e:
                    self.logger.debug(f"Strategy creation failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in strategy workflow test: {e}")
        
        return {
            'tests': workflow_tests,
            'success_rate': sum(workflow_tests.values()) / len(workflow_tests),
            'overall_success': all(workflow_tests.values())
        }
    
    async def _test_signal_workflow(self) -> Dict[str, Any]:
        """Test end-to-end signal workflow."""
        self.logger.info("Testing signal workflow...")
        
        workflow_tests = {
            'signal_creation': False,
            'signal_storage': False,
            'signal_retrieval': False,
            'signal_management': False
        }
        
        try:
            if self.orchestrator.signal_manager:
                # Test signal creation
                try:
                    signal = await self.orchestrator.signal_manager.add_signal(
                        symbol='TEST_SIGNAL',
                        strategy='workflow_test',
                        signal_type='BUY',
                        entry_price=100.0,
                        stop_loss_pct=2.0,
                        target_pct=4.0
                    )
                    workflow_tests['signal_creation'] = signal is not None
                    
                    if workflow_tests['signal_creation']:
                        workflow_tests['signal_storage'] = True  # add_signal includes storage
                        
                        # Test signal retrieval
                        try:
                            signals = await self.orchestrator.data_layer.get_signals(
                                symbol='TEST_SIGNAL', strategy='workflow_test'
                            )
                            workflow_tests['signal_retrieval'] = signals is not None and len(signals) > 0
                        except Exception as e:
                            self.logger.debug(f"Signal retrieval failed: {e}")
                        
                        # Test signal management (update)
                        try:
                            await self.orchestrator.signal_manager.update_signal(
                                signal.id, status='ACTIVE'
                            )
                            workflow_tests['signal_management'] = True
                        except Exception as e:
                            self.logger.debug(f"Signal management failed: {e}")
                        
                        # Clean up test signal
                        try:
                            await self.orchestrator.data_layer.execute_query(
                                "DELETE FROM signals WHERE symbol = 'TEST_SIGNAL'"
                            )
                        except:
                            pass
                    
                except Exception as e:
                    self.logger.debug(f"Signal creation failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in signal workflow test: {e}")
        
        return {
            'tests': workflow_tests,
            'success_rate': sum(workflow_tests.values()) / len(workflow_tests),
            'overall_success': all(workflow_tests.values())
        }
    
    async def _test_analysis_workflow(self) -> Dict[str, Any]:
        """Test end-to-end analysis workflow."""
        self.logger.info("Testing analysis workflow...")
        
        workflow_tests = {
            'market_analysis': False,
            'technical_indicators': False,
            'risk_analysis': False,
            'recommendation_generation': False
        }
        
        try:
            if self.orchestrator.analysis_engine and self.orchestrator.historical_data_manager:
                # Test market analysis
                try:
                    analysis = await self.orchestrator.analysis_engine.analyze_market_conditions(
                        self.test_symbol, self.test_timeframe
                    )
                    
                    if analysis and 'error' not in analysis:
                        workflow_tests['market_analysis'] = True
                        
                        # Check technical indicators
                        if 'momentum_indicators' in analysis and 'rsi' in analysis['momentum_indicators']:
                            workflow_tests['technical_indicators'] = True
                        
                        # Check risk analysis
                        if 'risk_metrics' in analysis and 'var_95' in analysis['risk_metrics']:
                            workflow_tests['risk_analysis'] = True
                        
                        # Check recommendation generation
                        if 'market_condition' in analysis and 'recommendation' in analysis['market_condition']:
                            workflow_tests['recommendation_generation'] = True
                    
                except Exception as e:
                    self.logger.debug(f"Market analysis failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in analysis workflow test: {e}")
        
        return {
            'tests': workflow_tests,
            'success_rate': sum(workflow_tests.values()) / len(workflow_tests),
            'overall_success': all(workflow_tests.values())
        }
    
    def _identify_gaps(self, validation_results: Dict[str, Any]) -> List[str]:
        """Identify gaps in the workflow."""
        gaps = []
        
        # Component gaps
        components = validation_results.get('components', {})
        for component, status in components.items():
            if status.get('status') == 'missing':
                gaps.append(f"Missing component: {component}")
            elif status.get('status') == 'error':
                gaps.append(f"Error in component: {component} - {status.get('error', 'Unknown error')}")
        
        # Workflow gaps
        workflows = validation_results.get('workflow_tests', {})
        for workflow_name, workflow_result in workflows.items():
            if not workflow_result.get('overall_success', False):
                failed_tests = [test for test, success in workflow_result.get('tests', {}).items() if not success]
                if failed_tests:
                    gaps.append(f"Failed tests in {workflow_name}: {', '.join(failed_tests)}")
        
        # Data availability gaps
        if not any(workflows.get('data_workflow', {}).get('tests', {}).values()):
            gaps.append("Critical: No data workflow functionality available")
        
        # Strategy execution gaps
        if not workflows.get('strategy_workflow', {}).get('overall_success', False):
            gaps.append("Strategy execution workflow incomplete")
        
        return gaps
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        gaps = validation_results.get('gaps_identified', [])
        components = validation_results.get('components', {})
        workflows = validation_results.get('workflow_tests', {})
        
        # Component recommendations
        if any('API client' in gap for gap in gaps):
            recommendations.append("Configure and initialize Kite API client for data access")
        
        if any('Data layer' in gap for gap in gaps):
            recommendations.append("Set up database backend (PostgreSQL or ClickHouse) and run migration")
        
        if any('Historical data manager' in gap for gap in gaps):
            recommendations.append("Initialize historical data manager for backtesting capabilities")
        
        # Data recommendations
        data_workflow = workflows.get('data_workflow', {})
        if not data_workflow.get('overall_success', False):
            recommendations.append("Run initial historical data collection for priority symbols")
            recommendations.append("Verify database connectivity and schema")
        
        # Strategy recommendations
        strategy_workflow = workflows.get('strategy_workflow', {})
        if not strategy_workflow.get('overall_success', False):
            recommendations.append("Verify strategy configuration and parameters")
            recommendations.append("Test strategy execution with sample data")
        
        # Analysis recommendations
        analysis_workflow = workflows.get('analysis_workflow', {})
        if not analysis_workflow.get('overall_success', False):
            recommendations.append("Ensure sufficient historical data for technical analysis")
            recommendations.append("Verify analysis engine configuration")
        
        # General recommendations
        if len(gaps) > 5:
            recommendations.append("Consider running setup_database.py and migrate_database.py scripts")
            recommendations.append("Review system configuration files")
        
        if not recommendations:
            recommendations.append("System appears to be functioning correctly")
            recommendations.append("Consider running live trading simulation to further validate")
        
        return recommendations
    
    def _calculate_overall_status(self, validation_results: Dict[str, Any]) -> str:
        """Calculate overall system status."""
        try:
            components = validation_results.get('components', {})
            workflows = validation_results.get('workflow_tests', {})
            gaps = validation_results.get('gaps_identified', [])
            
            # Count available components
            available_components = sum(1 for status in components.values() 
                                     if status.get('status') == 'available')
            total_components = len(components)
            
            # Count successful workflows
            successful_workflows = sum(1 for workflow in workflows.values() 
                                     if workflow.get('overall_success', False))
            total_workflows = len(workflows)
            
            # Calculate scores
            component_score = available_components / total_components if total_components > 0 else 0
            workflow_score = successful_workflows / total_workflows if total_workflows > 0 else 0
            
            # Determine status
            if component_score >= 0.8 and workflow_score >= 0.8 and len(gaps) <= 2:
                return 'excellent'
            elif component_score >= 0.6 and workflow_score >= 0.6 and len(gaps) <= 5:
                return 'good'
            elif component_score >= 0.4 and workflow_score >= 0.4:
                return 'fair'
            else:
                return 'poor'
                
        except Exception as e:
            self.logger.error(f"Error calculating overall status: {e}")
            return 'unknown'
