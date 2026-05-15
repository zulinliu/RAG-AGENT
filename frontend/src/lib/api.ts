import { getToken, removeToken } from "./auth";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, string>;
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }
  return url.pathname + url.search;
}

async function request<T>(
  path: string,
  options: RequestInit & RequestOptions = {}
): Promise<T> {
  const { params, headers: customHeaders, ...fetchOptions } = options;

  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...customHeaders,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = buildUrl(path, params);

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
  });

  if (response.status === 401) {
    removeToken();
    window.location.href = "/login";
    throw new ApiError(401, "登录已过期，请重新登录");
  }

  if (!response.ok) {
    let detail = `请求失败 (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || body.message || detail;
    } catch {
      // use default detail
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  get<T>(path: string, params?: Record<string, string>): Promise<T> {
    return request<T>(path, { method: "GET", params });
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: "DELETE" });
  },

  async upload<T>(path: string, formData: FormData): Promise<T> {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(buildUrl(path), {
      method: "POST",
      headers,
      body: formData,
    });

    if (response.status === 401) {
      removeToken();
      window.location.href = "/login";
      throw new ApiError(401, "登录已过期，请重新登录");
    }

    if (!response.ok) {
      let detail = `上传失败 (${response.status})`;
      try {
        const body = await response.json();
        detail = body.detail || body.message || detail;
      } catch {
        // use default detail
      }
      throw new ApiError(response.status, detail);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as T;
  },
};

export interface SSECallbacks {
  onChunk: (text: string) => void;
  onDone: (metadata?: Record<string, unknown>) => void;
  onError: (error: Error) => void;
}

export function createSSEStream(
  path: string,
  body: Record<string, unknown>,
  callbacks: SSECallbacks
): AbortController {
  const controller = new AbortController();
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  fetch(buildUrl(path), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        controller.abort();
        let detail = `请求失败 (${response.status})`;
        try {
          const errBody = await response.json();
          detail = errBody.detail || detail;
        } catch {
          // use default detail
        }
        throw new ApiError(response.status, detail);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("无法读取响应流");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete events (delimited by blank lines)
        // Split on double newlines to find event boundaries
        const eventBlocks = buffer.split("\n\n");
        // Keep the last (potentially incomplete) block in the buffer
        buffer = eventBlocks.pop() || "";

        for (const block of eventBlocks) {
          // Collect all data: lines within a single event
          const dataLines: string[] = [];

          for (const line of block.split("\n")) {
            if (line.startsWith("data: ")) {
              dataLines.push(line.slice(6));
            }
          }

          if (dataLines.length === 0) continue;

          // Per SSE spec, multiple data lines are joined with \n
          const data = dataLines.join("\n").trim();

          if (data === "[DONE]") {
            callbacks.onDone();
            return;
          }
          try {
            const parsed = JSON.parse(data) as {
              type?: string;
              data?: unknown;
              text?: string;
              error?: string;
              content?: string;
            };
            if (parsed.error || parsed.type === "error") {
              callbacks.onError(new Error(String(parsed.error || parsed.data || parsed.content || "请求失败")));
              return;
            }
            if (parsed.type === "done") {
              callbacks.onDone(
                typeof parsed.data === "object" && parsed.data !== null
                  ? (parsed.data as Record<string, unknown>)
                  : undefined
              );
              return;
            }
            if (typeof parsed.text === "string") {
              callbacks.onChunk(parsed.text);
            } else if (parsed.type === "text" && typeof parsed.data === "string") {
              callbacks.onChunk(parsed.data);
            }
          } catch {
            // skip malformed chunks
          }
        }
      }

      callbacks.onDone();
    })
    .catch((err: unknown) => {
      if (err instanceof DOMException && err.name === "AbortError") {
        callbacks.onDone();
        return;
      }
      callbacks.onError(
        err instanceof Error ? err : new Error(String(err))
      );
    });

  return controller;
}
