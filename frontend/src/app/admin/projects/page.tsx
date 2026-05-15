"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Plus,
  Edit3,
  Trash2,
  Database,
  Users,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { EmptyState, Loading } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";
import type { Project } from "@/lib/types";

interface ProjectDataSource {
  id: string;
  name: string;
  type: string;
  status: string;
}

interface ProjectFormData {
  name: string;
  description: string;
}

export default function ProjectsPage() {
  const { addToast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [detailProject, setDetailProject] = useState<Project | null>(null);
  const [dataSources, setDataSources] = useState<ProjectDataSource[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);

  const [formData, setFormData] = useState<ProjectFormData>({
    name: "",
    description: "",
  });

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.get<Project[]>("/projects");
      setProjects(data);
    } catch {
      addToast("error", "加载项目列表失败");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = () => {
    setEditingProject(null);
    setFormData({ name: "", description: "" });
    setModalOpen(true);
  };

  const handleEdit = (project: Project) => {
    setEditingProject(project);
    setFormData({ name: project.name, description: project.description });
    setModalOpen(true);
  };

  const handleDetail = async (project: Project) => {
    setDetailProject(project);
    setDetailOpen(true);
    try {
      const ds = await api.get<ProjectDataSource[]>(
        `/projects/${project.id}/datasources`
      );
      setDataSources(ds);
    } catch {
      setDataSources([]);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      addToast("warning", "请输入项目名称");
      return;
    }

    try {
      if (editingProject) {
        await api.put(`/projects/${editingProject.id}`, formData);
        addToast("success", "项目已更新");
      } else {
        await api.post("/projects", formData);
        addToast("success", "项目已创建");
      }
      setModalOpen(false);
      loadProjects();
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "保存失败"
      );
    }
  };

  const handleDelete = (project: Project) => {
    setDeleteTarget(project);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/projects/${deleteTarget.id}`);
      addToast("success", "项目已删除");
      loadProjects();
    } catch {
      addToast("error", "删除失败");
    } finally {
      setShowDeleteConfirm(false);
      setDeleteTarget(null);
    }
  };

  if (loading) return <Loading text="加载项目列表..." />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            项目管理
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            管理知识库项目，每个项目独立维护数据源和文档
          </p>
        </div>
        <Button onClick={handleCreate} icon={<Plus size={16} />}>
          创建项目
        </Button>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={<Database size={48} />}
          title="暂无项目"
          description="创建第一个项目，开始构建企业知识库"
          action={
            <Button onClick={handleCreate} icon={<Plus size={16} />}>
              创建项目
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  项目名称
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  描述
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  创建时间
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr
                  key={project.id}
                  className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg-secondary)]"
                >
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-[var(--color-text-primary)]">
                      {project.name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                    {project.description || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                    {new Date(project.created_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleDetail(project)}
                        className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
                        title="详情"
                      >
                        <ExternalLink size={14} />
                      </button>
                      <button
                        onClick={() => handleEdit(project)}
                        className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
                        title="编辑"
                      >
                        <Edit3 size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(project)}
                        className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-error)]"
                        title="删除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingProject ? "编辑项目" : "创建项目"}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setModalOpen(false)}
            >
              取消
            </Button>
            <Button onClick={handleSave}>
              {editingProject ? "保存" : "创建"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="项目名称"
            value={formData.name}
            onChange={(e) =>
              setFormData({ ...formData, name: e.target.value })
            }
            placeholder="输入项目名称"
          />
          <Textarea
            label="项目描述"
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            placeholder="描述项目的用途和范围"
            rows={3}
          />
        </div>
      </Modal>

      {/* Detail Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title={detailProject?.name || "项目详情"}
        maxWidth="max-w-2xl"
      >
        {detailProject && (
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--color-text-secondary)]">
                基本信息
              </h3>
              <div className="rounded-lg bg-[var(--color-bg-primary)] p-3">
                <p className="text-sm text-[var(--color-text-muted)]">
                  {detailProject.description || "暂无描述"}
                </p>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--color-text-secondary)]">
                数据源 ({dataSources.length})
              </h3>
              {dataSources.length === 0 ? (
                <p className="text-sm text-[var(--color-text-muted)]">
                  暂无数据源
                </p>
              ) : (
                <div className="space-y-2">
                  {dataSources.map((ds) => (
                    <div
                      key={ds.id}
                      className="flex items-center justify-between rounded-lg bg-[var(--color-bg-primary)] px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <Database
                          size={14}
                          className="text-[var(--color-primary)]"
                        />
                        <span className="text-sm text-[var(--color-text-primary)]">
                          {ds.name}
                        </span>
                      </div>
                      <span
                        className={`text-xs ${ds.status === "active" ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]"}`}
                      >
                        {ds.status === "active" ? "已连接" : ds.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={showDeleteConfirm}
        onClose={() => {
          setShowDeleteConfirm(false);
          setDeleteTarget(null);
        }}
        title="确认删除"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowDeleteConfirm(false);
                setDeleteTarget(null);
              }}
            >
              取消
            </Button>
            <Button onClick={confirmDelete} className="bg-red-600 hover:bg-red-700 text-white">
              确认删除
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-secondary)]">
          确定要删除项目「{deleteTarget?.name}」吗？此操作不可撤销。
        </p>
      </Modal>
    </div>
  );
}
