"""
Twitter / X Agent

Twitter API v2 integration via async httpx.
OAuth 1.0a for write operations is implemented using stdlib (hmac, hashlib, base64, urllib).
OAuth 2.0 for user-specific replies using Bearer tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
import uuid
from typing import Optional

import httpx

from agents.base_agent import BaseAgent
from utils.prompts.twitter import build_twitter_reply_prompt

logger = logging.getLogger(__name__)

TWITTER_API_BASE = "https://api.twitter.com/2"


class TwitterAgent(BaseAgent):
    """Twitter / X integration agent using API v2."""

    def __init__(self) -> None:
        super().__init__(agent_name="TwitterAgent")

    # ------------------------------------------------------------------
    # Read endpoints (Bearer Token auth)
    # ------------------------------------------------------------------

    async def get_mentions(
        self,
        bearer_token: str,
        user_id: str,
        max_results: int = 10,
    ) -> list[dict]:
        """
        Fetch recent mentions of a user.

        Returns:
            List of tweet dicts.
        """
        url = f"{TWITTER_API_BASE}/users/{user_id}/mentions"
        params = {
            "max_results": min(max_results, 100),
            "expansions": "author_id",
            "tweet.fields": "created_at,public_metrics,author_id",
            "user.fields": "id,name,username"
        }
        headers = {"Authorization": f"Bearer {bearer_token}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Map user expansions to tweets
                tweets = data.get("data", [])
                users_map = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                for tweet in tweets:
                    if "author_id" in tweet and tweet["author_id"] in users_map:
                        tweet["author"] = users_map[tweet["author_id"]]
                
                return tweets
        except httpx.HTTPStatusError as exc:
            self.logger.error("TwitterAgent.get_mentions HTTP error: %s — %s", exc, exc.response.text)
            return []
        except Exception as exc:
            self.logger.error("TwitterAgent.get_mentions failed: %s", exc)
            return []

    async def get_timeline(
        self,
        bearer_token: str,
        user_id: str,
        max_results: int = 10,
    ) -> list[dict]:
        """
        Fetch recent tweets from a user's timeline.

        Returns:
            List of tweet dicts.
        """
        url = f"{TWITTER_API_BASE}/users/{user_id}/tweets"
        params = {
            "max_results": min(max_results, 100),
            "expansions": "author_id",
            "tweet.fields": "created_at,public_metrics,author_id",
            "user.fields": "id,name,username"
        }
        headers = {"Authorization": f"Bearer {bearer_token}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                tweets = data.get("data", [])
                users_map = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                for tweet in tweets:
                    if "author_id" in tweet and tweet["author_id"] in users_map:
                        tweet["author"] = users_map[tweet["author_id"]]
                
                return tweets
        except httpx.HTTPStatusError as exc:
            self.logger.error("TwitterAgent.get_timeline HTTP error: %s — %s", exc, exc.response.text)
            return []
        except Exception as exc:
            self.logger.error("TwitterAgent.get_timeline failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Write endpoints (OAuth 2.0 — User Bearer Token)
    # ------------------------------------------------------------------

    async def post_reply_oauth2(
        self,
        access_token: str,
        tweet_id: str,
        text: str,
    ) -> dict:
        """
        Post a reply to a tweet using OAuth 2.0 (user's personal access token).
        
        This is the NEW method for per-user replies.
        Uses the user's own Twitter bearer token (not app-level token).

        Args:
            access_token: User's OAuth 2.0 access token from Twitter
            tweet_id: ID of tweet to reply to
            text: Reply text (max 280 chars)

        Returns:
            API response dict or {} on failure.
        """
        url = f"{TWITTER_API_BASE}/tweets"
        payload = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id},
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                self.logger.info("Posted reply via OAuth2: tweet_id=%s, reply_id=%s", tweet_id, result.get("data", {}).get("id"))
                return result
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "TwitterAgent.post_reply_oauth2 HTTP error: %s — %s",
                exc,
                exc.response.text,
            )
            return {}
        except Exception as exc:
            self.logger.error("TwitterAgent.post_reply_oauth2 failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Write endpoints (OAuth 1.0a — Legacy)
    # ------------------------------------------------------------------

    async def post_reply(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str,
        tweet_id: str,
        text: str,
    ) -> dict:
        """
        Post a reply to a tweet using OAuth 1.0a (legacy, app-level credentials).

        Returns:
            API response dict or {} on failure.
        """
        url = f"{TWITTER_API_BASE}/tweets"
        payload = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id},
        }

        auth_header = self._build_oauth1_header(
            method="POST",
            url=url,
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_secret=access_secret,
        )

        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "TwitterAgent.post_reply HTTP error: %s — %s",
                exc,
                exc.response.text,
            )
            return {}
        except Exception as exc:
            self.logger.error("TwitterAgent.post_reply failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # OAuth 1.0a header construction (stdlib only)
    # ------------------------------------------------------------------

    def _build_oauth1_header(
        self,
        method: str,
        url: str,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str,
        extra_params: Optional[dict] = None,
    ) -> str:
        """
        Build an OAuth 1.0a Authorization header using stdlib (hmac, hashlib,
        base64, urllib) — no external OAuth library required.
        """
        oauth_nonce = uuid.uuid4().hex
        oauth_timestamp = str(int(time.time()))

        oauth_params: dict[str, str] = {
            "oauth_consumer_key": api_key,
            "oauth_nonce": oauth_nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": oauth_timestamp,
            "oauth_token": access_token,
            "oauth_version": "1.0",
        }

        # Combine OAuth params with any extra query params for signature base
        all_params = dict(oauth_params)
        if extra_params:
            all_params.update(extra_params)

        # Percent-encode and sort
        def percent_encode(s: str) -> str:
            return urllib.parse.quote(str(s), safe="")

        sorted_params = sorted(
            (percent_encode(k), percent_encode(v))
            for k, v in all_params.items()
        )
        param_string = "&".join(f"{k}={v}" for k, v in sorted_params)

        # Signature base string
        signature_base = "&".join([
            percent_encode(method.upper()),
            percent_encode(url),
            percent_encode(param_string),
        ])

        # Signing key
        signing_key = f"{percent_encode(api_secret)}&{percent_encode(access_secret)}"

        # HMAC-SHA1 signature
        hashed = hmac.new(
            signing_key.encode("ascii"),
            signature_base.encode("ascii"),
            hashlib.sha1,
        )
        oauth_signature = base64.b64encode(hashed.digest()).decode("ascii")

        # Build the Authorization header
        oauth_params["oauth_signature"] = oauth_signature
        header_parts = ", ".join(
            f'{percent_encode(k)}="{percent_encode(v)}"'
            for k, v in sorted(oauth_params.items())
        )
        return f"OAuth {header_parts}"

    # ------------------------------------------------------------------
    # LLM-powered reply generation
    # ------------------------------------------------------------------

    async def generate_reply_text(
        self,
        post_content: str,
        author_handle: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Generate a reply text for a tweet using the LLM.

        Returns:
            Reply text (max 280 chars).
        """
        prompt = build_twitter_reply_prompt(
            author_handle=author_handle,
            post_content=post_content,
            context=context,
        )
        reply = await self._call_llm(prompt)
        reply = reply.strip()
        # Enforce Twitter character limit
        if len(reply) > 280:
            reply = reply[:277] + "..."
        return reply
