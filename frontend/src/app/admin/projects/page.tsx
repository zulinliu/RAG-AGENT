'use client';

import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Users as UsersIcon, X } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

interface Member {
  user_id: string;
  username: string;
  role: string;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showMemberModal, setShowMemberModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [members, setMembers] = useState<Member[]>([]);
  const [form, setForm] = useState({ name: '', description: '' });
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'viewer' });

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const res = await apiClient.projects.list();
      setProjects(res.items || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingProject(null);
    setForm({ name: '', description: '' });
    setShowModal(true);
  };

  const handleEdit = (project: Project) => {
    setEditingProject(project);
    setForm({ name: project.name, description: project.description || '' });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editingProject) {
        await apiClient.projects.update(editingProject.id, form);
      } else {
        await apiClient.projects.create(form);
      }
      setShowModal(false);
      loadProjects();
    } catch {}
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此项目？')) return;
    try {
      await apiClient.projects.delete(id);
      loadProjects();
    } catch {}
  };

  const handleMembers = async (projectId: string) => {
    setSelectedProjectId(projectId);
    try {
      const res = await apiClient.projects.listMembers(projectId);
      setMembers(res || []);
    } catch {
      setMembers([]);
    }
    setShowMemberModal(true);
  };

  const handleAddMember = async () => {
    try {
      await apiClient.projects.addMember(selectedProjectId, memberForm);
      const res = await apiClient.projects.listMembers(selectedProjectId);
      setMembers(res || []);
      setMemberForm({ user_id: '', role: 'viewer' });
    } catch {}
  };

  const handleRemoveMember = async (userId: string) => {
    try {
      await apiClient.projects.removeMember(selectedProjectId, userId);
      const res = await apiClient.projects.listMembers(selectedProjectId);
      setMembers(res || []);
    } catch {}
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">项目管理</h1>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={16} />
          创建项目
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">项目名称</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">描述</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">创建时间</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{project.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{project.description || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(project.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleMembers(project.id)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 rounded transition-colors"
                        title="成员管理"
                      >
                        <UsersIcon size={16} />
                      </button>
                      <button
                        onClick={() => handleEdit(project)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 rounded transition-colors"
                        title="编辑"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(project.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded transition-colors"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-gray-400">
                    暂无项目
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">{editingProject ? '编辑项目' : '创建项目'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">项目名称</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
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

      {showMemberModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">成员管理</h2>
              <button onClick={() => setShowMemberModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="用户ID"
                  value={memberForm.user_id}
                  onChange={(e) => setMemberForm({ ...memberForm, user_id: e.target.value })}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <select
                  value={memberForm.role}
                  onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="admin">管理员</option>
                  <option value="editor">编辑者</option>
                  <option value="viewer">查看者</option>
                </select>
                <button
                  onClick={handleAddMember}
                  className="px-3 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  添加
                </button>
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {members.map((member) => (
                  <div
                    key={member.user_id}
                    className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <span className="text-sm font-medium text-gray-900">{member.username}</span>
                      <span className="ml-2 text-xs text-gray-500">{member.role}</span>
                    </div>
                    <button
                      onClick={() => handleRemoveMember(member.user_id)}
                      className="text-gray-400 hover:text-red-600 transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
