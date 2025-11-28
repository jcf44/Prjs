import React, { useEffect, useRef, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Mic, MicOff, Activity } from "lucide-react";
import { useStore } from '@/lib/store';
import { voiceApi } from '@/lib/api';
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function VoiceControl() {
    const { isVoiceActive, setIsVoiceActive, voiceStatus, setVoiceStatus } = useStore();
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    const startVoice = useCallback(async () => {
        try {
            await voiceApi.start();
            toast.success("Voice mode activated");
        } catch (error) {
            console.error(error);
            toast.error("Failed to start voice mode");
            setIsVoiceActive(false);
        }
    }, [setIsVoiceActive]);

    const stopVoice = useCallback(async () => {
        try {
            await voiceApi.stop();
        } catch (error) {
            console.error(error);
        }
    }, []);

    const checkStatus = useCallback(async () => {
        try {
            const response = await voiceApi.status();
            const { listening_for_command, is_running } = response.data;
            if (!is_running) {
                setVoiceStatus('idle');
            } else if (listening_for_command) {
                setVoiceStatus('listening');
            } else {
                setVoiceStatus('waiting'); // Waiting for wake word or processing
            }
        } catch (error) {
            console.error(error);
        }
    }, [setVoiceStatus]);

    // Poll status when active
    useEffect(() => {
        if (isVoiceActive) {
            startVoice();
            intervalRef.current = setInterval(checkStatus, 1000);
        } else {
            stopVoice();
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            setVoiceStatus('idle');
        }

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [isVoiceActive, startVoice, stopVoice, checkStatus, setVoiceStatus]);

    return (
        <div className="flex flex-col items-center gap-4 p-6 bg-card rounded-lg border shadow-sm">
            <div className="relative">
                {isVoiceActive && (
                    <span className="absolute -inset-1 rounded-full bg-primary/20 animate-ping"></span>
                )}
                <Button
                    variant={isVoiceActive ? "destructive" : "default"}
                    size="lg"
                    className={cn("h-16 w-16 rounded-full", isVoiceActive && "animate-pulse")}
                    onClick={() => setIsVoiceActive(!isVoiceActive)}
                >
                    {isVoiceActive ? <MicOff className="h-8 w-8" /> : <Mic className="h-8 w-8" />}
                </Button>
            </div>

            <div className="text-center space-y-1">
                <h3 className="font-semibold">Voice Mode</h3>
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground h-6">
                    {isVoiceActive ? (
                        <>
                            <Activity className="h-4 w-4 animate-bounce" />
                            <span>
                                {voiceStatus === 'listening' ? 'Listening...' :
                                    voiceStatus === 'waiting' ? 'Say "Hey Wendy"' :
                                        'Processing...'}
                            </span>
                        </>
                    ) : (
                        <span>Click to start</span>
                    )}
                </div>
            </div>
        </div>
    );
}
