'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus,
  MessageSquare,
  Settings,
  LogOut,
  ChevronDown,
  Loader2,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatInput } from '@/components/ChatInput';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  feedback?: 'positive' | 'negative' | null;
}

interface Conversation {
  id: string;
  title: string;
  project_id: string;
  created_at: string;
  updated_at: string;
}

interface Project {
  id: string;
  name: string;
  description?: string;
}

export default function ChatPage() {
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [user, setUser] = useState<any>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('rag_qa_token') : null;
    if (!token) {
      router.push('/login');
      return;
    }
    loadUser();
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadConversations();
    }
  }, [selectedProject]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadUser = async () => {
    try {
      const userData = await apiClient.auth.getMe();
      setUser(userData);
    } catch {
      router.push('/login');
    }
  };

  const loadProjects = async () => {
    try {
      const res = await apiClient.projects.list();
      setProjects(res.items || []);
      if (res.items?.length > 0 && !selectedProject) {
        setSelectedProject(res.items[0].id);
      }
    } catch {}
  };

  const loadConversations = useCallback(async () => {
    if (!selectedProject) return;
    try {
      const convs = await apiClient.chat.listConversations(selectedProject);
      setConversations(convs || []);
    } catch {}
  }, [selectedProject]);

  const loadConversationMessages = async (conversationId: string) => {
    try {
      setLoading(true);
      const conv = await apiClient.chat.getConversation(conversationId);
      setCurrentConversation(conversationId);
      setMessages(
        (conv.messages || []).map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.sources || [],
          feedback: m.feedback || null,
        }))
      );
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    setCurrentConversation('');
    setMessages([]);
    setStreamingContent('');
  };

  const handleSend = async (question: string) => {
    if (!selectedProject) return;

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: question,
    };
    setMessages((prev) => [...prev, userMessage]);
    setSending(true);
    setStreamingContent('');

    try {
      const eventSource = apiClient.chat.sendMessageStream({
        project_id: selectedProject,
        conversation_id: currentConversation || undefined,
        question,
      });

      let fullContent = '';
      let convId = currentConversation;
      let sources: any[] = [];

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'conversation_id') {
            convId = data.conversation_id;
            setCurrentConversation(convId);
          } else if (data.type === 'content') {
            fullContent += data.content;
            setStreamingContent(fullContent);
          } else if (data.type === 'sources') {
            sources = data.sources || [];
          } else if (data.type === 'done') {
            const assistantMessage: Message = {
              id: data.message_id || `temp-assistant-${Date.now()}`,
              role: 'assistant',
              content: fullContent,
              sources,
            };
            setMessages((prev) => [...prev, assistantMessage]);
            setStreamingContent('');
            eventSource.close();
            setSending(false);
            if (convId) {
              loadConversations();
            }
          }
        } catch {}
      };

      eventSource.onerror = () => {
        if (fullContent) {
          const assistantMessage: Message = {
            id: `temp-assistant-${Date.now()}`,
            role: 'assistant',
            content: fullContent,
            sources,
          };
          setMessages((prev) => [...prev, assistantMessage]);
        }
        setStreamingContent('');
        eventSource.close();
        setSending(false);
      };
    } catch {
      setSending(false);
    }
  };

  const handleLogout = () => {
    apiClient.removeToken();
    router.push('/login');
  };

  return (
    <div className="h-screen flex flex-col">
      <header className="flex-shrink-0 h-14 border-b border-gray-200 bg-white flex items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-gray-900">RAG QA</h1>
          <div className="relative">
            <button
              onClick={() => setShowProjectDropdown(!showProjectDropdown)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              {projects.find((p) => p.id === selectedProject)?.name || '选择项目'}
              <ChevronDown size={14} />
            </button>
            {showProjectDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => {
                      setSelectedProject(project.id);
                      setShowProjectDropdown(false);
                      handleNewConversation();
                    }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                      project.id === selectedProject
                        ? 'text-blue-600 bg-blue-50'
                        : 'text-gray-700'
                    }`}
                  >
                    {project.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push('/admin/dashboard')}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="管理后台"
          >
            <Settings size={18} />
          </button>
          <button
            onClick={handleLogout}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="退出登录"
          >
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-64 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col">
          <div className="p-3">
            <button
              onClick={handleNewConversation}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus size={16} />
              新建对话
            </button>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => loadConversationMessages(conv.id)}
                className={`w-full text-left px-3 py-2.5 text-sm rounded-lg mb-1 transition-colors flex items-center gap-2 ${
                  conv.id === currentConversation
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <MessageSquare size={14} className="flex-shrink-0" />
                <span className="truncate">{conv.title}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <div className="max-w-4xl mx-auto px-6 py-6">
              {messages.length === 0 && !streamingContent && (
                <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-gray-400">
                  <MessageSquare size={48} className="mb-4" />
                  <p className="text-lg font-medium">开始新的对话</p>
                  <p className="text-sm mt-1">选择项目并输入您的问题</p>
                </div>
              )}
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  id={msg.id}
                  role={msg.role}
                  content={msg.content}
                  sources={msg.sources}
                  feedback={msg.feedback}
                />
              ))}
              {streamingContent && (
                <ChatMessage
                  id="streaming"
                  role="assistant"
                  content={streamingContent}
                />
              )}
              {sending && !streamingContent && (
                <div className="flex justify-start mb-6">
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                    <Loader2 size={18} className="animate-spin text-blue-500" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
          <ChatInput onSend={handleSend} disabled={sending || !selectedProject} />
        </main>
      </div>
    </div>
  );
}
