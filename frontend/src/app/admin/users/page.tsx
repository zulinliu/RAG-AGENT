"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Shield, UserCheck, UserX } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Loading, EmptyState } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";
import type { User } from "@/lib/types";

const roleOptions = [
  { value: "admin", label: "管理员" },
  { value: "editor", label: "编辑者" },
  { value: "viewer", label: "查看者" },
];

const roleLabels: Record<string, string> = {
  admin: "管理员",
  editor: "编辑者",
  viewer: "查看者",
};

function roleBadgeColor(role: string): string {
  switch (role) {
    case "admin":
      return "bg-[var(--color-primary)]/20 text-[var(--color-primary)]";
    case "editor":
      return "bg-[var(--color-success)]/20 text-[var(--color-success)]";
    default:
      return "bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]";
  }
}

export default function UsersPage() {
  const { addToast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [newRole, setNewRole] = useState("");

  const loadUsers = useCallback(async () => {
    try {
      const data = await api.get<User[]>("/users");
      setUsers(data);
    } catch {
      addToast("error", "加载用户列表失败");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleRoleClick = (user: User) => {
    setSelectedUser(user);
    setNewRole(user.role);
    setRoleModalOpen(true);
  };

  const handleSaveRole = async () => {
    if (!selectedUser || !newRole) return;
    try {
      await api.put(`/users/${selectedUser.id}/role`, { role: newRole });
      addToast("success", `已更新 ${selectedUser.username} 的角色`);
      setRoleModalOpen(false);
      loadUsers();
    } catch (err) {
      addToast(
        "error",
        err instanceof Error ? err.message : "更新角色失败"
      );
    }
  };

  if (loading) return <Loading text="加载用户列表..." />;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
          用户管理
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          管理系统用户及角色权限
        </p>
      </div>

      {users.length === 0 ? (
        <EmptyState
          icon={<Shield size={48} />}
          title="暂无用户"
          description="系统中还没有注册用户"
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  用户名
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  邮箱
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  角色
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  注册时间
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-[var(--color-text-muted)]">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr
                  key={user.id}
                  className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-bg-secondary)]"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-bg-tertiary)] text-xs font-medium text-[var(--color-text-primary)]">
                        {user.username.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm font-medium text-[var(--color-text-primary)]">
                        {user.username}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                    {user.email || "-"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${roleBadgeColor(user.role)}`}
                    >
                      {roleLabels[user.role] || user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                    {new Date(user.created_at).toLocaleDateString("zh-CN")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRoleClick(user)}
                      icon={<UserCheck size={12} />}
                    >
                      角色
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Role Edit Modal */}
      <Modal
        open={roleModalOpen}
        onClose={() => setRoleModalOpen(false)}
        title={`编辑角色 - ${selectedUser?.username}`}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setRoleModalOpen(false)}
            >
              取消
            </Button>
            <Button onClick={handleSaveRole}>保存</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-[var(--color-bg-primary)] p-3">
            <p className="text-sm text-[var(--color-text-secondary)]">
              当前角色:{" "}
              <span className="font-medium text-[var(--color-text-primary)]">
                {selectedUser && roleLabels[selectedUser.role]}
              </span>
            </p>
          </div>
          <Select
            label="新角色"
            options={roleOptions}
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
          />
          <div className="rounded-lg border border-[var(--color-border)] p-3 text-xs text-[var(--color-text-muted)]">
            <p className="mb-1 font-medium text-[var(--color-text-secondary)]">
              角色说明:
            </p>
            <ul className="space-y-1">
              <li>
                <strong>管理员</strong>: 拥有所有权限，包括用户管理
              </li>
              <li>
                <strong>编辑者</strong>: 可以管理项目和数据源
              </li>
              <li>
                <strong>查看者</strong>: 只能使用问答功能
              </li>
            </ul>
          </div>
        </div>
      </Modal>
    </div>
  );
}
