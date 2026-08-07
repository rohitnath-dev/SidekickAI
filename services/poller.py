import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from config import settings
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from models.token import OAuthToken
from repositories.token_repo import TokenRepository
from services.oauth import get_credentials

logger = logging.getLogger(__name__)

async def start_polling() -> None:
    """
    Background worker loop that periodically polls Gmail, Twitter, Telegram,
    and Discord for new messages and runs them through the AI priority/drafting pipeline.
    """
    logger.info("Background multi-channel ingestion poller started.")
    
    # Wait for the database and app startup to fully finalize
    await asyncio.sleep(5)
    
    while True:
        # Check if poller is enabled in settings
        if not settings.POLLER_ENABLED:
            logger.info("Background Poller: Poller is disabled in settings. Sleeping for %d seconds.", settings.POLLER_INTERVAL_SECONDS)
            await asyncio.sleep(settings.POLLER_INTERVAL_SECONDS)
            continue
            
        db = SessionLocal()
        try:
            # Retrieve all users
            users = db.query(User).all()
            if not users:
                logger.warning("Background Poller: No registered users found. Skipping loop iteration.")
            else:
                for user in users:
                    # 1. SMART POLLER - CHECK BEFORE SYNC
                    gmail_token = db.query(OAuthToken).filter_by(user_id=user.id, provider="google").first()
                    has_gmail = bool(gmail_token and gmail_token.access_token)
                    
                    tokens = TokenRepository.list_by_user(db, user.id)
                    has_telegram = any(t.provider == "telegram" and t.access_token and t.access_token != "disabled" for t in tokens)
                    has_whatsapp = any(t.provider == "whatsapp" and t.access_token and t.access_token != "disabled" for t in tokens)
                    has_discord = any(t.provider == "discord" and t.access_token and t.access_token != "disabled" for t in tokens)
                    has_twitter = any(t.provider == "twitter" and t.access_token and t.access_token != "disabled" for t in tokens)

                    # If NO integrations are connected for a user, SKIP the entire poll cycle for that user.
                    if not (has_gmail or has_telegram or has_whatsapp or has_discord or has_twitter):
                        logger.info("Poller skipped: No integrations connected for user %d", user.id)
                        continue
                        
                    logger.info("Background Poller: Starting poll cycle for user_id=%d", user.id)

                    # 1. Gmail Ingestion Polling
                    if has_gmail:
                        creds = get_credentials(user.id, db)
                        if creds:
                            try:
                                from agents.gmail_agent import GmailAgent
                                logger.info("Background Poller: Syncing Gmail for user_id=%d", user.id)
                                res = await GmailAgent().sync_messages(
                                    creds=creds,
                                    db=db,
                                    user_id=user.id,
                                    limit=50,
                                    unread_only=True,
                                )
                                synced_count = res.get("synced", 0) if isinstance(res, dict) else 0
                                if synced_count == 0:
                                    logger.info("Poller skipped: 0 messages found, skipping AI pipeline for Gmail user_id=%d", user.id)
                            except Exception as e:
                                logger.error("Background Poller: Gmail sync failed for user_id=%d: %s", user.id, e)
                        else:
                            logger.info("Background Poller: Gmail active but failed to load credentials for user_id=%d", user.id)

                    # 2. Twitter Mentions Ingestion Polling
                    twitter_user_id = settings.TWITTER_USER_ID
                    if has_twitter and settings.TWITTER_BEARER_TOKEN and twitter_user_id:
                        try:
                            from agents.twitter_agent import TwitterAgent
                            logger.info("Background Poller: Syncing Twitter mentions for user_id=%d", user.id)
                            tweets = await TwitterAgent().get_mentions(
                                bearer_token=settings.TWITTER_BEARER_TOKEN,
                                user_id=twitter_user_id,
                                max_results=5,
                            )
                            if not tweets:
                                logger.info("Poller skipped: 0 messages found, skipping AI pipeline for Twitter user_id=%d", user.id)
                            else:
                                for t in tweets:
                                    tweet_id = t.get("id")
                                    if not tweet_id:
                                        continue
                                    existing = db.query(Message).filter_by(message_id=tweet_id, source=MessageSource.TWITTER).first()
                                    if existing:
                                        continue
                                    
                                    logger.info("Background Poller: New Twitter mention found (ID: %s)", tweet_id)
                                    db_msg = Message(
                                        user_id=user.id,
                                        message_id=tweet_id,
                                        source=MessageSource.TWITTER,
                                        sender=t.get("author_id") or "TwitterUser",
                                        body=t.get("text", ""),
                                        priority=MessagePriority.MEDIUM,
                                        status=MessageStatus.UNREAD,
                                        received_at=datetime.utcnow()
                                    )
                                    db.add(db_msg)
                                    db.commit()
                                    db.refresh(db_msg)
                                    
                                    try:
                                        from services.ai_pipeline import process_message_ai
                                        await process_message_ai(db, db_msg)
                                    except Exception as e:
                                        logger.error("Background Poller: Twitter AI pipeline failed for tweet %s: %s", tweet_id, e)
                        except Exception as e:
                            logger.error("Background Poller: Twitter sync failed for user_id=%d: %s", user.id, e)

                    # 3. Telegram Ingestion Polling
                    if has_telegram:
                        try:
                            from routes.telegram import sync_telegram
                            logger.info("Background Poller: Syncing Telegram for user_id=%d", user.id)
                            res = await sync_telegram(current_user=user, db=db)
                            synced_count = getattr(res, "synced", 0) if hasattr(res, "synced") else (res.get("synced", 0) if isinstance(res, dict) else 0)
                            if synced_count == 0:
                                logger.info("Poller skipped: 0 messages found, skipping AI pipeline for Telegram user_id=%d", user.id)
                        except Exception as e:
                            logger.error("Background Poller: Telegram sync failed for user_id=%d: %s", user.id, e)

                    # 4. Discord Ingestion Polling
                    if has_discord:
                        try:
                            from routes.discord import sync_discord
                            logger.info("Background Poller: Syncing Discord for user_id=%d", user.id)
                            res = await sync_discord(current_user=user, db=db)
                            synced_count = getattr(res, "synced", 0) if hasattr(res, "synced") else (res.get("synced", 0) if isinstance(res, dict) else 0)
                            if synced_count == 0:
                                logger.info("Poller skipped: 0 messages found, skipping AI pipeline for Discord user_id=%d", user.id)
                        except Exception as e:
                            logger.error("Background Poller: Discord sync failed for user_id=%d: %s", user.id, e)

        except Exception as e:
            logger.error("Background Poller loop encountered an error: %s", e)
        finally:
            db.close()
            
        # Sleep for POLLER_INTERVAL_SECONDS
        await asyncio.sleep(settings.POLLER_INTERVAL_SECONDS)
