'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ThumbsUp, ThumbsDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import oneDark from 'react-syntax-highlighter/dist/esm/styles/prism/one-dark';
import { SourceCard } from './SourceCard';
import { apiClient } from '@/lib/api';

interface Source {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  score: number;
  metadata?: Record<string, any>;
}

interface ChatMessageProps {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  feedback?: 'positive' | 'negative' | null;
}

export function ChatMessage({ id, role, content, sources, feedback }: ChatMessageProps) {
  const [showSources, setShowSources] = useState(false);
  const [currentFeedback, setCurrentFeedback] = useState<'positive' | 'negative' | null>(feedback || null);

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    const newRating = currentFeedback === rating ? null : rating;
    try {
      if (newRating) {
        await apiClient.chat.addFeedback(id, { rating: newRating });
      }
      setCurrentFeedback(newRating);
    } catch {}
  };

  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : ''}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-white border border-gray-200 text-gray-900'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown
                components={{
                  code({ node, className, children, ref, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const inline = !match;
                    return !inline ? (
                      <SyntaxHighlighter
                        style={oneDark as any}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          margin: '8px 0',
                          borderRadius: '8px',
                          fontSize: '13px',
                        }}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm"
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              {showSources ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              引用来源 ({sources.length})
            </button>
            {showSources && (
              <div className="mt-2 space-y-2">
                {sources.map((source, index) => (
                  <SourceCard key={source.chunk_id || index} source={source} index={index} />
                ))}
              </div>
            )}
          </div>
        )}

        {!isUser && (
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => handleFeedback('positive')}
              className={`p-1 rounded transition-colors ${
                currentFeedback === 'positive'
                  ? 'text-green-600 bg-green-50'
                  : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
              }`}
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => handleFeedback('negative')}
              className={`p-1 rounded transition-colors ${
                currentFeedback === 'negative'
                  ? 'text-red-600 bg-red-50'
                  : 'text-gray-400 hover:text-red-600 hover:bg-red-50'
              }`}
            >
              <ThumbsDown size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
