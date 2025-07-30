import pandas as pd
import numpy as np
from src import config

class RiskManager:
    def __init__(self, initial_capital=config.INITIAL_CAPITAL, risk_per_trade=config.RISK_PER_TRADE):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.trades = []
        self.open_positions = []
        self.trade_history = pd.DataFrame(columns=[
            'entry_time', 'exit_time', 'direction', 'entry_price', 'exit_price', 
            'stop_loss', 'take_profit', 'size', 'pnl', 'pnl_pct', 'rr', 'outcome'
        ])
        
    def calculate_position_size(self, entry_price, stop_loss):
        """Calculate position size based on risk parameters"""
        if entry_price == stop_loss:
            return 0
            
        # Risk amount in dollars
        risk_amount = self.current_capital * self.risk_per_trade
        
        # Price difference for stop loss
        price_risk = abs(entry_price - stop_loss)
        
        # Calculate position size in units (lots)
        # For GOLD in MT5: 1 standard lot = 100 troy oz
        # Each $1 movement in gold price = $100 per standard lot
        
        # Calculate potential loss for 1 lot
        loss_per_lot = price_risk * 100  # $1 price change = $100 per lot
        
        # Calculate position size in lots
        position_size_lots = risk_amount / loss_per_lot
        
        # Round down to nearest 0.01 lot
        position_size_lots = np.floor(position_size_lots * 100) / 100
        
        # Ensure minimum position size
        position_size_lots = max(0.01, position_size_lots)
        
        return position_size_lots
        
    def open_position(self, signal, timestamp):
        """Open a new trading position based on signal"""
        # Check if we already have maximum positions open
        if len(self.open_positions) >= config.MAX_POSITIONS:
            print(f"[{timestamp}] Maximum positions already open. Cannot open new position.")
            return None
            
        # Calculate position size
        size = self.calculate_position_size(signal['entry_price'], signal['stop_loss'])
        
        if size <= 0:
            print(f"[{timestamp}] Invalid position size calculated: {size}. Skipping trade.")
            return None
        
        # Create position object
        position = {
            'entry_time': timestamp,
            'direction': signal['direction'],
            'entry_price': signal['entry_price'],
            'current_price': signal['entry_price'],
            'stop_loss': signal['stop_loss'],
            'original_stop_loss': signal['stop_loss'],  # For tracking trailing stops
            'tp1': signal['tp1'],
            'tp2': signal['tp2'],
            'size': size,
            'risk': signal['risk'],
            'rr1': signal['rr1'],
            'rr2': signal['rr2'],
            'hit_tp1': False,
            'crt_high': signal['crt_high'],
            'crt_low': signal['crt_low'],
        }
        
        self.open_positions.append(position)
        
        # Calculate and display trade info
        risk_amount = self.current_capital * self.risk_per_trade
        
        print(f"[{timestamp}] OPENED {position['direction']} position: " +
              f"Entry={position['entry_price']:.2f}, " +
              f"SL={position['stop_loss']:.2f}, " +
              f"TP1={position['tp1']:.2f}, " + 
              f"TP2={position['tp2']:.2f}, " +
              f"Size={position['size']:.2f} lots, " +
              f"Risk=${risk_amount:.2f}, " +
              f"R:R1={position['rr1']:.2f}, R:R2={position['rr2']:.2f}")
        
        return position
        
    def update_positions(self, timestamp, current_price):
        """Update all open positions with current market price"""
        for position in self.open_positions:
            position['current_price'] = current_price
            
            # Check if TP1 is hit and we should move SL to breakeven
            if config.TRAIL_TO_BREAKEVEN_AT_TP1 and not position['hit_tp1']:
                if (position['direction'] == 'LONG' and current_price >= position['tp1']) or \
                   (position['direction'] == 'SHORT' and current_price <= position['tp1']):
                    position['hit_tp1'] = True
                    position['stop_loss'] = position['entry_price']
                    print(f"[{timestamp}] TP1 hit, moved SL to breakeven for {position['direction']} trade")
        
        return self.open_positions
        
    def check_position_exits(self, timestamp, candle):
        """Check if any positions should be closed based on price levels"""
        high, low, close = candle['high'], candle['low'], candle['close']
        positions_to_close = []
        
        for position in self.open_positions:
            exit_price = None
            exit_reason = None
            
            if position['direction'] == 'LONG':
                # Check stop loss hit (low price went below SL)
                if low <= position['stop_loss']:
                    exit_price = position['stop_loss']
                    exit_reason = 'stop_loss'
                # Check TP1 hit
                elif high >= position['tp1'] and not position['hit_tp1']:
                    exit_price = position['tp1']
                    exit_reason = 'tp1'
                # Check TP2 hit
                elif high >= position['tp2']:
                    exit_price = position['tp2']
                    exit_reason = 'tp2'
                    
            elif position['direction'] == 'SHORT':
                # Check stop loss hit (high price went above SL)
                if high >= position['stop_loss']:
                    exit_price = position['stop_loss']
                    exit_reason = 'stop_loss'
                # Check TP1 hit
                elif low <= position['tp1'] and not position['hit_tp1']:
                    exit_price = position['tp1']
                    exit_reason = 'tp1'
                # Check TP2 hit
                elif low <= position['tp2']:
                    exit_price = position['tp2']
                    exit_reason = 'tp2'
            
            if exit_price is not None:
                # Calculate P&L
                pnl = self._calculate_pnl(position, exit_price)
                
                # Update position with exit information
                position.update({
                    'exit_time': timestamp,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl': pnl,
                    'pnl_pct': pnl / self.current_capital * 100
                })
                
                positions_to_close.append(position)
                
        # Close positions and update trade history
        for position in positions_to_close:
            self._close_position(position)
            
        return positions_to_close
    
    def _calculate_pnl(self, position, exit_price):
        """Calculate profit/loss for a position"""
        direction_mult = 1 if position['direction'] == 'LONG' else -1
        price_diff = (exit_price - position['entry_price']) * direction_mult
        
        # For GOLD in MT5: 1 lot = 100 Troy Oz
        # Each $1 movement in price = $100 per lot
        pnl = price_diff * position['size'] * 100
        
        return pnl
    
    def _close_position(self, position):
        """Close a position and update account"""
        # Remove from open positions
        self.open_positions = [p for p in self.open_positions if p['entry_time'] != position['entry_time']]
        
        # Update account capital
        self.current_capital += position['pnl']
        
        # Add to trade history
        trade_record = {
            'entry_time': position['entry_time'],
            'exit_time': position['exit_time'],
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'exit_price': position['exit_price'],
            'stop_loss': position['original_stop_loss'],
            'take_profit': position['tp2'],  # Using ultimate target
            'size': position['size'],
            'pnl': position['pnl'],
            'pnl_pct': position['pnl_pct'],
            'rr': position['rr2'],
            'outcome': 'win' if position['pnl'] > 0 else 'loss'
        }
        
        self.trade_history = pd.concat([
            self.trade_history, 
            pd.DataFrame([trade_record])
        ])
        
        # Print trade summary
        print(f"[{position['exit_time']}] CLOSED {position['direction']} position: " +
              f"Entry={position['entry_price']:.2f}, " +
              f"Exit={position['exit_price']:.2f}, " +
              f"Reason={position['exit_reason']}, " +
              f"P&L=${position['pnl']:.2f} ({position['pnl_pct']:.2f}%), " +
              f"New Balance=${self.current_capital:.2f}")
        
        self.trades.append(position)
        return position
    
    def get_performance_metrics(self):
        """Calculate and return performance metrics"""
        if len(self.trade_history) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'avg_rr': 0
            }
            
        wins = self.trade_history[self.trade_history['pnl'] > 0]
        losses = self.trade_history[self.trade_history['pnl'] <= 0]
        
        win_rate = len(wins) / len(self.trade_history) if len(self.trade_history) > 0 else 0
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        largest_win = wins['pnl'].max() if len(wins) > 0 else 0
        largest_loss = losses['pnl'].min() if len(losses) > 0 else 0
        
        total_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        total_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        metrics = {
            'total_trades': len(self.trade_history),
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'total_pnl': self.current_capital - self.initial_capital,
            'total_pnl_pct': (self.current_capital - self.initial_capital) / self.initial_capital * 100,
            'avg_rr': self.trade_history['rr'].mean()
        }
        
        return metrics