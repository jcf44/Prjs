import asyncio
import httpx
from backend.main import app
from backend.config import get_settings
import structlog
import os

logger = structlog.get_logger()

async def verify():
    settings = get_settings()
    base_url = f"http://{settings.HOST}:{settings.PORT}"
    
    # We will use TestClient for simplicity if we can, but since we want to test the actual running server logic
    # including async database connections, let's try to start the app using uvicorn programmatically or just use TestClient which supports lifespan
    
    from fastapi.testclient import TestClient
    
    logger.info("Starting verification...")
    
    with TestClient(app) as client:
        # 1. Health Check
        logger.info("Testing /health endpoint...")
        response = client.get("/health")
        if response.status_code == 200:
            data = response.json()
            logger.info("Health check passed", response=data)
            if "models_available" in data:
                logger.info("Models available", models=data["models_available"])
        else:
            logger.error("Health check failed", status=response.status_code, response=response.text)
            return

        # 2. Chat Completion (Stateless)
        logger.info("Testing /v1/chat/completions endpoint...")
        payload = {
            "model": "auto", 
            "messages": [{"role": "user", "content": "Say hello!"}],
            "stream": False
        }
        
        try:
            response = client.post("/v1/chat/completions", json=payload)
            if response.status_code == 200:
                logger.info("Chat completion passed", response=response.json())
            else:
                logger.warning("Chat completion failed", status=response.status_code, response=response.text)
        except Exception as e:
            logger.error("Chat completion error", error=str(e))

        # 3. Stateful Chat (Memory & Routing)
        logger.info("Testing /v1/chat endpoint (Stateful)...")
        simple_payload = {
            "message": "My name is Wendy.",
            "model": "auto"
        }
        
        try:
            response = client.post("/v1/chat", json=simple_payload)
            if response.status_code == 200:
                data = response.json()
                logger.info("Stateful chat passed", response=data)
                conversation_id = data.get("conversation_id")
                
                # Follow up to test memory
                if conversation_id:
                    follow_up = {
                        "message": "What is my name?",
                        "conversation_id": conversation_id
                    }
                    response = client.post("/v1/chat", json=follow_up)
                    if response.status_code == 200:
                        logger.info("Memory test passed", response=response.json())
                    else:
                        logger.warning("Memory test failed", status=response.status_code, response=response.text)
                
                # Test Conversation List
                logger.info("Testing /v1/conversations endpoint...")
                response = client.get("/v1/conversations")
                if response.status_code == 200:
                    logger.info("Conversation list passed", response=response.json())
                else:
                    logger.warning("Conversation list failed", status=response.status_code, response=response.text)
                    
            else:
                logger.warning("Stateful chat failed", status=response.status_code, response=response.text)
        except Exception as e:
            logger.error("Stateful chat error", error=str(e))

        # 4. Document Ingestion & RAG
        logger.info("Testing Document Ingestion...")
        # Create a dummy text file
        with open("test_doc.txt", "w") as f:
            f.write("Wendy is a local AI assistant created by the user. She uses Ollama for intelligence.")
            
        try:
            with open("test_doc.txt", "rb") as f:
                files = {"file": ("test_doc.txt", f, "text/plain")}
                response = client.post("/v1/documents/ingest", files=files)
                
            if response.status_code == 200:
                logger.info("Ingestion passed", response=response.json())
                
                # Test RAG Query
                logger.info("Testing RAG Query...")
                rag_payload = {
                    "message": "Who created Wendy?",
                    "model": "qwen3:32b-q4_K_M" # Force Doc Brain to trigger RAG logic
                }
                response = client.post("/v1/chat", json=rag_payload)
                if response.status_code == 200:
                    data = response.json()
                    logger.info("RAG query passed", response=data)
                    if "sources" in data and len(data["sources"]) > 0:
                        logger.info("RAG successfully cited sources", sources=data["sources"])
                    else:
                        logger.warning("RAG did not cite sources (might be expected if model missing)")
                else:
                    logger.warning("RAG query failed", status=response.status_code, response=response.text)
            else:
                logger.warning("Ingestion failed", status=response.status_code, response=response.text)
        except Exception as e:
            logger.error("RAG test error", error=str(e))
        finally:
            if os.path.exists("test_doc.txt"):
                os.remove("test_doc.txt")

        # 5. Vision (Mock Test)
        logger.info("Testing /v1/vision/analyze endpoint...")
        # Tiny 1x1 transparent GIF base64
        dummy_image = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        vision_payload = {
            "image": dummy_image,
            "prompt": "What is this?"
        }
        
        try:
            response = client.post("/v1/vision/analyze", json=vision_payload)
            if response.status_code == 200:
                logger.info("Vision analysis passed", response=response.json())
            elif response.status_code == 500:
                 # Expected if model not pulled
                logger.warning("Vision analysis failed (expected if model missing)", status=response.status_code, response=response.text)
            else:
                logger.warning("Vision analysis failed", status=response.status_code, response=response.text)
        except Exception as e:
            logger.error("Vision analysis error", error=str(e))

if __name__ == "__main__":
    # Configure logging for the script
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    asyncio.run(verify())
