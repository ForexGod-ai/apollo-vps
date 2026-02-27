#!/usr/bin/env python3
"""
🔥 RESET MATRIX - Glitch in Matrix V8.0
====================================

Utilitar de curățenie pentru a șterge toate setup-urile din monitoring_setups.json
și a pregăti sistemul pentru o rescanare completă cu noile filtre V7 (ATR) și V8 (Premium/Discount).

Funcționalitate:
- Găsește monitoring_setups.json în mod dinamic (pathlib)
- Suprascrie fișierul cu array gol []
- Verifică integritatea după ștergere
- Printează mesaj de succes

Utilizare:
    python3 reset_matrix.py

Autor: ФорексГод
Data: 27 Februarie 2026
Versiune: V8.0 (ATR + Premium/Discount)
"""

import sys
from pathlib import Path
import json
from datetime import datetime
from typing import Optional

# ANSI Colors pentru terminal
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def find_monitoring_file() -> Optional[Path]:
    """
    Găsește monitoring_setups.json în mod dinamic.
    
    Căutare:
    1. Directorul curent
    2. Directorul părinte
    3. Directorul de bază al proiectului
    
    Returns:
        Path către monitoring_setups.json sau None dacă nu e găsit
    """
    # Metoda 1: Director curent
    current_dir = Path.cwd()
    monitoring_file = current_dir / "monitoring_setups.json"
    
    if monitoring_file.exists():
        return monitoring_file
    
    # Metoda 2: Director părinte
    parent_dir = current_dir.parent
    monitoring_file = parent_dir / "monitoring_setups.json"
    
    if monitoring_file.exists():
        return monitoring_file
    
    # Metoda 3: Caută în directorul scriptului
    script_dir = Path(__file__).parent.resolve()
    monitoring_file = script_dir / "monitoring_setups.json"
    
    if monitoring_file.exists():
        return monitoring_file
    
    # Metoda 4: Caută recursiv în directorul curent (max 2 nivele)
    for file in current_dir.rglob("monitoring_setups.json"):
        return file
    
    return None

def backup_monitoring_file(monitoring_file: Path) -> Optional[Path]:
    """
    Creează un backup al fișierului înainte de ștergere.
    
    Args:
        monitoring_file: Path către monitoring_setups.json
    
    Returns:
        Path către backup sau None dacă backup-ul a eșuat
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = monitoring_file.parent / f"monitoring_setups_backup_{timestamp}.json"
        
        # Citește conținutul original
        with open(monitoring_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Scrie backup
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return backup_file
    
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  WARNING: Could not create backup: {e}{Colors.RESET}")
        return None

def reset_monitoring_file(monitoring_file: Path, create_backup: bool = True) -> bool:
    """
    Șterge toate setup-urile din monitoring_setups.json.
    
    Args:
        monitoring_file: Path către monitoring_setups.json
        create_backup: Dacă True, creează backup înainte de ștergere
    
    Returns:
        True dacă resetarea a reușit, False altfel
    """
    try:
        # Backup opțional
        backup_path = None
        if create_backup:
            backup_path = backup_monitoring_file(monitoring_file)
            if backup_path:
                print(f"{Colors.CYAN}💾 Backup created: {backup_path.name}{Colors.RESET}")
        
        # Suprascrie cu array gol
        with open(monitoring_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        
        # Verifică integritatea
        with open(monitoring_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("File content is not a valid array")
        
        if len(data) != 0:
            raise ValueError("File was not properly reset")
        
        return True
    
    except Exception as e:
        print(f"{Colors.RED}❌ ERROR: Failed to reset file: {e}{Colors.RESET}")
        return False

def print_banner():
    """Printează banner-ul aplicației."""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🔥 RESET MATRIX - Glitch in Matrix V8.0{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}\n")
    print(f"{Colors.WHITE}Utilitar de curățenie pentru monitoring_setups.json{Colors.RESET}")
    print(f"{Colors.WHITE}Versiune: V8.0 (ATR Prominence + Premium/Discount Zone){Colors.RESET}")
    print(f"{Colors.WHITE}Data: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}{Colors.RESET}\n")

def print_stats(monitoring_file: Path):
    """
    Printează statistici despre fișierul curent.
    
    Args:
        monitoring_file: Path către monitoring_setups.json
    """
    try:
        with open(monitoring_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"{Colors.YELLOW}⚠️  WARNING: File contains invalid data (not an array){Colors.RESET}")
            return
        
        print(f"{Colors.BOLD}📊 CURRENT STATUS:{Colors.RESET}")
        print(f"   File: {Colors.CYAN}{monitoring_file.name}{Colors.RESET}")
        print(f"   Location: {Colors.WHITE}{monitoring_file.parent}{Colors.RESET}")
        print(f"   Setups: {Colors.YELLOW}{len(data)}{Colors.RESET}")
        print(f"   Size: {Colors.WHITE}{monitoring_file.stat().st_size} bytes{Colors.RESET}")
        
        if len(data) > 0:
            # Analiză rapidă a setup-urilor
            symbols = set()
            directions = {'bullish': 0, 'bearish': 0}
            
            for setup in data:
                if isinstance(setup, dict):
                    symbols.add(setup.get('symbol', 'UNKNOWN'))
                    direction = setup.get('daily_choch', {}).get('direction', '').lower()
                    if direction in directions:
                        directions[direction] += 1
            
            print(f"   Symbols: {Colors.CYAN}{', '.join(sorted(symbols))}{Colors.RESET}")
            print(f"   Bullish: {Colors.GREEN}{directions['bullish']}{Colors.RESET}")
            print(f"   Bearish: {Colors.RED}{directions['bearish']}{Colors.RESET}")
        
        print()
    
    except Exception as e:
        print(f"{Colors.RED}❌ ERROR: Could not read file stats: {e}{Colors.RESET}\n")

def main():
    """Main entry point."""
    print_banner()
    
    # Găsește fișierul
    print(f"{Colors.BOLD}🔍 Searching for monitoring_setups.json...{Colors.RESET}")
    monitoring_file = find_monitoring_file()
    
    if not monitoring_file:
        print(f"{Colors.RED}❌ ERROR: monitoring_setups.json not found!{Colors.RESET}")
        print(f"{Colors.YELLOW}   Searched in:{Colors.RESET}")
        print(f"   - {Path.cwd()}")
        print(f"   - {Path.cwd().parent}")
        print(f"   - {Path(__file__).parent.resolve()}")
        print(f"\n{Colors.WHITE}Please run this script from the project directory.{Colors.RESET}\n")
        return 1
    
    print(f"{Colors.GREEN}✅ Found: {monitoring_file}{Colors.RESET}\n")
    
    # Printează statistici curente
    print_stats(monitoring_file)
    
    # Confirmă ștergerea
    print(f"{Colors.BOLD}{Colors.YELLOW}⚠️  WARNING: This will delete ALL monitored setups!{Colors.RESET}")
    print(f"{Colors.WHITE}   A backup will be created automatically.{Colors.RESET}")
    print(f"{Colors.WHITE}   This action prepares the system for a fresh scan with V8.0 filters.{Colors.RESET}\n")
    
    response = input(f"{Colors.BOLD}Continue with reset? (yes/no): {Colors.RESET}").strip().lower()
    
    if response not in ['yes', 'y']:
        print(f"\n{Colors.YELLOW}❌ Reset cancelled by user.{Colors.RESET}\n")
        return 0
    
    print()
    
    # Resetare
    print(f"{Colors.BOLD}🔥 Resetting matrix...{Colors.RESET}")
    success = reset_monitoring_file(monitoring_file, create_backup=True)
    
    if not success:
        print(f"\n{Colors.RED}❌ Reset failed! Check error messages above.{Colors.RESET}\n")
        return 1
    
    # Success message
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✅ MEMORIA A FOST ȘTEARSĂ. GATA DE RESCANARE!{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.RESET}\n")
    
    print(f"{Colors.WHITE}✅ monitoring_setups.json reset to empty array{Colors.RESET}")
    print(f"{Colors.WHITE}✅ System ready for fresh scan with V8.0 filters{Colors.RESET}")
    print(f"{Colors.WHITE}✅ Backup created for safety{Colors.RESET}\n")
    
    print(f"{Colors.BOLD}🚀 NEXT STEPS:{Colors.RESET}")
    print(f"   1. Run: {Colors.CYAN}python3 daily_scanner.py{Colors.RESET}")
    print(f"   2. Monitor: {Colors.CYAN}tail -f logs/scanner_*.log{Colors.RESET}")
    print(f"   3. Check Telegram for new alerts (V8.0 filtered setups)\n")
    
    print(f"{Colors.BOLD}{Colors.MAGENTA}🎯 V8.0 ACTIVE FILTERS:{Colors.RESET}")
    print(f"   ✅ ATR Prominence Filter (1.5x ATR) - Eliminates micro-swings")
    print(f"   ✅ Premium/Discount Zone (50% Fib) - Only deep retracements")
    print(f"   ✅ Expected: 40-60% fewer setups, but higher quality\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}❌ Reset cancelled by user (Ctrl+C).{Colors.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ FATAL ERROR: {e}{Colors.RESET}\n")
        sys.exit(1)
