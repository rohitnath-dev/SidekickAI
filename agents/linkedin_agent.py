"""
LinkedIn Agent
LinkedIn API integration via async httpx.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com"


class LinkedInAgent(BaseAgent):
    """LinkedIn integration agent using LinkedIn API v2."""

    def __init__(self) -> None:
        super().__init__(agent_name="LinkedInAgent")

    async def get_profile(self, access_token: str) -> dict:
        """
        Fetch authenticated member's profile details via OpenID Connect userinfo endpoint.
        """
        url = f"{LINKEDIN_API_BASE}/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()
                return res.json()
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "LinkedInAgent.get_profile HTTP error: %s — %s",
                exc,
                exc.response.text,
            )
            return {}
        except Exception as exc:
            self.logger.error("LinkedInAgent.get_profile failed: %s", exc)
            return {}

    async def create_post(self, access_token: str, person_id: str, text: str) -> dict:
        """
        Create a text post on behalf of the member.
        """
        url = f"{LINKEDIN_API_BASE}/v2/posts"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        
        # Format mention placeholders if present in text (e.g. @[Name](urn:li:person:id))
        # No extra transformation is needed as it is passed as standard string commentary.
        payload = {
            "author": f"urn:li:person:{person_id}",
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                post_id = (
                    res.headers.get("x-linkedin-id")
                    or res.headers.get("x-restli-id")
                    or ""
                )
                body = res.json() if res.content else {}
                return {
                    "success": True,
                    "id": post_id,
                    "status_code": res.status_code,
                    "body": body,
                }
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "LinkedInAgent.create_post HTTP error: %s — %s",
                exc,
                exc.response.text,
            )
            return {"success": False, "error": exc.response.text}
        except Exception as exc:
            self.logger.error("LinkedInAgent.create_post failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def get_mentions(self, access_token: str) -> list[dict]:
        """
        Fetch recent mentions of the member.
        Note: The LinkedIn public API does not support reading member notifications/mentions directly.
        """
        self.logger.warning(
            "LinkedIn public API does not support fetching personal mentions feed programmatically."
        )
        return []
