import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import logging

class MT5Connector:
    """
    Class to handle connection to MetaTrader 5 terminal and data retrieval
    """
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.logger = logging.getLogger("crt_trading.mt5_connector")
        
    def connect(self, max_retries=3, retry_delay=2):
        """
        Initialize connection to MetaTrader 5 terminal
        
        Parameters:
        max_retries (int): Maximum number of connection attempts
        retry_delay (int): Delay in seconds between retries
        
        Returns:
        bool: True if connection successful, False otherwise
        """
        # Try to connect with retries
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"MT5 connection attempt {attempt}/{max_retries}...")
            
            # Check if MT5 is already initialized
            if mt5.terminal_info() is not None:
                self.logger.info("MT5 is already initialized")
            else:
                # Initialize MT5 connection
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    self.logger.error(f"MT5 initialization failed, error code: {error_code}")
                    
                    if error_code[0] == -10005:  # IPC timeout
                        self.logger.warning("MT5 terminal may not be running. Please start MetaTrader 5 and try again.")
                    
                    if attempt < max_retries:
                        self.logger.info(f"Retrying in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        continue
                    else:
                        self.logger.error("Maximum retries reached. Could not initialize MT5.")
                        return False
            
            # Log in to the trading account
            if self.login and self.password and self.server:
                login_result = mt5.login(
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
                
                if not login_result:
                    error_code = mt5.last_error()
                    self.logger.error(f"MT5 login failed, error code: {error_code}")
                    
                    if attempt < max_retries:
                        mt5.shutdown()
                        self.logger.info(f"Retrying in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        continue
                    else:
                        mt5.shutdown()
                        self.logger.error("Maximum retries reached. Could not login to MT5.")
                        return False
                    
                self.logger.info(f"MT5 login successful for account #{self.login}")
            
            # Check connection status
            account_info = mt5.account_info()
            if account_info is None:
                error_code = mt5.last_error()
                self.logger.error(f"No account info, error code: {error_code}")
                
                if attempt < max_retries:
                    mt5.shutdown()
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                    continue
                else:
                    mt5.shutdown()
                    self.logger.error("Maximum retries reached. Could not get account info.")
                    return False
                
            # Successfully connected
            self.connected = True
            self.logger.info(f"Connected to MT5: {account_info.server}, Account: {account_info.login}, Balance: ${account_info.balance}")
            return True
            
        return False
        
    def disconnect(self):
        """Close connection to MT5 terminal"""
        mt5.shutdown()
        self.connected = False
        self.logger.info("Disconnected from MT5")
        
    def get_account_info(self):
        """Get account information"""
        if not self.connected and not self.connect():
            return None
            
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error(f"Failed to get account info, error code: {mt5.last_error()}")
            return None
            
        # Convert to dictionary
        account_dict = {
            'login': account_info.login,
            'server': account_info.server,
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'free_margin': account_info.margin_free,
            'leverage': account_info.leverage,
            'currency': account_info.currency
        }
        
        return account_dict
        
    def get_ohlcv_data(self, symbol, timeframe, count=500, start_time=None, end_time=None):
        """
        Get OHLCV data for a symbol and timeframe
        
        Parameters:
        symbol (str): Trading instrument symbol (e.g., "XAUUSD")
        timeframe (str): Timeframe as string ("1h", "5m", etc.)
        count (int): Number of bars to retrieve (if no start/end time specified)
        start_time (datetime): Start time for data retrieval
        end_time (datetime): End time for data retrieval
        
        Returns:
        DataFrame: OHLCV data
        """
        if not self.connected and not self.connect():
            return None
            
        # Convert timeframe string to MT5 timeframe constant
        tf_mapping = {
            "1m": mt5.TIMEFRAME_M1,
            "5m": mt5.TIMEFRAME_M5, 
            "15m": mt5.TIMEFRAME_M15,
            "30m": mt5.TIMEFRAME_M30,
            "1h": mt5.TIMEFRAME_H1,
            "4h": mt5.TIMEFRAME_H4,
            "1d": mt5.TIMEFRAME_D1
        }
        
        if timeframe.lower() not in tf_mapping:
            self.logger.error(f"Invalid timeframe: {timeframe}, supported: {list(tf_mapping.keys())}")
            return None
            
        mt5_timeframe = tf_mapping[timeframe.lower()]
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found, trying to enable it")
            # Try to enable the symbol
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to enable symbol {symbol}")
                return None
        
        # Get rates based on parameters
        if start_time and end_time:
            # Get rates within time range
            rates = mt5.copy_rates_range(symbol, mt5_timeframe, start_time, end_time)
        else:
            # Get latest N rates
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
            
        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to get rates for {symbol}, error code: {mt5.last_error()}")
            return None
              # Convert to DataFrame
        rates_df = pd.DataFrame(rates)
        rates_df['timestamp'] = pd.to_datetime(rates_df['time'], unit='s')
        rates_df.set_index('timestamp', inplace=True)
        rates_df.drop('time', axis=1, inplace=True)
        rates_df.rename(columns={
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume'
        }, inplace=True)
        
        return rates_df
        
    def get_current_price(self, symbol):
        """Get the current price for a symbol"""
        if not self.connected and not self.connect():
            return None
            
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None
        
        # Convert named tuple to dictionary to safely access attributes
        symbol_dict = symbol_info._asdict()
            
        return {
            'bid': symbol_dict.get('bid', 0),
            'ask': symbol_dict.get('ask', 0),
            'spread': symbol_dict.get('spread', 0)
        }
        
    def place_market_order(self, symbol, order_type, volume, sl=None, tp=None, comment="CRT Strategy"):
        """
        Place a market order
        
        Parameters:
        symbol (str): Trading instrument symbol (e.g., "XAUUSD")
        order_type (str): "BUY" or "SELL"
        volume (float): Trade volume in lots
        sl (float): Stop Loss price
        tp (float): Take Profit price
        comment (str): Order comment
        
        Returns:
        int: Order ticket number or None if failed
        """
        if not self.connected and not self.connect():
            return None
              # Check symbol
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None
        
        # Convert named tuple to dictionary to safely access attributes
        symbol_dict = symbol_info._asdict()
            
        # Get price
        price = symbol_dict.get('ask', 0) if order_type.upper() == "BUY" else symbol_dict.get('bid', 0)
        
        # Define order type
        mt5_order_type = mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        
        # Prepare request structure
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_order_type,
            "price": price,
            "deviation": 20,  # max price deviation in points
            "magic": 12345,   # magic number to identify trades
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,  # good till canceled
            "type_filling": mt5.ORDER_FILLING_FOK,  # fill or kill
        }
        
        # Add SL/TP if provided
        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp
            
        # Send order
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Order failed, retcode: {result.retcode}, {result.comment}")
            return None
            
        self.logger.info(f"Order placed successfully, ticket: {result.order}")
        return result.order
        
    def close_position(self, ticket):
        """
        Close an open position
        
        Parameters:
        ticket (int): Position ticket
        
        Returns:
        bool: True if closed successfully, False otherwise
        """
        if not self.connected and not self.connect():
            return False
            
        # Get position info
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            self.logger.error(f"Position with ticket {ticket} not found")
            return False
            
        position = position[0]
        
        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position.ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_BUY if position.type == 1 else mt5.ORDER_TYPE_SELL,  # Opposite direction
            "price": mt5.symbol_info_tick(position.symbol).ask if position.type == 1 else mt5.symbol_info_tick(position.symbol).bid,
            "deviation": 20,
            "magic": 12345,
            "comment": "CRT Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        # Send request
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Close position failed, retcode: {result.retcode}, {result.comment}")
            return False
            
        self.logger.info(f"Position {ticket} closed successfully")
        return True
