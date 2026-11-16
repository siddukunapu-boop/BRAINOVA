/**
 * StudyOS — Shared Query Cache, Request Deduplication & Stale-While-Revalidate Hook
 * Prevents repeated API request storms and eliminates redundant loading screens on route switches.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiRequest, onApiMutation } from '../services/api';

interface CacheEntry<T = unknown> {
  data: T;
  fetchedAt: number;
}

const DEFAULT_STALE_TIME_MS = 30_000; // 30s fresh window
const DEFAULT_MAX_AGE_MS = 5 * 60_000; // 5m stale-while-revalidate window

const _cache = new Map<string, CacheEntry>();
const _inflight = new Map<string, Promise<unknown>>();
const _listeners = new Map<string, Set<() => void>>();

function notifyKey(key: string): void {
  const subs = _listeners.get(key);
  if (subs) {
    subs.forEach((cb) => cb());
  }
}

export function getCachedEntry<T>(
  key: string,
  staleTimeMs: number = DEFAULT_STALE_TIME_MS,
  maxAgeMs: number = DEFAULT_MAX_AGE_MS
): { data: T; isStale: boolean } | null {
  const entry = _cache.get(key);
  if (!entry) return null;
  const age = Date.now() - entry.fetchedAt;
  if (age > maxAgeMs) {
    _cache.delete(key);
    return null;
  }
  return {
    data: entry.data as T,
    isStale: age > staleTimeMs,
  };
}

export function setCachedEntry<T>(key: string, data: T): void {
  _cache.set(key, { data, fetchedAt: Date.now() });
  notifyKey(key);
}

export function invalidateQueryCache(prefix?: string): void {
  if (!prefix) {
    _cache.clear();
    _inflight.clear();
    return;
  }
  for (const key of Array.from(_cache.keys())) {
    if (key.startsWith(prefix)) {
      _cache.delete(key);
    }
  }
}

onApiMutation((path) => {
  // Automatically invalidate the mutated resource family and dashboard summary
  const clean = path.split('?')[0];
  const segments = clean.split('/').filter(Boolean);
  if (segments.length >= 2) {
    invalidateQueryCache(`/${segments[0]}/${segments[1]}`);
  }
  if (!clean.startsWith('/api/dashboard')) {
    invalidateQueryCache('/api/dashboard');
  }
});

export function deduplicatedGet<T = unknown>(
  path: string,
  options: { force?: boolean; staleTimeMs?: number; maxAgeMs?: number } = {}
): Promise<T> {
  const {
    force = false,
    staleTimeMs = DEFAULT_STALE_TIME_MS,
    maxAgeMs = DEFAULT_MAX_AGE_MS,
  } = options;

  if (!force) {
    const cached = getCachedEntry<T>(path, staleTimeMs, maxAgeMs);
    if (cached && !cached.isStale) {
      return Promise.resolve(cached.data);
    }
  }

  const existing = _inflight.get(path);
  if (existing) {
    return existing as Promise<T>;
  }

  const req = apiRequest<T>(path, { method: 'GET' })
    .then((data) => {
      _cache.set(path, { data, fetchedAt: Date.now() });
      notifyKey(path);
      return data;
    })
    .finally(() => {
      _inflight.delete(path);
    });

  _inflight.set(path, req);
  return req;
}

export function prefetchQuery(path: string, staleTimeMs: number = DEFAULT_STALE_TIME_MS): void {
  const cached = getCachedEntry(path, staleTimeMs);
  if (cached && !cached.isStale) return;
  deduplicatedGet(path, { staleTimeMs }).catch(() => {
    // Prefetch failures are non-fatal
  });
}

export interface UseCachedQueryOptions<T> {
  enabled?: boolean;
  staleTimeMs?: number;
  maxAgeMs?: number;
  initialData?: T;
}

export function useCachedQuery<T = unknown>(
  path: string | null,
  options: UseCachedQueryOptions<T> = {}
): {
  data: T | undefined;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  refetch: (force?: boolean) => Promise<T | undefined>;
  setData: React.Dispatch<React.SetStateAction<T | undefined>>;
} {
  const {
    enabled = true,
    staleTimeMs = DEFAULT_STALE_TIME_MS,
    maxAgeMs = DEFAULT_MAX_AGE_MS,
    initialData,
  } = options;

  const initialCached = path ? getCachedEntry<T>(path, staleTimeMs, maxAgeMs) : null;
  const [data, setData] = useState<T | undefined>(initialCached?.data ?? initialData);
  const [loading, setLoading] = useState<boolean>(Boolean(enabled && path && !initialCached));
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (force: boolean = false): Promise<T | undefined> => {
      if (!path || !enabled) return undefined;
      const cached = !force ? getCachedEntry<T>(path, staleTimeMs, maxAgeMs) : null;
      if (cached) {
        if (mountedRef.current) {
          setData(cached.data);
          setLoading(false);
          setError(null);
        }
        if (!cached.isStale) {
          return cached.data;
        }
        if (mountedRef.current) setRefreshing(true);
      } else if (mountedRef.current) {
        if (data === undefined) setLoading(true);
        else setRefreshing(true);
      }

      try {
        const result = await deduplicatedGet<T>(path, { force, staleTimeMs, maxAgeMs });
        if (mountedRef.current) {
          setData(result);
          setError(null);
        }
        return result;
      } catch (err) {
        if (mountedRef.current) {
          const msg = err instanceof Error ? err.message : 'Failed to load data.';
          setError(msg);
        }
        return undefined;
      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [path, enabled, staleTimeMs, maxAgeMs]
  );

  useEffect(() => {
    if (!path || !enabled) {
      setLoading(false);
      return;
    }
    execute(false);
  }, [path, enabled, execute]);

  return { data, loading, refreshing, error, refetch: execute, setData };
}
