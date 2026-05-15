"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Sparkles } from "lucide-react";
import { ChatSidebar } from "@/components/chat/sidebar";
import { ChatMessage } from "@/components/chat/message";
import { ChatInput } from "@/components/chat/input";
import { EmptyState } from "@/components/ui/loading";
import { api, createSSEStream } from "@/lib/api";
import { useAppStore, type Project, type Conversation } from "@/lib/store";
import type { ChatMessageData } from "@/lib/types";
import { useToast } from "@/components/ui/toast";

export default function ChatPage() {
  const router = useRouter();
  const { currentProject, setCurrentProject, user, setUser } = useAppStore();
  const { addToast } = useToast();

  const [projects, setProjects] = useState<Project[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const streamingContentRef = useRef("");
  const completedRef = useRef(false);

  // Keep ref in sync with state
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, scrollToBottom]);

  // Load projects
  useEffect(() => {
    const controller = new AbortController();
    api
      .get<Project[]>("/projects")
      .then((data) => {
        if (!controller.signal.aborted) {
          setProjects(data);
          if (data.length > 0 && !currentProject) {
            setCurrentProject(data[0]);
          }
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          addToast("error", "加载项目列表失败");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setProjectsLoading(false);
        }
      });
    return () => controller.abort();
  }, [currentProject, setCurrentProject, addToast]);

  // Load user info
  useEffect(() => {
    if (!user) {
      const controller = new AbortController();
      api
        .get<{ id: string; username: string; email: string; role: string }>(
          "/auth/me"
        )
        .then((u) => {
          if (!controller.signal.aborted) {
            setUser({
              id: u.id,
              username: u.username,
              email: u.email,
              role: u.role,
            });
          }
        })
        .catch(() => {
          // User info load failure is non-critical, no toast needed
        });
      return () => controller.abort();
    }
  }, [user, setUser]);

  // Load conversations when project changes
  useEffect(() => {
    if (!currentProject) {
      setConversations([]);
      return;
    }
    const controller = new AbortController();
    api
      .get<Conversation[]>("/qa/conversations", {
        project_id: currentProject.id,
      })
      .then((data) => {
        if (!controller.signal.aborted) setConversations(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          addToast("error", "加载对话列表失败");
        }
      });
    return () => controller.abort();
  }, [currentProject, addToast]);

  const handleSelectProject = useCallback(
    (projectId: string) => {
      const project = projects.find((p) => p.id === projectId);
      if (project) {
        setCurrentProject(project);
        setCurrentConversationId(null);
        setMessages([]);
      }
    },
    [projects, setCurrentProject]
  );

  const handleSelectConversation = useCallback(
    (convId: string) => {
      setCurrentConversationId(convId);
      api
        .get<{
          id: string;
          messages: ChatMessageData[];
        }>(`/qa/conversations/${convId}`)
        .then((data) => {
          setMessages(data.messages || []);
        })
        .catch(() => {
          setMessages([]);
        });
    },
    []
  );

  const handleNewConversation = useCallback(() => {
    setCurrentConversationId(null);
    setMessages([]);
  }, []);

  const handleSend = useCallback(
    (query: string) => {
      if (!currentProject) return;

      const userMessage: ChatMessageData = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setStreamingContent("");
      completedRef.current = false;

      const assistantMessageId = crypto.randomUUID();

      abortRef.current = createSSEStream(
        "/qa/stream",
        {
          project_id: currentProject.id,
          query,
          conversation_id: currentConversationId || undefined,
        },
        {
          onChunk: (text) => {
            setStreamingContent((prev) => prev + text);
          },
          onDone: () => {
            completedRef.current = true;
            setIsStreaming(false);
            const content = streamingContentRef.current;
            if (content) {
              const assistantMessage: ChatMessageData = {
                id: assistantMessageId,
                role: "assistant",
                content,
              };
              setMessages((msgs) => [...msgs, assistantMessage]);
            }
            setStreamingContent("");

            // Refresh conversations list
            if (currentProject) {
              api
                .get<Conversation[]>("/qa/conversations", {
                  project_id: currentProject.id,
                })
                .then(setConversations)
                .catch(() => {
                  addToast("error", "刷新对话列表失败");
                });
            }
          },
          onError: (error) => {
            if (completedRef.current) return;
            setIsStreaming(false);
            const content = streamingContentRef.current;
            if (content) {
              const assistantMessage: ChatMessageData = {
                id: assistantMessageId,
                role: "assistant",
                content,
              };
              setMessages((msgs) => [...msgs, assistantMessage]);
            }
            setStreamingContent("");
            const errorMessage: ChatMessageData = {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `出错了: ${error.message}`,
            };
            setMessages((msgs) => [...msgs, errorMessage]);
          },
        }
      );
    },
    [currentProject, currentConversationId, addToast]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    const content = streamingContentRef.current;
    if (content) {
      const msg: ChatMessageData = {
        id: crypto.randomUUID(),
        role: "assistant",
        content,
      };
      setMessages((msgs) => [...msgs, msg]);
    }
    setStreamingContent("");
  }, []);

  return (
    <div className="flex h-screen">
      <ChatSidebar
        projects={projects}
        selectedProjectId={currentProject?.id || null}
        onSelectProject={handleSelectProject}
        conversations={conversations}
        selectedConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-primary)] px-6 py-3">
          <div className="flex items-center gap-2">
            {currentProject ? (
              <>
                <MessageSquare
                  size={18}
                  className="text-[var(--color-primary)]"
                />
                <span className="text-sm font-medium text-[var(--color-text-primary)]">
                  {currentProject.name}
                </span>
              </>
            ) : (
              <span className="text-sm text-[var(--color-text-muted)]">
                请选择一个项目
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
            {user && <span>{user.username}</span>}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isStreaming ? (
            <div className="flex h-full items-center justify-center">
              {currentProject ? (
                <EmptyState
                  icon={<Sparkles size={48} />}
                  title="选择一个项目开始提问"
                  description="输入你的问题，AI 将基于项目知识库为你提供精准解答"
                />
              ) : projectsLoading ? (
                <EmptyState
                  icon={
                    <svg
                      className="h-8 w-8 animate-spin text-[var(--color-primary)]"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                  }
                  title="加载项目中..."
                />
              ) : (
                <EmptyState
                  icon={<MessageSquare size={48} />}
                  title="暂无项目"
                  description="请先在管理后台创建项目并添加数据源"
                  action={
                    <button
                      onClick={() => router.push("/admin/projects")}
                      className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm text-white hover:bg-[var(--color-primary-hover)]"
                    >
                      创建项目
                    </button>
                  }
                />
              )}
            </div>
          ) : (
            <div className="mx-auto max-w-3xl">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  citations={msg.citations}
                  confidence={msg.confidence}
                  messageId={msg.id}
                  feedback={msg.feedback}
                />
              ))}
              {isStreaming && streamingContent && (
                <ChatMessage
                  role="assistant"
                  content={streamingContent}
                  isStreaming={true}
                />
              )}
              {isStreaming && !streamingContent && (
                <div className="px-4 py-6">
                  <div className="flex gap-4">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-medium text-white">
                      AI
                    </div>
                    <div className="flex items-center">
                      <div className="flex gap-1">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-primary)]" />
                        <span
                          className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-primary)]"
                          style={{ animationDelay: "0.1s" }}
                        />
                        <span
                          className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-primary)]"
                          style={{ animationDelay: "0.2s" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          disabled={!currentProject}
        />
      </div>
    </div>
  );
}
