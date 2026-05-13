"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Upload,
  FileText,
  Eye,
  RefreshCw,
  Trash2,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Loading, EmptyState } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";

interface Document {
  id: string;
  filename: string;
  status: string;
  size: number;
  chunk_count: number;
  project_id: string;
  created_at: string;
  updated_at: string;
}

interface DocumentChunk {
  id: string;
  content: string;
  chunk_index: number;
  metadata: Record<string, string>;
}

interface PaginatedResponse {
  items: Document[];
  total: number;
  page: number;
  size: number;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    processing: "处理中",
    completed: "已完成",
    error: "错误",
    failed: "失败",
    indexed: "已索引",
  };
  return labels[status] || status;
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
    case "indexed":
      return "text-[var(--color-success)]";
    case "processing":
      return "text-[var(--color-primary)]";
    case "error":
    case "failed":
      return "text-[var(--color-error)]";
    default:
      return "text-[var(--color-text-muted)]";
  }
}

export default function DocumentsPage() {
  const { addToast } = useToast();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize] = useState(20);

  const [chunksModalOpen, setChunksModalOpen] = useState(false);
  const [selectedChunks, setSelectedChunks] = useState<DocumentChunk[]>([]);
  const [selectedDocName, setSelectedDocName] = useState("");
  const [chunksLoading, setChunksLoading] = useState(false);

  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.get<{ id: string; name: string }[]>("/projects");
      setProjects(data);
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id);
      }
    } catch {
      addToast("error", "加载项目失败");
    }
  }, [addToast, selectedProjectId]);

  const loadDocuments = useCallback(async () => {
    if (!selectedProjectId) return;
    try {
      const data = await api.get<PaginatedResponse>(
        `/projects/${selectedProjectId}/documents`,
        { page: String(page), size: String(pageSize) }
      );
      setDocuments(data.items);
      setTotal(data.total);
    } catch {
      addToast("error", "加载文档列表失败");
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedProjectId, page, pageSize]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProjectId) loadDocuments();
  }, [loadDocuments, selectedProjectId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !selectedProjectId) return;

    setUploading(true);
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        await api.upload(
          `/projects/${selectedProjectId}/documents/upload`,
          formData
        );
        addToast("success", `${file.name} 上传成功`);
      } catch (err) {
        addToast(
          "error",
          `${file.name} 上传失败: ${err instanceof Error ? err.message : "未知错误"}`
        );
      }
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    loadDocuments();
  };

  const handleViewChunks = async (doc: Document) => {
    setSelectedDocName(doc.filename);
    setChunksModalOpen(true);
    setChunksLoading(true);
    try {
      const chunks = await api.get<DocumentChunk[]>(`/documents/${doc.id}/chunks`);
      setSelectedChunks(chunks);
    } catch {
      setSelectedChunks([]);
      addToast("error", "加载文档分块失败");
    } finally {
      setChunksLoading(false);
    }
  };

  const handleDelete = async (doc: Document) => {
    if (!confirm(`确定要删除文档"${doc.filename}"吗？`)) return;
    try {
      await api.delete(`/documents/${doc.id}`);
      addToast("success", "文档已删除");
      loadDocuments();
    } catch {
      addToast("error", "删除失败");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  if (loading) return <Loading text="加载文档列表..." />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            文档管理
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            管理各项目的知识文档，查看处理状态和分块详情
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() =>
              fileInputRef.current && fileInputRef.current.click()
            }
            loading={uploading}
            icon={<Upload size={16} />}
            disabled={!selectedProjectId}
          >
            上传文档
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleUpload}
            className="hidden"
            accept=".pdf,.txt,.md,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv"
          />
        </div>
      </div>

      {/* Project filter */}
      <div className="mb-4">
        <select
          value={selectedProjectId}
          onChange={(e) => {
            setSelectedProjectId(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-primary)] focus:outline-none"
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

      {!selectedProjectId ? (
        <EmptyState
          icon={<FileText size={48} />}
          title="请选择项目"
          description="选择一个项目查看其文档"
        />
      ) : documents.length === 0 ? (
        <EmptyState
          icon={<FileText size={48} />}
          title="暂无文档"
          description="上传文档到项目中，系统会自动进行分块和索引"
          action={
            <Button
              onClick={() =>
                fileInputRef.current && fileInputRef.current.click()
              }
              icon={<Upload size={16} />}
            >
              上传文档
            </Button>
          }
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    文件名
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    状态
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    大小
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    分块数
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    更新时间
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase text-[var(--color-text-muted)]">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg-secondary)]"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText
                          size={14}
                          className="text-[var(--color-primary)]"
                        />
                        <span className="text-sm text-[var(--color-text-primary)]">
                          {doc.filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-sm ${statusColor(doc.status)}`}
                      >
                        {statusLabel(doc.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {formatFileSize(doc.size)}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {doc.chunk_count}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {new Date(doc.updated_at).toLocaleString("zh-CN")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleViewChunks(doc)}
                          className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
                          title="查看分块"
                        >
                          <Eye size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(doc)}
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">
                共 {total} 个文档
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  上一页
                </Button>
                <span className="text-sm text-[var(--color-text-secondary)]">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Chunks Modal */}
      <Modal
        open={chunksModalOpen}
        onClose={() => setChunksModalOpen(false)}
        title={`文档分块 - ${selectedDocName}`}
        maxWidth="max-w-3xl"
      >
        {chunksLoading ? (
          <Loading text="加载分块..." />
        ) : selectedChunks.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
            暂无分块数据
          </p>
        ) : (
          <div className="space-y-3">
            {selectedChunks.map((chunk) => (
              <div
                key={chunk.id}
                className="rounded-lg border border-[var(--color-border)] p-3"
              >
                <div className="mb-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                  <span className="font-medium">#{chunk.chunk_index + 1}</span>
                </div>
                <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
                  {chunk.content.length > 500
                    ? `${chunk.content.slice(0, 500)}...`
                    : chunk.content}
                </p>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
