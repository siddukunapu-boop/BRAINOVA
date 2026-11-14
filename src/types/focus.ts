export type FocusSessionStatus = 'active' | 'completed' | 'aborted';

export type FocusEventType =
  | 'visibility_hidden'
  | 'visibility_visible'
  | 'window_blur'
  | 'window_focus'
  | 'fullscreen_entered'
  | 'fullscreen_exited'
  | 'fullscreen_failed'
  | 'fullscreen_restored'
  | 'external_navigation_blocked'
  | 'keyboard_lock_failed'
  | 'capability_unavailable';

export interface FocusSession {
  id: string;
  user_id: string;
  session_title: string;
  duration_seconds: number;
  short_break_minutes: number;
  sound_enabled: boolean;
  animations_enabled: boolean;
  started_at: string;
  ends_at: string;
  completed_at: string;
  status: FocusSessionStatus;
  distraction_event_count: number;
  created_at: string;
  updated_at: string;
}

export interface FocusEventItem {
  id: string;
  session_id: string;
  user_id: string;
  event_type: FocusEventType;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface FocusConfig {
  durationMinutes: number;
  sessionTitle: string;
  shortBreakMinutes: number;
  soundEnabled: boolean;
  animationsEnabled: boolean;
}

export type FocusPhase = 'idle' | 'activating' | 'active' | 'completed';

export type FullscreenCapabilityStatus = 'active' | 'inactive' | 'unsupported' | 'failed';
export type KeyboardLockCapabilityStatus = 'active' | 'unsupported' | 'denied' | 'failed';
export type WakeLockCapabilityStatus = 'active' | 'unavailable' | 'released';

export interface FocusCapabilityState {
  fullscreenSupported: boolean;
  fullscreenActive: boolean;
  fullscreenStatus: FullscreenCapabilityStatus;
  fullscreenFailedReason: string;
  wakeLockSupported: boolean;
  wakeLockActive: boolean;
  wakeLockStatus: WakeLockCapabilityStatus;
  keyboardLockSupported: boolean;
  keyboardLockActive: boolean;
  keyboardLockStatus: KeyboardLockCapabilityStatus;
  keyboardLockErrorReason: string;
  visibilitySupported: boolean;
  navigationGuardActive: boolean;
}
