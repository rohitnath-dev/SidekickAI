"""WhatsApp routes — Meta Cloud API integration."""

from __future__ import annotations

import logging
import hmac
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from routes.gmail import MessageResponse, _msg_to_response

from config import settings
from dependencies import get_current_user, get_optional_user
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    to: str          # E.164 phone number e.g. "15551234567"
    text: str


class ReplyRequest(BaseModel):
    sender_name: str
    message_content: str
    to: str
    context: Optional[str] = None
    auto_send: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_whatsapp():
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp is not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Webhook verification endpoint for Meta (no auth required)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified.")
        return hub_challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed.")


async def verify_whatsapp_signature(request: Request) -> bytes:
    """Validate signature to ensure incoming payload is genuinely from Meta."""
    if not settings.WHATSAPP_APP_SECRET:
        # Bypassed if not configured for local development ease
        return await request.body()

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        logger.warning("WhatsApp Webhook: Missing or invalid signature header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid signature header."
        )

    received_sig = signature.split("sha256=")[1]
    body = await request.body()
    
    expected_sig = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        logger.warning("WhatsApp Webhook: HMAC signature validation failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HMAC signature validation failed."
        )

    return body


async def process_whatsapp_payload_async(body: dict) -> None:
    """Asynchronously process incoming WhatsApp webhook payloads."""
    from agents.whatsapp_agent import WhatsAppAgent
    from models.message import Message, MessageSource, MessagePriority, MessageStatus
    from datetime import datetime
    from services.ai_pipeline import process_message_ai

    db = SessionLocal()
    try:
        messages = await WhatsAppAgent().get_webhook_messages(body)
        for msg in messages:
            sender = msg.get("from", "")
            text = msg.get("text", "")
            msg_id = msg.get("message_id", "")
            if not msg_id:
                continue

            logger.info("Background WhatsApp processing: message from %s", sender)

            # Skip if already exists
            existing = db.query(Message).filter_by(message_id=msg_id, source=MessageSource.WHATSAPP).first()
            if existing:
                continue

            # Find user
            from models.user import User
            user = db.query(User).first()
            user_id = user.id if user else 1

            db_msg = Message(
                user_id=user_id,
                message_id=msg_id,
                source=MessageSource.WHATSAPP,
                sender=sender,
                body=text,
                priority=MessagePriority.MEDIUM,
                status=MessageStatus.UNREAD,
                received_at=datetime.utcnow()
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            # Trigger AI pipeline
            try:
                await process_message_ai(db, db_msg)
            except Exception as e:
                logger.error("Failed to run AI pipeline for WhatsApp message %s: %s", msg_id, e)
    except Exception as exc:
        logger.error("Background WhatsApp processing error: %s", exc)
    finally:
        db.close()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receive incoming WhatsApp messages from Meta (no auth required)."""
    try:
        raw_body = await verify_whatsapp_signature(request)
        body = json.loads(raw_body)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("WhatsApp Webhook parsing error: %s", exc)
        return {"status": "ok"}

    # Process payload in the background asynchronously
    background_tasks.add_task(process_whatsapp_payload_async, body)

    # Always return 200 OK instantly to Meta
    return {"status": "ok"}


@router.get("/authorize")
async def authorize(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Generate the Meta/WhatsApp Business Login OAuth consent URL."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        token = request.query_params.get("token")

    try:
        from services.whatsapp_auth import generate_whatsapp_authorization_url
        url, state = generate_whatsapp_authorization_url(state=token)
    except Exception as exc:
        logger.error("Failed to generate WhatsApp authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate WhatsApp authorization URL. Check META_APP_ID.",
        )
    return {"authorization_url": url, "state": state}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(default=""),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Exchange the Meta auth code for tokens and store them."""
    user_id = None
    if current_user:
        user_id = current_user.id
    elif state:
        from dependencies import decode_access_token
        user_id_str = decode_access_token(state)
        if user_id_str:
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                pass

    if not user_id:
        logger.error("WhatsApp OAuth callback failed: User could not be identified.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found. Please log in again and reconnect.",
        )

    try:
        from services.whatsapp_auth import exchange_whatsapp_code_for_tokens
        await exchange_whatsapp_code_for_tokens(code=code, state=state, db=db, user_id=user_id)
    except Exception as exc:
        logger.error("WhatsApp OAuth exchange failed for user %s: %s", user_id, exc)
        
        detail = "Could not find a connected WhatsApp Business Account (WABA) ID. Make sure permissions are granted."
        if isinstance(exc, HTTPException):
            detail = exc.detail
        elif hasattr(exc, "detail"):
            detail = exc.detail
        else:
            detail = str(exc)
            
        return HTMLResponse(
            status_code=400,
            content=f"""
            <html>
                <head>
                    <title>WhatsApp Connection Error</title>
                    <script type="text/javascript">
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: "whatsapp-connection-error", 
                                message: {json.dumps(detail)}
                            }}, window.location.origin);
                        }}
                    </script>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
                    <style>
                        body {{
                            font-family: 'Inter', sans-serif;
                            background-color: #09090b;
                            color: #e4e4e7;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            padding: 0 20px;
                        }}
                        .card {{
                            max-width: 450px;
                            background-color: #18181b;
                            border: 1px solid #27272a;
                            border-radius: 12px;
                            padding: 30px;
                            text-align: center;
                            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                        }}
                        h2 {{
                            color: #f87171;
                            margin-top: 0;
                            font-size: 20px;
                        }}
                        p {{
                            font-size: 14px;
                            color: #a1a1aa;
                            line-height: 1.5;
                        }}
                        .btn {{
                            display: inline-block;
                            margin-top: 20px;
                            padding: 10px 20px;
                            background-color: #3b82f6;
                            color: white;
                            text-decoration: none;
                            border-radius: 6px;
                            font-size: 14px;
                            font-weight: 500;
                            transition: background-color 0.2s;
                        }}
                        .btn:hover {{
                            background-color: #2563eb;
                        }}
                        .btn-secondary {{
                            background-color: transparent;
                            border: 1px solid #27272a;
                            color: #a1a1aa;
                            margin-left: 10px;
                        }}
                        .btn-secondary:hover {{
                            background-color: #27272a;
                            color: white;
                        }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>Connection Failed</h2>
                        <p>{detail}</p>
                        <p style="margin-top: 15px; font-size: 13px; color: #a1a1aa;">
                            <strong>Note:</strong> A Meta WhatsApp Business Account (WABA) with a registered business phone number is required. Personal WhatsApp accounts cannot be connected.
                        </p>
                        <a href="https://developers.facebook.com/docs/whatsapp/overview" target="_blank" class="btn">Meta Documentation</a>
                        <button onclick="window.close()" class="btn btn-secondary">Close Window</button>
                    </div>
                </body>
            </html>
            """
        )
    
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>WhatsApp Connected Successfully</title>
                <script type="text/javascript">
                    if (window.opener) {
                        window.opener.postMessage("whatsapp-connected", window.location.origin);
                    }
                    window.close();
                </script>
            </head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                <h2>WhatsApp Business Account connected successfully!</h2>
                <p>This window will close automatically.</p>
            </body>
        </html>
        """
    )


def handle_whatsapp_error(exc: Exception):
    import httpx
    
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        try:
            body = exc.response.json()
            error_data = body.get("error", {})
            message = error_data.get("message", "WhatsApp API error")
            code = error_data.get("code", status_code)
        except Exception:
            message = exc.response.text or "WhatsApp API error"
            code = status_code
            
        if status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "WHATSAPP_AUTH_FAILED",
                    "message": "WhatsApp authentication failed. Please update your API token in the settings.",
                    "action": "reconnect",
                }
            )
            
        if status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "WHATSAPP_RATE_LIMIT",
                    "message": "WhatsApp API rate limit exceeded. Please try again later.",
                    "action": "wait",
                }
            )
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": f"WHATSAPP_API_ERROR_{code}",
                "message": f"WhatsApp error: {message}",
                "action": "retry",
            }
        )
        
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "code": "WHATSAPP_GATEWAY_ERROR",
            "message": f"Failed to communicate with WhatsApp API: {str(exc)}",
            "action": "retry",
        }
    )


@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent
    from repositories.token_repo import TokenRepository

    # Try database credentials first
    token = TokenRepository.get(db, user_id=current_user.id, provider="whatsapp")
    if token and token.access_token != "disabled":
        api_token = token.access_token
        phone_number_id = token.refresh_token
    else:
        if token and token.access_token == "disabled":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp is disconnected. Please connect in settings.",
            )
        if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp is not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID, or connect via settings.",
            )
        api_token = settings.WHATSAPP_API_TOKEN
        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

    try:
        result = await WhatsAppAgent().send_message(
            api_token=api_token,
            phone_number_id=phone_number_id,
            to=request.to,
            text=request.text,
        )
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        handle_whatsapp_error(exc)

    msg_id = None
    if isinstance(result, dict):
        msgs = result.get("messages", [])
        if msgs:
            msg_id = msgs[0].get("id")

    return {"status": "sent", "message_id": msg_id}


@router.post("/reply/generate")
async def generate_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI reply to a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent

    try:
        reply_text = await WhatsAppAgent().generate_reply_text(
            sender_name=request.sender_name,
            message_content=request.message_content,
            context=request.context,
        )
    except Exception as exc:
        logger.error("WhatsApp reply generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return {"reply_text": reply_text}


@router.post("/reply/send")
async def send_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and send an AI reply to a WhatsApp message."""
    from agents.whatsapp_agent import WhatsAppAgent
    from repositories.token_repo import TokenRepository

    # Try database credentials first
    token = TokenRepository.get(db, user_id=current_user.id, provider="whatsapp")
    if token and token.access_token != "disabled":
        api_token = token.access_token
        phone_number_id = token.refresh_token
    else:
        if token and token.access_token == "disabled":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp is disconnected. Please connect in settings.",
            )
        if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="WhatsApp is not configured. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID, or connect via settings.",
            )
        api_token = settings.WHATSAPP_API_TOKEN
        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

    agent = WhatsAppAgent()
    try:
        reply_text = await agent.generate_reply_text(
            sender_name=request.sender_name,
            message_content=request.message_content,
            context=request.context,
        )
        result = await agent.send_message(
            api_token=api_token,
            phone_number_id=phone_number_id,
            to=request.to,
            text=reply_text,
        )
    except Exception as exc:
        logger.error("WhatsApp reply send failed: %s", exc)
        handle_whatsapp_error(exc)

    msg_id = None
    if isinstance(result, dict):
        msgs = result.get("messages", [])
        if msgs:
            msg_id = msgs[0].get("id")

    return {"status": "sent", "reply_text": reply_text, "message_id": msg_id}


@router.get("/messages", response_model=list[MessageResponse])
async def list_whatsapp_messages(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    high_priority_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List stored WhatsApp messages for the current user."""
    from repositories.message_repo import MessageRepository

    messages = MessageRepository.list_by_user(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        source="whatsapp",
        high_priority_only=high_priority_only,
    )
    return [_msg_to_response(m) for m in messages]
