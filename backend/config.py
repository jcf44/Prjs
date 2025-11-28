from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    APP_NAME: str = "Wendy"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8181
    
    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "wendy"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Models
    DOC_BRAIN_MODEL: str = "qwen3:32b-q4_K_M"
    FAST_BRAIN_MODEL: str = "qwen2.5:14b"
    VISION_MODEL: str = "qwen2.5-vl:7b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # RAG
    CHROMA_DB_PATH: str = os.path.join(os.path.expanduser("~"), ".wendy", "chroma_db")
    
    # Voice
    WAKE_WORD_MODEL_PATH: str = "" # Empty means default or auto-download
    STT_MODEL_SIZE: str = "base.en"
    TTS_VOICE: str = "en_US-lessac-medium"
    AUDIO_DEVICE_INDEX: Optional[int] = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings():
    return Settings()
