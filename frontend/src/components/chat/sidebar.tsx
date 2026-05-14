"use client";

import React, { useState, useMemo } from "react";
import {
  Plus,
  Search,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  LogOut,
  Settings,
} from "lucide-react";
import { useAppStore, type Project, type Conversation } from "@/lib/store";
import { removeToken } from "@/lib/auth";
import { useRouter } from "next/navigation";

interface SidebarProps {
  projects: Project[];
  selectedProjectId: string | null;
  onSelectProject: (id: string) => void;
  conversations: Conversation[];
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

function groupByDate(conversations: Conversation[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups: { label: string; items: Conversation[] }[] = [
    { label: "今天", items: [] },
    { label: "昨天", items: [] },
    { label: "更早", items: [] },
  ];

  for (const conv of conversations) {
    const date = new Date(conv.updated_at);
    if (date >= today) {
      groups[0].items.push(conv);
    } else if (date >= yesterday) {
      groups[1].items.push(conv);
    } else {
      groups[2].items.push(conv);
    }
  }

  return groups.filter((g) => g.items.length > 0);
}

export function ChatSidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  conversations,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
}: SidebarProps) {
  const router = useRouter();
  const { sidebarCollapsed, setSidebarCollapsed, setUser } = useAppStore();
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) =>
      c.title.toLowerCase().includes(q)
    );
  }, [conversations, searchQuery]);

  const grouped = useMemo(
    () => groupByDate(filteredConversations),
    [filteredConversations]
  );

  const handleLogout = () => {
    removeToken();
    setUser(null);
    router.push("/login");
  };

  if (sidebarCollapsed) {
    return (
      <div className="flex h-full w-14 flex-col items-center border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-3">
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="mb-4 rounded-lg p-2 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          title="展开侧边栏"
        >
          <ChevronRight size={18} />
        </button>
        <button
          onClick={onNewConversation}
          className="mb-4 rounded-lg p-2 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          title="新建对话"
        >
          <Plus size={18} />
        </button>
        <div className="flex-1" />
        <button
          onClick={handleLogout}
          className="rounded-lg p-2 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          title="退出登录"
        >
          <LogOut size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-72 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-3 py-3">
        <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">
          对话
        </h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setSidebarCollapsed(true)}
            className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
            title="收起侧边栏"
          >
            <ChevronLeft size={16} />
          </button>
        </div>
      </div>

      {/* New Conversation */}
      <div className="px-3 py-2">
        <button
          onClick={onNewConversation}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          <Plus size={14} />
          新建对话
        </button>
      </div>

      {/* Project Selector */}
      <div className="px-3 py-1">
        <div className="relative">
          <FolderOpen
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
          />
          <select
            value={selectedProjectId || ""}
            onChange={(e) => onSelectProject(e.target.value)}
            className="w-full appearance-none rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] py-2 pl-8 pr-3 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-primary)] focus:outline-none"
          >
            <option value="" disabled>
              选择项目...
            </option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 py-1">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索对话..."
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] py-2 pl-8 pr-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:border-[var(--color-primary)] focus:outline-none"
          />
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {grouped.length === 0 ? (
          <div className="px-2 py-8 text-center text-xs text-[var(--color-text-muted)]">
            暂无对话
          </div>
        ) : (
          grouped.map((group) => (
            <div key={group.label} className="mb-2">
              <div className="px-2 py-1 text-xs font-medium text-[var(--color-text-muted)]">
                {group.label}
              </div>
              {group.items.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                    selectedConversationId === conv.id
                      ? "bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
                  }`}
                >
                  <MessageSquare size={14} className="flex-shrink-0" />
                  <span className="truncate">{conv.title}</span>
                </button>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--color-border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/admin/projects")}
            className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <Settings size={14} />
            管理
          </button>
          <button
            onClick={handleLogout}
            className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <LogOut size={14} />
            退出
          </button>
        </div>
      </div>
    </div>
  );
}
