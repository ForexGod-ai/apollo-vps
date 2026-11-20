#!/usr/bin/env python3
"""
Clean Chart Generator - dark theme + cyan/purple candles + CHoCH break line (V52 Strat 3)
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
        timeframe: str = "Daily",
        chart_context: Optional[dict] = None,
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

            ctx = chart_context or {}
            anchor = ctx.get('poi_first_touch_time')
            df_full = df
            if anchor and timeframe.upper() == '4H':
                try:
                    from radar_gates import parse_radar_dt
                    adt = parse_radar_dt(anchor)
                    if adt is not None:
                        start_idx = 0
                        for i in range(len(df_full)):
                            if df_full.index[i] >= adt:
                                start_idx = max(0, i - 12)
                                break
                        df = df_full.iloc[start_idx:]
                        if len(df) > 180:
                            df = df.iloc[-180:]
                        if len(df) < 60:
                            df = df_full.iloc[-min(60, len(df_full)):]
                except Exception:
                    df = df_full.tail(60)
            else:
                df = df_full.tail(60)
            
            # Title — safe attrs (dict, TradeSetup, SimpleNamespace)
            if setup is None:
                direction = 'sell'
            elif getattr(setup, 'direction', None):
                direction = str(setup.direction).lower()
            elif getattr(setup, 'daily_choch', None):
                direction = (
                    'sell' if setup.daily_choch.direction == 'bearish' else 'buy'
                )
            else:
                direction = 'sell'

            emoji = '🟢' if direction in ('buy', 'long', 'bullish') else '🔴'
            strategy_raw = getattr(setup, 'strategy_type', None) if setup else None
            if strategy_raw is None and setup is not None and isinstance(setup, dict):
                strategy_raw = setup.get('strategy_type')
            strategy = str(strategy_raw or '').upper()
            rr_val = getattr(setup, 'risk_reward', None) if setup else None
            if rr_val is None and setup is not None and isinstance(setup, dict):
                rr_val = setup.get('risk_reward')
            rr = f"R:R 1:{float(rr_val):.1f}" if rr_val else ''
            
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

            break_px = None
            if setup is not None:
                if isinstance(setup, dict):
                    break_px = setup.get('choch_break_price')
                else:
                    break_px = getattr(setup, 'choch_break_price', None)
            sig_label = str(ctx.get('signal_label') or 'CHoCH 4H')
            if break_px is not None:
                try:
                    ax.axhline(
                        float(break_px),
                        color='#ff9800',
                        linestyle='--',
                        linewidth=1.2,
                        label=sig_label,
                    )
                except (TypeError, ValueError):
                    pass
            poi_top = ctx.get('poi_top')
            poi_bottom = ctx.get('poi_bottom')
            if poi_top is not None and poi_bottom is not None:
                try:
                    lo_p = float(min(poi_top, poi_bottom))
                    hi_p = float(max(poi_top, poi_bottom))
                    ax.axhspan(lo_p, hi_p, color='#2196f3', alpha=0.12, label='POI D1')
                except (TypeError, ValueError):
                    pass
            fib_top = ctx.get('fib_top')
            fib_bottom = ctx.get('fib_bottom')
            if fib_top is not None and fib_bottom is not None:
                try:
                    lo_f = float(min(fib_top, fib_bottom))
                    hi_f = float(max(fib_top, fib_bottom))
                    ax.axhspan(lo_f, hi_f, color='#4caf50', alpha=0.15, label='Fib 60–80%')
                except (TypeError, ValueError):
                    pass
            if break_px is not None or poi_top is not None or fib_top is not None:
                ax.legend(
                    loc='upper left',
                    fontsize=8,
                    facecolor='#1e222d',
                    labelcolor='#d1d4dc',
                )

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
        save_path: Optional[str] = None,
        chart_context: Optional[dict] = None,
    ):
        """Create 4H chart - same as daily but with '4H' timeframe label"""
        return self.create_daily_chart(
            symbol, df, setup, save_path, timeframe="4H", chart_context=chart_context,
        )
    
    def create_1h_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        setup = None,
        save_path: Optional[str] = None
    ):
        """Create 1H chart - same as daily but with '1H' timeframe label"""
        return self.create_daily_chart(symbol, df, setup, save_path, timeframe="1H")

