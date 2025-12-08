#!/usr/bin/env python3
"""
Verificare LIVE: Toate simbolurile din pairs_config.json sunt accesibile în cTrader?
Testează mapping-ul și raportează ce simboluri lipsesc.
"""

import json
from ctrader_data_client import CTraderDataClient

def verify_all_symbols():
    """Verifică toate simbolurile LIVE în cTrader"""
    
    print("\n" + "="*70)
    print("🔍 VERIFICARE LIVE: Simboluri cTrader IC Markets")
    print("="*70 + "\n")
    
    # Load pairs config
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
    
    # Extract actual pairs (it's a list)
    pairs_list = config.get('pairs', [])
    
    print(f"📋 Găsite {len(pairs_list)} perechi în config\n")
    
    # Initialize cTrader client
    print("📡 Conectare la cTrader IC Markets...")
    client = CTraderDataClient()
    
    # Symbol mapping (same as in PythonSignalExecutor.cs)
    def map_symbol(python_symbol):
        """Map Python symbol names to cTrader names"""
        if python_symbol == "PIUSDT":
            return None  # Disabled
        if python_symbol == "USOIL":
            return "WTIUSD"  # Oil mapping
        return python_symbol
    
    # Test each symbol
    results = {
        'working': [],
        'mapped': [],
        'missing': [],
        'disabled': []
    }
    
    for python_symbol in pairs_list:
        # Extract symbol name from dict
        symbol_name = python_symbol.get('symbol', python_symbol)
        ctrader_symbol = map_symbol(symbol_name)
        
        if ctrader_symbol is None:
            results['disabled'].append(symbol_name)
            print(f"⚫ {symbol_name:12} → DISABLED (nu există în IC Markets)")
            continue
        
        # Test if symbol exists in cTrader
        print(f"🔄 Testing {symbol_name:12} → {ctrader_symbol:12}...", end=" ")
        
        try:
            # Try to get symbol data
            data = client.get_historical_data(ctrader_symbol, "H1", 10)
            
            if data is not None and len(data) > 0:
                if symbol_name != ctrader_symbol:
                    results['mapped'].append((symbol_name, ctrader_symbol))
                    print(f"✅ MAPPED & WORKING")
                else:
                    results['working'].append(symbol_name)
                    print(f"✅ WORKING")
            else:
                results['missing'].append(symbol_name)
                print(f"❌ NOT FOUND")
        except Exception as e:
            results['missing'].append(symbol_name)
            print(f"❌ ERROR: {str(e)[:50]}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 RAPORT FINAL")
    print("="*70 + "\n")
    
    total_active = len(results['working']) + len(results['mapped'])
    total_configured = len(pairs_list)
    
    print(f"✅ SIMBOLURI FUNCȚIONALE: {total_active}/{total_configured}")
    print(f"   └─ Direct (fără mapping): {len(results['working'])}")
    print(f"   └─ Cu mapping: {len(results['mapped'])}")
    
    if results['mapped']:
        print(f"\n🔄 MAPPED SYMBOLS ({len(results['mapped'])}):")
        for py_sym, ct_sym in results['mapped']:
            print(f"   • {py_sym} → {ct_sym}")
    
    if results['disabled']:
        print(f"\n⚫ DISABLED SYMBOLS ({len(results['disabled'])}):")
        for sym in results['disabled']:
            print(f"   • {sym}")
    
    if results['missing']:
        print(f"\n❌ SIMBOLURI LIPSĂ ({len(results['missing'])}):")
        for sym in results['missing']:
            print(f"   • {sym}")
        print("\n⚠️  ATENȚIE: Acestea NU vor primi semnale în cTrader!")
    else:
        print(f"\n🎯 PERFECT! Toate simbolurile active sunt accesibile!")
    
    # Verify cBot mapping is correct
    print("\n" + "="*70)
    print("🔧 VERIFICARE MAPPING în PythonSignalExecutor.cs")
    print("="*70 + "\n")
    
    with open('PythonSignalExecutor.cs', 'r') as f:
        code = f.read()
    
    # Check if USOIL → WTIUSD mapping exists
    if 'if (pythonSymbol == "USOIL") return "WTIUSD";' in code:
        print("✅ USOIL → WTIUSD mapping: GĂSIT în cod")
    else:
        print("❌ USOIL → WTIUSD mapping: LIPSEȘTE din cod!")
    
    # Check if PIUSDT is disabled
    if 'if (pythonSymbol == "PIUSDT") return null;' in code:
        print("✅ PIUSDT disabled: CORECT")
    else:
        print("⚠️  PIUSDT disabled: Nu găsesc disable logic")
    
    print("\n" + "="*70)
    
    if total_active == total_configured - len(results['disabled']):
        print("✅ SISTEMUL ESTE COMPLET FUNCȚIONAL!")
        print(f"   Toate {total_active} perechi active pot primi semnale în cTrader! 🚀")
    else:
        missing_count = len(results['missing'])
        print(f"⚠️  ATENȚIE: {missing_count} simboluri configurate NU sunt accesibile!")
        print("   cBot-ul va IGNORA semnalele pentru acestea!")
    
    print("="*70 + "\n")
    
    return results

if __name__ == "__main__":
    verify_all_symbols()
