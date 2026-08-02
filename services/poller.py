import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from config import settings
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from services.oauth import get_credentials

logger = logging.getLogger(__name__)

async def start_polling() -> None:
    """
    Background worker loop that periodically polls Gmail and Twitter
    for new messages and runs them through the AI priority/drafting pipeline.
    """
    logger.info("Background multi-channel ingestion poller started.")
    
    # Wait for the database and app startup to fully finalize
    await asyncio.sleep(5)
    
    while True:
        db = SessionLocal()
        try:
            # Retrieve the first user
            user = db.query(User).first()
            if not user:
                logger.warning("Background Poller: No registered user found. Skipping loop iteration.")
            else:
                # 1. Gmail Ingestion Polling
                creds = get_credentials(user.id, db)
                if creds:
                    try:
                        from agents.gmail_agent import GmailAgent
                        logger.info("Background Poller: Syncing Gmail for user_id=%d", user.id)
                        # sync_messages automatically processes each new email through process_message_ai
                        await GmailAgent().sync_messages(
                            creds=creds,
                            db=db,
                            user_id=user.id,
                            limit=50,
                            unread_only=True,
                        )
                    except Exception as e:
                        logger.error("Background Poller: Gmail sync failed: %s", e)
                
                # 2. Twitter Mentions Ingestion Polling
                twitter_user_id = settings.TWITTER_USER_ID
                if settings.TWITTER_BEARER_TOKEN and twitter_user_id:
                    try:
                        from agents.twitter_agent import TwitterAgent
                        logger.info("Background Poller: Syncing Twitter mentions for user_id=%d, twitter_user_id=%s", user.id, twitter_user_id)
                        tweets = await TwitterAgent().get_mentions(
                            bearer_token=settings.TWITTER_BEARER_TOKEN,
                            user_id=twitter_user_id,
                            max_results=5,
                        )
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
                            
                            # Run AI pipeline
                            try:
                                from services.ai_pipeline import process_message_ai
                                await process_message_ai(db, db_msg)
                            except Exception as e:
                                logger.error("Background Poller: Twitter AI pipeline failed for tweet %s: %s", tweet_id, e)
                    except Exception as e:
                        logger.error("Background Poller: Twitter sync failed: %s", e)

        except Exception as e:
            logger.error("Background Poller loop encountered an error: %s", e)
        finally:
            db.close()
            
        # Poll every 30 seconds
        await asyncio.sleep(30)
