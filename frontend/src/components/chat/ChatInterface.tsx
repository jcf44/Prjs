import React from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useStore } from '@/lib/store';
import { chatApi } from '@/lib/api';
import { toast } from "sonner";

export function ChatInterface() {
    const {
        addMessage,
        setIsLoading,
        selectedModel,
        useRag,
        messages
    } = useStore();

    const handleSend = async (text: string) => {
        // Add user message
        addMessage({ role: 'user', content: text });
        setIsLoading(true);

        try {
            // TODO: Implement streaming properly. For now, using standard request.
            // If backend supports streaming, we should use fetch + ReadableStream here.

            // Temporary: Mock streaming or just wait for response
            const response = await chatApi.sendMessage(text, selectedModel, useRag);

            // Add assistant message
            addMessage({
                role: 'assistant',
                content: response.answer || response.message || "No response",
                sources: response.sources
            });

        } catch (error) {
            console.error(error);
            toast.error("Failed to send message");
            addMessage({ role: 'assistant', content: "Sorry, I encountered an error." });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full w-full max-w-3xl mx-auto border-x bg-background shadow-sm">
            <div className="flex items-center justify-between p-4 border-b">
                <h2 className="font-semibold">Wendy Chat</h2>
                <div className="text-xs text-muted-foreground">
                    Model: {selectedModel} | RAG: {useRag ? 'On' : 'Off'}
                </div>
            </div>

            <MessageList />

            <ChatInput onSend={handleSend} disabled={false} />
        </div>
    );
}
