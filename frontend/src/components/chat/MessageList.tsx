import React, { useEffect, useRef } from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageItem } from './MessageItem';
import { useStore } from '@/lib/store';

export function MessageList() {
    const { messages, isLoading } = useStore();
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }
    }, [messages, isLoading]);

    return (
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4 pb-4">
                {messages.map((msg, index) => (
                    <MessageItem key={index} message={msg} />
                ))}
                {isLoading && (
                    <div className="flex gap-3 p-4">
                        <div className="animate-pulse flex space-x-4">
                            <div className="rounded-full bg-slate-200 h-8 w-8"></div>
                            <div className="flex-1 space-y-2 py-1">
                                <div className="h-2 bg-slate-200 rounded"></div>
                                <div className="h-2 bg-slate-200 rounded w-5/6"></div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </ScrollArea>
    );
}
