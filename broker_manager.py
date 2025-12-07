"""
Broker Manager - suportă multiple brokere (MT5, Oanda, Binance, cTrader)
"""
import os
from loguru import logger
from abc import ABC, abstractmethod


class BrokerInterface(ABC):
    """Interfață abstractă pentru brokere"""
    
    @abstractmethod
    def connect(self):
        """Conectează la broker"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Deconectează de la broker"""
        pass
    
    @abstractmethod
    def execute_order(self, order_data):
        """Execută un ordin"""
        pass
    
    @abstractmethod
    def get_account_info(self):
        """Obține informații despre cont"""
        pass
    
    @abstractmethod
    def get_open_positions(self):
        """Obține pozițiile deschise"""
        pass


class MT5Broker(BrokerInterface):
    """Broker MetaTrader 5"""
    
    def __init__(self):
        self.connected = False
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError:
            logger.error("MetaTrader5 nu este instalat!")
            self.mt5 = None
    
    def connect(self):
        """Conectează la MT5"""
        if not self.mt5:
            return False
        
        try:
            if not self.mt5.initialize():
                logger.error(f"MT5 initialize() failed: {self.mt5.last_error()}")
                return False
            
            # Login dacă sunt credențiale
            login = os.getenv('MT5_LOGIN')
            password = os.getenv('MT5_PASSWORD')
            server = os.getenv('MT5_SERVER')
            
            if login and password and server:
                if not self.mt5.login(int(login), password=password, server=server):
                    logger.error(f"MT5 login failed: {self.mt5.last_error()}")
                    return False
            
            self.connected = True
            account = self.mt5.account_info()
            logger.info(f"✅ Conectat la MT5: {account.login if account else 'Unknown'}")
            return True
            
        except Exception as e:
            logger.error(f"Eroare conectare MT5: {e}")
            return False
    
    def disconnect(self):
        """Deconectează de la MT5"""
        if self.mt5:
            self.mt5.shutdown()
            self.connected = False
    
    def execute_order(self, order_data):
        """Execută ordin pe MT5"""
        if not self.connected or not self.mt5:
            return {'success': False, 'error': 'Not connected to MT5'}
        
        try:
            symbol = order_data['symbol']
            action = order_data['action'].upper()
            volume = order_data['volume']
            
            # Verifică simbol
            symbol_info = self.mt5.symbol_info(symbol)
            if not symbol_info:
                return {'success': False, 'error': f'Symbol {symbol} not found'}
            
            if not symbol_info.visible:
                self.mt5.symbol_select(symbol, True)
            
            # Pregătește request
            if action == 'BUY':
                order_type = self.mt5.ORDER_TYPE_BUY
                price = self.mt5.symbol_info_tick(symbol).ask
            elif action == 'SELL':
                order_type = self.mt5.ORDER_TYPE_SELL
                price = self.mt5.symbol_info_tick(symbol).bid
            else:
                return {'success': False, 'error': 'Invalid action'}
            
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": price,
                "sl": float(order_data.get('stop_loss', 0)),
                "tp": float(order_data.get('take_profit', 0)),
                "deviation": 20,
                "magic": 987654,
                "comment": order_data.get('comment', 'TradingView AI'),
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            
            result = self.mt5.order_send(request)
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f'Order failed: {result.retcode}',
                    'result': result
                }
            
            return {
                'success': True,
                'ticket': result.order,
                'price': result.price,
                'volume': result.volume,
                'broker': 'MT5'
            }
            
        except Exception as e:
            logger.error(f"Eroare execuție MT5: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_account_info(self):
        """Obține info cont MT5"""
        if not self.connected or not self.mt5:
            return None
        
        account = self.mt5.account_info()
        if not account:
            return None
        
        return {
            'balance': account.balance,
            'equity': account.equity,
            'margin': account.margin,
            'free_margin': account.margin_free,
            'profit': account.profit
        }
    
    def get_open_positions(self):
        """Obține poziții deschise MT5"""
        if not self.connected or not self.mt5:
            return []
        
        positions = self.mt5.positions_get()
        if not positions:
            return []
        
        return [
            {
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == 0 else 'SELL',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'profit': pos.profit,
                'sl': pos.sl,
                'tp': pos.tp
            }
            for pos in positions
        ]


class OandaBroker(BrokerInterface):
    """Broker Oanda"""
    
    def __init__(self):
        self.connected = False
        self.api = None
        try:
            import oandapyV20
            import oandapyV20.endpoints.orders as orders
            import oandapyV20.endpoints.accounts as accounts
            import oandapyV20.endpoints.positions as positions
            self.oanda = oandapyV20
            self.orders_module = orders
            self.accounts_module = accounts
            self.positions_module = positions
        except ImportError:
            logger.error("oandapyV20 nu este instalat!")
    
    def connect(self):
        """Conectează la Oanda"""
        try:
            api_key = os.getenv('OANDA_API_KEY')
            account_id = os.getenv('OANDA_ACCOUNT_ID')
            environment = os.getenv('OANDA_ENVIRONMENT', 'practice')
            
            if not api_key or not account_id:
                logger.error("Lipsesc credențiale Oanda!")
                return False
            
            self.api = self.oanda.API(access_token=api_key, environment=environment)
            self.account_id = account_id
            self.connected = True
            
            logger.info(f"✅ Conectat la Oanda ({environment}): {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Eroare conectare Oanda: {e}")
            return False
    
    def disconnect(self):
        """Deconectează de la Oanda"""
        self.connected = False
        self.api = None
    
    def execute_order(self, order_data):
        """Execută ordin pe Oanda"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected to Oanda'}
        
        try:
            # Format Oanda pentru simbol (ex: EUR_USD)
            symbol = order_data['symbol'].replace('/', '_')
            if '_' not in symbol and len(symbol) == 6:
                symbol = f"{symbol[:3]}_{symbol[3:]}"
            
            units = int(order_data['volume'] * 100000)  # Convert lots to units
            if order_data['action'].upper() == 'SELL':
                units = -units
            
            order_spec = {
                "order": {
                    "instrument": symbol,
                    "units": str(units),
                    "type": "MARKET",
                    "positionFill": "DEFAULT"
                }
            }
            
            # Adaugă SL/TP dacă există
            if order_data.get('stop_loss'):
                order_spec['order']['stopLossOnFill'] = {
                    "price": str(order_data['stop_loss'])
                }
            
            if order_data.get('take_profit'):
                order_spec['order']['takeProfitOnFill'] = {
                    "price": str(order_data['take_profit'])
                }
            
            r = self.orders_module.OrderCreate(self.account_id, data=order_spec)
            response = self.api.request(r)
            
            return {
                'success': True,
                'ticket': response['orderFillTransaction']['id'],
                'price': float(response['orderFillTransaction']['price']),
                'broker': 'Oanda'
            }
            
        except Exception as e:
            logger.error(f"Eroare execuție Oanda: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_account_info(self):
        """Obține info cont Oanda"""
        if not self.connected:
            return None
        
        try:
            r = self.accounts_module.AccountDetails(self.account_id)
            response = self.api.request(r)
            account = response['account']
            
            return {
                'balance': float(account['balance']),
                'equity': float(account['NAV']),
                'profit': float(account['unrealizedPL'])
            }
        except:
            return None
    
    def get_open_positions(self):
        """Obține poziții deschise Oanda"""
        if not self.connected:
            return []
        
        try:
            r = self.positions_module.OpenPositions(self.account_id)
            response = self.api.request(r)
            
            positions_list = []
            for pos in response.get('positions', []):
                long_units = float(pos['long']['units'])
                short_units = float(pos['short']['units'])
                
                if long_units != 0 or short_units != 0:
                    positions_list.append({
                        'symbol': pos['instrument'],
                        'type': 'BUY' if long_units > 0 else 'SELL',
                        'volume': abs(long_units + short_units) / 100000,
                        'profit': float(pos['unrealizedPL'])
                    })
            
            return positions_list
        except:
            return []


class BinanceBroker(BrokerInterface):
    """Broker Binance Futures"""
    
    def __init__(self):
        self.connected = False
        self.exchange = None
        try:
            import ccxt
            self.ccxt = ccxt
        except ImportError:
            logger.error("ccxt nu este instalat!")
    
    def connect(self):
        """Conectează la Binance"""
        try:
            api_key = os.getenv('BINANCE_API_KEY')
            secret = os.getenv('BINANCE_SECRET')
            testnet = os.getenv('BINANCE_TESTNET', 'True').lower() == 'true'
            
            if not api_key or not secret:
                logger.error("Lipsesc credențiale Binance!")
                return False
            
            self.exchange = self.ccxt.binance({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            
            if testnet:
                self.exchange.set_sandbox_mode(True)
            
            # Test conexiune
            self.exchange.load_markets()
            self.connected = True
            
            logger.info(f"✅ Conectat la Binance Futures ({'Testnet' if testnet else 'Live'})")
            return True
            
        except Exception as e:
            logger.error(f"Eroare conectare Binance: {e}")
            return False
    
    def disconnect(self):
        """Deconectează de la Binance"""
        self.connected = False
        self.exchange = None
    
    def execute_order(self, order_data):
        """Execută ordin pe Binance"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected to Binance'}
        
        try:
            symbol = order_data['symbol']
            # Format Binance: BTCUSDT
            if '/' not in symbol:
                symbol = f"{symbol[:3]}/{symbol[3:]}"
            
            side = 'buy' if order_data['action'].upper() == 'BUY' else 'sell'
            amount = order_data['volume']
            
            # Plasează ordin
            order = self.exchange.create_market_order(symbol, side, amount)
            
            # Adaugă SL/TP dacă există
            if order_data.get('stop_loss'):
                self.exchange.create_order(
                    symbol, 'stop_market', 'sell' if side == 'buy' else 'buy',
                    amount, None, {'stopPrice': order_data['stop_loss']}
                )
            
            return {
                'success': True,
                'ticket': order['id'],
                'price': order['price'],
                'broker': 'Binance'
            }
            
        except Exception as e:
            logger.error(f"Eroare execuție Binance: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_account_info(self):
        """Obține info cont Binance"""
        if not self.connected:
            return None
        
        try:
            balance = self.exchange.fetch_balance()
            return {
                'balance': balance['total']['USDT'],
                'equity': balance['total']['USDT'],
                'profit': 0
            }
        except:
            return None
    
    def get_open_positions(self):
        """Obține poziții deschise Binance"""
        if not self.connected:
            return []
        
        try:
            positions = self.exchange.fetch_positions()
            return [
                {
                    'symbol': pos['symbol'],
                    'type': 'BUY' if float(pos['contracts']) > 0 else 'SELL',
                    'volume': abs(float(pos['contracts'])),
                    'profit': float(pos['unrealizedPnl'])
                }
                for pos in positions if float(pos['contracts']) != 0
            ]
        except:
            return []


class CTraderBroker(BrokerInterface):
    """Broker cTrader pentru IC Markets"""
    
    def __init__(self):
        self.connected = False
        self.executor = None
    
    def connect(self):
        """Conectează la cTrader"""
        try:
            from ctrader_executor import CTraderExecutor
            
            self.executor = CTraderExecutor()
            if self.executor.connect():
                self.connected = True
                logger.success("✅ Conectat la cTrader (IC Markets)")
                return True
            else:
                logger.error("❌ Conexiune cTrader eșuată")
                return False
                
        except Exception as e:
            logger.error(f"Eroare conectare cTrader: {e}")
            return False
    
    def disconnect(self):
        """Deconectează de la cTrader"""
        if self.executor:
            self.executor.disconnect()
            self.connected = False
            logger.info("cTrader deconectat")
    
    def execute_order(self, order_data):
        """Execută ordin pe cTrader"""
        if not self.connected or not self.executor:
            return {'success': False, 'error': 'Not connected to cTrader'}
        
        try:
            symbol = order_data['symbol']
            action = order_data['action'].upper()
            volume = order_data['volume']
            price = order_data.get('price', 0)
            stop_loss = order_data.get('stop_loss', 0)
            take_profit = order_data.get('take_profit', 0)
            comment = order_data.get('comment', 'AI Trading Bot')
            
            order = self.executor.place_order(
                symbol=symbol,
                order_type='buy' if action == 'BUY' else 'sell',
                volume=volume,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                comment=comment
            )
            
            if order:
                return {
                    'success': True,
                    'ticket': order['order_id'],
                    'price': order['entry_price'],
                    'volume': order['volume'],
                    'broker': 'cTrader'
                }
            else:
                return {'success': False, 'error': 'Order placement failed'}
                
        except Exception as e:
            logger.error(f"Eroare execuție cTrader: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_account_info(self):
        """Obține info cont cTrader LIVE"""
        if not self.connected or not self.executor:
            return None
        
        try:
            account_info = self.executor.get_account_info()
            return account_info
        except Exception as e:
            logger.error(f"Eroare get account info: {e}")
            return None
    
    def get_open_positions(self):
        """Obține poziții deschise cTrader"""
        if not self.connected or not self.executor:
            return []
        
        try:
            positions = self.executor.get_open_positions()
            return positions
        except Exception as e:
            logger.error(f"Eroare get positions: {e}")
            return []


class BrokerManager:
    """Manager pentru toate brokerele"""
    
    def __init__(self):
        self.brokers = {
            'MT5': MT5Broker(),
            'OANDA': OandaBroker(),
            'BINANCE': BinanceBroker(),
            'CTRADER': CTraderBroker(),
            'DEMO': DemoBroker()
        }
        
        self.default_broker = os.getenv('DEFAULT_BROKER', 'CTRADER').upper()
        self.active_broker = None
        
        # Conectează la broker-ul implicit
        self.connect(self.default_broker)
    
    def connect(self, broker_name):
        """Conectează la un broker specific"""
        broker_name = broker_name.upper()
        
        if broker_name not in self.brokers:
            logger.error(f"Broker necunoscut: {broker_name}")
            return False
        
        broker = self.brokers[broker_name]
        if broker.connect():
            self.active_broker = broker
            return True
        
        return False
    
    def execute_order(self, order_data):
        """Execută ordin pe broker-ul activ"""
        if not self.active_broker:
            return {'success': False, 'error': 'No active broker'}
        
        return self.active_broker.execute_order(order_data)
    
    def get_account_info(self):
        """Obține info cont de la broker-ul activ"""
        if not self.active_broker:
            return None
        
        return self.active_broker.get_account_info()
    
    def get_open_positions(self):
        """Obține poziții deschise de la broker-ul activ"""
        if not self.active_broker:
            return []
        
        return self.active_broker.get_open_positions()


class DemoBroker(BrokerInterface):
    """Broker DEMO pentru testare fără conturi reale"""
    
    def __init__(self):
        self.connected = False
        self.demo_balance = 10000.0
        self.demo_positions = []
        self.order_counter = 1
    
    def connect(self):
        """Simulează conectarea"""
        self.connected = True
        logger.success("✅ DEMO Broker conectat (mod simulare)")
        return True
    
    def disconnect(self):
        """Simulează deconectarea"""
        self.connected = False
        logger.info("DEMO Broker deconectat")
    
    def execute_order(self, order_data):
        """Simulează executarea unui ordin"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected to demo broker'}
        
        order_id = f"DEMO_{self.order_counter}"
        self.order_counter += 1
        
        # Adaugă poziția în lista demo
        position = {
            'order_id': order_id,
            'symbol': order_data.get('symbol'),
            'action': order_data.get('action'),
            'volume': order_data.get('volume', 0.1),
            'price': order_data.get('price'),
            'stop_loss': order_data.get('stop_loss'),
            'take_profit': order_data.get('take_profit')
        }
        self.demo_positions.append(position)
        
        logger.success(f"✅ DEMO Order executat: {order_data.get('action').upper()} {order_data.get('volume', 0.1)} {order_data.get('symbol')} @ {order_data.get('price')}")
        logger.info(f"   SL: {order_data.get('stop_loss')} | TP: {order_data.get('take_profit')}")
        
        return {
            'success': True,
            'order_id': order_id,
            'message': f'Demo order placed: {order_id}',
            'position': position
        }
    
    def get_account_info(self):
        """Returnează info cont demo"""
        return {
            'balance': self.demo_balance,
            'equity': self.demo_balance,
            'margin': 0,
            'free_margin': self.demo_balance,
            'profit': 0,
            'currency': 'USD',
            'type': 'DEMO'
        }
    
    def get_open_positions(self):
        """Returnează poziții demo deschise"""
        return self.demo_positions
