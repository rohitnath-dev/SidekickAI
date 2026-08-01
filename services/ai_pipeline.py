import logging
from sqlalchemy.orm import Session
from models.message import Message, MessagePriority
from agents.priority_agent import PriorityAgent
from agents.summary_agent import SummaryAgent
from agents.reply_agent import ReplyAgent

logger = logging.getLogger(__name__)

async def process_message_ai(db: Session, message: Message) -> None:
    """
    Runs the full AI agent pipeline for a message:
    1. Priority ranking
    2. Summary and action items extraction
    3. Suggested reply draft generation
    Updates the database record and commits.
    """
    try:
        logger.info("Running AI pipeline for message %d (source=%s)", message.id, message.source.value)
        
        # 1. Priority Agent
        priority_agent = PriorityAgent()
        priority_result = await priority_agent.analyze(message)
        
        level_str = priority_result.get("priority_level", "medium").lower()
        try:
            priority_enum = MessagePriority(level_str)
        except ValueError:
            priority_enum = MessagePriority.MEDIUM
            
        requires_reply = bool(priority_result.get("requires_reply", False))
        confidence_score = priority_result.get("score")
        
        # 2. Summary Agent
        summary_agent = SummaryAgent()
        # Generate summary
        summary_result = await summary_agent.generate_summary(message.body)
        summary = summary_result.get("summary", "") if isinstance(summary_result, dict) else ""
        sentiment = summary_result.get("sentiment", "") if isinstance(summary_result, dict) else ""
        category = summary_result.get("category", "") if isinstance(summary_result, dict) else ""
        
        # Extract action items
        action_result = await summary_agent.extract_action_items(message.body)
        action_items = ""
        if isinstance(action_result, dict):
            items_list = action_result.get("action_items", [])
            if isinstance(items_list, list):
                action_items = "\n".join(f"- {i}" for i in items_list)
            else:
                action_items = str(items_list)
        
        # 3. Reply Agent
        reply_agent = ReplyAgent()
        sender_name = message.sender.split("<")[0].strip() if message.sender else "User"
        reply_result = await reply_agent.generate_reply(
            recipient_name=sender_name,
            email_content=message.body,
        )
        suggested_reply = reply_result.get("reply", "") if isinstance(reply_result, dict) else ""
        
        # Update model
        message.update_from_ai(
            summary=summary,
            priority=priority_enum,
            sentiment=sentiment,
            category=category,
            action_items=action_items,
            suggested_reply=suggested_reply,
            confidence_score=confidence_score,
            requires_reply=requires_reply,
        )
        db.commit()
        logger.info("AI pipeline completed successfully for message %d", message.id)
        
    except Exception as e:
        logger.error("Failed to run AI pipeline for message %d: %s", message.id, e, exc_info=True)
        # Set processed = True anyway so it doesn't get stuck
        message.is_processed = True
        db.commit()
