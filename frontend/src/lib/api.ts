import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8181/v1';

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
  chunk_count?: number;
  created_at?: string;
}

export interface ChatRequest {
  message: string;
  model?: string;
  user_id?: string;
  conversation_id?: string;
}

export interface ChatResponse {
  answer: string;
  model_used: string;
  sources?: string[];
  conversation_id?: string;
}

export const chatApi = {
  sendMessage: async (message: string, model: string = 'auto', useRag: boolean = false): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat', {
      message,
      model: useRag ? 'rag' : model,
    });
    return response.data;
  },

  // Streaming version using fetch (for future implementation)
  sendMessageStream: async function* (message: string, model: string = 'auto', useRag: boolean = false) {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        model: useRag ? 'rag' : model,
        stream: true,
      }),
    });

    if (!response.ok) throw new Error('Chat request failed');
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') return;
          try {
            yield JSON.parse(data);
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  },
};

export const voiceApi = {
  start: () => api.post('/voice/start'),
  stop: () => api.post('/voice/stop'),
  status: () => api.get<{
    is_running: boolean;
    listening_for_command: boolean;
    buffer_size: number;
    keywords_file: string;
  }>('/voice/status'),
  testTts: (text: string) => api.post(`/voice/test/tts?text=${encodeURIComponent(text)}`),
};

export const documentsApi = {
  list: () => api.get<Document[]>('/documents/'),
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/documents/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: (sourceId: string) => api.delete(`/documents/${sourceId}`),
  query: (query: string, nResults: number = 5) => 
    api.post('/documents/query', { query, n_results: nResults }),
};
