const TOKEN_KEY = 'rag_qa_token';

class ApiClient {
  private baseURL: string;

  constructor() {
    this.baseURL = '/api';
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }

  setToken(token: string) {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, token);
  }

  removeToken() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.removeToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  auth = {
    login: (username: string, password: string) =>
      this.request<{ access_token: string; token_type: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),

    register: (data: { username: string; email: string; password: string }) =>
      this.request<{ id: string; username: string }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    getMe: () =>
      this.request<{ id: string; username: string; email: string; role: string }>('/auth/me'),
  };

  projects = {
    list: (params?: { skip?: number; limit?: number }) => {
      const query = new URLSearchParams();
      if (params?.skip) query.set('skip', String(params.skip));
      if (params?.limit) query.set('limit', String(params.limit));
      return this.request<{ items: any[]; total: number }>(`/projects?${query.toString()}`);
    },

    create: (data: { name: string; description?: string }) =>
      this.request<any>('/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    get: (id: string) =>
      this.request<any>(`/projects/${id}`),

    update: (id: string, data: { name?: string; description?: string }) =>
      this.request<any>(`/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (id: string) =>
      this.request<void>(`/projects/${id}`, { method: 'DELETE' }),

    addMember: (projectId: string, data: { user_id: string; role: string }) =>
      this.request<any>(`/projects/${projectId}/members`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    listMembers: (projectId: string) =>
      this.request<any[]>(`/projects/${projectId}/members`),

    removeMember: (projectId: string, userId: string) =>
      this.request<void>(`/projects/${projectId}/members/${userId}`, {
        method: 'DELETE',
      }),
  };

  datasources = {
    list: (projectId: string) =>
      this.request<any[]>(`/projects/${projectId}/datasources`),

    create: (projectId: string, data: any) =>
      this.request<any>(`/projects/${projectId}/datasources`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (projectId: string, datasourceId: string, data: any) =>
      this.request<any>(`/projects/${projectId}/datasources/${datasourceId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (projectId: string, datasourceId: string) =>
      this.request<void>(`/projects/${projectId}/datasources/${datasourceId}`, {
        method: 'DELETE',
      }),

    testConnection: (projectId: string, datasourceId: string) =>
      this.request<{ success: boolean; message: string }>(
        `/projects/${projectId}/datasources/${datasourceId}/test`,
        { method: 'POST' }
      ),

    triggerSync: (projectId: string, datasourceId: string) =>
      this.request<{ task_id: string }>(
        `/projects/${projectId}/datasources/${datasourceId}/sync`,
        { method: 'POST' }
      ),
  };

  chat = {
    sendMessage: (data: {
      project_id: string;
      conversation_id?: string;
      question: string;
    }) =>
      this.request<{
        answer: string;
        conversation_id: string;
        sources: any[];
      }>('/chat/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    sendMessageStream: (data: {
      project_id: string;
      conversation_id?: string;
      question: string;
    }) => {
      const token = this.getToken();
      const params = new URLSearchParams({
        project_id: data.project_id,
        question: data.question,
      });
      if (data.conversation_id) {
        params.set('conversation_id', data.conversation_id);
      }
      const url = `${this.baseURL}/chat/stream?${params.toString()}`;
      return new EventSource(url);
    },

    listConversations: (projectId: string) =>
      this.request<any[]>(`/chat/conversations?project_id=${projectId}`),

    getConversation: (conversationId: string) =>
      this.request<any>(`/chat/conversations/${conversationId}`),

    addFeedback: (messageId: string, data: { rating: 'positive' | 'negative'; comment?: string }) =>
      this.request<any>(`/chat/messages/${messageId}/feedback`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  };

  knowledge = {
    listDocuments: (projectId: string, params?: { skip?: number; limit?: number }) => {
      const query = new URLSearchParams({ project_id: projectId });
      if (params?.skip) query.set('skip', String(params.skip));
      if (params?.limit) query.set('limit', String(params.limit));
      return this.request<{ items: any[]; total: number }>(`/knowledge/documents?${query.toString()}`);
    },

    getDocument: (documentId: string) =>
      this.request<any>(`/knowledge/documents/${documentId}`),

    deleteDocument: (documentId: string) =>
      this.request<void>(`/knowledge/documents/${documentId}`, { method: 'DELETE' }),

    uploadDocument: (projectId: string, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const token = this.getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      return fetch(`${this.baseURL}/knowledge/documents?project_id=${projectId}`, {
        method: 'POST',
        headers,
        body: formData,
      }).then((res) => {
        if (!res.ok) throw new Error('Upload failed');
        return res.json();
      });
    },
  };

  admin = {
    getStats: () =>
      this.request<{
        total_documents: number;
        total_conversations: number;
        total_questions: number;
        accuracy_rate: number;
      }>('/admin/stats'),

    getSyncTasks: (params?: { skip?: number; limit?: number; status?: string }) => {
      const query = new URLSearchParams();
      if (params?.skip) query.set('skip', String(params.skip));
      if (params?.limit) query.set('limit', String(params.limit));
      if (params?.status) query.set('status', params.status);
      return this.request<{ items: any[]; total: number }>(`/admin/sync-tasks?${query.toString()}`);
    },

    getBadCases: (params?: { skip?: number; limit?: number }) => {
      const query = new URLSearchParams();
      if (params?.skip) query.set('skip', String(params.skip));
      if (params?.limit) query.set('limit', String(params.limit));
      return this.request<{ items: any[]; total: number }>(`/admin/bad-cases?${query.toString()}`);
    },
  };
}

export const apiClient = new ApiClient();
