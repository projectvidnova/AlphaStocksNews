"""
Options Position Manager
Manages active options positions with stop-loss, target, and trailing mechanisms.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("options_position_manager")


class OptionsPosition:
    """Represents a single options position."""
    
    def __init__(
        self,
        position_id: str,
        symbol: str,
        option_type: str,
        strike: float,
        entry_premium: float,
        quantity: int,
        lot_size: int,
        stop_loss_premium: float,
        target_premium: float,
        mode: str,
        signal_id: str,
        underlying_symbol: str,
        underlying_entry_price: float
    ):
        self.position_id = position_id
        self.symbol = symbol
        self.option_type = option_type
        self.strike = strike
        self.entry_premium = entry_premium
        self.quantity = quantity
        self.lot_size = lot_size
        self.stop_loss_premium = stop_loss_premium
        self.target_premium = target_premium
        self.mode = mode
        self.signal_id = signal_id
        self.underlying_symbol = underlying_symbol
        self.underlying_entry_price = underlying_entry_price
        
        # Position state
        self.status = "ACTIVE"  # ACTIVE, PARTIAL, CLOSED
        self.entry_time = get_current_time()
        self.exit_time = None
        self.exit_premium = None
        self.exit_reason = None
        
        # P&L tracking
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.peak_profit = 0.0
        
        # Trailing stop-loss
        self.original_stop_loss = stop_loss_premium
        self.trail_activated = False
        
        # Partial booking tracking
        self.remaining_quantity = quantity
        self.partial_exits = []
    
    def update_pnl(self, current_premium: float):
        """Update unrealized P&L."""
        pnl_per_lot = (current_premium - self.entry_premium) * self.lot_size
        self.unrealized_pnl = pnl_per_lot * (self.remaining_quantity / self.lot_size)
        
        # Track peak profit for trailing
        if self.unrealized_pnl > self.peak_profit:
            self.peak_profit = self.unrealized_pnl
    
    def get_total_pnl(self) -> float:
        """Get total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    def get_percentage_pnl(self, current_premium: float) -> float:
        """Get percentage P&L."""
        if self.entry_premium == 0:
            return 0.0
        return ((current_premium - self.entry_premium) / self.entry_premium) * 100
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'option_type': self.option_type,
            'strike': self.strike,
            'entry_premium': self.entry_premium,
            'quantity': self.quantity,
            'remaining_quantity': self.remaining_quantity,
            'lot_size': self.lot_size,
            'stop_loss_premium': self.stop_loss_premium,
            'target_premium': self.target_premium,
            'mode': self.mode,
            'signal_id': self.signal_id,
            'underlying_symbol': self.underlying_symbol,
            'status': self.status,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_premium': self.exit_premium,
            'exit_reason': self.exit_reason,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': self.get_total_pnl(),
            'trail_activated': self.trail_activated
        }


class OptionsPositionManager:
    """
    Manages all active options positions with stop-loss, target, and trailing.
    
    THREAD SAFETY: Lock-free design using:
    - Each position monitored independently
    - Database as single source of truth for position state
    - Read-only access to active_positions dict (rebuilt periodically)
    - Position updates isolated per position
    - Accept eventual consistency for non-critical data
    """
    
    def __init__(self, api_client, mode_config: Dict, data_layer=None, 
                 paper_trading=True, logging_only_mode=False):
        """
        Initialize position manager.
        
        Args:
            api_client: Kite API client for price updates and order placement
            mode_config: Configuration for the trading mode
            data_layer: Data layer for persistence
            paper_trading: If True, simulate orders
            logging_only_mode: If True, only log orders (don't execute)
        """
        self.api_client = api_client
        self.mode_config = mode_config
        self.data_layer = data_layer
        self.paper_trading = paper_trading
        self.logging_only_mode = logging_only_mode
        
        self.active_positions: Dict[str, OptionsPosition] = {}
        self.closed_positions: List[OptionsPosition] = []
        
        # Configuration
        self.risk_config = mode_config.get('risk_management', {})
        self.exit_config = mode_config.get('exit_rules', {})
        
        # Monitoring
        self.monitoring_task = None
        self.monitoring_interval = 5  # seconds
    
    def add_position(self, position: OptionsPosition):
        """Add a new position to manage."""
        self.active_positions[position.position_id] = position
        logger.info(
            f"Added position: {position.symbol} @ ₹{position.entry_premium}, "
            f"SL: ₹{position.stop_loss_premium}, Target: ₹{position.target_premium}"
        )
    
    async def start_monitoring(self):
        """Start monitoring all active positions."""
        if self.monitoring_task is None:
            self.monitoring_task = asyncio.create_task(self._monitor_positions())
            logger.info("Started position monitoring")
    
    async def stop_monitoring(self):
        """Stop monitoring positions."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
            logger.info("Stopped position monitoring")
    
    async def _monitor_positions(self):
        """Continuously monitor all active positions."""
        while True:
            try:
                if self.active_positions:
                    await self._check_all_positions()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)
    
    async def _check_all_positions(self):
        """Check all active positions for exit conditions."""
        positions_to_check = list(self.active_positions.values())
        
        for position in positions_to_check:
            try:
                await self._check_position(position)
            except Exception as e:
                logger.error(f"Error checking position {position.position_id}: {e}")
    
    async def _check_position(self, position: OptionsPosition):
        """Check a single position for exit conditions."""
        # Get current premium
        current_premium = await self._get_current_premium(position.symbol)
        if current_premium is None:
            logger.warning(f"Could not fetch premium for {position.symbol}")
            return
        
        # Update P&L
        position.update_pnl(current_premium)
        
        # Calculate percentage P&L
        pnl_pct = position.get_percentage_pnl(current_premium)
        
        logger.debug(
            f"Position {position.symbol}: Premium=₹{current_premium:.2f}, "
            f"P&L={pnl_pct:.2f}%, SL=₹{position.stop_loss_premium:.2f}, "
            f"Target=₹{position.target_premium:.2f}"
        )
        
        # Check exit conditions
        exit_reason = None
        exit_quantity = position.remaining_quantity
        
        # 1. Check stop-loss
        if current_premium <= position.stop_loss_premium:
            exit_reason = "STOP_LOSS"
            logger.warning(
                f"Stop-loss hit for {position.symbol}: "
                f"Current ₹{current_premium} <= SL ₹{position.stop_loss_premium}"
            )
        
        # 2. Check target
        elif current_premium >= position.target_premium:
            exit_reason = "TARGET"
            logger.info(
                f"Target reached for {position.symbol}: "
                f"Current ₹{current_premium} >= Target ₹{position.target_premium}"
            )
        
        # 3. Check partial booking
        elif self._should_partial_book(position, pnl_pct):
            partial_pct = self.exit_config.get('partial_size_pct', 50)
            exit_quantity = int(position.remaining_quantity * partial_pct / 100)
            exit_reason = "PARTIAL_BOOKING"
            logger.info(
                f"Partial booking for {position.symbol}: "
                f"Booking {exit_quantity}/{position.remaining_quantity} units at {pnl_pct:.2f}% profit"
            )
        
        # 4. Check trailing stop-loss
        elif self._should_activate_trail(position, pnl_pct):
            new_stop_loss = self._calculate_trailing_stop(position, current_premium)
            if new_stop_loss > position.stop_loss_premium:
                logger.info(
                    f"Trailing stop-loss for {position.symbol}: "
                    f"₹{position.stop_loss_premium} -> ₹{new_stop_loss}"
                )
                position.stop_loss_premium = new_stop_loss
                position.trail_activated = True
        
        # 5. Check time-based exit
        elif self._should_time_exit(position):
            exit_reason = "TIME_LIMIT"
            logger.info(f"Time limit reached for {position.symbol}")
        
        # Execute exit if needed
        if exit_reason:
            await self._execute_exit(position, current_premium, exit_reason, exit_quantity)
    
    def _should_partial_book(self, position: OptionsPosition, pnl_pct: float) -> bool:
        """Check if partial booking should be done."""
        # Only if enabled and position is fully active
        if not self.exit_config.get('partial_booking', False):
            return False
        
        if position.status != "ACTIVE":
            return False
        
        # Check if profit threshold reached
        partial_threshold = self.exit_config.get('partial_booking_at_pct', 50)
        return pnl_pct >= partial_threshold
    
    def _should_activate_trail(self, position: OptionsPosition, pnl_pct: float) -> bool:
        """Check if trailing stop-loss should be activated."""
        if not self.exit_config.get('trail_stop', False):
            return False
        
        trail_threshold = self.exit_config.get('trail_after_profit_pct', 30)
        return pnl_pct >= trail_threshold
    
    def _calculate_trailing_stop(self, position: OptionsPosition, current_premium: float) -> float:
        """Calculate new trailing stop-loss."""
        trail_pct = self.exit_config.get('trail_percentage', 50)
        
        # Trail at X% of profit from entry
        profit = current_premium - position.entry_premium
        trailed_stop = position.entry_premium + (profit * (100 - trail_pct) / 100)
        
        return max(trailed_stop, position.stop_loss_premium)
    
    def _should_time_exit(self, position: OptionsPosition) -> bool:
        """Check if position should be exited based on time."""
        max_hold_hours = self.exit_config.get('max_hold_hours', 6)
        hold_time = (get_current_time() - position.entry_time).total_seconds() / 3600
        
        return hold_time >= max_hold_hours
    
    async def _get_current_premium(self, symbol: str) -> Optional[float]:
        """Get current option premium from API."""
        try:
            # Fetch LTP for the option
            # get_quote is synchronous, not async - don't use await
            quote = self.api_client.get_quote(["NFO:" + symbol])
            if quote and symbol in quote:
                return quote[symbol].get('last_price', None)
            return None
        except Exception as e:
            logger.error(f"Error fetching premium for {symbol}: {e}")
            return None
    
    async def _execute_exit(
        self,
        position: OptionsPosition,
        exit_premium: float,
        exit_reason: str,
        quantity: int
    ):
        """Execute exit order for position."""
        try:
            logger.info(
                f"Executing exit for {position.symbol}: {quantity} units @ ₹{exit_premium}, "
                f"Reason: {exit_reason}"
            )
            
            # Place exit order (SELL for long options)
            order_id = await self._place_exit_order(
                position.symbol, quantity, exit_premium
            )
            
            if order_id:
                # Update position
                pnl_per_lot = (exit_premium - position.entry_premium) * position.lot_size
                pnl = pnl_per_lot * (quantity / position.lot_size)
                
                position.realized_pnl += pnl
                position.remaining_quantity -= quantity
                
                # Record partial exit
                position.partial_exits.append({
                    'quantity': quantity,
                    'premium': exit_premium,
                    'pnl': pnl,
                    'reason': exit_reason,
                    'time': get_current_time()
                })
                
                # Update status
                if position.remaining_quantity == 0:
                    position.status = "CLOSED"
                    position.exit_time = get_current_time()
                    position.exit_premium = exit_premium
                    position.exit_reason = exit_reason
                    
                    # Move to closed positions
                    self.closed_positions.append(position)
                    del self.active_positions[position.position_id]
                    
                    logger.info(
                        f"Position closed: {position.symbol}, "
                        f"Total P&L: ₹{position.realized_pnl:.2f} "
                        f"({position.get_percentage_pnl(exit_premium):.2f}%)"
                    )
                else:
                    position.status = "PARTIAL"
                    logger.info(
                        f"Partial exit completed: {quantity} units closed, "
                        f"{position.remaining_quantity} remaining"
                    )
                
                # Save to data layer
                if self.data_layer:
                    await self._save_position(position)
            
        except Exception as e:
            logger.error(f"Error executing exit for {position.symbol}: {e}", exc_info=True)
    
    async def _place_exit_order(
        self,
        symbol: str,
        quantity: int,
        premium: float
    ) -> Optional[str]:
        """Place exit order via API."""
        try:
            import uuid
            
            order_params = {
                'symbol': symbol,
                'exchange': 'NFO',
                'transaction_type': 'SELL',
                'quantity': quantity,
                'order_type': 'LIMIT',
                'price': premium,
                'product': 'MIS',  # Intraday
                'validity': 'DAY'
            }
            
            # LOGGING ONLY MODE - Just log, don't execute
            if self.logging_only_mode:
                order_id = f"EXIT_LOG_{uuid.uuid4().hex[:8]}"
                logger.info("="*80)
                logger.info("[LOGGING ONLY MODE] EXIT ORDER NOT PLACED")
                logger.info("="*80)
                logger.info(f"Exit Order Details:")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Exchange: NFO")
                logger.info(f"   Action: SELL")
                logger.info(f"   Quantity: {quantity}")
                logger.info(f"   Order Type: LIMIT")
                logger.info(f"   Price: ₹{premium:.2f}")
                logger.info(f"   Total Value: ₹{premium * quantity:.2f}")
                logger.info(f"   Simulated Order ID: {order_id}")
                logger.info("="*80)
                return order_id
            
            # PAPER TRADING MODE - Simulate order
            elif self.paper_trading:
                order_id = f"EXIT_PAPER_{uuid.uuid4().hex[:8]}"
                logger.info("="*60)
                logger.info(f"📄 Paper Exit Order: SELL {symbol} x {quantity} @ ₹{premium}")
                logger.info(f"   Paper Order ID: {order_id}")
                logger.info("="*60)
                return order_id
            
            # LIVE TRADING MODE - Place real order
            else:
                logger.warning("="*80)
                logger.warning("💰 LIVE EXIT ORDER - SELLING WITH REAL MONEY!")
                logger.warning("="*80)
                order_id = self.api_client.place_order(**order_params)
                logger.info(f"✅ Real exit order placed: {order_id}")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Quantity: {quantity}")
                logger.info(f"   Price: ₹{premium}")
                logger.warning("="*80)
                return order_id
            
            logger.info("="*60)
            logger.info(f"🚪 EXIT ORDER:")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Action: SELL")
            logger.info(f"   Quantity: {quantity} units")
            logger.info(f"   Price: ₹{premium:.2f}")
            logger.info(f"   Total: ₹{premium * quantity:.2f}")
            logger.info(f"   Order ID: {order_id}")
            logger.info("="*60)
            
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing exit order: {e}")
            return None
    
    async def _save_position(self, position: OptionsPosition):
        """Save position to data layer."""
        try:
            if self.data_layer:
                await self.data_layer.store_options_position(position.to_dict())
        except Exception as e:
            logger.error(f"Error saving position: {e}")
    
    def get_active_positions_summary(self) -> Dict:
        """Get summary of all active positions."""
        if not self.active_positions:
            return {'count': 0, 'total_pnl': 0.0, 'positions': []}
        
        total_pnl = sum(pos.get_total_pnl() for pos in self.active_positions.values())
        positions = [pos.to_dict() for pos in self.active_positions.values()]
        
        return {
            'count': len(self.active_positions),
            'total_pnl': total_pnl,
            'positions': positions
        }
    
    def get_position_by_signal(self, signal_id: str) -> Optional[OptionsPosition]:
        """
        Get position by signal ID (for idempotency checking).
        
        Lock-free read from active_positions dict.
        Eventual consistency is acceptable here.
        
        Args:
            signal_id: Signal UUID
            
        Returns:
            OptionsPosition if exists, None otherwise
        """
        # Check active positions
        for position in self.active_positions.values():
            if position.signal_id == signal_id:
                return position
        
        # Check closed positions (also check history)
        for position in self.closed_positions:
            if position.signal_id == signal_id:
                return position
        
        return None
    
    def get_performance_metrics(self) -> Dict:
        """Calculate performance metrics from closed positions (lock-free)."""
        if not self.closed_positions:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'total_pnl': 0.0
            }
        
        total_trades = len(self.closed_positions)
        winning_trades = [pos for pos in self.closed_positions if pos.realized_pnl > 0]
        losing_trades = [pos for pos in self.closed_positions if pos.realized_pnl < 0]
        
        win_rate = len(winning_trades) / total_trades * 100
        avg_win = sum(pos.realized_pnl for pos in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(pos.realized_pnl for pos in losing_trades) / len(losing_trades) if losing_trades else 0
        
        total_wins = sum(pos.realized_pnl for pos in winning_trades)
        total_losses = abs(sum(pos.realized_pnl for pos in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        total_pnl = sum(pos.realized_pnl for pos in self.closed_positions)
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl
        }
