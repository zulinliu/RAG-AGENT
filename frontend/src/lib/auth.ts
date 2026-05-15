/**
 * JWT token management for the RAG Agent frontend.
 *
 * SECURITY NOTE: Tokens are currently stored in localStorage, which is
 * accessible to any JavaScript running in the same origin. This makes them
 * vulnerable to XSS attacks. This is an acceptable trade-off for the current
 * phase of development (internal tool, 50-200 users).
 *
 * Future improvement: Migrate to httpOnly cookies set by the backend.
 * httpOnly cookies are not accessible to JavaScript and provide significantly
 * better protection against token theft via XSS. The backend would need to:
 *   1. Set the JWT in a SameSite=Strict; Secure; HttpOnly cookie
 *   2. Add a CSRF token for cross-origin protection
 *   3. Provide a dedicated /auth/logout endpoint to clear the cookie
 */

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
      // Token has no expiry — treat as invalid for safety
      removeToken();
      return false;
    }
    // Allow a 30-second clock-skew tolerance to avoid edge-case logouts
    if (payload.exp * 1000 < Date.now() - 30_000) {
      removeToken();
      return false;
    }
    return true;
  } catch {
    return false;
  }
}
