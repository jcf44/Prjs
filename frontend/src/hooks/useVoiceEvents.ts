import { useEffect, useRef } from 'react';
import { useStore } from '@/lib/store';
import { toast } from 'sonner';

// Use same API base URL as the rest of the app (port 8181)
const API_BASE_URL = (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_URL) || 'http://localhost:8181';

/**
 * Hook to connect to voice events SSE stream
 * Automatically adds voice conversation messages to the chat
 */
export function useVoiceEvents(isActive: boolean) {
    const eventSourceRef = useRef<EventSource | null>(null);
    const { addMessage } = useStore();

    useEffect(() => {
        if (!isActive) {
            // Cleanup when voice mode is inactive
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
            }
            return;
        }

        // Connect to SSE endpoint
        const eventSource = new EventSource(`${API_BASE_URL}/v1/voice/events`);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
            console.log('Connected to voice events stream');
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // Handle different event types
                if (data.type === 'connected') {
                    console.log('Voice events stream ready');
                } else if (data.type === 'transcription') {
                    // User's spoken message
                    addMessage({
                        role: data.data.role,
                        content: data.data.content
                    });
                } else if (data.type === 'response') {
                    // AI's response
                    addMessage({
                        role: data.data.role,
                        content: data.data.content
                    });
                }
            } catch (error) {
                console.error('Error parsing voice event:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('Voice events stream error:', error);

            // Only log errors, don't show toast to user
            // EventSource automatically reconnects on errors
            // Normal closure happens when voice mode is stopped
            if (eventSource.readyState === EventSource.CONNECTING) {
                console.log('Voice events reconnecting...');
            } else if (eventSource.readyState === EventSource.CLOSED) {
                console.log('Voice events stream closed');
            }
        };

        // Cleanup on unmount or when voice mode stops
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
                console.log('Voice events SSE connection closed');
            }
        };
    }, [isActive, addMessage]);
}
