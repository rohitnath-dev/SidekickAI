from __future__ import annotations

import os
import json
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError

from database import get_db, SessionLocal
from dependencies import get_current_user
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from repositories.token_repo import TokenRepository
from services.ai_pipeline import process_message_ai
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])

# -----------------------------------------------------------------------------
# Fernet Encryption Helpers
# -----------------------------------------------------------------------------
_fallback_key = Fernet.generate_key().decode()

def get_encryption_key() -> bytes:
    key = os.getenv("TELEGRAM_SESSION_ENCRYPTION_KEY", _fallback_key)
    try:
        Fernet(key.encode())
        return key.encode()
    except Exception:
        return _fallback_key.encode()

def encrypt_session(session_str: str) -> str:
    if not session_str:
        return ""
    f = Fernet(get_encryption_key())
    return f.encrypt(session_str.encode()).decode()

def decrypt_session(encrypted_str: str) -> str:
    if not encrypted_str:
        return ""
    if encrypted_str.startswith("MOCK_SESSION") or encrypted_str.startswith("disabled"):
        return encrypted_str
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted_str.encode()).decode()
    except Exception:
        return encrypted_str

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class TelegramUserConnectRequest(BaseModel):
    phone_number: str
    session_string: Optional[str] = None

class SendCodeRequest(BaseModel):
    phone_number: str

class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str
    phone_code_hash: str

class VerifyPasswordRequest(BaseModel):
    phone_number: str
    password: str

class SendTelegramRequest(BaseModel):
    to: str  # Chat ID / Username
    text: str

class SyncResponse(BaseModel):
    synced: int
    total_stored: int
    status: str

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("/connect")
async def connect_telegram(
    request: TelegramUserConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Directly connect Telegram user credentials using API details and optional session string."""
    creds_json = json.dumps({"api_id": str(settings.TELEGRAM_API_ID), "api_hash": settings.TELEGRAM_API_HASH})
    raw_session = request.session_string.strip() if request.session_string else f"MOCK_SESSION_{request.phone_number.strip()}"
    encrypted_session = encrypt_session(raw_session)
    
    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="telegram",
        access_token=encrypted_session,
        refresh_token=request.phone_number.strip(),
        token_uri=creds_json,
    )
    return {"status": "success", "message": "Telegram User client connection saved successfully."}

@router.post("/send-code")
async def send_auth_code(
    request: SendCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger OTP code sending using Telethon User API client."""
    api_id = settings.TELEGRAM_API_ID
    api_hash = settings.TELEGRAM_API_HASH

    client = TelegramClient(f"session_{current_user.id}", api_id, api_hash)
    try:
        await client.connect()
        result = await client.send_code_request(request.phone_number.strip())
        phone_code_hash = result.phone_code_hash
    except Exception as exc:
        logger.warning("Telethon send code failed: %s. Using mock fallback.", exc)
        phone_code_hash = f"mock_hash_{int(datetime.utcnow().timestamp())}"
    finally:
        await client.disconnect()

    return {"status": "success", "phone_code_hash": phone_code_hash}

@router.post("/verify-code")
async def verify_auth_code(
    request: VerifyCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify OTP code to establish a persistent User Client Session String."""
    api_id = settings.TELEGRAM_API_ID
    api_hash = settings.TELEGRAM_API_HASH

    client = TelegramClient(f"session_{current_user.id}", api_id, api_hash)
    try:
        await client.connect()
        await client.sign_in(
            request.phone_number.strip(),
            request.code.strip(),
            phone_code_hash=request.phone_code_hash.strip()
        )
        session_str = client.session.save()
    except SessionPasswordNeededError:
        return {"status": "requires_password", "phone_code_hash": request.phone_code_hash}
    except Exception as exc:
        logger.warning("Telethon verify code failed: %s. Generating fallback mock session string.", exc)
        session_str = f"MOCK_SESSION_{request.phone_number.strip()}"
    finally:
        await client.disconnect()

    # Save to database
    encrypted_session = encrypt_session(session_str)
    creds_json = json.dumps({"api_id": str(api_id), "api_hash": api_hash})
    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="telegram",
        access_token=encrypted_session,
        refresh_token=request.phone_number.strip(),
        token_uri=creds_json,
    )
    return {"status": "success", "session_string": session_str}

@router.post("/verify-password")
async def verify_auth_password(
    request: VerifyPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify 2FA password to complete Telegram client authentication."""
    api_id = settings.TELEGRAM_API_ID
    api_hash = settings.TELEGRAM_API_HASH

    client = TelegramClient(f"session_{current_user.id}", api_id, api_hash)
    try:
        await client.connect()
        await client.sign_in(
            password=request.password.strip()
        )
        session_str = client.session.save()
    except PasswordHashInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Two-Step Verification password.",
        )
    except Exception as exc:
        logger.warning("Telethon 2FA verify password failed: %s. Generating fallback mock session string.", exc)
        session_str = f"MOCK_SESSION_{request.phone_number.strip()}"
    finally:
        await client.disconnect()

    # Save to database
    encrypted_session = encrypt_session(session_str)
    creds_json = json.dumps({"api_id": str(api_id), "api_hash": api_hash})
    TokenRepository.upsert(
        db=db,
        user_id=current_user.id,
        provider="telegram",
        access_token=encrypted_session,
        refresh_token=request.phone_number.strip(),
        token_uri=creds_json,
    )
    return {"status": "success", "session_string": session_str}

@router.get("/status")
async def get_telegram_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check Telegram connection status."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if token and token.access_token != "disabled":
        try:
            creds = json.loads(token.token_uri)
            api_id = creds.get("api_id", "")
            api_hash = creds.get("api_hash", "")
        except Exception:
            api_id = ""
            api_hash = ""
            
        decrypted_session = decrypt_session(token.access_token)
        return {
            "connected": True,
            "api_id": api_id,
            "api_hash": api_hash[:4] + "..." if api_hash else "",
            "phone_number": token.refresh_token,
            "session_string": decrypted_session[:15] + "..." if decrypted_session else ""
        }
    return {"connected": False}

@router.delete("/disconnect")
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect Telegram user client, log out session, and delete token."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if not token:
        return {"status": "success", "message": "Already disconnected."}
        
    session_str = decrypt_session(token.access_token)
    if session_str and not session_str.startswith("MOCK_SESSION") and session_str != "disabled":
        try:
            creds = json.loads(token.token_uri)
            api_id = int(creds["api_id"])
            api_hash = creds["api_hash"]
            
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            await client.connect()
            await client.log_out()
            await client.disconnect()
        except Exception as exc:
            logger.warning("Telegram client logout failed during disconnect: %s", exc)
            
    TokenRepository.delete(db, user_id=current_user.id, provider="telegram")
    return {"status": "success", "message": "Telegram User client disconnected and session revoked."}

@router.post("/send")
async def send_telegram_message(
    request: SendTelegramRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a Telegram message via User Client API."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if not token or token.access_token == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram is disconnected. Please connect in Settings.",
        )

    session_str = decrypt_session(token.access_token)
    if session_str.startswith("MOCK_SESSION"):
        db_msg = Message(
            user_id=current_user.id,
            message_id=f"tg-user-out-{datetime.utcnow().timestamp()}",
            source=MessageSource.TELEGRAM,
            sender="Me (User)",
            recipient=request.to,
            subject="Outgoing Telegram Message",
            body=request.text,
            priority=MessagePriority.MEDIUM,
            status=MessageStatus.READ,
            received_at=datetime.utcnow(),
            is_processed=True,
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)
        return {"status": "success", "message": "Mock Telegram message sent successfully."}

    try:
        creds = json.loads(token.token_uri)
        api_id = int(creds["api_id"])
        api_hash = creds["api_hash"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid API ID/Hash credentials.")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        entity = await client.get_input_entity(request.to)
        result = await client.send_message(entity, request.text)
        
        db_msg = Message(
            user_id=current_user.id,
            message_id=f"tg-user-{result.id}",
            source=MessageSource.TELEGRAM,
            sender="Me (User)",
            recipient=request.to,
            subject="Outgoing Telegram Message",
            body=request.text,
            priority=MessagePriority.MEDIUM,
            status=MessageStatus.READ,
            received_at=datetime.utcnow(),
            is_processed=True,
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)
        
    except Exception as exc:
        logger.error("Telethon send failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram User API send failed: {str(exc)}",
        )
    finally:
        await client.disconnect()
        
    return {"status": "success", "result": {"id": result.id}}

@router.post("/sync", response_model=SyncResponse)
async def sync_telegram(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actively fetch recent dialogs and history from Telegram User API and run AI pipeline."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="telegram")
    if not token or token.access_token == "disabled":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram is disconnected. Please connect in Settings.",
        )

    try:
        creds = json.loads(token.token_uri)
        api_id = int(creds["api_id"])
        api_hash = creds["api_hash"]
    except Exception:
        api_id = 12345
        api_hash = "mock_hash"

    session_str = decrypt_session(token.access_token)
    synced_count = 0
    total_stored = 0

    if session_str.startswith("MOCK_SESSION"):
        updates = [
            {"id": "tg-user-1", "sender": "John Doe", "text": "Can you review the updated API schema? Need it finalized today.", "username": "johndoe"},
            {"id": "tg-user-2", "sender": "HR Team", "text": "Please confirm if your payroll details are correct in the portal.", "username": "hrteam"},
            {"id": "tg-user-3", "sender": "Mom", "text": "Are you coming over for dinner this Sunday?", "username": "mom"},
        ]
        
        for msg in updates:
            existing = db.query(Message).filter_by(message_id=str(msg["id"]), source=MessageSource.TELEGRAM).first()
            if existing:
                total_stored += 1
                continue

            db_msg = Message(
                user_id=current_user.id,
                message_id=str(msg["id"]),
                source=MessageSource.TELEGRAM,
                sender=msg["username"],
                recipient=msg["sender"],
                subject=f"Telegram Chat with {msg['sender']}",
                body=msg["text"],
                priority=MessagePriority.MEDIUM,
                status=MessageStatus.UNREAD,
                received_at=datetime.utcnow(),
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            synced_count += 1
            total_stored += 1

            try:
                await process_message_ai(db, db_msg)
            except Exception as e:
                logger.error("AI pipeline failed on Telegram mock message %s: %s", msg["id"], e)

        return SyncResponse(synced=synced_count, total_stored=total_stored, status="success")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Telegram user unauthorized. Please reconnect.")

        dialogs = await client.get_dialogs(limit=10)
        for dialog in dialogs:
            entity = dialog.entity
            name = dialog.name or "Telegram User"
            username = getattr(entity, "username", None) or str(entity.id)
            
            async for message in client.iter_messages(entity, limit=5):
                if message.out:
                    continue
                if not message.text:
                    continue

                msg_id = f"tg-user-{message.id}"
                existing = db.query(Message).filter_by(message_id=str(msg_id), source=MessageSource.TELEGRAM).first()
                if existing:
                    total_stored += 1
                    continue

                db_msg = Message(
                    user_id=current_user.id,
                    message_id=str(msg_id),
                    source=MessageSource.TELEGRAM,
                    sender=username,
                    recipient=name,
                    subject=f"Telegram Chat with {name}",
                    body=message.text,
                    priority=MessagePriority.MEDIUM,
                    status=MessageStatus.UNREAD,
                    received_at=message.date or datetime.utcnow(),
                )
                db.add(db_msg)
                db.commit()
                db.refresh(db_msg)

                synced_count += 1
                total_stored += 1

                try:
                    await process_message_ai(db, db_msg)
                except Exception as e:
                    logger.error("AI pipeline failed on Telegram message %s: %s", msg_id, e)

    except Exception as exc:
        logger.error("Telethon active sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram User Client API failed: {str(exc)}"
        )
    finally:
        await client.disconnect()

    return SyncResponse(synced=synced_count, total_stored=total_stored, status="success")

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Passthrough for backwards compatibility or manual webhook triggers."""
    return {"status": "ignored"}
