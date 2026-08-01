"""
WhatsApp OAuth / Embedded Signup service.
Handles:
  1. URL generation for Meta Business Login redirect flow.
  2. Exchange of authorization code for user access token.
  3. Querying Meta Graph API to extract WABA ID and Phone Number ID.
  4. Securely saving credentials to the database.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from config import settings
from models.token import OAuthToken
from repositories.token_repo import TokenRepository

logger = logging.getLogger(__name__)


def generate_whatsapp_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Generate the manual redirect URL for Meta Business Login (WhatsApp Embedded Signup).

    Returns:
        (authorization_url, state)
    """
    if not settings.META_APP_ID:
        raise ValueError("META_APP_ID is not configured in settings.")

    base_url = "https://www.facebook.com/v19.0/dialog/oauth"
    
    # We request permissions required to manage and message WhatsApp business accounts
    scopes = [
        "whatsapp_business_management",
        "whatsapp_business_messaging",
        "business_management"
    ]
    
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.WHATSAPP_REDIRECT_URI,
        "response_type": "code",
        "scope": ",".join(scopes)
    }

    if state:
        params["state"] = state
        
    if settings.WHATSAPP_CONFIG_ID:
        params["config_id"] = settings.WHATSAPP_CONFIG_ID

    query_str = urllib.parse.urlencode(params)
    auth_url = f"{base_url}?{query_str}"
    
    return auth_url, state or ""


async def exchange_whatsapp_code_for_tokens(
    code: str,
    state: str,
    db: Session,
    user_id: int
) -> OAuthToken:
    """
    Exchange the Meta auth code for a user access token, query the Graph API
    for WABA ID and phone number ID, and save the credentials to the database.
    """
    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meta App ID or App Secret is not configured."
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Exchange code for access token
        token_url = f"{settings.WHATSAPP_API_BASE_URL}/oauth/access_token"
        token_params = {
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.WHATSAPP_REDIRECT_URI,
            "code": code,
        }
        
        try:
            logger.info("Exchanging auth code for Meta access token...")
            token_res = await client.get(token_url, params=token_params)
            token_res.raise_for_status()
            token_data = token_res.json()
        except Exception as exc:
            logger.error("Failed Meta token exchange: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange authorization code with Meta: {str(exc)}"
            )

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Meta response did not contain an access_token."
            )

        # 2. Call debug_token to retrieve user granular scopes / WABA ID
        debug_url = f"{settings.WHATSAPP_API_BASE_URL}/debug_token"
        debug_params = {
            "input_token": access_token,
            "access_token": f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
        }
        
        waba_id = None
        scopes_list = []
        try:
            logger.info("Debugging Meta access token to find WABA ID...")
            debug_res = await client.get(debug_url, params=debug_params)
            debug_res.raise_for_status()
            debug_data = debug_res.json().get("data", {})
            scopes_list = debug_data.get("scopes", [])
            
            granular_scopes = debug_data.get("granular_scopes", [])
            for gs in granular_scopes:
                if gs.get("scope") in ("whatsapp_business_management", "whatsapp_business_messaging"):
                    target_ids = gs.get("target_ids", [])
                    if target_ids:
                        waba_id = target_ids[0]
                        break
        except Exception as exc:
            logger.warning("Failed to debug token via debug_token endpoint: %s", exc)

        # Fallback 1: Query client_whatsapp_business_accounts via businesses list
        if not waba_id:
            try:
                logger.info("Falling back to businesses endpoint to look for WABA ID...")
                biz_url = f"{settings.WHATSAPP_API_BASE_URL}/me/businesses"
                biz_res = await client.get(biz_url, params={"access_token": access_token})
                if biz_res.status_code == 200:
                    biz_data = biz_res.json().get("data", [])
                    for biz in biz_data:
                        biz_id = biz.get("id")
                        if biz_id:
                            waba_client_url = f"{settings.WHATSAPP_API_BASE_URL}/{biz_id}/client_whatsapp_business_accounts"
                            waba_res = await client.get(waba_client_url, params={"access_token": access_token})
                            if waba_res.status_code == 200:
                                waba_list = waba_res.json().get("data", [])
                                if waba_list:
                                    waba_id = waba_list[0].get("id")
                                    logger.info("Found WABA ID from businesses client accounts: %s", waba_id)
                                    break
            except Exception as fallback_exc:
                logger.error("Fallback WABA ID lookup failed: %s", fallback_exc)

        if not waba_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not find a connected WhatsApp Business Account (WABA) ID. Make sure permissions are granted."
            )

        # 3. Retrieve first phone number ID linked to the WABA ID
        phone_number_id = None
        try:
            logger.info("Retrieving phone numbers for WABA ID %s...", waba_id)
            phone_url = f"{settings.WHATSAPP_API_BASE_URL}/{waba_id}/phone_numbers"
            phone_res = await client.get(phone_url, params={"access_token": access_token})
            phone_res.raise_for_status()
            phone_data = phone_res.json().get("data", [])
            if phone_data:
                phone_number_id = phone_data[0].get("id")
                logger.info("Found Phone Number ID: %s", phone_number_id)
        except Exception as phone_exc:
            logger.error("Failed to retrieve phone number ID: %s", phone_exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch phone number details for WABA: {str(phone_exc)}"
            )

        if not phone_number_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No phone numbers are associated with this WhatsApp Business Account."
            )

        # 4. Save/upsert tokens in the database
        expires_at = None
        expires_in = token_data.get("expires_in")
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))

        # We store phone_number_id in refresh_token and waba_id in token_uri
        token = TokenRepository.upsert(
            db=db,
            user_id=user_id,
            provider="whatsapp",
            access_token=access_token,
            refresh_token=phone_number_id,
            token_uri=waba_id,
            scopes=json.dumps(scopes_list or ["whatsapp_business_management", "whatsapp_business_messaging"]),
            expires_at=expires_at
        )
        
        logger.info("Successfully connected WhatsApp and saved credentials for user_id=%d", user_id)
        return token
