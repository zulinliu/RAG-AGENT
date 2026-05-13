'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  FolderKanban,
  Database,
  RefreshCw,
  Users,
  MessageSquare,
  LogOut,
} from 'lucide-react';
import { apiClient } from '@/lib/api';

const navItems = [
  { href: '/admin/dashboard', label: '质量监控', icon: LayoutDashboard },
  { href: '/admin/projects', label: '项目管理', icon: FolderKanban },
  { href: '/admin/datasources', label: '数据源配置', icon: Database },
  { href: '/admin/sync', label: '同步任务', icon: RefreshCw },
  { href: '/admin/users', label: '用户权限', icon: Users },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('rag_qa_token') : null;
    if (!token) {
      router.push('/login');
      return;
    }
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await apiClient.auth.getMe();
      setUser(userData);
    } catch {
      router.push('/login');
    }
  };

  const handleLogout = () => {
    apiClient.removeToken();
    router.push('/login');
  };

  return (
    <div className="h-screen flex">
      <aside className="w-56 flex-shrink-0 bg-gray-900 text-white flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-gray-800">
          <Link href="/chat" className="flex items-center gap-2">
            <MessageSquare size={20} />
            <span className="font-semibold">RAG QA</span>
          </Link>
        </div>
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400 truncate">
              {user?.username || '...'}
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 text-gray-400 hover:text-white rounded transition-colors"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-gray-50">
        {children}
      </main>
    </div>
  );
}
