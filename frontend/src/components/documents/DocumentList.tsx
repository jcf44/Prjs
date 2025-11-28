import React, { useEffect, useState } from 'react';
import { documentsApi, Document } from '@/lib/api';
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileText, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";

export function DocumentList() {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isUploading, setIsUploading] = useState(false);

    useEffect(() => {
        loadDocuments();
    }, []);

    const loadDocuments = async () => {
        try {
            const response = await documentsApi.list();
            setDocuments(response.data);
        } catch (error) {
            console.error(error);
            toast.error("Failed to load documents");
        }
    };

    const handleDelete = async (sourceId: string) => {
        try {
            await documentsApi.delete(sourceId);
            toast.success("Document deleted");
            loadDocuments();
        } catch (error) {
            console.error(error);
            toast.error("Failed to delete document");
        }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        try {
            await documentsApi.upload(file);
            toast.success("Document uploaded");
            loadDocuments();
        } catch (error) {
            console.error(error);
            toast.error("Failed to upload document");
        } finally {
            setIsUploading(false);
            // Reset input
            e.target.value = '';
        }
    };

    return (
        <div className="flex flex-col h-full bg-card border rounded-lg overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between">
                <h3 className="font-semibold">Knowledge Base</h3>
                <div className="relative">
                    <Input
                        type="file"
                        className="absolute inset-0 opacity-0 cursor-pointer"
                        onChange={handleUpload}
                        disabled={isUploading}
                    />
                    <Button size="sm" variant="outline" disabled={isUploading}>
                        <Upload className="h-4 w-4 mr-2" />
                        {isUploading ? 'Uploading...' : 'Upload'}
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                    {documents.length === 0 ? (
                        <div className="text-center text-muted-foreground p-8 text-sm">
                            No documents found.
                        </div>
                    ) : (
                        documents.map((doc) => (
                            <div key={doc.source_id} className="flex items-center justify-between p-3 rounded-md hover:bg-muted/50 border">
                                <div className="flex items-center gap-3 overflow-hidden">
                                    <FileText className="h-4 w-4 shrink-0 text-primary" />
                                    <div className="truncate text-sm font-medium" title={doc.filename}>
                                        {doc.filename}
                                    </div>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                    onClick={() => handleDelete(doc.source_id)}
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
