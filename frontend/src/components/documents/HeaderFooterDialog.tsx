"use client";

import React, { useEffect, useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, X, Plus, Check } from "lucide-react";
import { documentsApi } from '@/lib/api';
import { toast } from "sonner";

interface HeaderFooterDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    documentId: string;
    projectId: string;
    onConvert: (customPatterns: string[]) => void;
}

export function HeaderFooterDialog({
    open,
    onOpenChange,
    documentId,
    projectId,
    onConvert
}: HeaderFooterDialogProps) {
    const [loading, setLoading] = useState(false);
    const [detectedPatterns, setDetectedPatterns] = useState<string[]>([]);
    const [selectedPatterns, setSelectedPatterns] = useState<Set<string>>(new Set());
    const [customPatterns, setCustomPatterns] = useState<string[]>([]);
    const [newPattern, setNewPattern] = useState('');

    useEffect(() => {
        if (open) {
            loadHeadersFooters();
        } else {
            // Reset state when dialog closes
            setDetectedPatterns([]);
            setSelectedPatterns(new Set());
            setCustomPatterns([]);
            setNewPattern('');
        }
    }, [open, documentId]);

    const loadHeadersFooters = async () => {
        setLoading(true);
        try {
            const response = await documentsApi.previewHeaders(documentId);
            setDetectedPatterns(response.data.detected_patterns || []);
            // By default, select all detected patterns
            setSelectedPatterns(new Set(response.data.detected_patterns || []));
        } catch (error) {
            console.error(error);
            toast.error("Failed to load header/footer patterns");
        } finally {
            setLoading(false);
        }
    };

    const togglePattern = (pattern: string) => {
        setSelectedPatterns(prev => {
            const next = new Set(prev);
            if (next.has(pattern)) {
                next.delete(pattern);
            } else {
                next.add(pattern);
            }
            return next;
        });
    };

    const addCustomPattern = () => {
        if (newPattern.trim()) {
            setCustomPatterns(prev => [...prev, newPattern.trim()]);
            setSelectedPatterns(prev => new Set(prev).add(newPattern.trim()));
            setNewPattern('');
        }
    };

    const removeCustomPattern = (pattern: string) => {
        setCustomPatterns(prev => prev.filter(p => p !== pattern));
        setSelectedPatterns(prev => {
            const next = new Set(prev);
            next.delete(pattern);
            return next;
        });
    };

    const handleConvert = () => {
        const patternsToExclude = Array.from(selectedPatterns);
        onConvert(patternsToExclude);
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Configure Header/Footer Exclusions</DialogTitle>
                    <DialogDescription>
                        Select which patterns to exclude from the converted document.
                        Checked patterns will be removed from the final output.
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="flex-1 space-y-4 overflow-hidden flex flex-col">
                        {/* Detected Patterns */}
                        <div className="flex-1 overflow-hidden flex flex-col">
                            <h4 className="text-sm font-medium mb-2">
                                Detected Patterns ({detectedPatterns.length})
                            </h4>
                            <ScrollArea className="flex-1 border rounded-md">
                                <div className="p-2 space-y-1">
                                    {detectedPatterns.length === 0 ? (
                                        <div className="text-center text-muted-foreground text-sm py-4">
                                            No patterns detected automatically
                                        </div>
                                    ) : (
                                        detectedPatterns.map((pattern) => (
                                            <div
                                                key={pattern}
                                                className={`flex items-start gap-2 p-2 rounded cursor-pointer hover:bg-muted/50 transition-colors ${
                                                    selectedPatterns.has(pattern) ? 'bg-primary/10' : ''
                                                }`}
                                                onClick={() => togglePattern(pattern)}
                                            >
                                                <div className={`mt-0.5 h-4 w-4 border rounded flex items-center justify-center shrink-0 ${
                                                    selectedPatterns.has(pattern)
                                                        ? 'bg-primary border-primary'
                                                        : 'border-input'
                                                }`}>
                                                    {selectedPatterns.has(pattern) && (
                                                        <Check className="h-3 w-3 text-primary-foreground" />
                                                    )}
                                                </div>
                                                <span className="text-sm flex-1 break-all">{pattern}</span>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </ScrollArea>
                        </div>

                        {/* Custom Patterns */}
                        <div className="space-y-2">
                            <h4 className="text-sm font-medium">
                                Custom Patterns
                            </h4>
                            <div className="flex gap-2">
                                <Input
                                    placeholder="Add custom pattern to exclude..."
                                    value={newPattern}
                                    onChange={(e) => setNewPattern(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault();
                                            addCustomPattern();
                                        }
                                    }}
                                />
                                <Button
                                    type="button"
                                    size="icon"
                                    variant="outline"
                                    onClick={addCustomPattern}
                                    disabled={!newPattern.trim()}
                                >
                                    <Plus className="h-4 w-4" />
                                </Button>
                            </div>
                            {customPatterns.length > 0 && (
                                <div className="space-y-1 max-h-32 overflow-y-auto border rounded-md p-2">
                                    {customPatterns.map((pattern) => (
                                        <div
                                            key={pattern}
                                            className="flex items-center justify-between gap-2 p-2 rounded bg-primary/10"
                                        >
                                            <span className="text-sm flex-1 break-all">{pattern}</span>
                                            <Button
                                                type="button"
                                                size="icon"
                                                variant="ghost"
                                                className="h-6 w-6 shrink-0"
                                                onClick={() => removeCustomPattern(pattern)}
                                            >
                                                <X className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleConvert} disabled={loading}>
                        Convert Document
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
