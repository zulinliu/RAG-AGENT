'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';

interface Source {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  score: number;
  metadata?: Record<string, any>;
}

interface SourceCardProps {
  source: Source;
  index: number;
}

export function SourceCard({ source, index }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm">
          <FileText size={14} className="text-blue-500" />
          <span className="font-medium text-gray-700 truncate max-w-[200px]">
            {source.document_name}
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-500">相似度: {(source.score * 100).toFixed(1)}%</span>
        </div>
        {expanded ? (
          <ChevronUp size={14} className="text-gray-400" />
        ) : (
          <ChevronDown size={14} className="text-gray-400" />
        )}
      </button>
      {expanded && (
        <div className="px-3 py-2 border-t border-gray-200">
          <p className="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">
            {source.content}
          </p>
          {source.metadata && Object.keys(source.metadata).length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-100">
              <div className="flex flex-wrap gap-2">
                {Object.entries(source.metadata).map(([key, value]) => (
                  <span
                    key={key}
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-200 text-gray-600"
                  >
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
