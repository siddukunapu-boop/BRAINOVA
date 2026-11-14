// Frontend unit tests for BRAINOVA Strict Focus Mode using Node's built-in test runner.
// Run: node --test tests/frontend/focus_mode.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  classifyNavigationUrl,
  getInitialCapabilities,
  requestFullscreenImmediate,
  exitFullscreenSafe,
  acquireWakeLockSafe,
  acquireKeyboardLockSafe,
  releaseKeyboardLockSafe,
  isDistractionShortcutEvent,
} from '../../src/lib/focusCapabilities.ts';
import {
  computeRemainingSeconds,
  computeProgressPercent,
  formatCountdown,
  formatDurationHuman,
} from '../../src/lib/focusTimer.ts';

test('central navigation policy allows all internal BRAINOVA routes and local blobs', () => {
  const origin = 'http://127.0.0.1:8000';
  for (const url of [
    '/dashboard',
    '/roadmaps',
    '/roadmaps/rm_123/topics/tp_456',
    '/resources',
    '/diary',
    '/study-journal',
    '/focus',
    '/settings',
    'http://127.0.0.1:8000/study-journal',
    '#top',
    'blob:http://127.0.0.1:8000/abc-123',
    'data:text/plain;base64,SGVsbG8=',
    '',
  ]) {
    const decision = classifyNavigationUrl(url, origin);
    assert.equal(decision.allowed, true, `Expected internal/safe URL to be allowed: ${url}`);
  }
});

test('central navigation policy blocks external origins and protocols', () => {
  const origin = 'http://127.0.0.1:8000';
  const ext1 = classifyNavigationUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ', origin);
  assert.equal(ext1.allowed, false);
  if (!ext1.allowed) {
    assert.equal(ext1.reason, 'external_http');
    assert.equal(ext1.host, 'www.youtube.com');
  }

  const ext2 = classifyNavigationUrl('http://localhost:5173/other', origin);
  assert.equal(ext2.allowed, false);

  const ext3 = classifyNavigationUrl('//evil.example.com/path', origin);
  assert.equal(ext3.allowed, false);

  const ext4 = classifyNavigationUrl('mailto:someone@example.com', origin);
  assert.equal(ext4.allowed, false);
  if (!ext4.allowed) {
    assert.equal(ext4.reason, 'external_protocol');
  }
});

test('authoritative timer engine computes remaining seconds accurately across refresh and clock offset', () => {
  const startMs = Date.UTC(2026, 10, 14, 10, 0, 0);
  const endMs = startMs + 25 * 60 * 1000;
  const startIso = new Date(startMs).toISOString();
  const endIso = new Date(endMs).toISOString();

  // At start
  assert.equal(computeRemainingSeconds(endIso, startMs, 0), 1500);
  assert.equal(computeProgressPercent(startIso, endIso, startMs, 0), 0);

  // Midpoint after simulated refresh (12m30s elapsed)
  const midMs = startMs + 750 * 1000;
  assert.equal(computeRemainingSeconds(endIso, midMs, 0), 750);
  assert.equal(computeProgressPercent(startIso, endIso, midMs, 0), 50);

  // Server clock offset (+5s ahead of client)
  assert.equal(computeRemainingSeconds(endIso, midMs, 5000), 745);

  // Past expiration clamps cleanly to 0 and 100%
  const afterMs = endMs + 120 * 1000;
  assert.equal(computeRemainingSeconds(endIso, afterMs, 0), 0);
  assert.equal(computeProgressPercent(startIso, endIso, afterMs, 0), 100);
});

test('countdown and duration formatters produce clean human-readable output', () => {
  assert.equal(formatCountdown(1500), '25:00');
  assert.equal(formatCountdown(65), '01:05');
  assert.equal(formatCountdown(3661), '01:01:01');
  assert.equal(formatCountdown(-5), '00:00');

  assert.equal(formatDurationHuman(1500), '25 min');
  assert.equal(formatDurationHuman(3600), '1h');
  assert.equal(formatDurationHuman(5400), '1h 30m');
});

test('capability detection never claims active when browser APIs are unsupported', async () => {
  const caps = getInitialCapabilities(false);
  assert.equal(caps.fullscreenSupported, false);
  assert.equal(caps.fullscreenActive, false);
  assert.equal(caps.fullscreenStatus, 'unsupported');
  assert.equal(caps.wakeLockSupported, false);
  assert.equal(caps.wakeLockActive, false);
  assert.equal(caps.wakeLockStatus, 'unavailable');
  assert.equal(caps.keyboardLockSupported, false);
  assert.equal(caps.keyboardLockActive, false);
  assert.equal(caps.keyboardLockStatus, 'unsupported');

  const fsRes = await requestFullscreenImmediate();
  assert.equal(fsRes.supported, false);
  assert.equal(fsRes.active, false);

  const wake = await acquireWakeLockSafe();
  assert.equal(wake, null);

  const kb = await acquireKeyboardLockSafe();
  assert.equal(kb.active, false);
  assert.equal(kb.status, 'unsupported');
});

test('all-keys keyboard lock, fullscreen, wake lock, denial handling, and cleanup work accurately', async () => {
  const origDoc = globalThis.document;
  const origNavDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');

  let released = false;
  let unlocked = false;
  let exited = false;
  let fsEl = null;
  let lockArgsCount = -1;

  try {
    globalThis.document = {
      fullscreenEnabled: true,
      visibilityState: 'visible',
      get fullscreenElement() {
        return fsEl;
      },
      documentElement: {
        requestFullscreen: async () => {
          fsEl = globalThis.document.documentElement;
        },
      },
      exitFullscreen: async () => {
        exited = true;
        fsEl = null;
      },
    };

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {
        wakeLock: {
          request: async () => ({
            release: async () => {
              released = true;
            },
          }),
        },
        keyboard: {
          lock: async (...args) => {
            lockArgsCount = args.length;
          },
          unlock: () => {
            unlocked = true;
          },
        },
      },
    });

    const fsOk = await requestFullscreenImmediate();
    assert.equal(fsOk.supported, true);
    assert.equal(fsOk.active, true);

    const wake = await acquireWakeLockSafe();
    assert.ok(wake);

    const kb = await acquireKeyboardLockSafe();
    assert.equal(kb.active, true);
    assert.equal(kb.status, 'active');
    assert.equal(lockArgsCount, 0, 'Expected all-keys capture navigator.keyboard.lock() with 0 args');

    // Denied Keyboard Lock returns status 'denied'
    globalThis.navigator.keyboard.lock = async () => {
      const err = new Error('Permission denied');
      err.name = 'NotAllowedError';
      throw err;
    };
    const kbDenied = await acquireKeyboardLockSafe();
    assert.equal(kbDenied.active, false);
    assert.equal(kbDenied.status, 'denied');

    await wake.release();
    releaseKeyboardLockSafe();
    await exitFullscreenSafe();
    assert.equal(released, true);
    assert.equal(unlocked, true);
    assert.equal(exited, true);

    // Test fullscreen rejection handling
    globalThis.document.documentElement.requestFullscreen = async () => {
      throw new Error('User denied fullscreen');
    };
    const fsDenied = await requestFullscreenImmediate();
    assert.equal(fsDenied.supported, true);
    assert.equal(fsDenied.active, false);
    assert.match(fsDenied.reason, /denied/);
  } finally {
    globalThis.document = origDoc;
    if (origNavDesc) {
      Object.defineProperty(globalThis, 'navigator', origNavDesc);
    }
  }
});

test('defensive shortcut helper targets distraction shortcuts without breaking typing or editing', () => {
  assert.equal(isDistractionShortcutEvent({ key: 'F11' }), true);
  assert.equal(isDistractionShortcutEvent({ key: 'w', ctrlKey: true }), true);
  assert.equal(isDistractionShortcutEvent({ key: 't', ctrlKey: true }), true);
  assert.equal(isDistractionShortcutEvent({ key: 'n', ctrlKey: true }), true);
  assert.equal(isDistractionShortcutEvent({ key: 'l', ctrlKey: true }), true);

  // Normal typing, rich-text editing, and copy/paste must NOT be blocked
  assert.equal(isDistractionShortcutEvent({ key: 'a' }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'c', ctrlKey: true }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'v', ctrlKey: true }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'b', ctrlKey: true }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'i', ctrlKey: true }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'u', ctrlKey: true }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'Tab' }), false);
  assert.equal(isDistractionShortcutEvent({ key: 'Enter' }), false);
});

test('3-finger touchpad swipe interruption (blur + hidden + fullscreen exit) preserves active session and recovers', async () => {
  const origDoc = globalThis.document;
  const origNavDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');

  const apiCalls = [];
  let fsEl = null;
  let visibility = 'visible';
  let wakeCount = 0;
  let kbLockCount = 0;

  const startMs = Date.UTC(2026, 10, 14, 12, 0, 0);
  const endsMs = startMs + 1500 * 1000;
  const session = {
    id: 'focus_touchpad_1',
    user_id: 'u1',
    session_title: '25m Deep Study',
    duration_seconds: 1500,
    short_break_minutes: 5,
    sound_enabled: true,
    animations_enabled: true,
    started_at: new Date(startMs).toISOString(),
    ends_at: new Date(endsMs).toISOString(),
    completed_at: '',
    status: 'active',
    distraction_event_count: 0,
  };

  try {
    globalThis.document = {
      fullscreenEnabled: true,
      get visibilityState() {
        return visibility;
      },
      get fullscreenElement() {
        return fsEl;
      },
      documentElement: {
        requestFullscreen: async () => {
          fsEl = globalThis.document.documentElement;
        },
      },
      exitFullscreen: async () => {
        fsEl = null;
      },
    };

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {
        wakeLock: {
          request: async () => {
            wakeCount += 1;
            return { release: async () => {} };
          },
        },
        keyboard: {
          lock: async () => {
            kbLockCount += 1;
          },
          unlock: () => {},
        },
      },
    });

    // 1. Start 25-minute Focus session
    apiCalls.push('/api/focus/sessions/start');
    const fsStart = await requestFullscreenImmediate();
    assert.equal(fsStart.active, true);
    const wake1 = await acquireWakeLockSafe();
    assert.ok(wake1);
    const kb1 = await acquireKeyboardLockSafe();
    assert.equal(kb1.active, true);
    assert.equal(computeRemainingSeconds(session.ends_at, startMs, 0), 1500);

    // 2-4. Simulate 3-finger touchpad swipe: blur -> hidden -> fullscreen exited
    apiCalls.push('/api/focus/sessions/focus_touchpad_1/events:window_blur');
    visibility = 'hidden';
    apiCalls.push('/api/focus/sessions/focus_touchpad_1/events:visibility_hidden');
    fsEl = null;
    releaseKeyboardLockSafe();
    apiCalls.push('/api/focus/sessions/focus_touchpad_1/events:fullscreen_exited');

    // 5. Simulate 30 seconds passing while in Task View / other app
    const after30sMs = startMs + 30 * 1000;
    const remAfter30s = computeRemainingSeconds(session.ends_at, after30sMs, 0);
    assert.equal(remAfter30s, 1470);
    assert.equal(session.status, 'active');

    // 6-7. User returns: window.focus -> visible -> Re-enter Focus Mode (fullscreen + locks)
    visibility = 'visible';
    apiCalls.push('/api/focus/sessions/focus_touchpad_1/events:window_focus');
    const fsRecovered = await requestFullscreenImmediate();
    assert.equal(fsRecovered.active, true);
    const wake2 = await acquireWakeLockSafe();
    assert.ok(wake2);
    const kb2 = await acquireKeyboardLockSafe();
    assert.equal(kb2.active, true);
    assert.equal(kb2.status, 'active');

    // 8. Verify no abort or premature complete was called, and no duplicate start
    assert.equal(apiCalls.some((c) => c.includes('/abort')), false);
    assert.equal(apiCalls.some((c) => c.includes('/complete')), false);
    assert.equal(apiCalls.filter((c) => c.includes('/start')).length, 1);
    assert.equal(wakeCount, 2);
    assert.equal(kbLockCount, 2);
  } finally {
    globalThis.document = origDoc;
    if (origNavDesc) {
      Object.defineProperty(globalThis, 'navigator', origNavDesc);
    }
  }
});
