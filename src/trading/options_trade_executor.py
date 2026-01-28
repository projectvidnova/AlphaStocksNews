"""
Options Trade Executor
Main component that connects signals to options trading execution.
"""

import logging
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .strike_selector import StrikeSelector
from .options_position_manager import OptionsPositionManager, OptionsPosition
from .options_greeks import OptionsGreeksCalculator
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("options_trade_executor")


class OptionsTradeExecutor:
    """
    Main executor that connects trading signals to options execution.
    
    Workflow:
    1. Receives signal from signal_manager
    2. Selects optimal strike using StrikeSelector
    3. Calculates stop-loss and target
    4. Places entry order
    5. Hands off to OptionsPositionManager for monitoring
    """
    
    def __init__(
        self,
        api_client,
        signal_manager,
        config: Dict,
        data_layer=None
    ):
        """
        Initialize options trade executor.
        
        Args:
            api_client: Kite API client
            signal_manager: Signal manager instance
            config: Options trading configuration
            data_layer: Data layer for persistence
        """
        self.api_client = api_client
        self.signal_manager = signal_manager
        self.config = config
        self.data_layer = data_layer
        
        # Get trading mode
        self.mode = config.get('mode', 'BALANCED')
        self.mode_config = config['modes'][self.mode]
        
        # Trading mode flags
        self.paper_trading = config.get('paper_trading', True)
        self.logging_only_mode = config.get('logging_only_mode', False)  # NEW: Logging mode
        
        # Initialize components
        self.strike_selector = StrikeSelector(api_client, self.mode_config)
        self.strike_selector.set_common_filters(config.get('common_filters', {}))
        
        self.position_manager = OptionsPositionManager(
            api_client,
            self.mode_config,
            data_layer,
            paper_trading=self.paper_trading,
            logging_only_mode=self.logging_only_mode
        )
        
        self.greeks_calculator = OptionsGreeksCalculator(
            risk_free_rate=0.06  # 6% for India
        )
        
        # Position sizing config
        self.position_config = config.get('position_management', {})
        
        # State
        self.enabled = False
        self.signal_listener_task = None
        
        # Statistics
        self.stats = {
            'signals_received': 0,
            'trades_executed': 0,
            'trades_skipped': 0,
            'entry_errors': 0,
            'logging_only_trades': 0  # NEW: Track logging-only trades
        }
        
        logger.info(f"Options Trade Executor initialized in {self.mode} mode")
        logger.info(f"Mode config: {self.mode_config.get('description', 'N/A')}")
        
        # Log trading mode status
        if self.logging_only_mode:
            logger.info("[LOGGING ONLY MODE] Orders will be logged but NOT executed")
        elif self.paper_trading:
            logger.info("[PAPER TRADING MODE] Orders will be simulated")
        else:
            logger.warning("[LIVE TRADING MODE] Real orders will be placed!")
    
    async def start(self):
        """Start the options trade executor."""
        if self.enabled:
            logger.warning("Options executor already running")
            return
        
        self.enabled = True
        
        # Start position monitoring
        await self.position_manager.start_monitoring()
        
        # Start signal listener
        self.signal_listener_task = asyncio.create_task(self._listen_for_signals())
        
        logger.info("Options Trade Executor started")
    
    async def stop(self):
        """Stop the options trade executor."""
        self.enabled = False
        
        # Stop signal listener
        if self.signal_listener_task:
            self.signal_listener_task.cancel()
            try:
                await self.signal_listener_task
            except asyncio.CancelledError:
                pass
        
        # Stop position monitoring
        await self.position_manager.stop_monitoring()
        
        logger.info("Options Trade Executor stopped")
    
    async def _listen_for_signals(self):
        """Listen for new signals and execute trades."""
        logger.info("Started listening for trading signals...")
        
        while self.enabled:
            try:
                # Get recent signals from signal manager
                await self._process_new_signals()
                
                # Check every 10 seconds
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in signal listener: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    async def _process_new_signals(self):
        """Process new signals from signal manager."""
        try:
            # Get signals from the last minute
            recent_signals = await self._get_recent_signals()
            
            for signal in recent_signals:
                # Skip if already processed
                if await self._is_signal_processed(signal['id']):
                    continue
                
                self.stats['signals_received'] += 1
                
                # Process the signal
                await self.process_signal(signal)
                
        except Exception as e:
            logger.error(f"Error processing signals: {e}")
    
    async def _get_recent_signals(self) -> List[Dict]:
        """Get recent unprocessed signals (last 1 hour only)."""
        try:
            signals_to_process = []
            
            # Method 1: Try database first (prefer database for production)
            if self.data_layer:
                try:
                    from datetime import datetime, timedelta
                    # Only get signals from last 1 hour (not days/months old)
                    start_time = get_current_time() - timedelta(hours=1)
                    db_signals = await self.data_layer.get_signals(start_time=start_time)
                    
                    if db_signals:
                        # Convert to list of dicts if needed
                        for sig in db_signals:
                            if isinstance(sig, dict):
                                signals_to_process.append(sig)
                            elif hasattr(sig, 'to_dict'):
                                signals_to_process.append(sig.to_dict())
                            else:
                                signals_to_process.append(sig)
                        
                        logger.debug(f"Retrieved {len(signals_to_process)} signals from database (last 1 hour)")
                except Exception as e:
                    logger.debug(f"Database signal retrieval failed: {e}")
            
            # Method 2: Fallback to signal manager's in-memory signals
            if not signals_to_process and self.signal_manager:
                try:
                    if hasattr(self.signal_manager, 'get_active_signals_list'):
                        memory_signals = self.signal_manager.get_active_signals_list()
                        signals_to_process.extend(memory_signals)
                        logger.debug(f"Retrieved {len(memory_signals)} signals from memory")
                except Exception as e:
                    logger.debug(f"Memory signal retrieval failed: {e}")
            
            # Filter unprocessed and recent signals only
            from datetime import datetime, timedelta
            one_hour_ago = get_current_time() - timedelta(hours=1)
            
            unprocessed = []
            for sig in signals_to_process:
                sig_id = sig.get('id', sig.get('signal_id', ''))
                sig_timestamp = sig.get('timestamp', '')
                
                # Skip if no ID
                if not sig_id:
                    continue
                
                # Skip if already processed
                if await self._is_signal_processed(sig_id):
                    continue
                
                # Skip if too old (timestamp check)
                if sig_timestamp:
                    try:
                        sig_dt = datetime.fromisoformat(sig_timestamp.replace('Z', '+00:00'))
                        # Ensure timezone-aware for comparison
                        if sig_dt.tzinfo:
                            sig_dt = to_ist(sig_dt)  # Convert to IST if has timezone
                        else:
                            # Assume naive datetime is IST
                            from src.utils.timezone_utils import make_aware
                            sig_dt = make_aware(sig_dt, 'IST')
                        
                        one_hour_ago = get_current_time() - timedelta(hours=1)
                        if sig_dt < one_hour_ago:
                            logger.debug(f"Skipping old signal {sig_id[:8]} from {sig_timestamp}")
                            continue
                    except (ValueError, AttributeError):
                        pass  # If timestamp parse fails, include signal (better safe than sorry)
                
                unprocessed.append(sig)
            
            if unprocessed:
                logger.info(f"Found {len(unprocessed)} unprocessed signals")
            
            return unprocessed[:10]  # Limit to 10
            
        except Exception as e:
            logger.error(f"Error fetching recent signals: {e}", exc_info=True)
            return []
    
    async def _is_signal_processed(self, signal_id: str) -> bool:
        """Check if signal has already been processed."""
        # Check if we have an active position for this signal
        for position in self.position_manager.active_positions.values():
            if position.signal_id == signal_id:
                return True
        return False
    
    async def process_signal(self, signal: Dict) -> bool:
        """
        Process a trading signal and execute options trade.
        
        Args:
            signal: Signal dictionary with symbol, signal_type, entry_price, target, etc.
            
        Returns:
            True if trade executed successfully, False otherwise
        """
        try:
            symbol = signal.get('symbol', '')
            signal_type = signal.get('signal_type', '')
            entry_price = signal.get('entry_price', 0)
            target_price = signal.get('target', 0)
            signal_id = signal.get('id', '')
            signal_timestamp = signal.get('timestamp', '')
            
            # 0. Filter out very old signals (older than 24 hours)
            if signal_timestamp:
                try:
                    signal_dt = datetime.fromisoformat(signal_timestamp.replace('Z', '+00:00'))
                    # Ensure timezone-aware for accurate age calculation
                    if signal_dt.tzinfo:
                        signal_dt = to_ist(signal_dt)  # Convert to IST if has timezone
                    else:
                        # Assume naive datetime is IST
                        from src.utils.timezone_utils import make_aware
                        signal_dt = make_aware(signal_dt, 'IST')
                    
                    signal_age = get_current_time() - signal_dt
                    
                    if signal_age > timedelta(hours=24):
                        logger.debug(
                            f"Ignoring stale signal (age: {signal_age.total_seconds()/3600:.1f}h): "
                            f"{symbol} {signal_type} from {signal_timestamp}"
                        )
                        self.stats['trades_skipped'] += 1
                        return False
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Could not parse signal timestamp '{signal_timestamp}': {e}")
            
            logger.info(f"Processing signal: {symbol} {signal_type} @ {entry_price}, target: {target_price}")
            
            # 1. Validate signal (this also checks if symbol is valid for options)
            if not self._validate_signal(signal):
                logger.warning(f"Signal validation failed for {symbol}")
                self.stats['trades_skipped'] += 1
                return False
            
            # 2. Clean symbol (remove exchange prefix for options processing)
            clean_symbol = symbol.replace('NSE:', '').replace('NFO:', '').strip()
            logger.debug(f"Cleaned symbol: {symbol} -> {clean_symbol}")
            
            # 3. Check risk limits
            if not self._check_risk_limits():
                logger.warning("Risk limits exceeded, skipping trade")
                self.stats['trades_skipped'] += 1
                return False
            
            # 4. Calculate expected move
            if target_price > 0 and entry_price > 0:
                expected_move_pct = abs((target_price - entry_price) / entry_price * 100)
            else:
                expected_move_pct = 1.5  # Default assumption
            
            # 5. Get signal strength (if available in metadata)
            signal_strength = signal.get('metadata', {}).get('confidence', 0.7)
            
            # 6. Select optimal strike (use cleaned symbol)
            selected_option = self.strike_selector.select_best_strike(
                underlying_symbol=clean_symbol,  # Use cleaned symbol
                current_price=entry_price,
                signal_type=signal_type,
                expected_move_pct=expected_move_pct,
                signal_strength=signal_strength
            )
            
            if not selected_option:
                logger.error(f"Could not select strike for {clean_symbol}")
                self.stats['trades_skipped'] += 1
                return False
            
            # 7. Get current option premium
            current_premium = await self._get_option_premium(selected_option['symbol'])
            if not current_premium or current_premium <= 0:
                logger.error(f"Could not fetch premium for {selected_option['symbol']}")
                self.stats['trades_skipped'] += 1
                return False
            
            selected_option['ltp'] = current_premium
            
            logger.info(
                f"Selected option: {selected_option['symbol']} (Strike: {selected_option['strike']}, "
                f"Premium: ₹{current_premium}, Delta: {selected_option.get('delta', 'N/A')})"
            )
            
            # 8. Calculate stop-loss and target premiums
            stop_loss_premium, target_premium = self._calculate_exit_levels(
                current_premium, selected_option, expected_move_pct
            )
            
            logger.info(
                f"Exit levels: Entry=₹{current_premium}, SL=₹{stop_loss_premium}, "
                f"Target=₹{target_premium}"
            )
            
            # 9. Calculate position size
            quantity = self._calculate_position_size(
                current_premium, selected_option['lot_size'], entry_price
            )
            
            if quantity <= 0:
                logger.warning("Position size calculation resulted in 0 quantity")
                self.stats['trades_skipped'] += 1
                return False
            
            logger.info(f"Position size: {quantity} units ({quantity / selected_option['lot_size']:.1f} lots)")
            
            # 10. Place entry order
            order_id = await self._place_entry_order(selected_option, quantity, current_premium)
            
            if not order_id:
                logger.error("Failed to place entry order")
                self.stats['entry_errors'] += 1
                return False
            
            # 11. Create position and add to position manager
            position = OptionsPosition(
                position_id=str(uuid.uuid4()),
                symbol=selected_option['symbol'],
                option_type=selected_option['option_type'],
                strike=selected_option['strike'],
                entry_premium=current_premium,
                quantity=quantity,
                lot_size=selected_option['lot_size'],
                stop_loss_premium=stop_loss_premium,
                target_premium=target_premium,
                mode=self.mode,
                signal_id=signal_id,
                underlying_symbol=clean_symbol,  # Use cleaned symbol
                underlying_entry_price=entry_price
            )
            
            self.position_manager.add_position(position)
            
            self.stats['trades_executed'] += 1
            
            logger.info(
                f"✅ Options trade executed successfully: {selected_option['symbol']}, "
                f"Qty: {quantity}, Entry: ₹{current_premium}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}", exc_info=True)
            self.stats['entry_errors'] += 1
            return False
    
    def _validate_signal(self, signal: Dict) -> bool:
        """Validate if signal meets entry criteria."""
        # 0. Filter out test signals explicitly
        symbol = signal.get('symbol', '')
        if symbol.startswith('TEST_') or symbol == 'TEST_SIGNAL':
            logger.debug(f"Ignoring test signal: {symbol}")
            return False
        
        # 1. Check if symbol is valid for options trading
        # Valid options underlyings (Indian market)
        VALID_OPTIONS_SYMBOLS = {
            'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY',  # Indices
            'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',  # Stocks
            'SBIN', 'BHARTIARTL', 'ITC', 'KOTAKBANK', 'LT',
            'BAJFINANCE', 'ASIANPAINT', 'MARUTI', 'TITAN', 'WIPRO',
            'ONGC', 'TATAMOTORS', 'AXISBANK', 'SUNPHARMA', 'HINDUNILVR'
        }
        
        # Symbol aliases/mappings for commonly misnamed symbols
        SYMBOL_ALIASES = {
            'NIFTYFINSERVICE': None,  # Not tradeable via options, ignore
            'NIFTYBANK': 'BANKNIFTY',
            'NIFTYFIN': 'FINNIFTY',
            'NIFTYMID': 'MIDCPNIFTY'
        }
        
        # Clean symbol (remove exchange prefix, whitespace)
        clean_symbol = symbol.replace('NSE:', '').replace('NFO:', '').replace('BSE:', '').strip()
        
        # Check if symbol needs alias mapping
        if clean_symbol in SYMBOL_ALIASES:
            mapped_symbol = SYMBOL_ALIASES[clean_symbol]
            if mapped_symbol is None:
                logger.debug(
                    f"Symbol '{symbol}' (cleaned: '{clean_symbol}') is not tradeable for options. Ignoring."
                )
                return False
            else:
                logger.info(f"Mapping symbol '{clean_symbol}' to '{mapped_symbol}'")
                clean_symbol = mapped_symbol
                # Update signal with corrected symbol
                signal['symbol'] = mapped_symbol
        
        if clean_symbol not in VALID_OPTIONS_SYMBOLS:
            logger.warning(
                f"Symbol '{symbol}' (cleaned: '{clean_symbol}') is not a valid options underlying. "
                f"Valid symbols: {sorted(VALID_OPTIONS_SYMBOLS)}"
            )
            return False
        
        # 2. Check if signal has required fields
        if not signal.get('entry_price') or not signal.get('signal_type'):
            logger.warning(f"Signal missing required fields (entry_price or signal_type)")
            return False
        
        # Get entry filters from mode config
        entry_filters = self.mode_config.get('entry_filters', {})
        
        # 3. Check signal strength
        min_strength = entry_filters.get('min_signal_strength', 0.6)
        signal_strength = signal.get('metadata', {}).get('confidence', 0.7)
        
        if signal_strength < min_strength:
            logger.debug(f"Signal strength {signal_strength} < minimum {min_strength}")
            return False
        
        # 4. Check expected move
        entry_price = signal.get('entry_price', 0)
        target_price = signal.get('target', 0)
        
        if entry_price > 0 and target_price > 0:
            expected_move_pct = abs((target_price - entry_price) / entry_price * 100)
            min_move = entry_filters.get('min_expected_move_pct', 1.0)
            
            if expected_move_pct < min_move:
                logger.debug(f"Expected move {expected_move_pct:.2f}% < minimum {min_move}%")
                return False
        
        logger.info(f"✅ Signal validation passed for {clean_symbol}")
        return True
    
    def _check_risk_limits(self) -> bool:
        """Check if current risk limits allow new trade."""
        max_positions = self.position_config.get('max_concurrent_positions', 3)
        
        active_count = len(self.position_manager.active_positions)
        if active_count >= max_positions:
            logger.debug(f"Max concurrent positions reached: {active_count}/{max_positions}")
            return False
        
        # Could add more checks: daily loss limit, consecutive losses, etc.
        
        return True
    
    def _calculate_exit_levels(
        self,
        entry_premium: float,
        option_details: Dict,
        expected_move_pct: float
    ) -> tuple:
        """
        Calculate stop-loss and target premiums.
        
        Returns:
            (stop_loss_premium, target_premium)
        """
        # Get risk management config
        risk_config = self.mode_config.get('risk_management', {})
        
        # Stop-loss calculation
        stop_loss_pct = risk_config.get('stop_loss_pct', 35)
        stop_loss_premium = entry_premium * (1 - stop_loss_pct / 100)
        
        # Target calculation
        target_pct = risk_config.get('target_pct', 60)
        target_premium = entry_premium * (1 + target_pct / 100)
        
        # Ensure minimum values
        stop_loss_premium = max(stop_loss_premium, 1.0)  # Minimum ₹1
        target_premium = max(target_premium, entry_premium + 5)  # Minimum ₹5 profit
        
        return stop_loss_premium, target_premium
    
    def _calculate_position_size(
        self,
        premium: float,
        lot_size: int,
        underlying_price: float
    ) -> int:
        """
        Calculate position size based on risk management rules.
        
        Returns:
            Quantity to trade (in units)
        """
        # Get position sizing config
        risk_per_trade_pct = self.mode_config.get('risk_management', {}).get('risk_per_trade_pct', 3.0)
        
        # Assume capital (this should come from account balance)
        # For now, use a placeholder - in production, fetch from API
        total_capital = 100000  # ₹1 Lakh default
        
        # Capital to risk per trade
        capital_at_risk = total_capital * (risk_per_trade_pct / 100)
        
        # Stop-loss percentage
        stop_loss_pct = self.mode_config.get('risk_management', {}).get('stop_loss_pct', 35)
        
        # Calculate maximum loss per lot
        max_loss_per_lot = premium * lot_size * (stop_loss_pct / 100)
        
        # Calculate number of lots
        if max_loss_per_lot > 0:
            lots = int(capital_at_risk / max_loss_per_lot)
        else:
            lots = 1
        
        # Apply max lots limit
        max_lots = self.position_config.get('max_lots_per_trade', 5)
        lots = min(lots, max_lots)
        
        # Ensure at least 1 lot
        lots = max(lots, 1)
        
        # Convert to quantity
        quantity = lots * lot_size
        
        logger.debug(
            f"Position sizing: Capital=₹{total_capital}, Risk={risk_per_trade_pct}%, "
            f"Lots={lots}, Quantity={quantity}"
        )
        
        return quantity
    
    async def _get_option_premium(self, symbol: str) -> Optional[float]:
        """Get current option premium."""
        try:
            # get_quote is synchronous, not async - don't use await
            quote = self.api_client.get_quote(["NFO:" + symbol])
            if quote and symbol in quote:
                return quote[symbol].get('last_price')
            return None
        except Exception as e:
            logger.error(f"Error fetching premium for {symbol}: {e}")
            return None
    
    async def _place_entry_order(
        self,
        option: Dict,
        quantity: int,
        premium: float
    ) -> Optional[str]:
        """Place entry order to buy the option."""
        try:
            order_params = {
                'symbol': option['symbol'],
                'exchange': 'NFO',
                'transaction_type': 'BUY',
                'quantity': quantity,
                'order_type': 'LIMIT',
                'price': premium,
                'product': 'MIS',  # Intraday (change to NRML for carry forward)
                'validity': 'DAY'
            }
            
            # LOGGING ONLY MODE - Just log, don't place order
            if self.logging_only_mode:
                order_id = f"LOG_{uuid.uuid4().hex[:8]}"
                logger.info("="*80)
                logger.info("[LOGGING ONLY MODE] ORDER NOT PLACED")
                logger.info("="*80)
                logger.info(f"Order Details:")
                logger.info(f"   Symbol: {option['symbol']}")
                logger.info(f"   Strike: {option.get('strike', 'N/A')}")
                logger.info(f"   Option Type: {option.get('option_type', 'N/A')}")
                logger.info(f"   Exchange: NFO")
                logger.info(f"   Action: BUY")
                logger.info(f"   Quantity: {quantity} units ({quantity/option.get('lot_size', 25):.1f} lots)")
                logger.info(f"   Order Type: LIMIT")
                logger.info(f"   Price: ₹{premium:.2f}")
                logger.info(f"   Product: MIS (Intraday)")
                logger.info(f"   Total Value: ₹{premium * quantity:.2f}")
                logger.info(f"   Simulated Order ID: {order_id}")
                logger.info("="*80)
                logger.info("To execute real orders, set 'logging_only_mode': false")
                logger.info("="*80)
                self.stats['logging_only_trades'] += 1
                return order_id
            
            # PAPER TRADING MODE - Simulate order
            elif self.paper_trading:
                order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
                logger.info("="*60)
                logger.info(f"📄 Paper Trade Order: BUY {option['symbol']} x {quantity} @ ₹{premium}")
                logger.info(f"   Paper Order ID: {order_id}")
                logger.info("="*60)
                return order_id
            
            # LIVE TRADING MODE - Place real order
            else:
                logger.warning("="*80)
                logger.warning("💰 LIVE TRADING - PLACING REAL ORDER WITH REAL MONEY!")
                logger.warning("="*80)
                order_id = self.api_client.place_order(**order_params)
                logger.info(f"✅ Real order placed: {order_id}")
                logger.info(f"   Symbol: {option['symbol']}")
                logger.info(f"   Quantity: {quantity} units")
                logger.info(f"   Price: ₹{premium}")
                logger.info(f"   Total: ₹{premium * quantity:.2f}")
                logger.warning("="*80)
                return order_id
            
        except Exception as e:
            logger.error(f"Error placing entry order: {e}", exc_info=True)
            return None
    
    def get_statistics(self) -> Dict:
        """Get executor statistics."""
        position_summary = self.position_manager.get_active_positions_summary()
        performance = self.position_manager.get_performance_metrics()
        
        return {
            'mode': self.mode,
            'enabled': self.enabled,
            'executor_stats': self.stats,
            'active_positions': position_summary,
            'performance': performance
        }
    
    async def force_exit_all(self, reason: str = "MANUAL"):
        """Force exit all active positions."""
        logger.warning(f"Force exiting all positions: {reason}")
        
        for position in list(self.position_manager.active_positions.values()):
            try:
                current_premium = await self._get_option_premium(position.symbol)
                if current_premium:
                    await self.position_manager._execute_exit(
                        position, current_premium, reason, position.remaining_quantity
                    )
            except Exception as e:
                logger.error(f"Error force exiting {position.symbol}: {e}")
