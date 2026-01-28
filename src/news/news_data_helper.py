"""
News Data Layer Helper

Provides news-specific data operations that work with the existing data layer
or fall back to in-memory storage when database support is not available.
"""

import hashlib
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from src.utils.logger_setup import setup_logger
from src.utils.timezone_utils import get_current_time


class NewsDataHelper:
    """
    Helper class for news-related data operations.
    
    Works with the existing data layer when available, falls back to
    in-memory storage for deduplication when database doesn't have
    news-specific tables.
    """
    
    def __init__(self, data_layer: Optional[Any] = None, max_memory_items: int = 10000):
        """
        Initialize the news data helper.
        
        Args:
            data_layer: Optional data layer instance
            max_memory_items: Maximum items to keep in memory cache
        """
        self.data_layer = data_layer
        self.max_memory_items = max_memory_items
        self.logger = setup_logger("NewsDataHelper", level="INFO")
        
        # In-memory fallback storage
        self._processed_news_ids: Set[str] = set()
        self._news_cache: Dict[str, Dict[str, Any]] = {}
        self._analysis_cache: Dict[str, Dict[str, Any]] = {}
        self._alert_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.stats = Counter({
            "news_stored": 0,
            "news_retrieved": 0,
            "duplicates_prevented": 0,
            "database_operations": 0,
            "memory_operations": 0
        })
        
        self.logger.info("NewsDataHelper initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize the helper and check database capabilities.
        
        Returns:
            bool: True if ready to use
        """
        try:
            if self.data_layer:
                # Try to check if news tables exist
                has_news_tables = await self._check_news_tables()
                if has_news_tables:
                    self.logger.info("Database news tables available")
                else:
                    self.logger.info("Using in-memory storage for news deduplication")
            else:
                self.logger.info("No data layer - using in-memory storage")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing NewsDataHelper: {e}")
            return True  # Still operational with in-memory fallback
    
    async def _check_news_tables(self) -> bool:
        """Check if the database has news-specific tables."""
        try:
            if not self.data_layer:
                return False
            
            # Try to execute a simple query to check for news table
            if hasattr(self.data_layer, 'execute_query'):
                try:
                    result = await self.data_layer.execute_query(
                        "SELECT 1 FROM news_items LIMIT 1"
                    )
                    return True
                except:
                    pass
            
            return False
            
        except Exception:
            return False
    
    async def is_news_processed(self, news_id: str) -> bool:
        """
        Check if a news item has already been processed.
        
        Args:
            news_id: Unique news identifier
            
        Returns:
            bool: True if already processed
        """
        try:
            # Try database first
            if self.data_layer and hasattr(self.data_layer, 'execute_query'):
                try:
                    result = await self.data_layer.execute_query(
                        "SELECT 1 FROM news_items WHERE news_id = :news_id LIMIT 1",
                        {"news_id": news_id}
                    )
                    if result:
                        self.stats["database_operations"] += 1
                        if result:
                            self.stats["duplicates_prevented"] += 1
                        return bool(result)
                except:
                    pass
            
            # Fall back to in-memory
            self.stats["memory_operations"] += 1
            is_processed = news_id in self._processed_news_ids
            if is_processed:
                self.stats["duplicates_prevented"] += 1
            return is_processed
            
        except Exception as e:
            self.logger.error(f"Error checking if news processed: {e}")
            return False
    
    async def mark_news_processed(self, news_id: str, news_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a news item as processed.
        
        Args:
            news_id: Unique news identifier
            news_data: Optional news item data to store
            
        Returns:
            bool: True if successful
        """
        try:
            # Try database first
            if self.data_layer and news_data and hasattr(self.data_layer, 'execute_query'):
                try:
                    await self.data_layer.execute_query(
                        """
                        INSERT INTO news_items (news_id, title, source_feed, published_date, created_at)
                        VALUES (:news_id, :title, :source_feed, :published_date, :created_at)
                        """,
                        {
                            "news_id": news_id,
                            "title": news_data.get("title", "")[:500],
                            "source_feed": news_data.get("source_feed", ""),
                            "published_date": news_data.get("published_date"),
                            "created_at": get_current_time()
                        }
                    )
                    self.stats["database_operations"] += 1
                    self.stats["news_stored"] += 1
                except:
                    pass
            
            # Also add to in-memory cache
            self._processed_news_ids.add(news_id)
            if news_data:
                self._news_cache[news_id] = news_data
            
            # Cleanup if cache is too large
            await self._cleanup_memory_cache()
            
            self.stats["memory_operations"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking news as processed: {e}")
            return False
    
    async def get_processed_news_ids(self, since: Optional[datetime] = None) -> Set[str]:
        """
        Get set of processed news IDs.
        
        Args:
            since: Optional datetime to filter from
            
        Returns:
            Set of processed news IDs
        """
        try:
            result = set()
            
            # Try database first
            if self.data_layer and hasattr(self.data_layer, 'execute_query'):
                try:
                    query = "SELECT news_id FROM news_items"
                    params = {}
                    
                    if since:
                        query += " WHERE created_at >= :since"
                        params["since"] = since
                    
                    rows = await self.data_layer.execute_query(query, params)
                    if rows:
                        result = {row[0] for row in rows if row}
                        self.stats["database_operations"] += 1
                        self.stats["news_retrieved"] += len(result)
                        return result
                except:
                    pass
            
            # Fall back to in-memory
            self.stats["memory_operations"] += 1
            return self._processed_news_ids.copy()
            
        except Exception as e:
            self.logger.error(f"Error getting processed news IDs: {e}")
            return self._processed_news_ids.copy()
    
    async def store_news_analysis(self, analysis_data: Dict[str, Any]) -> bool:
        """
        Store a news analysis result.
        
        Args:
            analysis_data: Analysis data dictionary
            
        Returns:
            bool: True if successful
        """
        try:
            news_id = analysis_data.get("news_id", "")
            
            # Try database first
            if self.data_layer and hasattr(self.data_layer, 'execute_query'):
                try:
                    await self.data_layer.execute_query(
                        """
                        INSERT INTO news_analysis 
                        (news_id, impact_level, sentiment, confidence_score, affected_stocks, 
                         expected_direction, expected_move_pct, analysis_timestamp)
                        VALUES (:news_id, :impact_level, :sentiment, :confidence_score, :affected_stocks,
                                :expected_direction, :expected_move_pct, :analysis_timestamp)
                        """,
                        {
                            "news_id": news_id,
                            "impact_level": analysis_data.get("impact_level", ""),
                            "sentiment": analysis_data.get("sentiment", ""),
                            "confidence_score": analysis_data.get("confidence_score", 0.0),
                            "affected_stocks": ",".join(analysis_data.get("affected_stocks", [])),
                            "expected_direction": analysis_data.get("expected_direction", ""),
                            "expected_move_pct": analysis_data.get("expected_move_pct", 0.0),
                            "analysis_timestamp": analysis_data.get("analysis_timestamp", get_current_time())
                        }
                    )
                    self.stats["database_operations"] += 1
                except:
                    pass
            
            # Also store in memory
            self._analysis_cache[news_id] = analysis_data
            self.stats["memory_operations"] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing news analysis: {e}")
            return False
    
    async def store_news_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Store a news alert.
        
        Args:
            alert_data: Alert data dictionary
            
        Returns:
            bool: True if successful
        """
        try:
            alert_id = alert_data.get("alert_id", "")
            
            # Try database first
            if self.data_layer and hasattr(self.data_layer, 'execute_query'):
                try:
                    await self.data_layer.execute_query(
                        """
                        INSERT INTO news_alerts 
                        (alert_id, news_id, symbol, alert_type, priority, recommended_action,
                         entry_price, stop_loss, target, created_at, valid_until)
                        VALUES (:alert_id, :news_id, :symbol, :alert_type, :priority, :recommended_action,
                                :entry_price, :stop_loss, :target, :created_at, :valid_until)
                        """,
                        {
                            "alert_id": alert_id,
                            "news_id": alert_data.get("news_id", ""),
                            "symbol": alert_data.get("symbol", ""),
                            "alert_type": alert_data.get("alert_type", ""),
                            "priority": alert_data.get("priority", ""),
                            "recommended_action": alert_data.get("recommended_action", ""),
                            "entry_price": alert_data.get("entry_price"),
                            "stop_loss": alert_data.get("stop_loss"),
                            "target": alert_data.get("target"),
                            "created_at": alert_data.get("created_at", get_current_time()),
                            "valid_until": alert_data.get("valid_until")
                        }
                    )
                    self.stats["database_operations"] += 1
                except:
                    pass
            
            # Also store in memory
            self._alert_cache[alert_id] = alert_data
            self.stats["memory_operations"] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing news alert: {e}")
            return False
    
    async def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent news alerts.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
        """
        try:
            # Try database first
            if self.data_layer and hasattr(self.data_layer, 'execute_query'):
                try:
                    rows = await self.data_layer.execute_query(
                        """
                        SELECT alert_id, news_id, symbol, alert_type, priority, 
                               recommended_action, entry_price, stop_loss, target, 
                               created_at, valid_until
                        FROM news_alerts
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """,
                        {"limit": limit}
                    )
                    if rows:
                        self.stats["database_operations"] += 1
                        return [dict(row) for row in rows]
                except:
                    pass
            
            # Fall back to in-memory
            self.stats["memory_operations"] += 1
            alerts = list(self._alert_cache.values())
            alerts.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
            return alerts[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting recent alerts: {e}")
            return []
    
    async def _cleanup_memory_cache(self):
        """Clean up memory cache if it's too large."""
        try:
            # Cleanup processed news IDs
            if len(self._processed_news_ids) > self.max_memory_items:
                # Keep only the most recent half
                to_remove = len(self._processed_news_ids) - (self.max_memory_items // 2)
                self._processed_news_ids = set(list(self._processed_news_ids)[to_remove:])
                self.logger.info(f"Cleaned up {to_remove} old news IDs from memory")
            
            # Cleanup news cache
            if len(self._news_cache) > self.max_memory_items // 2:
                oldest_keys = list(self._news_cache.keys())[:len(self._news_cache) // 2]
                for key in oldest_keys:
                    del self._news_cache[key]
            
            # Cleanup analysis cache
            if len(self._analysis_cache) > self.max_memory_items // 4:
                oldest_keys = list(self._analysis_cache.keys())[:len(self._analysis_cache) // 2]
                for key in oldest_keys:
                    del self._analysis_cache[key]
            
            # Cleanup alert cache
            if len(self._alert_cache) > 1000:
                oldest_keys = list(self._alert_cache.keys())[:len(self._alert_cache) // 2]
                for key in oldest_keys:
                    del self._alert_cache[key]
                    
        except Exception as e:
            self.logger.error(f"Error during memory cleanup: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get helper statistics."""
        stats = dict(self.stats)
        stats["memory_news_ids"] = len(self._processed_news_ids)
        stats["memory_news_items"] = len(self._news_cache)
        stats["memory_analyses"] = len(self._analysis_cache)
        stats["memory_alerts"] = len(self._alert_cache)
        return stats
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = Counter({
            "news_stored": 0,
            "news_retrieved": 0,
            "duplicates_prevented": 0,
            "database_operations": 0,
            "memory_operations": 0
        })
