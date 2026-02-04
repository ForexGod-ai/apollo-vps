#!/usr/bin/env python3
"""
AUDIT: Test REVERSAL vs CONTINUATION Detection Logic
"""

import pandas as pd
import sys
sys.path.insert(0, '.')
from smc_detector import SMCDetector

# Test detection logic
detector = SMCDetector()

# Simulate CHoCH
class MockCHoCH:
    def __init__(self, direction, prev_trend, index):
        self.direction = direction
        self.previous_trend = prev_trend
        self.index = index
        self.break_price = 1.0

# Test cases
print('=' * 60)
print('AUDIT: REVERSAL vs CONTINUATION Detection')
print('=' * 60)

# Create test dataframe with price action
df_test = pd.DataFrame({
    'open': [1.1] * 100,
    'high': [1.12] * 100,
    'low': [1.08] * 100,
    'close': [1.09] * 100,
    'time': pd.date_range('2025-01-01', periods=100, freq='D')
})
df_test.set_index('time', inplace=True)

# Case 1: REVERSAL BULLISH (Bearish -> Bullish CHoCH)
print('\n1. BULLISH CHoCH + Previous BEARISH:')
print('   Expected: REVERSAL')
choch1 = MockCHoCH('bullish', 'bearish', 50)
result1 = detector.detect_strategy_type(df_test, choch1, None)
print(f'   Detected: {result1.upper()}')
status1 = 'CORRECT' if result1 == 'reversal' else 'WRONG'
print(f'   Status: {status1}')

# Case 2: CONTINUATION BEARISH (Bearish -> Bearish CHoCH)
print('\n2. BEARISH CHoCH + Previous BEARISH:')
print('   Expected: CONTINUATION')
choch2 = MockCHoCH('bearish', 'bearish', 50)
result2 = detector.detect_strategy_type(df_test, choch2, None)
print(f'   Detected: {result2.upper()}')
status2 = 'CORRECT' if result2 == 'continuation' else 'WRONG'
print(f'   Status: {status2}')

# Case 3: REVERSAL BEARISH (Bullish -> Bearish CHoCH)
print('\n3. BEARISH CHoCH + Previous BULLISH:')
print('   Expected: REVERSAL')
choch3 = MockCHoCH('bearish', 'bullish', 50)
result3 = detector.detect_strategy_type(df_test, choch3, None)
print(f'   Detected: {result3.upper()}')
status3 = 'CORRECT' if result3 == 'reversal' else 'WRONG'
print(f'   Status: {status3}')

# Case 4: CONTINUATION BULLISH (Bullish -> Bullish CHoCH)
print('\n4. BULLISH CHoCH + Previous BULLISH:')
print('   Expected: CONTINUATION')
choch4 = MockCHoCH('bullish', 'bullish', 50)
result4 = detector.detect_strategy_type(df_test, choch4, None)
print(f'   Detected: {result4.upper()}')
status4 = 'CORRECT' if result4 == 'continuation' else 'WRONG'
print(f'   Status: {status4}')

print('\n' + '=' * 60)
print('SUMMARY:')
correct = sum([
    result1 == 'reversal',
    result2 == 'continuation', 
    result3 == 'reversal',
    result4 == 'continuation'
])
print(f'   Correct: {correct}/4')
print(f'   Accuracy: {(correct/4)*100:.0f}%')

if correct == 4:
    print('   Result: ALL TESTS PASSED!')
else:
    print('   Result: DETECTION LOGIC HAS ISSUES!')
    
print('=' * 60)
