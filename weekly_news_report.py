"""
⛔ DEPRECATED — V10.4 NEWS SOURCE UNIFICATION
────────────────
🔱 ФорексГод — ФорексГод — Глитч Ин Матрикс 🔱

This module is DISABLED as of V10.4.
All news notifications now flow EXCLUSIVELY through:
  news_fetcher.py → data/upcoming_news.json → news_reminder_engine.py → Telegram

The weekly_news_report.py used a DIFFERENT data source (news_calendar_monitor)
which caused contradictory news data in Telegram. UNIFIED path only.

To re-enable (NOT recommended): remove the sys.exit() guard below.
────────────────
"""

import sys
import logging

logger = logging.getLogger(__name__)

# ═══ V10.4 KILL SWITCH — SINGLE NEWS SOURCE ENFORCEMENT ═══
logger.warning("⛔ weekly_news_report.py is DISABLED (V10.4 News Unification)")
logger.warning("   All news now flows through: news_fetcher.py → news_reminder_engine.py")
print("⛔ DEPRECATED: weekly_news_report.py disabled by V10.4 News Unification")
print("   Use news_fetcher.py + news_reminder_engine.py instead.")
sys.exit(0)
# ═══════════════════════════════════════════════════════════


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
        """Format weekly news report for Telegram - PREMIUM v5.0"""
        
        # ━━━━━━━━━━━━━━━━━━
        # PREMIUM SEPARATOR: 18 chars (consistent across all sections)
        # ━━━━━━━━━━━━━━━━━━
        SEPARATOR = "━━━━━━━━━━━━━━━━━━"
        
        if not events:
            return f"""📅 *WEEKLY REPORT*

🗓️ Week: {datetime.now().strftime('%b %d')}
✅ No high-impact news
🟢 Clear trading

{SEPARATOR}
✨ *Glitch in Matrix by ФорексГод* ✨
🧠 AI-Powered • 💎 Smart Money"""
        
        # Sort events by time
        events.sort(key=lambda x: x.time)
        
        # Calculate week range
        today = datetime.now()
        week_start = today + timedelta(days=(7 - today.weekday()))
        week_end = week_start + timedelta(days=6)
        
        # ━━━━━━━━━━━━━━━━━━━━━
        # HEADER SECTION
        # ━━━━━━━━━━━━━━━━━━━━━
        message = f"📅 *WEEKLY REPORT*\n\n"
        message += f"🗓️ {week_start.strftime('%b %d')}-{week_end.strftime('%b %d')}\n"
        message += f"🔥 {len(events)} HIGH impact\n"
        message += f"⏰ {datetime.now().strftime('%a %H:%M')}\n\n"
        message += f"{SEPARATOR}\n"
        
        # Count critical events
        critical_count = sum(1 for e in events if self.is_critical_event(e))
        if critical_count > 0:
            message += f"\n⚠️ *{critical_count} CRITICAL*\n"
        
        # ━━━━━━━━━━━━━━━━━━━━━
        # EVENTS BY DAY
        # ━━━━━━━━━━━━━━━━━━━━━
        
        # Group by day
        events_by_day = {}
        for event in events:
            day_key = event.time.strftime('%A, %B %d')
            if day_key not in events_by_day:
                events_by_day[day_key] = []
            events_by_day[day_key].append(event)
        
        # Format each day
        for day_label, day_events in events_by_day.items():
            message += f"\n📍 *{day_label}*\n"
            message += f"{SEPARATOR}\n\n"
            
            day_events.sort(key=lambda x: x.time)
            for event in day_events:
                flag = self._get_currency_flag(event.currency)
                critical_marker = "⚠️ " if self.is_critical_event(event) else ""
                
                message += f"{critical_marker}{flag} *{event.currency}* {event.event}\n"
                message += f"🕐 {event.time.strftime('%H:%M')}\n"
                
                if event.forecast:
                    message += f"📊 F: `{event.forecast}` P: `{event.previous or 'N/A'}`\n"
                
                # Warnings for critical events
                if self.is_critical_event(event):
                    if 'NFP' in event.event.upper():
                        message += "💥 *EXTREME VOL*\n"
                    elif 'FOMC' in event.event.upper():
                        message += "💥 *FED*\n"
                    elif 'CPI' in event.event.upper():
                        message += "📊 *INFLATION*\n"
                
                message += "\n"
        
        # ━━━━━━━━━━━━━━━━━━━━━
        # SUMMARY SECTION
        # ━━━━━━━━━━━━━━━━━━━━━
        message += f"{SEPARATOR}\n\n"
        message += "📊 *SUMMARY:*\n\n"
        
        currency_counts = {}
        for event in events:
            if event.currency not in currency_counts:
                currency_counts[event.currency] = {'total': 0, 'critical': 0}
            currency_counts[event.currency]['total'] += 1
            if self.is_critical_event(event):
                currency_counts[event.currency]['critical'] += 1
        
        sorted_currencies = sorted(currency_counts.items(), key=lambda x: x[1]['total'], reverse=True)
        for currency, counts in sorted_currencies:
            flag = self._get_currency_flag(currency)
            crit = f" ⚠️ {counts['critical']}" if counts['critical'] > 0 else ""
            message += f"{flag} {currency}: {counts['total']}{crit}\n"
        
        # ━━━━━━━━━━━━━━━━━━━━━
        # STRATEGY SECTION
        # ━━━━━━━━━━━━━━━━━━━━━
        message += f"\n{SEPARATOR}\n\n"
        message += "🎯 *STRATEGY:*\n\n"
        
        if critical_count > 3:
            message += "⚠️ HIGH VOL WEEK\n• Reduce sizing\n• Wider SL\n"
        elif critical_count > 0:
            message += "⚡ MODERATE\n• Standard risk\n• Close before news\n"
        else:
            message += "✅ LOW NEWS\n• Focus technicals\n"
        
        # ━━━━━━━━━━━━━━━━━━━━━
        # FOOTER SECTION
        # ━━━━━━━━━━━━━━━━━━━━━
        message += f"\n{SEPARATOR}\n\n"
        message += f"📅 Next: {(datetime.now() + timedelta(days=7)).strftime('%a %b %d')}\n\n"
        message += f"{SEPARATOR}\n"
        message += "✨ *Glitch in Matrix by ФорексГод* ✨\n"
        message += "🧠 AI-Powered • 💎 Smart Money"
        
        return message
    
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
