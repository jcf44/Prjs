from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    DOCX = "docx"
    PDF = "pdf"
    XLSX = "xlsx"
    PPTX = "pptx"
    MD = "md"
    TXT = "txt"

class Document(BaseModel):
    path: str
    filename: str
    document_type: DocumentType
    file_hash: str
    size_bytes: int
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    indexed_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_profile: str
    project_id: str = "default" # Default for migration

    model_config = ConfigDict(populate_by_name=True)

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    input_type: str = "text" # text, voice
    attachments: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    sources: List[str] = Field(default_factory=list)

class Conversation(BaseModel):
    conversation_id: str
    user_profile: str
    project_id: str = "default" # Default for migration
    started_at: datetime = Field(default_factory=datetime.now)
    last_message_at: datetime = Field(default_factory=datetime.now)
    title: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UserRole(str, Enum):
    ADMIN = "admin"
    STANDARD = "standard"
    RESTRICTED = "restricted"

class UserProfile(BaseModel):
    profile_id: str
    display_name: str
    role: UserRole
    preferences: Dict[str, Any] = Field(default_factory=dict)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: Optional[datetime] = None
