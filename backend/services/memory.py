from datetime import datetime
from typing import List, Optional
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.database import get_database
from backend.domain.models import Conversation, Message, MessageRole
import structlog

logger = structlog.get_logger()

class MemoryService:
    def __init__(self):
        self.collection_name = "conversations"

    async def get_collection(self):
        db = await get_database()
        return db[self.collection_name]

    async def create_conversation(self, user_profile: str, title: Optional[str] = None, first_message: Optional[str] = None) -> Conversation:
        collection = await self.get_collection()
        conversation_id = str(uuid.uuid4())
        
        if not title and first_message:
            title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        
        conversation = Conversation(
            conversation_id=conversation_id,
            user_profile=user_profile,
            title=title,
            started_at=datetime.now(),
            last_message_at=datetime.now(),
            messages=[]
        )
        
        await collection.insert_one(conversation.model_dump(mode="json"))
        logger.info("Created new conversation", conversation_id=conversation_id, user_profile=user_profile, title=title)
        return conversation

    async def add_message(self, conversation_id: str, message: Message):
        collection = await self.get_collection()
        
        update_result = await collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$push": {"messages": message.model_dump(mode="json")},
                "$set": {"last_message_at": datetime.now()}
            }
        )
        
        if update_result.modified_count == 0:
            logger.warning("Conversation not found for update", conversation_id=conversation_id)
            # Optionally create if not exists, but for now let's assume it exists
            
        logger.debug("Added message to conversation", conversation_id=conversation_id, role=message.role)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        collection = await self.get_collection()
        doc = await collection.find_one({"conversation_id": conversation_id})
        
        if doc:
            return Conversation(**doc)
        return None

    async def get_recent_conversations(self, user_profile: str, limit: int = 10) -> List[Conversation]:
        collection = await self.get_collection()
        cursor = collection.find({"user_profile": user_profile}).sort("last_message_at", -1).limit(limit)
        
        conversations = []
        async for doc in cursor:
            conversations.append(Conversation(**doc))
            
        return conversations

_memory_service: MemoryService | None = None

def get_memory_service():
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
