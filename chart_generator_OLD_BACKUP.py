"""
Chart Generator - ForexGod Trading AI  
TradingView-Style Professional Charts with SMC Annotations
"""

import os
import io
from typing import Optional, List, Tuple
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D

from smc_detector import TradeSetup, FVG, CHoCH


class ChartGenerator:
    """Generate professional TradingView-style candlestick charts with SMC annotations"""
    
    def __init__(self, dark_theme: bool = True):
        """
        Initialize chart generator with TradingView styling
        
        Args:
            dark_theme: Use dark background like TradingView (default True)
        """
        self.dark_theme = dark_theme
        
        if dark_theme:
            # TradingView Dark Theme - clean version
            mc = mpf.make_marketcolors(
                up='#26a69a',      # Teal green
                down='#ef5350',    # Red
                edge={'up':'#26a69a', 'down':'#ef5350'},
                wick={'up':'#26a69a', 'down':'#ef5350'},
                volume='in'
            )
            
            self.style = mpf.make_mpf_style(
                marketcolors=mc,
                gridcolor='#363c4e',
                gridstyle='--',
                y_on_right=False,
                rc={
                    'font.size': 10,
                },
                facecolor='#1e222d',
                figcolor='#131722'
            )
            
            self.bg_color = '#131722'
            self.text_color = '#d1d4dc'
            self.grid_color = '#363c4e'
        else:
            # Light theme (original)
            self.style = mpf.make_mpf_style(
                base_mpf_style='classic',
                marketcolors=mpf.make_marketcolors(
                    up='#26a69a',
                    down='#ef5350',
                    edge='inherit',
                    wick='inherit',
                    volume='inherit',
                    alpha=1.0
                ),
                facecolor='white',
                figcolor='white',
                gridcolor='#E0E0E0',
                gridstyle='-',
                gridaxis='both'
            )
            self.bg_color = 'white'
            self.text_color = 'black'
            self.grid_color = '#E0E0E0'
    
    def _add_fvg_zone(self, ax, df: pd.DataFrame, fvg: FVG, alpha: float = 0.15):
        """
        Add FVG zone as shaded rectangle (like TradingView)
        
        Args:
            ax: Matplotlib axis
            df: DataFrame with DatetimeIndex
            fvg: FVG object with top/bottom/index
            alpha: Transparency (0-1)
        """
        try:
            # Get FVG start and end dates
            fvg_start_idx = fvg.index
            fvg_end_idx = len(df) - 1  # Extend to current candle
            
            if fvg_start_idx >= len(df):
                return
            
            fvg_start_date = df.index[fvg_start_idx]
            fvg_end_date = df.index[fvg_end_idx]
            
            # Color based on direction
            color = '#9c27b0' if fvg.direction == 'bullish' else '#9c27b0'  # Purple for both
            
            # Draw rectangle
            rect = patches.Rectangle(
                (fvg_start_date, fvg.bottom),
                fvg_end_date - fvg_start_date,
                fvg.top - fvg.bottom,
                linewidth=1,
                edgecolor=color,
                facecolor=color,
                alpha=alpha,
                linestyle='--'
            )
            ax.add_patch(rect)
            
            # Add FVG label
            mid_price = (fvg.top + fvg.bottom) / 2
            ax.text(
                fvg_end_date,
                mid_price,
                f'  FVG {fvg.direction.upper()}',
                color=color,
                fontsize=9,
                fontweight='bold',
                verticalalignment='center',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=self.bg_color, edgecolor=color, alpha=0.8)
            )
        except Exception as e:
            print(f"⚠️ Error adding FVG zone: {e}")
    
    def _add_choch_marker(self, ax, df: pd.DataFrame, choch: CHoCH):
        """
        Add CHoCH marker with arrow and label (like TradingView)
        
        Args:
            ax: Matplotlib axis
            df: DataFrame with DatetimeIndex
            choch: CHoCH object
        """
        try:
            if choch.index >= len(df):
                return
            
            choch_date = df.index[choch.index]
            choch_price = choch.break_price
            
            # Color and arrow based on direction
            if choch.direction == 'bullish':
                color = '#26a69a'  # Green
                arrow_y = choch_price - (choch_price * 0.002)  # Arrow below price
                va = 'top'
                arrow_props = dict(arrowstyle='->', color=color, lw=2)
            else:
                color = '#ef5350'  # Red
                arrow_y = choch_price + (choch_price * 0.002)  # Arrow above price
                va = 'bottom'
                arrow_props = dict(arrowstyle='->', color=color, lw=2)
            
            # Draw arrow
            ax.annotate(
                '',
                xy=(choch_date, choch_price),
                xytext=(choch_date, arrow_y),
                arrowprops=arrow_props
            )
            
            # Add CHoCH label
            ax.text(
                choch_date,
                arrow_y,
                f'CHoCH {choch.direction.upper()}',
                color=color,
                fontsize=9,
                fontweight='bold',
                ha='center',
                va=va,
                bbox=dict(boxstyle='round,pad=0.4', facecolor=self.bg_color, edgecolor=color, alpha=0.9)
            )
        except Exception as e:
            print(f"⚠️ Error adding CHoCH marker: {e}")
    
    def _add_trade_levels(self, ax, df: pd.DataFrame, setup: TradeSetup):
        """
        Add Entry, SL, TP horizontal lines (like TradingView)
        
        Args:
            ax: Matplotlib axis
            df: DataFrame with DatetimeIndex
            setup: TradeSetup with entry/sl/tp prices
        """
        try:
            start_date = df.index[0]
            end_date = df.index[-1]
            
            # Entry line (orange)
            ax.hlines(
                setup.entry_price,
                start_date,
                end_date,
                colors='#ff9800',
                linestyles='solid',
                linewidth=2,
                label=f'Entry: {setup.entry_price:.5f}'
            )
            
            # Stop Loss (red)
            ax.hlines(
                setup.stop_loss,
                start_date,
                end_date,
                colors='#f44336',
                linestyles='dashed',
                linewidth=1.5,
                label=f'SL: {setup.stop_loss:.5f}'
            )
            
            # Take Profit (green)
            ax.hlines(
                setup.take_profit,
                start_date,
                end_date,
                colors='#4caf50',
                linestyles='dashed',
                linewidth=1.5,
                label=f'TP: {setup.take_profit:.5f}'
            )
            
            # Add labels on the right
            ax.text(
                end_date,
                setup.entry_price,
                f'  {setup.entry_price:.5f}',
                color='#ff9800',
                fontsize=9,
                fontweight='bold',
                verticalalignment='center'
            )
            ax.text(
                end_date,
                setup.stop_loss,
                f'  SL {setup.stop_loss:.5f}',
                color='#f44336',
                fontsize=8,
                verticalalignment='center'
            )
            ax.text(
                end_date,
                setup.take_profit,
                f'  TP {setup.take_profit:.5f}',
                color='#4caf50',
                fontsize=8,
                verticalalignment='center'
            )
        except Exception as e:
            print(f"⚠️ Error adding trade levels: {e}")
    
    def create_daily_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup: Optional[TradeSetup] = None,
        save_path: Optional[str] = None,
        timeframe: str = "Daily",
        show_annotations: bool = True
    ) -> Optional[str]:
        """
        Create professional TradingView-style chart with SMC annotations
        
        Args:
            symbol: Trading pair symbol
            df: OHLC DataFrame
            setup: TradeSetup with FVG, CHoCH, entry/sl/tp
            save_path: File path to save (or None for BytesIO)
            timeframe: Timeframe label ("Daily", "4H", "1H")
            show_annotations: Add FVG zones, CHoCH markers, trade levels
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
            for col in ['Open', 'High', 'Low', 'Close']:
                if col not in df.columns:
                    raise ValueError(f"Missing column: {col}")
            df = df[['Open', 'High', 'Low', 'Close']]
            
            # Create chart title with strategy info
            title = f'{symbol} - {timeframe}'
            if setup:
                direction_emoji = '🟢' if setup.direction == 'buy' else '🔴'
                title += f'  {direction_emoji} {setup.strategy_type.upper()} - R:R 1:{setup.risk_reward:.1f}'
            
            # Plot candlestick chart
            fig, axlist = mpf.plot(
                df,
                type='candle',
                style=self.style,
                title=dict(title=title, fontsize=14, color=self.text_color, weight='bold'),
                ylabel='Price',
                ylabel_lower='',
                volume=False,
                figsize=(12, 6),
                tight_layout=True,
                returnfig=True,
                datetime_format='%b %d',
                xrotation=0
            )
            
            # Get main axis
            ax = axlist[0] if isinstance(axlist, list) else axlist
            
            # Add SMC annotations if setup provided
            if setup and show_annotations:
                # 1. Add FVG zone (purple rectangle)
                if setup.fvg:
                    self._add_fvg_zone(ax, df, setup.fvg)
                
                # 2. Add Daily CHoCH marker
                if setup.daily_choch:
                    self._add_choch_marker(ax, df, setup.daily_choch)
                
                # 3. Add 4H CHoCH marker (if exists)
                if setup.h4_choch:
                    self._add_choch_marker(ax, df, setup.h4_choch)
                
                # 4. Add Entry/SL/TP lines
                self._add_trade_levels(ax, df, setup)
            
            # Customize appearance
            ax.set_facecolor('#1e222d')
            fig.patch.set_facecolor(self.bg_color)
            ax.tick_params(axis='both', colors=self.text_color, labelsize=9)
            
            for spine in ax.spines.values():
                spine.set_color(self.grid_color)
            
            # Save or return
            if save_path:
                # Handle relative paths
                if not os.path.isabs(save_path):
                    save_path = os.path.abspath(save_path)
                
                # Create directory if needed
                save_dir = os.path.dirname(save_path)
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                
                fig.savefig(
                    save_path,
                    dpi=100,
                    bbox_inches='tight',
                    facecolor=self.bg_color,
                    edgecolor='none',
                    pad_inches=0.1
                )
                plt.close(fig)
                return save_path
            else:
                buf = io.BytesIO()
                fig.savefig(
                    buf,
                    format='png',
                    dpi=100,
                    bbox_inches='tight',
                    facecolor=self.bg_color,
                    edgecolor='none',
                    pad_inches=0.1
                )
                buf.seek(0)
                plt.close(fig)
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
        """Create 4H chart with correct title"""
        return self.create_daily_chart(symbol, df, setup, save_path, timeframe="4H")

    def create_1h_chart(
        self, 
        symbol: str,
        df: pd.DataFrame,
        setup: TradeSetup,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """Create 1H chart for SCALE_IN Entry 1 validation with correct title"""
        return self.create_daily_chart(symbol, df, setup, save_path, timeframe="1H")
