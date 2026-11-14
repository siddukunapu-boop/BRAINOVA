import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Edit3,
  Eye,
  FileText,
  GraduationCap,
  Library,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';
import { StudyRichEditor } from '../components/StudyRichEditor';
import { StudyDatePicker, StudySelect, StudySelectOption } from '../components/StudyControls';
import { SharedNotebookCover, SharedNotebookOpeningFlap } from '../components/NotebookCover';
import {
  cloneStudyPageDoc,
  createEmptyStudyPageDoc,
  extractStudyPlainText,
  LearningStatus,
  StudyJournalEntry,
  StudyPageDoc,
} from '../types/studyJournal';
import '../styles/diary.css';
import '../styles/study-journal.css';

type NotebookPhase = 'closed' | 'opening' | 'open';
type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function getTodayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatStudyDate(isoDate: string): string {
  const parts = (isoDate || '').slice(0, 10).split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return isoDate;
  }
  const dt = new Date(parts[0], parts[1] - 1, parts[2]);
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(dt);
}

function createDraftKey(): string {
  return `sj_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

const LEARNING_STATUS_OPTIONS: StudySelectOption<LearningStatus>[] = [
  { value: 'needs_revision', label: 'Needs Revision' },
  { value: 'understood', label: 'Understood' },
];

const LIBRARY_STATUS_OPTIONS: StudySelectOption<'all' | LearningStatus>[] = [
  { value: 'all', label: 'All Statuses' },
  { value: 'understood', label: 'Understood' },
  { value: 'needs_revision', label: 'Needs Revision' },
];

const SORT_OPTIONS: StudySelectOption<'newest' | 'oldest'>[] = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
];

export const StudyJournalPage: React.FC = () => {
  const { user } = useApp();

  const notebookSectionRef = useRef<HTMLElement | null>(null);
  const librarySectionRef = useRef<HTMLElement | null>(null);
  const subjectInputRef = useRef<HTMLInputElement | null>(null);

  // Notebook physical state
  const [phase, setPhase] = useState<NotebookPhase>('closed');
  const [isOpeningAnim, setIsOpeningAnim] = useState(false);
  const [turnDirection, setTurnDirection] = useState<'next' | 'prev' | null>(null);
  const [isTurning, setIsTurning] = useState(false);

  // Active entry state
  const [entryId, setEntryId] = useState<string | null>(null);
  const [clientDraftKey, setClientDraftKey] = useState<string>(createDraftKey);
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [chapterOrModule, setChapterOrModule] = useState('');
  const [studyDate, setStudyDate] = useState(getTodayIsoDate);
  const [durationMinutes, setDurationMinutes] = useState<number>(30);
  const [learningStatus, setLearningStatus] = useState<LearningStatus>('needs_revision');
  const [keyConcepts, setKeyConcepts] = useState('');
  const [learningOutcomes, setLearningOutcomes] = useState('');
  const [revisionNotes, setRevisionNotes] = useState('');
  const [pages, setPages] = useState<StudyPageDoc[]>([createEmptyStudyPageDoc()]);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);

  // Persistence & library state
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [entries, setEntries] = useState<StudyJournalEntry[]>([]);
  const [loadingEntries, setLoadingEntries] = useState(true);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [recoverableDraft, setRecoverableDraft] = useState<StudyJournalEntry | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StudyJournalEntry | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Library filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | LearningStatus>('all');
  const [dateFilter, setDateFilter] = useState('');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');

  const autosaveTimerRef = useRef<number | null>(null);
  const saveSeqRef = useRef(0);
  const inFlightSaveRef = useRef(false);
  const skipNextAutosaveRef = useRef(false);
  const hasDirtyChangesRef = useRef(false);

  const userName = (user?.name || '').trim();
  const editorPlaceholder = userName
    ? `${userName}, capture key definitions, worked examples, formulas, and study notes here...`
    : 'Capture key definitions, worked examples, formulas, and study notes here...';

  const loadEntries = useCallback(async () => {
    setLoadingEntries(true);
    setLibraryError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.set('search', searchQuery.trim());
      if (subjectFilter) params.set('subject', subjectFilter);
      if (statusFilter !== 'all') params.set('learning_status', statusFilter);
      if (dateFilter) params.set('study_date', dateFilter);
      params.set('sort', sortOrder);

      const res = await apiRequest<{ entries: StudyJournalEntry[] }>(
        `/api/study-journal?${params.toString()}`
      );
      setEntries(res.entries || []);
    } catch (err) {
      setLibraryError(
        err instanceof Error ? err.message : 'Unable to load your Study Journal entries.'
      );
    } finally {
      setLoadingEntries(false);
    }
  }, [dateFilter, searchQuery, sortOrder, statusFilter, subjectFilter]);

  const checkRecoverableDraft = useCallback(async () => {
    try {
      const res = await apiRequest<{ draft: StudyJournalEntry | null }>('/api/study-journal/draft');
      if (res.draft) {
        setRecoverableDraft(res.draft);
      }
    } catch {
      // Non-fatal draft probe
    }
  }, []);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    void checkRecoverableDraft();
  }, [checkRecoverableDraft]);

  useEffect(() => {
    if (!deleteTarget) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !deleting) {
        setDeleteTarget(null);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [deleteTarget, deleting]);

  const subjectFilterOptions = useMemo<StudySelectOption[]>(() => {
    const set = new Set<string>();
    entries.forEach((e) => {
      if (e.subject?.trim()) set.add(e.subject.trim());
    });
    if (subjectFilter && !set.has(subjectFilter)) {
      set.add(subjectFilter);
    }
    const sorted = Array.from(set).sort((a, b) => a.localeCompare(b));
    return [
      { value: '', label: 'All Subjects' },
      ...sorted.map((s) => ({ value: s, label: s })),
    ];
  }, [entries, subjectFilter]);

  const hasContent = useMemo(() => {
    if (title.trim() || subject.trim() || topic.trim() || chapterOrModule.trim()) return true;
    if (keyConcepts.trim() || learningOutcomes.trim() || revisionNotes.trim()) return true;
    return pages.some((p) => extractStudyPlainText(p).length > 0);
  }, [chapterOrModule, keyConcepts, learningOutcomes, pages, revisionNotes, subject, title, topic]);

  const persistEntry = useCallback(
    async (markAsFinal: boolean) => {
      if (inFlightSaveRef.current && !markAsFinal) return;
      inFlightSaveRef.current = true;
      const seq = ++saveSeqRef.current;
      setSaveState('saving');
      setSaveError(null);

      const safeDuration = Math.min(1440, Math.max(0, Math.round(Number(durationMinutes) || 0)));
      const payload = {
        title: title.trim(),
        subject: subject.trim(),
        topic: topic.trim(),
        chapter_or_module: chapterOrModule.trim(),
        study_date: studyDate || getTodayIsoDate(),
        duration_minutes: safeDuration,
        learning_status: learningStatus,
        key_concepts: keyConcepts.trim(),
        learning_outcomes: learningOutcomes.trim(),
        revision_notes: revisionNotes.trim(),
        pages: pages.map(cloneStudyPageDoc),
        is_draft: !markAsFinal,
        client_draft_key: clientDraftKey,
      };

      try {
        const res = entryId
          ? await apiRequest<{ entry: StudyJournalEntry }>(`/api/study-journal/${entryId}`, {
              method: 'PUT',
              body: JSON.stringify(payload),
            })
          : await apiRequest<{ entry: StudyJournalEntry }>('/api/study-journal', {
              method: 'POST',
              body: JSON.stringify(payload),
            });

        if (seq !== saveSeqRef.current) return;

        const saved = res.entry;
        setEntryId(saved.id);
        hasDirtyChangesRef.current = false;
        setSaveState('saved');
        if (!saved.is_draft) {
          setRecoverableDraft(null);
        }
        await loadEntries();
      } catch (err) {
        if (seq !== saveSeqRef.current) return;
        setSaveState('error');
        setSaveError(err instanceof Error ? err.message : 'Unable to save study entry');
      } finally {
        inFlightSaveRef.current = false;
      }
    },
    [
      chapterOrModule,
      clientDraftKey,
      durationMinutes,
      entryId,
      keyConcepts,
      learningOutcomes,
      learningStatus,
      loadEntries,
      pages,
      revisionNotes,
      studyDate,
      subject,
      title,
      topic,
    ]
  );

  const flushPendingSave = useCallback(async () => {
    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    if (phase === 'open' && hasContent && hasDirtyChangesRef.current) {
      await persistEntry(false);
    }
  }, [hasContent, persistEntry, phase]);

  // Debounced autosave while notebook is open and user has typed content
  useEffect(() => {
    if (phase !== 'open' || !hasContent) return;
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false;
      return;
    }

    hasDirtyChangesRef.current = true;
    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current);
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      autosaveTimerRef.current = null;
      void persistEntry(false);
    }, 1400);

    return () => {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current);
      }
    };
  }, [
    phase,
    hasContent,
    title,
    subject,
    topic,
    chapterOrModule,
    studyDate,
    durationMinutes,
    learningStatus,
    keyConcepts,
    learningOutcomes,
    revisionNotes,
    pages,
    persistEntry,
  ]);

  const openNotebookAnimation = useCallback(() => {
    if (phase === 'open') return;
    setPhase('open');
    setIsOpeningAnim(true);
    window.setTimeout(() => {
      setIsOpeningAnim(false);
    }, 920);
  }, [phase]);

  const handleCloseNotebook = async () => {
    await flushPendingSave();
    setPhase('closed');
  };

  const handleReturnToLibrary = async () => {
    await flushPendingSave();
    librarySectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const resetForNewEntry = async () => {
    await flushPendingSave();
    skipNextAutosaveRef.current = true;
    hasDirtyChangesRef.current = false;
    setEntryId(null);
    setClientDraftKey(createDraftKey());
    setTitle('');
    setSubject('');
    setTopic('');
    setChapterOrModule('');
    setStudyDate(getTodayIsoDate());
    setDurationMinutes(30);
    setLearningStatus('needs_revision');
    setKeyConcepts('');
    setLearningOutcomes('');
    setRevisionNotes('');
    setPages([createEmptyStudyPageDoc()]);
    setCurrentPageIndex(0);
    setSaveState('idle');
    setSaveError(null);
    openNotebookAnimation();
    notebookSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const loadEntryIntoNotebook = async (entry: StudyJournalEntry, focusMetadata = false) => {
    await flushPendingSave();
    skipNextAutosaveRef.current = true;
    hasDirtyChangesRef.current = false;
    setEntryId(entry.id);
    setClientDraftKey(entry.client_draft_key || createDraftKey());
    setTitle(entry.title || '');
    setSubject(entry.subject || '');
    setTopic(entry.topic || '');
    setChapterOrModule(entry.chapter_or_module || '');
    setStudyDate(entry.study_date || getTodayIsoDate());
    setDurationMinutes(entry.duration_minutes ?? 30);
    setLearningStatus(entry.learning_status || 'needs_revision');
    setKeyConcepts(entry.key_concepts || '');
    setLearningOutcomes(entry.learning_outcomes || '');
    setRevisionNotes(entry.revision_notes || '');
    setPages(
      entry.pages && entry.pages.length > 0
        ? entry.pages.map(cloneStudyPageDoc)
        : [createEmptyStudyPageDoc()]
    );
    setCurrentPageIndex(0);
    setSaveState('saved');
    setSaveError(null);
    openNotebookAnimation();
    notebookSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (focusMetadata) {
      window.setTimeout(() => subjectInputRef.current?.focus(), 680);
    }
  };

  const handleTurnPage = (direction: 'next' | 'prev') => {
    if (isTurning) return;
    const target = direction === 'next' ? currentPageIndex + 1 : currentPageIndex - 1;
    if (target < 0 || target >= pages.length) return;

    setTurnDirection(direction);
    setIsTurning(true);
    window.setTimeout(() => {
      setCurrentPageIndex(target);
    }, 520);
    window.setTimeout(() => {
      setIsTurning(false);
      setTurnDirection(null);
    }, 1150);
  };

  const handleAddPage = () => {
    if (isTurning) return;
    const nextPages = [...pages, createEmptyStudyPageDoc()];
    setPages(nextPages);
    setTurnDirection('next');
    setIsTurning(true);
    window.setTimeout(() => {
      setCurrentPageIndex(nextPages.length - 1);
    }, 520);
    window.setTimeout(() => {
      setIsTurning(false);
      setTurnDirection(null);
    }, 1150);
  };

  const handleCurrentPageChange = useCallback(
    (nextDoc: StudyPageDoc) => {
      setPages((prev) => prev.map((p, idx) => (idx === currentPageIndex ? nextDoc : p)));
    },
    [currentPageIndex]
  );

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiRequest(`/api/study-journal/${deleteTarget.id}`, { method: 'DELETE' });
      const deletedId = deleteTarget.id;
      setDeleteTarget(null);
      if (entryId === deletedId) {
        skipNextAutosaveRef.current = true;
        hasDirtyChangesRef.current = false;
        setEntryId(null);
        setClientDraftKey(createDraftKey());
        setPages([createEmptyStudyPageDoc()]);
        setCurrentPageIndex(0);
        setSaveState('idle');
      }
      await loadEntries();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Unable to delete entry');
    } finally {
      setDeleting(false);
    }
  };

  const hasActiveFilters = Boolean(
    searchQuery.trim() || subjectFilter || statusFilter !== 'all' || dateFilter || sortOrder !== 'newest'
  );

  const clearFilters = () => {
    setSearchQuery('');
    setSubjectFilter('');
    setStatusFilter('all');
    setDateFilter('');
    setSortOrder('newest');
  };

  const totalWordCount = useMemo(
    () =>
      pages.reduce((sum, p) => {
        const text = extractStudyPlainText(p);
        return sum + (text ? text.split(/\s+/).filter(Boolean).length : 0);
      }, 0),
    [pages]
  );

  const currentDoc = pages[currentPageIndex] || createEmptyStudyPageDoc();

  return (
    <div className="study-journal-shell space-y-8">
      {/* Page Header */}
      <header className="flex flex-wrap items-center justify-between gap-5">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-400/30">
              <GraduationCap size={24} className="shrink-0" />
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">Study Journal</h1>
          </div>
          <p className="text-sm opacity-75 mt-2 max-w-2xl">
            Structured academic notebook with rich formatting, glitter inks, multi-page notes, and
            revision tracking.
          </p>
        </div>

        <div className="study-btn-row">
          {phase === 'open' ? (
            <>
              <span
                className={`diary-status-pill ${saveState}`}
                role="status"
                aria-live="polite"
              >
                {saveState === 'saving' && (
                  <>
                    <Loader2 size={16} className="animate-spin shrink-0" /> Saving...
                  </>
                )}
                {saveState === 'saved' && (
                  <>
                    <CheckCircle2 size={16} className="shrink-0" /> Saved
                  </>
                )}
                {saveState === 'error' && (
                  <>
                    <AlertCircle size={16} className="shrink-0" />
                    <button
                      type="button"
                      className="underline font-bold"
                      onClick={() => void persistEntry(false)}
                    >
                      Unable to save — Retry
                    </button>
                  </>
                )}
                {saveState === 'idle' && (
                  <>
                    <Sparkles size={16} className="shrink-0" /> Ready
                  </>
                )}
              </span>

              <button
                type="button"
                onClick={() => void handleReturnToLibrary()}
                className="study-btn study-btn-secondary"
              >
                <Library size={17} className="shrink-0" /> Return to Library
              </button>

              <button
                type="button"
                onClick={() => void handleCloseNotebook()}
                className="study-btn study-btn-secondary"
              >
                <X size={17} className="shrink-0" /> Close Notebook
              </button>

              <button
                type="button"
                onClick={() => void resetForNewEntry()}
                className="study-btn study-btn-secondary"
              >
                <Plus size={17} className="shrink-0" /> New Entry
              </button>

              <button
                type="button"
                disabled={saveState === 'saving'}
                onClick={() => void persistEntry(true)}
                className="study-btn study-btn-primary"
              >
                <Save size={17} className="shrink-0" /> {entryId ? 'Update Entry' : 'Save Study Session'}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={openNotebookAnimation}
              className="study-btn study-btn-primary"
            >
              <BookOpen size={17} className="shrink-0" /> Open Notebook
            </button>
          )}
        </div>
      </header>

      {saveError && (
        <div
          className="study-save-error-banner rounded-xl border border-rose-500/35 bg-rose-500/10 text-sm text-rose-300 flex flex-wrap items-center justify-between gap-5"
          role="alert"
        >
          <span className="min-w-0 break-words">{saveError}</span>
          <button
            type="button"
            onClick={() => void persistEntry(false)}
            className="study-btn study-btn-danger"
          >
            <RotateCcw size={17} className="shrink-0" /> Retry Save
          </button>
        </div>
      )}

      {/* Recoverable Draft Banner */}
      {recoverableDraft && entryId !== recoverableDraft.id && (
        <div className="study-draft-banner rounded-2xl border border-amber-400/35 bg-amber-500/10 flex flex-wrap items-center justify-between gap-5">
          <div className="text-sm min-w-0">
            <span className="font-bold text-amber-300">Unsaved Study Draft Found:</span>{' '}
            <span className="opacity-90 break-words">
              {recoverableDraft.title || recoverableDraft.subject || 'Untitled Journal'} —{' '}
              {recoverableDraft.topic || 'Untitled Topic'} ({recoverableDraft.page_count} page
              {recoverableDraft.page_count === 1 ? '' : 's'})
            </span>
          </div>
          <div className="study-btn-row shrink-0">
            <button
              type="button"
              onClick={() => void loadEntryIntoNotebook(recoverableDraft, false)}
              className="study-btn study-btn-primary"
            >
              Restore Draft
            </button>
            <button
              type="button"
              onClick={() => setRecoverableDraft(null)}
              className="study-btn study-btn-secondary"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Closed / Opening / Open Physical Notebook */}
      <section ref={notebookSectionRef} className="diary-stage">
        {phase === 'closed' && (
          <SharedNotebookCover
            idPrefix="study"
            badge="BRAINOVA • ACADEMIC EDITION"
            title="Study Journal"
            subtitle={
              entryId && (title || topic)
                ? `Resume: "${title || topic}" (${formatStudyDate(studyDate)})`
                : userName
                  ? `${userName}'s Academic Notebook — Tap to open`
                  : 'Personal Academic Notebook — Tap to open'
            }
            ariaLabel="Open Study Journal Notebook"
            onOpen={openNotebookAnimation}
          />
        )}

        {phase === 'open' && (
          <div className="space-y-4 min-w-0">
            {/* Academic Metadata Panel */}
            <div className="study-meta-panel">
              <div className="study-meta-grid">
                <div className="study-meta-field">
                  <label htmlFor="sj-subject">Subject</label>
                  <input
                    ref={subjectInputRef}
                    id="sj-subject"
                    type="text"
                    className="study-meta-input"
                    placeholder="e.g., Operating Systems"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </div>
                <div className="study-meta-field">
                  <label htmlFor="sj-topic">Topic</label>
                  <input
                    id="sj-topic"
                    type="text"
                    className="study-meta-input"
                    placeholder="e.g., Deadlock Prevention"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                  />
                </div>
                <div className="study-meta-field">
                  <label htmlFor="sj-chapter">Chapter / Module</label>
                  <input
                    id="sj-chapter"
                    type="text"
                    className="study-meta-input"
                    placeholder="e.g., Module 3"
                    value={chapterOrModule}
                    onChange={(e) => setChapterOrModule(e.target.value)}
                  />
                </div>
                <div className="study-meta-field">
                  <label htmlFor="sj-date">Study Date</label>
                  <StudyDatePicker
                    id="sj-date"
                    ariaLabel="Study Date"
                    value={studyDate}
                    onChange={setStudyDate}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 min-w-0">
                  <div className="study-meta-field">
                    <label htmlFor="sj-duration">Minutes</label>
                    <input
                      id="sj-duration"
                      type="number"
                      min={0}
                      max={1440}
                      className="study-meta-input"
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(Number(e.target.value))}
                    />
                  </div>
                  <div className="study-meta-field">
                    <label htmlFor="sj-status">Status</label>
                    <StudySelect<LearningStatus>
                      id="sj-status"
                      ariaLabel="Learning Status"
                      value={learningStatus}
                      options={LEARNING_STATUS_OPTIONS}
                      onChange={setLearningStatus}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Physical Open Notebook */}
            <div className="diary-open-shell" style={{ width: '100%' }}>
              {isOpeningAnim && <SharedNotebookOpeningFlap idPrefix="study" />}
              <div className="diary-notebook-frame">
              <div className="diary-paper-stack">
                <div className="study-paper-page">
                  {isTurning && turnDirection && (
                    <div
                      className={`diary-turning-sheet ${
                        turnDirection === 'next' ? 'turn-next' : 'turn-prev'
                      }`}
                    />
                  )}

                  {/* Page Header — Title Matches Personal Diary Input */}
                  <div className="study-page-header">
                    <div className="study-page-title-block">
                      <input
                        id="sj-title"
                        type="text"
                        maxLength={200}
                        className="study-diary-title-input"
                        placeholder="Untitled Journal"
                        aria-label="Study journal title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                      />
                      {(subject.trim() || topic.trim() || chapterOrModule.trim()) && (
                        <div className="study-page-subject-kicker">
                          {[subject.trim(), chapterOrModule.trim(), topic.trim()]
                            .filter(Boolean)
                            .join(' · ')}
                        </div>
                      )}
                    </div>

                    <div className="study-page-meta-pills">
                      <span className="study-diary-date-stamp">{formatStudyDate(studyDate)}</span>
                      <span className="inline-flex items-center gap-1.5">
                        <Clock size={15} className="shrink-0" /> {durationMinutes || 0} min
                      </span>
                      <span className={`study-status-badge ${learningStatus}`}>
                        {learningStatus === 'understood' ? 'Understood' : 'Needs Revision'}
                      </span>
                    </div>
                  </div>

                  {/* Rich Text Editor + Formatting Toolbar */}
                  <div className="py-4 min-w-0">
                    <StudyRichEditor
                      pageKey={`${entryId || clientDraftKey}-p${currentPageIndex}`}
                      doc={currentDoc}
                      placeholder={editorPlaceholder}
                      onChange={handleCurrentPageChange}
                    />
                  </div>

                  {/* Academic Reflection Boxes */}
                  <div className="pb-4 min-w-0">
                    <div className="study-reflection-grid">
                      <div className="study-reflection-box">
                        <label htmlFor="sj-concepts">Key Concepts</label>
                        <textarea
                          id="sj-concepts"
                          placeholder="Core terms, theorems, formulas..."
                          value={keyConcepts}
                          onChange={(e) => setKeyConcepts(e.target.value)}
                        />
                      </div>
                      <div className="study-reflection-box">
                        <label htmlFor="sj-outcomes">Learning Outcomes</label>
                        <textarea
                          id="sj-outcomes"
                          placeholder="What you can now explain or solve..."
                          value={learningOutcomes}
                          onChange={(e) => setLearningOutcomes(e.target.value)}
                        />
                      </div>
                      <div className="study-reflection-box">
                        <label htmlFor="sj-revision">Revision Notes</label>
                        <textarea
                          id="sj-revision"
                          placeholder="Questions or areas to revisit..."
                          value={revisionNotes}
                          onChange={(e) => setRevisionNotes(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Page Navigation Matching Personal Diary + Separated Add Page */}
                  <div className="study-page-footer">
                    <div className="study-nav-cluster">
                      <button
                        type="button"
                        className="study-nav-circle-btn"
                        disabled={currentPageIndex === 0 || isTurning}
                        onClick={() => handleTurnPage('prev')}
                        aria-label="Previous study journal page"
                        title="Previous page"
                      >
                        <ChevronLeft size={18} className="shrink-0" />
                      </button>

                      <span className="study-page-indicator" aria-live="polite">
                        Page {currentPageIndex + 1} of {pages.length}
                      </span>

                      <button
                        type="button"
                        className="study-nav-circle-btn"
                        disabled={currentPageIndex >= pages.length - 1 || isTurning}
                        onClick={() => handleTurnPage('next')}
                        aria-label="Next study journal page"
                        title="Next page"
                      >
                        <ChevronRight size={18} className="shrink-0" />
                      </button>
                    </div>

                    <div className="study-btn-row">
                      <button
                        type="button"
                        className="study-add-page-btn"
                        disabled={isTurning}
                        onClick={handleAddPage}
                        aria-label="Add Page"
                      >
                        <Plus size={17} className="shrink-0" /> Add Page
                      </button>

                      <span className="text-xs font-semibold text-stone-600">
                        {totalWordCount} word{totalWordCount === 1 ? '' : 's'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            </div>
          </div>
        )}
      </section>

      {/* Study Journal Library */}
      <section ref={librarySectionRef} className="study-library-section">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-3 min-w-0">
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-400/25">
              <BookOpen size={22} className="shrink-0" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="text-xl font-bold">Study Journal Library</h2>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-bold">
                  {entries.length}
                </span>
              </div>
              <p className="text-xs opacity-75 mt-0.5">
                Search, filter, reopen, edit, or organize your saved study sessions.
              </p>
            </div>
          </div>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="study-btn study-btn-secondary"
            >
              <RotateCcw size={17} className="shrink-0" /> Clear Filters
            </button>
          )}
        </div>

        {/* Custom Search & Filter Controls */}
        <div className="study-library-controls">
          <div className="study-search-box">
            <Search className="study-search-icon" />
            <input
              type="search"
              aria-label="Search study entries"
              placeholder="Search subject, topic, concepts, or notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="study-search-input"
            />
          </div>

          <StudySelect
            ariaLabel="Filter by subject"
            value={subjectFilter}
            options={subjectFilterOptions}
            onChange={setSubjectFilter}
          />

          <StudySelect<'all' | LearningStatus>
            ariaLabel="Filter by learning status"
            value={statusFilter}
            options={LIBRARY_STATUS_OPTIONS}
            onChange={setStatusFilter}
          />

          <StudyDatePicker
            ariaLabel="Filter by study date"
            placeholder="All Dates"
            allowClear
            value={dateFilter}
            onChange={setDateFilter}
          />

          <StudySelect<'newest' | 'oldest'>
            ariaLabel="Sort study entries"
            value={sortOrder}
            options={SORT_OPTIONS}
            onChange={setSortOrder}
          />
        </div>

        {/* Loading / Error / Empty / Card Grid */}
        {loadingEntries ? (
          <div className="py-12 text-center text-sm opacity-75 flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading your study journal...
          </div>
        ) : libraryError ? (
          <div className="study-error-state space-y-4" role="alert">
            <AlertCircle size={26} className="mx-auto text-rose-400" />
            <p className="font-bold text-base">Could not load your Study Journal entries</p>
            <p className="text-sm opacity-75 max-w-md mx-auto">{libraryError}</p>
            <div className="study-btn-row justify-center">
              <button
                type="button"
                onClick={() => void loadEntries()}
                className="study-btn study-btn-secondary"
              >
                <RotateCcw size={17} className="shrink-0" /> Retry
              </button>
            </div>
          </div>
        ) : entries.length === 0 ? (
          <div className="study-empty-state space-y-4">
            <FileText size={26} className="mx-auto opacity-70 text-indigo-400" />
            <h3 className="font-bold text-base">
              {hasActiveFilters
                ? 'No study sessions match your filters'
                : 'Your Study Journal Library is ready'}
            </h3>
            <p className="text-sm opacity-75 max-w-md mx-auto">
              {hasActiveFilters
                ? 'Try clearing your search or filters to view all saved study sessions.'
                : 'Open the physical notebook above to write your first rich-text study session.'}
            </p>
            <div className="study-btn-row justify-center pt-1">
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="study-btn study-btn-secondary"
                >
                  <RotateCcw size={17} className="shrink-0" /> Clear Filters
                </button>
              )}
              <button
                type="button"
                onClick={() => void resetForNewEntry()}
                className="study-btn study-btn-primary"
              >
                <BookOpen size={17} className="shrink-0" /> Open Notebook & Create Entry
              </button>
            </div>
          </div>
        ) : (
          <div className="study-library-grid">
            {entries.map((entry) => (
              <article
                key={entry.id}
                className={`study-entry-card ${entry.is_draft ? 'is-draft' : ''}`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-indigo-400 break-words">
                      {entry.subject || 'General Study'}
                    </span>
                    <span className={`study-status-badge ${entry.learning_status}`}>
                      {entry.learning_status === 'understood' ? 'Understood' : 'Needs Revision'}
                    </span>
                  </div>

                  <h3 className="study-card-title">
                    {entry.title || entry.topic || 'Untitled Journal'}
                  </h3>
                  {entry.title && entry.topic && (
                    <div className="text-xs font-semibold opacity-75 mt-1 break-words">
                      {entry.topic}
                    </div>
                  )}

                  <div className="text-xs opacity-70 flex flex-wrap items-center gap-1.5 mt-2">
                    <span>{formatStudyDate(entry.study_date)}</span>
                    <span>·</span>
                    <span>{entry.duration_minutes} min</span>
                    <span>·</span>
                    <span>
                      {entry.page_count} page{entry.page_count === 1 ? '' : 's'}
                    </span>
                    {entry.is_draft && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                        Draft
                      </span>
                    )}
                  </div>

                  <p className="study-card-preview mt-3">
                    {entry.preview || 'No written notes on this study session yet.'}
                  </p>
                </div>

                <div className="study-btn-row pt-3 border-t border-slate-400/20">
                  <button
                    type="button"
                    onClick={() => void loadEntryIntoNotebook(entry, false)}
                    className="study-btn study-btn-secondary"
                  >
                    <Eye size={17} className="shrink-0" /> Open
                  </button>
                  <button
                    type="button"
                    onClick={() => void loadEntryIntoNotebook(entry, true)}
                    className="study-btn study-btn-secondary"
                  >
                    <Edit3 size={17} className="shrink-0" /> Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(entry)}
                    className="study-btn study-btn-danger"
                    aria-label={`Delete ${entry.title || entry.topic || entry.subject || 'entry'}`}
                  >
                    <Trash2 size={17} className="shrink-0" /> Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="sj-delete-title"
          onClick={() => {
            if (!deleting) setDeleteTarget(null);
          }}
        >
          <div
            className="study-delete-dialog w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 space-y-5 text-slate-100 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="sj-delete-title" className="text-lg font-bold">
              Delete Study Journal Entry?
            </h3>
            <p className="text-sm text-slate-300 break-words leading-relaxed">
              Permanently delete{' '}
              <span className="font-semibold text-white">
                {deleteTarget.title || deleteTarget.subject || 'Untitled Journal'} —{' '}
                {deleteTarget.topic || 'Untitled Topic'}
              </span>
              ? This cannot be undone.
            </p>
            <div className="study-btn-row justify-end">
              <button
                type="button"
                disabled={deleting}
                onClick={() => setDeleteTarget(null)}
                className="study-btn study-btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => void confirmDelete()}
                className="study-btn study-btn-danger-solid"
              >
                {deleting ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
