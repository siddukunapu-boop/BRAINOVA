import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Maximize2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { useFocus } from '../context/FocusContext';
import { formatCountdown, formatDurationHuman } from '../lib/focusTimer';

function formatLocalTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function capLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export const FocusStatusBar: React.FC = () => {
  const {
    activeSession,
    phase,
    remainingSeconds,
    progressPercent,
    capabilities,
    blockedNavNotice,
    offlineSyncPending,
    reenterFullscreen,
    dismissBlockedNotice,
    abortFocus,
  } = useFocus();

  const [confirmEnd, setConfirmEnd] = useState(false);

  const srAnnouncement = useMemo(() => {
    if (phase !== 'active' || !activeSession) return '';
    if (remainingSeconds === 300) return '5 minutes remaining in Focus session.';
    if (remainingSeconds === 60) return '1 minute remaining in Focus session.';
    if (remainingSeconds === 10) return '10 seconds remaining in Focus session.';
    return '';
  }, [phase, activeSession, remainingSeconds]);

  if ((phase !== 'active' && phase !== 'activating') || !activeSession) {
    return null;
  }

  const title = activeSession.session_title || 'Strict Focus Session';
  const formattedTime = formatCountdown(remainingSeconds);

  return (
    <section
      className="focus-status-dock"
      aria-label="Active Focus Session Status"
      data-testid="focus-status-bar"
    >
      <div className="focus-status-progress-track" aria-hidden="true">
        <div
          className="focus-status-progress-fill"
          style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
        />
      </div>

      <div className="focus-status-inner">
        <div className="focus-status-left">
          <div className="focus-active-pill">
            <span className="focus-pulse-dot" aria-hidden="true" />
            <ShieldCheck size={15} aria-hidden="true" />
            <span>Focus Active</span>
          </div>
          <div className="focus-status-title" title={title}>
            {title}
          </div>
          {offlineSyncPending && (
            <span className="focus-cap-chip warn" title="Events queued locally while offline">
              Offline Sync Pending
            </span>
          )}
        </div>

        <div className="focus-status-center">
          <div
            className="focus-countdown-display"
            aria-label={`Remaining time ${formattedTime}`}
          >
            <Clock size={16} aria-hidden="true" />
            <span>{formattedTime}</span>
          </div>
          <div className="focus-cap-row" aria-label="Browser Protection Capabilities">
            <span
              className={`focus-cap-chip ${
                capabilities.fullscreenStatus === 'active'
                  ? 'ok'
                  : capabilities.fullscreenStatus === 'failed'
                  ? 'warn'
                  : 'muted'
              }`}
              title={
                capabilities.fullscreenFailedReason ||
                `Fullscreen: ${capLabel(capabilities.fullscreenStatus)}`
              }
            >
              Fullscreen: {capLabel(capabilities.fullscreenStatus)}
            </span>
            <span
              className={`focus-cap-chip ${
                capabilities.wakeLockStatus === 'active' ? 'ok' : 'muted'
              }`}
            >
              Wake Lock: {capLabel(capabilities.wakeLockStatus)}
            </span>
            <span
              className={`focus-cap-chip ${
                capabilities.keyboardLockStatus === 'active'
                  ? 'ok'
                  : capabilities.keyboardLockStatus === 'denied'
                  ? 'warn'
                  : 'muted'
              }`}
              title={
                capabilities.keyboardLockErrorReason ||
                `Keyboard Lock: ${capLabel(capabilities.keyboardLockStatus)}`
              }
            >
              Key Lock: {capLabel(capabilities.keyboardLockStatus)}
            </span>
            <span className="focus-cap-chip ok">Nav Guard: Active</span>
            <span
              className={`focus-cap-chip ${
                activeSession.distraction_event_count > 0 ? 'warn' : 'muted'
              }`}
              title="Recorded visibility, fullscreen exit, or blocked external link events"
            >
              Events: {activeSession.distraction_event_count}
            </span>
          </div>
        </div>

        <div className="focus-status-actions">
          {!capabilities.fullscreenActive && capabilities.fullscreenSupported && (
            <button
              type="button"
              className="focus-mini-btn focus-mini-btn-accent"
              onClick={() => reenterFullscreen()}
            >
              <Maximize2 size={14} aria-hidden="true" />
              <span>Re-enter Focus</span>
            </button>
          )}
          {!confirmEnd ? (
            <button
              type="button"
              className="focus-mini-btn focus-mini-btn-danger"
              onClick={() => setConfirmEnd(true)}
            >
              <X size={14} aria-hidden="true" />
              <span>End</span>
            </button>
          ) : (
            <div className="focus-confirm-inline">
              <button
                type="button"
                className="focus-mini-btn focus-mini-btn-danger"
                onClick={() => {
                  setConfirmEnd(false);
                  abortFocus();
                }}
              >
                Confirm End
              </button>
              <button
                type="button"
                className="focus-mini-btn"
                onClick={() => setConfirmEnd(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {blockedNavNotice && (
        <div className="focus-inline-notice" role="status">
          <ExternalLink size={14} aria-hidden="true" />
          <span>{blockedNavNotice}</span>
          <button
            type="button"
            className="focus-notice-close"
            onClick={dismissBlockedNotice}
            aria-label="Dismiss blocked navigation notice"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="sr-only" aria-live="polite">
        {srAnnouncement}
      </div>
    </section>
  );
};

export const FocusModalsOverlay: React.FC = () => {
  const navigate = useNavigate();
  const {
    activeSession,
    completedSession,
    phase,
    remainingSeconds,
    capabilities,
    fullscreenExitWarning,
    reenterFullscreen,
    dismissFullscreenWarning,
    dismissCompletedModal,
    abortFocus,
  } = useFocus();

  return (
    <>
      {/* 1. Focus Activation Animation */}
      {phase === 'activating' && activeSession && (
        <div
          className="focus-activation-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Activating Strict Focus Mode"
        >
          <div className="focus-activation-card">
            <div className="focus-shield-emblem">
              <Shield size={40} aria-hidden="true" />
            </div>
            <div className="focus-activation-kicker">STRICT FOCUS MODE</div>
            <h2 className="focus-activation-title">
              {activeSession.session_title || 'Deep Study Session'}
            </h2>
            <div className="focus-activation-timer">{formatCountdown(remainingSeconds)}</div>
            <p className="focus-activation-sub">
              Browser guard active · All BRAINOVA tools ready
            </p>
          </div>
        </div>
      )}

      {/* 2. Fullscreen Exit Recovery Interface */}
      {phase === 'active' && fullscreenExitWarning && (
        <div
          className="focus-modal-backdrop"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="focus-fs-warn-title"
          data-testid="focus-recovery-modal"
        >
          <div className="focus-modal-card focus-warning-card">
            <div className="focus-modal-icon warn">
              <ShieldAlert size={28} aria-hidden="true" />
            </div>
            <h3 id="focus-fs-warn-title" className="focus-modal-title">
              Fullscreen Mode Interrupted
            </h3>
            <p className="focus-modal-desc">
              Your Focus session is still active and your server timer has been preserved.
              Re-enter fullscreen to restore browser keyboard capture and distraction protection.
            </p>

            <div className="focus-stats-grid">
              <div className="focus-stat-box">
                <span className="focus-stat-label">Remaining Time</span>
                <span className="focus-stat-value">{formatCountdown(remainingSeconds)}</span>
              </div>
              <div className="focus-stat-box">
                <span className="focus-stat-label">Keyboard Lock</span>
                <span className="focus-stat-value">
                  {capLabel(capabilities.keyboardLockStatus)}
                </span>
              </div>
            </div>

            {capabilities.fullscreenFailedReason && (
              <div className="focus-honest-note" role="alert">
                <AlertTriangle size={15} aria-hidden="true" />
                <span>Fullscreen error: {capabilities.fullscreenFailedReason}</span>
              </div>
            )}

            <div className="focus-modal-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => reenterFullscreen()}
                data-testid="reenter-focus-btn"
              >
                <Maximize2 size={16} aria-hidden="true" />
                <span>
                  {capabilities.fullscreenFailedReason
                    ? 'Retry Fullscreen'
                    : 'Re-enter Focus Mode'}
                </span>
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={dismissFullscreenWarning}
              >
                Continue Without Fullscreen
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => abortFocus()}>
                End Session
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Session Completion Experience */}
      {phase === 'completed' && completedSession && (
        <div
          className="focus-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="focus-complete-title"
        >
          <div className="focus-modal-card focus-complete-card">
            <div className="focus-modal-icon success">
              <CheckCircle2 size={32} aria-hidden="true" />
            </div>
            <div className="focus-complete-badge">
              <Sparkles size={14} aria-hidden="true" />
              <span>Focus Session Complete</span>
            </div>
            <h2 id="focus-complete-title" className="focus-modal-title">
              {completedSession.session_title || 'Strict Focus Session'}
            </h2>
            <p className="focus-modal-desc">
              Browser locks have been released and normal BRAINOVA navigation is restored.
            </p>

            <div className="focus-stats-grid">
              <div className="focus-stat-box">
                <span className="focus-stat-label">Total Duration</span>
                <span className="focus-stat-value">
                  {formatDurationHuman(completedSession.duration_seconds)}
                </span>
              </div>
              <div className="focus-stat-box">
                <span className="focus-stat-label">Status</span>
                <span className="focus-stat-value capitalize">{completedSession.status}</span>
              </div>
              <div className="focus-stat-box">
                <span className="focus-stat-label">Distraction Events</span>
                <span className="focus-stat-value">
                  {completedSession.distraction_event_count}
                </span>
              </div>
              <div className="focus-stat-box">
                <span className="focus-stat-label">Window</span>
                <span className="focus-stat-value">
                  {formatLocalTime(completedSession.started_at)} –{' '}
                  {formatLocalTime(completedSession.completed_at || completedSession.ends_at)}
                </span>
              </div>
            </div>

            {completedSession.distraction_event_count > 0 && (
              <div className="focus-honest-note">
                <AlertTriangle size={15} aria-hidden="true" />
                <span>
                  {completedSession.distraction_event_count} focus interruption{' '}
                  {completedSession.distraction_event_count === 1 ? 'event was' : 'events were'}{' '}
                  recorded during this session.
                </span>
              </div>
            )}

            <div className="focus-modal-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  dismissCompletedModal();
                  navigate('/focus');
                }}
              >
                View Focus History
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={dismissCompletedModal}
              >
                Return to Workspace
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
