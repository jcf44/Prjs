import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
}

export interface Document {
  source_id: string;
  filename: string;
  source: string;
  created_at?: string;
}

export const chatApi = {
  sendMessage: async (message: string, model: string = 'auto', useRag: boolean = false) => {
    const response = await api.post('/chat', {
      message,
      model: useRag ? 'rag' : model,
      stream: true, // We will handle streaming separately if needed, or use fetch for stream
    });
    return response.data;
  },
};

export const voiceApi = {
  start: async () => api.post('/voice/start'),
  stop: async () => api.post('/voice/stop'),
  status: async () => api.get('/voice/status'),
};

export const documentsApi = {
  list: async () => api.get<Document[]>('/documents/'),
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/documents/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: async (sourceId: string) => api.delete(`/documents/${sourceId}`),
};
