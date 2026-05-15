"use client";

import React, { useState } from "react";
import { Database, Plug, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

interface Project {
  id: string;
  name: string;
}

interface DataSourceFormProps {
  projects: Project[];
  onClose: () => void;
  onSuccess: () => void;
}

type DataSourceType = "local" | "dingtalk" | "seafile" | "nas";

interface FieldConfig {
  key: string;
  label: string;
  type: "text" | "password" | "url";
  placeholder: string;
  required: boolean;
}

const dataSourceTypes: { value: DataSourceType; label: string; icon: string }[] = [
  { value: "local", label: "本地文件", icon: "folder" },
  { value: "dingtalk", label: "钉钉知识库", icon: "dingtalk" },
  { value: "seafile", label: "Seafile", icon: "cloud" },
  { value: "nas", label: "NAS 存储", icon: "server" },
];

const fieldConfigs: Record<DataSourceType, FieldConfig[]> = {
  local: [
    { key: "path", label: "文件路径", type: "text", placeholder: "/data/documents", required: true },
    { key: "pattern", label: "文件匹配模式", type: "text", placeholder: "*.pdf,*.txt,*.md", required: false },
  ],
  dingtalk: [
    { key: "app_key", label: "App Key", type: "text", placeholder: "钉钉应用 App Key", required: true },
    { key: "app_secret", label: "App Secret", type: "password", placeholder: "钉钉应用 App Secret", required: true },
    { key: "space_id", label: "知识库空间 ID", type: "text", placeholder: "知识库空间 ID", required: true },
  ],
  seafile: [
    { key: "server_url", label: "服务器地址", type: "url", placeholder: "https://seafile.example.com", required: true },
    { key: "api_token", label: "API Token", type: "password", placeholder: "Seafile API Token", required: true },
    { key: "repo_id", label: "资料库 ID", type: "text", placeholder: "资料库 ID", required: true },
  ],
  nas: [
    { key: "host", label: "NAS 地址", type: "url", placeholder: "https://nas.example.com:5000", required: true },
    { key: "username", label: "用户名", type: "text", placeholder: "NAS 登录用户名", required: true },
    { key: "password", label: "密码", type: "password", placeholder: "NAS 登录密码", required: true },
    { key: "share_path", label: "共享路径", type: "text", placeholder: "/share/documents", required: true },
  ],
};

export function DataSourceForm({
  projects,
  onClose,
  onSuccess,
}: DataSourceFormProps) {
  const { addToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    project_id: projects.length > 0 ? projects[0].id : "",
    type: "local" as DataSourceType,
    config: {} as Record<string, string>,
  });

  const fields = fieldConfigs[formData.type];

  const updateConfig = (key: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      config: { ...prev.config, [key]: value },
    }));
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      // TODO: 后端需提供 POST /api/v1/datasources/test-connection 端点
      // 该端点应接收 { type, config } 参数并返回 { success: boolean, message?: string }
      addToast("info", "连接测试中...");
      // Validate required fields before testing
      const requiredFields = fields.filter((f) => f.required);
      for (const field of requiredFields) {
        if (!formData.config[field.key]?.trim()) {
          addToast("warning", `请先填写${field.label}再测试连接`);
          return;
        }
      }
      await api.post("/datasources/test-connection", {
        type: formData.type,
        config: formData.config,
      });
      addToast("success", "连接测试成功");
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "连接测试失败"
      );
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      addToast("warning", "请输入数据源名称");
      return;
    }
    if (!formData.project_id) {
      addToast("warning", "请选择项目");
      return;
    }

    const requiredFields = fields.filter((f) => f.required);
    for (const field of requiredFields) {
      if (!formData.config[field.key]?.trim()) {
        addToast("warning", `请填写${field.label}`);
        return;
      }
    }

    setSaving(true);
    try {
      await api.post(`/projects/${formData.project_id}/datasources`, {
        name: formData.name,
        type: formData.type,
        config: formData.config,
      });
      addToast("success", "数据源已创建");
      onSuccess();
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "创建失败"
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="添加数据源"
      maxWidth="max-w-xl"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={handleTest}
            loading={testing}
            icon={<Plug size={14} />}
          >
            测试连接
          </Button>
          <div className="flex-1" />
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} loading={saving}>
            保存
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label="数据源名称"
          value={formData.name}
          onChange={(e) =>
            setFormData({ ...formData, name: e.target.value })
          }
          placeholder="输入数据源名称"
        />

        <Select
          label="所属项目"
          options={projects.map((p) => ({
            value: p.id,
            label: p.name,
          }))}
          value={formData.project_id}
          onChange={(e) =>
            setFormData({ ...formData, project_id: e.target.value })
          }
          placeholder="选择项目"
        />

        <div>
          <label className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]">
            数据源类型
          </label>
          <div className="grid grid-cols-4 gap-2">
            {dataSourceTypes.map((dsType) => (
              <button
                key={dsType.value}
                onClick={() =>
                  setFormData({
                    ...formData,
                    type: dsType.value,
                    config: {},
                  })
                }
                className={`flex flex-col items-center gap-1.5 rounded-lg border p-3 text-sm transition-colors ${
                  formData.type === dsType.value
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                    : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-light)]"
                }`}
              >
                <Database size={20} />
                {dsType.label}
              </button>
            ))}
          </div>
        </div>

        {/* Dynamic fields based on type */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">
            连接配置
          </h3>
          {fields.map((field) => (
            <Input
              key={field.key}
              label={field.label}
              type={field.type === "password" ? "password" : "text"}
              value={formData.config[field.key] || ""}
              onChange={(e) => updateConfig(field.key, e.target.value)}
              placeholder={field.placeholder}
            />
          ))}
        </div>
      </div>
    </Modal>
  );
}
