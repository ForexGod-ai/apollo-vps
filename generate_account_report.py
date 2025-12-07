#!/usr/bin/env python3
"""
📊 RAPORT COMPLET CONT cTRADER
Account: 9709773 (IC Markets Demo)
Data raport: 2025-12-07
"""

import json
from datetime import datetime
from collections import defaultdict
from loguru import logger

logger.info("="*80)
logger.info("📊 RAPORT COMPLET CONT cTRADER")
logger.info("="*80)

# Read trade history
with open('trade_history.json', 'r') as f:
    trades = json.load(f)

# Account info
INITIAL_BALANCE = 1000.0
account_id = "9709773"
broker = "IC Markets"
platform = "cTrader"
account_type = "Demo"

logger.info(f"\n🏦 INFORMAȚII CONT:")
logger.info(f"   Account ID: {account_id}")
logger.info(f"   Broker: {broker}")
logger.info(f"   Platform: {platform}")
logger.info(f"   Tip: {account_type}")
logger.info(f"   Sold inițial: ${INITIAL_BALANCE:.2f}")

# Current balance
total_profit = sum(trade['profit'] for trade in trades)
current_balance = INITIAL_BALANCE + total_profit

logger.info(f"\n💰 SOLD CURENT:")
logger.info(f"   Balance: ${current_balance:.2f}")
logger.info(f"   Profit total: ${total_profit:+.2f}")
logger.info(f"   Profit %: {(total_profit/INITIAL_BALANCE*100):+.2f}%")
logger.info(f"   Growth: {((current_balance/INITIAL_BALANCE - 1)*100):.2f}%")

# Trade statistics
logger.info(f"\n📈 STATISTICI TRANZACȚII:")
logger.info(f"   Total tranzacții: {len(trades)}")
logger.info(f"   Tranzacții închise: {len([t for t in trades if t['status'] == 'CLOSED'])}")
logger.info(f"   Tranzacții deschise: {len([t for t in trades if t['status'] == 'OPEN'])}")

# Win/Loss stats
winning_trades = [t for t in trades if t['profit'] > 0]
losing_trades = [t for t in trades if t['profit'] < 0]
breakeven_trades = [t for t in trades if t['profit'] == 0]

logger.info(f"\n🎯 WIN RATE:")
logger.info(f"   Winning trades: {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
logger.info(f"   Losing trades: {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
logger.info(f"   Breakeven: {len(breakeven_trades)}")
logger.success(f"   ✅ WIN RATE: {len(winning_trades)/len(trades)*100:.1f}%")

# Profit stats
if winning_trades:
    avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades)
    max_win = max(t['profit'] for t in winning_trades)
    logger.info(f"\n💚 PROFIT STATS:")
    logger.info(f"   Average win: ${avg_win:.2f}")
    logger.info(f"   Max win: ${max_win:.2f}")
    logger.info(f"   Total profit: ${sum(t['profit'] for t in winning_trades):.2f}")

if losing_trades:
    avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades)
    max_loss = min(t['profit'] for t in losing_trades)
    logger.info(f"\n❌ LOSS STATS:")
    logger.info(f"   Average loss: ${avg_loss:.2f}")
    logger.info(f"   Max loss: ${max_loss:.2f}")
    logger.info(f"   Total loss: ${sum(t['profit'] for t in losing_trades):.2f}")

# Symbol breakdown
symbols = defaultdict(lambda: {'count': 0, 'profit': 0, 'pips': 0})
for trade in trades:
    symbol = trade['symbol']
    symbols[symbol]['count'] += 1
    symbols[symbol]['profit'] += trade['profit']
    symbols[symbol]['pips'] += trade.get('pips', 0)

logger.info(f"\n📊 BREAKDOWN PE PERECHI:")
for symbol, stats in sorted(symbols.items(), key=lambda x: x[1]['profit'], reverse=True):
    logger.info(f"   {symbol}:")
    logger.info(f"      • Trades: {stats['count']}")
    logger.info(f"      • Profit: ${stats['profit']:+.2f}")
    logger.info(f"      • Pips: {stats['pips']:+.1f}")
    logger.info(f"      • Avg profit/trade: ${stats['profit']/stats['count']:.2f}")

# Direction breakdown
buy_trades = [t for t in trades if t['direction'] == 'BUY']
sell_trades = [t for t in trades if t['direction'] == 'SELL']

logger.info(f"\n📈 BREAKDOWN PE DIRECȚIE:")
logger.info(f"   BUY trades: {len(buy_trades)}")
logger.info(f"      • Profit: ${sum(t['profit'] for t in buy_trades):+.2f}")
logger.info(f"      • Win rate: {len([t for t in buy_trades if t['profit'] > 0])/len(buy_trades)*100:.1f}%")

if sell_trades:
    logger.info(f"   SELL trades: {len(sell_trades)}")
    logger.info(f"      • Profit: ${sum(t['profit'] for t in sell_trades):+.2f}")
    logger.info(f"      • Win rate: {len([t for t in sell_trades if t['profit'] > 0])/len(sell_trades)*100:.1f}%")

# Volume stats
total_volume = sum(trade['lot_size'] for trade in trades)
avg_volume = total_volume / len(trades)

logger.info(f"\n📊 VOLUME STATS:")
logger.info(f"   Total volume: {total_volume:.2f} lots")
logger.info(f"   Average volume: {avg_volume:.3f} lots")
logger.info(f"   Min volume: {min(t['lot_size'] for t in trades):.2f} lots")
logger.info(f"   Max volume: {max(t['lot_size'] for t in trades):.2f} lots")

# Time analysis
logger.info(f"\n⏰ PERIOADA TRADING:")
if trades:
    first_trade = min(trades, key=lambda x: x['open_time'])
    last_trade = max(trades, key=lambda x: x.get('close_time', x['open_time']))
    
    logger.info(f"   Prima tranzacție: {first_trade['open_time']}")
    logger.info(f"   Ultima tranzacție: {last_trade.get('close_time', last_trade['open_time'])}")
    
    # Parse dates
    start_date = datetime.fromisoformat(first_trade['open_time'])
    end_date = datetime.fromisoformat(last_trade.get('close_time', last_trade['open_time']))
    days = (end_date - start_date).days + 1
    
    logger.info(f"   Zile de trading: {days}")
    logger.info(f"   Trades/zi: {len(trades)/days:.1f}")
    logger.info(f"   Profit/zi: ${total_profit/days:.2f}")

# Risk stats
logger.info(f"\n⚠️  RISK MANAGEMENT:")
risk_per_trade = 0.02  # 2%
logger.info(f"   Risk per trade: {risk_per_trade*100}%")
logger.info(f"   Max risk: ${current_balance * risk_per_trade:.2f}")
logger.info(f"   Max drawdown permis: 20% = ${current_balance * 0.20:.2f}")
logger.info(f"   Max daily loss: 5% = ${current_balance * 0.05:.2f}")

# Best and worst trades
logger.info(f"\n🏆 BEST TRADES:")
best_trades = sorted(trades, key=lambda x: x['profit'], reverse=True)[:3]
for i, trade in enumerate(best_trades, 1):
    logger.success(f"   {i}. Ticket #{trade['ticket']}: {trade['symbol']} {trade['direction']}")
    logger.info(f"      Profit: ${trade['profit']:.2f} ({trade['pips']:.1f} pips)")
    logger.info(f"      Entry: {trade['entry_price']} → Exit: {trade['closing_price']}")

if losing_trades:
    logger.info(f"\n💔 WORST TRADES:")
    worst_trades = sorted(trades, key=lambda x: x['profit'])[:3]
    for i, trade in enumerate(worst_trades, 1):
        logger.error(f"   {i}. Ticket #{trade['ticket']}: {trade['symbol']} {trade['direction']}")
        logger.info(f"      Loss: ${trade['profit']:.2f} ({trade.get('pips', 0):.1f} pips)")
        logger.info(f"      Entry: {trade['entry_price']} → Exit: {trade['closing_price']}")

# Performance summary
logger.info(f"\n" + "="*80)
logger.success(f"📊 PERFORMANCE SUMMARY")
logger.info("="*80)
logger.success(f"💰 Balance: ${current_balance:.2f} (from ${INITIAL_BALANCE:.2f})")
logger.success(f"📈 Total Profit: ${total_profit:+.2f} ({(total_profit/INITIAL_BALANCE*100):+.2f}%)")
logger.success(f"🎯 Win Rate: {len(winning_trades)/len(trades)*100:.1f}% ({len(winning_trades)}/{len(trades)} trades)")
logger.success(f"📊 Total Trades: {len(trades)}")
logger.success(f"💎 Average Trade: ${total_profit/len(trades):.2f}")
logger.success(f"🎲 Risk/Reward: {avg_win/abs(avg_loss) if losing_trades else 'N/A':.2f}" if losing_trades else "🎲 Risk/Reward: N/A (no losses)")
logger.info("="*80)

# Save report to file
report_data = {
    'account_id': account_id,
    'broker': broker,
    'platform': platform,
    'account_type': account_type,
    'report_date': datetime.now().isoformat(),
    'balance': {
        'initial': INITIAL_BALANCE,
        'current': current_balance,
        'total_profit': total_profit,
        'growth_percent': (current_balance/INITIAL_BALANCE - 1) * 100
    },
    'statistics': {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': len(winning_trades)/len(trades)*100,
        'average_win': avg_win if winning_trades else 0,
        'average_loss': avg_loss if losing_trades else 0,
        'total_volume': total_volume
    },
    'symbols': dict(symbols),
    'direction': {
        'buy': {
            'count': len(buy_trades),
            'profit': sum(t['profit'] for t in buy_trades)
        },
        'sell': {
            'count': len(sell_trades),
            'profit': sum(t['profit'] for t in sell_trades) if sell_trades else 0
        }
    }
}

with open('account_report.json', 'w') as f:
    json.dump(report_data, f, indent=2)

logger.success("\n✅ Raport salvat în account_report.json")
