#!/usr/bin/env python3
"""
TradingView-style Chart Generator - Clean Version
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
import mplfinance as mpf
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
import io
import os


class ChartGenerator:
    """Generate professional TradingView-style charts"""
    
    def __init__(self, dark_theme: bool = True):
        """Initialize with simple color scheme"""
        self.dark_theme = dark_theme
        
        if dark_theme:
            # TradingView colors
            self.bg_color = '#131722'
            self.candle_bg = '#1e222d'
            self.text_color = '#d1d4dc'
            self.grid_color = '#363c4e'
            self.green = '#26a69a'
            self.red = '#ef5350'
        else:
            self.bg_color = 'white'
            self.candle_bg = 'white'
            self.text_color = 'black'
            self.grid_color = '#e0e0e0'
            self.green = '#26a69a'
            self.red = '#ef5350'
    
    def create_daily_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup = None,
        save_path: Optional[str] = None,
        timeframe: str = "Daily"
    ) -> Optional[str]:
        """
        Create clean candlestick chart with annotations
        
        Args:
            symbol: Trading pair
            df: OHLC DataFrame
            setup: TradeSetup object
            save_path: Output file path
            timeframe: Display timeframe
        """
        try:
            # Prepare data
            df = df.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                elif 'Time' in df.columns:
                    df = df.set_index('Time')
                df.index = pd.to_datetime(df.index)
            
            # Standardize columns
            df = df.rename(columns={
                'open': 'Open', 'high': 'High', 
                'low': 'Low', 'close': 'Close'
            })
            df = df[['Open', 'High', 'Low', 'Close']]
            
            # Create figure with explicit size and DPI
            plt.style.use('default')
            fig = plt.figure(figsize=(10, 5), dpi=100, facecolor=self.bg_color)
            ax = fig.add_subplot(111, facecolor=self.candle_bg)
            
            # Plot candlesticks manually
            self._plot_candlesticks(ax, df)
            
            # Add annotations if setup exists
            if setup:
                self._add_annotations(ax, df, setup)
            
            # Style the chart
            self._style_chart(ax, symbol, timeframe, setup)
            
            # Save
            if save_path:
                if not os.path.isabs(save_path):
                    save_path = os.path.abspath(save_path)
                save_dir = os.path.dirname(save_path)
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                
                fig.savefig(
                    save_path,
                    dpi=100,
                    bbox_inches='tight',
                    facecolor=self.bg_color,
                    pad_inches=0.2
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
                    pad_inches=0.2
                )
                buf.seek(0)
                plt.close(fig)
                return buf.getvalue()
                
        except Exception as e:
            print(f"❌ Error creating chart: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _plot_candlesticks(self, ax, df):
        """Plot ultra-thin candlesticks like original Telegram charts"""
        # Ultra-thin candles like in your screenshots
        body_width = 0.8
        wick_width = 0.8
        
        up_color = '#26a69a'
        down_color = '#ef5350'
        
        for idx, (date, row) in enumerate(df.iterrows()):
            o = row['Open']
            h = row['High']
            l = row['Low']
            c = row['Close']
            
            color = up_color if c >= o else down_color
            
            # Wick (thin line from low to high)
            ax.plot([idx, idx], [l, h], 
                   color=color, linewidth=wick_width, 
                   solid_capstyle='butt', zorder=1)
            
            # Body (very thin rectangle or line)
            body_h = abs(c - o)
            
            if body_h > 0.00001:  # Has body
                body_bottom = min(o, c)
                # Draw as thin filled rectangle
                ax.fill_between(
                    [idx - body_width/2, idx + body_width/2],
                    body_bottom, body_bottom + body_h,
                    color=color, linewidth=0, zorder=2
                )
            else:  # Doji - horizontal line
                ax.plot([idx - body_width/2, idx + body_width/2], 
                       [o, o], color=color, linewidth=1.5, 
                       solid_capstyle='butt', zorder=2)
        
        # Tight limits
        ax.set_xlim(-0.5, len(df) - 0.5)
        price_range = df['High'].max() - df['Low'].min()
        ax.set_ylim(
            df['Low'].min() - price_range * 0.02,
            df['High'].max() + price_range * 0.02
        )
    
    def _add_annotations(self, ax, df, setup):
        """Add LARGE visible FVG zone, CHoCH marker, Entry/SL/TP like TradingView"""
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # 1. FVG zone - HUGE PURPLE RECTANGLE (like in your screenshot)
        if setup.fvg:
            fvg_rect = patches.Rectangle(
                (xlim[0], setup.fvg.bottom),
                xlim[1] - xlim[0],  # Full width
                setup.fvg.top - setup.fvg.bottom,
                linewidth=2,
                edgecolor='#9c27b0',
                facecolor='#9c27b0',
                alpha=0.15,  # More visible
                linestyle='-',
                zorder=5
            )
            ax.add_patch(fvg_rect)
            
            # FVG label - LEFT side, large font
            ax.text(
                xlim[0] + 3, 
                setup.fvg.middle,
                'FVG', 
                color='#9c27b0', 
                fontsize=11, 
                weight='bold',
                bbox=dict(
                    boxstyle='round,pad=0.5', 
                    facecolor='#1e222d', 
                    edgecolor='#9c27b0', 
                    linewidth=1.5,
                    alpha=0.9
                ),
                zorder=10
            )
        
        # 2. CHoCH marker - BIG ARROW + TEXT (like TradingView)
        if setup.daily_choch:
            # Find approximate candle index for CHoCH (use 20% from left)
            choch_x = len(df) * 0.2
            choch_price = setup.daily_choch.break_price
            
            # Arrow pointing to CHoCH candle
            if setup.direction == 'sell':
                # Bearish CHoCH - red arrow DOWN
                arrow = patches.FancyArrowPatch(
                    (choch_x, choch_price + (ylim[1] - ylim[0]) * 0.08),
                    (choch_x, choch_price + (ylim[1] - ylim[0]) * 0.02),
                    arrowstyle='->,head_width=0.8,head_length=0.8',
                    color='#ef5350',
                    linewidth=2.5,
                    zorder=10
                )
            else:
                # Bullish CHoCH - green arrow UP
                arrow = patches.FancyArrowPatch(
                    (choch_x, choch_price - (ylim[1] - ylim[0]) * 0.08),
                    (choch_x, choch_price - (ylim[1] - ylim[0]) * 0.02),
                    arrowstyle='->,head_width=0.8,head_length=0.8',
                    color='#26a69a',
                    linewidth=2.5,
                    zorder=10
                )
            ax.add_patch(arrow)
            
            # CHoCH label above/below arrow
            arrow_color = '#ef5350' if setup.direction == 'sell' else '#26a69a'
            label_y = choch_price + (ylim[1] - ylim[0]) * 0.10 if setup.direction == 'sell' else choch_price - (ylim[1] - ylim[0]) * 0.10
            
            ax.text(
                choch_x, label_y,
                'CHoCH',
                color=arrow_color,
                fontsize=10,
                weight='bold',
                ha='center',
                bbox=dict(
                    boxstyle='round,pad=0.4',
                    facecolor='#1e222d',
                    edgecolor=arrow_color,
                    linewidth=1.5,
                    alpha=0.95
                ),
                zorder=10
            )
        
        # 3. Entry line - THICK ORANGE (like TradingView)
        ax.axhline(
            setup.entry_price, 
            color='#ff9800', 
            linewidth=2, 
            linestyle='-', 
            alpha=0.9,
            zorder=8
        )
        ax.text(
            xlim[1] - 8, 
            setup.entry_price, 
            f' Entry: {setup.entry_price:.5f} ',
            color='#ff9800', 
            fontsize=9, 
            weight='bold',
            va='center',
            bbox=dict(
                boxstyle='round,pad=0.4', 
                facecolor='#1e222d', 
                edgecolor='#ff9800', 
                linewidth=1.5,
                alpha=0.95
            ),
            zorder=10
        )
        
        # 4. SL line - THICK RED DASHED
        ax.axhline(
            setup.stop_loss, 
            color='#ef5350', 
            linewidth=2, 
            linestyle='--', 
            alpha=0.9,
            zorder=8
        )
        ax.text(
            xlim[1] - 8, 
            setup.stop_loss, 
            f' SL: {setup.stop_loss:.5f} ',
            color='#ef5350', 
            fontsize=9, 
            weight='bold',
            va='center',
            bbox=dict(
                boxstyle='round,pad=0.4', 
                facecolor='#1e222d', 
                edgecolor='#ef5350', 
                linewidth=1.5,
                alpha=0.95
            ),
            zorder=10
        )
        
        # 5. TP line - THICK GREEN DASHED
        ax.axhline(
            setup.take_profit, 
            color='#26a69a', 
            linewidth=2, 
            linestyle='--', 
            alpha=0.9,
            zorder=8
        )
        ax.text(
            xlim[1] - 8, 
            setup.take_profit, 
            f' TP: {setup.take_profit:.5f} ',
            color='#26a69a', 
            fontsize=9, 
            weight='bold',
            va='center',
            bbox=dict(
                boxstyle='round,pad=0.4', 
                facecolor='#1e222d', 
                edgecolor='#26a69a', 
                linewidth=1.5,
                alpha=0.95
            ),
            zorder=10
        )
    
    def _style_chart(self, ax, symbol, timeframe, setup):
        """Apply clean TradingView styling"""
        # Title
        direction = getattr(setup, 'direction', 'sell') if setup else ''
        emoji = '🟢' if direction == 'buy' else '🔴'
        strategy = setup.strategy_type.upper() if setup else ''
        rr = f"R:R 1:{setup.risk_reward:.1f}" if setup else ''
        
        title = f'{symbol} - {timeframe}'
        if setup:
            title += f'  {emoji} {strategy} - {rr}'
        
        ax.set_title(title, fontsize=13, color=self.text_color, 
                    weight='bold', pad=15)
        
        # Axis labels
        ax.set_xlabel('', fontsize=10, color=self.text_color)  # Hide for cleaner look
        ax.set_ylabel('Price', fontsize=10, color=self.text_color)
        
        # Minimal grid
        ax.grid(True, color=self.grid_color, linestyle=':', 
               linewidth=0.5, alpha=0.2, axis='y')
        
        # Spines - minimal
        for spine in ax.spines.values():
            spine.set_color(self.grid_color)
            spine.set_linewidth(0.5)
        
        # Ticks
        ax.tick_params(axis='both', colors=self.text_color, labelsize=9,
                      length=3, width=0.5)
        
        # Format X-axis to show dates
        n_bars = len(ax.get_xlim())
        if n_bars > 50:
            step = int(n_bars / 8)  # ~8 date labels
        else:
            step = max(5, int(n_bars / 6))
        
        # Clear x-axis for minimal look (like your Telegram charts)
        ax.set_xticks([])
        ax.set_xlabel('Date', fontsize=9, color=self.text_color, labelpad=10)
