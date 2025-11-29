import { create } from 'zustand';
import { ChatMessage, Project, projectsApi } from './api';

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

    // Projects
    projects: Project[];
    currentProject: Project | null;
    fetchProjects: () => Promise<void>;
    setCurrentProject: (project: Project) => void;
    createProject: (name: string, description?: string) => Promise<void>;
    deleteProject: (projectId: string) => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
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

    // Projects
    projects: [],
    currentProject: null,
    fetchProjects: async () => {
        try {
            const response = await projectsApi.list();
            const projects = response.data;
            set({ projects });

            // Set default project if none selected
            if (!get().currentProject && projects.length > 0) {
                set({ currentProject: projects[0] });
            }
        } catch (error) {
            console.error('Failed to fetch projects:', error);
        }
    },
    setCurrentProject: (project) => set({ currentProject: project }),
    createProject: async (name, description) => {
        try {
            await projectsApi.create(name, description);
            await get().fetchProjects();
        } catch (error) {
            console.error('Failed to create project:', error);
            throw error;
        }
    },
    deleteProject: async (projectId) => {
        try {
            await projectsApi.delete(projectId);
            await get().fetchProjects();
            // If deleted current project, switch to another
            const { currentProject, projects } = get();
            if (currentProject?.project_id === projectId) {
                set({ currentProject: projects.length > 0 ? projects[0] : null });
            }
        } catch (error) {
            console.error('Failed to delete project:', error);
            throw error;
        }
    },
}));
