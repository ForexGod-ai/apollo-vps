# 🔍 RAPORT URGENT: SURSA DE DATE SCANNER "GLITCH IN MATRIX"

**Data: 9 Decembrie 2025**  
**Status: IDENTIFICAT COMPLET**

---

## 📊 SURSA CURENTĂ DE DATE

### **Furnizor Principal:**
**Alpha Vantage API** (FREE tier - 500 requests/day)

### **Fallback Hierarchy:**
1. **cTrader REST API** (Priority 1) - INACTIV momentan (credențiale OK dar API nu răspunde)
2. **Alpha Vantage API** (Priority 2) - **ACTIV ACUM** ✅
3. **Error** - Dacă ambele fail

---

## 🔌 METODA DE CONEXIUNE

**Protocol:** REST API (HTTP GET requests)  
**Endpoint:** `https://www.alphavantage.co/query`  
**Autentificare:** API Key (în `.env` ca `ALPHA_VANTAGE_API_KEY`)

**Format Request:**
```
GET https://www.alphavantage.co/query?
  function=FX_DAILY/FX_INTRADAY
  &from_symbol=GBP
  &to_symbol=USD
  &apikey=YOUR_KEY
  &outputsize=full
```

**Limite:**
- ✅ 500 requests/day (FREE)
- ⚠️  H4 timeframe = folosește H1 și resamplează (Alpha Vantage nu are H4 nativ)

---

## 📂 PUNCT DE INTRARE (Fișiere Cheie)

### **1. Scanner Principal:**
📁 `morning_strategy_scan.py` (linia 29)
```python
from ctrader_data_client import get_ctrader_client
```

**Linia 82-84:** Apel pentru date
```python
df = self.ctrader_client.get_historical_data(symbol, timeframe, bars)
```

---

### **2. Data Provider:**
📁 `ctrader_data_client.py`

**Funcția Principală:** `get_historical_data()` (linia 306-343)

**Logica Fallback:**
```python
# Priority 1: cTrader API (nu funcționează acum)
if self.access_token:
    df = self._fetch_from_ctrader_api(...)
    if df: return df

# Priority 2: Alpha Vantage (ACTIV)
logger.info(f"🔄 Using Alpha Vantage API...")
df = self._fetch_from_alpha_vantage(symbol, timeframe, bars)
return df
```

**Metoda Alpha Vantage:** `_fetch_from_alpha_vantage()` (linia 492-590)

---

## 📋 FORMAT DATE AȘTEPTAT DE SCANNER

**DataFrame Pandas cu coloane:**
```python
{
    'time': datetime,      # Timestamp
    'open': float,         # Deschidere
    'high': float,         # Maxim
    'low': float,          # Minim
    'close': float,        # Închidere
    'volume': int          # Volum (0 pentru forex)
}
```

**Index:** DateTime (timezone aware)  
**Sortare:** Crescător (oldest → newest)

---

## 🎯 TIMEFRAME-URI SUPORTATE

| Scanner Cere | Alpha Vantage Oferă | Conversie |
|-------------|---------------------|-----------|
| D1          | Daily               | Direct ✅ |
| H4          | 60min (H1)          | Resample 4x ⚠️ |
| H1          | 60min               | Direct ✅ |

**Problemă H4:** Alpha Vantage nu are H4 nativ → folosește H1 și resamplează la 4H

---

## ⚠️  PROBLEME IDENTIFICATE

### **1. Dependență Alpha Vantage**
- ❌ User a cerut explicit: "am RENUNTAT LA ALPHA VANTAGE"
- ✅ Dar scannerul ÎNCĂ folosește Alpha Vantage ca sursă primară
- ⚠️  Limită: 500 req/day (21 pairs × 2 timeframes × zilnic = 42 req/day → OK)

### **2. cTrader API Inactiv**
- ✅ Credențiale configurate corect în `.env`
- ❌ API nu răspunde (posibil ProtoOA app "Submitted", nu "Active")
- 🔄 Fallback-ul la Alpha Vantage SALVEAZĂ situația

### **3. H4 Timeframe Compromis**
- Alpha Vantage: H1 → resample → H4 (potențial imprecis)
- cTrader ProtoOA: ar avea H4 nativ

---

## ✅ SOLUȚIE PROPUSĂ

### **Faza 1: IMEDIAT (Rămâne Alpha Vantage)**
- ✅ Scannerul funcționează ACUM cu Alpha Vantage
- ✅ Toate 21 paritatile au date D1 și H4
- ⚠️  Acceptăm H4 resample până la activare cTrader

### **Faza 2: VIITOR (Switch la cTrader ProtoOA)**
Când aplicația "ForexGod_ProtoOA_Test" devine **Active**:
1. Update `.env` cu noul CLIENT_SECRET
2. `_fetch_from_ctrader_api()` va reveni prioritar
3. Alpha Vantage devine backup automat
4. H4 nativ din cTrader ✅

---

## 📊 MAPARE NECESARĂ PENTRU CTRADER

Când implementăm cTrader ProtoOA (WebSocket), formatul **TREBUIE** să fie identic:

**Input Actual (Alpha Vantage):**
```python
{
    'time': pd.Timestamp,
    'open': 1.26745,
    'high': 1.26892,
    'low': 1.26650,
    'close': 1.26788,
    'volume': 0
}
```

**Output cTrader ProtoOA (viitor):**
```python
{
    'time': pd.Timestamp,           # Convert din UTC Unix timestamp
    'open': trendbar.open / 100000, # cTrader sends pips × 100000
    'high': trendbar.high / 100000,
    'low': trendbar.low / 100000,
    'close': trendbar.close / 100000,
    'volume': trendbar.volume       # cTrader are volum real
}
```

**Diferențe Cheie:**
- cTrader: preț în **pips × 100000** → trebuie împărțit
- cTrader: **Unix timestamp (UTC)** → convert la pandas datetime
- cTrader: **volum real** (nu 0 ca la Alpha Vantage)

---

## 🎯 CONCLUZIE

**Sursa Curentă:** **Alpha Vantage API** (REST)  
**Fișier Entry:** `ctrader_data_client.py` → linia 332  
**Funcție Cheie:** `_fetch_from_alpha_vantage()` (linia 492-590)  

**Status Operațional:** ✅ **FUNCȚIONAL**  
**Calitate Date:** ⚠️  Bună (dar H4 = resample din H1)  
**Dependență:** Alpha Vantage FREE tier (500 req/day)  

**Next Step:** Activare cTrader ProtoOA → auto-switch la date native IC Markets
