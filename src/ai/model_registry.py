"""
AI Model Registry
Centralized model management with versioning, metrics tracking, and model lifecycle
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import sqlite3

from ..utils.logger_setup import setup_logger
import hashlib
import shutil

from .ai_engine import BaseAIModel, ModelMetrics
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


@dataclass
class ModelVersion:
    """Model version metadata."""
    model_name: str
    version: str
    path: Path
    metrics: ModelMetrics
    created_at: datetime
    is_active: bool = False
    description: str = ""
    feature_names: List[str] = None
    hyperparameters: Dict[str, Any] = None
    training_data_hash: str = ""
    
    def __post_init__(self):
        if self.feature_names is None:
            self.feature_names = []
        if self.hyperparameters is None:
            self.hyperparameters = {}


@dataclass
class ModelExperiment:
    """Model training experiment record."""
    experiment_id: str
    model_name: str
    hyperparameters: Dict[str, Any]
    training_data_hash: str
    metrics: Dict[str, float]
    feature_importance: Dict[str, float]
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    notes: str = ""


class ModelRegistry:
    """Centralized model registry for AI models."""
    
    def __init__(self, registry_path: str = "data/ai_models"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.registry_path / "model_registry.db"
        self.models_path = self.registry_path / "models"
        self.models_path.mkdir(exist_ok=True)
        
        self.logger = setup_logger("ai.model_registry")
        
        # Initialize database
        self._init_registry_db()
        
        # In-memory model cache
        self.model_cache = {}
    
    def _init_registry_db(self):
        """Initialize SQLite database for model registry."""
        
        with sqlite3.connect(self.db_path) as conn:
            # Model versions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    description TEXT,
                    feature_names TEXT,  -- JSON array
                    hyperparameters TEXT,  -- JSON object
                    training_data_hash TEXT,
                    
                    -- Metrics
                    accuracy REAL,
                    precision_score REAL,
                    recall REAL,
                    f1_score REAL,
                    confidence_calibration REAL,
                    samples_trained INTEGER,
                    
                    UNIQUE(model_name, version)
                )
            """)
            
            # Experiments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT UNIQUE NOT NULL,
                    model_name TEXT NOT NULL,
                    hyperparameters TEXT,  -- JSON object
                    training_data_hash TEXT,
                    metrics TEXT,  -- JSON object
                    feature_importance TEXT,  -- JSON object
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'running',
                    notes TEXT
                )
            """)
            
            # Model performance tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    prediction_accuracy REAL,
                    confidence_score REAL,
                    prediction_count INTEGER DEFAULT 1,
                    correct_predictions INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_model_active ON model_versions(model_name, is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_experiment_status ON model_experiments(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_model ON model_performance(model_name, version)")
    
    async def register_model(self, model: BaseAIModel, version: str = None, 
                           description: str = "", training_data_hash: str = "") -> str:
        """Register a trained model in the registry."""
        
        if not model.is_trained:
            raise ValueError("Model must be trained before registration")
        
        if version is None:
            version = get_current_time().strftime("%Y%m%d_%H%M%S")
        
        # Create model directory
        model_dir = self.models_path / model.model_name / version
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = model_dir / "model.pkl"
        model.save_model(model_path)
        
        # Save metadata
        metadata = {
            'model_name': model.model_name,
            'version': version,
            'feature_names': model.feature_names,
            'confidence_threshold': model.confidence_threshold,
            'created_at': get_current_time().isoformat(),
            'description': description
        }
        
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Register in database
        with sqlite3.connect(self.db_path) as conn:
            # Deactivate previous versions
            conn.execute("""
                UPDATE model_versions 
                SET is_active = FALSE 
                WHERE model_name = ?
            """, (model.model_name,))
            
            # Insert new version
            conn.execute("""
                INSERT INTO model_versions (
                    model_name, version, path, created_at, is_active, description,
                    feature_names, hyperparameters, training_data_hash,
                    accuracy, precision_score, recall, f1_score, 
                    confidence_calibration, samples_trained
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model.model_name, version, str(model_path), 
                get_current_time().isoformat(), True, description,
                json.dumps(model.feature_names), json.dumps({}), training_data_hash,
                model.metrics.accuracy if model.metrics else 0.0,
                model.metrics.precision if model.metrics else 0.0,
                model.metrics.recall if model.metrics else 0.0,
                model.metrics.f1_score if model.metrics else 0.0,
                model.metrics.confidence_calibration if model.metrics else 0.0,
                model.metrics.samples_trained if model.metrics else 0
            ))
        
        # Update cache
        cache_key = f"{model.model_name}:{version}"
        self.model_cache[cache_key] = model
        
        self.logger.info(f"Registered model {model.model_name} version {version}")
        return version
    
    async def load_model(self, model_name: str, version: str = None) -> Optional[BaseAIModel]:
        """Load a model from the registry."""
        
        # Use active version if none specified
        if version is None:
            version = self.get_active_version(model_name)
            if not version:
                self.logger.warning(f"No active version found for {model_name}")
                return None
        
        # Check cache first
        cache_key = f"{model_name}:{version}"
        if cache_key in self.model_cache:
            return self.model_cache[cache_key]
        
        # Load from disk
        try:
            model_path = self.models_path / model_name / version / "model.pkl"
            
            if not model_path.exists():
                self.logger.error(f"Model file not found: {model_path}")
                return None
            
            # Load metadata to determine model type
            metadata_path = self.models_path / model_name / version / "metadata.json"
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Create model instance (this needs to match the original model type)
            # For now, we'll use a generic approach
            from .ai_engine import SignalValidationModel
            
            if model_name == "signal_validation":
                model = SignalValidationModel(
                    confidence_threshold=metadata.get('confidence_threshold', 0.85)
                )
            else:
                self.logger.error(f"Unknown model type: {model_name}")
                return None
            
            # Load the trained model
            model.load_model(model_path)
            
            # Cache the model
            self.model_cache[cache_key] = model
            
            self.logger.info(f"Loaded model {model_name} version {version}")
            return model
            
        except Exception as e:
            self.logger.error(f"Error loading model {model_name}:{version}: {e}")
            return None
    
    def get_active_version(self, model_name: str) -> Optional[str]:
        """Get the active version for a model."""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT version FROM model_versions 
                WHERE model_name = ? AND is_active = TRUE
                LIMIT 1
            """, (model_name,))
            
            result = cursor.fetchone()
            return result[0] if result else None
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models."""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT model_name, version, created_at, is_active, description,
                       accuracy, precision_score, recall, f1_score, samples_trained
                FROM model_versions
                ORDER BY model_name, created_at DESC
            """)
            
            models = []
            for row in cursor.fetchall():
                models.append({
                    'model_name': row[0],
                    'version': row[1],
                    'created_at': row[2],
                    'is_active': bool(row[3]),
                    'description': row[4],
                    'accuracy': row[5],
                    'precision': row[6],
                    'recall': row[7],
                    'f1_score': row[8],
                    'samples_trained': row[9]
                })
            
            return models
    
    def get_model_metrics(self, model_name: str, version: str = None) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific model version."""
        
        if version is None:
            version = self.get_active_version(model_name)
            if not version:
                return None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT accuracy, precision_score, recall, f1_score, 
                       confidence_calibration, samples_trained, created_at
                FROM model_versions
                WHERE model_name = ? AND version = ?
            """, (model_name, version))
            
            result = cursor.fetchone()
            if result:
                return {
                    'accuracy': result[0],
                    'precision': result[1],
                    'recall': result[2],
                    'f1_score': result[3],
                    'confidence_calibration': result[4],
                    'samples_trained': result[5],
                    'created_at': result[6]
                }
            
            return None
    
    async def start_experiment(self, model_name: str, hyperparameters: Dict[str, Any],
                             training_data_hash: str, description: str = "") -> str:
        """Start a new model training experiment."""
        
        experiment_id = f"{model_name}_{get_current_time().strftime('%Y%m%d_%H%M%S')}"
        
        experiment = ModelExperiment(
            experiment_id=experiment_id,
            model_name=model_name,
            hyperparameters=hyperparameters,
            training_data_hash=training_data_hash,
            metrics={},
            feature_importance={},
            started_at=get_current_time(),
            status="running",
            notes=description
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO model_experiments (
                    experiment_id, model_name, hyperparameters, training_data_hash,
                    metrics, feature_importance, started_at, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment.experiment_id, experiment.model_name,
                json.dumps(experiment.hyperparameters), experiment.training_data_hash,
                json.dumps(experiment.metrics), json.dumps(experiment.feature_importance),
                experiment.started_at.isoformat(), experiment.status, experiment.notes
            ))
        
        self.logger.info(f"Started experiment {experiment_id}")
        return experiment_id
    
    async def complete_experiment(self, experiment_id: str, metrics: Dict[str, float],
                                feature_importance: Dict[str, float] = None):
        """Mark an experiment as completed with final metrics."""
        
        if feature_importance is None:
            feature_importance = {}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE model_experiments 
                SET metrics = ?, feature_importance = ?, completed_at = ?, status = 'completed'
                WHERE experiment_id = ?
            """, (
                json.dumps(metrics), json.dumps(feature_importance),
                get_current_time().isoformat(), experiment_id
            ))
        
        self.logger.info(f"Completed experiment {experiment_id}")
    
    def get_experiment_history(self, model_name: str = None) -> List[Dict[str, Any]]:
        """Get experiment history, optionally filtered by model name."""
        
        query = """
            SELECT experiment_id, model_name, hyperparameters, metrics, 
                   started_at, completed_at, status, notes
            FROM model_experiments
        """
        params = []
        
        if model_name:
            query += " WHERE model_name = ?"
            params.append(model_name)
        
        query += " ORDER BY started_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            
            experiments = []
            for row in cursor.fetchall():
                experiments.append({
                    'experiment_id': row[0],
                    'model_name': row[1],
                    'hyperparameters': json.loads(row[2]) if row[2] else {},
                    'metrics': json.loads(row[3]) if row[3] else {},
                    'started_at': row[4],
                    'completed_at': row[5],
                    'status': row[6],
                    'notes': row[7]
                })
            
            return experiments
    
    async def track_model_performance(self, model_name: str, version: str,
                                    prediction_accuracy: float, confidence_score: float):
        """Track real-time model performance."""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO model_performance (
                    model_name, version, timestamp, prediction_accuracy, 
                    confidence_score, prediction_count, correct_predictions
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (
                model_name, version, get_current_time().isoformat(),
                prediction_accuracy, confidence_score,
                1 if prediction_accuracy > 0.5 else 0
            ))
        
        self.logger.debug(f"Tracked performance for {model_name}:{version}")
    
    def get_performance_metrics(self, model_name: str, version: str = None,
                              days: int = 30) -> Dict[str, Any]:
        """Get aggregated performance metrics for a model."""
        
        if version is None:
            version = self.get_active_version(model_name)
            if not version:
                return {}
        
        cutoff_date = (get_current_time() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_predictions,
                    SUM(correct_predictions) as correct_predictions,
                    AVG(prediction_accuracy) as avg_accuracy,
                    AVG(confidence_score) as avg_confidence,
                    MIN(timestamp) as first_prediction,
                    MAX(timestamp) as last_prediction
                FROM model_performance
                WHERE model_name = ? AND version = ? AND timestamp >= ?
            """, (model_name, version, cutoff_date))
            
            result = cursor.fetchone()
            if result and result[0] > 0:
                return {
                    'total_predictions': result[0],
                    'correct_predictions': result[1],
                    'accuracy_rate': result[1] / result[0] if result[0] > 0 else 0,
                    'avg_accuracy': result[2],
                    'avg_confidence': result[3],
                    'first_prediction': result[4],
                    'last_prediction': result[5],
                    'days_tracked': days
                }
            
            return {}
    
    def set_active_version(self, model_name: str, version: str):
        """Set the active version for a model."""
        
        with sqlite3.connect(self.db_path) as conn:
            # Deactivate all versions
            conn.execute("""
                UPDATE model_versions 
                SET is_active = FALSE 
                WHERE model_name = ?
            """, (model_name,))
            
            # Activate specified version
            conn.execute("""
                UPDATE model_versions 
                SET is_active = TRUE 
                WHERE model_name = ? AND version = ?
            """, (model_name, version))
        
        # Clear cache for this model
        cache_keys_to_remove = [k for k in self.model_cache.keys() if k.startswith(f"{model_name}:")]
        for key in cache_keys_to_remove:
            del self.model_cache[key]
        
        self.logger.info(f"Set active version for {model_name}: {version}")
    
    def delete_model_version(self, model_name: str, version: str):
        """Delete a specific model version."""
        
        # Check if it's the active version
        active_version = self.get_active_version(model_name)
        if active_version == version:
            raise ValueError(f"Cannot delete active version {version}. Set a different active version first.")
        
        # Remove from filesystem
        model_dir = self.models_path / model_name / version
        if model_dir.exists():
            shutil.rmtree(model_dir)
        
        # Remove from database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM model_versions 
                WHERE model_name = ? AND version = ?
            """, (model_name, version))
            
            conn.execute("""
                DELETE FROM model_performance 
                WHERE model_name = ? AND version = ?
            """, (model_name, version))
        
        # Remove from cache
        cache_key = f"{model_name}:{version}"
        if cache_key in self.model_cache:
            del self.model_cache[cache_key]
        
        self.logger.info(f"Deleted model {model_name} version {version}")
    
    def cleanup_old_versions(self, model_name: str, keep_versions: int = 5):
        """Clean up old model versions, keeping only the specified number."""
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all versions ordered by creation date
            cursor = conn.execute("""
                SELECT version, is_active FROM model_versions 
                WHERE model_name = ?
                ORDER BY created_at DESC
            """, (model_name,))
            
            versions = cursor.fetchall()
            
            # Keep active version plus specified number of recent versions
            versions_to_keep = set()
            kept_count = 0
            
            for version, is_active in versions:
                if is_active or kept_count < keep_versions:
                    versions_to_keep.add(version)
                    if not is_active:
                        kept_count += 1
            
            # Delete older versions
            for version, _ in versions:
                if version not in versions_to_keep:
                    try:
                        self.delete_model_version(model_name, version)
                    except Exception as e:
                        self.logger.error(f"Error deleting version {version}: {e}")
        
        self.logger.info(f"Cleaned up old versions for {model_name}, kept {len(versions_to_keep)} versions")


# Export main classes
__all__ = [
    'ModelVersion',
    'ModelExperiment', 
    'ModelRegistry'
]
