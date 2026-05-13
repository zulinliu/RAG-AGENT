"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  FolderOpen,
  Database,
  Users,
  FileText,
  BarChart3,
  MessageSquare,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { href: "/admin/projects", label: "项目管理", icon: FolderOpen },
  { href: "/admin/datasources", label: "数据源管理", icon: Database },
  { href: "/admin/users", label: "用户管理", icon: Users },
  { href: "/admin/documents", label: "文档管理", icon: FileText },
  { href: "/admin/status", label: "系统状态", icon: BarChart3 },
];

function Breadcrumb() {
  const pathname = usePathname();
  const current = navItems.find((item) => pathname === item.href);

  return (
    <div className="flex items-center gap-1.5 text-sm text-[var(--color-text-muted)]">
      <Link
        href="/admin"
        className="hover:text-[var(--color-text-primary)]"
      >
        管理
      </Link>
      {current && (
        <>
          <ChevronRight size={14} />
          <span className="text-[var(--color-text-primary)]">
            {current.label}
          </span>
        </>
      )}
    </div>
  );
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="flex w-56 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        {/* Logo */}
        <div className="border-b border-[var(--color-border)] px-4 py-4">
          <button
            onClick={() => router.push("/chat")}
            className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-primary)]">
              <BarChart3 size={16} className="text-white" />
            </div>
            管理后台
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-3">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                    : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
                }`}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Back to chat */}
        <div className="border-t border-[var(--color-border)] px-2 py-3">
          <button
            onClick={() => router.push("/chat")}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <MessageSquare size={16} />
            返回对话
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-primary)] px-6 py-3">
          <Breadcrumb />
        </header>
        <main className="flex-1 overflow-y-auto bg-[var(--color-bg-primary)] p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
