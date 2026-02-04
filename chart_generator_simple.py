#!/usr/bin/env python3
"""
Simple Chart Generator - Just dark theme + annotations
"""
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
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
            
            # Title
            direction = getattr(setup, 'direction', 'sell') if setup else ''
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
                title=title,
                ylabel='Price',
                volume=False,
                figsize=(12, 6),
                returnfig=True,
                tight_layout=True
            )
            
            ax = axlist[0]
            
            # Add annotations if setup exists
            if setup:
                self._add_simple_annotations(ax, df, setup)
            
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
    
    def _add_simple_annotations(self, ax, df, setup):
        """Add big visible annotations"""
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # FVG zone - purple rectangle
        if setup.fvg:
            rect = patches.Rectangle(
                (xlim[0], setup.fvg.bottom),
                xlim[1] - xlim[0],
                setup.fvg.top - setup.fvg.bottom,
                linewidth=2,
                edgecolor='#9c27b0',
                facecolor='#9c27b0',
                alpha=0.15,
                zorder=5
            )
            ax.add_patch(rect)
            
            ax.text(
                xlim[0] + 3, setup.fvg.middle, 'FVG',
                color='#9c27b0', fontsize=11, weight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#1e222d',
                         edgecolor='#9c27b0', linewidth=1.5, alpha=0.9),
                zorder=10
            )
        
        # CHoCH arrow
        if setup.daily_choch:
            choch_x = len(df) * 0.2
            choch_price = setup.daily_choch.break_price
            arrow_color = '#ef5350' if setup.direction == 'sell' else '#26a69a'
            
            if setup.direction == 'sell':
                arrow = FancyArrowPatch(
                    (choch_x, choch_price + (ylim[1] - ylim[0]) * 0.08),
                    (choch_x, choch_price + (ylim[1] - ylim[0]) * 0.02),
                    arrowstyle='->,head_width=0.8,head_length=0.8',
                    color=arrow_color, linewidth=2.5, zorder=10
                )
                label_y = choch_price + (ylim[1] - ylim[0]) * 0.10
            else:
                arrow = FancyArrowPatch(
                    (choch_x, choch_price - (ylim[1] - ylim[0]) * 0.08),
                    (choch_x, choch_price - (ylim[1] - ylim[0]) * 0.02),
                    arrowstyle='->,head_width=0.8,head_length=0.8',
                    color=arrow_color, linewidth=2.5, zorder=10
                )
                label_y = choch_price - (ylim[1] - ylim[0]) * 0.10
            
            ax.add_patch(arrow)
            ax.text(choch_x, label_y, 'CHoCH', color=arrow_color,
                   fontsize=10, weight='bold', ha='center',
                   bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e222d',
                            edgecolor=arrow_color, linewidth=1.5, alpha=0.95),
                   zorder=10)
        
        # Entry/SL/TP lines
        ax.axhline(setup.entry_price, color='#ff9800', linewidth=2, 
                   linestyle='-', alpha=0.9, zorder=8)
        ax.text(xlim[1] - 8, setup.entry_price, f' Entry: {setup.entry_price:.5f} ',
                color='#ff9800', fontsize=9, weight='bold', va='center',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e222d',
                         edgecolor='#ff9800', linewidth=1.5, alpha=0.95),
                zorder=10)
        
        ax.axhline(setup.stop_loss, color='#ef5350', linewidth=2,
                   linestyle='--', alpha=0.9, zorder=8)
        ax.text(xlim[1] - 8, setup.stop_loss, f' SL: {setup.stop_loss:.5f} ',
                color='#ef5350', fontsize=9, weight='bold', va='center',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e222d',
                         edgecolor='#ef5350', linewidth=1.5, alpha=0.95),
                zorder=10)
        
        ax.axhline(setup.take_profit, color='#26a69a', linewidth=2,
                   linestyle='--', alpha=0.9, zorder=8)
        ax.text(xlim[1] - 8, setup.take_profit, f' TP: {setup.take_profit:.5f} ',
                color='#26a69a', fontsize=9, weight='bold', va='center',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e222d',
                         edgecolor='#26a69a', linewidth=1.5, alpha=0.95),
                zorder=10)
