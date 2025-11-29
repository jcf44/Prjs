"use client";

import React, { useEffect, useState } from 'react';
import { documentsApi, Document } from '@/lib/api';
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileText, Trash2, Upload, FileCode, FileImage, FileSpreadsheet, FileType, File, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { ExcelIcon, MarkdownIcon, PdfIcon, WordIcon } from "./DocIcons";

import { useStore } from "@/lib/store";

export function DocumentList() {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const { currentProject } = useStore();

    useEffect(() => {
        if (currentProject) {
            loadDocuments();
        } else {
            setDocuments([]);
        }
    }, [currentProject]);

    const loadDocuments = async () => {
        if (!currentProject) return;
        try {
            const response = await documentsApi.list(currentProject.project_id);
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
        if (!file || !currentProject) return;

        setIsUploading(true);
        try {
            await documentsApi.upload(file, currentProject.project_id);
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

    const getFileIcon = (filename: string) => {
        const ext = filename.split('.').pop()?.toLowerCase();
        const className = "h-5 w-5 shrink-0"; // Slightly larger for custom icons

        switch (ext) {
            case 'pdf':
                return <PdfIcon className={className} />;
            case 'doc':
            case 'docx':
                return <WordIcon className={className} />;
            case 'xls':
            case 'xlsx':
            case 'csv':
                return <ExcelIcon className={className} />;
            case 'jpg':
            case 'jpeg':
            case 'png':
            case 'gif':
            case 'webp':
                return <FileImage className={`${className} text-primary`} />;
            case 'py':
            case 'js':
            case 'ts':
            case 'tsx':
            case 'jsx':
            case 'html':
            case 'css':
            case 'json':
                return <FileCode className={`${className} text-primary`} />;
            case 'md':
                return <MarkdownIcon className={className} />;
            default:
                return <File className={`${className} text-primary`} />;
        }
    };

    return (
        <div className="flex flex-col h-full bg-card border rounded-lg overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between">
                <h3 className="font-semibold">Knowledge Base</h3>
                <div className="relative">
                    {!isUploading && (
                        <Input
                            type="file"
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            onChange={handleUpload}
                            disabled={isUploading}
                        />
                    )}
                    <Button size="sm" variant="outline" disabled={isUploading}>
                        {isUploading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Uploading...
                            </>
                        ) : (
                            <>
                                <Upload className="h-4 w-4 mr-2" />
                                Upload
                            </>
                        )}
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1 [&>[data-radix-scroll-area-viewport]]:!block">
                <div className="p-2 space-y-2">
                    {documents.length === 0 ? (
                        <div className="text-center text-muted-foreground p-8 text-sm">
                            No documents found.
                        </div>
                    ) : (
                        documents.map((doc) => (
                            <div key={doc.source_id} className="flex items-center justify-between p-3 rounded-md hover:bg-muted/50 border group">
                                <div className="flex items-center gap-3 overflow-hidden flex-1 w-0 mr-2">
                                    {getFileIcon(doc.filename)}
                                    <div className="truncate text-sm font-medium" title={doc.filename}>
                                        {doc.filename}
                                    </div>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
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
