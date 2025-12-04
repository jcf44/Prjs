# Wendy - Local AI Assistant

## Project Overview

Wendy is a local AI assistant application that provides chat, document analysis, RAG (Retrieval-Augmented Generation), vision, and voice interaction capabilities. The application uses Ollama for local LLM inference and is built with a FastAPI backend and Next.js frontend.

## Architecture

### Tech Stack

**Backend (Python)**
- FastAPI for REST API
- Motor for async MongoDB operations
- ChromaDB for vector storage (RAG)
- Ollama for LLM inference
- PyMuPDF, pdfplumber for PDF processing
- faster-whisper for speech-to-text
- sherpa-onnx for wake word detection and TTS
- structlog for structured logging

**Frontend (TypeScript/React)**
- Next.js 16 (App Router)
- React 19
- Tailwind CSS v4
- Radix UI components
- Zustand for state management
- react-markdown for message rendering

### Project Structure

```
.
├── backend/
│   ├── api/               # API route handlers
│   │   ├── chat.py       # Chat endpoint
│   │   ├── documents.py  # Document management
│   │   ├── projects.py   # Project management
│   │   ├── vision.py     # Vision/image analysis
│   │   └── voice.py      # Voice interaction
│   ├── domain/           # Domain models
│   ├── services/         # Business logic
│   │   ├── converter.py  # Document conversion (PDF→Markdown)
│   │   ├── ingestion.py  # Document ingestion
│   │   ├── llm.py        # LLM service wrapper
│   │   ├── memory.py     # Conversation memory
│   │   ├── project.py    # Project management
│   │   ├── rag.py        # RAG implementation
│   │   ├── router.py     # Semantic routing
│   │   ├── vector_db.py  # ChromaDB wrapper
│   │   ├── vision.py     # Vision processing
│   │   └── voice/        # Voice pipeline components
│   ├── repositories/     # Data access layer
│   ├── config.py         # Configuration settings
│   ├── database.py       # MongoDB connection
│   ├── logging_config.py # Logging setup
│   └── main.py           # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js app router pages
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── lib/          # Utilities
│   │   └── stores/       # Zustand stores
│   └── public/           # Static assets
├── docs/                 # Documentation
└── chroma_db/           # Vector database storage
```

## Configuration

### Environment Variables

Create a `.env` file in the project root (see `.env.example`):

```env
# Server
HOST=127.0.0.1
PORT=8181

# Database
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=wendy

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Models
DOC_BRAIN_MODEL=qwen3:32b-q4_K_M
FAST_BRAIN_MODEL=qwen2.5:14b
VISION_MODEL=qwen2.5-vl:7b
EMBEDDING_MODEL=nomic-embed-text

# RAG
CHROMA_DB_PATH=~/.wendy/chroma_db

# Voice
SHERPA_KWS_MODEL_PATH=
SHERPA_TTS_MODEL_PATH=
STT_MODEL_SIZE=base.en
AUDIO_DEVICE_INDEX=
```

### Prerequisites

- Python 3.12+
- Node.js 20+
- MongoDB
- Ollama with required models pulled
- (Optional) Sherpa-ONNX models for voice features

## Development

### Backend Setup

```bash
# Install Python dependencies
pip install -e .

# Run development server
python -m backend.main
# or
wendy-api
```

The API will be available at `http://127.0.0.1:8181`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Key Features

### 1. Document Processing & RAG

- Upload and process documents (PDF, DOCX, XLSX, PPTX, MD)
- Advanced PDF to Markdown conversion with layout awareness
- Extract text, tables, images, headers/footers from PDFs
- Automatic chunking and vector embedding
- RAG-based question answering over document collections
- ChromaDB for vector storage

**Related files:**
- `backend/services/converter.py` - Document conversion logic
- `backend/services/ingestion.py` - Document ingestion pipeline
- `backend/services/rag.py` - RAG implementation
- `backend/services/vector_db.py` - Vector database wrapper

### 2. Chat Interface

- Streaming chat responses
- Conversation memory management
- Multiple LLM model support via Ollama
- Semantic routing to appropriate handlers

**Related files:**
- `backend/api/chat.py` - Chat API endpoints
- `backend/services/llm.py` - LLM service
- `backend/services/memory.py` - Conversation memory
- `backend/services/router.py` - Semantic routing

### 3. Vision Capabilities

- Image analysis and description
- Visual question answering
- Integration with vision-capable LLMs

**Related files:**
- `backend/api/vision.py`
- `backend/services/vision.py`

### 4. Voice Interaction

- Wake word detection
- Speech-to-text (STT) using faster-whisper
- Text-to-speech (TTS) via sherpa-onnx
- Real-time audio streaming
- Event broadcasting for UI updates

**Related files:**
- `backend/api/voice.py`
- `backend/services/voice/` - Voice pipeline components
  - `orchestrator.py` - Coordinates voice pipeline
  - `wakeword.py` - Wake word detection
  - `stt.py` - Speech-to-text
  - `tts.py` - Text-to-speech
  - `audio.py` - Audio I/O handling
  - `event_broadcaster.py` - SSE events for UI

### 5. Project Management

- Organize documents and conversations by project
- Project-scoped RAG queries
- Document listing and metadata

**Related files:**
- `backend/api/projects.py`
- `backend/services/project.py`
- `backend/domain/project.py`

## API Endpoints

### Health Check
- `GET /health` - Service health and model availability

### Chat
- `POST /api/chat` - Send chat message (streaming)
- `GET /api/chat/history` - Get conversation history

### Documents
- `POST /api/documents/upload` - Upload document
- `GET /api/documents` - List documents
- `DELETE /api/documents/{doc_id}` - Delete document
- `POST /api/documents/query` - RAG query over documents

### Vision
- `POST /api/vision/analyze` - Analyze image

### Voice
- `POST /api/voice/start` - Start voice interaction
- `POST /api/voice/stop` - Stop voice interaction
- `GET /api/voice/events` - SSE event stream

### Projects
- `GET /api/projects` - List projects
- `POST /api/projects` - Create project
- `GET /api/projects/{project_id}` - Get project details
- `DELETE /api/projects/{project_id}` - Delete project

## Database Schema

### MongoDB Collections

**conversations**
- Stores chat conversation history
- Fields: messages, project_id, created_at, updated_at

**documents**
- Stores document metadata
- Fields: filename, content_type, file_path, project_id, chunks, uploaded_at

**projects**
- Stores project information
- Fields: name, description, created_at, updated_at

### ChromaDB Collections

- Per-project vector collections for RAG
- Stores document chunks with embeddings
- Metadata: document_id, chunk_index, source

## Code Conventions

### Python

- Use async/await for I/O operations
- Type hints required (Python 3.12+ syntax)
- Structured logging with structlog
- Pydantic models for validation
- Follow FastAPI best practices
- Dependency injection via FastAPI Depends

### TypeScript/React

- TypeScript strict mode
- Functional components with hooks
- Tailwind for styling
- shadcn/ui component patterns
- Server components where appropriate
- Client components for interactivity

## Testing

Currently no automated tests. When adding tests:
- Use pytest for Python backend
- Use Jest/React Testing Library for frontend
- Focus on service layer and API contracts

## Deployment Considerations

- Runs locally by default (no cloud dependencies)
- Requires local Ollama instance with models
- MongoDB can be local or remote
- ChromaDB stores data in filesystem
- Voice features require audio device access
- CORS configured for localhost:3000

## Common Tasks

### Adding a New LLM Model

1. Pull model via Ollama: `ollama pull model-name`
2. Update `.env` to reference the model
3. Model will be available via `/health` endpoint

### Adding a New Document Type

1. Add converter in `backend/services/converter.py`
2. Update `DocumentConverter.convert()` method
3. Add content type handling in `backend/api/documents.py`

### Customizing Voice Pipeline

1. Download appropriate Sherpa-ONNX models
2. Update `SHERPA_KWS_MODEL_PATH` and `SHERPA_TTS_MODEL_PATH` in `.env`
3. Adjust `STT_MODEL_SIZE` for Whisper model size
4. Configure `AUDIO_DEVICE_INDEX` if needed

## Known Issues

- PDF conversion may struggle with complex layouts
- Voice features require specific model downloads
- Large document uploads may timeout (consider chunking)
- MongoDB connection must be available at startup

## Future Enhancements

- Authentication and user management
- Multi-user support
- Cloud deployment options
- Enhanced document preprocessing
- Fine-tuning capabilities
- Plugin system for extensibility

## Git Workflow

This repository uses git worktrees. Current worktree: `loving-blackburn`

Main repository: `C:\Work\Projects\Wendy\Prjs`

## Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sherpa-ONNX Models](https://github.com/k2-fsa/sherpa-onnx)

## Contact & Support

For issues or questions, refer to project documentation in the `docs/` directory.
