import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { ChatMessage } from '@/lib/api';
import { Bot, User } from 'lucide-react';

interface MessageItemProps {
    message: ChatMessage;
}

export function MessageItem({ message }: MessageItemProps) {
    const isUser = message.role === 'user';

    return (
        <div className={cn(
            "flex gap-3 p-4",
            isUser ? "flex-row-reverse bg-muted/50" : "bg-background"
        )}>
            <Avatar className="h-8 w-8">
                <AvatarFallback className={isUser ? "bg-primary text-primary-foreground" : "bg-secondary"}>
                    {isUser ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
                </AvatarFallback>
            </Avatar>

            <div className={cn(
                "flex-1 space-y-2 overflow-hidden",
                isUser ? "text-right" : "text-left"
            )}>
                <div className="prose dark:prose-invert max-w-none break-words">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.sources && message.sources.length > 0 && (
                    <div className="text-xs text-muted-foreground mt-2">
                        <p className="font-semibold">Sources:</p>
                        <ul className="list-disc list-inside">
                            {message.sources.map((source, i) => (
                                <li key={i}>{source}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
}
