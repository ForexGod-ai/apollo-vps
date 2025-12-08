# 🎯 Obține Credențialele Existente

Ai deja **1 aplicație autorizată** în contul tău cTrader!

## Pașii EXACT:

### 1️⃣ Mergi la Open API Section
În pagina unde ești acum (`https://id.ctrader.com/my/settings/overview`):

- Click pe **"Open API"** (secțiunea din dreapta jos cu iconița {API})
- SAU mergi direct la: **https://openapi.ctrader.com/apps**

### 2️⃣ Vezi Aplicația Existentă
Vei vedea lista de aplicații. Probabil ai deja una creată.

Click pe aplicația existentă pentru a vedea:
- **Client ID** (lungime ~57 caractere)
- **Client Secret** (lungime ~51 caractere)

### 3️⃣ Verifică Redirect URI
În setările aplicației, trebuie să existe **Redirect URI**:
- Verifică dacă există `http://localhost:5000/callback`
- Dacă NU există, adaugă-l în "Redirect URIs"

### 4️⃣ Generează Token NOU
În pagina aplicației:
- Caută butonul **"Generate Token"** sau **"Create Access Token"**
- SAU urmează acest link: `https://openapi.ctrader.com/apps/auth?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:5000/callback&scope=trading accounts&response_type=code`

### 5️⃣ Copiază Credențialele
După ce generezi token:
```
CLIENT_ID=... (copy exact)
CLIENT_SECRET=... (copy exact)  
ACCESS_TOKEN=... (copy exact - dacă îl arată direct)
```

---

## 🚀 Dacă NU vezi Access Token direct:

Atunci trebuie să rulezi OAuth2 flow-ul meu:

```bash
python3 ctrader_oauth2_flow.py
```

Dar ÎNAINTE:
1. Verifică că în `.env` ai `CLIENT_ID` și `CLIENT_SECRET` corecte
2. Verifică că ai `CTRADER_REDIRECT_URI=http://localhost:5000/callback` în `.env`
3. Verifică că redirect URI este adăugat în setările aplicației cTrader

---

## ❓ Ce să cauți în cTrader Dashboard:

Mergi la: https://openapi.ctrader.com/apps

Vei vedea:
- Lista de aplicații
- Click pe aplicație → Vezi Client ID, Client Secret
- "Redirect URIs" section → Adaugă `http://localhost:5000/callback` dacă lipsește
- "Generate Token" button → Pentru a genera access token nou
