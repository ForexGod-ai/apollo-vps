"""
Chart Generator - ForexGod Trading AI
Standalone chart generation using mplfinance for professional candlestick charts
"""

import os
import io
from typing import Optional
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from datetime import datetime

from smc_detector import TradeSetup


class ChartGenerator:
    """Generate professional trading charts with SMC markers"""
    
    def __init__(self):
        """Initialize chart generator with mplfinance styling"""
        # TradingView style colors
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
            figcolor='white',
            edgecolor='white'
        )
    
    def create_daily_chart(
        self, 
        symbol: str,
        df: pd.DataFrame,
        setup: Optional[TradeSetup] = None,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Create Daily timeframe chart with CHoCH and FVG markers
        EXACT CA DIMINEAȚA - cu date pe axa X!
        """
        try:
            # Create figure - CA DIMINEAȚA
            fig, ax = plt.subplots(figsize=(10, 5.5))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            
            # IMPORTANT: Convert index to datetime if not already
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                df.index = pd.to_datetime(df.index)
            
            # Prepare data
            df = df.copy()
            df['body_high'] = df[['open', 'close']].max(axis=1)
            df['body_low'] = df[['open', 'close']].min(axis=1)
            
            # Create numeric x-axis for plotting
            x_positions = range(len(df))
            
            # Plot candlesticks - CA DIMINEAȚA (BODY FOARTE GROS!)
            for i, (idx, row) in enumerate(df.iterrows()):
                o = row['open']
                h = row['high']
                l = row['low']
                c = row['close']
                
                is_bullish = c >= o
                
                # Culori TradingView
                body_color = '#089981' if is_bullish else '#F23645'
                edge_color = '#089981' if is_bullish else '#F23645'
                wick_color = '#787B86'
                
                body_high = max(o, c)
                body_low = min(o, c)
                body_height = body_high - body_low
                
                # WICK-uri FOARTE SUBȚIRI (aproape invizibile ca dimineața)
                ax.plot([i, i], [l, h], color=wick_color, linewidth=0.8, alpha=0.5, zorder=1)
                
                # BODY FOARTE FOARTE GROS - WIDTH 0.95 (aproape 100%!)
                if body_height > 0.00001:
                    rect = Rectangle(
                        (i - 0.475, body_low),  # Aproape tot spațiul disponibil
                        0.95,  # WIDTH MAXIM - body-uri GROASE ca dimineața!
                        body_height,
                        facecolor=body_color,
                        edgecolor=edge_color,
                        linewidth=0,  # Fără border - doar fill solid
                        alpha=1.0,
                        zorder=2
                    )
                    ax.add_patch(rect)
                else:
                    # Doji - linie groasă
                    ax.plot([i-0.475, i+0.475], [o, o], color=body_color, linewidth=2.0, zorder=2)
            
            # SET AXIS LIMITS - ZOOM OPTIM pentru body-uri vizibile!
            ax.set_xlim(-1, len(df))
            
            # Y-axis cu zoom mai mare - să se vadă body-urile!
            price_range = df['high'].max() - df['low'].min()
            y_padding = price_range * 0.05  # Doar 5% padding (mai tight = body-uri mai mari)
            ax.set_ylim(df['low'].min() - y_padding, df['high'].max() + y_padding)
            
            # FORMAT X-AXIS CU DATE - CA DIMINEAȚA!
            num_ticks = 5  # Show 5 date labels
            tick_positions = [int(i * (len(df) - 1) / (num_ticks - 1)) for i in range(num_ticks)]
            tick_labels = [df.index[pos].strftime('%b-%d') for pos in tick_positions]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels, fontsize=9, color='#6C757D')
            
            # Titlu și styling
            ax.set_title(f'{symbol} - Daily', fontsize=12, color='#2E3338', pad=10, fontweight='normal')
            ax.set_xlabel('')
            ax.set_ylabel('', fontsize=10)
            ax.tick_params(labelsize=9, colors='#6C757D')
            
            # Grid mai vizibil CA DIMINEAȚA
            ax.grid(True, alpha=0.3, color='#E0E0E0', linestyle='-', linewidth=0.8)
            ax.set_axisbelow(True)
            
            # Save or return bytes
            if save_path:
                # Ensure directory exists
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                plt.tight_layout()
                plt.savefig(
                    save_path, 
                    format='png', 
                    facecolor='white',
                    dpi=120,  # DPI optim - nu prea mare, nu prea mic
                    bbox_inches='tight'
                )
                plt.close(fig)
                
                return save_path
            else:
                # Return bytes for Telegram
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(
                    buf, 
                    format='png', 
                    facecolor='white',
                    dpi=120,  # Consistent DPI
                    bbox_inches='tight'
                )
                buf.seek(0)
                plt.close(fig)
                
                return buf.getvalue()
        
        except Exception as e:
            print(f"❌ Error creating Daily chart for {symbol}: {e}")
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
        """
        Create 4H timeframe chart with microtrend and entry confirmation
        Similar to daily chart but focuses on 4H CHoCH
        """
        try:
            # Create figure - PROFESSIONAL WHITE STYLE
            fig, ax = plt.subplots(figsize=(12, 6))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            
            # Plot candlesticks - TRADITIONAL STYLE
            for i in range(len(df)):
                is_bullish = df['close'].iloc[i] >= df['open'].iloc[i]
                body_color = '#26A69A' if is_bullish else '#EF5350'
                wick_color = '#787B86'
                
                body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
                body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
                
                ax.add_patch(plt.Rectangle(
                    (i - 0.3, body_bottom), 
                    0.6, 
                    body_height if body_height > 0 else df['high'].iloc[i] * 0.0001,
                    facecolor=body_color, 
                    edgecolor=body_color, 
                    linewidth=1,
                    alpha=1.0
                ))
                
                ax.plot(
                    [i, i], 
                    [df['low'].iloc[i], df['high'].iloc[i]], 
                    color=wick_color, 
                    linewidth=1, 
                    alpha=0.8
                )
            
            # Mark Daily FVG zone (background)
            fvg_start = 0
            fvg_rect = Rectangle(
                (fvg_start, setup.fvg.bottom),
                width=len(df),
                height=setup.fvg.top - setup.fvg.bottom,
                facecolor='#2196F3', 
                alpha=0.15, 
                edgecolor='#2196F3', 
                linewidth=2, 
                linestyle='--', 
                label='Daily FVG Zone', 
                zorder=3
            )
            ax.add_patch(fvg_rect)
            
            # Mark 4H CHoCH if available
            if setup.h4_choch:
                choch_idx = setup.h4_choch.index
                ax.scatter(
                    choch_idx, 
                    df['close'].iloc[choch_idx], 
                    color='#9C27B0', 
                    s=400, 
                    marker='*', 
                    zorder=10, 
                    edgecolors='white', 
                    linewidths=2, 
                    label='4H CHoCH (Reversal)'
                )
            
            # Entry/SL/TP levels
            ax.axhline(y=setup.entry_price, color='#4CAF50', linestyle='-', linewidth=2.5, label='Entry', alpha=0.9, zorder=5)
            ax.axhline(y=setup.stop_loss, color='#F44336', linestyle='--', linewidth=2, label='Stop Loss', alpha=0.9, zorder=5)
            ax.axhline(y=setup.take_profit, color='#FFC107', linestyle='--', linewidth=2, label='Take Profit', alpha=0.9, zorder=5)
            
            # Styling
            ax.set_title(
                f'{symbol} - 4H Timeframe | Entry Confirmation', 
                color='#E0E3EB', 
                fontsize=18, 
                fontweight='bold', 
                pad=20
            )
            
            ax.set_xlabel('Candles', color='#787B86', fontsize=14, labelpad=10)
            ax.set_ylabel('Price', color='#787B86', fontsize=14, labelpad=10)
            ax.tick_params(colors='#787B86', labelsize=11)
            
            legend = ax.legend(
                loc='upper left', 
                facecolor='#1E222D', 
                edgecolor='#2962FF', 
                labelcolor='#D1D4DC', 
                fontsize=11, 
                framealpha=0.95
            )
            legend.get_frame().set_linewidth(2)
            
            ax.grid(True, alpha=0.15, color='#363A45', linestyle='-', linewidth=0.6)
            ax.set_axisbelow(True)
            
            fig.text(
                0.5, 0.02, 
                '🔥 ForexGod - Glitch in Matrix Strategy', 
                ha='center', 
                fontsize=12, 
                color='#787B86', 
                alpha=0.7,
                weight='bold'
            )
            
            # Save
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                plt.tight_layout()
                plt.savefig(save_path, format='png', facecolor='#0B0E11', dpi=300, bbox_inches='tight')
                plt.close(fig)
                return save_path
            else:
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format='png', facecolor='#0B0E11', dpi=200, bbox_inches='tight')
                buf.seek(0)
                plt.close(fig)
                return buf.getvalue()
        
        except Exception as e:
            print(f"❌ Error creating 4H chart for {symbol}: {e}")
            return None


if __name__ == "__main__":
    """Test chart generator"""
    import numpy as np
    
    print("🧪 Testing Chart Generator...")
    
    # Create fake data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    prices = 1.0850 + np.cumsum(np.random.normal(0, 0.005, 100))
    
    df = pd.DataFrame({
        'time': dates,
        'open': prices * (1 + np.random.normal(0, 0.001, 100)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.003, 100))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.003, 100))),
        'close': prices,
        'volume': np.random.uniform(1000, 5000, 100)
    })
    
    generator = ChartGenerator()
    
    # Test chart without setup
    chart_path = generator.create_daily_chart(
        symbol="EURUSD",
        df=df,
        setup=None,
        save_path="charts/test_chart.png"
    )
    
    if chart_path:
        print(f"✅ Test chart created: {chart_path}")
    else:
        print("❌ Chart creation failed")
