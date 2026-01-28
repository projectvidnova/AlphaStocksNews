"""
Options Greeks Calculator
Calculates Delta, Gamma, Theta, Vega for options pricing and risk management.
"""

import math
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from scipy.stats import norm


class OptionsGreeksCalculator:
    """
    Calculate Black-Scholes Greeks for options.
    
    Greeks:
    - Delta: Rate of change of option price with underlying price
    - Gamma: Rate of change of delta with underlying price
    - Theta: Rate of change of option price with time (time decay)
    - Vega: Rate of change of option price with volatility
    - Rho: Rate of change of option price with interest rate
    """
    
    def __init__(self, risk_free_rate: float = 0.06):
        """
        Initialize Greeks calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 6% for India)
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_all_greeks(
        self,
        underlying_price: float,
        strike_price: float,
        time_to_expiry_days: int,
        volatility: float,
        option_type: str = "CE"
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option.
        
        Args:
            underlying_price: Current price of underlying asset
            strike_price: Strike price of option
            time_to_expiry_days: Days until expiry
            volatility: Implied volatility (as decimal, e.g., 0.20 for 20%)
            option_type: "CE" for Call or "PE" for Put
            
        Returns:
            Dictionary with all Greeks
        """
        # Convert days to years
        time_to_expiry = time_to_expiry_days / 365.0
        
        # Prevent divide by zero for expired options
        if time_to_expiry <= 0:
            return {
                'delta': 1.0 if option_type == "CE" else -1.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0,
                'intrinsic_value': max(0, underlying_price - strike_price) if option_type == "CE" 
                                   else max(0, strike_price - underlying_price),
                'time_value': 0.0
            }
        
        # Calculate d1 and d2 for Black-Scholes
        d1 = self._calculate_d1(
            underlying_price, strike_price, time_to_expiry, volatility
        )
        d2 = self._calculate_d2(d1, volatility, time_to_expiry)
        
        # Calculate Greeks
        greeks = {}
        
        if option_type == "CE":
            greeks['delta'] = self._calculate_call_delta(d1)
            greeks['gamma'] = self._calculate_gamma(underlying_price, d1, volatility, time_to_expiry)
            greeks['theta'] = self._calculate_call_theta(
                underlying_price, strike_price, d1, d2, volatility, time_to_expiry
            )
            greeks['vega'] = self._calculate_vega(underlying_price, d1, time_to_expiry)
            greeks['rho'] = self._calculate_call_rho(strike_price, d2, time_to_expiry)
            greeks['intrinsic_value'] = max(0, underlying_price - strike_price)
        else:  # PE
            greeks['delta'] = self._calculate_put_delta(d1)
            greeks['gamma'] = self._calculate_gamma(underlying_price, d1, volatility, time_to_expiry)
            greeks['theta'] = self._calculate_put_theta(
                underlying_price, strike_price, d1, d2, volatility, time_to_expiry
            )
            greeks['vega'] = self._calculate_vega(underlying_price, d1, time_to_expiry)
            greeks['rho'] = self._calculate_put_rho(strike_price, d2, time_to_expiry)
            greeks['intrinsic_value'] = max(0, strike_price - underlying_price)
        
        # Calculate theoretical premium using Black-Scholes
        greeks['theoretical_premium'] = self._calculate_black_scholes_price(
            underlying_price, strike_price, time_to_expiry, volatility, option_type
        )
        
        greeks['time_value'] = greeks['theoretical_premium'] - greeks['intrinsic_value']
        
        return greeks
    
    def _calculate_d1(
        self,
        underlying_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float
    ) -> float:
        """Calculate d1 for Black-Scholes formula."""
        return (
            (math.log(underlying_price / strike_price) + 
             (self.risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) /
            (volatility * math.sqrt(time_to_expiry))
        )
    
    def _calculate_d2(self, d1: float, volatility: float, time_to_expiry: float) -> float:
        """Calculate d2 for Black-Scholes formula."""
        return d1 - volatility * math.sqrt(time_to_expiry)
    
    def _calculate_call_delta(self, d1: float) -> float:
        """Calculate delta for call option."""
        return norm.cdf(d1)
    
    def _calculate_put_delta(self, d1: float) -> float:
        """Calculate delta for put option."""
        return norm.cdf(d1) - 1
    
    def _calculate_gamma(
        self,
        underlying_price: float,
        d1: float,
        volatility: float,
        time_to_expiry: float
    ) -> float:
        """Calculate gamma (same for calls and puts)."""
        return (
            norm.pdf(d1) / 
            (underlying_price * volatility * math.sqrt(time_to_expiry))
        )
    
    def _calculate_call_theta(
        self,
        underlying_price: float,
        strike_price: float,
        d1: float,
        d2: float,
        volatility: float,
        time_to_expiry: float
    ) -> float:
        """Calculate theta for call option (per day)."""
        theta_annual = (
            -(underlying_price * norm.pdf(d1) * volatility) / (2 * math.sqrt(time_to_expiry)) -
            self.risk_free_rate * strike_price * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2)
        )
        # Convert to per-day theta
        return theta_annual / 365.0
    
    def _calculate_put_theta(
        self,
        underlying_price: float,
        strike_price: float,
        d1: float,
        d2: float,
        volatility: float,
        time_to_expiry: float
    ) -> float:
        """Calculate theta for put option (per day)."""
        theta_annual = (
            -(underlying_price * norm.pdf(d1) * volatility) / (2 * math.sqrt(time_to_expiry)) +
            self.risk_free_rate * strike_price * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2)
        )
        # Convert to per-day theta
        return theta_annual / 365.0
    
    def _calculate_vega(
        self,
        underlying_price: float,
        d1: float,
        time_to_expiry: float
    ) -> float:
        """Calculate vega (same for calls and puts)."""
        return underlying_price * norm.pdf(d1) * math.sqrt(time_to_expiry) / 100
    
    def _calculate_call_rho(
        self,
        strike_price: float,
        d2: float,
        time_to_expiry: float
    ) -> float:
        """Calculate rho for call option."""
        return (
            strike_price * time_to_expiry * 
            math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        )
    
    def _calculate_put_rho(
        self,
        strike_price: float,
        d2: float,
        time_to_expiry: float
    ) -> float:
        """Calculate rho for put option."""
        return (
            -strike_price * time_to_expiry * 
            math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
        )
    
    def _calculate_black_scholes_price(
        self,
        underlying_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str
    ) -> float:
        """Calculate theoretical option price using Black-Scholes."""
        d1 = self._calculate_d1(underlying_price, strike_price, time_to_expiry, volatility)
        d2 = self._calculate_d2(d1, volatility, time_to_expiry)
        
        if option_type == "CE":
            price = (
                underlying_price * norm.cdf(d1) -
                strike_price * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2)
            )
        else:  # PE
            price = (
                strike_price * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) -
                underlying_price * norm.cdf(-d1)
            )
        
        return price
    
    def estimate_option_move(
        self,
        current_premium: float,
        underlying_move: float,
        delta: float,
        gamma: float,
        theta: float,
        time_days: float = 1.0
    ) -> Dict[str, float]:
        """
        Estimate option premium after underlying moves.
        
        Args:
            current_premium: Current option premium
            underlying_move: Expected move in underlying (e.g., 100 for ₹100 move)
            delta: Current delta
            gamma: Current gamma
            theta: Daily theta decay
            time_days: Days for the move to happen
            
        Returns:
            Dictionary with estimated premium and P&L
        """
        # Delta effect: First-order price change
        delta_effect = delta * underlying_move
        
        # Gamma effect: Second-order price change
        gamma_effect = 0.5 * gamma * (underlying_move ** 2)
        
        # Theta effect: Time decay
        theta_effect = theta * time_days
        
        # Total estimated premium change
        total_change = delta_effect + gamma_effect + theta_effect
        
        # New estimated premium
        new_premium = max(0, current_premium + total_change)
        
        return {
            'current_premium': current_premium,
            'estimated_premium': new_premium,
            'delta_contribution': delta_effect,
            'gamma_contribution': gamma_effect,
            'theta_contribution': theta_effect,
            'total_change': total_change,
            'percentage_change': (total_change / current_premium * 100) if current_premium > 0 else 0
        }
    
    def calculate_probability_of_profit(
        self,
        underlying_price: float,
        strike_price: float,
        option_type: str,
        premium_paid: float,
        time_to_expiry_days: int,
        volatility: float
    ) -> float:
        """
        Calculate probability that option will be profitable at expiry.
        
        Returns:
            Probability as percentage (0-100)
        """
        # Calculate breakeven price
        if option_type == "CE":
            breakeven = strike_price + premium_paid
            # Probability that underlying > breakeven
            d2 = self._calculate_d2(
                self._calculate_d1(underlying_price, breakeven, time_to_expiry_days / 365.0, volatility),
                volatility,
                time_to_expiry_days / 365.0
            )
            prob = norm.cdf(d2) * 100
        else:  # PE
            breakeven = strike_price - premium_paid
            # Probability that underlying < breakeven
            d2 = self._calculate_d2(
                self._calculate_d1(underlying_price, breakeven, time_to_expiry_days / 365.0, volatility),
                volatility,
                time_to_expiry_days / 365.0
            )
            prob = norm.cdf(-d2) * 100
        
        return prob
    
    def get_moneyness(self, underlying_price: float, strike_price: float, option_type: str) -> str:
        """
        Determine if option is ITM, ATM, or OTM.
        
        Returns:
            "ITM", "ATM", or "OTM"
        """
        percentage_diff = abs((strike_price - underlying_price) / underlying_price * 100)
        
        if percentage_diff < 0.5:
            return "ATM"
        
        if option_type == "CE":
            return "ITM" if strike_price < underlying_price else "OTM"
        else:  # PE
            return "ITM" if strike_price > underlying_price else "OTM"
