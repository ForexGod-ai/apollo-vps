#!/usr/bin/env python3
"""
cTrader API Token Helper
Ghid pas cu pas pentru a obține access token
"""

from loguru import logger

def show_token_guide():
    """Afișează ghid complet pentru obținere token"""
    
    print("\n" + "="*70)
    print("🔑 CUM SĂ OBȚII cTRADER API TOKEN")
    print("="*70)
    
    print("\n📋 PASUL 1: Recuperează/Login la cTrader Connect")
    print("-"*70)
    print("   Opțiunea A - Dacă îți amintești email-ul:")
    print("   1. Du-te la: https://connect.spotware.com/")
    print("   2. Click pe 'Sign In'")
    print("   3. Introdu email-ul (cel cu care ai creat contul IC Markets)")
    print("   4. Dacă ai uitat parola → Click 'Forgot Password'")
    print("      - Primești email de reset")
    print("      - Setezi parolă nouă")
    
    print("\n   Opțiunea B - Login direct cu cTrader ID:")
    print("   1. Deschide aplicația cTrader desktop/mobile")
    print("   2. Click pe icon-ul de profil (sus-dreapta)")
    print("   3. Vezi 'cTrader ID' - folosește-l pentru login")
    print("   4. Sau click 'Login with cTrader ID' pe website")
    
    print("\n" + "-"*70)
    print("📋 PASUL 2: Creează/Găsește App")
    print("-"*70)
    print("   După ce te-ai logat:")
    print("   1. Click pe 'My Apps' (în meniu)")
    print("   2. Dacă ai deja app-uri create → Le vezi aici")
    print("   3. Dacă NU ai app → Click 'Create New App'")
    
    print("\n   Pentru app NOU:")
    print("   ├─ App Name: Trading AI Bot")
    print("   ├─ App Type: Desktop/Server Application")
    print("   ├─ Redirect URI: http://localhost:5000/callback")
    print("   └─ Permissions:")
    print("      ✅ accounts:read (citire cont)")
    print("      ✅ trading (executare ordine)")
    print("      ✅ balance:read (citire balance)")
    
    print("\n" + "-"*70)
    print("📋 PASUL 3: Copiază Access Token")
    print("-"*70)
    print("   1. Click pe app-ul tău din listă")
    print("   2. Caută secțiunea 'Credentials' sau 'API Keys'")
    print("   3. Vei vedea:")
    print("      - Client ID (ex: 123456_abc...)")
    print("      - Client Secret (string lung)")
    print("      - Access Token (începe cu 'eyJ...')")
    print("   4. Click pe 'Copy' lângă Access Token")
    
    print("\n   📝 Token-ul arată așa:")
    print("      eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY...")
    print("      (foarte lung, ~500+ caractere)")
    
    print("\n" + "-"*70)
    print("📋 PASUL 4: Adaugă în .env")
    print("-"*70)
    print("   1. Deschide fișierul .env din proiect")
    print("   2. Găsește linia: CTRADER_ACCESS_TOKEN=")
    print("   3. Lipește token-ul:")
    print("      CTRADER_ACCESS_TOKEN=eyJhbGciOiJIUzI1NiIsInR...")
    print("   4. Salvează fișierul")
    
    print("\n" + "-"*70)
    print("📋 PASUL 5: Testează Conexiunea")
    print("-"*70)
    print("   Rulează în terminal:")
    print("   $ python3 ctrader_live_sync.py")
    print("")
    print("   Dacă vezi:")
    print("   ✅ LIVE sync working!")
    print("   → TOKEN FUNCȚIONEAZĂ! 🎉")
    print("")
    print("   Dacă vezi:")
    print("   ❌ Authentication failed: 401")
    print("   → Token expirat/invalid - regenerează din portal")
    
    print("\n" + "="*70)
    print("🆘 PROBLEME COMUNE:")
    print("="*70)
    
    print("\n❌ 'Sign in failed'")
    print("   → Email/parolă greșite")
    print("   → Folosește 'Forgot Password' pentru reset")
    print("   → SAU login cu cTrader ID din aplicație")
    
    print("\n❌ 'No apps found'")
    print("   → Creează app nou (vezi Pasul 2)")
    print("   → Sau verifică că ești pe contul corect")
    
    print("\n❌ 'Token not found'")
    print("   → Click pe app din listă pentru detalii")
    print("   → Dacă lipsește → 'Generate New Token'")
    
    print("\n❌ 'Authentication failed: 401'")
    print("   → Token expirat (valabil ~90 zile)")
    print("   → Generează token nou din portal")
    print("   → Click 'Regenerate Token' în app settings")
    
    print("\n" + "="*70)
    print("📞 ALTERNATIVE:")
    print("="*70)
    print("   Dacă nu poți accesa portal-ul:")
    print("   1. Verifică email-ul pentru invitații vechi de la Spotware")
    print("   2. Contactează IC Markets support")
    print("   3. SAU creează cont nou (5 minute):")
    print("      - Folosește același email ca IC Markets")
    print("      - Link contul cTrader existent")
    
    print("\n" + "="*70)
    print("🔗 LINK-URI UTILE:")
    print("="*70)
    print("   Portal principal: https://connect.spotware.com/")
    print("   Documentație API: https://help.ctrader.com/open-api/")
    print("   IC Markets help: https://www.icmarkets.com/en/contact-us")
    
    print("\n" + "="*70)
    print("✅ QUICK STEPS (Rezumat):")
    print("="*70)
    print("   1. https://connect.spotware.com/ → Sign In")
    print("   2. My Apps → Click pe app-ul tău")
    print("   3. Copy Access Token (eyJ...)")
    print("   4. Paste în .env → CTRADER_ACCESS_TOKEN=eyJ...")
    print("   5. Test: python3 ctrader_live_sync.py")
    print("="*70 + "\n")
    
    print("💡 TIP: Dacă ai dificultăți, pot să-ți ajut pas cu pas!")
    print("    Spune-mi la ce pas te-ai blocat și îți explic mai detaliat.\n")


if __name__ == "__main__":
    show_token_guide()
