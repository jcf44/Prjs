import { create } from 'zustand';
import { ChatMessage } from './api';

interface AppState {
    // Chat
    messages: ChatMessage[];
    addMessage: (message: ChatMessage) => void;
    setMessages: (messages: ChatMessage[]) => void;
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;

    // Settings
    selectedModel: string;
    setSelectedModel: (model: string) => void;
    useRag: boolean;
    setUseRag: (useRag: boolean) => void;

    // Voice
    isVoiceActive: boolean;
    setIsVoiceActive: (active: boolean) => void;
    voiceStatus: string;
    setVoiceStatus: (status: string) => void;
}

export const useStore = create<AppState>((set) => ({
    // Chat
    messages: [],
    addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
    setMessages: (msgs) => set({ messages: msgs }),
    isLoading: false,
    setIsLoading: (loading) => set({ isLoading: loading }),

    // Settings
    selectedModel: 'auto',
    setSelectedModel: (model) => set({ selectedModel: model }),
    useRag: false,
    setUseRag: (useRag) => set({ useRag }),

    // Voice
    isVoiceActive: false,
    setIsVoiceActive: (active) => set({ isVoiceActive: active }),
    voiceStatus: 'idle',
    setVoiceStatus: (status) => set({ voiceStatus: status }),
}));
