"""
Chart Generator - ForexGod Trading AI  
Professional candlestick charts using mplfinance (CA DIMINEAȚA!)
"""

import os
import io
from typing import Optional
import mplfinance as mpf
import pandas as pd

from smc_detector import TradeSetup


class ChartGenerator:
    """Generate professional TradingView-style candlestick charts"""
    
    def __init__(self):
        """Initialize with TradingView styling"""
        # Professional TradingView colors
        self.style = mpf.make_mpf_style(
            base_mpf_style='charles',
            marketcolors=mpf.make_marketcolors(
                up='#089981',    # Green bullish
                down='#F23645',  # Red bearish
                edge='inherit',
                wick={'up':'#089981', 'down':'#F23645'},
                volume='inherit',
                alpha=1.0
            ),
            gridcolor='#E0E0E0',
            gridstyle='-',
            gridaxis='both',
            facecolor='white',
            figcolor='white'
        )
    
    def create_daily_chart(
        self, 
        symbol: str,
        df: pd.DataFrame,
        setup: Optional[TradeSetup] = None,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Create professional Daily chart - EXACT CA DIMINEAȚA!
        """
        try:
            # Prepare DataFrame
            df = df.copy()
            
            # mplfinance needs DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                elif 'Time' in df.columns:
                    df = df.set_index('Time')
                df.index = pd.to_datetime(df.index)
            else:
                # Already has DatetimeIndex, ensure it's datetime type
                if not pd.api.types.is_datetime64_any_dtype(df.index):
                    df.index = pd.to_datetime(df.index)
            
            # Rename to CAPITAL letters (mplfinance requirement)
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            # Keep only OHLC
            df = df[['Open', 'High', 'Low', 'Close']]
            
            # Create chart
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                mpf.plot(
                    df,
                    type='candle',  # Use candle instead of ohlc for better compatibility
                    style=self.style,
                    title=f'{symbol} - Daily',
                    ylabel='',
                    volume=False,
                    figsize=(10, 5.5),
                    tight_layout=True,
                    savefig=dict(
                        fname=save_path,
                        dpi=120,
                        bbox_inches='tight',
                        facecolor='white'
                    )
                )
                
                return save_path
            else:
                # Return bytes for Telegram
                buf = io.BytesIO()
                
                mpf.plot(
                    df,
                    type='candle',
                    style=self.style,
                    title=f'{symbol} - Daily',
                    ylabel='',
                    volume=False,
                    figsize=(10, 5.5),
                    tight_layout=True,
                    savefig=dict(
                        fname=buf,
                        dpi=120,
                        bbox_inches='tight',
                        facecolor='white'
                    )
                )
                
                buf.seek(0)
                return buf.getvalue()
        
        except Exception as e:
            print(f"❌ Error creating chart for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_4h_chart(
        self, 
        symbol: str,
        df: pd.DataFrame,
        setup: TradeSetup,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """Create 4H chart - same as daily"""
        return self.create_daily_chart(symbol, df, setup, save_path)
