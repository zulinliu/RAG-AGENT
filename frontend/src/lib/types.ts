/**
 * Unified type definitions shared across the frontend.
 * Import from here instead of defining inline types in page components.
 */

import type { CitationData } from "@/components/chat/citation";

// Re-export store types for convenience
export type { User, Project, Conversation } from "@/lib/store";

/** A single chat message in a conversation. */
export interface ChatMessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: CitationData[];
  confidence?: number;
  feedback?: "thumbs_up" | "thumbs_down" | null;
}

/** A data source attached to a project. */
export interface DataSource {
  id: string;
  name: string;
  source_type: string;
  project_id: string;
  config: Record<string, string>;
  sync_status: string;
  last_synced_at?: string;
  created_at: string;
}
