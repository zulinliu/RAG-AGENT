const TOKEN_KEY = "rag_agent_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      removeToken();
      return false;
    }
    const payload = JSON.parse(atob(parts[1]));
    if (typeof payload.exp !== "number") {
      return false;
    }
    if (payload.exp * 1000 < Date.now()) {
      removeToken();
      return false;
    }
    return true;
  } catch {
    return false;
  }
}
