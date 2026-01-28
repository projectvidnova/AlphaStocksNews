"""
AlphaStock AI Framework
Generic, extensible AI system for trading decisions with high confidence thresholds
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging

# Import AI engine components
from .ai_engine import AISignal, BaseAIModel, SignalValidationModel, ModelMetrics, RiskAssessmentModel, AnomalyDetectionModel
from .feature_store import FeatureStore, FeatureDefinition, FeatureValue, FeatureCalculator
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class FeatureEngineer:
    """Feature engineering pipeline for AI models."""
    
    def __init__(self):
        self.feature_configs = {}
        self.logger = setup_logger("ai.feature_engineer")
    
    def extract_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract technical analysis features."""
        
        features = df.copy()
        
        # Price features
        features['returns'] = df['close'].pct_change()
        features['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        features['price_volatility'] = features['returns'].rolling(20).std()
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            features[f'ma_{period}'] = df['close'].rolling(period).mean()
            features[f'ma_ratio_{period}'] = df['close'] / features[f'ma_{period}']
        
        # Technical indicators
        features['rsi'] = self._calculate_rsi(df['close'])
        features['bb_upper'], features['bb_lower'] = self._calculate_bollinger_bands(df['close'])
        features['macd'], features['macd_signal'] = self._calculate_macd(df['close'])
        
        # Volume features
        if 'volume' in df.columns:
            features['volume_ma'] = df['volume'].rolling(20).mean()
            features['volume_ratio'] = df['volume'] / features['volume_ma']
        
        # Volatility features
        features['high_low_ratio'] = df['high'] / df['low']
        features['close_open_ratio'] = df['close'] / df['open']
        
        # Remove rows with NaN values
        features = features.dropna()
        
        self.logger.info(f"Generated {len(features.columns)} technical features")
        
        return features
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        ma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper_band = ma + (std * std_dev)
        lower_band = ma - (std * std_dev)
        return upper_band, lower_band
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator."""
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=signal).mean()
        return macd, macd_signal


class AIDecisionEngine:
    """High-level AI decision engine that coordinates all AI models."""
    
    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self.models = {}
        self.feature_engineer = FeatureEngineer()
        self.logger = setup_logger("ai.decision_engine")
        
        # Model registry
        self.model_registry = {
            'signal_validation': SignalValidationModel(confidence_threshold),
            'risk_assessment': RiskAssessmentModel(0.80),
            'anomaly_detection': AnomalyDetectionModel(0.90)
        }
    
    async def validate_signal(self, signal_data: Dict[str, Any], market_data: pd.DataFrame) -> AISignal:
        """Validate a trading signal using AI models."""
        
        self.logger.info(f"Validating signal for {signal_data['symbol']}")
        
        # Extract features
        features = self.feature_engineer.extract_technical_features(market_data)
        
        if len(features) == 0:
            return AISignal(
                symbol=signal_data['symbol'],
                strategy=signal_data['strategy'],
                signal_type=signal_data['signal_type'],
                confidence=0.0,
                probability={},
                features_used=[],
                model_votes={},
                risk_score=1.0,
                timestamp=get_current_time(),
                execution_recommendation=False,
                reasoning=["Insufficient data for AI validation"]
            )
        
        # Get latest features for prediction
        latest_features = features.iloc[-1:].select_dtypes(include=[np.number])
        
        try:
            # Get AI validation
            signal_validator = self.model_registry['signal_validation']
            
            if signal_validator.is_trained:
                predictions, confidences = await signal_validator.predict(latest_features)
                
                confidence_score = float(confidences[0]) if len(confidences) > 0 else 0.0
                prediction = predictions[0] if len(predictions) > 0 else 'HOLD'
                
                # Determine execution recommendation
                execute = confidence_score >= self.confidence_threshold and prediction == signal_data['signal_type']
                
                # Generate reasoning
                reasoning = []
                if confidence_score >= self.confidence_threshold:
                    reasoning.append(f"High AI confidence: {confidence_score:.2%}")
                else:
                    reasoning.append(f"Low AI confidence: {confidence_score:.2%} < {self.confidence_threshold:.2%}")
                
                if prediction == signal_data['signal_type']:
                    reasoning.append("AI prediction aligns with strategy signal")
                else:
                    reasoning.append(f"AI suggests {prediction} vs strategy {signal_data['signal_type']}")
                
                return AISignal(
                    symbol=signal_data['symbol'],
                    strategy=signal_data['strategy'],
                    signal_type=signal_data['signal_type'],
                    confidence=confidence_score,
                    probability={prediction: confidence_score},
                    features_used=list(latest_features.columns),
                    model_votes={'signal_validation': prediction},
                    risk_score=1.0 - confidence_score,  # Simple risk scoring
                    timestamp=get_current_time(),
                    execution_recommendation=execute,
                    reasoning=reasoning
                )
            
            else:
                return AISignal(
                    symbol=signal_data['symbol'],
                    strategy=signal_data['strategy'],
                    signal_type=signal_data['signal_type'],
                    confidence=0.5,  # Default confidence when no AI available
                    probability={},
                    features_used=[],
                    model_votes={},
                    risk_score=0.5,
                    timestamp=get_current_time(),
                    execution_recommendation=True,  # Allow execution without AI if not trained
                    reasoning=["AI model not trained, using default validation"]
                )
        
        except Exception as e:
            self.logger.error(f"AI validation failed: {e}")
            return AISignal(
                symbol=signal_data['symbol'],
                strategy=signal_data['strategy'],
                signal_type=signal_data['signal_type'],
                confidence=0.0,
                probability={},
                features_used=[],
                model_votes={},
                risk_score=1.0,
                timestamp=get_current_time(),
                execution_recommendation=False,
                reasoning=[f"AI validation error: {str(e)}"]
            )
    
    async def assess_risk(self, symbol: str, market_data: pd.DataFrame, position_size: float = 1.0) -> Dict[str, Any]:
        """Assess risk for a trading position using AI."""
        
        self.logger.info(f"Assessing risk for {symbol}")
        
        try:
            # Extract features
            features = self.feature_engineer.extract_technical_features(market_data)
            
            if len(features) == 0:
                return {
                    'risk_score': 0.5,
                    'confidence': 0.0,
                    'recommendation': 'CAUTION',
                    'reasoning': ['Insufficient data for risk assessment']
                }
            
            latest_features = features.iloc[-1:].select_dtypes(include=[np.number])
            
            # Get risk assessment
            risk_model = self.model_registry['risk_assessment']
            
            if risk_model.is_trained:
                risk_scores, confidences = await risk_model.predict(latest_features)
                
                risk_score = float(risk_scores[0]) if len(risk_scores) > 0 else 0.5
                confidence = float(confidences[0]) if len(confidences) > 0 else 0.0
                
                # Risk-based recommendations
                if risk_score < 0.3:
                    recommendation = 'LOW_RISK'
                elif risk_score < 0.7:
                    recommendation = 'MEDIUM_RISK'
                else:
                    recommendation = 'HIGH_RISK'
                
                reasoning = [
                    f"AI risk score: {risk_score:.3f}",
                    f"Risk assessment confidence: {confidence:.2%}",
                    f"Position size factor: {position_size}"
                ]
                
                return {
                    'risk_score': risk_score,
                    'confidence': confidence,
                    'recommendation': recommendation,
                    'reasoning': reasoning,
                    'adjusted_position_size': position_size * (1.0 - risk_score)
                }
            else:
                return {
                    'risk_score': 0.5,
                    'confidence': 0.5,
                    'recommendation': 'MEDIUM_RISK',
                    'reasoning': ['Risk model not trained, using default assessment'],
                    'adjusted_position_size': position_size * 0.5
                }
                
        except Exception as e:
            self.logger.error(f"Risk assessment failed: {e}")
            return {
                'risk_score': 0.8,
                'confidence': 0.0,
                'recommendation': 'HIGH_RISK',
                'reasoning': [f'Risk assessment error: {str(e)}'],
                'adjusted_position_size': position_size * 0.2
            }
    
    async def detect_anomalies(self, symbol: str, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Detect market anomalies using AI."""
        
        self.logger.info(f"Detecting anomalies for {symbol}")
        
        try:
            # Extract features
            features = self.feature_engineer.extract_technical_features(market_data)
            
            if len(features) == 0:
                return {
                    'anomaly_score': 1.0,  # Normal by default
                    'confidence': 0.0,
                    'status': 'NORMAL',
                    'reasoning': ['Insufficient data for anomaly detection']
                }
            
            latest_features = features.iloc[-1:].select_dtypes(include=[np.number])
            
            # Get anomaly detection
            anomaly_model = self.model_registry['anomaly_detection']
            
            if anomaly_model.is_trained:
                anomaly_scores, confidences = await anomaly_model.predict(latest_features)
                
                anomaly_score = float(anomaly_scores[0]) if len(anomaly_scores) > 0 else 1.0
                confidence = float(confidences[0]) if len(confidences) > 0 else 0.0
                
                # Anomaly status
                if anomaly_score > 0.8:
                    status = 'NORMAL'
                elif anomaly_score > 0.5:
                    status = 'UNUSUAL'
                else:
                    status = 'ANOMALY'
                
                reasoning = [
                    f"Anomaly score: {anomaly_score:.3f} (higher = more normal)",
                    f"Detection confidence: {confidence:.2%}",
                    f"Market status: {status}"
                ]
                
                return {
                    'anomaly_score': anomaly_score,
                    'confidence': confidence,
                    'status': status,
                    'reasoning': reasoning
                }
            else:
                return {
                    'anomaly_score': 1.0,
                    'confidence': 0.5,
                    'status': 'NORMAL',
                    'reasoning': ['Anomaly detection model not trained, assuming normal']
                }
                
        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {e}")
            return {
                'anomaly_score': 0.0,  # Assume anomaly on error
                'confidence': 0.0,
                'status': 'UNKNOWN',
                'reasoning': [f'Anomaly detection error: {str(e)}']
            }
    
    async def train_models(self, historical_data: pd.DataFrame, signals_data: pd.DataFrame = None):
        """Train AI models on historical data."""
        
        self.logger.info("Training AI models...")
        
        # Prepare training data
        features = self.feature_engineer.extract_technical_features(historical_data)
        
        if len(features) == 0:
            self.logger.warning("No features available for training")
            return
        
        # Create labels from historical data (simplified example)
        labels = self._create_training_labels(features, signals_data)
        
        if len(labels) > 0:
            try:
                # Train signal validation model
                signal_validator = self.model_registry['signal_validation']
                signal_metrics = await signal_validator.train(features, labels)
                self.logger.info(f"Signal validation model trained. Accuracy: {signal_metrics.accuracy:.3f}")
                
                # Train risk assessment model (using volatility as target)
                risk_labels = features['price_volatility'].fillna(0.5) if 'price_volatility' in features.columns else pd.Series([0.5] * len(features))
                risk_model = self.model_registry['risk_assessment']
                risk_metrics = await risk_model.train(features, risk_labels)
                self.logger.info(f"Risk assessment model trained. R²: {risk_metrics.accuracy:.3f}")
                
                # Train anomaly detection model (unsupervised)
                anomaly_model = self.model_registry['anomaly_detection']
                anomaly_metrics = await anomaly_model.train(features)
                self.logger.info(f"Anomaly detection model trained. Normal ratio: {anomaly_metrics.accuracy:.3f}")
                
            except Exception as e:
                self.logger.error(f"Model training failed: {e}")
        else:
            self.logger.warning("No training labels available")
    
    def _create_training_labels(self, features: pd.DataFrame, signals: pd.DataFrame = None) -> pd.Series:
        """Create training labels from historical data."""
        
        labels = []
        for idx, row in features.iterrows():
            # Simple labeling based on future returns
            if 'returns' in features.columns:
                future_return = features['returns'].shift(-1).loc[idx] if idx < len(features) - 1 else 0
                if future_return > 0.01:  # Positive return threshold
                    labels.append('BUY')
                elif future_return < -0.01:  # Negative return threshold  
                    labels.append('SELL')
                else:
                    labels.append('HOLD')
            else:
                labels.append('HOLD')
        
        return pd.Series(labels[:len(features)], index=features.index)
    
    def get_model_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all AI models."""
        
        status = {}
        for name, model in self.model_registry.items():
            status[name] = {
                'is_trained': model.is_trained,
                'confidence_threshold': model.confidence_threshold,
                'metrics': model.metrics.__dict__ if model.metrics else None
            }
        
        return status


# Export main classes
__all__ = [
    'AISignal',
    'BaseAIModel', 
    'SignalValidationModel',
    'RiskAssessmentModel',
    'AnomalyDetectionModel',
    'FeatureEngineer',
    'FeatureStore',
    'AIDecisionEngine'
]
