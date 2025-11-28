import React, { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea"; // Need to install textarea or use Input
import { Send, Paperclip, Mic } from "lucide-react";
import { useStore } from '@/lib/store';

// We might need Textarea component from shadcn if we want auto-resize
// For now using standard textarea with shadcn styling classes or Input
import { Input } from "@/components/ui/input";

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
    const [input, setInput] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const { isVoiceActive, setIsVoiceActive } = useStore();

    const handleSend = () => {
        if (input.trim()) {
            onSend(input);
            setInput("");
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="flex items-end gap-2 p-4 border-t bg-background">
            <Button variant="ghost" size="icon" className="shrink-0">
                <Paperclip className="h-5 w-5" />
            </Button>

            <div className="relative flex-1">
                <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Message Wendy..."
                    disabled={disabled}
                    className="pr-12"
                />
            </div>

            <Button
                onClick={handleSend}
                disabled={!input.trim() || disabled}
                size="icon"
            >
                <Send className="h-5 w-5" />
            </Button>

            <Button
                variant={isVoiceActive ? "destructive" : "secondary"}
                size="icon"
                onClick={() => setIsVoiceActive(!isVoiceActive)}
            >
                <Mic className="h-5 w-5" />
            </Button>
        </div>
    );
}
