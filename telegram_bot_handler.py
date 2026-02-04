"""
Interactive Telegram Bot Handler for ForexGod Trading System
Handles two-way communication: commands, callbacks, and status reporting

Commands:
  /status - Account overview + open positions
  /summary - Weekly P&L report from SQLite
  /positions - Detailed list of open positions
  /balance - Account balance and equity
  /setups - Monitoring setups status
  /news - Upcoming high-impact news
  /help - Available commands

Author: ФорексГод
"""

import os
import sys
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from loguru import logger
import threading

# Telegram bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# Project imports
from news_calendar_monitor import NewsCalendarMonitor

load_dotenv()


class TradingBotHandler:
    """
    Interactive Telegram bot for trading system control
    Runs in background thread to not block trading execution
    """
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        
        # Database path
        self.db_path = 'data/trades.db'
        
        # News calendar integration
        try:
            self.news_monitor = NewsCalendarMonitor()
        except Exception as e:
            logger.warning(f"News monitor unavailable: {e}")
            self.news_monitor = None
        
        # Build application
        self.app = Application.builder().token(self.bot_token).build()
        
        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("summary", self.cmd_summary))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("setups", self.cmd_setups))
        self.app.add_handler(CommandHandler("news", self.cmd_news))
        
        # Callback query handler (for inline buttons)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("🤖 Telegram Bot Handler initialized")
    
    # ============================================================================
    # COMMAND HANDLERS
    # ============================================================================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        message = """
🚀 *GLITCH IN MATRIX - Trading Bot*

✨ Welcome, ФорексГод! ✨

I'm your AI-powered trading assistant. Here's what I can do:

📊 *Account Commands:*
/status - Full account overview
/balance - Balance & equity snapshot
/positions - All open positions
/summary - Weekly performance

🎯 *Trading Commands:*
/setups - Monitoring setups status
/news - High-impact news alerts

❓ *Help:*
/help - Show all commands

━━━━━━━━━━━━━━━━━━━━━━━━
💎 *Glitch in Matrix v3.2*
🧠 AI-Powered Smart Money Strategy
"""
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        message = """
📖 *AVAILABLE COMMANDS*

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *ACCOUNT MONITORING:*

/status
   └─ Full account dashboard
   └─ Open positions + P&L
   └─ Today's performance

/balance
   └─ Balance, Equity, Margin
   └─ Available margin

/positions
   └─ Detailed position list
   └─ Entry, Current, P&L
   └─ Break-even status

/summary
   └─ Weekly P&L report
   └─ Win rate & profit factor
   └─ Best/worst trades

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *TRADING STATUS:*

/setups
   └─ Active monitoring setups
   └─ READY vs MONITORING
   └─ Entry prices & R:R

/news
   └─ High-impact news (24-48h)
   └─ Currency exposure alerts
   └─ Trading recommendations

━━━━━━━━━━━━━━━━━━━━━━━━
💡 *TIPS:*

• Commands work anytime, anywhere
• Data updates every 30 seconds
• Use /status for quick overview

━━━━━━━━━━━━━━━━━━━━━━━━
✨ Strategy by ФорексГод ✨
"""
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - Full account dashboard"""
        try:
            message = self._generate_status_report()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /status: {e}")
            await update.message.reply_text(f"❌ Error generating status: {e}")
    
    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command - Weekly performance report"""
        try:
            message = self._generate_weekly_summary()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /summary: {e}")
            await update.message.reply_text(f"❌ Error generating summary: {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command - Detailed position list"""
        try:
            message = self._generate_positions_report()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /positions: {e}")
            await update.message.reply_text(f"❌ Error generating positions: {e}")
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command - Account balance snapshot"""
        try:
            message = self._generate_balance_report()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /balance: {e}")
            await update.message.reply_text(f"❌ Error generating balance: {e}")
    
    async def cmd_setups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setups command - Monitoring setups status"""
        try:
            message = self._generate_setups_report()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /setups: {e}")
            await update.message.reply_text(f"❌ Error generating setups: {e}")
    
    async def cmd_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /news command - High-impact news alerts"""
        try:
            message = self._generate_news_report()
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in /news: {e}")
            await update.message.reply_text(f"❌ Error generating news: {e}")
    
    async def handle_callback(self, query_update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = query_update.callback_query
        await query.answer()
        
        # Parse callback data
        data = query.data
        
        if data == "refresh_status":
            message = self._generate_status_report()
            await query.message.edit_text(message, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "refresh_positions":
            message = self._generate_positions_report()
            await query.message.edit_text(message, parse_mode=ParseMode.MARKDOWN)
        
        elif data.startswith("close_"):
            # Extract symbol from callback data
            symbol = data.replace("close_", "")
            await query.message.reply_text(
                f"⚠️ Manual position closing not yet implemented.\n"
                f"Please close {symbol} via cTrader or MetaTrader."
            )
    
    # ============================================================================
    # REPORT GENERATORS
    # ============================================================================
    
    def _generate_status_report(self) -> str:
        """Generate full status report with account + positions + today's performance"""
        try:
            # Read trade_history.json
            with open('trade_history.json', 'r') as f:
                data = json.load(f)
            
            account = data.get('account', {})
            positions = data.get('open_positions', [])
            
            balance = account.get('balance', 0)
            equity = account.get('equity', 0)
            margin_used = account.get('margin_used', 0)
            free_margin = account.get('free_margin', 0)
            
            # Calculate P&L
            total_pnl = equity - balance
            pnl_percent = (total_pnl / balance * 100) if balance > 0 else 0
            pnl_emoji = "🟢" if total_pnl > 0 else ("🔴" if total_pnl < 0 else "⚪")
            
            # Get today's performance from SQLite
            today_stats = self._get_today_performance()
            
            # Build message
            message = f"""
📊 *ACCOUNT STATUS*

━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Account Overview:*
Balance: `${balance:,.2f}`
Equity: `${equity:,.2f}`
P&L: `${total_pnl:+,.2f}` ({pnl_percent:+.2f}%) {pnl_emoji}

📊 *Margin:*
Used: `${margin_used:,.2f}` ({margin_used/balance*100:.1f}%)
Free: `${free_margin:,.2f}`

━━━━━━━━━━━━━━━━━━━━━━━━
🔥 *Open Positions: {len(positions)}*
"""
            
            # Add position summary
            if positions:
                winners = [p for p in positions if p.get('profit', 0) > 0]
                losers = [p for p in positions if p.get('profit', 0) < 0]
                
                message += f"\n💚 Winning: {len(winners)}"
                message += f"\n❤️ Losing: {len(losers)}"
                
                # Top 3 positions by P&L
                sorted_positions = sorted(positions, key=lambda p: p.get('profit', 0), reverse=True)
                message += f"\n\n*Top Positions:*"
                
                for i, pos in enumerate(sorted_positions[:3], 1):
                    symbol = pos.get('symbol', 'Unknown')
                    direction = pos.get('direction', 'buy').upper()
                    profit = pos.get('profit', 0)
                    emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                    
                    message += f"\n{i}. `{symbol}` {direction} | `${profit:+.2f}` {emoji}"
            else:
                message += "\n_No open positions_"
            
            # Today's performance
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n📈 *Today's Performance:*"
            message += f"\n{today_stats}"
            
            # Monitoring setups
            setups = self._get_monitoring_setups()
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n📋 *Monitoring Setups: {len(setups)}*"
            
            ready_setups = [s for s in setups if s.get('status') == 'READY']
            monitoring_setups = [s for s in setups if s.get('status') == 'MONITORING']
            
            if ready_setups:
                message += f"\n🟢 Ready to execute: {len(ready_setups)}"
            if monitoring_setups:
                message += f"\n⏳ Monitoring: {len(monitoring_setups)}"
            
            # High-impact news alert
            news_alert = self._get_news_alert_summary()
            if news_alert:
                message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                message += f"\n{news_alert}"
            
            # Footer
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            message += f"\n✨ *Strategy by ФорексГод* ✨"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating status report: {e}")
            return f"❌ Error: {e}"
    
    def _generate_weekly_summary(self) -> str:
        """Generate weekly P&L summary from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get trades from last 7 days
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(profit) as total_profit,
                    AVG(profit) as avg_profit,
                    MAX(profit) as best_trade,
                    MIN(profit) as worst_trade
                FROM closed_trades
                WHERE DATE(close_time) >= ?
            """, (seven_days_ago,))
            
            stats = cursor.fetchone()
            total_trades, wins, losses, total_profit, avg_profit, best_trade, worst_trade = stats
            
            # Calculate metrics
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            # Get daily breakdown
            cursor.execute("""
                SELECT 
                    DATE(close_time) as date,
                    COUNT(*) as trades,
                    SUM(profit) as profit
                FROM closed_trades
                WHERE DATE(close_time) >= ?
                GROUP BY DATE(close_time)
                ORDER BY date DESC
            """, (seven_days_ago,))
            
            daily_stats = cursor.fetchall()
            
            # Get best/worst symbols
            cursor.execute("""
                SELECT 
                    symbol,
                    COUNT(*) as trades,
                    SUM(profit) as profit
                FROM closed_trades
                WHERE DATE(close_time) >= ?
                GROUP BY symbol
                ORDER BY profit DESC
                LIMIT 3
            """, (seven_days_ago,))
            
            top_symbols = cursor.fetchall()
            
            conn.close()
            
            # Build message
            profit_emoji = "🟢" if total_profit > 0 else ("🔴" if total_profit < 0 else "⚪")
            
            message = f"""
💰 *WEEKLY PERFORMANCE REPORT*

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Overall Stats (Last 7 Days):*

Total Profit: `${total_profit:+,.2f}` {profit_emoji}
Total Trades: `{total_trades}`
Wins: `{wins}` ✅ | Losses: `{losses}` ❌
Win Rate: `{win_rate:.1f}%`

Average: `${avg_profit:.2f}`
Best Trade: `${best_trade:.2f}` 💎
Worst Trade: `${worst_trade:.2f}` 

━━━━━━━━━━━━━━━━━━━━━━━━
📅 *Daily Breakdown:*
"""
            
            for date, trades, profit in daily_stats:
                day_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                message += f"\n`{date}`: {trades} trades | `${profit:+.2f}` {day_emoji}"
            
            if top_symbols:
                message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                message += f"\n🏆 *Top Performing Pairs:*\n"
                
                for symbol, trades, profit in top_symbols:
                    emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                    message += f"\n`{symbol}`: {trades} trades | `${profit:+.2f}` {emoji}"
            
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            message += f"\n✨ *Strategy by ФорексГод* ✨"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")
            return f"❌ Error: {e}"
    
    def _generate_positions_report(self) -> str:
        """Generate detailed positions report"""
        try:
            with open('trade_history.json', 'r') as f:
                data = json.load(f)
            
            positions = data.get('open_positions', [])
            
            if not positions:
                return """
📊 *OPEN POSITIONS*

━━━━━━━━━━━━━━━━━━━━━━━━
_No open positions_

✨ Market is waiting for your next move! 🎯
"""
            
            message = f"""
📊 *OPEN POSITIONS* ({len(positions)})

━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # Sort by profit (highest first)
            sorted_positions = sorted(positions, key=lambda p: p.get('profit', 0), reverse=True)
            
            for i, pos in enumerate(sorted_positions, 1):
                symbol = pos.get('symbol', 'Unknown')
                direction = pos.get('direction', 'buy').upper()
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                profit = pos.get('profit', 0)
                volume = pos.get('volume', 0)
                
                # Calculate pips
                pip_value = 0.01 if 'JPY' in symbol else 0.0001
                pips = (current - entry) / pip_value if direction == 'BUY' else (entry - current) / pip_value
                
                # Emoji indicators
                profit_emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                direction_emoji = "📈" if direction == 'BUY' else "📉"
                
                # Break-even status (simplified check)
                is_breakeven = "🛡️ BE" if profit > 20 else ""  # Rough estimate
                
                message += f"""
*{i}. {symbol}* {direction_emoji} {direction}
├─ Entry: `{entry:.5f}`
├─ Current: `{current:.5f}`
├─ P&L: `${profit:+.2f}` ({pips:+.1f} pips) {profit_emoji}
├─ Volume: `{volume:.2f}` lots
└─ Status: {is_breakeven if is_breakeven else "Active 🕒"}
"""
            
            message += f"\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            message += f"\n✨ *Strategy by ФорексГод* ✨"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating positions report: {e}")
            return f"❌ Error: {e}"
    
    def _generate_balance_report(self) -> str:
        """Generate balance snapshot"""
        try:
            with open('trade_history.json', 'r') as f:
                data = json.load(f)
            
            account = data.get('account', {})
            
            balance = account.get('balance', 0)
            equity = account.get('equity', 0)
            margin_used = account.get('margin_used', 0)
            free_margin = account.get('free_margin', 0)
            margin_level = account.get('margin_level', 0)
            
            total_pnl = equity - balance
            pnl_percent = (total_pnl / balance * 100) if balance > 0 else 0
            pnl_emoji = "🟢" if total_pnl > 0 else ("🔴" if total_pnl < 0 else "⚪")
            
            # Margin level indicator
            if margin_level > 300:
                margin_status = "🟢 Healthy"
            elif margin_level > 150:
                margin_status = "🟡 Moderate"
            else:
                margin_status = "🔴 Warning"
            
            message = f"""
💰 *ACCOUNT BALANCE*

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Current Status:*

Balance: `${balance:,.2f}`
Equity: `${equity:,.2f}`
Floating P&L: `${total_pnl:+,.2f}` {pnl_emoji}
P&L %: `{pnl_percent:+.2f}%`

━━━━━━━━━━━━━━━━━━━━━━━━
📈 *Margin Info:*

Used: `${margin_used:,.2f}`
Free: `${free_margin:,.2f}`
Level: `{margin_level:.0f}%` {margin_status}
Usage: `{margin_used/balance*100:.1f}%` of balance

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Updated: {datetime.now().strftime('%H:%M:%S')}
✨ *Strategy by ФорексГод* ✨
"""
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating balance report: {e}")
            return f"❌ Error: {e}"
    
    def _generate_setups_report(self) -> str:
        """Generate monitoring setups report"""
        try:
            setups = self._get_monitoring_setups()
            
            if not setups:
                return """
📋 *MONITORING SETUPS*

━━━━━━━━━━━━━━━━━━━━━━━━
_No active setups_

🔍 Scanner will find opportunities soon! 
✨ Patience is key to profitable trading.
"""
            
            ready_setups = [s for s in setups if s.get('status') == 'READY']
            monitoring_setups = [s for s in setups if s.get('status') == 'MONITORING']
            
            message = f"""
📋 *MONITORING SETUPS* ({len(setups)})

━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            if ready_setups:
                message += f"\n🟢 *READY TO EXECUTE* ({len(ready_setups)}):\n"
                
                for setup in ready_setups:
                    symbol = setup.get('symbol', 'Unknown')
                    direction = setup.get('direction', 'buy').upper()
                    entry = setup.get('entry_price', 0)
                    rr = setup.get('risk_reward', 0)
                    
                    direction_emoji = "📈" if direction == 'BUY' else "📉"
                    
                    message += f"\n• `{symbol}` {direction_emoji} {direction}"
                    message += f"\n  Entry: `{entry:.5f}` | R:R `1:{rr:.1f}`"
            
            if monitoring_setups:
                message += f"\n\n⏳ *MONITORING* ({len(monitoring_setups)}):\n"
                
                for setup in monitoring_setups:
                    symbol = setup.get('symbol', 'Unknown')
                    direction = setup.get('direction', 'buy').upper()
                    entry = setup.get('entry_price', 0)
                    
                    direction_emoji = "📈" if direction == 'BUY' else "📉"
                    
                    message += f"\n• `{symbol}` {direction_emoji} {direction}"
                    message += f"\n  Waiting for confirmation..."
            
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            message += f"\n✨ *Strategy by ФорексГод* ✨"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating setups report: {e}")
            return f"❌ Error: {e}"
    
    def _generate_news_report(self) -> str:
        """Generate high-impact news report"""
        try:
            if not self.news_monitor:
                return """
📰 *HIGH-IMPACT NEWS*

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ _News monitor not available_

Please check economic_calendar.json manually.
"""
            
            # Fetch upcoming news (next 48 hours)
            news_events = self._get_upcoming_high_impact_news()
            
            if not news_events:
                return """
📰 *HIGH-IMPACT NEWS*

━━━━━━━━━━━━━━━━━━━━━━━━
✅ _No high-impact news in next 48 hours_

🎯 Safe to trade all pairs!
💡 Always check before NFP/FOMC days.
"""
            
            message = f"""
📰 *HIGH-IMPACT NEWS* (Next 48h)

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Upcoming Events:*
"""
            
            for event in news_events[:10]:  # Show max 10 events
                time_str = event['time'].strftime('%a %H:%M')
                currency = event['currency']
                impact = event['impact']
                title = event['event']
                
                impact_emoji = "🔴" if impact == 'HIGH' else ("🟡" if impact == 'MEDIUM' else "🟢")
                
                message += f"\n\n{impact_emoji} *{currency}* - {time_str}"
                message += f"\n   {title}"
            
            # Add trading recommendations
            affected_currencies = set(e['currency'] for e in news_events)
            
            if affected_currencies:
                message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                message += f"\n⚠️ *Affected Currencies:*"
                message += f"\n{', '.join(affected_currencies)}"
                message += f"\n\n💡 *Recommendation:*"
                message += f"\nAvoid trading these pairs before news release."
                message += f"\nConsider closing positions 30min before."
            
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            message += f"\n✨ *Strategy by ФорексГод* ✨"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"Error generating news report: {e}")
            return f"❌ Error: {e}"
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_today_performance(self) -> str:
        """Get today's trading performance from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as trades,
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(profit) as profit
                FROM closed_trades
                WHERE DATE(close_time) = ?
            """, (today,))
            
            stats = cursor.fetchone()
            conn.close()
            
            trades, wins, profit = stats
            
            if trades == 0:
                return "No trades closed today"
            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
            
            return f"Trades: `{trades}` | Wins: `{wins}` | P&L: `${profit:+.2f}` {emoji}"
        
        except Exception as e:
            logger.error(f"Error getting today's performance: {e}")
            return "Error loading today's stats"
    
    def _get_monitoring_setups(self) -> List[Dict]:
        """Load monitoring setups from monitoring_setups.json"""
        try:
            with open('monitoring_setups.json', 'r') as f:
                data = json.load(f)
            return data.get('setups', [])
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Error loading setups: {e}")
            return []
    
    def _get_news_alert_summary(self) -> Optional[str]:
        """Get brief news alert for status report"""
        try:
            news = self._get_upcoming_high_impact_news()
            
            if not news:
                return None
            
            # Count high-impact events in next 24h
            high_impact = [e for e in news if e['impact'] == 'HIGH']
            
            if not high_impact:
                return None
            
            return f"⚠️ *{len(high_impact)} High-Impact News* in next 24h\n_Use /news for details_"
        
        except Exception as e:
            return None
    
    def _get_upcoming_high_impact_news(self) -> List[Dict]:
        """Get high-impact news events from calendar"""
        try:
            # Try to load from economic_calendar.json
            with open('economic_calendar.json', 'r') as f:
                calendar = json.load(f)
            
            events = calendar.get('events', [])
            
            # Filter high-impact events in next 48 hours
            now = datetime.now()
            cutoff = now + timedelta(hours=48)
            
            high_impact = []
            for event in events:
                # Parse time string
                try:
                    event_time = datetime.fromisoformat(event.get('time', ''))
                    
                    if now <= event_time <= cutoff:
                        impact = event.get('impact', 'LOW')
                        if impact in ['HIGH', 'MEDIUM']:
                            high_impact.append({
                                'time': event_time,
                                'currency': event.get('currency', 'N/A'),
                                'impact': impact,
                                'event': event.get('event', 'Unknown')
                            })
                except:
                    continue
            
            # Sort by time
            high_impact.sort(key=lambda e: e['time'])
            
            return high_impact
        
        except Exception as e:
            logger.warning(f"Could not load news calendar: {e}")
            return []
    
    # ============================================================================
    # BOT LIFECYCLE
    # ============================================================================
    
    def run_async(self):
        """Run bot in async mode (blocking)"""
        logger.info("🚀 Starting Telegram bot (async mode)...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def run_background(self):
        """Run bot in background thread (non-blocking)"""
        def bot_thread():
            logger.info("🚀 Starting Telegram bot in background thread...")
            asyncio.run(self.app.run_polling(allowed_updates=Update.ALL_TYPES))
        
        thread = threading.Thread(target=bot_thread, daemon=True)
        thread.start()
        logger.success("✅ Telegram bot running in background")
        return thread


# ============================================================================
# STANDALONE EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Run bot in standalone mode (for testing)
    """
    print("🤖 Telegram Bot Handler - ForexGod Trading System")
    print("=" * 60)
    
    try:
        bot = TradingBotHandler()
        print("✅ Bot initialized successfully")
        print("🚀 Starting bot polling...")
        print("💡 Send /start to your Telegram bot to test")
        print("=" * 60)
        
        bot.run_async()  # Run in blocking mode
    
    except KeyboardInterrupt:
        print("\n⏹️  Bot stopped by user")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
