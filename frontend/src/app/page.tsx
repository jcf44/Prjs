"use client";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { DocumentList } from "@/components/documents/DocumentList";
import { VoiceControl } from "@/components/voice/VoiceControl";
import { useStore } from "@/lib/store";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

import { ProjectSelector } from "@/components/projects/ProjectSelector";

export default function Home() {
  const { useRag, setUseRag } = useStore();

  return (
    <main className="flex h-screen bg-background overflow-hidden">
      {/* Left Sidebar: Documents */}
      <aside className="w-80 border-r bg-muted/10 flex flex-col hidden md:flex">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent mb-4">
            Wendy AI
          </h1>
          <ProjectSelector />
        </div>
        <div className="flex-1 overflow-hidden p-4">
          <DocumentList />
        </div>
        <div className="p-4 border-t space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="rag-mode">RAG Mode</Label>
            <Switch
              id="rag-mode"
              checked={useRag}
              onCheckedChange={setUseRag}
            />
          </div>
        </div>
      </aside>

      {/* Main Content: Chat */}
      <section className="flex-1 flex flex-col min-w-0">
        <ChatInterface />
      </section>

      {/* Right Sidebar: Voice & Status (Optional/Collapsible) */}
      <aside className="w-72 border-l bg-muted/10 p-4 space-y-6 hidden lg:block">
        <VoiceControl />

        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          <h3 className="font-semibold text-foreground mb-2">System Status</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Backend</span>
              <span className="text-green-500">Connected</span>
            </div>
            <div className="flex justify-between">
              <span>Model</span>
              <span>Qwen 2.5</span>
            </div>
            <div className="flex justify-between">
              <span>Memory</span>
              <span>Active</span>
            </div>
          </div>
        </div>
      </aside>
    </main>
  );
}
