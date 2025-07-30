import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from src import config
from src.mt5_connector import MT5Connector

class DataHandler:
    def __init__(self, csv_path=None, use_mt5=False):
        self.csv_path = csv_path or config.DATA_FILE
        self.raw_data = None
        self.data_1h = None
        self.data_5m = None
        self.use_mt5 = use_mt5
        self.mt5_connector = None
        self.logger = logging.getLogger("crt_trading.data_handler")
        
        # Initialize MT5 connector if needed
        if self.use_mt5:
            self.logger.info("Initializing MT5 connector for live data")
            self.mt5_connector = MT5Connector(
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER
            )
        
    def load_data(self):
        """Load OHLCV data from CSV file or MT5"""
        if self.use_mt5 and self.mt5_connector:
            print(f"Loading live data from MT5 for {config.MT5_SYMBOL}")
            
            # Connect to MT5
            if not self.mt5_connector.connect():
                print("Failed to connect to MT5. Falling back to CSV data.")
                self.use_mt5 = False
            else:
                # Get account info to verify connection
                account_info = self.mt5_connector.get_account_info()
                print(f"Connected to MT5: {account_info['server']}, Account: {account_info['login']}")
                
                # Get OHLCV data for 1H and 5M timeframes
                # For initial data load, get enough data for strategy setup (500 bars)
                self.raw_data = self.mt5_connector.get_ohlcv_data(
                    symbol=config.MT5_SYMBOL,
                    timeframe="5m",
                    count=1000  # Get enough data for resampling
                )
                
                if self.raw_data is None or self.raw_data.empty:
                    print(f"Failed to get MT5 data for {config.MT5_SYMBOL}. Falling back to CSV data.")
                    self.use_mt5 = False
                else:
                    print(f"Loaded {len(self.raw_data)} rows of live MT5 data")
                    return self.raw_data
                
        # Fallback to CSV data if MT5 is not used or failed
        if not self.use_mt5:
            print(f"Loading data from {self.csv_path}")
            self.raw_data = pd.read_csv(self.csv_path)
            
            # Ensure timestamp is in datetime format
            self.raw_data['timestamp'] = pd.to_datetime(self.raw_data['timestamp'], format=config.DATE_FORMAT)
            self.raw_data.set_index('timestamp', inplace=True)
            
            # Sort by time
            self.raw_data.sort_index(inplace=True)
            
            print(f"Loaded {len(self.raw_data)} rows of data from CSV")
            
        return self.raw_data
        
    def resample_data(self):
        """Resample data to different timeframes"""
        if self.raw_data is None:
            self.load_data()
            
        print("Resampling data to 1H and 5min timeframes...")
        
        # Resample to 1-hour timeframe
        self.data_1h = self.raw_data.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Resample to 5-minute timeframe
        self.data_5m = self.raw_data.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        print(f"Resampled to {len(self.data_1h)} 1H candles and {len(self.data_5m)} 5min candles")
        return self.data_1h, self.data_5m
    
    def prepare_data_for_strategy(self):
        """Add necessary technical indicators and prepare data for CRT strategy"""
        if self.data_1h is None or self.data_5m is None:
            self.resample_data()
            
        # Calculate candle body size and wick sizes for 1H
        self.data_1h['body_size'] = abs(self.data_1h['close'] - self.data_1h['open'])
        self.data_1h['upper_wick'] = self.data_1h['high'] - self.data_1h[['open', 'close']].max(axis=1)
        self.data_1h['lower_wick'] = self.data_1h[['open', 'close']].min(axis=1) - self.data_1h['low']
        
        # Identify potential order blocks (engulfing candles)
        self._identify_order_blocks()
        
        # Align 5min data with corresponding 1H CRT ranges
        self._align_timeframes()
        
        return self.data_1h, self.data_5m
    
    def _identify_order_blocks(self):
        """Identify potential order blocks for entry confirmation"""
        # Calculate candle range
        self.data_1h['candle_range'] = self.data_1h['high'] - self.data_1h['low']
        
        # Calculate average range over the last 20 candles
        self.data_1h['avg_range'] = self.data_1h['candle_range'].rolling(20).mean()
        
        # Mark engulfing candles (potential order blocks)
        self.data_1h['is_engulfing'] = False
        for i in range(1, len(self.data_1h)):
            current = self.data_1h.iloc[i]
            prev = self.data_1h.iloc[i-1]
            
            if current['body_size'] > prev['body_size'] * 1.5 and current['candle_range'] > prev['candle_range']:
                self.data_1h.at[self.data_1h.index[i], 'is_engulfing'] = True
    
    def _align_timeframes(self):
        """Associate each 5-minute candle with its corresponding 1-hour CRT range"""
        # Create hour reference for each 5-minute candle
        self.data_5m['hour_ref'] = self.data_5m.index.floor('1H')
        
        # Forward fill 1H data to match with 5min data
        hour_data = self.data_1h.copy()
        hour_data['crt_high'] = hour_data['high']
        hour_data['crt_low'] = hour_data['low']
        hour_data['crt_mid'] = (hour_data['high'] + hour_data['low']) / 2
        
        # Join hour data to 5min data
        self.data_5m = self.data_5m.join(
            hour_data[['crt_high', 'crt_low', 'crt_mid']], 
            on='hour_ref', 
            how='left'
        )
        
        # Forward fill CRT levels
        self.data_5m[['crt_high', 'crt_low', 'crt_mid']] = self.data_5m[['crt_high', 'crt_low', 'crt_mid']].ffill()
        
    def get_forward_testing_data(self):
        """Prepare data for forward testing simulation"""
        if self.data_5m is None:
            self.prepare_data_for_strategy()
        
        # Create a copy to avoid modifying original data
        return self.data_1h.copy(), self.data_5m.copy()
    
    def fetch_latest_data(self):
        """Fetch the latest candle data from MT5 (used for live trading)"""
        if not self.use_mt5 or not self.mt5_connector:
            self.logger.error("MT5 connector not available for fetching latest data")
            return None
            
        # Get the latest 5-minute candle
        latest_5m = self.mt5_connector.get_ohlcv_data(
            symbol=config.MT5_SYMBOL,
            timeframe="5m",
            count=1
        )
        
        # Get the latest 1-hour candle
        latest_1h = self.mt5_connector.get_ohlcv_data(
            symbol=config.MT5_SYMBOL,
            timeframe="1h",
            count=1
        )
        
        if latest_5m is None or latest_1h is None:
            self.logger.error("Failed to fetch latest candle data from MT5")
            return None, None
            
        return latest_1h, latest_5m
        
    def update_live_data(self):
        """Update data with the latest candles from MT5"""
        if not self.use_mt5 or not self.mt5_connector:
            return False
            
        latest_1h, latest_5m = self.fetch_latest_data()
        if latest_1h is None or latest_5m is None:
            return False
            
        # Update the 1-hour data
        if not self.data_1h.index.contains(latest_1h.index[0]):
            self.data_1h = pd.concat([self.data_1h, latest_1h])
            self.logger.info(f"Added new 1H candle: {latest_1h.index[0]}")
        
        # Update the 5-minute data
        if not self.data_5m.index.contains(latest_5m.index[0]):
            self.data_5m = pd.concat([self.data_5m, latest_5m])
            self.logger.info(f"Added new 5m candle: {latest_5m.index[0]}")
            
        return True