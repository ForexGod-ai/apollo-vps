#!/usr/bin/env python3
"""
cTrader OAuth Connection Manager
Handles OAuth authentication and token management
"""

import os
import requests
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv
import json

load_dotenv()


class CTraderOAuthManager:
    """
    Manages OAuth authentication with cTrader Open API
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.refresh_token = os.getenv('CTRADER_REFRESH_TOKEN', 'OqWPIMHuxNw7VnnzmgmD5nUKBkOuKmGFCuJi77YHv-Q')
        
        # OAuth endpoints
        self.auth_url = "https://openapi.ctrader.com"
        self.token_url = "https://openapi.ctrader.com/apps/token"
        
        self.token_cache = {
            'access_token': self.access_token,
            'expires_at': None
        }
        
        logger.info("🔐 OAuth Manager initialized")
    
    def get_valid_token(self) -> str:
        """
        Get a valid access token (refresh if needed)
        Returns the access token string
        """
        try:
            # If we have a token in cache and it's not expired
            if self.token_cache['access_token'] and self._is_token_valid():
                return self.token_cache['access_token']
            
            # Try to refresh token
            logger.info("🔄 Access token expired, refreshing...")
            new_token = self._refresh_access_token()
            
            if new_token:
                self.token_cache['access_token'] = new_token
                # Access tokens typically last 30 days
                self.token_cache['expires_at'] = datetime.now() + timedelta(days=30)
                return new_token
            
            # Fallback to stored token
            return self.access_token
            
        except Exception as e:
            logger.error(f"❌ Token error: {e}")
            return self.access_token
    
    def _is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.token_cache['expires_at']:
            return False
        return datetime.now() < self.token_cache['expires_at']
    
    def _refresh_access_token(self) -> str:
        """
        Refresh access token using refresh token
        """
        try:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(self.token_url, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data.get('access_token')
                new_refresh_token = token_data.get('refresh_token')
                
                # Update refresh token if we got a new one
                if new_refresh_token:
                    self.refresh_token = new_refresh_token
                    logger.info("✅ Refresh token updated")
                
                logger.success("✅ Access token refreshed")
                return new_access_token
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Refresh error: {e}")
            return None


def test_oauth():
    """Test OAuth manager"""
    logger.info("="*70)
    logger.info("🧪 TESTING OAUTH MANAGER")
    logger.info("="*70)
    
    oauth = CTraderOAuthManager()
    
    token = oauth.get_valid_token()
    
    if token:
        logger.success(f"✅ Valid token obtained: {token[:20]}...")
        logger.info(f"   Token length: {len(token)} characters")
    else:
        logger.error("❌ Failed to get valid token")
    
    logger.info("="*70)


if __name__ == "__main__":
    test_oauth()
