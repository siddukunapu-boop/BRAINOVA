import type {
  FocusCapabilityState,
  KeyboardLockCapabilityStatus,
} from '../types/focus.ts';

export type NavigationPolicyDecision =
  | { allowed: true; reason: 'internal' | 'hash' | 'blob_or_data' | 'empty' }
  | { allowed: false; reason: 'external_http' | 'external_protocol'; host: string };

/**
 * Central navigation policy for Strict Focus Mode.
 * Distinguishes internal BRAINOVA routes and safe local blobs from external origins.
 */
export function classifyNavigationUrl(
  rawHref: string | null | undefined,
  currentOrigin: string
): NavigationPolicyDecision {
  const href = (rawHref || '').trim();
  if (!href) {
    return { allowed: true, reason: 'empty' };
  }
  if (href.startsWith('#')) {
    return { allowed: true, reason: 'hash' };
  }
  if (href.startsWith('blob:') || href.startsWith('data:')) {
    return { allowed: true, reason: 'blob_or_data' };
  }
  if (href.startsWith('/') && !href.startsWith('//')) {
    return { allowed: true, reason: 'internal' };
  }

  try {
    const base = currentOrigin || 'http://localhost';
    const parsed = new URL(href, base);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      if (parsed.origin === base) {
        return { allowed: true, reason: 'internal' };
      }
      return {
        allowed: false,
        reason: 'external_http',
        host: parsed.hostname || parsed.host || 'external site',
      };
    }
    return {
      allowed: false,
      reason: 'external_protocol',
      host: parsed.protocol.replace(':', ''),
    };
  } catch {
    return { allowed: true, reason: 'internal' };
  }
}

export function isFullscreenSupported(): boolean {
  if (typeof document === 'undefined') return false;
  const doc = document as Document & { webkitFullscreenEnabled?: boolean };
  const root = document.documentElement as HTMLElement & {
    webkitRequestFullscreen?: (options?: FullscreenOptions) => Promise<void> | void;
  };
  return Boolean(
    (doc.fullscreenEnabled || doc.webkitFullscreenEnabled) &&
      (typeof root?.requestFullscreen === 'function' ||
        typeof root?.webkitRequestFullscreen === 'function')
  );
}

export function getFullscreenElement(): Element | null {
  if (typeof document === 'undefined') return null;
  const doc = document as Document & { webkitFullscreenElement?: Element | null };
  return doc.fullscreenElement || doc.webkitFullscreenElement || null;
}

export function isWakeLockSupported(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as Navigator & {
    wakeLock?: { request?: (type: 'screen') => Promise<unknown> };
  };
  return Boolean(nav.wakeLock && typeof nav.wakeLock.request === 'function');
}

export function isKeyboardLockSupported(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as Navigator & {
    keyboard?: { lock?: (keys?: string[]) => Promise<void>; unlock?: () => void };
  };
  return Boolean(nav.keyboard && typeof nav.keyboard.lock === 'function');
}

export function getInitialCapabilities(navigationGuardActive = false): FocusCapabilityState {
  const fsSupported = isFullscreenSupported();
  const fsActive = Boolean(getFullscreenElement());
  const wakeSupported = isWakeLockSupported();
  const kbSupported = isKeyboardLockSupported();

  return {
    fullscreenSupported: fsSupported,
    fullscreenActive: fsActive,
    fullscreenStatus: !fsSupported ? 'unsupported' : fsActive ? 'active' : 'inactive',
    fullscreenFailedReason: '',
    wakeLockSupported: wakeSupported,
    wakeLockActive: false,
    wakeLockStatus: wakeSupported ? 'released' : 'unavailable',
    keyboardLockSupported: kbSupported,
    keyboardLockActive: false,
    keyboardLockStatus: kbSupported ? 'failed' : 'unsupported',
    keyboardLockErrorReason: kbSupported
      ? ''
      : 'Keyboard Lock API is not supported in this browser.',
    visibilitySupported:
      typeof document !== 'undefined' && typeof document.visibilityState === 'string',
    navigationGuardActive,
  };
}

/**
 * Request fullscreen synchronously inside a user click handler so browser user activation is preserved.
 */
export function requestFullscreenImmediate(
  target?: HTMLElement
): Promise<{ active: boolean; supported: boolean; reason: string }> {
  if (typeof document === 'undefined' || !isFullscreenSupported()) {
    return Promise.resolve({
      active: false,
      supported: false,
      reason: 'Fullscreen API is not supported in this browser.',
    });
  }

  const el = (target || document.documentElement) as HTMLElement & {
    webkitRequestFullscreen?: (options?: FullscreenOptions) => Promise<void> | void;
  };

  try {
    let res: Promise<void> | void;
    if (typeof el.requestFullscreen === 'function') {
      try {
        res = el.requestFullscreen({ navigationUI: 'hide' });
      } catch {
        res = el.requestFullscreen();
      }
    } else {
      res = el.webkitRequestFullscreen?.();
    }

    if (res && typeof (res as Promise<void>).then === 'function') {
      return (res as Promise<void>)
        .then(() => ({
          active: Boolean(getFullscreenElement()),
          supported: true,
          reason: '',
        }))
        .catch((err: unknown) => ({
          active: false,
          supported: true,
          reason: err instanceof Error ? err.message : 'Fullscreen permission was denied.',
        }));
    }

    return Promise.resolve({
      active: Boolean(getFullscreenElement()),
      supported: true,
      reason: '',
    });
  } catch (err) {
    return Promise.resolve({
      active: false,
      supported: true,
      reason: err instanceof Error ? err.message : 'Fullscreen request failed.',
    });
  }
}

export async function exitFullscreenSafe(): Promise<void> {
  if (typeof document === 'undefined') return;
  const doc = document as Document & { webkitExitFullscreen?: () => Promise<void> | void };
  if (!getFullscreenElement()) return;
  try {
    if (typeof doc.exitFullscreen === 'function') {
      await doc.exitFullscreen();
    } else if (typeof doc.webkitExitFullscreen === 'function') {
      await doc.webkitExitFullscreen();
    }
  } catch {
    // Ignore errors if document is no longer in fullscreen
  }
}

export interface WakeLockHandle {
  release: () => Promise<void>;
}

export async function acquireWakeLockSafe(): Promise<WakeLockHandle | null> {
  if (!isWakeLockSupported()) return null;
  try {
    const nav = navigator as Navigator & {
      wakeLock: {
        request: (type: 'screen') => Promise<{
          release: () => Promise<void>;
          addEventListener?: (ev: string, cb: () => void) => void;
        }>;
      };
    };
    const sentinel = await nav.wakeLock.request('screen');
    return {
      release: async () => {
        try {
          await sentinel.release();
        } catch {
          // Ignore release failures
        }
      },
    };
  } catch {
    return null;
  }
}

export interface KeyboardLockResult {
  active: boolean;
  status: KeyboardLockCapabilityStatus;
  reason: string;
}

/**
 * Request all-keys Keyboard Lock capture mode (`navigator.keyboard.lock()`).
 * Supported only in fullscreen in Chromium-based browsers; never claims OS-reserved shortcuts are blocked.
 */
export async function acquireKeyboardLockSafe(): Promise<KeyboardLockResult> {
  if (!isKeyboardLockSupported()) {
    return {
      active: false,
      status: 'unsupported',
      reason: 'Keyboard Lock API is not supported in this browser.',
    };
  }
  if (!getFullscreenElement()) {
    return {
      active: false,
      status: 'failed',
      reason: 'Fullscreen must be active before Keyboard Lock can be acquired.',
    };
  }
  try {
    const nav = navigator as Navigator & {
      keyboard: { lock: (keys?: string[]) => Promise<void> };
    };
    await nav.keyboard.lock();
    return {
      active: true,
      status: 'active',
      reason: '',
    };
  } catch (err: unknown) {
    const errName = err instanceof Error ? err.name : '';
    const errMsg = err instanceof Error ? err.message : 'Keyboard Lock request failed.';
    if (errName === 'NotAllowedError' || errName === 'SecurityError') {
      return {
        active: false,
        status: 'denied',
        reason: errMsg,
      };
    }
    return {
      active: false,
      status: 'failed',
      reason: errMsg,
    };
  }
}

export function releaseKeyboardLockSafe(): void {
  if (typeof navigator === 'undefined') return;
  const nav = navigator as Navigator & {
    keyboard?: { unlock?: () => void };
  };
  try {
    if (nav.keyboard && typeof nav.keyboard.unlock === 'function') {
      nav.keyboard.unlock();
    }
  } catch {
    // Ignore unlock errors
  }
}

/**
 * Additional defensive check for keyboard events that reach JS.
 * Never blocks typing, text selection, rich-text editing, or accessibility navigation.
 */
export function isDistractionShortcutEvent(e: {
  key?: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
}): boolean {
  const key = (e.key || '').toLowerCase();
  if (key === 'f11') return true;
  if (e.ctrlKey || e.metaKey) {
    // Only browser-chrome tab/window/address-bar shortcuts; never editing shortcuts (c/v/x/a/z/y/b/i/u)
    if (key === 'w' || key === 't' || key === 'n' || key === 'l') {
      return true;
    }
  }
  return false;
}
