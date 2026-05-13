'use client';

import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, X, Plug, RefreshCw, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface Datasource {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
  project_id: string;
  status: string;
  created_at: string;
}

const datasourceTypes = [
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'minio', label: 'MinIO/S3' },
  { value: 'web', label: 'Web爬虫' },
  { value: 'file', label: '文件上传' },
];

const configFields: Record<string, { key: string; label: string; type: string }[]> = {
  postgres: [
    { key: 'host', label: '主机', type: 'text' },
    { key: 'port', label: '端口', type: 'text' },
    { key: 'database', label: '数据库', type: 'text' },
    { key: 'username', label: '用户名', type: 'text' },
    { key: 'password', label: '密码', type: 'password' },
    { key: 'schema', label: 'Schema', type: 'text' },
    { key: 'table', label: '表名', type: 'text' },
  ],
  mysql: [
    { key: 'host', label: '主机', type: 'text' },
    { key: 'port', label: '端口', type: 'text' },
    { key: 'database', label: '数据库', type: 'text' },
    { key: 'username', label: '用户名', type: 'text' },
    { key: 'password', label: '密码', type: 'password' },
    { key: 'table', label: '表名', type: 'text' },
  ],
  minio: [
    { key: 'endpoint', label: 'Endpoint', type: 'text' },
    { key: 'access_key', label: 'Access Key', type: 'text' },
    { key: 'secret_key', label: 'Secret Key', type: 'password' },
    { key: 'bucket', label: 'Bucket', type: 'text' },
    { key: 'prefix', label: '前缀', type: 'text' },
  ],
  web: [
    { key: 'urls', label: 'URL列表(逗号分隔)', type: 'text' },
    { key: 'max_depth', label: '最大深度', type: 'text' },
    { key: 'max_pages', label: '最大页面数', type: 'text' },
  ],
  file: [],
};

export default function DatasourcesPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [datasources, setDatasources] = useState<Datasource[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDs, setEditingDs] = useState<Datasource | null>(null);
  const [testingId, setTestingId] = useState<string>('');
  const [syncingId, setSyncingId] = useState<string>('');
  const [form, setForm] = useState({
    name: '',
    type: 'postgres',
    config: {} as Record<string, string>,
  });

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) loadDatasources();
  }, [selectedProject]);

  const loadProjects = async () => {
    try {
      const res = await apiClient.projects.list();
      setProjects(res.items || []);
      if (res.items?.length > 0) {
        setSelectedProject(res.items[0].id);
      }
    } catch {}
  };

  const loadDatasources = async () => {
    if (!selectedProject) return;
    try {
      setLoading(true);
      const res = await apiClient.datasources.list(selectedProject);
      setDatasources(res || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingDs(null);
    setForm({ name: '', type: 'postgres', config: {} });
    setShowModal(true);
  };

  const handleEdit = (ds: Datasource) => {
    setEditingDs(ds);
    setForm({
      name: ds.name,
      type: ds.type,
      config: Object.fromEntries(
        Object.entries(ds.config || {}).map(([k, v]) => [k, String(v)])
      ),
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editingDs) {
        await apiClient.datasources.update(selectedProject, editingDs.id, {
          name: form.name,
          type: form.type,
          config: form.config,
        });
      } else {
        await apiClient.datasources.create(selectedProject, {
          name: form.name,
          type: form.type,
          config: form.config,
        });
      }
      setShowModal(false);
      loadDatasources();
    } catch {}
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此数据源？')) return;
    try {
      await apiClient.datasources.delete(selectedProject, id);
      loadDatasources();
    } catch {}
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const res = await apiClient.datasources.testConnection(selectedProject, id);
      alert(res.success ? `连接成功: ${res.message}` : `连接失败: ${res.message}`);
    } catch (err: any) {
      alert(`测试失败: ${err.message}`);
    } finally {
      setTestingId('');
    }
  };

  const handleSync = async (id: string) => {
    setSyncingId(id);
    try {
      await apiClient.datasources.triggerSync(selectedProject, id);
      alert('同步任务已触发');
    } catch (err: any) {
      alert(`触发失败: ${err.message}`);
    } finally {
      setSyncingId('');
    }
  };

  const currentFields = configFields[form.type] || [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">数据源配置</h1>
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={16} />
          添加数据源
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">类型</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">状态</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {datasources.map((ds) => (
                <tr key={ds.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{ds.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {datasourceTypes.find((t) => t.value === ds.type)?.label || ds.type}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        ds.status === 'active'
                          ? 'bg-green-100 text-green-700'
                          : ds.status === 'error'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {ds.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleTest(ds.id)}
                        disabled={testingId === ds.id}
                        className="p-1.5 text-gray-400 hover:text-green-600 rounded transition-colors disabled:opacity-50"
                        title="测试连接"
                      >
                        {testingId === ds.id ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : (
                          <Plug size={16} />
                        )}
                      </button>
                      <button
                        onClick={() => handleSync(ds.id)}
                        disabled={syncingId === ds.id}
                        className="p-1.5 text-gray-400 hover:text-blue-600 rounded transition-colors disabled:opacity-50"
                        title="触发同步"
                      >
                        {syncingId === ds.id ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : (
                          <RefreshCw size={16} />
                        )}
                      </button>
                      <button
                        onClick={() => handleEdit(ds)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 rounded transition-colors"
                        title="编辑"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(ds.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded transition-colors"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {datasources.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-gray-400">
                    暂无数据源
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">{editingDs ? '编辑数据源' : '添加数据源'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value, config: {} })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {datasourceTypes.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              {currentFields.map((field) => (
                <div key={field.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
                  <input
                    type={field.type}
                    value={form.config[field.key] || ''}
                    onChange={(e) =>
                      setForm({ ...form, config: { ...form.config, [field.key]: e.target.value } })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSave}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
