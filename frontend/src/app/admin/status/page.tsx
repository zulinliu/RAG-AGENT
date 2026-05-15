"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loading } from "@/components/ui/loading";

interface HealthStatus {
  status: string;
  services: Record<string, { status: string; latency_ms?: number }>;
}

export default function StatusPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchHealth = async () => {
    try {
      const data = await api.get<HealthStatus>("/health");
      setHealth(data);
      setError("");
    } catch {
      setError("无法获取系统状态");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <Loading />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">系统状态</h1>
        <span className="text-sm text-[var(--color-text-secondary)]">
          每 30 秒自动刷新
        </span>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400">
          {error}
        </div>
      )}

      {health && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(health.services || {}).map(([name, info]) => (
            <div
              key={name}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-medium capitalize">{name}</h3>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    info.status === "healthy"
                      ? "bg-green-500/10 text-green-400"
                      : "bg-red-500/10 text-red-400"
                  }`}
                >
                  {info.status === "healthy" ? "正常" : "异常"}
                </span>
              </div>
              {info.latency_ms !== undefined && (
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                  延迟: {info.latency_ms.toFixed(1)}ms
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
