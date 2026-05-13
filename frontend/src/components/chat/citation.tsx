"use client";

import React, { useState } from "react";
import { ChevronDown, FileText, User, Calendar } from "lucide-react";

export interface CitationData {
  index: number;
  document_title: string;
  section?: string;
  author?: string;
  date?: string;
  content: string;
  relevance_score?: number;
}

interface CitationProps {
  citations: CitationData[];
}

export function Citation({ citations }: CitationProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggle = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <button
            key={c.index}
            onClick={() => toggle(c.index)}
            className={`citation-tag ${expandedIndex === c.index ? "bg-[var(--color-primary-hover)]" : ""}`}
            title={c.document_title}
          >
            <FileText size={10} className="mr-0.5" />
            来源{c.index + 1}
          </button>
        ))}
      </div>

      {expandedIndex !== null && (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] p-3 text-sm sse-message">
          {(() => {
            const citation = citations.find(
              (c) => c.index === expandedIndex
            );
            if (!citation) return null;
            return (
              <>
                <div className="mb-2 flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileText
                      size={14}
                      className="text-[var(--color-primary)]"
                    />
                    <span className="font-medium text-[var(--color-text-primary)]">
                      {citation.document_title}
                    </span>
                  </div>
                  <button
                    onClick={() => setExpandedIndex(null)}
                    className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                  >
                    <ChevronDown size={14} className="rotate-180" />
                  </button>
                </div>

                <div className="mb-2 flex flex-wrap gap-3 text-xs text-[var(--color-text-muted)]">
                  {citation.section && (
                    <span>章节: {citation.section}</span>
                  )}
                  {citation.author && (
                    <span className="flex items-center gap-1">
                      <User size={10} />
                      {citation.author}
                    </span>
                  )}
                  {citation.date && (
                    <span className="flex items-center gap-1">
                      <Calendar size={10} />
                      {citation.date}
                    </span>
                  )}
                  {citation.relevance_score !== undefined && (
                    <span>
                      相关度: {Math.round(citation.relevance_score * 100)}%
                    </span>
                  )}
                </div>

                <div className="rounded bg-[var(--color-bg-secondary)] p-2 text-[var(--color-text-secondary)]">
                  <p className="leading-relaxed">{citation.content}</p>
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}
