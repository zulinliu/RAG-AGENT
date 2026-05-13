"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { ThumbsUp, ThumbsDown, AlertTriangle, Copy, Check } from "lucide-react";
import { Citation, type CitationData } from "./citation";
import { api } from "@/lib/api";

interface MessageProps {
  role: "user" | "assistant";
  content: string;
  citations?: CitationData[];
  confidence?: number;
  messageId?: string;
  feedback?: "thumbs_up" | "thumbs_down" | null;
  isStreaming?: boolean;
}

function ConfidenceIndicator({ confidence }: { confidence: number }) {
  const level =
    confidence >= 0.8 ? "high" : confidence >= 0.5 ? "medium" : "low";
  const label =
    level === "high"
      ? "高置信度"
      : level === "medium"
        ? "中等置信度"
        : "低置信度";
  const percentage = Math.round(confidence * 100);

  return (
    <div className="mt-2 flex items-center gap-1.5 text-xs">
      {level === "low" && (
        <AlertTriangle size={12} className="text-[var(--color-warning)]" />
      )}
      <span className={`confidence-${level}`}>
        {label} ({percentage}%)
      </span>
    </div>
  );
}

export function ChatMessage({
  role,
  content,
  citations,
  confidence,
  messageId,
  feedback: initialFeedback,
  isStreaming,
}: MessageProps) {
  const [currentFeedback, setCurrentFeedback] = useState<
    "thumbs_up" | "thumbs_down" | null
  >(initialFeedback ?? null);
  const [copied, setCopied] = useState(false);

  const isAssistant = role === "assistant";

  const handleFeedback = async (type: "thumbs_up" | "thumbs_down") => {
    if (!messageId) return;
    const newFeedback = currentFeedback === type ? null : type;
    setCurrentFeedback(newFeedback);
    try {
      if (newFeedback) {
        await api.post("/qa/feedback", {
          message_id: messageId,
          feedback: newFeedback,
        });
      }
    } catch {
      setCurrentFeedback(currentFeedback);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex gap-4 px-4 py-6 ${isAssistant ? "bg-[var(--color-bg-secondary)]" : ""}`}
    >
      <div className="flex-shrink-0">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm font-medium ${isAssistant ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]"}`}
        >
          {isAssistant ? "AI" : "U"}
        </div>
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1 text-sm font-medium text-[var(--color-text-secondary)]">
          {isAssistant ? "AI 助手" : "你"}
        </div>

        {isAssistant ? (
          <div className="markdown-body text-[var(--color-text-primary)]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const inline = !match;

                  if (inline) {
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  }

                  return (
                    <div className="relative">
                      <div className="absolute right-2 top-2 rounded bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-xs text-[var(--color-text-muted)]">
                        {match[1]}
                      </div>
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          margin: 0,
                          borderRadius: "0.5rem",
                          fontSize: "0.8125rem",
                        }}
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    </div>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
            {isStreaming && <span className="sse-cursor" />}
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-[var(--color-text-primary)]">
            {content}
          </p>
        )}

        {isAssistant && citations && citations.length > 0 && (
          <Citation citations={citations} />
        )}

        {isAssistant && confidence !== undefined && (
          <ConfidenceIndicator confidence={confidence} />
        )}

        {isAssistant && !isStreaming && messageId && (
          <div className="mt-2 flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="rounded p-1.5 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
              title="复制"
            >
              {copied ? (
                <Check size={14} className="text-[var(--color-success)]" />
              ) : (
                <Copy size={14} />
              )}
            </button>
            <button
              onClick={() => handleFeedback("thumbs_up")}
              className={`rounded p-1.5 transition-colors ${currentFeedback === "thumbs_up" ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"}`}
              title="有帮助"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => handleFeedback("thumbs_down")}
              className={`rounded p-1.5 transition-colors ${currentFeedback === "thumbs_down" ? "text-[var(--color-error)]" : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"}`}
              title="无帮助"
            >
              <ThumbsDown size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
