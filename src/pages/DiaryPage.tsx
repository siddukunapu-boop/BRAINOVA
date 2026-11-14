import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Plus,
  Save,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  Lock,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';
import { SharedNotebookCover, SharedNotebookOpeningFlap } from '../components/NotebookCover';
import '../styles/diary.css';

interface DiaryEntry {
  id: string;
  user_id: string;
  title: string;
  entry_date: string;
  pages: string[];
  page_count: number;
  preview: string;
  is_draft: boolean;
  client_draft_key: string;
  created_at: string;
  updated_at: string;
}

function getTodayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatDiaryDate(isoDate: string): string {
  const parts = (isoDate || '').slice(0, 10).split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return isoDate;
  }
  const dt = new Date(parts[0], parts[1] - 1, parts[2]);
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(dt);
}

function newDraftKey(): string {
  return `draft_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ||
    document.documentElement.classList.contains('reduced-motion')
  );
}

export const DiaryPage: React.FC = () => {
  const { user, addToast } = useApp();
  const displayName = typeof user?.name === 'string' ? user.name.trim() : '';
  const diaryPlaceholder = displayName
    ? `Dear ${displayName}, write your thoughts here...`
    : 'Dear Diary, write your thoughts here...';

  // Notebook open / animation state
  const [isNotebookOpen, setIsNotebookOpen] = useState(false);
  const [isOpeningAnim, setIsOpeningAnim] = useState(false);
  const [turnDirection, setTurnDirection] = useState<'next' | 'prev' | null>(null);

  // Active entry state
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);
  const [activeIsDraft, setActiveIsDraft] = useState<boolean>(true);
  const [clientDraftKey, setClientDraftKey] = useState<string>(() => newDraftKey());
  const [title, setTitle] = useState('');
  const [entryDate, setEntryDate] = useState<string>(() => getTodayIsoDate());
  const [pages, setPages] = useState<string[]>(['']);
  const [currentPageIdx, setCurrentPageIdx] = useState(0);

  // Persistence & library state
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [loadingLibrary, setLoadingLibrary] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [savingExplicit, setSavingExplicit] = useState(false);
  const [deletingEntry, setDeletingEntry] = useState<DiaryEntry | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  const dirtyRef = useRef(false);
  const saveSeqRef = useRef(0);
  const autosaveTimerRef = useRef<number | null>(null);
  const latestStateRef = useRef({
    activeEntryId,
    activeIsDraft,
    clientDraftKey,
    title,
    entryDate,
    pages,
  });

  useEffect(() => {
    latestStateRef.current = {
      activeEntryId,
      activeIsDraft,
      clientDraftKey,
      title,
      entryDate,
      pages,
    };
  }, [activeEntryId, activeIsDraft, clientDraftKey, title, entryDate, pages]);

  const loadDiaryData = useCallback(async (restoreDraftIfIdle: boolean) => {
    setLoadingLibrary(true);
    try {
      const [listRes, draftRes] = await Promise.all([
        apiRequest<{ entries: DiaryEntry[] }>('/api/diary'),
        restoreDraftIfIdle
          ? apiRequest<{ draft: DiaryEntry | null }>('/api/diary/draft')
          : Promise.resolve({ draft: null }),
      ]);
      setEntries(listRes.entries || []);
      if (restoreDraftIfIdle && draftRes.draft) {
        const d = draftRes.draft;
        setActiveEntryId(d.id);
        setActiveIsDraft(true);
        setClientDraftKey(d.client_draft_key || newDraftKey());
        setTitle(d.title || '');
        setEntryDate(d.entry_date || getTodayIsoDate());
        setPages(d.pages && d.pages.length > 0 ? d.pages : ['']);
        setCurrentPageIdx(0);
        dirtyRef.current = false;
        setSaveStatus('saved');
      }
    } catch (err: any) {
      addToast(err.message || 'Could not load diary entries.', 'error');
    } finally {
      setLoadingLibrary(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadDiaryData(true);
  }, [loadDiaryData]);

  const persistToBackend = useCallback(
    async (explicitSave: boolean): Promise<boolean> => {
      const snap = latestStateRef.current;
      const hasAnyContent = Boolean(snap.title.trim()) || snap.pages.some((p) => p.trim());
      if (!hasAnyContent) {
        if (explicitSave) {
          addToast('Please write a title or some diary content before saving.', 'error');
        }
        return false;
      }

      const seq = ++saveSeqRef.current;
      const targetIsDraft = explicitSave ? false : snap.activeIsDraft;

      if (explicitSave) {
        setSavingExplicit(true);
      } else {
        setSaveStatus('saving');
      }

      try {
        let saved: DiaryEntry;
        if (snap.activeEntryId) {
          const res = await apiRequest<{ entry: DiaryEntry }>(
            `/api/diary/${snap.activeEntryId}`,
            {
              method: 'PUT',
              body: JSON.stringify({
                title: snap.title,
                pages: snap.pages,
                is_draft: targetIsDraft,
              }),
            }
          );
          saved = res.entry;
        } else {
          const res = await apiRequest<{ entry: DiaryEntry }>('/api/diary', {
            method: 'POST',
            body: JSON.stringify({
              title: snap.title,
              entry_date: snap.entryDate,
              pages: snap.pages,
              is_draft: targetIsDraft,
              client_draft_key: snap.clientDraftKey,
            }),
          });
          saved = res.entry;
        }

        if (seq === saveSeqRef.current) {
          setActiveEntryId(saved.id);
          setActiveIsDraft(saved.is_draft);
          setEntryDate(saved.entry_date);
          dirtyRef.current = false;
          setSaveStatus('saved');
        }

        const listRes = await apiRequest<{ entries: DiaryEntry[] }>('/api/diary');
        setEntries(listRes.entries || []);

        if (explicitSave) {
          addToast('Diary entry saved!', 'success');
        }
        return true;
      } catch (err: any) {
        if (seq === saveSeqRef.current) {
          setSaveStatus('error');
        }
        if (explicitSave) {
          addToast(err.message || 'Failed to save diary entry.', 'error');
        }
        return false;
      } finally {
        if (explicitSave) {
          setSavingExplicit(false);
        }
      }
    },
    [addToast]
  );

  // Debounced autosave whenever title or pages change
  useEffect(() => {
    if (!dirtyRef.current) return;
    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current);
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      persistToBackend(false);
    }, 900);

    return () => {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current);
      }
    };
  }, [title, pages, persistToBackend]);

  // Flush pending draft when navigating away
  useEffect(() => {
    return () => {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current);
      }
      if (dirtyRef.current) {
        persistToBackend(false);
      }
    };
  }, [persistToBackend]);

  const handleOpenNotebook = () => {
    if (isNotebookOpen) return;
    setIsNotebookOpen(true);
    if (!prefersReducedMotion()) {
      setIsOpeningAnim(true);
      window.setTimeout(() => setIsOpeningAnim(false), 980);
    }
  };

  const handleStartNewEntry = async () => {
    if (dirtyRef.current) {
      await persistToBackend(false);
    }
    setActiveEntryId(null);
    setActiveIsDraft(true);
    setClientDraftKey(newDraftKey());
    setTitle('');
    setEntryDate(getTodayIsoDate());
    setPages(['']);
    setCurrentPageIdx(0);
    dirtyRef.current = false;
    setSaveStatus('idle');
    handleOpenNotebook();
  };

  const handleOpenSavedEntry = async (entry: DiaryEntry) => {
    if (dirtyRef.current && activeEntryId !== entry.id) {
      await persistToBackend(false);
    }
    try {
      const res = await apiRequest<{ entry: DiaryEntry }>(`/api/diary/${entry.id}`);
      const full = res.entry;
      setActiveEntryId(full.id);
      setActiveIsDraft(full.is_draft);
      setClientDraftKey(full.client_draft_key || newDraftKey());
      setTitle(full.title || '');
      setEntryDate(full.entry_date);
      setPages(full.pages && full.pages.length > 0 ? full.pages : ['']);
      setCurrentPageIdx(0);
      dirtyRef.current = false;
      setSaveStatus('saved');
      handleOpenNotebook();
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    } catch (err: any) {
      addToast(err.message || 'Could not open diary entry.', 'error');
    }
  };

  const handlePageTextChange = (text: string) => {
    dirtyRef.current = true;
    setSaveStatus('idle');
    setPages((prev) => {
      const next = [...prev];
      next[currentPageIdx] = text;
      return next;
    });
  };

  const handleTitleChange = (val: string) => {
    dirtyRef.current = true;
    setSaveStatus('idle');
    setTitle(val);
  };

  const handleTurnPage = (dir: 'next' | 'prev') => {
    if (turnDirection !== null) return;
    if (dir === 'prev' && currentPageIdx === 0) return;

    const reduced = prefersReducedMotion();
    const applyPageSwitch = () => {
      if (dir === 'next') {
        setPages((prev) => {
          if (currentPageIdx === prev.length - 1) {
            return [...prev, ''];
          }
          return prev;
        });
        setCurrentPageIdx((idx) => idx + 1);
      } else {
        setCurrentPageIdx((idx) => Math.max(0, idx - 1));
      }
    };

    if (reduced) {
      applyPageSwitch();
      return;
    }

    setTurnDirection(dir);
    window.setTimeout(() => {
      applyPageSwitch();
    }, 180);
    window.setTimeout(() => {
      setTurnDirection(null);
    }, 1150);
  };

  const handleConfirmDelete = async () => {
    if (!deletingEntry) return;
    setDeletingBusy(true);
    try {
      await apiRequest(`/api/diary/${deletingEntry.id}`, { method: 'DELETE' });
      setEntries((prev) => prev.filter((e) => e.id !== deletingEntry.id));
      if (activeEntryId === deletingEntry.id) {
        setActiveEntryId(null);
        setActiveIsDraft(true);
        setClientDraftKey(newDraftKey());
        setTitle('');
        setEntryDate(getTodayIsoDate());
        setPages(['']);
        setCurrentPageIdx(0);
        dirtyRef.current = false;
        setSaveStatus('idle');
      }
      setDeletingEntry(null);
      addToast('Diary entry deleted.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Failed to delete diary entry.', 'error');
    } finally {
      setDeletingBusy(false);
    }
  };

  const isTurning = turnDirection !== null;

  return (
    <div className="diary-workspace">
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <div>
          <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
            Personal Diary
          </span>
          <h1 style={{ fontSize: '1.65rem', marginBottom: '4px' }}>
            My Personal Diary
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
            A quiet, private ruled notebook for daily reflections — safely saved to your account.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleStartNewEntry}
          >
            <Plus size={15} />
            <span>New Entry</span>
          </button>
          {isNotebookOpen && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setIsNotebookOpen(false)}
            >
              <Lock size={14} />
              <span>Close Diary</span>
            </button>
          )}
        </div>
      </div>

      {/* Physical Notebook Stage */}
      <section className="diary-stage" aria-label="Personal Diary Notebook">
        {!isNotebookOpen ? (
          <SharedNotebookCover
            idPrefix="diary"
            badge="BRAINOVA • PRIVATE EDITION"
            title="Personal Diary"
            subtitle={
              activeEntryId && title
                ? `Resume: "${title}" (${formatDiaryDate(entryDate)})`
                : `${formatDiaryDate(entryDate)} — Tap to open your ruled notebook`
            }
            ariaLabel="Open Personal Diary Notebook"
            onOpen={handleOpenNotebook}
          />
        ) : (
          <>
            {/* Subtle Save & Status Bar */}
            <div className="diary-toolbar" style={{ marginBottom: '12px' }}>
              <div className="diary-status-pill" aria-live="polite">
                {saveStatus === 'saving' && (
                  <>
                    <Loader2 size={13} className="spin" />
                    <span>Saving...</span>
                  </>
                )}
                {saveStatus === 'saved' && (
                  <>
                    <CheckCircle2 size={13} color="var(--status-success)" />
                    <span>{activeIsDraft ? 'Draft saved' : 'Saved'}</span>
                  </>
                )}
                {saveStatus === 'error' && (
                  <>
                    <AlertCircle size={13} color="var(--status-danger)" />
                    <span>Unable to save —</span>
                    <button
                      type="button"
                      onClick={() => persistToBackend(false)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--accent-blue)',
                        cursor: 'pointer',
                        padding: 0,
                        fontWeight: 600,
                        textDecoration: 'underline',
                      }}
                    >
                      Retry
                    </button>
                  </>
                )}
                {saveStatus === 'idle' && (
                  <span>
                    {activeIsDraft ? 'New entry (auto-protects draft)' : 'Editing saved entry'}
                  </span>
                )}
              </div>

              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => persistToBackend(true)}
                disabled={savingExplicit}
              >
                <Save size={14} />
                <span>
                  {savingExplicit
                    ? 'Saving...'
                    : activeEntryId && !activeIsDraft
                    ? 'Update Entry'
                    : 'Save Entry'}
                </span>
              </button>
            </div>

            {/* Open Ruled Notebook */}
            <div className="diary-open-shell">
              {isOpeningAnim && <SharedNotebookOpeningFlap idPrefix="diary" />}

              <div className="diary-notebook-frame">
                <div className="diary-paper-stack">
                  {turnDirection && (
                    <div
                      className={`diary-turning-sheet ${
                        turnDirection === 'next' ? 'turn-next' : 'turn-prev'
                      }`}
                      aria-hidden="true"
                    />
                  )}

                  <div className="diary-paper-page">
                    {/* Top: Entry Title & Top-Right Date + Weekday */}
                    <div className="diary-page-header">
                      <input
                        type="text"
                        className="diary-title-input"
                        placeholder="Entry title..."
                        aria-label="Diary entry title"
                        value={title}
                        onChange={(e) => handleTitleChange(e.target.value)}
                      />
                      <div className="diary-date-stamp" aria-label="Entry date">
                        {formatDiaryDate(entryDate)}
                      </div>
                    </div>

                    {/* Ruled Writing Area */}
                    <div className="diary-ruled-area-wrap">
                      <textarea
                        className="diary-ruled-textarea"
                        placeholder={diaryPlaceholder}
                        aria-label={`Diary writing area, page ${currentPageIdx + 1}`}
                        value={pages[currentPageIdx] ?? ''}
                        onChange={(e) => handlePageTextChange(e.target.value)}
                        rows={13}
                      />
                    </div>

                    {/* Bottom Page Navigation & Page Numbering */}
                    <div className="diary-page-footer">
                      <div>
                        {currentPageIdx > 0 && (
                          <button
                            type="button"
                            className="diary-turn-btn"
                            onClick={() => handleTurnPage('prev')}
                            disabled={isTurning}
                            aria-label="Previous diary page"
                            title="Previous page"
                          >
                            <ChevronLeft size={18} />
                          </button>
                        )}
                      </div>

                      <span className="diary-page-indicator">
                        Page {currentPageIdx + 1} of {pages.length}
                      </span>

                      <button
                        type="button"
                        className="diary-turn-btn"
                        onClick={() => handleTurnPage('next')}
                        disabled={isTurning}
                        aria-label="Next diary page"
                        title={
                          currentPageIdx === pages.length - 1
                            ? 'Turn to new blank page'
                            : 'Next page'
                        }
                      >
                        <ChevronRight size={18} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </section>

      {/* Organized Diary Library */}
      <section className="card" aria-label="Diary Library">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '10px',
            flexWrap: 'wrap',
            marginBottom: '16px',
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.22rem', margin: 0 }}>Diary Library</h2>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>
              Your saved entries and drafts, ordered newest first.
            </p>
          </div>
          <span className="badge badge-indigo">
            {entries.length} {entries.length === 1 ? 'Entry' : 'Entries'}
          </span>
        </div>

        {loadingLibrary ? (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Loading your diary entries...
          </p>
        ) : entries.length === 0 ? (
          <div
            style={{
              padding: '28px',
              textAlign: 'center',
              borderRadius: '12px',
              background: 'var(--surface-2)',
              border: '1px dashed var(--border-default)',
              color: 'var(--text-secondary)',
            }}
          >
            <FileText size={26} style={{ marginBottom: '8px', opacity: 0.7 }} />
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>No diary entries yet</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Open the notebook above and write your first page.
            </div>
          </div>
        ) : (
          <div className="diary-library-grid">
            {entries.map((entry) => {
              const isSelected = activeEntryId === entry.id;
              return (
                <article
                  key={entry.id}
                  className={`diary-entry-card ${entry.is_draft ? 'is-draft' : ''}`}
                  style={
                    isSelected
                      ? { borderColor: 'var(--accent-blue)', boxShadow: 'var(--shadow-sm)' }
                      : undefined
                  }
                >
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '6px',
                      }}
                    >
                      <span
                        className={`badge ${entry.is_draft ? 'badge-warning' : 'badge-success'}`}
                      >
                        {entry.is_draft ? 'Unsaved Draft' : 'Saved'}
                      </span>
                      <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                        {entry.page_count} {entry.page_count === 1 ? 'page' : 'pages'}
                      </span>
                    </div>

                    <div
                      style={{
                        fontSize: '0.78rem',
                        color: 'var(--accent-blue)',
                        fontWeight: 600,
                        marginBottom: '4px',
                      }}
                    >
                      {formatDiaryDate(entry.entry_date)}
                    </div>

                    <h3
                      style={{
                        fontSize: '1rem',
                        margin: '0 0 6px',
                        color: 'var(--text-primary)',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      {entry.title || 'Untitled Entry'}
                    </h3>

                    <p
                      style={{
                        fontSize: '0.84rem',
                        color: 'var(--text-secondary)',
                        margin: 0,
                        lineHeight: 1.45,
                        overflowWrap: 'anywhere',
                      }}
                    >
                      {entry.preview || 'Blank entry'}
                    </p>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '8px',
                      paddingTop: '8px',
                      borderTop: '1px solid var(--border-subtle)',
                    }}
                  >
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpenSavedEntry(entry)}
                    >
                      <BookOpen size={14} />
                      <span>Open</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setDeletingEntry(entry)}
                      aria-label={`Delete diary entry ${entry.title || 'Untitled Entry'}`}
                      style={{ color: 'var(--status-danger)' }}
                    >
                      <Trash2 size={14} />
                      <span>Delete</span>
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Delete Confirmation Modal */}
      {deletingEntry && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-diary-title"
          onClick={() => !deletingBusy && setDeletingEntry(null)}
        >
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 id="delete-diary-title" style={{ marginBottom: '8px' }}>
              Delete Diary Entry?
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              Are you sure you want to permanently delete{' '}
              <strong>"{deletingEntry.title || 'Untitled Entry'}"</strong> (
              {formatDiaryDate(deletingEntry.entry_date)})? This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={deletingBusy}
                onClick={() => setDeletingEntry(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={deletingBusy}
                onClick={handleConfirmDelete}
              >
                {deletingBusy ? 'Deleting...' : 'Delete Entry'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

