from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import structlog

from backend.services.voice import get_orchestrator, VoiceOrchestrator
from backend.services.voice.event_broadcaster import get_broadcaster

router = APIRouter(prefix="/v1/voice", tags=["voice"])
logger = structlog.get_logger()

# Track the background task
_voice_task: Optional[asyncio.Task] = None


class VoiceStatusResponse(BaseModel):
    is_running: bool
    listening_for_command: bool
    is_speaking: bool
    buffer_size: int
    keywords_file: Optional[str] = None


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    """Get the current status of the voice pipeline"""
    try:
        orchestrator = get_orchestrator()
        status = orchestrator.get_status()
        return VoiceStatusResponse(**status)
    except Exception as e:
        logger.error("Failed to get voice status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_voice():
    """Start the voice pipeline (wake word listening)"""
    global _voice_task
    
    try:
        orchestrator = get_orchestrator()
        
        if orchestrator.is_running:
            return {"status": "already_running", "message": "Voice pipeline is already running"}
        
        # Start the orchestrator in background
        _voice_task = asyncio.create_task(orchestrator.start())
        
        logger.info("Voice pipeline started")
        return {"status": "started", "message": "Voice pipeline started. Say 'Hey Wendy' to activate."}
        
    except Exception as e:
        logger.error("Failed to start voice pipeline", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_voice():
    """Stop the voice pipeline"""
    global _voice_task
    
    try:
        orchestrator = get_orchestrator()
        
        if not orchestrator.is_running:
            return {"status": "not_running", "message": "Voice pipeline is not running"}
        
        orchestrator.stop()
        
        if _voice_task:
            _voice_task.cancel()
            try:
                await _voice_task
            except asyncio.CancelledError:
                pass
            _voice_task = None
        
        logger.info("Voice pipeline stopped")
        return {"status": "stopped", "message": "Voice pipeline stopped"}
        
    except Exception as e:
        logger.error("Failed to stop voice pipeline", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/listen")
async def manual_listen():
    """Manually trigger listening mode (push-to-talk)"""
    try:
        orchestrator = get_orchestrator()
        
        if not orchestrator.is_running:
            raise HTTPException(status_code=400, detail="Voice mode not active. Start voice mode first.")
        
        if orchestrator.listening_for_command:
            return {"status": "already_listening", "message": "Already in listening mode"}
        
        if orchestrator.is_speaking or orchestrator.is_processing:
            return {"status": "busy", "message": "System is currently speaking or processing"}
        
        # Directly enter listening mode
        orchestrator._enter_listening_mode()
        
        logger.info("Manual listening triggered (push-to-talk)")
        return {"status": "listening", "message": "Listening for command..."}
        
    except Exception as e:
        logger.error("Failed to start manual listening", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/tts")
async def test_tts(text: str = "Hello, I am Wendy, your local AI assistant."):
    """Test TTS by synthesizing and playing text"""
    try:
        from backend.services.voice import get_tts_service, get_audio_service
        
        tts = get_tts_service()
        audio = get_audio_service()
        
        logger.info("Testing TTS", text=text)
        audio_bytes = tts.synthesize(text)
        audio.play_audio(audio_bytes)
        
        return {"status": "success", "message": f"Played: {text}", "audio_size": len(audio_bytes)}
        
    except Exception as e:
        logger.error("TTS test failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/wakeword")
async def test_wakeword():
    """Get info about the wake word configuration"""
    try:
        from backend.services.voice import get_wakeword_service
        import os
        
        ww = get_wakeword_service()
        
        # Read keywords file content
        keywords_content = ""
        if os.path.exists(ww.keywords_file):
            with open(ww.keywords_file, "r", encoding="utf-8") as f:
                keywords_content = f.read().strip()
        
        return {
            "status": "success",
            "keywords_file": ww.keywords_file,
            "keywords_content": keywords_content,
            "message": "Say the configured keyword to test detection"
        }
        
    except Exception as e:
        logger.error("Wake word test failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def voice_events():
    """
    SSE endpoint for streaming voice conversation events in real-time
    Clients receive events when voice commands are transcribed and responses generated
    """
    from backend.services.voice.event_broadcaster import set_main_loop
    
    # Store the main event loop reference for emit_sync to use
    set_main_loop()
    
    broadcaster = get_broadcaster()
    
    async def event_generator():
        """Generate SSE formatted events"""
        queue = await broadcaster.subscribe()
        try:
            logger.info("SSE client connected to voice events")
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Voice events stream connected'})}\n\n"
            
            while True:
                # Wait for events from the broadcaster
                event = await queue.get()
                
                # Format as SSE: data: {json}\n\n
                event_json = json.dumps(event)
                yield f"data: {event_json}\n\n"
                
        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
            await broadcaster.unsubscribe(queue)
            raise
        except Exception as e:
            logger.error("Error in SSE event stream", error=str(e))
            await broadcaster.unsubscribe(queue)
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
