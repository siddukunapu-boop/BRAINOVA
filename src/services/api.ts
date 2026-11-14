/**
 * AetherLearn AI — Strongly-Typed Frontend API Service Layer
 */

export const TOKEN_KEY = 'aetherlearn_auth_token';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function extractApiError(
  data: unknown,
  status: number
): { message: string; code?: string } {
  const fallback = `Request failed (${status})`;
  if (!data || typeof data !== 'object') {
    return { message: fallback };
  }
  const record = data as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return { message: detail };
  }
  if (detail && typeof detail === 'object') {
    const detailObj = detail as Record<string, unknown>;
    const code = typeof detailObj.code === 'string' ? detailObj.code : undefined;
    const message =
      typeof detailObj.message === 'string' && detailObj.message.trim()
        ? detailObj.message
        : fallback;
    return { message, code };
  }
  if (typeof record.message === 'string' && record.message.trim()) {
    const code = typeof record.code === 'string' ? record.code : undefined;
    return { message: record.message, code };
  }
  return { message: fallback };
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new ApiError(
      'Network request failed. Please verify the backend server is running.',
      0
    );
  }

  if (!response.ok) {
    let parsed: { message: string; code?: string } = {
      message: `Request failed (${response.status})`,
    };
    try {
      const data = await response.json();
      parsed = extractApiError(data, response.status);
    } catch {
      // ignore json parse error
    }
    throw new ApiError(parsed.message, response.status, parsed.code);
  }

  return response.json() as Promise<T>;
}

