"""
ClickHouse Data Layer Implementation for AlphaStock Trading System

ClickHouse is specifically designed for real-time analytics and time series data,
making it ideal for high-frequency trading data storage and retrieval.

Key advantages:
- Extremely fast INSERT and SELECT operations
- Columnar storage optimized for analytics
- Built-in data compression
- Excellent performance with time series data
"""

import asyncio
import threading
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import logging
from contextlib import asynccontextmanager

import clickhouse_connect
from clickhouse_connect.driver import Client

from . import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_utc, to_ist


class ClickHouseDataLayer(DataLayerInterface):
    """
    ClickHouse implementation of the data layer interface.
    
    Optimized for high-performance time series data operations.
    """
    
    def __init__(self, host: str = 'localhost', port: int = 8123,
                 database: str = 'alphastock', username: str = 'default',
                 password: str = '', pool_size: int = 10):
        """
        Initialize ClickHouse data layer.
        
        Args:
            host: ClickHouse server host
            port: ClickHouse server port
            database: Database name
            username: Username for authentication
            password: Password for authentication
            pool_size: Connection pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool_size = pool_size
        
        # Thread-local storage for ClickHouse clients
        # Each thread gets its own client to avoid concurrent query issues
        self._thread_local = threading.local()
        self.client: Optional[Client] = None  # Main client for initialization
        self.logger = setup_logger(name="ClickHouseDataLayer")
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize ClickHouse connection and create tables."""
        try:
            # Create ClickHouse client
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                send_receive_timeout=60
            )
            
            # Test connection
            result = self.client.query("SELECT 1").result_rows
            if not result or result[0][0] != 1:
                raise Exception("ClickHouse connection test failed")
            
            # Create database if it doesn't exist
            self.client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            
            # Create tables
            await self._create_tables()
            
            self._initialized = True
            self.logger.info("ClickHouse data layer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ClickHouse data layer: {e}")
            return False
    
    def _get_thread_client(self) -> Client:
        """
        Get or create a ClickHouse client for the current thread.
        
        This ensures each thread has its own client instance to avoid
        'concurrent queries within the same session' errors.
        
        Returns:
            Client: Thread-local ClickHouse client
        """
        if not hasattr(self._thread_local, 'client') or self._thread_local.client is None:
            # Create a new client for this thread
            self._thread_local.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
                send_receive_timeout=60
            )
            thread_name = threading.current_thread().name
            self.logger.debug(f"Created new ClickHouse client for thread: {thread_name}")
        
        return self._thread_local.client
    
    async def close(self):
        """Close ClickHouse connections."""
        try:
            # Close main client
            if self.client:
                self.client.close()
                self.client = None
            
            # Close thread-local client if exists
            if hasattr(self._thread_local, 'client') and self._thread_local.client:
                self._thread_local.client.close()
                self._thread_local.client = None
            
            self._initialized = False
            self.logger.info("ClickHouse data layer closed")
        except Exception as e:
            self.logger.error(f"Error closing ClickHouse data layer: {e}")
    
    async def _migrate_schemas(self):
        """
        Migrate existing table schemas to match current definitions.
        Handles schema changes like DateTime -> DateTime64(3).
        """
        try:
            # Check if historical_data table exists
            check_query = """
                SELECT name, engine 
                FROM system.tables 
                WHERE database = %(database)s 
                AND name = 'historical_data'
            """
            result = self.client.query(
                check_query, 
                parameters={'database': self.database}
            )
            
            if not result.result_rows:
                # Table doesn't exist, will be created by _create_tables
                self.logger.info("historical_data table does not exist, will be created")
                return
            
            # Check current schema for timestamp column
            schema_query = """
                SELECT name, type 
                FROM system.columns 
                WHERE database = %(database)s 
                AND table = 'historical_data'
                AND name = 'timestamp'
            """
            schema_result = self.client.query(
                schema_query,
                parameters={'database': self.database}
            )
            
            if schema_result.result_rows:
                column_type = schema_result.result_rows[0][1]
                self.logger.info(f"historical_data.timestamp current type: {column_type}")
                
                # Check if migration is needed (DateTime -> DateTime64(3))
                if column_type == 'DateTime' or column_type.startswith('DateTime)'):
                    self.logger.warning("⚠️  historical_data schema migration needed: DateTime -> DateTime64(3)")
                    await self._migrate_historical_data_table()
                elif column_type == 'DateTime64(3)':
                    self.logger.info("✅ historical_data schema is up to date")
                else:
                    self.logger.warning(f"Unexpected timestamp type: {column_type}")
            
        except Exception as e:
            self.logger.error(f"Error checking schema migration: {e}")
            # Don't fail initialization, just log the error
    
    async def _migrate_historical_data_table(self):
        """
        Migrate historical_data table from DateTime to DateTime64(3).
        Creates new table, copies data in batches by partition, and replaces old table.
        """
        try:
            self.logger.info("🔄 Starting historical_data schema migration...")
            
            # Step 1: Create new table with correct schema
            new_table_sql = """
            CREATE TABLE IF NOT EXISTS historical_data_new (
                timestamp DateTime64(3),
                date Date MATERIALIZED toDate(timestamp),
                symbol String,
                asset_type String,
                timeframe String,
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                volume UInt64,
                turnover Float64
            ) ENGINE = MergeTree()
            PARTITION BY (symbol, toYYYYMM(date))
            ORDER BY (symbol, timeframe, timestamp)
            SETTINGS index_granularity = 8192
            """
            self.client.command(new_table_sql)
            self.logger.info("✅ Created historical_data_new table")
            
            # Step 2: Get total row count
            old_count = self.client.query("SELECT COUNT(*) FROM historical_data").result_rows[0][0]
            self.logger.info(f"📊 Total rows to migrate: {old_count}")
            
            # Step 3: Get distinct partitions (symbol combinations)
            partitions_query = """
                SELECT DISTINCT symbol
                FROM historical_data
                ORDER BY symbol
            """
            partitions_result = self.client.query(partitions_query)
            symbols = [row[0] for row in partitions_result.result_rows]
            
            self.logger.info(f"📦 Found {len(symbols)} distinct symbols to migrate")
            
            # Step 4: Copy data symbol by symbol to avoid too many partitions error
            migrated_count = 0
            for i, symbol in enumerate(symbols, 1):
                try:
                    copy_query = f"""
                    INSERT INTO historical_data_new
                    SELECT 
                        timestamp,
                        symbol,
                        asset_type,
                        timeframe,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        turnover
                    FROM historical_data
                    WHERE symbol = '{symbol}'
                    """
                    self.client.command(copy_query)
                    
                    # Get count for this symbol
                    symbol_count = self.client.query(
                        f"SELECT COUNT(*) FROM historical_data_new WHERE symbol = '{symbol}'"
                    ).result_rows[0][0]
                    migrated_count += symbol_count
                    
                    if i % 10 == 0 or i == len(symbols):
                        self.logger.info(f"⏳ Progress: {i}/{len(symbols)} symbols, {migrated_count}/{old_count} rows")
                    
                except Exception as symbol_error:
                    self.logger.error(f"❌ Failed to migrate symbol {symbol}: {symbol_error}")
                    raise
            
            # Step 5: Verify row count
            new_count = self.client.query("SELECT COUNT(*) FROM historical_data_new").result_rows[0][0]
            
            if old_count != new_count:
                raise Exception(f"Row count mismatch: old={old_count}, new={new_count}")
            
            self.logger.info(f"✅ Copied {new_count} rows to new table")
            
            # Step 6: Rename tables atomically
            self.client.command("RENAME TABLE historical_data TO historical_data_old")
            self.logger.info("✅ Renamed historical_data to historical_data_old")
            
            self.client.command("RENAME TABLE historical_data_new TO historical_data")
            self.logger.info("✅ Renamed historical_data_new to historical_data")
            
            # Step 7: Drop old table
            self.client.command("DROP TABLE historical_data_old")
            self.logger.info("✅ Dropped historical_data_old table")
            
            self.logger.info("✅ Schema migration completed successfully!")
            
        except Exception as e:
            self.logger.error(f"❌ Schema migration failed: {e}")
            # Try to rollback if possible
            try:
                # Check if old table still exists
                check = self.client.query(
                    "SELECT name FROM system.tables WHERE database = %(db)s AND name = 'historical_data_old'",
                    parameters={'db': self.database}
                )
                if check.result_rows:
                    self.logger.warning("Attempting rollback...")
                    # If historical_data doesn't exist, rename old back
                    check_new = self.client.query(
                        "SELECT name FROM system.tables WHERE database = %(db)s AND name = 'historical_data'",
                        parameters={'db': self.database}
                    )
                    if not check_new.result_rows:
                        self.client.command("RENAME TABLE historical_data_old TO historical_data")
                        self.logger.info("Rollback completed")
                    
                # Clean up new table if it exists
                check_new_table = self.client.query(
                    "SELECT name FROM system.tables WHERE database = %(db)s AND name = 'historical_data_new'",
                    parameters={'db': self.database}
                )
                if check_new_table.result_rows:
                    self.client.command("DROP TABLE historical_data_new")
                    self.logger.info("Cleaned up historical_data_new table")
                    
            except Exception as rollback_error:
                self.logger.error(f"Rollback failed: {rollback_error}")
            raise
    
    async def _create_tables(self):
        """Create all required tables and update schemas if needed."""
        # First, check and migrate existing tables if schema differs
        await self._migrate_schemas()
        
        # Market data table (partitioned by date for performance)
        market_data_table = """
        CREATE TABLE IF NOT EXISTS market_data (
            timestamp DateTime64(3),
            date Date MATERIALIZED toDate(timestamp),
            symbol String,
            asset_type String,
            runner_name String,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            ltp Float64,
            volume UInt64,
            turnover Float64,
            price_change Float64,
            price_change_pct Float64,
            volatility Float64,
            bid_price Float64,
            ask_price Float64,
            bid_size UInt32,
            ask_size UInt32,
            metadata String DEFAULT ''
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, asset_type, timestamp)
        SETTINGS index_granularity = 8192
        """
        
        # Historical OHLC data table
        historical_data_table = """
        CREATE TABLE IF NOT EXISTS historical_data (
            timestamp DateTime64(3),
            date Date MATERIALIZED toDate(timestamp),
            symbol String,
            asset_type String,
            timeframe String,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64,
            turnover Float64
        ) ENGINE = MergeTree()
        PARTITION BY (symbol, toYYYYMM(date))
        ORDER BY (symbol, timeframe, timestamp)
        SETTINGS index_granularity = 8192
        """
        
        # Trading signals table
        signals_table = """
        CREATE TABLE IF NOT EXISTS trading_signals (
            timestamp DateTime64(3),
            date Date MATERIALIZED toDate(timestamp),
            signal_id String,
            symbol String,
            asset_type String,
            strategy String,
            action String,
            price Float64,
            quantity UInt32,
            confidence Float64,
            target Float64,
            stop_loss Float64,
            metadata String DEFAULT ''
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, strategy, timestamp)
        SETTINGS index_granularity = 8192
        """
        
        # Options data table
        options_data_table = """
        CREATE TABLE IF NOT EXISTS options_data (
            timestamp DateTime64(3),
            date Date MATERIALIZED toDate(timestamp),
            underlying String,
            expiry_date Date,
            strike Float64,
            option_type String,
            ltp Float64,
            bid Float64,
            ask Float64,
            volume UInt64,
            open_interest UInt64,
            delta Float64,
            gamma Float64,
            theta Float64,
            vega Float64,
            implied_volatility Float64,
            moneyness Float64,
            time_to_expiry Float64
        ) ENGINE = MergeTree()
        PARTITION BY (underlying, toYYYYMM(expiry_date))
        ORDER BY (underlying, expiry_date, strike, option_type, timestamp)
        SETTINGS index_granularity = 8192
        """
        
        # Performance data table
        performance_table = """
        CREATE TABLE IF NOT EXISTS strategy_performance (
            timestamp DateTime64(3),
            date Date MATERIALIZED toDate(timestamp),
            strategy String,
            symbol String,
            total_trades UInt32,
            winning_trades UInt32,
            losing_trades UInt32,
            total_pnl Float64,
            max_drawdown Float64,
            sharpe_ratio Float64,
            win_rate Float64,
            avg_win Float64,
            avg_loss Float64,
            metadata String DEFAULT ''
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (strategy, symbol, timestamp)
        SETTINGS index_granularity = 8192
        """
        
        # Execute table creation
        tables = [
            market_data_table,
            historical_data_table,
            signals_table,
            options_data_table,
            performance_table
        ]
        
        for table_sql in tables:
            try:
                self.client.command(table_sql)
                self.logger.debug(f"Created table: {table_sql.split('(')[0].split()[-1]}")
            except Exception as e:
                self.logger.error(f"Error creating table: {e}")
                raise
    
    async def store_market_data(self, symbol: str, asset_type: str,
                               data: pd.DataFrame, runner_name: str) -> bool:
        """Store market data in ClickHouse."""
        try:
            if data.empty:
                return True
            
            # Prepare data for insertion
            data_copy = data.copy()
            data_copy['symbol'] = symbol
            data_copy['asset_type'] = asset_type
            data_copy['runner_name'] = runner_name
            
            # Ensure timestamp column (IST timezone-aware)
            if 'timestamp' not in data_copy.columns:
                data_copy['timestamp'] = get_current_time()
            
            # Convert timestamps to UTC for storage (ClickHouse DateTime is UTC)
            if 'timestamp' in data_copy.columns:
                data_copy['timestamp'] = pd.to_datetime(data_copy['timestamp']).apply(
                    lambda dt: to_utc(dt) if dt.tzinfo else to_utc(to_ist(dt))
                )
            
            # Fill missing columns with defaults
            required_columns = [
                'open', 'high', 'low', 'close', 'ltp', 'volume', 'turnover',
                'price_change', 'price_change_pct', 'volatility',
                'bid_price', 'ask_price', 'bid_size', 'ask_size', 'metadata'
            ]
            
            for col in required_columns:
                if col not in data_copy.columns:
                    if col in ['metadata']:
                        data_copy[col] = ''
                    elif col in ['bid_size', 'ask_size', 'volume']:
                        data_copy[col] = 0
                    else:
                        data_copy[col] = 0.0
            
            # Insert data using thread-local client
            client = self._get_thread_client()
            client.insert_df('market_data', data_copy)
            
            self.logger.debug(f"Stored {len(data_copy)} market data records for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing market data for {symbol}: {e}")
            return False
    
    async def get_market_data(self, symbol: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit: Optional[int] = None) -> pd.DataFrame:
        """Retrieve market data from ClickHouse."""
        try:
            query = "SELECT * FROM market_data WHERE symbol = %(symbol)s"
            params = {'symbol': symbol}
            
            if start_time:
                # Convert IST to UTC for querying
                start_utc = to_utc(start_time) if start_time.tzinfo else to_utc(to_ist(start_time))
                query += " AND timestamp >= %(start_time)s"
                params['start_time'] = start_utc
            
            if end_time:
                # Convert IST to UTC for querying
                end_utc = to_utc(end_time) if end_time.tzinfo else to_utc(to_ist(end_time))
                query += " AND timestamp <= %(end_time)s"
                params['end_time'] = end_utc
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            # Use thread-local client
            client = self._get_thread_client()
            result = client.query_df(query, parameters=params)
            
            if not result.empty:
                # Convert timestamps back to IST for display
                if 'timestamp' in result.columns:
                    result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
                result.set_index('timestamp', inplace=True)
                result.sort_index(inplace=True)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving market data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def get_latest_market_data(self, symbol: str) -> Optional[pd.Series]:
        """Get the latest market data point for a symbol."""
        try:
            query = """
            SELECT * FROM market_data 
            WHERE symbol = %(symbol)s 
            ORDER BY timestamp DESC 
            LIMIT 1
            """
            
            # Use thread-local client
            client = self._get_thread_client()
            result = client.query_df(query, parameters={'symbol': symbol})
            
            if not result.empty:
                # Convert timestamp to IST
                if 'timestamp' in result.columns:
                    result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
                return result.iloc[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting latest market data for {symbol}: {e}")
            return None
    
    async def store_historical_data(self, symbol: str, asset_type: str,
                                   data: pd.DataFrame, timeframe: str) -> bool:
        """Store historical OHLC data."""
        try:
            if data.empty:
                return True
            
            data_copy = data.copy()
            data_copy['symbol'] = symbol
            data_copy['asset_type'] = asset_type
            data_copy['timeframe'] = timeframe
            
            # Ensure required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume', 'turnover']
            for col in required_columns:
                if col not in data_copy.columns:
                    if col in ['volume']:
                        data_copy[col] = 0
                    elif col in ['turnover']:
                        data_copy[col] = 0.0
                    else:
                        data_copy[col] = data_copy.get('close', 0.0)
            
            # Convert timestamps to UTC for storage (ClickHouse DateTime is UTC)
            if 'timestamp' in data_copy.columns:
                # If index is datetime, use it as timestamp
                if isinstance(data_copy.index, pd.DatetimeIndex):
                    data_copy['timestamp'] = data_copy.index
                
                # Convert to UTC for storage
                data_copy['timestamp'] = pd.to_datetime(data_copy['timestamp']).apply(
                    lambda dt: to_utc(dt) if dt.tzinfo else to_utc(to_ist(dt))
                )
            
            # Use thread-local client
            client = self._get_thread_client()
            client.insert_df('historical_data', data_copy)
            
            self.logger.debug(f"Stored {len(data_copy)} historical records for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing historical data for {symbol}: {e}")
            return False
    
    async def get_historical_data(self, symbol: str, timeframe: str,
                                 start_date: Union[datetime, date], 
                                 end_date: Union[datetime, date]) -> pd.DataFrame:
        """Retrieve historical OHLC data."""
        try:
            # Convert date to datetime if needed (at start of day)
            if isinstance(start_date, date) and not isinstance(start_date, datetime):
                start_date = datetime.combine(start_date, datetime.min.time())
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                end_date = datetime.combine(end_date, datetime.max.time())
            
            # Convert IST times to UTC for querying (ClickHouse stores in UTC)
            start_utc = to_utc(start_date) if start_date.tzinfo else to_utc(to_ist(start_date))
            end_utc = to_utc(end_date) if end_date.tzinfo else to_utc(to_ist(end_date))
            
            query = """
            SELECT * FROM historical_data 
            WHERE symbol = %(symbol)s 
            AND timeframe = %(timeframe)s
            AND timestamp >= %(start_date)s
            AND timestamp <= %(end_date)s
            ORDER BY timestamp ASC
            """
            
            params = {
                'symbol': symbol,
                'timeframe': timeframe,
                'start_date': start_utc,
                'end_date': end_utc
            }
            
            # Use thread-local client
            client = self._get_thread_client()
            result = client.query_df(query, parameters=params)
            
            # Convert timestamps back to IST for display
            if not result.empty and 'timestamp' in result.columns:
                result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
            
            # Don't set timestamp as index - keep it as a column for compatibility
            # with historical data manager's completeness check
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def store_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Store trading signal."""
        try:
            # Get timestamp (IST timezone-aware)
            timestamp = signal_data.get('timestamp', get_current_time())
            
            # Convert to UTC for storage
            if isinstance(timestamp, datetime):
                timestamp_utc = to_utc(timestamp) if timestamp.tzinfo else to_utc(to_ist(timestamp))
            else:
                timestamp_utc = to_utc(get_current_time())
            
            # Prepare signal data
            data_dict = {
                'timestamp': timestamp_utc,
                'signal_id': signal_data.get('signal_id', ''),
                'symbol': signal_data.get('symbol', ''),
                'asset_type': signal_data.get('asset_type', ''),
                'strategy': signal_data.get('strategy', ''),
                'action': signal_data.get('action', ''),
                'price': float(signal_data.get('price', 0.0)),
                'quantity': int(signal_data.get('quantity', 0)),
                'confidence': float(signal_data.get('confidence', 0.0)),
                'target': float(signal_data.get('target', 0.0)),
                'stop_loss': float(signal_data.get('stop_loss', 0.0)),
                'metadata': signal_data.get('metadata', '')
            }
            
            # Use thread-local client to avoid concurrent query errors
            client = self._get_thread_client()
            client.insert('trading_signals', [list(data_dict.values())],
                         column_names=list(data_dict.keys()))
            
            self.logger.debug(f"Stored signal for {signal_data.get('symbol')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing signal: {e}")
            return False
    
    async def get_signals(self, symbol: Optional[str] = None,
                         strategy: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve trading signals."""
        try:
            query = "SELECT * FROM trading_signals WHERE 1=1"
            params = {}
            
            if symbol:
                query += " AND symbol = %(symbol)s"
                params['symbol'] = symbol
            
            if strategy:
                query += " AND strategy = %(strategy)s"
                params['strategy'] = strategy
            
            if start_time:
                # Convert IST to UTC for querying
                start_utc = to_utc(start_time) if start_time.tzinfo else to_utc(to_ist(start_time))
                query += " AND timestamp >= %(start_time)s"
                params['start_time'] = start_utc
            
            if end_time:
                # Convert IST to UTC for querying
                end_utc = to_utc(end_time) if end_time.tzinfo else to_utc(to_ist(end_time))
                query += " AND timestamp <= %(end_time)s"
                params['end_time'] = end_utc
            
            query += " ORDER BY timestamp DESC"
            
            # Use thread-local client to avoid concurrent query errors
            client = self._get_thread_client()
            result = client.query_df(query, parameters=params)
            
            # Convert timestamps back to IST
            if not result.empty and 'timestamp' in result.columns:
                result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
            
            # Convert to list of dicts
            signals = result.to_dict('records')
            
            # Add 'id' field as alias for 'signal_id' for backward compatibility
            for signal in signals:
                if 'signal_id' in signal and 'id' not in signal:
                    signal['id'] = signal['signal_id']
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error retrieving signals: {e}")
            return []
    
    async def get_last_signal(self, symbol: str, strategy: str, 
                             since: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve the last signal for a given symbol and strategy.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            since: Optional start time filter (e.g., today's market open)
        
        Returns:
            Dictionary containing last signal data or None if no signal found
        """
        try:
            query = """
                SELECT * FROM trading_signals 
                WHERE symbol = %(symbol)s 
                AND strategy = %(strategy)s
            """
            params = {'symbol': symbol, 'strategy': strategy}
            
            if since:
                # Convert IST to UTC for querying
                since_utc = to_utc(since) if since.tzinfo else to_utc(to_ist(since))
                query += " AND timestamp >= %(since)s"
                params['since'] = since_utc
            
            query += " ORDER BY timestamp DESC LIMIT 1"
            
            # Use thread-local client to avoid concurrent query errors
            client = self._get_thread_client()
            result = client.query_df(query, parameters=params)
            
            if result.empty:
                return None
            
            # Convert timestamp back to IST
            if 'timestamp' in result.columns:
                result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
            
            signal = result.to_dict('records')[0]
            
            # Add 'id' field as alias for 'signal_id' for backward compatibility
            if 'signal_id' in signal and 'id' not in signal:
                signal['id'] = signal['signal_id']
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error retrieving last signal for {symbol}/{strategy}: {e}")
            return None
    
    async def store_options_data(self, underlying: str, expiry_date: str,
                                data: pd.DataFrame) -> bool:
        """Store options chain data."""
        try:
            if data.empty:
                return True
            
            data_copy = data.copy()
            data_copy['underlying'] = underlying
            data_copy['expiry_date'] = expiry_date
            
            if 'timestamp' not in data_copy.columns:
                data_copy['timestamp'] = get_current_time()
            
            # Convert timestamps to UTC for storage
            if 'timestamp' in data_copy.columns:
                data_copy['timestamp'] = pd.to_datetime(data_copy['timestamp']).apply(
                    lambda dt: to_utc(dt) if dt.tzinfo else to_utc(to_ist(dt))
                )
            
            # Fill missing columns
            required_columns = [
                'strike', 'option_type', 'ltp', 'bid', 'ask', 'volume',
                'open_interest', 'delta', 'gamma', 'theta', 'vega',
                'implied_volatility', 'moneyness', 'time_to_expiry'
            ]
            
            for col in required_columns:
                if col not in data_copy.columns:
                    if col == 'option_type':
                        data_copy[col] = 'CE'
                    elif col in ['volume', 'open_interest']:
                        data_copy[col] = 0
                    else:
                        data_copy[col] = 0.0
            
            self.client.insert_df('options_data', data_copy)
            
            self.logger.debug(f"Stored options data for {underlying}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing options data: {e}")
            return False
    
    async def get_options_chain(self, underlying: str, expiry_date: str) -> pd.DataFrame:
        """Retrieve options chain data."""
        try:
            query = """
            SELECT * FROM options_data 
            WHERE underlying = %(underlying)s 
            AND expiry_date = %(expiry_date)s
            ORDER BY strike ASC, option_type ASC
            """
            
            params = {
                'underlying': underlying,
                'expiry_date': expiry_date
            }
            
            result = self.client.query_df(query, parameters=params)
            
            # Convert timestamps back to IST
            if not result.empty and 'timestamp' in result.columns:
                result['timestamp'] = pd.to_datetime(result['timestamp']).apply(to_ist)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving options chain: {e}")
            return pd.DataFrame()
    
    async def store_performance_data(self, strategy: str, symbol: str,
                                   performance_data: Dict[str, Any]) -> bool:
        """Store strategy performance metrics."""
        try:
            # Get timestamp (IST timezone-aware)
            timestamp = performance_data.get('timestamp', get_current_time())
            
            # Convert to UTC for storage
            if isinstance(timestamp, datetime):
                timestamp_utc = to_utc(timestamp) if timestamp.tzinfo else to_utc(to_ist(timestamp))
            else:
                timestamp_utc = to_utc(get_current_time())
            
            data_dict = {
                'timestamp': timestamp_utc,
                'strategy': strategy,
                'symbol': symbol,
                'total_trades': int(performance_data.get('total_trades', 0)),
                'winning_trades': int(performance_data.get('winning_trades', 0)),
                'losing_trades': int(performance_data.get('losing_trades', 0)),
                'total_pnl': float(performance_data.get('total_pnl', 0.0)),
                'max_drawdown': float(performance_data.get('max_drawdown', 0.0)),
                'sharpe_ratio': float(performance_data.get('sharpe_ratio', 0.0)),
                'win_rate': float(performance_data.get('win_rate', 0.0)),
                'avg_win': float(performance_data.get('avg_win', 0.0)),
                'avg_loss': float(performance_data.get('avg_loss', 0.0)),
                'metadata': performance_data.get('metadata', '')
            }
            
            self.client.insert('strategy_performance', [list(data_dict.values())],
                             column_names=list(data_dict.keys()))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing performance data: {e}")
            return False
    
    async def get_performance_summary(self, strategy: Optional[str] = None,
                                    symbol: Optional[str] = None,
                                    days: int = 30) -> Dict[str, Any]:
        """Get performance summary."""
        try:
            query = """
            SELECT 
                strategy,
                symbol,
                sum(total_trades) as total_trades,
                sum(winning_trades) as winning_trades,
                sum(losing_trades) as losing_trades,
                sum(total_pnl) as total_pnl,
                max(max_drawdown) as max_drawdown,
                avg(sharpe_ratio) as avg_sharpe_ratio,
                avg(win_rate) as avg_win_rate
            FROM strategy_performance 
            WHERE timestamp >= %(start_date)s
            """
            
            params = {
                'start_date': get_current_time() - timedelta(days=days)
            }
            
            if strategy:
                query += " AND strategy = %(strategy)s"
                params['strategy'] = strategy
            
            if symbol:
                query += " AND symbol = %(symbol)s"
                params['symbol'] = symbol
            
            query += " GROUP BY strategy, symbol"
            
            result = self.client.query_df(query, parameters=params)
            
            if not result.empty:
                return result.to_dict('records')[0]
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting performance summary: {e}")
            return {}
    
    async def execute_query(self, query: str, parameters: Optional[Dict] = None) -> Any:
        """Execute a custom query."""
        try:
            if parameters:
                result = self.client.query_df(query, parameters=parameters)
            else:
                result = self.client.query_df(query)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of ClickHouse."""
        try:
            # Basic connectivity test
            result = self.client.query("SELECT 1").result_rows
            
            # Get system information
            system_info = self.client.query("""
                SELECT 
                    name, 
                    value 
                FROM system.settings 
                WHERE name IN ('max_memory_usage', 'max_execution_time')
            """).result_rows
            
            # Get table sizes
            table_sizes = self.client.query(f"""
                SELECT 
                    table,
                    formatReadableSize(sum(bytes)) as size,
                    sum(rows) as rows
                FROM system.parts 
                WHERE database = '{self.database}'
                GROUP BY table
            """).result_rows
            
            return {
                'status': 'healthy' if result and result[0][0] == 1 else 'unhealthy',
                'connection': 'active',
                'system_info': dict(system_info),
                'table_sizes': {row[0]: {'size': row[1], 'rows': row[2]} for row in table_sizes}
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def optimize_storage(self) -> bool:
        """Optimize ClickHouse storage."""
        try:
            # Optimize tables
            tables = ['market_data', 'historical_data', 'trading_signals', 
                     'options_data', 'strategy_performance']
            
            for table in tables:
                self.client.command(f"OPTIMIZE TABLE {table}")
            
            self.logger.info("Storage optimization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error optimizing storage: {e}")
            return False
    
    async def batch_store_market_data(self, batch_data: List[Dict[str, Any]]) -> bool:
        """Store multiple market data records in a batch."""
        try:
            if not batch_data:
                return True
            
            # Convert to DataFrame for efficient insertion
            df = pd.DataFrame(batch_data)
            
            # Fill missing columns
            required_columns = [
                'timestamp', 'symbol', 'asset_type', 'runner_name',
                'open', 'high', 'low', 'close', 'ltp', 'volume', 'turnover',
                'price_change', 'price_change_pct', 'volatility',
                'bid_price', 'ask_price', 'bid_size', 'ask_size', 'metadata'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    if col == 'timestamp':
                        df[col] = get_current_time()
                    elif col in ['metadata']:
                        df[col] = ''
                    elif col in ['bid_size', 'ask_size', 'volume']:
                        df[col] = 0
                    else:
                        df[col] = 0.0
            
            self.client.insert_df('market_data', df)
            
            self.logger.debug(f"Batch stored {len(batch_data)} market data records")
            return True
            
        except Exception as e:
            self.logger.error(f"Error batch storing market data: {e}")
            return False
    
    async def get_symbols_by_asset_type(self, asset_type: str) -> List[str]:
        """Get all symbols for a specific asset type."""
        try:
            query = """
            SELECT DISTINCT symbol 
            FROM market_data 
            WHERE asset_type = %(asset_type)s
            """
            
            result = self.client.query(query, parameters={'asset_type': asset_type})
            return [row[0] for row in result.result_rows]
            
        except Exception as e:
            self.logger.error(f"Error getting symbols by asset type: {e}")
            return []
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> bool:
        """Clean up old data beyond the retention period."""
        try:
            cutoff_date = get_current_time() - timedelta(days=days_to_keep)
            
            tables = ['market_data', 'historical_data', 'trading_signals', 
                     'options_data', 'strategy_performance']
            
            for table in tables:
                query = f"""
                ALTER TABLE {table} 
                DELETE WHERE timestamp < %(cutoff_date)s
                """
                
                self.client.command(query, parameters={'cutoff_date': cutoff_date})
            
            self.logger.info(f"Cleaned up data older than {days_to_keep} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return False
