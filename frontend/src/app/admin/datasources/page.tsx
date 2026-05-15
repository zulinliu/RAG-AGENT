"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Plus,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loading, EmptyState } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";
import { DataSourceForm } from "@/components/admin/data-source-form";
import type { Project, DataSource } from "@/lib/types";

interface SyncStatus {
  status: string;
  progress?: number;
  last_synced_at?: string;
  error?: string;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "active":
    case "completed":
      return <CheckCircle size={14} className="text-[var(--color-success)]" />;
    case "error":
    case "failed":
      return <XCircle size={14} className="text-[var(--color-error)]" />;
    case "syncing":
    case "running":
      return <Loader2 size={14} className="animate-spin text-[var(--color-primary)]" />;
    default:
      return <Clock size={14} className="text-[var(--color-text-muted)]" />;
  }
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "已连接",
    completed: "同步完成",
    error: "错误",
    failed: "失败",
    syncing: "同步中",
    running: "运行中",
    pending: "等待中",
    inactive: "未激活",
  };
  return labels[status] || status;
}

export default function DataSourcesPage() {
  const { addToast } = useToast();
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    try {
      const [projectsData, ...dsResults] = await Promise.all([
        api.get<Project[]>("/projects"),
        ...(selectedProjectId === "all"
          ? []
          : [api.get<DataSource[]>(`/projects/${selectedProjectId}/datasources`)]),
      ]);
      setProjects(projectsData);

      if (selectedProjectId === "all") {
        // TODO: 后端应提供 GET /api/v1/datasources 端点返回所有数据源，避免 N+1 查询
        const dsResults = await Promise.allSettled(
          projectsData.map((p) =>
            api.get<DataSource[]>(`/projects/${p.id}/datasources`)
          )
        );
        const allDs: DataSource[] = [];
        for (const result of dsResults) {
          if (result.status === "fulfilled") {
            allDs.push(...result.value);
          }
        }
        setDataSources(allDs);
      } else {
        setDataSources(dsResults[0] || []);
      }
    } catch {
      addToast("error", "加载数据失败");
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedProjectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSync = async (dsId: string) => {
    setSyncingIds((prev) => new Set(prev).add(dsId));
    try {
      await api.post(`/datasources/${dsId}/sync`);
      addToast("success", "同步已触发");
      setTimeout(loadData, 2000);
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "同步失败"
      );
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(dsId);
        return next;
      });
    }
  };

  const handleTestConnection = async (dsId: string) => {
    try {
      const status = await api.get<SyncStatus>(`/datasources/${dsId}/status`);
      if (status.status === "active" || status.status === "completed") {
        addToast("success", "连接测试成功");
      } else {
        addToast("warning", `连接状态: ${statusLabel(status.status)}`);
      }
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "连接测试失败"
      );
    }
  };

  const filteredDs =
    selectedProjectId === "all"
      ? dataSources
      : dataSources.filter((ds) => ds.project_id === selectedProjectId);

  if (loading) return <Loading text="加载数据源..." />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            数据源管理
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            管理各项目的知识数据来源，支持多种数据源类型
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)} icon={<Plus size={16} />}>
          添加数据源
        </Button>
      </div>

      {/* Project Filter */}
      <div className="mb-4">
        <select
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-primary)] focus:outline-none"
        >
          <option value="all">全部项目</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {filteredDs.length === 0 ? (
        <EmptyState
          icon={<RefreshCw size={48} />}
          title="暂无数据源"
          description="为项目添加数据源，开始同步知识文档"
          action={
            <Button
              onClick={() => setFormOpen(true)}
              icon={<Plus size={16} />}
            >
              添加数据源
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4">
          {filteredDs.map((ds) => {
            const projectName = projects.find(
              (p) => p.id === ds.project_id
            )?.name;
            const isSyncing = syncingIds.has(ds.id);

            return (
              <div
                key={ds.id}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-[var(--color-text-primary)]">
                        {ds.name}
                      </h3>
                      <span className="rounded bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 text-xs text-[var(--color-text-muted)]">
                        {ds.type}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                      <span>项目: {projectName}</span>
                      <span className="flex items-center gap-1">
                        <StatusIcon status={ds.status} />
                        {statusLabel(ds.status)}
                      </span>
                      {ds.last_synced_at && (
                        <span>
                          上次同步:{" "}
                          {new Date(ds.last_synced_at).toLocaleString("zh-CN")}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleTestConnection(ds.id)}
                    >
                      测试连接
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleSync(ds.id)}
                      loading={isSyncing}
                      icon={<RefreshCw size={12} />}
                    >
                      同步
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* DataSource Form Modal */}
      {formOpen && (
        <DataSourceForm
          projects={projects}
          onClose={() => setFormOpen(false)}
          onSuccess={() => {
            setFormOpen(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}
