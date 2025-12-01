import React from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useStore } from '@/lib/store';
import { chatApi } from '@/lib/api';
import { toast } from "sonner";
import { X } from "lucide-react";

export function ChatInterface() {
    const {
        addMessage,
        setIsLoading,
        isLoading,
        selectedModel,
        useRag,
        messages,
        currentProject,
        setMessages,
        focusedDocumentId,
        setFocusedDocumentId,
        documents
    } = useStore();

    const focusedDocumentName = React.useMemo(() => {
        return documents.find(d => d.source_id === focusedDocumentId)?.filename || "Unknown Document";
    }, [documents, focusedDocumentId]);

    React.useEffect(() => {
        // Clear messages when project changes
        setMessages([]);
        // Ideally we would fetch recent conversation here
    }, [currentProject, setMessages]);

    const handleSend = async (text: string) => {
        if (!currentProject) {
            toast.error("Please select a project first");
            return;
        }

        // Add user message
        addMessage({ role: 'user', content: text });
        setIsLoading(true);

        try {
            // TODO: Implement streaming properly. For now, using standard request.
            // If backend supports streaming, we should use fetch + ReadableStream here.

            // Temporary: Mock streaming or just wait for response
            const response = await chatApi.sendMessage(text, selectedModel, useRag, currentProject.project_id, focusedDocumentId);

            // Add assistant message
            addMessage({
                role: 'assistant',
                content: response.answer || "No response",
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
        <div className="flex flex-col h-full w-full max-w-3xl mx-auto border-x bg-background shadow-sm overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
                <h2 className="font-semibold">Wendy Chat</h2>
                <div className="text-xs text-muted-foreground">
                    Model: {selectedModel} | RAG: {useRag ? 'On' : 'Off'}
                </div>
            </div>

            {focusedDocumentId && (
                <div className="bg-primary/10 border-b border-primary/20 p-2 px-4 flex items-center justify-between text-sm text-primary animate-in slide-in-from-top-2 fade-in duration-200">
                    <span className="font-medium flex items-center gap-2">
                        <span className="text-lg">👁️</span>
                        Focusing on: <span className="font-bold">{focusedDocumentName}</span> (Full Context)
                    </span>
                    <button
                        onClick={() => setFocusedDocumentId(null)}
                        className="hover:bg-primary/20 p-1 rounded-full transition-colors"
                        title="Clear Focus"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
            )}

            <MessageList />

            <ChatInput onSend={handleSend} disabled={isLoading} />
        </div>
    );
}
