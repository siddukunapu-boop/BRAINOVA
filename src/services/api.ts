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
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
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
    let errorDetail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorDetail =
          typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new ApiError(errorDetail, response.status);
  }

  return response.json() as Promise<T>;
}

