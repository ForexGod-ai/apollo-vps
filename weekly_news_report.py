"""
Weekly Forex News Report - ForexGod Trading System
Runs every Sunday at 21:00 to show all HIGH impact news for the coming week
Gives you a complete overview to plan your trading week
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List
from dotenv import load_dotenv
import logging

# Reuse NewsEvent and NewsCalendarMonitor from news_calendar_monitor
from news_calendar_monitor import NewsEvent, NewsCalendarMonitor

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyNewsReport(NewsCalendarMonitor):
    """Extended monitor for weekly reports"""
    
    def is_critical_event(self, event: NewsEvent) -> bool:
        """Check if event is critical based on keywords"""
        return any(keyword.lower() in event.event.lower() 
                  for keyword in self.critical_keywords)
    
    def _get_currency_flag(self, currency: str) -> str:
        """Get flag emoji for currency"""
        flags = {
            'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
            'AUD': '🇦🇺', 'NZD': '🇳🇿', 'CAD': '🇨🇦', 'CHF': '🇨🇭'
        }
        return flags.get(currency, '🏴')
    
    def format_weekly_telegram_message(self, events: List[NewsEvent]) -> str:
        """Format weekly news report for Telegram"""
        
        if not events:
            return """
📅 *WEEKLY FOREX NEWS REPORT*
🗓️ Week of {week_start}

✅ No high-impact news scheduled for next week
🟢 Clear trading conditions expected

━━━━━━━━━━━━━━━━━━━━
✨ *ForexGod Weekly News* ✨
🧠 _Glitch in Matrix Trading System_
""".format(week_start=datetime.now().strftime('%B %d, %Y'))
        
        # Sort events by time
        events.sort(key=lambda x: x.time)
        
        # Calculate week range
        today = datetime.now()
        week_start = today + timedelta(days=(7 - today.weekday()))  # Next Monday
        week_end = week_start + timedelta(days=6)  # Next Sunday
        
        message = "📅 *WEEKLY FOREX NEWS REPORT* 📅\n\n"
        message += f"🗓️ Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}\n"
        message += f"🔥 {len(events)} HIGH impact events scheduled\n"
        message += f"⏰ Generated: {datetime.now().strftime('%A, %b %d at %H:%M')}\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Group by day of week
        events_by_day = {}
        for event in events:
            day_key = event.time.strftime('%A, %B %d')  # "Monday, December 16"
            if day_key not in events_by_day:
                events_by_day[day_key] = []
            events_by_day[day_key].append(event)
        
        # Count critical events
        critical_count = sum(1 for e in events if self.is_critical_event(e))
        
        if critical_count > 0:
            message += f"⚠️ *{critical_count} CRITICAL EVENTS THIS WEEK*\n\n"
        
        # Format each day
        for day_label, day_events in events_by_day.items():
            # Day header
            message += f"📍 *{day_label}*\n"
            message += "─────────────────────\n"
            
            # Sort events by time within day
            day_events.sort(key=lambda x: x.time)
            
            for event in day_events:
                flag = self._get_currency_flag(event.currency)
                critical_marker = "⚠️ " if self.is_critical_event(event) else ""
                
                message += f"\n{critical_marker}{flag} *{event.currency}* - {event.event}\n"
                message += f"   🕐 {event.time.strftime('%H:%M')}\n"
                message += f"   🔴 Impact: *{event.impact}*\n"
                
                if event.forecast:
                    message += f"   📊 Forecast: `{event.forecast}`\n"
                if event.previous:
                    message += f"   📈 Previous: `{event.previous}`\n"
                
                # Add specific trading advice for critical events
                if self.is_critical_event(event):
                    if 'NFP' in event.event.upper() or 'PAYROLL' in event.event.upper():
                        message += f"   💥 *EXTREME VOLATILITY - Avoid USD pairs*\n"
                    elif 'FOMC' in event.event.upper() or 'FED' in event.event.upper():
                        message += f"   💥 *FED DECISION - Major USD impact*\n"
                    elif 'CPI' in event.event.upper() or 'INFLATION' in event.event.upper():
                        message += f"   📊 *Inflation data - High volatility*\n"
                    elif 'INTEREST RATE' in event.event.upper():
                        message += f"   💰 *Rate Decision - Avoid {event.currency} pairs*\n"
            
            message += "\n"
        
        # Weekly summary by currency
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "📊 *WEEKLY SUMMARY BY CURRENCY:*\n\n"
        
        currency_counts = {}
        for event in events:
            if event.currency not in currency_counts:
                currency_counts[event.currency] = {'total': 0, 'critical': 0}
            currency_counts[event.currency]['total'] += 1
            if self.is_critical_event(event):
                currency_counts[event.currency]['critical'] += 1
        
        # Sort by total events
        sorted_currencies = sorted(currency_counts.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for currency, counts in sorted_currencies:
            flag = self._get_currency_flag(currency)
            critical_marker = f" (⚠️ {counts['critical']} critical)" if counts['critical'] > 0 else ""
            message += f"{flag} *{currency}*: {counts['total']} events{critical_marker}\n"
        
        message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        message += "🎯 *TRADING STRATEGY FOR THE WEEK:*\n\n"
        
        # Give specific advice based on events
        if critical_count > 3:
            message += "⚠️ *HIGH VOLATILITY WEEK*\n"
            message += "• Be extra cautious with position sizing\n"
            message += "• Consider wider stop losses\n"
            message += "• Avoid trading 30min before/after major events\n"
        elif critical_count > 0:
            message += "⚡ *MODERATE VOLATILITY WEEK*\n"
            message += "• Standard risk management\n"
            message += "• Monitor news times closely\n"
            message += "• Close/reduce positions before critical events\n"
        else:
            message += "✅ *LOW NEWS WEEK*\n"
            message += "• Normal trading conditions\n"
            message += "• Focus on technical setups\n"
            message += "• Still monitor for unexpected news\n"
        
        message += "\n━━━━━━━━━━━━━━━━━━━━\n"
        message += "💡 *REMINDERS:*\n"
        message += "• Close trades 30min before major news\n"
        message += "• NFP, FOMC = avoid trading entirely\n"
        message += "• Check daily updates at 8am, 2pm, 8pm, 2am\n"
        message += "• Plan your week around these events\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "✨ *ForexGod Weekly News Report* ✨\n"
        message += "🧠 _Glitch in Matrix Trading System_\n"
        message += f"📅 _Next report: {(datetime.now() + timedelta(days=7)).strftime('%A, %b %d at 21:00')}_\n"
        
        return message.strip()
    
    def run_weekly_report(self):
        """Generate and send weekly news report"""
        logger.info("=" * 60)
        logger.info("📅 WEEKLY FOREX NEWS REPORT - STARTED")
        logger.info("=" * 60)
        
        # Try manual calendar first
        logger.info("📖 Loading manual calendar...")
        all_events = self.fetch_manual_calendar(days_ahead=7)
        
        # Fallback to ForexFactory if manual empty
        if not all_events:
            logger.info("⚠️ Manual calendar empty, trying ForexFactory...")
            all_events = self.fetch_forexfactory_calendar(days_ahead=7)
        
        # Filter for HIGH impact only
        high_impact_events = self.filter_high_impact_events(all_events)
        
        # Format weekly message
        message = self.format_weekly_telegram_message(high_impact_events)
        
        # Send to Telegram (use parent class method)
        success = self.send_telegram_alert(message)
        
        if success:
            logger.info(f"✅ Weekly report sent: {len(high_impact_events)} events")
        else:
            logger.error("❌ Failed to send weekly report")
        
        logger.info("=" * 60)
        return success


def main():
    """Main entry point"""
    try:
        reporter = WeeklyNewsReport()
        reporter.run_weekly_report()
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
