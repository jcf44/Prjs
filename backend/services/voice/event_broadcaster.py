"""
Voice Event Broadcaster for SSE (Server-Sent Events)
Allows broadcasting voice conversation events to connected clients in real-time
"""
import asyncio
import json
import structlog
from typing import Dict, Any
from datetime import datetime

logger = structlog.get_logger()


class VoiceEventBroadcaster:
    """Broadcasts voice events to SSE subscribers"""
    
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to voice events. Returns a queue that will receive events."""
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.append(queue)
        logger.info("New SSE subscriber", total_subscribers=len(self._subscribers))
        return queue
    
    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from voice events"""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
        logger.info("SSE subscriber removed", total_subscribers=len(self._subscribers))
    
    async def emit(self, event_type: str, data: Dict[str, Any]):
        """
        Emit an event to all subscribers
        
        Args:
            event_type: Type of event (e.g., 'transcription', 'response')
            data: Event data (will be JSON serialized)
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("Broadcasting voice event", event_type=event_type, subscribers=len(self._subscribers))
        
        # Send to all subscribers (non-blocking)
        async with self._lock:
            dead_queues = []
            for queue in self._subscribers:
                try:
                    # Non-blocking put, drop if queue is full
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue full, dropping event")
                    dead_queues.append(queue)
                except Exception as e:
                    logger.error("Error sending event to subscriber", error=str(e))
                    dead_queues.append(queue)
            
            # Clean up dead queues
            for queue in dead_queues:
                self._subscribers.remove(queue)
    
    def emit_sync(self, event_type: str, data: Dict[str, Any]):
        """
        Synchronous wrapper for emit - schedules the coroutine from any thread
        Use this from non-async code (like the voice orchestrator thread)
        """
        global _main_event_loop
        
        try:
            if _main_event_loop is None:
                logger.warning("Main event loop not set yet, cannot emit event", event_type=event_type)
                return
            
            # Schedule the coroutine on the main event loop from this worker thread
            future = asyncio.run_coroutine_threadsafe(self.emit(event_type, data), _main_event_loop)
            logger.debug("Scheduled voice event emission", event_type=event_type)
        except Exception as e:
            logger.error("Failed to emit event sync", error=str(e), exc_info=True)


# Global reference to the main event loop (set when SSE endpoint is accessed)
_main_event_loop = None
# Singleton instance
_broadcaster: VoiceEventBroadcaster | None = None


def set_main_loop():
    """Set the global main event loop reference. Call this from an async endpoint."""
    global _main_event_loop
    if _main_event_loop is None:
        try:
            _main_event_loop = asyncio.get_running_loop()
            logger.info("Main event loop reference stored for SSE")
        except RuntimeError:
            logger.warning("Could not get running loop")


def get_broadcaster() -> VoiceEventBroadcaster:
    """Get the singleton voice event broadcaster"""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = VoiceEventBroadcaster()
    return _broadcaster
