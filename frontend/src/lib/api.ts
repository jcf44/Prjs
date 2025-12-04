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

export interface Project {
  project_id: string;
  name: string;
  description?: string;
  user_profile: string;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  model?: string;
  user_id?: string;
  conversation_id?: string;
  project_id?: string;
}

export interface ChatResponse {
  answer: string;
  model_used: string;
  sources?: string[];
  conversation_id?: string;
}

export const chatApi = {
  sendMessage: async (message: string, model: string = 'auto', useRag: boolean = false, projectId: string = 'default', focusDocumentId: string | null = null): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat', {
      message,
      model: useRag ? 'rag' : model,
      project_id: projectId,
      focus_document_id: focusDocumentId,
    });
    return response.data;
  },

  // Streaming version using fetch (for future implementation)
  sendMessageStream: async function* (message: string, model: string = 'auto', useRag: boolean = false, projectId: string = 'default') {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        model: useRag ? 'rag' : model,
        project_id: projectId,
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
  listen: () => api.post('/voice/listen'), // Manual trigger for push-to-talk
  status: () => api.get<{
    is_running: boolean;
    listening_for_command: boolean;
    is_speaking: boolean;
    buffer_size: number;
    keywords_file: string;
  }>('/voice/status'),
  testTts: (text: string) => api.post(`/voice/test/tts?text=${encodeURIComponent(text)}`),
};

export interface HeaderFooterPreview {
  detected_patterns: string[];
  total_pages: number;
  pages_analyzed: number;
}

export const documentsApi = {
  list: (projectId: string = 'default') => api.get<Document[]>('/documents/', { params: { project_id: projectId } }),
  upload: async (file: File, projectId: string = 'default') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    return api.post('/documents/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: (sourceId: string) => api.delete(`/documents/${sourceId}`),
  query: (query: string, nResults: number = 5, projectId: string = 'default') =>
    api.post('/documents/query', { query, n_results: nResults, project_id: projectId }),
  previewHeaders: (sourceId: string) =>
    api.get<HeaderFooterPreview>(`/documents/${sourceId}/preview-headers`),
  convert: (sourceId: string, projectId: string = 'default', customHeadersFooters?: string[]) =>
    api.post(`/documents/${sourceId}/convert`, {
      project_id: projectId,
      custom_headers_footers: customHeadersFooters,
    }),
  download: async (sourceId: string, filename: string) => {
    const response = await api.get(`/documents/${sourceId}/download`, {
      responseType: 'blob',
    });
    // Create blob link to download
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export const projectsApi = {
  list: () => api.get<Project[]>('/projects/'),
  create: (name: string, description?: string) => {
    const formData = new FormData();
    formData.append('name', name);
    if (description) formData.append('description', description);
    return api.post<Project>('/projects/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  get: (projectId: string) => api.get<Project>(`/projects/${projectId}`),
  delete: (projectId: string) => api.delete(`/projects/${projectId}`),
};
