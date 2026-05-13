'use client';

import { useState, useEffect } from 'react';
import { FileText, MessageSquare, Target, AlertTriangle, ThumbsDown } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface Stats {
  total_documents: number;
  total_conversations: number;
  total_questions: number;
  accuracy_rate: number;
}

interface BadCase {
  id: string;
  question: string;
  expected_answer: string;
  actual_answer: string;
  score: number;
  created_at: string;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [badCases, setBadCases] = useState<BadCase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsRes, badCasesRes] = await Promise.all([
        apiClient.admin.getStats(),
        apiClient.admin.getBadCases({ limit: 20 }),
      ]);
      setStats(statsRes);
      setBadCases(badCasesRes.items || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const statCards = stats
    ? [
        {
          label: '文档总数',
          value: stats.total_documents,
          icon: FileText,
          color: 'text-blue-600',
          bg: 'bg-blue-50',
        },
        {
          label: '对话总数',
          value: stats.total_conversations,
          icon: MessageSquare,
          color: 'text-green-600',
          bg: 'bg-green-50',
        },
        {
          label: '问答总数',
          value: stats.total_questions,
          icon: Target,
          color: 'text-purple-600',
          bg: 'bg-purple-50',
        },
        {
          label: '准确率',
          value: `${(stats.accuracy_rate * 100).toFixed(1)}%`,
          icon: AlertTriangle,
          color: 'text-orange-600',
          bg: 'bg-orange-50',
        },
      ]
    : [];

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">质量监控仪表盘</h1>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {statCards.map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.label}
                  className="bg-white rounded-xl border border-gray-200 p-5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-500">{card.label}</p>
                      <p className="text-2xl font-semibold text-gray-900 mt-1">{card.value}</p>
                    </div>
                    <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center`}>
                      <Icon size={20} className={card.color} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="bg-white rounded-xl border border-gray-200">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center gap-2">
              <ThumbsDown size={18} className="text-red-500" />
              <h2 className="text-base font-semibold text-gray-900">Bad Case 列表</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {badCases.map((bc) => (
                <div key={bc.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{bc.question}</p>
                      <div className="mt-2 space-y-1">
                        <p className="text-xs text-gray-500">
                          <span className="font-medium text-green-600">期望：</span>
                          {bc.expected_answer}
                        </p>
                        <p className="text-xs text-gray-500">
                          <span className="font-medium text-red-600">实际：</span>
                          {bc.actual_answer}
                        </p>
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                        评分: {bc.score.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {badCases.length === 0 && (
                <div className="px-5 py-12 text-center text-gray-400">
                  暂无 Bad Case
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
