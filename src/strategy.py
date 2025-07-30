import numpy as np
import pandas as pd
from datetime import datetime
from src import config

class CRTStrategy:
    def __init__(self):
        self.current_crt_high = None
        self.current_crt_low = None
        self.current_crt_mid = None
        self.current_hour = None
        self.signals = []
        
    def detect_signals(self, hourly_candle, five_min_candles):
        """
        Detect CRT trading signals based on 1H and 5min candles
        
        Parameters:
        hourly_candle (pd.Series): Current 1-hour candle data
        five_min_candles (pd.DataFrame): 5-minute candles within the current hour
        
        Returns:
        list: Trading signals detected
        """
        # Update CRT range from the hourly candle
        self._update_crt_range(hourly_candle)
        
        # Check for signals in the 5-minute candles
        detected_signals = []
        
        for idx, candle in five_min_candles.iterrows():
            # Skip if we don't have a CRT range yet
            if self.current_crt_high is None or self.current_crt_low is None:
                continue
            
            signal = self._check_candle_for_signal(idx, candle)
            if signal:
                detected_signals.append(signal)
                
        return detected_signals
    
    def _update_crt_range(self, hourly_candle):
        """Update the CRT range based on new hourly candle"""
        candle_hour = hourly_candle.name.hour
        
        # If this is a new hour, update the CRT range
        if self.current_hour != candle_hour:
            self.current_crt_high = hourly_candle['high']
            self.current_crt_low = hourly_candle['low']
            self.current_crt_mid = (self.current_crt_high + self.current_crt_low) / 2
            self.current_hour = candle_hour
            
            print(f"New CRT Range at {hourly_candle.name}: High={self.current_crt_high:.2f}, Low={self.current_crt_low:.2f}")
    
    def _check_candle_for_signal(self, timestamp, candle):
        """Check if a 5-minute candle generates a CRT signal"""
        # Ensure we have CRT levels
        if not all([self.current_crt_high, self.current_crt_low, self.current_crt_mid]):
            return None
            
        # Sweep high: High above CRT high but close back inside
        sweep_high = (candle['high'] > self.current_crt_high) and (candle['close'] < self.current_crt_high)
        
        # Sweep low: Low below CRT low but close back inside
        sweep_low = (candle['low'] < self.current_crt_low) and (candle['close'] > self.current_crt_low)
        
        # Generate signal
        if sweep_high and candle['close'] < self.current_crt_high:
            return self._create_signal(timestamp, 'SHORT', candle)
            
        elif sweep_low and candle['close'] > self.current_crt_low:
            return self._create_signal(timestamp, 'LONG', candle)
            
        return None
    
    def _create_signal(self, timestamp, direction, candle):
        """Create a trading signal with entry, stop loss and take profit levels"""
        if direction == 'LONG':
            # For long: Enter at close, SL below the wick, TP at mid and high
            entry_price = candle['close']
            stop_loss = candle['low'] - (candle['close'] - candle['low']) * 0.1  # Just below the wick
            tp1 = self.current_crt_mid
            tp2 = self.current_crt_high
        else:
            # For short: Enter at close, SL above the wick, TP at mid and low
            entry_price = candle['close']
            stop_loss = candle['high'] + (candle['high'] - candle['close']) * 0.1  # Just above the wick
            tp1 = self.current_crt_mid
            tp2 = self.current_crt_low
            
        # Calculate risk-reward metrics
        risk = abs(entry_price - stop_loss)
        reward1 = abs(entry_price - tp1)
        reward2 = abs(entry_price - tp2)
        
        # RR calculations
        rr1 = reward1 / risk if risk > 0 else 0
        rr2 = reward2 / risk if risk > 0 else 0
        
        signal = {
            'timestamp': timestamp,
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'risk': risk,
            'rr1': rr1,
            'rr2': rr2,
            'crt_high': self.current_crt_high,
            'crt_low': self.current_crt_low
        }
        
        self.signals.append(signal)
        return signal
    
    def get_order_block(self, data_1h, timestamp, direction):
        """Identify the last order block for trade confirmation"""
        # Get hourly data up to the signal timestamp
        historical_data = data_1h.loc[:timestamp]
        
        if len(historical_data) < 5:  # Need enough history
            return None
        
        # Look for the most recent engulfing candle in the last 10 bars
        recent_data = historical_data.iloc[-10:]
        
        for i in range(len(recent_data)-1, -1, -1):
            candle = recent_data.iloc[i]
            
            if candle['is_engulfing']:
                # For long, look for bearish engulfing (red candle)
                if direction == 'LONG' and candle['close'] < candle['open']:
                    return {
                        'timestamp': recent_data.index[i],
                        'high': candle['high'],
                        'low': candle['low'],
                        'open': candle['open'],
                        'close': candle['close']
                    }
                # For short, look for bullish engulfing (green candle)
                elif direction == 'SHORT' and candle['close'] > candle['open']:
                    return {
                        'timestamp': recent_data.index[i],
                        'high': candle['high'],
                        'low': candle['low'],
                        'open': candle['open'],
                        'close': candle['close']
                    }
        
        return None