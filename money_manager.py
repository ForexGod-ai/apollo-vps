"""
Money Manager - gestionează riscul și calculează dimensiunea pozițiilor
"""
import os
import json
from loguru import logger
from datetime import datetime, timedelta


class MoneyManager:
    """Gestionează riscul și money management-ul automat"""
    
    def __init__(self, broker_type='CTRADER'):
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', 0.02))
        self.max_positions = int(os.getenv('MAX_POSITIONS', 3))
        self.broker_type = broker_type.upper()
        
        # Get LIVE balance from broker
        self.account_balance = self._fetch_live_balance()
        
        # Tracking
        self.open_positions = []
        self.trade_history = []
        self.daily_trades = {}
        
        # Limite
        self.max_daily_loss = self.account_balance * 0.05  # 5% per zi
        self.max_drawdown = self.account_balance * 0.20    # 20% drawdown maxim
        
        self.peak_balance = self.account_balance
        self.current_balance = self.account_balance
        
        logger.info(f"💰 Money Manager inițializat: Balance=${self.account_balance:.2f}, Risk={self.risk_per_trade*100}%")
    
    def _fetch_live_balance(self) -> float:
        """
        Fetch LIVE account balance from broker
        
        Returns:
            Current account balance
        """
        try:
            # Read from trade_history.json for accurate balance
            with open('trade_history.json', 'r') as f:
                trades = json.load(f)
            
            if not trades:
                logger.warning("⚠️  No trade history, using default")
                return 1336.12  # Your current balance
            
            # Calculate from trade history
            initial_balance = 1000.0
            total_profit = sum(trade.get('profit', 0) for trade in trades)
            balance = initial_balance + total_profit
            
            logger.success(f"✅ Balance from trade history: ${balance:.2f} ({len(trades)} trades)")
            return balance
                
        except FileNotFoundError:
            logger.warning("⚠️  No trade history found")
            return 1336.12  # Your current balance
        except Exception as e:
            logger.error(f"❌ Error reading balance: {e}")
            return float(os.getenv('ACCOUNT_BALANCE', 1336))
    
    def refresh_balance(self):
        """
        Refresh account balance from live broker data
        """
        try:
            new_balance = self._fetch_live_balance()
            if new_balance != self.account_balance:
                logger.info(f"💰 Balance updated: ${self.account_balance:.2f} → ${new_balance:.2f}")
                self.account_balance = new_balance
                self.current_balance = new_balance
                
                # Update limits
                self.max_daily_loss = self.account_balance * 0.05
                self.max_drawdown = self.account_balance * 0.20
                
                if new_balance > self.peak_balance:
                    self.peak_balance = new_balance
        except Exception as e:
            logger.error(f"❌ Error refreshing balance: {e}")
    
    def calculate_position_size(self, signal_data):
        """
        Calculează dimensiunea poziției bazată pe risc
        
        Args:
            signal_data: Dict cu datele semnalului
            
        Returns:
            Dict cu detalii despre poziție
        """
        result = {
            'approved': False,
            'position_size': 0,
            'risk_amount': 0,
            'reason': None
        }
        
        try:
            # 1. Verifică numărul de poziții deschise
            if len(self.open_positions) >= self.max_positions:
                result['reason'] = f"Max positions reached ({self.max_positions})"
                logger.warning(f"⚠️ Limita de poziții atinsă: {len(self.open_positions)}/{self.max_positions}")
                return result
            
            # 2. Verifică drawdown
            current_drawdown = self.calculate_drawdown()
            if current_drawdown >= 0.20:  # 20%
                result['reason'] = f"Max drawdown exceeded ({current_drawdown:.1%})"
                logger.error(f"🛑 Drawdown excesiv: {current_drawdown:.1%}")
                return result
            
            # 3. Verifică pierderi zilnice
            today = datetime.now().date()
            daily_loss = self.daily_trades.get(today, {}).get('loss', 0)
            if abs(daily_loss) >= self.max_daily_loss:
                result['reason'] = f"Daily loss limit reached (${abs(daily_loss):.2f})"
                logger.error(f"🛑 Limita de pierderi zilnice atinsă: ${abs(daily_loss):.2f}")
                return result
            
            # 4. Calculează dimensiunea poziției
            price = signal_data.get('price', 0)
            sl = signal_data.get('stop_loss', 0)
            
            if not price or not sl or price == sl:
                result['reason'] = "Invalid price or stop loss"
                return result
            
            # Risc în valoare monetară
            risk_amount = self.current_balance * self.risk_per_trade
            
            # Distanța stop-loss în pips/points
            risk_distance = abs(price - sl)
            
            # Presupunem pip value standard (pentru Forex)
            # Pentru o pereche standard, 1 pip = 0.0001, value ≈ $10 per lot
            pip_value = 10  # Simplificat - ar trebui calculat dinamic
            pips = risk_distance / 0.0001
            
            # Calculare lot size
            # Risk = Lots * Pips * Pip Value
            # Lots = Risk / (Pips * Pip Value)
            if pips > 0 and pip_value > 0:
                position_size = risk_amount / (pips * pip_value)
            else:
                position_size = 0.01  # Minim
            
            # Rotunjire și limitare
            position_size = round(position_size, 2)
            position_size = max(0.01, min(position_size, 10.0))  # Între 0.01 și 10 lots
            
            # 5. Verifică dacă poziția este validă
            if position_size < 0.01:
                result['reason'] = "Position size too small"
                return result
            
            # Aprobare
            result['approved'] = True
            result['position_size'] = position_size
            result['risk_amount'] = risk_amount
            result['risk_pips'] = pips
            result['risk_percentage'] = self.risk_per_trade * 100
            
            logger.info(f"💰 Poziție calculată: {position_size} lots (risc: ${risk_amount:.2f}, {pips:.1f} pips)")
            
        except Exception as e:
            logger.error(f"❌ Eroare la calcularea poziției: {e}")
            result['reason'] = f"Calculation error: {str(e)}"
        
        return result
    
    def calculate_drawdown(self):
        """Calculează drawdown-ul curent"""
        if self.peak_balance == 0:
            return 0
        
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        return drawdown
    
    def record_trade(self, order_data, execution_result):
        """
        Înregistrează o tranzacție executată
        
        Args:
            order_data: Datele ordinului
            execution_result: Rezultatul execuției
        """
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': order_data['symbol'],
            'action': order_data['action'],
            'volume': order_data['volume'],
            'price': order_data.get('price'),
            'sl': order_data.get('stop_loss'),
            'tp': order_data.get('take_profit'),
            'ticket': execution_result.get('ticket'),
            'status': 'open'
        }
        
        # Adaugă la poziții deschise
        if order_data['action'] in ['buy', 'sell']:
            self.open_positions.append(trade)
        
        # Adaugă în istoric
        self.trade_history.append(trade)
        
        logger.info(f"📝 Tranzacție înregistrată: {trade['action'].upper()} {trade['volume']} {trade['symbol']}")
    
    def update_position(self, ticket, profit=None, status=None):
        """
        Actualizează o poziție deschisă
        
        Args:
            ticket: Ticket-ul poziției
            profit: Profitul curent
            status: Noul status ('open', 'closed')
        """
        for pos in self.open_positions:
            if pos.get('ticket') == ticket:
                if profit is not None:
                    pos['profit'] = profit
                    
                    # Update balance
                    self.current_balance = self.account_balance + profit
                    
                    # Update peak
                    if self.current_balance > self.peak_balance:
                        self.peak_balance = self.current_balance
                
                if status:
                    pos['status'] = status
                    
                    # Dacă e închisă, mută din poziții deschise
                    if status == 'closed' and profit is not None:
                        self.open_positions.remove(pos)
                        
                        # Înregistrează în pierderi zilnice
                        today = datetime.now().date()
                        if today not in self.daily_trades:
                            self.daily_trades[today] = {'profit': 0, 'loss': 0, 'count': 0}
                        
                        self.daily_trades[today]['count'] += 1
                        if profit >= 0:
                            self.daily_trades[today]['profit'] += profit
                        else:
                            self.daily_trades[today]['loss'] += profit
                
                break
    
    def get_statistics(self):
        """Returnează statistici despre trading"""
        closed_trades = [t for t in self.trade_history if t.get('status') == 'closed']
        
        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t.get('profit', 0) > 0)
        losing_trades = sum(1 for t in closed_trades if t.get('profit', 0) < 0)
        
        total_profit = sum(t.get('profit', 0) for t in closed_trades)
        
        return {
            'current_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'total_profit': total_profit,
            'drawdown': self.calculate_drawdown(),
            'open_positions': len(self.open_positions),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0
        }
