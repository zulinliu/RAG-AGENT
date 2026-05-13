import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RAG QA Platform',
  description: 'Intelligent Q&A Platform powered by RAG',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        {children}
      </body>
    </html>
  );
}
