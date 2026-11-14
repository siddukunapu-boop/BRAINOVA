import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../services/api';
import { useApp } from './AppContext';
import type {
  FocusCapabilityState,
  FocusConfig,
  FocusEventType,
  FocusPhase,
  FocusSession,
} from '../types/focus';
import {
  acquireKeyboardLockSafe,
  acquireWakeLockSafe,
  classifyNavigationUrl,
  exitFullscreenSafe,
  getFullscreenElement,
  getInitialCapabilities,
  isDistractionShortcutEvent,
  releaseKeyboardLockSafe,
  requestFullscreenImmediate,
  type WakeLockHandle,
} from '../lib/focusCapabilities';
import {
  computeProgressPercent,
  computeRemainingSeconds,
  loadFocusSessionCache,
  loadPendingFocusEvents,
  playFocusChime,
  queuePendingFocusEvent,
  saveFocusSessionCache,
  savePendingFocusEvents,
} from '../lib/focusTimer';

interface FocusContextValue {
  activeSession: FocusSession | null;
  completedSession: FocusSession | null;
  history: FocusSession[];
  loadingHistory: boolean;
  isReconciling: boolean;
  phase: FocusPhase;
  remainingSeconds: number;
  progressPercent: number;
  capabilities: FocusCapabilityState;
  fullscreenExitWarning: boolean;
  blockedNavNotice: string | null;
  distractionNotice: string | null;
  offlineSyncPending: boolean;
  startFocus: (config: FocusConfig) => Promise<void>;
  reenterFullscreen: () => Promise<void>;
  dismissFullscreenWarning: () => void;
  dismissBlockedNotice: () => void;
  dismissCompletedModal: () => void;
  abortFocus: () => Promise<void>;
  refreshHistory: () => Promise<void>;
  deleteHistorySession: (sessionId: string) => Promise<void>;
  clearAllHistory: () => Promise<{ deleted_count: number; active_preserved: boolean }>;
}

const FocusContext = createContext<FocusContextValue | undefined>(undefined);

function makeClientRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `freq_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export const FocusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, addToast } = useApp();

  const [activeSession, setActiveSession] = useState<FocusSession | null>(null);
  const [completedSession, setCompletedSession] = useState<FocusSession | null>(null);
  const [history, setHistory] = useState<FocusSession[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [isReconciling, setIsReconciling] = useState<boolean>(() => Boolean(user));
  const [phase, setPhase] = useState<FocusPhase>('idle');
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [progressPercent, setProgressPercent] = useState(0);
  const [capabilities, setCapabilities] = useState<FocusCapabilityState>(() =>
    getInitialCapabilities(false)
  );
  const [fullscreenExitWarning, setFullscreenExitWarning] = useState(false);
  const [blockedNavNotice, setBlockedNavNotice] = useState<string | null>(null);
  const [distractionNotice, setDistractionNotice] = useState<string | null>(null);
  const [offlineSyncPending, setOfflineSyncPending] = useState(false);

  const serverOffsetMsRef = useRef<number>(0);
  const wakeLockRef = useRef<WakeLockHandle | null>(null);
  const completingRef = useRef<boolean>(false);
  const activeSessionRef = useRef<FocusSession | null>(null);
  const phaseRef = useRef<FocusPhase>('idle');
  const wasFullscreenRef = useRef<boolean>(false);
  const userDismissedRecoveryRef = useRef<boolean>(false);
  const activationTimerRef = useRef<number | null>(null);

  useEffect(() => {
    activeSessionRef.current = activeSession;
  }, [activeSession]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const updateServerOffset = useCallback((serverTimeIso?: string) => {
    if (!serverTimeIso) return;
    const serverMs = Date.parse(serverTimeIso);
    if (Number.isFinite(serverMs)) {
      serverOffsetMsRef.current = serverMs - Date.now();
    }
  }, []);

  const releaseBrowserLocks = useCallback(async () => {
    if (wakeLockRef.current) {
      await wakeLockRef.current.release();
      wakeLockRef.current = null;
    }
    releaseKeyboardLockSafe();
    await exitFullscreenSafe();
    wasFullscreenRef.current = false;
    setCapabilities(getInitialCapabilities(false));
    setFullscreenExitWarning(false);
    setBlockedNavNotice(null);
    setDistractionNotice(null);
  }, []);

  const flushPendingEvents = useCallback(async () => {
    if (!user) return;
    const queued = loadPendingFocusEvents();
    if (queued.length === 0) {
      setOfflineSyncPending(false);
      return;
    }
    const remaining: typeof queued = [];
    for (let i = 0; i < queued.length; i += 1) {
      const evt = queued[i];
      try {
        await apiRequest(`/api/focus/sessions/${evt.sessionId}/events`, {
          method: 'POST',
          body: JSON.stringify({
            event_type: evt.eventType,
            occurred_at: evt.occurredAt,
            metadata: evt.metadata || {},
          }),
        });
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status === 0 || (status && status >= 500)) {
          remaining.push(...queued.slice(i));
          break;
        }
      }
    }
    savePendingFocusEvents(remaining);
    setOfflineSyncPending(remaining.length > 0);
  }, [user]);

  const recordEvent = useCallback(
    async (sessionId: string, eventType: FocusEventType, metadata?: Record<string, unknown>) => {
      const occurredAt = new Date().toISOString();
      try {
        const res = await apiRequest<{ session?: FocusSession }>(
          `/api/focus/sessions/${sessionId}/events`,
          {
            method: 'POST',
            body: JSON.stringify({
              event_type: eventType,
              occurred_at: occurredAt,
              metadata: metadata || {},
            }),
          }
        );
        if (res.session) {
          setActiveSession(res.session);
          saveFocusSessionCache(res.session, serverOffsetMsRef.current);
        }
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status === 0 || (status && status >= 500)) {
          queuePendingFocusEvent({ sessionId, eventType, occurredAt, metadata });
          setOfflineSyncPending(true);
        }
      }
    },
    []
  );

  const refreshHistory = useCallback(async () => {
    if (!user) return;
    setLoadingHistory(true);
    try {
      const res = await apiRequest<{ sessions: FocusSession[]; server_time?: string }>(
        '/api/focus/sessions?limit=25'
      );
      updateServerOffset(res.server_time);
      setHistory(res.sessions || []);
    } catch {
      // Keep existing history if offline
    } finally {
      setLoadingHistory(false);
    }
  }, [user, updateServerOffset]);

  const completeSessionInternal = useCallback(
    async (session: FocusSession) => {
      if (completingRef.current) return;
      completingRef.current = true;
      try {
        await releaseBrowserLocks();
        saveFocusSessionCache(null);
        await flushPendingEvents();

        let finalSession: FocusSession = {
          ...session,
          status: 'completed',
          completed_at: session.ends_at,
        };
        try {
          const res = await apiRequest<{ session: FocusSession; server_time?: string }>(
            `/api/focus/sessions/${session.id}/complete`,
            { method: 'POST' }
          );
          updateServerOffset(res.server_time);
          if (res.session) finalSession = res.session;
        } catch {
          setOfflineSyncPending(true);
        }

        if (session.sound_enabled) {
          playFocusChime('complete');
        }
        setActiveSession(null);
        setRemainingSeconds(0);
        setProgressPercent(100);
        setCompletedSession(finalSession);
        setPhase('completed');
        refreshHistory();
      } finally {
        completingRef.current = false;
      }
    },
    [releaseBrowserLocks, flushPendingEvents, updateServerOffset, refreshHistory]
  );

  const reconcileWithBackend = useCallback(async () => {
    if (!user) {
      setIsReconciling(false);
      return;
    }
    setIsReconciling(true);
    await flushPendingEvents();
    try {
      const res = await apiRequest<{
        session: FocusSession | null;
        recently_completed: FocusSession | null;
        server_time?: string;
      }>('/api/focus/sessions/active');
      updateServerOffset(res.server_time);

      if (res.session) {
        const rem = computeRemainingSeconds(
          res.session.ends_at,
          Date.now(),
          serverOffsetMsRef.current
        );
        if (rem <= 0) {
          await completeSessionInternal(res.session);
          return;
        }
        setActiveSession(res.session);
        saveFocusSessionCache(res.session, serverOffsetMsRef.current);
        setRemainingSeconds(rem);
        setProgressPercent(
          computeProgressPercent(
            res.session.started_at,
            res.session.ends_at,
            Date.now(),
            serverOffsetMsRef.current
          )
        );
        setPhase('active');
        const fsActive = Boolean(getFullscreenElement());
        setCapabilities((prev) => ({
          ...getInitialCapabilities(true),
          fullscreenActive: fsActive,
          fullscreenStatus: !prev.fullscreenSupported
            ? 'unsupported'
            : fsActive
            ? 'active'
            : 'inactive',
          wakeLockActive: Boolean(wakeLockRef.current),
          wakeLockStatus: !prev.wakeLockSupported
            ? 'unavailable'
            : wakeLockRef.current
            ? 'active'
            : 'released',
        }));
      } else {
        saveFocusSessionCache(null);
        if (res.recently_completed && phaseRef.current !== 'completed') {
          await releaseBrowserLocks();
          setActiveSession(null);
          setCompletedSession(res.recently_completed);
          setPhase('completed');
        } else if (phaseRef.current === 'active') {
          await releaseBrowserLocks();
          setActiveSession(null);
          setPhase('idle');
        }
      }
    } catch {
      const cached = loadFocusSessionCache();
      if (cached && cached.session.user_id === user.id && cached.session.status === 'active') {
        serverOffsetMsRef.current = cached.serverOffsetMs;
        const rem = computeRemainingSeconds(
          cached.session.ends_at,
          Date.now(),
          serverOffsetMsRef.current
        );
        if (rem > 0) {
          setActiveSession(cached.session);
          setRemainingSeconds(rem);
          setProgressPercent(
            computeProgressPercent(
              cached.session.started_at,
              cached.session.ends_at,
              Date.now(),
              serverOffsetMsRef.current
            )
          );
          setPhase('active');
          const fsActive = Boolean(getFullscreenElement());
          setCapabilities((prev) => ({
            ...getInitialCapabilities(true),
            fullscreenActive: fsActive,
            fullscreenStatus: !prev.fullscreenSupported
              ? 'unsupported'
              : fsActive
              ? 'active'
              : 'inactive',
          }));
        } else {
          await completeSessionInternal(cached.session);
        }
      }
    } finally {
      setIsReconciling(false);
    }
  }, [user, flushPendingEvents, updateServerOffset, completeSessionInternal, releaseBrowserLocks]);

  useEffect(() => {
    if (!user) {
      if (activationTimerRef.current) {
        window.clearTimeout(activationTimerRef.current);
        activationTimerRef.current = null;
      }
      releaseBrowserLocks();
      setActiveSession(null);
      setCompletedSession(null);
      setHistory([]);
      setPhase('idle');
      setIsReconciling(false);
      return;
    }

    reconcileWithBackend();
    refreshHistory();

    const handleOnline = () => {
      reconcileWithBackend();
    };
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'brainova_focus_active_session_v1') {
        reconcileWithBackend();
      }
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('storage', handleStorage);
    };
  }, [user, reconcileWithBackend, refreshHistory, releaseBrowserLocks]);

  // Authoritative timer loop
  useEffect(() => {
    if (!activeSession || (phase !== 'active' && phase !== 'activating')) return;

    const tick = () => {
      const rem = computeRemainingSeconds(
        activeSession.ends_at,
        Date.now(),
        serverOffsetMsRef.current
      );
      const pct = computeProgressPercent(
        activeSession.started_at,
        activeSession.ends_at,
        Date.now(),
        serverOffsetMsRef.current
      );
      setRemainingSeconds((prev) => (prev !== rem ? rem : prev));
      setProgressPercent((prev) => (Math.abs(prev - pct) >= 0.2 ? pct : prev));
      if (rem <= 0 && !completingRef.current) {
        completeSessionInternal(activeSession);
      }
    };

    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [activeSession, phase, completeSessionInternal]);

  // Central Navigation Guard & Defensive Shortcut Layer while Focus is active
  useEffect(() => {
    if (phase !== 'active' && phase !== 'activating') return;

    const blockExternalTarget = (href: string, via: string): boolean => {
      const decision = classifyNavigationUrl(href, window.location.origin);
      if (!decision.allowed) {
        setBlockedNavNotice(
          `External navigation to ${decision.host} was blocked to protect your Focus session.`
        );
        if (activeSessionRef.current) {
          recordEvent(activeSessionRef.current.id, 'external_navigation_blocked', {
            host: decision.host,
            reason: decision.reason,
            via,
          });
        }
        return true;
      }
      return false;
    };

    const handleAnchorEvent = (e: MouseEvent, via: string) => {
      const target = e.target as HTMLElement | null;
      const anchor = target?.closest?.('a') as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      if (!href) return;
      if (anchor.hasAttribute('download') && (href.startsWith('blob:') || href.startsWith('/'))) {
        return;
      }
      if (blockExternalTarget(href, via)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const handleClickCapture = (e: MouseEvent) => handleAnchorEvent(e, 'click');
    const handleAuxClickCapture = (e: MouseEvent) => {
      if (e.button === 1) handleAnchorEvent(e, 'middle_click');
    };
    const handleContextMenuCapture = (e: MouseEvent) => handleAnchorEvent(e, 'context_menu');

    const handleFormSubmitCapture = (e: SubmitEvent) => {
      const form = e.target as HTMLFormElement | null;
      const action = form?.getAttribute?.('action');
      if (!action) return;
      if (blockExternalTarget(action, 'form_submit')) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const handleKeyDownCapture = (e: KeyboardEvent) => {
      if (isDistractionShortcutEvent(e)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const originalOpen = window.open;
    window.open = function guardedWindowOpen(
      url?: string | URL,
      target?: string,
      features?: string
    ): Window | null {
      const href = url ? String(url) : '';
      if (blockExternalTarget(href, 'window.open')) {
        return null;
      }
      return originalOpen.call(window, url, target, features);
    };

    document.addEventListener('click', handleClickCapture, true);
    document.addEventListener('auxclick', handleAuxClickCapture, true);
    document.addEventListener('contextmenu', handleContextMenuCapture, true);
    document.addEventListener('submit', handleFormSubmitCapture, true);
    window.addEventListener('keydown', handleKeyDownCapture, true);
    return () => {
      document.removeEventListener('click', handleClickCapture, true);
      document.removeEventListener('auxclick', handleAuxClickCapture, true);
      document.removeEventListener('contextmenu', handleContextMenuCapture, true);
      document.removeEventListener('submit', handleFormSubmitCapture, true);
      window.removeEventListener('keydown', handleKeyDownCapture, true);
      window.open = originalOpen;
    };
  }, [phase, recordEvent]);

  // Page Visibility + Fullscreen monitoring while Focus is active
  useEffect(() => {
    if (phase !== 'active' && phase !== 'activating') return;

    const handleVisibilityChange = async () => {
      const session = activeSessionRef.current;
      if (!session) return;
      if (document.visibilityState === 'hidden') {
        setDistractionNotice('Tab switch or minimized window detected.');
        recordEvent(session.id, 'visibility_hidden');
      } else if (document.visibilityState === 'visible') {
        recordEvent(session.id, 'visibility_visible');
        if (!wakeLockRef.current) {
          const handle = await acquireWakeLockSafe();
          if (handle) {
            wakeLockRef.current = handle;
            setCapabilities((prev) => ({
              ...prev,
              wakeLockActive: true,
              wakeLockStatus: 'active',
            }));
          }
        }
        const rem = computeRemainingSeconds(
          session.ends_at,
          Date.now(),
          serverOffsetMsRef.current
        );
        if (rem <= 0) {
          completeSessionInternal(session);
        } else {
          setRemainingSeconds(rem);
        }
      }
    };

    const handleFullscreenChange = () => {
      const isFs = Boolean(getFullscreenElement());
      const session = activeSessionRef.current;
      if (!session) return;

      if (
        !isFs &&
        wasFullscreenRef.current &&
        (phaseRef.current === 'active' || phaseRef.current === 'activating')
      ) {
        // Unexpected fullscreen exit (e.g. 3-finger swipe / Task View / F11 / Escape):
        // NEVER abort, complete, or reset the timer!
        wasFullscreenRef.current = false;
        userDismissedRecoveryRef.current = false;
        setFullscreenExitWarning(true);
        setDistractionNotice('Fullscreen mode was interrupted.');
        releaseKeyboardLockSafe();
        setCapabilities((prev) => ({
          ...prev,
          fullscreenActive: false,
          fullscreenStatus: prev.fullscreenSupported ? 'inactive' : 'unsupported',
          keyboardLockActive: false,
          keyboardLockStatus: prev.keyboardLockSupported ? 'failed' : 'unsupported',
          keyboardLockErrorReason: prev.keyboardLockSupported
            ? 'Released because fullscreen exited.'
            : prev.keyboardLockErrorReason,
        }));
        recordEvent(session.id, 'fullscreen_exited');
      } else if (isFs) {
        wasFullscreenRef.current = true;
        userDismissedRecoveryRef.current = false;
        setFullscreenExitWarning(false);
        setCapabilities((prev) => ({
          ...prev,
          fullscreenActive: true,
          fullscreenStatus: 'active',
          fullscreenFailedReason: '',
        }));
      }
    };

    let lastBlurRecordedAt = 0;

    const handleWindowBlur = () => {
      const session = activeSessionRef.current;
      if (!session || (phaseRef.current !== 'active' && phaseRef.current !== 'activating')) return;
      const now = Date.now();
      if (now - lastBlurRecordedAt < 1500) return;
      lastBlurRecordedAt = now;
      // Window blur can come from Task View / Mission Control, app switching, or system dialogs;
      // keep session ACTIVE and record honestly without assuming an OS gesture was used.
      recordEvent(session.id, 'window_blur', {
        visibility: document.visibilityState,
      });
    };

    const handleWindowFocus = async () => {
      const session = activeSessionRef.current;
      if (!session || (phaseRef.current !== 'active' && phaseRef.current !== 'activating')) return;
      recordEvent(session.id, 'window_focus', {
        visibility: document.visibilityState,
      });
      if (!wakeLockRef.current && document.visibilityState === 'visible') {
        const handle = await acquireWakeLockSafe();
        if (handle) {
          wakeLockRef.current = handle;
          setCapabilities((prev) => ({
            ...prev,
            wakeLockActive: true,
            wakeLockStatus: 'active',
          }));
        }
      }
      const rem = computeRemainingSeconds(
        session.ends_at,
        Date.now(),
        serverOffsetMsRef.current
      );
      if (rem <= 0) {
        completeSessionInternal(session);
      } else {
        setRemainingSeconds(rem);
        // If fullscreen was lost while switched away and user hasn't dismissed recovery, show recovery UI
        if (
          !getFullscreenElement() &&
          wasFullscreenRef.current &&
          !userDismissedRecoveryRef.current
        ) {
          wasFullscreenRef.current = false;
          setFullscreenExitWarning(true);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    window.addEventListener('blur', handleWindowBlur);
    window.addEventListener('focus', handleWindowFocus);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      window.removeEventListener('blur', handleWindowBlur);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [phase, recordEvent, completeSessionInternal]);

  const startFocus = useCallback(
    async (config: FocusConfig) => {
      if (!user) return;
      if (activeSessionRef.current) {
        addToast('A Focus session is already active.', 'info');
        return;
      }

      // 1. Synchronous fullscreen request inside Start Focus user interaction
      const fsPromise = requestFullscreenImmediate(document.documentElement);

      const durationSeconds = Math.round(config.durationMinutes * 60);
      const clientRequestId = makeClientRequestId();

      let startedSession: FocusSession;
      try {
        const res = await apiRequest<{ session: FocusSession; server_time?: string }>(
          '/api/focus/sessions/start',
          {
            method: 'POST',
            body: JSON.stringify({
              duration_seconds: durationSeconds,
              session_title: config.sessionTitle.trim(),
              short_break_minutes: config.shortBreakMinutes,
              sound_enabled: config.soundEnabled,
              animations_enabled: config.animationsEnabled,
              client_request_id: clientRequestId,
            }),
          }
        );
        updateServerOffset(res.server_time);
        startedSession = res.session;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unable to start Focus session.';
        addToast(msg, 'error');
        await exitFullscreenSafe();
        return;
      }

      const fsResult = await fsPromise;
      wasFullscreenRef.current = fsResult.active;

      const wakeHandle = await acquireWakeLockSafe();
      wakeLockRef.current = wakeHandle;

      const kbResult = fsResult.active
        ? await acquireKeyboardLockSafe()
        : {
            active: false,
            status: capabilities.keyboardLockSupported ? ('failed' as const) : ('unsupported' as const),
            reason: capabilities.keyboardLockSupported
              ? 'Fullscreen is required before acquiring Keyboard Lock.'
              : 'Keyboard Lock API is not supported in this browser.',
          };

      const baseCaps = getInitialCapabilities(true);
      const nextCaps: FocusCapabilityState = {
        ...baseCaps,
        fullscreenSupported: fsResult.supported,
        fullscreenActive: fsResult.active,
        fullscreenStatus: !fsResult.supported
          ? 'unsupported'
          : fsResult.active
          ? 'active'
          : 'failed',
        fullscreenFailedReason: fsResult.active ? '' : fsResult.reason,
        wakeLockActive: Boolean(wakeHandle),
        wakeLockStatus: !baseCaps.wakeLockSupported
          ? 'unavailable'
          : wakeHandle
          ? 'active'
          : 'released',
        keyboardLockActive: kbResult.active,
        keyboardLockStatus: kbResult.status,
        keyboardLockErrorReason: kbResult.reason,
      };

      setCapabilities(nextCaps);
      setActiveSession(startedSession);
      saveFocusSessionCache(startedSession, serverOffsetMsRef.current);
      setRemainingSeconds(
        computeRemainingSeconds(startedSession.ends_at, Date.now(), serverOffsetMsRef.current)
      );
      setProgressPercent(0);
      setCompletedSession(null);
      setFullscreenExitWarning(false);

      if (fsResult.active) {
        recordEvent(startedSession.id, 'fullscreen_entered');
      } else {
        recordEvent(startedSession.id, 'fullscreen_failed', { reason: fsResult.reason });
      }
      if (!wakeHandle) {
        recordEvent(startedSession.id, 'capability_unavailable', { capability: 'wake_lock' });
      }
      if (fsResult.active && !kbResult.active) {
        recordEvent(startedSession.id, 'keyboard_lock_failed', {
          status: kbResult.status,
          reason: kbResult.reason,
        });
      }

      if (config.soundEnabled) {
        playFocusChime('start');
      }

      const reducedMotion =
        Boolean(user.preferences?.reduced_motion) ||
        (typeof window !== 'undefined' &&
          window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

      if (config.animationsEnabled && !reducedMotion) {
        setPhase('activating');
        activationTimerRef.current = window.setTimeout(() => {
          setPhase('active');
          activationTimerRef.current = null;
        }, 950);
      } else {
        setPhase('active');
      }
    },
    [user, addToast, updateServerOffset, recordEvent, capabilities.keyboardLockSupported]
  );

  const reenterFullscreen = useCallback(async () => {
    const fsResult = await requestFullscreenImmediate(document.documentElement);
    wasFullscreenRef.current = fsResult.active;

    let wakeHandle = wakeLockRef.current;
    if (!wakeHandle) {
      wakeHandle = await acquireWakeLockSafe();
      wakeLockRef.current = wakeHandle;
    }

    const kbResult = fsResult.active
      ? await acquireKeyboardLockSafe()
      : {
          active: false,
          status: capabilities.keyboardLockSupported ? ('failed' as const) : ('unsupported' as const),
          reason: fsResult.reason || 'Fullscreen restoration did not complete.',
        };

    if (fsResult.active) {
      setFullscreenExitWarning(false);
      if (activeSessionRef.current) {
        recordEvent(activeSessionRef.current.id, 'fullscreen_restored');
        if (!kbResult.active) {
          recordEvent(activeSessionRef.current.id, 'keyboard_lock_failed', {
            status: kbResult.status,
            reason: kbResult.reason,
          });
        }
      }
    } else if (activeSessionRef.current) {
      recordEvent(activeSessionRef.current.id, 'fullscreen_failed', { reason: fsResult.reason });
    }

    setCapabilities((prev) => ({
      ...prev,
      fullscreenSupported: fsResult.supported,
      fullscreenActive: fsResult.active,
      fullscreenStatus: !fsResult.supported
        ? 'unsupported'
        : fsResult.active
        ? 'active'
        : 'failed',
      fullscreenFailedReason: fsResult.active ? '' : fsResult.reason,
      wakeLockActive: Boolean(wakeHandle),
      wakeLockStatus: !prev.wakeLockSupported
        ? 'unavailable'
        : wakeHandle
        ? 'active'
        : 'released',
      keyboardLockActive: kbResult.active,
      keyboardLockStatus: kbResult.status,
      keyboardLockErrorReason: kbResult.reason,
    }));
  }, [recordEvent, capabilities.keyboardLockSupported]);

  const dismissFullscreenWarning = useCallback(() => {
    userDismissedRecoveryRef.current = true;
    setFullscreenExitWarning(false);
  }, []);

  const dismissBlockedNotice = useCallback(() => {
    setBlockedNavNotice(null);
  }, []);

  const dismissCompletedModal = useCallback(() => {
    setCompletedSession(null);
    setPhase('idle');
  }, []);

  const abortFocus = useCallback(async () => {
    const session = activeSessionRef.current;
    await releaseBrowserLocks();
    saveFocusSessionCache(null);
    if (session) {
      try {
        await apiRequest(`/api/focus/sessions/${session.id}/abort`, { method: 'POST' });
      } catch {
        // Always allow local exit even if offline
      }
    }
    setActiveSession(null);
    setRemainingSeconds(0);
    setProgressPercent(0);
    setPhase('idle');
    addToast('Focus session ended. Normal navigation restored.', 'info');
    refreshHistory();
  }, [releaseBrowserLocks, addToast, refreshHistory]);

  const deleteHistorySession = useCallback(
    async (sessionId: string) => {
      await apiRequest(`/api/focus/sessions/${sessionId}`, { method: 'DELETE' });
      setHistory((prev) => prev.filter((item) => item.id !== sessionId));
      addToast('Focus session deleted from history.', 'success');
    },
    [addToast]
  );

  const clearAllHistory = useCallback(async () => {
    const res = await apiRequest<{ deleted_count: number; active_preserved: boolean }>(
      '/api/focus/sessions/history',
      { method: 'DELETE' }
    );
    setHistory((prev) => prev.filter((item) => item.status === 'active'));
    addToast(
      res.active_preserved
        ? `Cleared ${res.deleted_count} historical sessions. Active session preserved.`
        : `Cleared ${res.deleted_count} historical sessions.`,
      'success'
    );
    return res;
  }, [addToast]);

  return (
    <FocusContext.Provider
      value={{
        activeSession,
        completedSession,
        history,
        loadingHistory,
        isReconciling,
        phase,
        remainingSeconds,
        progressPercent,
        capabilities,
        fullscreenExitWarning,
        blockedNavNotice,
        distractionNotice,
        offlineSyncPending,
        startFocus,
        reenterFullscreen,
        dismissFullscreenWarning,
        dismissBlockedNotice,
        dismissCompletedModal,
        abortFocus,
        refreshHistory,
        deleteHistorySession,
        clearAllHistory,
      }}
    >
      {children}
    </FocusContext.Provider>
  );
};

export function useFocus(): FocusContextValue {
  const ctx = useContext(FocusContext);
  if (!ctx) {
    throw new Error('useFocus must be used within FocusProvider');
  }
  return ctx;
}
