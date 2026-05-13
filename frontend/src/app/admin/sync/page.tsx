'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface SyncTask {
  id: string;
  datasource_id: string;
  datasource_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  documents_synced: number;
  chunks_created: number;
  error_message: string | null;
}

export default function SyncPage() {
  const [tasks, setTasks] = useState<SyncTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    loadTasks();
  }, [statusFilter]);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const res = await apiClient.admin.getSyncTasks({
        status: statusFilter || undefined,
        limit: 50,
      });
      setTasks(res.items || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">同步任务监控</h1>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部状态</option>
            <option value="pending">等待中</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
          <button
            onClick={loadTasks}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            刷新
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">数据源</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">状态</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">开始时间</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">完成时间</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">文档数</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">分块数</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">错误信息</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">
                  {task.datasource_name}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      statusColors[task.status] || 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {task.status === 'running' && (
                      <Loader2 size={10} className="mr-1 animate-spin" />
                    )}
                    {task.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">
                  {task.started_at ? new Date(task.started_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">
                  {task.finished_at ? new Date(task.finished_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">{task.documents_synced}</td>
                <td className="px-4 py-3 text-sm text-gray-900">{task.chunks_created}</td>
                <td className="px-4 py-3 text-sm text-red-500 max-w-xs truncate">
                  {task.error_message || '-'}
                </td>
              </tr>
            ))}
            {tasks.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                  暂无同步任务
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
