"use client";

import React, { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAppStore, type Project } from "@/lib/store";
import { api } from "@/lib/api";
import type { CitationData } from "@/components/chat/citation";
import { useToast } from "@/components/ui/toast";

interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: CitationData[];
  confidence?: number;
  feedback?: "thumbs_up" | "thumbs_down" | null;
}

interface ConversationDetail {
  id: string;
  title: string;
  project_id: string;
  messages: ConversationMessage[];
}

export default function ConversationPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = params.id as string;
  const { currentProject, setCurrentProject, setUser, user } = useAppStore();
  const { addToast } = useToast();

  const [conversation, setConversation] =
    React.useState<ConversationDetail | null>(null);
  const [loading, setLoading] = React.useState(true);

  useEffect(() => {
    const controller = new AbortController();
    api
      .get<ConversationDetail>(`/qa/conversations/${conversationId}`)
      .then((data) => {
        if (!controller.signal.aborted) {
          setConversation(data);
          if (!currentProject || currentProject.id !== data.project_id) {
            api
              .get<Project>(`/projects/${data.project_id}`)
              .then(setCurrentProject)
              .catch(() => {
                addToast("error", "加载项目信息失败");
              });
          }
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          router.replace("/chat");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [conversationId, currentProject, setCurrentProject, router, addToast]);

  useEffect(() => {
    if (!user) {
      api
        .get<{ id: string; username: string; email: string; role: string }>(
          "/auth/me"
        )
        .then((u) =>
          setUser({
            id: u.id,
            username: u.username,
            email: u.email,
            role: u.role,
          })
        )
        .catch(() => {
          // User info load failure is non-critical
        });
    }
  }, [user, setUser]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
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
      </div>
    );
  }

  if (!conversation) return null;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-bg-primary)] px-6 py-3">
        <button
          onClick={() => router.push("/chat")}
          className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h1 className="text-sm font-medium text-[var(--color-text-primary)]">
            {conversation.title}
          </h1>
          <p className="text-xs text-[var(--color-text-muted)]">
            {conversation.messages.length} 条消息
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl">
          {conversation.messages.map((msg) => (
            <div
              key={msg.id}
              className={`px-4 py-6 ${msg.role === "assistant" ? "bg-[var(--color-bg-secondary)]" : ""}`}
            >
              <div className="flex gap-4">
                <div className="flex-shrink-0">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm font-medium ${msg.role === "assistant" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]"}`}
                  >
                    {msg.role === "assistant" ? "AI" : "U"}
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="mb-1 text-sm font-medium text-[var(--color-text-secondary)]">
                    {msg.role === "assistant" ? "AI 助手" : "你"}
                  </div>
                  <div className="text-[var(--color-text-primary)]">
                    {msg.content}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--color-border)] px-6 py-3">
        <div className="mx-auto max-w-3xl text-center">
          <button
            onClick={() => router.push("/chat")}
            className="rounded-lg bg-[var(--color-bg-tertiary)] px-4 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >
            返回对话列表继续提问
          </button>
        </div>
      </div>
    </div>
  );
}
