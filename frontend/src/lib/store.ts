import { create } from "zustand";

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  avatar?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  project_id: string;
  created_at: string;
  updated_at: string;
}

interface AppState {
  user: User | null;
  currentProject: Project | null;
  conversations: Conversation[];
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;

  setUser: (user: User | null) => void;
  setCurrentProject: (project: Project | null) => void;
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  removeConversation: (id: string) => void;
  setSidebarOpen: (open: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  currentProject: null,
  conversations: [],
  sidebarOpen: true,
  sidebarCollapsed: false,

  setUser: (user) => set({ user }),
  setCurrentProject: (project) => set({ currentProject: project }),
  setConversations: (conversations) => set({ conversations }),
  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),
  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
    })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
