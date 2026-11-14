import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bell,
  Clock,
  Coffee,
  Eye,
  History,
  Info,
  Lock,
  Maximize2,
  Shield,
  ShieldCheck,
  Sparkles,
  Trash2,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useFocus } from '../context/FocusContext';
import { apiRequest } from '../services/api';
import type { FocusEventItem, FocusSession } from '../types/focus';
import { formatCountdown, formatDurationHuman } from '../lib/focusTimer';
import { TouchpadSetupFlowchart } from '../components/TouchpadSetupFlowchart';

const DURATION_PRESETS = [15, 25, 45, 60, 90] as const;
const BREAK_PRESETS = [0, 5, 10, 15] as const;

function formatDateTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatEventLabel(type: string): string {
  return type
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function getActualDurationSeconds(item: FocusSession): number | null {
  if (!item.started_at || !item.completed_at) return null;
  const start = Date.parse(item.started_at);
  const end = Date.parse(item.completed_at);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  return Math.round((end - start) / 1000);
}

export const FocusModePage: React.FC = () => {
  const {
    activeSession,
    history,
    loadingHistory,
    phase,
    remainingSeconds,
    progressPercent,
    capabilities,
    startFocus,
    reenterFullscreen,
    abortFocus,
    deleteHistorySession,
    clearAllHistory,
  } = useFocus();

  const [selectedPreset, setSelectedPreset] = useState<number | 'custom'>(25);
  const [customMinutes, setCustomMinutes] = useState<string>('30');
  const [sessionTitle, setSessionTitle] = useState<string>('');
  const [shortBreakMinutes, setShortBreakMinutes] = useState<number>(5);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [animationsEnabled, setAnimationsEnabled] = useState<boolean>(true);
  const [starting, setStarting] = useState<boolean>(false);

  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
  const [sessionEvents, setSessionEvents] = useState<Record<string, FocusEventItem[]>>({});
  const [loadingEventsId, setLoadingEventsId] = useState<string | null>(null);

  // Individual delete confirmation & error state
  const [deleteTarget, setDeleteTarget] = useState<FocusSession | null>(null);
  const [deletingSingle, setDeletingSingle] = useState<boolean>(false);
  const [deleteSingleError, setDeleteSingleError] = useState<string>('');

  // Clear All History confirmation & error state
  const [clearAllOpen, setClearAllOpen] = useState<boolean>(false);
  const [clearingAll, setClearingAll] = useState<boolean>(false);
  const [clearAllError, setClearAllError] = useState<string>('');

  const effectiveMinutes = useMemo(() => {
    if (selectedPreset !== 'custom') return selectedPreset;
    const parsed = Number(customMinutes);
    return Number.isFinite(parsed) ? Math.floor(parsed) : 0;
  }, [selectedPreset, customMinutes]);

  const durationError = useMemo(() => {
    if (selectedPreset !== 'custom') return '';
    if (!customMinutes.trim()) return 'Enter a custom duration in minutes.';
    const parsed = Number(customMinutes);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
      return 'Duration must be a whole number of minutes.';
    }
    if (parsed < 1 || parsed > 240) {
      return 'Custom duration must be between 1 and 240 minutes.';
    }
    return '';
  }, [selectedPreset, customMinutes]);

  const eligibleHistoryCount = useMemo(
    () => history.filter((item) => item.status !== 'active').length,
    [history]
  );

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (durationError || effectiveMinutes < 1 || effectiveMinutes > 240 || starting) return;
    setStarting(true);
    try {
      await startFocus({
        durationMinutes: effectiveMinutes,
        sessionTitle,
        shortBreakMinutes,
        soundEnabled,
        animationsEnabled,
      });
    } finally {
      setStarting(false);
    }
  };

  const handleToggleEvents = async (sessionId: string) => {
    if (expandedSessionId === sessionId) {
      setExpandedSessionId(null);
      return;
    }
    setExpandedSessionId(sessionId);
    if (!sessionEvents[sessionId]) {
      setLoadingEventsId(sessionId);
      try {
        const res = await apiRequest<{ events: FocusEventItem[] }>(
          `/api/focus/sessions/${sessionId}`
        );
        setSessionEvents((prev) => ({ ...prev, [sessionId]: res.events || [] }));
      } catch {
        setSessionEvents((prev) => ({ ...prev, [sessionId]: [] }));
      } finally {
        setLoadingEventsId(null);
      }
    }
  };

  const handleConfirmDeleteSingle = async () => {
    if (!deleteTarget || deletingSingle) return;
    setDeletingSingle(true);
    setDeleteSingleError('');
    try {
      await deleteHistorySession(deleteTarget.id);
      if (expandedSessionId === deleteTarget.id) {
        setExpandedSessionId(null);
      }
      setDeleteTarget(null);
    } catch (err: unknown) {
      setDeleteSingleError(
        err instanceof Error ? err.message : 'Unable to delete this focus session.'
      );
    } finally {
      setDeletingSingle(false);
    }
  };

  const handleConfirmClearAll = async () => {
    if (clearingAll) return;
    setClearingAll(true);
    setClearAllError('');
    try {
      await clearAllHistory();
      setExpandedSessionId(null);
      setClearAllOpen(false);
    } catch (err: unknown) {
      setClearAllError(
        err instanceof Error ? err.message : 'Unable to clear focus history.'
      );
    } finally {
      setClearingAll(false);
    }
  };

  const isActive = (phase === 'active' || phase === 'activating') && Boolean(activeSession);

  return (
    <div className="focus-page" data-testid="focus-mode-page">
      {/* Hero Header */}
      <header className="focus-hero-card">
        <div className="focus-hero-content">
          <div className="focus-hero-kicker">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>BRAINOVA STRICT FOCUS MODE</span>
          </div>
          <h1 className="focus-hero-title">Distraction-Protected Study Environment</h1>
          <p className="focus-hero-subtitle">
            Enter browser fullscreen with all-keys Keyboard Lock (where supported), external
            navigation guards, visibility monitoring, wake lock, and an authoritative backend timer
            — while keeping every BRAINOVA learning tool completely usable.
          </p>
        </div>
        <div className="focus-hero-caps" aria-label="Browser capability readiness">
          <div className="focus-cap-badge">
            <Maximize2 size={14} aria-hidden="true" />
            <span>Fullscreen: {capabilities.fullscreenSupported ? 'Supported' : 'Unsupported'}</span>
          </div>
          <div className="focus-cap-badge">
            <Eye size={14} aria-hidden="true" />
            <span>Visibility Monitor: {capabilities.visibilitySupported ? 'Ready' : 'Unavailable'}</span>
          </div>
          <div className="focus-cap-badge">
            <Bell size={14} aria-hidden="true" />
            <span>Wake Lock: {capabilities.wakeLockSupported ? 'Supported' : 'Unavailable'}</span>
          </div>
          <div className="focus-cap-badge">
            <Lock size={14} aria-hidden="true" />
            <span>
              All-Keys Lock: {capabilities.keyboardLockSupported ? 'Supported' : 'Unsupported'}
            </span>
          </div>
        </div>
      </header>

      <div className="focus-main-grid">
        {/* Left Column: Configurator OR Live Session Panel */}
        <section className="focus-panel" aria-label="Focus Session Controls">
          {isActive && activeSession ? (
            <div className="focus-live-panel">
              <div className="focus-live-header">
                <span className="focus-active-pill">
                  <span className="focus-pulse-dot" aria-hidden="true" />
                  <span>Session In Progress</span>
                </span>
                <span className="focus-live-events">
                  Distraction events: <strong>{activeSession.distraction_event_count}</strong>
                </span>
              </div>

              <h2 className="focus-live-title">
                {activeSession.session_title || 'Strict Focus Session'}
              </h2>

              <div className="focus-live-timer-box">
                <div className="focus-live-timer">{formatCountdown(remainingSeconds)}</div>
                <div className="focus-live-progress-bar" aria-hidden="true">
                  <div
                    className="focus-live-progress-fill"
                    style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
                  />
                </div>
                <div className="focus-live-meta">
                  <span>Duration: {formatDurationHuman(activeSession.duration_seconds)}</span>
                  <span>Ends at {formatDateTime(activeSession.ends_at)}</span>
                </div>
              </div>

              <div className="focus-workspace-links">
                <div className="focus-workspace-links-label">
                  Continue studying anywhere in BRAINOVA:
                </div>
                <div className="focus-quick-routes">
                  <Link to="/dashboard" className="btn btn-secondary btn-sm">
                    Dashboard
                  </Link>
                  <Link to="/roadmaps" className="btn btn-secondary btn-sm">
                    AI Roadmaps
                  </Link>
                  <Link to="/resources" className="btn btn-secondary btn-sm">
                    Reading Materials
                  </Link>
                  <Link to="/diary" className="btn btn-secondary btn-sm">
                    Personal Diary
                  </Link>
                  <Link to="/study-journal" className="btn btn-secondary btn-sm">
                    Study Journal
                  </Link>
                </div>
              </div>

              <div className="focus-live-actions">
                {!capabilities.fullscreenActive && capabilities.fullscreenSupported && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => reenterFullscreen()}
                  >
                    <Maximize2 size={16} aria-hidden="true" />
                    <span>Re-enter Focus Mode</span>
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => abortFocus()}
                >
                  End Focus Session
                </button>
              </div>
            </div>
          ) : (
            <form className="focus-config-form" onSubmit={handleStart}>
              <h2 className="focus-panel-heading">
                <Shield size={18} aria-hidden="true" />
                <span>Configure Focus Session</span>
              </h2>

              {/* Study Intention */}
              <div className="focus-field">
                <label htmlFor="focus-session-title" className="focus-label">
                  Study Intention / Session Title <span className="focus-optional">(optional)</span>
                </label>
                <input
                  id="focus-session-title"
                  type="text"
                  className="form-input focus-control-input"
                  maxLength={120}
                  placeholder="e.g., Distributed Systems — Raft Consensus Notes"
                  value={sessionTitle}
                  onChange={(e) => setSessionTitle(e.target.value)}
                />
              </div>

              {/* Duration Presets */}
              <div className="focus-field">
                <span className="focus-label">Focus Duration</span>
                <div className="focus-preset-grid" role="group" aria-label="Focus duration presets">
                  {DURATION_PRESETS.map((mins) => (
                    <button
                      key={mins}
                      type="button"
                      className={`focus-preset-btn ${selectedPreset === mins ? 'active' : ''}`}
                      onClick={() => setSelectedPreset(mins)}
                    >
                      {mins} min
                    </button>
                  ))}
                  <button
                    type="button"
                    className={`focus-preset-btn ${selectedPreset === 'custom' ? 'active' : ''}`}
                    onClick={() => setSelectedPreset('custom')}
                  >
                    Custom
                  </button>
                </div>

                {selectedPreset === 'custom' && (
                  <div className="focus-custom-row">
                    <label htmlFor="focus-custom-minutes" className="sr-only">
                      Custom duration in minutes
                    </label>
                    <input
                      id="focus-custom-minutes"
                      type="number"
                      min={1}
                      max={240}
                      step={1}
                      className="form-input focus-control-input focus-custom-input"
                      value={customMinutes}
                      onChange={(e) => setCustomMinutes(e.target.value)}
                      placeholder="1 - 240"
                    />
                    <span className="focus-custom-unit">minutes (1 – 240)</span>
                  </div>
                )}
                {durationError && (
                  <div className="focus-field-error" role="alert">
                    {durationError}
                  </div>
                )}
              </div>

              {/* Short Break */}
              <div className="focus-field">
                <span className="focus-label">
                  <Coffee size={14} aria-hidden="true" /> Planned Short Break After Session
                </span>
                <div className="focus-break-row" role="group" aria-label="Short break options">
                  {BREAK_PRESETS.map((mins) => (
                    <button
                      key={mins}
                      type="button"
                      className={`focus-chip-btn ${shortBreakMinutes === mins ? 'active' : ''}`}
                      onClick={() => setShortBreakMinutes(mins)}
                    >
                      {mins === 0 ? 'No break' : `${mins} min break`}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sound & Animation Preferences */}
              <div className="focus-toggles-row">
                <button
                  type="button"
                  className={`focus-toggle-card ${soundEnabled ? 'active' : ''}`}
                  onClick={() => setSoundEnabled((s) => !s)}
                  aria-pressed={soundEnabled}
                >
                  {soundEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}
                  <div>
                    <div className="focus-toggle-title">Chime Sounds</div>
                    <div className="focus-toggle-sub">{soundEnabled ? 'Enabled' : 'Muted'}</div>
                  </div>
                </button>

                <button
                  type="button"
                  className={`focus-toggle-card ${animationsEnabled ? 'active' : ''}`}
                  onClick={() => setAnimationsEnabled((a) => !a)}
                  aria-pressed={animationsEnabled}
                >
                  <Sparkles size={17} />
                  <div>
                    <div className="focus-toggle-title">Transitions</div>
                    <div className="focus-toggle-sub">
                      {animationsEnabled ? 'Smooth animations' : 'Minimal'}
                    </div>
                  </div>
                </button>
              </div>

              {/* Pre-start Summary */}
              <div className="focus-summary-box">
                <div className="focus-summary-title">Session Summary</div>
                <div className="focus-summary-grid">
                  <div>
                    <span>Duration</span>
                    <strong>{durationError ? '—' : `${effectiveMinutes} minutes`}</strong>
                  </div>
                  <div>
                    <span>Break</span>
                    <strong>{shortBreakMinutes === 0 ? 'None' : `${shortBreakMinutes} min`}</strong>
                  </div>
                  <div>
                    <span>Fullscreen</span>
                    <strong>
                      {capabilities.fullscreenSupported ? 'Requested on start' : 'Unsupported'}
                    </strong>
                  </div>
                  <div>
                    <span>Keyboard Capture</span>
                    <strong>
                      {capabilities.keyboardLockSupported
                        ? 'All-keys lock requested'
                        : 'Unsupported in browser'}
                    </strong>
                  </div>
                </div>
              </div>

              {!capabilities.keyboardLockSupported && (
                <div className="focus-honest-note">
                  <Info size={15} aria-hidden="true" />
                  <span>
                    All-keys Keyboard Lock is not supported in this browser. Browser shortcuts and
                    OS shortcuts remain under browser/OS control.
                  </span>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary focus-start-btn"
                disabled={Boolean(durationError) || starting}
                data-testid="start-focus-btn"
              >
                <ShieldCheck size={18} aria-hidden="true" />
                <span>{starting ? 'Starting Focus...' : 'Start Focus'}</span>
              </button>
            </form>
          )}
        </section>

        {/* Right Column: Cinematic Touchpad Setup Flowchart + History */}
        <div className="focus-side-col">
          <TouchpadSetupFlowchart />

          <section className="focus-panel" aria-label="Focus Session History">
            <div className="focus-history-header">
              <div className="focus-history-title-row">
                <h2 className="focus-panel-heading">
                  <History size={18} aria-hidden="true" />
                  <span>Focus History</span>
                </h2>
                <span className="focus-history-count" data-testid="focus-history-count">
                  {history.length} {history.length === 1 ? 'session' : 'sessions'}
                </span>
              </div>
              {eligibleHistoryCount > 0 && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm focus-clear-history-btn"
                  onClick={() => {
                    setClearAllError('');
                    setClearAllOpen(true);
                  }}
                  data-testid="clear-all-history-btn"
                >
                  <Trash2 size={14} aria-hidden="true" />
                  <span>Clear All History</span>
                </button>
              )}
            </div>

            {loadingHistory ? (
              <div className="focus-empty-history">Loading Focus history...</div>
            ) : history.length === 0 ? (
              <div className="focus-empty-history" data-testid="focus-history-empty">
                No Focus sessions recorded yet. Configure a session and click Start Focus to begin.
              </div>
            ) : (
              <div className="focus-history-list">
                {history.map((item) => {
                  const isExpanded = expandedSessionId === item.id;
                  const events = sessionEvents[item.id] || [];
                  const actualSecs = getActualDurationSeconds(item);
                  const canDelete = item.status !== 'active';
                  return (
                    <div key={item.id} className="focus-history-card">
                      <div className="focus-history-top">
                        <div className="focus-history-title-wrap">
                          <div className="focus-history-title">
                            {item.session_title || 'Strict Focus Session'}
                          </div>
                          <div className="focus-history-meta">
                            <span>
                              <Clock size={12} aria-hidden="true" />{' '}
                              {formatDurationHuman(item.duration_seconds)}
                              {actualSecs !== null && item.status === 'aborted'
                                ? ` (${formatDurationHuman(actualSecs)} actual)`
                                : ''}
                            </span>
                            <span>{formatDateTime(item.started_at)}</span>
                          </div>
                        </div>
                        <div className="focus-history-right-actions">
                          <span className={`focus-status-tag ${item.status}`}>{item.status}</span>
                          {canDelete && (
                            <button
                              type="button"
                              className="focus-icon-delete-btn"
                              title="Delete session"
                              aria-label={`Delete ${item.session_title || 'Strict Focus Session'}`}
                              onClick={() => {
                                setDeleteSingleError('');
                                setDeleteTarget(item);
                              }}
                              data-testid={`delete-session-${item.id}`}
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="focus-history-footer">
                        <span className="focus-history-events-count">
                          <Activity size={13} aria-hidden="true" /> {item.distraction_event_count}{' '}
                          distraction {item.distraction_event_count === 1 ? 'event' : 'events'}
                        </span>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleToggleEvents(item.id)}
                        >
                          {isExpanded ? 'Hide Log' : 'View Log'}
                        </button>
                      </div>

                      {isExpanded && (
                        <div className="focus-event-log">
                          {loadingEventsId === item.id ? (
                            <div className="focus-event-empty">Loading events...</div>
                          ) : events.length === 0 ? (
                            <div className="focus-event-empty">
                              No distraction or capability events logged.
                            </div>
                          ) : (
                            events.map((evt) => (
                              <div key={evt.id} className="focus-event-row">
                                <span>{formatEventLabel(evt.event_type)}</span>
                                <span className="focus-event-time">
                                  {formatDateTime(evt.occurred_at)}
                                </span>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Individual Delete Confirmation Dialog */}
      {deleteTarget && (
        <div
          className="focus-modal-backdrop"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="focus-delete-single-title"
          data-testid="delete-single-dialog"
        >
          <div className="focus-modal-card">
            <div className="focus-modal-icon warn">
              <Trash2 size={24} aria-hidden="true" />
            </div>
            <h3 id="focus-delete-single-title" className="focus-modal-title">
              Delete Focus Session?
            </h3>
            <p className="focus-modal-desc">
              Are you sure you want to permanently delete{' '}
              <strong>{deleteTarget.session_title || 'Strict Focus Session'}</strong> (
              {formatDateTime(deleteTarget.started_at)}) from your history? This action cannot be
              undone.
            </p>
            {deleteSingleError && (
              <div className="focus-honest-note" role="alert">
                <AlertTriangle size={15} aria-hidden="true" />
                <span>{deleteSingleError}</span>
              </div>
            )}
            <div className="focus-modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={deletingSingle}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={deletingSingle}
                onClick={handleConfirmDeleteSingle}
                data-testid="confirm-delete-single-btn"
              >
                {deletingSingle ? 'Deleting...' : deleteSingleError ? 'Retry Delete' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clear All History Confirmation Dialog */}
      {clearAllOpen && (
        <div
          className="focus-modal-backdrop"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="focus-clear-all-title"
          data-testid="clear-all-dialog"
        >
          <div className="focus-modal-card">
            <div className="focus-modal-icon warn">
              <Trash2 size={24} aria-hidden="true" />
            </div>
            <h3 id="focus-clear-all-title" className="focus-modal-title">
              Clear All Focus History?
            </h3>
            <p className="focus-modal-desc">
              This will permanently delete all {eligibleHistoryCount} completed and aborted focus{' '}
              {eligibleHistoryCount === 1 ? 'session' : 'sessions'} and their event logs from your
              account. This action cannot be undone.
            </p>
            {activeSession && (
              <div className="focus-honest-note">
                <Info size={15} aria-hidden="true" />
                <span>
                  Your currently active Focus session will be preserved and cannot be removed
                  through history cleanup.
                </span>
              </div>
            )}
            {clearAllError && (
              <div className="focus-honest-note" role="alert">
                <AlertTriangle size={15} aria-hidden="true" />
                <span>{clearAllError}</span>
              </div>
            )}
            <div className="focus-modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={clearingAll}
                onClick={() => setClearAllOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={clearingAll}
                onClick={handleConfirmClearAll}
                data-testid="confirm-clear-all-btn"
              >
                {clearingAll
                  ? 'Clearing...'
                  : clearAllError
                  ? 'Retry Clear All'
                  : 'Clear All History'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
