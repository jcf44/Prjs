from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from backend.services.llm import get_llm_service, LLMService
from backend.services.memory import get_memory_service, MemoryService
from backend.services.router import get_router_service, RouterService
from backend.services.rag import get_rag_service, RAGService
from backend.domain.models import Message, MessageRole
import structlog
import uuid
import re

router = APIRouter(prefix="/v1", tags=["chat"])
logger = structlog.get_logger()

WENDY_SYSTEM_PROMPT = """You are Wendy, a helpful local AI assistant. 
You are knowledgeable, friendly, and focused on being genuinely helpful.
You have access to the user's personal knowledge base and can help with 
documents, research, and technical questions."""

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "auto" 
    messages: List[ChatMessage]
    stream: bool = False
    user_profile: Optional[str] = "default"

class SimpleChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_profile: str = "default"
    model: str = "auto"
    stream: bool = False

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    llm: LLMService = Depends(get_llm_service),
    router_service: RouterService = Depends(get_router_service)
):
    try:
        model = request.model
        if model == "auto":
            # Use the last user message for routing
            last_user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
            model = router_service.route(last_user_msg)
            logger.info("Auto-routed model", selected_model=model)

        # Convert Pydantic models to dicts for Ollama
        messages = [msg.model_dump() for msg in request.messages]
        
        response = await llm.chat(
            model=model,
            messages=messages,
            stream=request.stream
        )
        
        return response
    except Exception as e:
        logger.error("Chat completion failed", error=str(e))
        if "model" in str(e).lower() and "not found" in str(e).lower():
             raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Model not available: {model}"
            )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def simple_chat(
    request: SimpleChatRequest,
    llm: LLMService = Depends(get_llm_service),
    memory: MemoryService = Depends(get_memory_service),
    router_service: RouterService = Depends(get_router_service),
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        conversation_id = request.conversation_id
        
        # 1. Create conversation if needed
        if not conversation_id:
            conv = await memory.create_conversation(
                user_profile=request.user_profile, 
                first_message=request.message
            )
            conversation_id = conv.conversation_id
        
        # 2. Add user message to memory
        user_msg = Message(role=MessageRole.USER, content=request.message)
        await memory.add_message(conversation_id, user_msg)
        
        # 3. Retrieve history
        conversation = await memory.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        # 4. Determine model
        model = request.model
        if model == "auto":
            model = router_service.route(request.message)
            
        # 5. Check for RAG trigger
        use_rag = request.model == "rag" # Explicit flag if model is "rag"
        
        # Heuristic detection
        if not use_rag:
             rag_triggers = [
                r"in my (documents?|files?|notes?)",
                r"according to",
                r"what does .* say about",
                r"find .* in",
                r"search (for|my)",
            ]
             if any(re.search(p, request.message, re.IGNORECASE) for p in rag_triggers):
                 use_rag = True
                 logger.info("RAG triggered by heuristic")
        
        # Also trigger if model is DOC_BRAIN (legacy behavior)
        if "qwen3" in model:
            use_rag = True

        assistant_content = ""
        sources = []
        
        # 6. Call LLM (with or without RAG)
        if use_rag:
             # Ensure we use a capable model for RAG
             rag_model = model if model != "auto" else router_service.doc_brain_model
             rag_response = await rag_service.query(request.message, model=rag_model)
             assistant_content = rag_response["answer"]
             sources = [meta.get("filename", "unknown") for meta in rag_response.get("sources", [])]
             # Deduplicate sources
             sources = list(set(sources))
             model = rag_model # Update model used for logging
        else:
            # Standard Chat
            history = [{"role": "system", "content": WENDY_SYSTEM_PROMPT}]
            history.extend([
                {"role": msg.role.value, "content": msg.content} 
                for msg in conversation.messages
            ])
            response = await llm.chat(model=model, messages=history, stream=False)
            assistant_content = response['message']['content']

        # 7. Add assistant message to memory
        assistant_msg = Message(
            role=MessageRole.ASSISTANT, 
            content=assistant_content,
            model_used=model,
            sources=sources
        )
        await memory.add_message(conversation_id, assistant_msg)
        
        return {
            "answer": assistant_content,
            "conversation_id": conversation_id,
            "model_used": model,
            "sources": sources
        }
        
    except Exception as e:
        logger.error("Simple chat failed", error=str(e))
        if "model" in str(e).lower() and "not found" in str(e).lower():
             raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Model not available: {model}"
            )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations")
async def list_conversations(
    user_profile: str = "default",
    limit: int = 10,
    memory: MemoryService = Depends(get_memory_service)
):
    conversations = await memory.get_recent_conversations(user_profile, limit)
    return {
        "conversations": [
            {
                "conversation_id": c.conversation_id,
                "title": c.title,
                "last_message_at": c.last_message_at,
                "message_count": len(c.messages)
            }
            for c in conversations
        ]
    }
