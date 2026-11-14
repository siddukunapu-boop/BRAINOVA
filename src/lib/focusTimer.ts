import type { FocusEventType, FocusSession } from '../types/focus.ts';

const FOCUS_CACHE_KEY = 'brainova_active_focus_session_v1';
const FOCUS_PENDING_EVENTS_KEY = 'brainova_focus_pending_events_v1';

export interface PendingFocusEvent {
  sessionId: string;
  eventType: FocusEventType;
  occurredAt: string;
  metadata?: Record<string, unknown>;
}

export function parseIsoMs(iso: string): number {
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : 0;
}

/**
 * Compute remaining whole seconds from the authoritative end timestamp.
 * serverOffsetMs = serverNowMs - clientNowMs.
 */
export function computeRemainingSeconds(
  endsAtIso: string,
  nowMs: number = Date.now(),
  serverOffsetMs: number = 0
): number {
  const endMs = parseIsoMs(endsAtIso);
  if (!endMs) return 0;
  const authoritativeNow = nowMs + serverOffsetMs;
  const diffMs = Math.max(0, endMs - authoritativeNow);
  return Math.ceil(diffMs / 1000);
}

/**
 * Compute elapsed progress percentage (0..100) from startedAt and endsAt.
 */
export function computeProgressPercent(
  startedAtIso: string,
  endsAtIso: string,
  nowMs: number = Date.now(),
  serverOffsetMs: number = 0
): number {
  const startMs = parseIsoMs(startedAtIso);
  const endMs = parseIsoMs(endsAtIso);
  if (!startMs || !endMs || endMs <= startMs) return 100;
  const authoritativeNow = nowMs + serverOffsetMs;
  const ratio = (authoritativeNow - startMs) / (endMs - startMs);
  return Math.max(0, Math.min(100, Math.round(ratio * 1000) / 10));
}

export function formatCountdown(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const seconds = clamped % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  if (hours > 0) {
    const hh = String(hours).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

export function formatDurationHuman(totalSeconds: number): string {
  const mins = Math.max(1, Math.round(totalSeconds / 60));
  if (mins < 60) return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `${hrs}h ${rem}m` : `${hrs}h`;
}

export function saveFocusSessionCache(session: FocusSession | null, serverOffsetMs = 0): void {
  if (typeof localStorage === 'undefined') return;
  try {
    if (!session) {
      localStorage.removeItem(FOCUS_CACHE_KEY);
      return;
    }
    localStorage.setItem(
      FOCUS_CACHE_KEY,
      JSON.stringify({ session, serverOffsetMs, cachedAt: Date.now() })
    );
  } catch {
    // Ignore storage quota errors
  }
}

export function loadFocusSessionCache(): { session: FocusSession; serverOffsetMs: number } | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(FOCUS_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { session?: FocusSession; serverOffsetMs?: number };
    if (!parsed?.session?.id || !parsed.session.ends_at) return null;
    return {
      session: parsed.session,
      serverOffsetMs: typeof parsed.serverOffsetMs === 'number' ? parsed.serverOffsetMs : 0,
    };
  } catch {
    return null;
  }
}

export function loadPendingFocusEvents(): PendingFocusEvent[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(FOCUS_PENDING_EVENTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function queuePendingFocusEvent(evt: PendingFocusEvent): void {
  if (typeof localStorage === 'undefined') return;
  try {
    const existing = loadPendingFocusEvents();
    existing.push(evt);
    localStorage.setItem(FOCUS_PENDING_EVENTS_KEY, JSON.stringify(existing.slice(-50)));
  } catch {
    // Ignore storage quota errors
  }
}

export function savePendingFocusEvents(events: PendingFocusEvent[]): void {
  if (typeof localStorage === 'undefined') return;
  try {
    if (events.length === 0) {
      localStorage.removeItem(FOCUS_PENDING_EVENTS_KEY);
    } else {
      localStorage.setItem(FOCUS_PENDING_EVENTS_KEY, JSON.stringify(events.slice(-50)));
    }
  } catch {
    // Ignore storage quota errors
  }
}

export function playFocusChime(kind: 'start' | 'complete'): void {
  if (typeof window === 'undefined') return;
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const notes = kind === 'start' ? [523.25, 659.25] : [523.25, 659.25, 783.99];
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + idx * 0.11);
      gain.gain.setValueAtTime(0.001, now + idx * 0.11);
      gain.gain.exponentialRampToValueAtTime(0.06, now + idx * 0.11 + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.11 + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + idx * 0.11);
      osc.stop(now + idx * 0.11 + 0.48);
    });
    setTimeout(() => {
      ctx.close().catch(() => {});
    }, 1200);
  } catch {
    // Ignore audio context restriction errors
  }
}

