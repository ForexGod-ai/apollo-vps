#!/usr/bin/env python3
"""
Clean Chart Generator - ONLY dark theme + cyan/purple candles
NO annotations, NO FVG, NO CHoCH, NO Entry/SL/TP
"""
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
from typing import Optional


class ChartGenerator:
    """Simple chart generator with dark background"""
    
    def __init__(self, dark_theme: bool = True):
        """Initialize with simple style"""
        if dark_theme:
            # Dark TradingView colors - EXACT like your screenshot
            mc = mpf.make_marketcolors(
                up='#00bcd4',      # Bright cyan/turquoise for UP candles
                down='#9c27b0',    # Purple/violet for DOWN candles (like TradingView)
                edge='inherit',
                wick='inherit',
                volume='inherit'
            )
            
            self.style = mpf.make_mpf_style(
                marketcolors=mc,
                gridstyle=':',
                gridcolor='#363c4e',
                facecolor='#1e222d',
                figcolor='#131722',
                gridaxis='both',
                y_on_right=False
            )
            
            self.bg_color = '#131722'
            self.text_color = '#d1d4dc'
        else:
            self.style = 'charles'
            self.bg_color = 'white'
            self.text_color = 'black'
    
    def create_daily_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup = None,
        save_path: Optional[str] = None,
        timeframe: str = "Daily"
    ):
        """Create simple chart with mplfinance"""
        try:
            # Prepare data
            df = df.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                elif 'Time' in df.columns:
                    df = df.set_index('Time')
                df.index = pd.to_datetime(df.index)
            
            df = df.rename(columns={
                'open': 'Open', 'high': 'High',
                'low': 'Low', 'close': 'Close'
            })
            df = df[['Open', 'High', 'Low', 'Close']]
            
            # 🔍 ZOOM FIX: Show last 60 candles for better visibility
            # Daily: 60 candles = ~2 months | 4H: 10 days | 1H: 2.5 days
            df = df.tail(60)
            
            # Title
            # Determine direction from CHoCH
            if hasattr(setup, 'direction'):
                direction = setup.direction
            elif setup.daily_choch:
                # Bearish CHoCH means sell setup
                direction = 'sell' if setup.daily_choch.direction == 'bearish' else 'buy'
            else:
                direction = 'sell'  # Default
            
            emoji = '🟢' if direction == 'buy' else '🔴'
            strategy = setup.strategy_type.upper() if setup else ''
            rr = f"R:R 1:{setup.risk_reward:.1f}" if setup else ''
            
            title = f'{symbol} - {timeframe}'
            if setup:
                title += f'  {emoji} {strategy} - {rr}'
            
            # Plot with mplfinance
            fig, axlist = mpf.plot(
                df,
                type='candle',
                style=self.style,
                title=dict(
                    title=title,
                    color='#d1d4dc',  # Light gray text for dark background
                    fontsize=12,
                    weight='bold',
                    y=0.98  # Position title higher (default is 0.98, goes up to 1.0)
                ),
                ylabel='Price',
                volume=False,
                figsize=(12, 7),  # Increased height for more space at top
                returnfig=True,
                tight_layout=True
            )
            
            ax = axlist[0]
            
            # Set tick colors and ylabel color to light gray for visibility
            ax.tick_params(axis='both', colors='#d1d4dc', labelsize=9)
            ax.set_ylabel('Price', color='#d1d4dc', fontsize=10)
            
            # NO annotations - clean chart with only candles!
            # Removed: FVG zones, CHoCH markers, Entry/SL/TP lines
            
            # Save
            if save_path:
                if not os.path.isabs(save_path):
                    save_path = os.path.abspath(save_path)
                save_dir = os.path.dirname(save_path)
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                
                fig.savefig(save_path, dpi=100, bbox_inches='tight', 
                           facecolor=self.bg_color)
                plt.close(fig)
                return save_path
            else:
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=100, 
                           bbox_inches='tight', facecolor=self.bg_color)
                buf.seek(0)
                plt.close(fig)
                return buf.getvalue()
                
        except Exception as e:
            print(f"❌ Chart error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_4h_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup = None,
        save_path: Optional[str] = None
    ):
        """Create 4H chart - same as daily but with '4H' timeframe label"""
        return self.create_daily_chart(symbol, df, setup, save_path, timeframe="4H")
    
    def create_1h_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup = None,
        save_path: Optional[str] = None
    ):
        """Create 1H chart - same as daily but with '1H' timeframe label"""
        return self.create_daily_chart(symbol, df, setup, save_path, timeframe="1H")

