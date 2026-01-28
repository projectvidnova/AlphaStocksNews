"""
Intelligent Strike Selection Engine
Selects optimal option strikes based on signal, mode, and market conditions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("strike_selector")


class StrikeSelector:
    """
    Intelligent strike selection based on trading mode and signal strength.
    """
    
    def __init__(self, api_client, mode_config: Dict):
        """
        Initialize strike selector.
        
        Args:
            api_client: Kite API client
            mode_config: Configuration for the selected trading mode
        """
        self.api_client = api_client
        self.mode_config = mode_config
        self.strike_config = mode_config.get('strike_selection', {})
        self.common_filters = {}
    
    def set_common_filters(self, filters: Dict):
        """Set common filtering criteria."""
        self.common_filters = filters
    
    def select_best_strike(
        self,
        underlying_symbol: str,
        current_price: float,
        signal_type: str,
        expected_move_pct: float,
        signal_strength: float = 0.7
    ) -> Optional[Dict]:
        """
        Select the best strike based on mode and signal.
        
        Args:
            underlying_symbol: Symbol like "BANKNIFTY", "NIFTY"
            current_price: Current price of underlying
            signal_type: "BUY" or "SELL"
            expected_move_pct: Expected percentage move from signal
            signal_strength: Signal confidence (0-1)
            
        Returns:
            Dictionary with selected option details or None
        """
        try:
            # Get options chain
            options_chain = self._get_options_chain(underlying_symbol)
            if not options_chain:
                logger.error(f"Could not fetch options chain for {underlying_symbol}")
                return None
            
            # Determine option type
            option_type = "CE" if signal_type == "BUY" else "PE"
            
            # Calculate target strike based on mode
            target_strike = self._calculate_target_strike(
                current_price, expected_move_pct, signal_strength
            )
            
            logger.info(
                f"Strike selection for {underlying_symbol}: {signal_type} signal, "
                f"current={current_price}, target_strike={target_strike}, mode={self.mode_config.get('description', 'N/A')}"
            )
            
            # Filter options by type and criteria
            filtered_options = self._filter_options(
                options_chain, option_type, current_price, target_strike
            )
            
            if not filtered_options:
                logger.warning("No options matched the filtering criteria")
                return None
            
            # Select the best option from filtered list
            best_option = self._rank_and_select_best(
                filtered_options, current_price, expected_move_pct
            )
            
            if best_option:
                logger.info(
                    f"Selected: {best_option['symbol']} (Strike: {best_option['strike']}, "
                    f"Premium: ₹{best_option.get('ltp', 0)}, Delta: {best_option.get('delta', 'N/A')})"
                )
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error selecting strike: {e}", exc_info=True)
            return None
    
    def _calculate_target_strike(
        self,
        current_price: float,
        expected_move_pct: float,
        signal_strength: float
    ) -> float:
        """Calculate target strike based on mode configuration."""
        preference = self.strike_config.get('preference', 'ATM')
        offset_pct = self.strike_config.get('offset_percentage', 0)
        
        # Handle dynamic selection
        if self.strike_config.get('dynamic_selection', False):
            dynamic_rules = self.strike_config.get('dynamic_rules', {})
            
            # Check rules based on expected move
            for rule_key, rule_value in dynamic_rules.items():
                if 'if_expected_move_gt' in rule_key:
                    threshold = float(rule_key.split('_')[-1].replace('pct', ''))
                    if expected_move_pct >= threshold:
                        if 'otm' in rule_value:
                            # Extract percentage from rule like "1pct_otm"
                            otm_pct = float(rule_value.split('pct')[0])
                            offset_pct = otm_pct
                        elif rule_value == 'atm':
                            offset_pct = 0
                
                elif 'if_expected_move_lt' in rule_key:
                    threshold = float(rule_key.split('_')[-1].replace('pct', ''))
                    if expected_move_pct < threshold:
                        offset_pct = 0
        
        # Calculate strike based on preference
        if preference == "ITM":
            # Negative offset for ITM
            target_strike = current_price * (1 - abs(offset_pct) / 100)
        elif preference == "ATM":
            target_strike = current_price
        elif preference == "OTM":
            target_strike = current_price * (1 + abs(offset_pct) / 100)
        elif preference == "ATM_OR_SLIGHT_OTM":
            # Use offset as is (can be 0 for ATM or positive for OTM)
            target_strike = current_price * (1 + offset_pct / 100)
        else:
            target_strike = current_price
        
        return target_strike
    
    def _get_options_chain(self, underlying_symbol: str) -> Optional[List[Dict]]:
        """Fetch options chain from API."""
        try:
            # Get instruments from NFO segment
            instruments = self.api_client.get_instruments("NFO")
            
            # Normalize underlying symbol
            symbol_mapping = {
                "BANKNIFTY": "NIFTY BANK",
                "NIFTY": "NIFTY 50",
                "FINNIFTY": "NIFTY FIN SERVICE"
            }
            
            search_symbol = symbol_mapping.get(underlying_symbol, underlying_symbol)
            
            # Filter options for this underlying
            options = [
                inst for inst in instruments
                if inst.get('name', '').upper() in [underlying_symbol.upper(), search_symbol.upper()]
                and inst.get('instrument_type') in ['CE', 'PE']
            ]
            
            logger.info(f"Found {len(options)} options for {underlying_symbol}")
            return options
            
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return None
    
    def _filter_options(
        self,
        options_chain: List[Dict],
        option_type: str,
        current_price: float,
        target_strike: float
    ) -> List[Dict]:
        """Filter options based on criteria."""
        filtered = []
        
        # Get filter thresholds
        min_oi = self.common_filters.get('min_open_interest', 100)
        min_volume = self.common_filters.get('min_volume', 50)
        min_premium = self.common_filters.get('min_premium', 10)
        max_premium = self.common_filters.get('max_premium', 300)
        min_days_to_expiry = self.common_filters.get('min_days_to_expiry', 2)
        max_days_to_expiry = self.common_filters.get('max_days_to_expiry', 30)
        
        today = get_current_time().date()
        
        for option in options_chain:
            # Filter by option type
            if option.get('instrument_type') != option_type:
                continue
            
            strike = option.get('strike', 0)
            expiry = option.get('expiry')
            
            # Filter by expiry
            if expiry:
                if isinstance(expiry, str):
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                else:
                    expiry_date = expiry
                
                days_to_expiry = (expiry_date - today).days
                
                if days_to_expiry < min_days_to_expiry or days_to_expiry > max_days_to_expiry:
                    continue
            else:
                days_to_expiry = 7  # Default assumption
            
            # Filter by strike range (within reasonable range of target)
            strike_diff_pct = abs(strike - target_strike) / current_price * 100
            
            # Allow strikes within 5% of target strike
            if strike_diff_pct > 5:
                continue
            
            # Add calculated fields
            option['days_to_expiry'] = days_to_expiry
            option['strike_diff_from_target'] = abs(strike - target_strike)
            option['moneyness_pct'] = (strike - current_price) / current_price * 100
            
            # Estimate delta based on moneyness (simplified)
            option['estimated_delta'] = self._estimate_delta(
                current_price, strike, option_type, days_to_expiry
            )
            
            filtered.append(option)
        
        logger.info(f"Filtered to {len(filtered)} options matching criteria")
        return filtered
    
    def _estimate_delta(
        self,
        current_price: float,
        strike: float,
        option_type: str,
        days_to_expiry: int
    ) -> float:
        """Estimate delta based on moneyness (simplified approximation)."""
        moneyness_pct = (strike - current_price) / current_price * 100
        
        if option_type == "CE":
            # For calls
            if moneyness_pct < -2:  # Deep ITM
                return 0.70
            elif moneyness_pct < -0.5:  # ITM
                return 0.60
            elif abs(moneyness_pct) <= 0.5:  # ATM
                return 0.50
            elif moneyness_pct <= 1.5:  # Slight OTM
                return 0.40
            elif moneyness_pct <= 3:  # OTM
                return 0.30
            else:  # Far OTM
                return 0.20
        else:
            # For puts (negative delta)
            if moneyness_pct > 2:  # Deep ITM
                return 0.70
            elif moneyness_pct > 0.5:  # ITM
                return 0.60
            elif abs(moneyness_pct) <= 0.5:  # ATM
                return 0.50
            elif moneyness_pct >= -1.5:  # Slight OTM
                return 0.40
            elif moneyness_pct >= -3:  # OTM
                return 0.30
            else:  # Far OTM
                return 0.20
    
    def _rank_and_select_best(
        self,
        options: List[Dict],
        current_price: float,
        expected_move_pct: float
    ) -> Optional[Dict]:
        """Rank options and select the best one."""
        if not options:
            return None
        
        # Score each option
        for option in options:
            score = 0
            
            # Factor 1: Proximity to target strike (40% weight)
            strike_diff = option['strike_diff_from_target']
            max_diff = current_price * 0.05  # 5% range
            proximity_score = (1 - min(strike_diff / max_diff, 1)) * 40
            score += proximity_score
            
            # Factor 2: Delta appropriateness (30% weight)
            min_delta = self.strike_config.get('min_delta', 0.35)
            delta = option.get('estimated_delta', 0.5)
            if delta >= min_delta:
                delta_score = min(delta / 0.60, 1) * 30  # Normalize to 0.6 as optimal
            else:
                delta_score = 0
            score += delta_score
            
            # Factor 3: Days to expiry (20% weight)
            days = option['days_to_expiry']
            optimal_days = 7  # Weekly options preferred
            days_score = (1 - min(abs(days - optimal_days) / optimal_days, 1)) * 20
            score += days_score
            
            # Factor 4: Strike interval (10% weight)
            # Prefer standard strikes (multiples of 100 for Bank Nifty, 50 for Nifty)
            strike = option['strike']
            strike_interval = 100 if current_price > 30000 else 50
            if strike % strike_interval == 0:
                score += 10
            
            option['selection_score'] = score
        
        # Sort by score and return the best
        options.sort(key=lambda x: x.get('selection_score', 0), reverse=True)
        best = options[0]
        
        # Format the response
        return {
            'symbol': best.get('tradingsymbol', ''),
            'instrument_token': best.get('instrument_token'),
            'strike': best.get('strike'),
            'option_type': best.get('instrument_type'),
            'expiry': best.get('expiry'),
            'lot_size': best.get('lot_size', 1),
            'days_to_expiry': best.get('days_to_expiry'),
            'delta': best.get('estimated_delta'),
            'moneyness_pct': best.get('moneyness_pct'),
            'score': best.get('selection_score'),
            'exchange': 'NFO'
        }
