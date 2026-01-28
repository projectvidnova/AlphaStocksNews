"""
PostgreSQL Data Layer Implementation for AlphaStock Trading System

PostgreSQL implementation optimized for trading data with time series optimizations.
Uses TimescaleDB extension when available for better time series performance.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import logging
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sqlalchemy as sa

from . import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class PostgreSQLDataLayer(DataLayerInterface):
    """
    PostgreSQL implementation of the data layer interface.
    
    Optimized for trading data with proper indexing and partitioning.
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5432,
                 database: str = 'alphastock', username: str = 'postgres',
                 password: str = '', pool_size: int = 20, max_overflow: int = 30):
        """
        Initialize PostgreSQL data layer.
        
        Args:
            host: PostgreSQL server host
            port: PostgreSQL server port
            database: Database name
            username: Username for authentication
            password: Password for authentication
            pool_size: Connection pool size
            max_overflow: Maximum pool overflow
        """
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.logger = setup_logger(name="PostgreSQLDataLayer")
        self._initialized = False
        
        # Connection strings
        self.sync_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        self.async_url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
    
    async def initialize(self) -> bool:
        """Initialize PostgreSQL connection and create tables."""
        try:
            # Create sync engine for setup operations
            self.engine = create_engine(
                self.sync_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create async engine for operations
            self.async_engine = create_async_engine(
                self.async_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                if not result or result[0] != 1:
                    raise Exception("PostgreSQL connection test failed")
            
            # Create database if it doesn't exist (handled externally)
            # Create tables and indexes
            await self._create_tables()
            
            # Try to enable TimescaleDB if available
            await self._setup_timescaledb()
            
            self._initialized = True
            self.logger.info("PostgreSQL data layer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize PostgreSQL data layer: {e}")
            return False
    
    async def close(self):
        """Close PostgreSQL connections."""
        try:
            if self.async_engine:
                await self.async_engine.dispose()
                self.async_engine = None
            
            if self.engine:
                self.engine.dispose()
                self.engine = None
            
            self._initialized = False
            self.logger.info("PostgreSQL data layer closed")
        except Exception as e:
            self.logger.error(f"Error closing PostgreSQL data layer: {e}")
    
    async def _setup_timescaledb(self):
        """Try to set up TimescaleDB extension for better time series performance."""
        try:
            with self.engine.connect() as conn:
                # Check if TimescaleDB is available
                result = conn.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_available_extensions 
                        WHERE name = 'timescaledb'
                    );
                """)).fetchone()
                
                if result and result[0]:
                    # Enable TimescaleDB
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
                    
                    # Convert tables to hypertables
                    tables_to_convert = [
                        ('market_data', 'timestamp'),
                        ('historical_data', 'timestamp'),
                        ('trading_signals', 'timestamp'),
                        ('options_data', 'timestamp'),
                        ('strategy_performance', 'timestamp')
                    ]
                    
                    for table_name, time_column in tables_to_convert:
                        try:
                            conn.execute(text(f"""
                                SELECT create_hypertable('{table_name}', '{time_column}',
                                    if_not_exists => TRUE);
                            """))
                            self.logger.info(f"Converted {table_name} to hypertable")
                        except Exception as e:
                            self.logger.debug(f"Could not convert {table_name} to hypertable: {e}")
                    
                    conn.commit()
                    self.logger.info("TimescaleDB extension enabled successfully")
                else:
                    self.logger.info("TimescaleDB not available, using standard PostgreSQL")
                    
        except Exception as e:
            self.logger.warning(f"Could not set up TimescaleDB: {e}")
    
    async def _create_tables(self):
        """Create all required tables."""
        # Market data table
        market_data_table = """
        CREATE TABLE IF NOT EXISTS market_data (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            symbol VARCHAR(50) NOT NULL,
            asset_type VARCHAR(20) NOT NULL,
            runner_name VARCHAR(50) NOT NULL,
            open DECIMAL(15,4),
            high DECIMAL(15,4),
            low DECIMAL(15,4),
            close DECIMAL(15,4),
            ltp DECIMAL(15,4),
            volume BIGINT DEFAULT 0,
            turnover DECIMAL(20,2) DEFAULT 0,
            price_change DECIMAL(15,4) DEFAULT 0,
            price_change_pct DECIMAL(8,4) DEFAULT 0,
            volatility DECIMAL(8,4) DEFAULT 0,
            bid_price DECIMAL(15,4) DEFAULT 0,
            ask_price DECIMAL(15,4) DEFAULT 0,
            bid_size INTEGER DEFAULT 0,
            ask_size INTEGER DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Historical OHLC data table
        historical_data_table = """
        CREATE TABLE IF NOT EXISTS historical_data (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            symbol VARCHAR(50) NOT NULL,
            asset_type VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            open DECIMAL(15,4) NOT NULL,
            high DECIMAL(15,4) NOT NULL,
            low DECIMAL(15,4) NOT NULL,
            close DECIMAL(15,4) NOT NULL,
            volume BIGINT DEFAULT 0,
            turnover DECIMAL(20,2) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe, timestamp)
        );
        """
        
        # Trading signals table
        signals_table = """
        CREATE TABLE IF NOT EXISTS trading_signals (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            signal_id VARCHAR(100) UNIQUE,
            symbol VARCHAR(50) NOT NULL,
            asset_type VARCHAR(20) NOT NULL,
            strategy VARCHAR(50) NOT NULL,
            action VARCHAR(10) NOT NULL,
            price DECIMAL(15,4) NOT NULL,
            quantity INTEGER DEFAULT 0,
            confidence DECIMAL(5,4) DEFAULT 0,
            target DECIMAL(15,4) DEFAULT 0,
            stop_loss DECIMAL(15,4) DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Options data table
        options_data_table = """
        CREATE TABLE IF NOT EXISTS options_data (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            underlying VARCHAR(50) NOT NULL,
            expiry_date DATE NOT NULL,
            strike DECIMAL(15,4) NOT NULL,
            option_type VARCHAR(2) NOT NULL, -- CE or PE
            ltp DECIMAL(15,4),
            bid DECIMAL(15,4),
            ask DECIMAL(15,4),
            volume BIGINT DEFAULT 0,
            open_interest BIGINT DEFAULT 0,
            delta DECIMAL(8,6),
            gamma DECIMAL(8,6),
            theta DECIMAL(8,6),
            vega DECIMAL(8,6),
            implied_volatility DECIMAL(8,6),
            moneyness DECIMAL(8,6),
            time_to_expiry DECIMAL(10,6),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Performance data table
        performance_table = """
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            strategy VARCHAR(50) NOT NULL,
            symbol VARCHAR(50) NOT NULL,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            total_pnl DECIMAL(15,4) DEFAULT 0,
            max_drawdown DECIMAL(8,4) DEFAULT 0,
            sharpe_ratio DECIMAL(8,4) DEFAULT 0,
            win_rate DECIMAL(5,4) DEFAULT 0,
            avg_win DECIMAL(15,4) DEFAULT 0,
            avg_loss DECIMAL(15,4) DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create indexes for performance
        indexes = [
            # Market data indexes
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON market_data(symbol, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_asset_type ON market_data(asset_type);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp DESC);",
            
            # Historical data indexes
            "CREATE INDEX IF NOT EXISTS idx_historical_data_symbol_timeframe ON historical_data(symbol, timeframe, timestamp DESC);",
            
            # Signals indexes
            "CREATE INDEX IF NOT EXISTS idx_signals_symbol_strategy ON trading_signals(symbol, strategy, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON trading_signals(timestamp DESC);",
            
            # Options data indexes
            "CREATE INDEX IF NOT EXISTS idx_options_underlying_expiry ON options_data(underlying, expiry_date, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_options_strike_type ON options_data(underlying, expiry_date, strike, option_type);",
            
            # Performance indexes
            "CREATE INDEX IF NOT EXISTS idx_performance_strategy_symbol ON strategy_performance(strategy, symbol, timestamp DESC);"
        ]
        
        # Execute table and index creation
        with self.engine.connect() as conn:
            tables = [
                market_data_table,
                historical_data_table,
                signals_table,
                options_data_table,
                performance_table
            ]
            
            for table_sql in tables:
                try:
                    conn.execute(text(table_sql))
                    self.logger.debug(f"Created table")
                except Exception as e:
                    self.logger.error(f"Error creating table: {e}")
                    raise
            
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                except Exception as e:
                    self.logger.warning(f"Error creating index: {e}")
            
            conn.commit()
    
    async def store_market_data(self, symbol: str, asset_type: str,
                               data: pd.DataFrame, runner_name: str) -> bool:
        """Store market data in PostgreSQL."""
        try:
            if data.empty:
                return True
            
            # Prepare data for insertion
            data_copy = data.copy()
            data_copy['symbol'] = symbol
            data_copy['asset_type'] = asset_type
            data_copy['runner_name'] = runner_name
            
            # Ensure timestamp column
            if 'timestamp' not in data_copy.columns:
                data_copy['timestamp'] = get_current_time()
            
            # Fill missing columns with defaults
            required_columns = [
                'open', 'high', 'low', 'close', 'ltp', 'volume', 'turnover',
                'price_change', 'price_change_pct', 'volatility',
                'bid_price', 'ask_price', 'bid_size', 'ask_size'
            ]
            
            for col in required_columns:
                if col not in data_copy.columns:
                    if col in ['bid_size', 'ask_size', 'volume']:
                        data_copy[col] = 0
                    else:
                        data_copy[col] = 0.0
            
            # Add metadata column
            if 'metadata' not in data_copy.columns:
                data_copy['metadata'] = '{}'
            
            # Insert using pandas to_sql for efficiency
            data_copy.to_sql(
                'market_data',
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.logger.debug(f"Stored {len(data_copy)} market data records for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing market data for {symbol}: {e}")
            return False
    
    async def get_market_data(self, symbol: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit: Optional[int] = None) -> pd.DataFrame:
        """Retrieve market data from PostgreSQL."""
        try:
            query = "SELECT * FROM market_data WHERE symbol = %(symbol)s"
            params = {'symbol': symbol}
            
            if start_time:
                query += " AND timestamp >= %(start_time)s"
                params['start_time'] = start_time
            
            if end_time:
                query += " AND timestamp <= %(end_time)s"
                params['end_time'] = end_time
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            result = pd.read_sql(
                text(query),
                self.engine,
                params=params,
                parse_dates=['timestamp']
            )
            
            if not result.empty:
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
            
            result = pd.read_sql(
                text(query),
                self.engine,
                params={'symbol': symbol},
                parse_dates=['timestamp']
            )
            
            if not result.empty:
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
            
            # Insert using pandas (handles duplicates with ON CONFLICT)
            data_copy.to_sql(
                'historical_data',
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.logger.debug(f"Stored {len(data_copy)} historical records for {symbol}")
            return True
            
        except Exception as e:
            if "duplicate key value" in str(e).lower():
                self.logger.debug(f"Some historical data already exists for {symbol}")
                return True
            else:
                self.logger.error(f"Error storing historical data for {symbol}: {e}")
                return False
    
    async def get_historical_data(self, symbol: str, timeframe: str,
                                 start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Retrieve historical OHLC data."""
        try:
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
                'start_date': start_date,
                'end_date': end_date
            }
            
            result = pd.read_sql(
                text(query),
                self.engine,
                params=params,
                parse_dates=['timestamp']
            )
            
            if not result.empty:
                result.set_index('timestamp', inplace=True)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def store_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Store trading signal."""
        try:
            query = """
            INSERT INTO trading_signals 
            (timestamp, signal_id, symbol, asset_type, strategy, action, 
             price, quantity, confidence, target, stop_loss, metadata)
            VALUES (%(timestamp)s, %(signal_id)s, %(symbol)s, %(asset_type)s, 
                    %(strategy)s, %(action)s, %(price)s, %(quantity)s, 
                    %(confidence)s, %(target)s, %(stop_loss)s, %(metadata)s)
            """
            
            params = {
                'timestamp': signal_data.get('timestamp', get_current_time()),
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
                'metadata': signal_data.get('metadata', '{}')
            }
            
            with self.engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()
            
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
                query += " AND timestamp >= %(start_time)s"
                params['start_time'] = start_time
            
            if end_time:
                query += " AND timestamp <= %(end_time)s"
                params['end_time'] = end_time
            
            query += " ORDER BY timestamp DESC"
            
            result = pd.read_sql(
                text(query),
                self.engine,
                params=params,
                parse_dates=['timestamp']
            )
            
            return result.to_dict('records')
            
        except Exception as e:
            self.logger.error(f"Error retrieving signals: {e}")
            return []
    
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
            
            data_copy.to_sql(
                'options_data',
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=500
            )
            
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
            
            result = pd.read_sql(
                text(query),
                self.engine,
                params=params,
                parse_dates=['timestamp', 'expiry_date']
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving options chain: {e}")
            return pd.DataFrame()
    
    async def store_performance_data(self, strategy: str, symbol: str,
                                   performance_data: Dict[str, Any]) -> bool:
        """Store strategy performance metrics."""
        try:
            query = """
            INSERT INTO strategy_performance 
            (timestamp, strategy, symbol, total_trades, winning_trades, 
             losing_trades, total_pnl, max_drawdown, sharpe_ratio, 
             win_rate, avg_win, avg_loss, metadata)
            VALUES (%(timestamp)s, %(strategy)s, %(symbol)s, %(total_trades)s,
                    %(winning_trades)s, %(losing_trades)s, %(total_pnl)s,
                    %(max_drawdown)s, %(sharpe_ratio)s, %(win_rate)s,
                    %(avg_win)s, %(avg_loss)s, %(metadata)s)
            """
            
            params = {
                'timestamp': performance_data.get('timestamp', get_current_time()),
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
                'metadata': performance_data.get('metadata', '{}')
            }
            
            with self.engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()
            
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
                SUM(total_trades) as total_trades,
                SUM(winning_trades) as winning_trades,
                SUM(losing_trades) as losing_trades,
                SUM(total_pnl) as total_pnl,
                MAX(max_drawdown) as max_drawdown,
                AVG(sharpe_ratio) as avg_sharpe_ratio,
                AVG(win_rate) as avg_win_rate
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
            
            result = pd.read_sql(text(query), self.engine, params=params)
            
            if not result.empty:
                return result.to_dict('records')[0]
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting performance summary: {e}")
            return {}
    
    async def execute_query(self, query: str, parameters: Optional[Dict] = None) -> Any:
        """Execute a custom query."""
        try:
            result = pd.read_sql(
                text(query),
                self.engine,
                params=parameters or {}
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of PostgreSQL."""
        try:
            with self.engine.connect() as conn:
                # Basic connectivity test
                result = conn.execute(text("SELECT 1")).fetchone()
                
                # Get database size
                db_size = conn.execute(text("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)).fetchone()
                
                # Get table sizes
                table_sizes = conn.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
                """)).fetchall()
                
                # Get connection info
                conn_info = conn.execute(text("""
                    SELECT count(*) as active_connections
                    FROM pg_stat_activity 
                    WHERE state = 'active';
                """)).fetchone()
                
            return {
                'status': 'healthy' if result and result[0] == 1 else 'unhealthy',
                'connection': 'active',
                'database_size': db_size[0] if db_size else 'unknown',
                'active_connections': conn_info[0] if conn_info else 0,
                'table_sizes': {row[1]: row[2] for row in table_sizes}
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def optimize_storage(self) -> bool:
        """Optimize PostgreSQL storage."""
        try:
            with self.engine.connect() as conn:
                # Run VACUUM and ANALYZE on all tables
                tables = ['market_data', 'historical_data', 'trading_signals', 
                         'options_data', 'strategy_performance']
                
                for table in tables:
                    conn.execute(text(f"VACUUM ANALYZE {table}"))
                
                # Update statistics
                conn.execute(text("ANALYZE"))
                
                conn.commit()
            
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
                'bid_price', 'ask_price', 'bid_size', 'ask_size'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    if col == 'timestamp':
                        df[col] = get_current_time()
                    elif col in ['bid_size', 'ask_size', 'volume']:
                        df[col] = 0
                    else:
                        df[col] = 0.0
            
            # Add metadata
            if 'metadata' not in df.columns:
                df['metadata'] = '{}'
            
            df.to_sql(
                'market_data',
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.logger.debug(f"Batch stored {len(batch_data)} market data records")
            return True
            
        except Exception as e:
            self.logger.error(f"Error batch storing market data: {e}")
            return False
    
    async def get_symbols_by_asset_type(self, asset_type: str) -> List[str]:
        """Get all symbols for a specific asset type."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT DISTINCT symbol FROM market_data WHERE asset_type = :asset_type"),
                    {"asset_type": asset_type}
                ).fetchall()
                
                return [row[0] for row in result]
            
        except Exception as e:
            self.logger.error(f"Error getting symbols by asset type: {e}")
            return []
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> bool:
        """Clean up old data beyond the retention period."""
        try:
            cutoff_date = get_current_time() - timedelta(days=days_to_keep)
            
            tables = ['market_data', 'historical_data', 'trading_signals', 
                     'options_data', 'strategy_performance']
            
            with self.engine.connect() as conn:
                for table in tables:
                    result = conn.execute(
                        text(f"DELETE FROM {table} WHERE timestamp < :cutoff_date"),
                        {"cutoff_date": cutoff_date}
                    )
                    
                    self.logger.info(f"Deleted {result.rowcount} old records from {table}")
                
                conn.commit()
            
            self.logger.info(f"Cleaned up data older than {days_to_keep} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return False
