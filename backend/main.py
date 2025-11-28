from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.services.llm import get_llm_service, LLMService
from fastapi import Depends

# Configure logging before app startup
configure_logging()
logger = structlog.get_logger()

from backend.database import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Wendy Backend...")
    await db.connect()
    yield
    await db.close()
    logger.info("Shutting down Wendy Backend...")

from backend.api import chat, vision

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    
    app.include_router(chat.router)
    app.include_router(vision.router)
    
    @app.get("/health")
    async def health_check(llm: LLMService = Depends(get_llm_service)):
        models = await llm.list_models()
        return {
            "status": "ok", 
            "version": settings.VERSION,
            "models_available": models,
            "mongodb": "connected" if db.client else "disconnected"
        }
        
    return app

app = create_app()

def start():
    import uvicorn
    settings = get_settings()
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)

if __name__ == "__main__":
    start()
