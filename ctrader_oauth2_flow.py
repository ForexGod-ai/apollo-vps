"""
cTrader OAuth2 Flow - Complete Implementation
==============================================
Obține Access Token & Refresh Token FRESH prin OAuth2

Faze:
1. Generate Authorization URL → User opens in browser
2. User approves → Spotware redirects with Authorization Code
3. Exchange code for tokens (access_token + refresh_token)
4. Save tokens to .env
"""

import os
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from loguru import logger
from dotenv import load_dotenv, set_key
import requests

load_dotenv()


class CTraderOAuth2:
    """
    OAuth2 Flow Manager pentru cTrader Open API
    """
    
    # Spotware OAuth2 Endpoints
    AUTH_URL = "https://openapi.ctrader.com/apps/auth"
    TOKEN_URL = "https://openapi.ctrader.com/apps/token"
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        
        # Redirect URI (trebuie să fie exact ca în Spotware App Settings)
        self.redirect_uri = os.getenv('CTRADER_REDIRECT_URI', 'http://localhost:5000/callback')
        
        # Scopes (permissions)
        # trading: permite execuție ordine
        # accounts: citește info cont
        self.scope = "trading accounts"
        
        logger.info("🔐 cTrader OAuth2 Manager initialized")
        logger.info(f"   Client ID: {self.client_id[:20]}...")
        logger.info(f"   Redirect URI: {self.redirect_uri}")
    
    # ==================== FAZA 1: AUTHORIZATION CODE ====================
    
    def get_authorization_url(self) -> str:
        """
        FAZA 1: Construiește URL-ul de autorizare
        
        Returns:
            URL complet pentru autorizare în browser
        """
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'response_type': 'code',  # OAuth2 Authorization Code Flow
        }
        
        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        
        logger.info("=" * 80)
        logger.info("📋 FAZA 1: AUTHORIZATION URL")
        logger.info("=" * 80)
        logger.info(f"\nURL: {auth_url}\n")
        
        return auth_url
    
    def start_authorization_flow(self) -> str:
        """
        FAZA 1: Pornește fluxul OAuth2
        
        Returns:
            Authorization code extras din URL-ul de răspuns
        """
        # Generează URL
        auth_url = self.get_authorization_url()
        
        # Deschide în browser
        logger.info("🌐 Opening authorization page in browser...")
        logger.info("   Please approve the authorization request")
        logger.info("   You will be redirected to: " + self.redirect_uri)
        
        try:
            webbrowser.open(auth_url)
            logger.success("✅ Browser opened!")
        except Exception as e:
            logger.warning(f"⚠️  Could not open browser automatically: {e}")
            logger.info(f"\nPlease open this URL manually:\n{auth_url}\n")
        
        # Așteaptă redirect URL de la user
        logger.info("\n" + "=" * 80)
        logger.info("⏳ WAITING FOR AUTHORIZATION...")
        logger.info("=" * 80)
        logger.info("\nAfter approving, you will be redirected to:")
        logger.info(f"   {self.redirect_uri}?code=XXXXX")
        logger.info("\nCopy the FULL redirect URL from your browser address bar")
        logger.info("(the URL after being redirected)")
        
        redirect_url = input("\n📝 Paste the redirect URL here: ").strip()
        
        # Extrage authorization code
        code = self._extract_code_from_url(redirect_url)
        
        if code:
            logger.success(f"✅ Authorization code obtained: {code[:20]}...")
            return code
        else:
            logger.error("❌ Could not extract code from URL!")
            return None
    
    def _extract_code_from_url(self, url: str) -> str:
        """
        Extrage codul de autorizare din URL-ul de redirect
        
        Args:
            url: URL complet de redirect (ex: http://localhost:5000/callback?code=ABC123)
            
        Returns:
            Authorization code sau None
        """
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            if 'code' in params:
                code = params['code'][0]
                return code
            else:
                logger.error("❌ 'code' parameter not found in URL")
                logger.debug(f"URL params: {params}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error parsing URL: {e}")
            return None
    
    # ==================== FAZA 2: TOKEN EXCHANGE ====================
    
    def exchange_code_for_tokens(self, auth_code: str) -> dict:
        """
        FAZA 2: Schimbă authorization code cu access_token & refresh_token
        
        Args:
            auth_code: Authorization code din FAZA 1
            
        Returns:
            Dict cu access_token, refresh_token, expires_in
        """
        logger.info("\n" + "=" * 80)
        logger.info("📋 FAZA 2: TOKEN EXCHANGE")
        logger.info("=" * 80)
        logger.info(f"Exchanging code: {auth_code[:20]}...")
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(
                self.TOKEN_URL,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code == 200:
                tokens = response.json()
                
                logger.success("✅ Tokens received!")
                logger.info(f"   Access Token: {tokens.get('access_token', '')[:30]}...")
                logger.info(f"   Refresh Token: {tokens.get('refresh_token', '')[:30]}...")
                logger.info(f"   Expires in: {tokens.get('expires_in', 0)} seconds")
                
                return tokens
            else:
                logger.error(f"❌ Token exchange failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Token exchange error: {e}")
            return None
    
    # ==================== FAZA 3: SAVE TOKENS ====================
    
    def save_tokens_to_env(self, tokens: dict):
        """
        FAZA 3: Salvează token-urile în .env
        
        Args:
            tokens: Dict cu access_token, refresh_token
        """
        logger.info("\n" + "=" * 80)
        logger.info("📋 FAZA 3: SAVE TOKENS")
        logger.info("=" * 80)
        
        env_path = '.env'
        
        try:
            # Update .env file
            set_key(env_path, 'CTRADER_ACCESS_TOKEN', tokens['access_token'])
            set_key(env_path, 'CTRADER_REFRESH_TOKEN', tokens['refresh_token'])
            
            logger.success("✅ Tokens saved to .env!")
            logger.info(f"   File: {env_path}")
            logger.info(f"   CTRADER_ACCESS_TOKEN updated")
            logger.info(f"   CTRADER_REFRESH_TOKEN updated")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving tokens: {e}")
            return False
    
    # ==================== COMPLETE FLOW ====================
    
    def run_complete_flow(self):
        """
        Rulează fluxul OAuth2 complet:
        1. Authorization URL → Browser
        2. User approves → Get code
        3. Exchange code → Get tokens
        4. Save tokens → .env
        """
        logger.info("=" * 80)
        logger.info("🚀 STARTING COMPLETE OAUTH2 FLOW")
        logger.info("=" * 80)
        
        # FAZA 1: Get authorization code
        auth_code = self.start_authorization_flow()
        
        if not auth_code:
            logger.error("❌ FAILED at FAZA 1 - No authorization code")
            return False
        
        # FAZA 2: Exchange code for tokens
        tokens = self.exchange_code_for_tokens(auth_code)
        
        if not tokens:
            logger.error("❌ FAILED at FAZA 2 - Token exchange failed")
            return False
        
        # FAZA 3: Save tokens
        if self.save_tokens_to_env(tokens):
            logger.info("\n" + "=" * 80)
            logger.success("🎉 OAUTH2 FLOW COMPLETE!")
            logger.info("=" * 80)
            logger.info("\n✅ You can now use the cTrader API with fresh tokens")
            logger.info("✅ Run test_twisted_connection.py to verify authentication")
            return True
        else:
            logger.error("❌ FAILED at FAZA 3 - Could not save tokens")
            return False


# ==================== HELPER: REFRESH TOKEN ====================

def refresh_access_token():
    """
    Helper function: Refresh an expired access token using refresh_token
    """
    logger.info("=" * 80)
    logger.info("🔄 REFRESHING ACCESS TOKEN")
    logger.info("=" * 80)
    
    refresh_token = os.getenv('CTRADER_REFRESH_TOKEN')
    client_id = os.getenv('CTRADER_CLIENT_ID')
    client_secret = os.getenv('CTRADER_CLIENT_SECRET')
    
    if not refresh_token:
        logger.error("❌ No refresh_token in .env!")
        return False
    
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    try:
        response = requests.post(
            CTraderOAuth2.TOKEN_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        if response.status_code == 200:
            tokens = response.json()
            
            logger.success("✅ Token refreshed!")
            logger.debug(f"Response: {tokens}")
            
            # Check if access_token exists
            if 'access_token' not in tokens:
                logger.error(f"❌ No access_token in response: {tokens}")
                return False
            
            # Save new tokens
            set_key('.env', 'CTRADER_ACCESS_TOKEN', tokens['access_token'])
            
            # Update refresh_token if provided
            if 'refresh_token' in tokens:
                set_key('.env', 'CTRADER_REFRESH_TOKEN', tokens['refresh_token'])
            
            logger.info(f"   New access token: {tokens['access_token'][:30]}...")
            return True
        else:
            logger.error(f"❌ Refresh failed: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Refresh error: {e}")
        return False


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'refresh':
        # Refresh existing token
        refresh_access_token()
    else:
        # Complete OAuth2 flow
        oauth = CTraderOAuth2()
        oauth.run_complete_flow()
