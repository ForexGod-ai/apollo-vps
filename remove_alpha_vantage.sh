#!/bin/bash
# Script automat pentru eliminarea Alpha Vantage după activarea cTrader ProtoOA
# RUN DOAR după ce toate testele trec!

set -e  # Exit on error

echo "🗑️  ELIMINARE ALPHA VANTAGE - SCRIPT AUTOMAT"
echo "=============================================="
echo ""

# Check if we're in the right directory
if [ ! -f "ctrader_data_client.py" ]; then
    echo "❌ ERROR: Run this from project root!"
    exit 1
fi

echo "⚠️  ATENȚIE: Acest script va șterge toate referințele la Alpha Vantage!"
echo ""
echo "Verifică că TOATE condițiile sunt îndeplinite:"
echo "  ✅ cTrader ProtoOA status = Active"
echo "  ✅ Test conexiune OK"
echo "  ✅ Toate 21 paritatile primesc date"
echo "  ✅ Scanner testat și funcțional"
echo "  ✅ Git backup făcut"
echo ""
read -p "Continui? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Anulat de user"
    exit 0
fi

echo ""
echo "🔍 Verificare pre-condiții..."

# Test cTrader connection
echo "   Testing cTrader data fetch..."
python3 -c "
from ctrader_data_client import get_ctrader_client
import sys

client = get_ctrader_client()
df = client.get_historical_data('GBPUSD', 'D1', 10)

if df is None or df.empty:
    print('❌ ERROR: Nu primesc date din cTrader!')
    sys.exit(1)
    
if 'Alpha Vantage' in str(df):
    print('❌ ERROR: Încă folosește Alpha Vantage!')
    sys.exit(1)

print('✅ cTrader data OK')
" || {
    echo "❌ Pre-condiții FAIL - STOP"
    exit 1
}

echo ""
echo "✅ Pre-condiții OK"
echo ""
echo "📦 Creating backup..."

# Git backup
git add -A
git commit -m "Backup before removing Alpha Vantage" || echo "Nothing to commit"
git tag -f before-alpha-removal
echo "✅ Backup created (tag: before-alpha-removal)"

echo ""
echo "🗑️  Removing Alpha Vantage references..."

# Create backup of ctrader_data_client.py
cp ctrader_data_client.py ctrader_data_client.py.backup

# Remove Alpha Vantage from ctrader_data_client.py
python3 << 'PYEOF'
import re

with open('ctrader_data_client.py', 'r') as f:
    content = f.read()

# Remove Alpha Vantage constant
content = re.sub(r'    # Alpha Vantage API.*\n    ALPHA_VANTAGE_BASE = ".*"\n', '', content)

# Remove Alpha Vantage symbols mapping
content = re.sub(r'    # Alpha Vantage symbol mapping.*?\n    }', '', content, flags=re.DOTALL)

# Remove alpha_vantage_key from __init__
content = re.sub(r"        self\.alpha_vantage_key = .*\n", '', content)

# Remove "Alpha Vantage backup" from logs
content = content.replace('-> Alpha Vantage backup', '')
content = content.replace('Priority: IC Markets WebSocket -> Alpha Vantage backup', 'Priority: IC Markets cTrader ProtoOA ONLY')

# Remove fallback to Alpha Vantage in get_historical_data
content = re.sub(
    r'            # Fallback to Alpha Vantage API.*?return None',
    '''            logger.error(f"❌ No data from cTrader for {symbol}")
            return None''',
    content,
    flags=re.DOTALL
)

# Remove _fetch_from_alpha_vantage function
content = re.sub(
    r'    def _fetch_from_alpha_vantage\(self.*?(?=\n    def |\nclass |\Z)',
    '',
    content,
    flags=re.DOTALL
)

# Clean up documentation
content = content.replace('NO Yahoo Finance, NO Twelve Data\nFallback hierarchy: IC Markets cTrader WebSocket -> Alpha Vantage API -> Error',
                         'NO external APIs - Direct IC Markets data via cTrader ProtoOA ONLY')

with open('ctrader_data_client.py', 'w') as f:
    f.write(content)

print("✅ ctrader_data_client.py cleaned")
PYEOF

# Remove Alpha Vantage key from .env
if grep -q "ALPHA_VANTAGE_API_KEY" .env 2>/dev/null; then
    sed -i.backup '/ALPHA_VANTAGE_API_KEY/d' .env
    echo "✅ Removed ALPHA_VANTAGE_API_KEY from .env"
fi

# Search for remaining references
echo ""
echo "🔍 Searching for remaining Alpha Vantage references..."
grep -r "Alpha Vantage" --include="*.py" . 2>/dev/null | grep -v ".backup" | grep -v "remove_alpha_vantage" || echo "✅ No Alpha Vantage references found"

echo ""
echo "✅ CLEANUP COMPLETE!"
echo ""
echo "📊 Next steps:"
echo "   1. Test scanner: python3 morning_strategy_scan.py"
echo "   2. Verify logs - no 'Alpha Vantage' should appear"
echo "   3. Commit: git add -A && git commit -m '✅ Removed Alpha Vantage'"
echo ""
echo "⚠️  Rollback (if needed): git reset --hard before-alpha-removal"
echo ""
