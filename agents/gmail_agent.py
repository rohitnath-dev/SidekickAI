"""  
Gmail Agent  
  
This agent is responsible for interacting with the Gmail API.  
  
Responsibilities:  
- Authenticate with Google Gmail API  
- Fetch emails  
- Parse Gmail responses  
- Convert Gmail messages into Message models  
- Expose clean methods for other agents  
  
NOTE:  
This agent NEVER performs AI tasks.  
It only retrieves and normalizes Gmail data.  
"""  
  
from __future__ import annotations  
  
import base64  
import logging  
from datetime import datetime  
from email import message_from_bytes  
from typing import Any, Dict, List, Optional  
  
from google.auth.transport.requests import Request  
from google.oauth2.credentials import Credentials  
from googleapiclient.discovery import Resource, build  
from googleapiclient.errors import HttpError  
  
from agents.base_agent import BaseAgent  
from config import settings  
from models.message import Message  
  
logger = logging.getLogger(__name__)  
  
  
class GmailAgent(BaseAgent):  
    """  
    Gmail integration agent.  
  
    Provides a production-ready interface for interacting  
    with the Gmail API.  
  
    This class does NOT perform AI analysis.  
    It only fetches and prepares email data.  
    """  
  
    SCOPES = [  
        "https://www.googleapis.com/auth/gmail.readonly",  
    ]  
  
    def __init__(self) -> None:  
        """  
        Initialize GmailAgent.  
        """  
  
        super().__init__(agent_name="GmailAgent")  
  
        self.credentials: Optional[Credentials] = None  
        self.service: Optional[Resource] = None  
  
        self._initialize_service()  
  
    # ==========================================================  
    # INITIALIZATION  
    # ==========================================================  
  
    def _initialize_service(self) -> None:  
        """  
        Initialize Gmail API service.  
        """  
  
        try:  
  
            self.credentials = Credentials.from_authorized_user_file(  
                settings.GMAIL_TOKEN_FILE,  
                self.SCOPES,  
            )  
  
            if (  
                self.credentials.expired  
                and self.credentials.refresh_token  
            ):  
                self.credentials.refresh(Request())  
  
            self.service = build(  
                "gmail",  
                "v1",  
                credentials=self.credentials,  
            )  
  
            logger.info(  
                "Gmail service initialized successfully."  
            )  
  
        except Exception as exc:  
  
            logger.exception(  
                "Failed to initialize Gmail service."  
            )  
  
            raise RuntimeError(  
                "Unable to initialize Gmail API."  
            ) from exc  
  
    def is_connected(self) -> bool:  
        """  
        Check whether Gmail API is available.  
  
        Returns:  
            True if connected.  
        """  
  
        return (  
            self.service is not None  
            and self.credentials is not None  
            and self.credentials.valid  
        )  
  
    # ==========================================================  
    # GMAIL FETCH METHODS  
    # ==========================================================  
  
    def get_profile(self) -> Dict[str, Any]:  
        """  
        Fetch the Gmail account profile.  
  
        Returns:  
            Gmail profile information.  
  
        Raises:  
            RuntimeError:  
                If Gmail service is unavailable.  
        """  
  
        if not self.is_connected():  
            raise RuntimeError("Gmail service is not connected.")  
  
        try:  
  
            profile = (  
                self.service.users()  
                .getProfile(userId="me")  
                .execute()  
            )  
  
            logger.info(  
                "Fetched Gmail profile for %s.",  
                profile.get("emailAddress"),  
            )  
  
            return profile  
  
        except HttpError as exc:  
  
            logger.exception(  
                "Failed to fetch Gmail profile."  
            )  
  
            raise RuntimeError(  
                "Unable to fetch Gmail profile."  
            ) from exc  
  
    def get_recent_messages(  
        self,  
        limit: int = 10,  
    ) -> List[Dict[str, Any]]:  
        """  
        Fetch the most recent Gmail messages.  
  
        Args:  
            limit:  
                Maximum number of messages.  
  
        Returns:  
            List of Gmail message metadata.  
        """  
  
        if not self.is_connected():  
            raise RuntimeError("Gmail service is not connected.")  
  
        try:  
  
            response = (  
                self.service.users()  
                .messages()  
                .list(  
                    userId="me",  
                    maxResults=limit,  
                )  
                .execute()  
            )  
  
            messages = response.get(  
                "messages",  
                [],  
            )  
  
            logger.info(  
                "Fetched %d recent messages.",  
                len(messages),  
            )  
  
            return messages  
  
        except HttpError as exc:  
  
            logger.exception(  
                "Unable to fetch recent Gmail messages."  
            )  
  
            raise RuntimeError(  
                "Failed to fetch recent messages."  
            ) from exc  
  
    def get_unread_messages(  
        self,  
        limit: int = 10,  
    ) -> List[Dict[str, Any]]:  
        """  
        Fetch unread Gmail messages.  
  
        Args:  
            limit:  
                Maximum number of unread messages.  
  
        Returns:  
            List of unread Gmail message metadata.  
        """  
  
        if not self.is_connected():  
            raise RuntimeError("Gmail service is not connected.")  
  
        try:  
  
            response = (  
                self.service.users()  
                .messages()  
                .list(  
                    userId="me",  
                    labelIds=["UNREAD"],  
                    maxResults=limit,  
                )  
                .execute()  
            )  
  
            messages = response.get(  
                "messages",  
                [],  
            )  
  
            logger.info(  
                "Fetched %d unread messages.",  
                len(messages),  
            )  
  
            return messages  
  
        except HttpError as exc:  
  
            logger.exception(  
                "Unable to fetch unread Gmail messages."  
            )  
  
            raise RuntimeError(  
                "Failed to fetch unread messages."  
            ) from exc  
  
    def get_message(  
        self,  
        message_id: str,  
    ) -> Dict[str, Any]:  
        """  
        Fetch a complete Gmail message.  
  
        Args:  
            message_id:  
                Gmail message ID.  
  
        Returns:  
            Complete Gmail API response.  
        """  
  
        if not self.is_connected():  
            raise RuntimeError("Gmail service is not connected.")  
  
        try:  
  
            message = (  
                self.service.users()  
                .messages()  
                .get(  
                    userId="me",  
                    id=message_id,  
                    format="full",  
                )  
                .execute()  
            )  
  
            logger.debug(  
                "Fetched Gmail message %s.",  
                message_id,  
            )  
  
            return message  
  
        except HttpError as exc:  
  
            logger.exception(  
                "Unable to fetch Gmail message."  
            )  
  
            raise RuntimeError(  
                f"Failed to fetch message '{message_id}'."  
            ) from exc  
  
    # ==========================================================  
    # MESSAGE PARSING  
    # ==========================================================  
  
    def _decode_base64(self, data: str) -> str:  
        """  
        Decode a Gmail Base64 URL-safe encoded string.  
  
        Args:  
            data:  
                Base64 encoded Gmail content.  
  
        Returns:  
            Decoded UTF-8 string.  
        """  
  
        if not data:  
            return ""  
  
        try:  
            decoded = base64.urlsafe_b64decode(data.encode("UTF-8"))  
  
            return decoded.decode(  
                "UTF-8",  
                errors="ignore",  
            )  
  
        except Exception:  
  
            logger.exception(  
                "Failed to decode Gmail message body."  
            )  
  
            return ""  
  
    def _extract_headers(  
        self,  
        payload: Dict[str, Any],  
    ) -> Dict[str, str]:  
        """  
        Extract useful email headers.  
  
        Args:  
            payload:  
                Gmail payload.  
  
        Returns:  
            Dictionary containing important headers.  
        """  
  
        result = {  
            "From": "",  
            "To": "",  
            "Subject": "",  
            "Date": "",  
        }  
  
        headers = payload.get(  
            "headers",  
            [],  
        )  
  
        for header in headers:  
  
            name = header.get("name")  
  
            if name in result:  
  
                result[name] = header.get(  
                    "value",  
                    "",  
                )  
  
        return result  
  
    def _extract_body(  
        self,  
        payload: Dict[str, Any],  
    ) -> str:  
        """  
        Extract plain-text email body.  
  
        Args:  
            payload:  
                Gmail payload.  
  
        Returns:  
            Email body as plain text.  
        """  
  
        body = payload.get(  
            "body",  
            {},  
        )  
  
        if body.get("data"):  
  
            return self._decode_base64(  
                body["data"],  
            )  
  
        for part in payload.get(  
            "parts",  
            [],  
        ):  
  
            mime = part.get(  
                "mimeType",  
                "",  
            )  
  
            if mime == "text/plain":  
  
                data = (  
                    part.get(  
                        "body",  
                        {},  
                    ).get(  
                        "data",  
                    )  
                )  
  
                if data:  
  
                    return self._decode_base64(  
                        data,  
                    )  
  
        return ""  
  
    def _parse_message(  
        self,  
        gmail_message: Dict[str, Any],  
    ) -> Dict[str, Any]:  
        """  
        Convert Gmail API response into a normalized dictionary.  
  
        Args:  
            gmail_message:  
                Raw Gmail API response.  
  
        Returns:  
            Normalized message dictionary.  
        """  
  
        payload = gmail_message.get(  
            "payload",  
            {},  
        )  
  
        headers = self._extract_headers(  
            payload,  
        )  
  
        body = self._extract_body(  
            payload,  
        )  
  
        return {  
            "message_id": gmail_message.get("id"),  
            "thread_id": gmail_message.get("threadId"),  
            "sender": headers["From"],  
            "recipient": headers["To"],  
            "subject": headers["Subject"],  
            "received_at": headers["Date"],  
            "body": body,  
        }  
  
    # ==========================================================  
    # MODEL CONVERSION  
    # ==========================================================  
  
    def parse_to_model(  
        self,  
        gmail_message: Dict[str, Any],  
    ) -> Message:  
        """  
        Convert a raw Gmail API message into a Message model.  
  
        Args:  
            gmail_message:  
                Raw Gmail API response.  
  
        Returns:  
            Message model instance.  
        """  
  
        parsed = self._parse_message(gmail_message)  
  
        return Message(  
            message_id=parsed["message_id"],  
            thread_id=parsed["thread_id"],  
            source="gmail",  
            sender=parsed["sender"],  
            recipient=parsed["recipient"],  
            subject=parsed["subject"],  
            body=parsed["body"],  
            received_at=datetime.utcnow(),  
        )  
  
    def fetch_recent_models(  
        self,  
        limit: int = 10,  
    ) -> List[Message]:  
        """  
        Fetch recent Gmail messages as Message models.  
  
        Args:  
            limit:  
                Maximum number of messages.  
  
        Returns:  
            List of Message objects.  
        """  
  
        models: List[Message] = []  
  
        recent = self.get_recent_messages(limit)  
  
        for item in recent:  
  
            raw = self.get_message(  
                item["id"],  
            )  
  
            models.append(  
                self.parse_to_model(raw)  
            )  
  
        logger.info(  
            "Converted %d recent Gmail messages.",  
            len(models),  
        )  
  
        return models  
  
    def fetch_unread_models(  
        self,  
        limit: int = 10,  
    ) -> List[Message]:  
        """  
        Fetch unread Gmail messages as Message models.  
  
        Args:  
            limit:  
                Maximum number of unread messages.  
  
        Returns:  
            List of Message objects.  
        """  
  
        models: List[Message] = []  
  
        unread = self.get_unread_messages(limit)  
  
        for item in unread:  
  
            raw = self.get_message(  
                item["id"],  
            )  
  
            models.append(  
                self.parse_to_model(raw)  
            )  
  
        logger.info(  
            "Converted %d unread Gmail messages.",  
            len(models),  
        )  
  
        return models  
  
