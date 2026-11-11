import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Video,
  BookOpen,
  CheckSquare,
  ExternalLink,
  Plus,
  Trash2,
  Edit3,
  Save,
  RefreshCw,
  CheckCircle2,
  Clock,
  Award,
  AlertTriangle,
  Play,
  FileText,
  ChevronLeft,
  ChevronRight,
  Eye,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const TopicWorkspacePage: React.FC = () => {
  const { roadmapId, topicId } = useParams<{ roadmapId: string; topicId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useApp();
  const navigate = useNavigate();

  const initialTab =
    (searchParams.get('tab') as 'tutorial' | 'reading' | 'quiz') || 'tutorial';
  const [activeTab, setActiveTab] = useState<'tutorial' | 'reading' | 'quiz'>(initialTab);

  const [workspace, setWorkspace] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  // --- SECTION A: TUTORIAL STATES ---
  const [activeTutorialIdx, setActiveTutorialIdx] = useState(0);
  const [customYtUrl, setCustomYtUrl] = useState('');
  const [customYtTitle, setCustomYtTitle] = useState('');
  const [customYtChannel, setCustomYtChannel] = useState('');
  const [replacingTutorialId, setReplacingTutorialId] = useState<string | null>(null);
  const [savingTutorial, setSavingTutorial] = useState(false);

  // --- SECTION B: READING & PERSONAL NOTES STATES ---
  const [isEditingReading, setIsEditingReading] = useState(false);
  const [editReadingOverview, setEditReadingOverview] = useState('');
  const [editReadingSummary, setEditReadingSummary] = useState('');
  const [editReadingSections, setEditReadingSections] = useState<any[]>([]);
  const [showOverwriteModal, setShowOverwriteModal] = useState(false);
  const [regeneratingReading, setRegeneratingReading] = useState(false);

  // Personal Notes States
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [noteDirty, setNoteDirty] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  // --- SECTION C: 20-MCQ EXAM & ATTEMPTS STATES ---
  const [examPhase, setExamPhase] = useState<'instructions' | 'active' | 'results'>('instructions');
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [examElapsedSeconds, setExamElapsedSeconds] = useState(0);
  const [submittingQuiz, setSubmittingQuiz] = useState(false);
  const [activeAttemptResult, setActiveAttemptResult] = useState<any | null>(null);

  const fetchWorkspace = async (silent = false) => {
    if (!topicId) return;
    if (!silent) setLoading(true);
    try {
      const res = await apiRequest(`/api/topics/${topicId}?auto_prepare=true`);
      setWorkspace(res);
      if (res.reading) {
        setEditReadingOverview(res.reading.overview || '');
        setEditReadingSummary(res.reading.summary || '');
        setEditReadingSections(res.reading.sections || []);
      }
      if (res.notes && res.notes.length > 0 && !selectedNoteId) {
        const firstNote = res.notes[0];
        setSelectedNoteId(firstNote.id);
        setNoteTitle(firstNote.title);
        setNoteContent(firstNote.content);
        setNoteDirty(false);
      }
    } catch (err: any) {
      addToast(err.message || 'Topic workspace could not be loaded.', 'error');
      navigate(roadmapId ? `/roadmaps/${roadmapId}` : '/roadmaps');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspace();
  }, [topicId]);

  // Exam timer effect when examPhase === 'active'
  useEffect(() => {
    if (examPhase !== 'active') return;
    const interval = setInterval(() => {
      setExamElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [examPhase]);

  const switchTab = (tab: 'tutorial' | 'reading' | 'quiz') => {
    if (noteDirty && activeTab === 'reading' && tab !== 'reading') {
      const proceed = window.confirm(
        'You have unsaved changes in your personal note. Switch tabs anyway?'
      );
      if (!proceed) return;
    }
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  // --- SECTION A HANDLERS ---
  const handleSaveCustomTutorial = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicId || !customYtUrl.trim()) return;
    setSavingTutorial(true);
    try {
      const res = await apiRequest<{ tutorials: any[] }>(`/api/topics/${topicId}/tutorials`, {
        method: 'POST',
        body: JSON.stringify({
          url: customYtUrl.trim(),
          title: customYtTitle.trim() || undefined,
          channel_name: customYtChannel.trim() || undefined,
          is_primary: true,
          replace_existing_id: replacingTutorialId || undefined,
        }),
      });
      setWorkspace((prev: any) => ({ ...prev, tutorials: res.tutorials }));
      setActiveTutorialIdx(0);
      setCustomYtUrl('');
      setCustomYtTitle('');
      setCustomYtChannel('');
      setReplacingTutorialId(null);
      addToast(
        replacingTutorialId
          ? 'Replaced tutorial with your custom YouTube video!'
          : 'Saved custom YouTube tutorial to this topic!',
        'success'
      );
    } catch (err: any) {
      addToast(err.message || 'Invalid YouTube URL.', 'error');
    } finally {
      setSavingTutorial(false);
    }
  };

  const handleDeleteTutorial = async (tutId: string) => {
    try {
      const res = await apiRequest<{ tutorials: any[] }>(`/api/tutorials/${tutId}`, {
        method: 'DELETE',
      });
      setWorkspace((prev: any) => ({ ...prev, tutorials: res.tutorials }));
      setActiveTutorialIdx(0);
      addToast('Deleted tutorial link. Topic and other resources remain intact.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Failed to delete tutorial.', 'error');
    }
  };

  // --- SECTION B HANDLERS ---
  const handleSaveReadingEdits = async () => {
    if (!topicId) return;
    try {
      const res = await apiRequest<{ reading: any }>(`/api/topics/${topicId}/reading`, {
        method: 'PUT',
        body: JSON.stringify({
          overview: editReadingOverview,
          summary: editReadingSummary,
          sections: editReadingSections,
        }),
      });
      setWorkspace((prev: any) => ({ ...prev, reading: res.reading }));
      setIsEditingReading(false);
      addToast('Saved your personal edits to the reading material.', 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to save reading material.', 'error');
    }
  };

  const handleRegenerateReading = async (confirmOverwrite = false) => {
    if (!topicId) return;
    setRegeneratingReading(true);
    try {
      const res = await apiRequest(`/api/topics/${topicId}/reading/regenerate`, {
        method: 'POST',
        body: JSON.stringify({ confirm_overwrite: confirmOverwrite }),
      });
      setWorkspace(res);
      setShowOverwriteModal(false);
      setIsEditingReading(false);
      addToast('Regenerated topic reading material.', 'success');
    } catch (err: any) {
      if (err.status === 409) {
        setShowOverwriteModal(true);
      } else {
        addToast(err.message || 'Regeneration failed.', 'error');
      }
    } finally {
      setRegeneratingReading(false);
    }
  };

  const handleSelectNote = (note: any) => {
    if (noteDirty) {
      const ok = window.confirm('Discard unsaved changes to current note?');
      if (!ok) return;
    }
    setSelectedNoteId(note.id);
    setNoteTitle(note.title);
    setNoteContent(note.content);
    setNoteDirty(false);
  };

  const handleStartNewNote = () => {
    if (noteDirty) {
      const ok = window.confirm('Discard unsaved changes to current note?');
      if (!ok) return;
    }
    setSelectedNoteId('new');
    setNoteTitle(`Notes on ${workspace?.topic?.title || 'Topic'}`);
    setNoteContent('');
    setNoteDirty(false);
  };

  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicId || !noteTitle.trim()) {
      addToast('Please provide a note title.', 'error');
      return;
    }
    setSavingNote(true);
    try {
      if (!selectedNoteId || selectedNoteId === 'new') {
        const res = await apiRequest<{ note: any }>('/api/notes', {
          method: 'POST',
          body: JSON.stringify({
            title: noteTitle.trim(),
            content: noteContent,
            topic_id: topicId,
            roadmap_id: roadmapId,
          }),
        });
        const updatedNotes = [res.note, ...(workspace?.notes || [])];
        setWorkspace((prev: any) => ({ ...prev, notes: updatedNotes }));
        setSelectedNoteId(res.note.id);
        setNoteDirty(false);
        addToast('Created and saved personal note!', 'success');
      } else {
        const res = await apiRequest<{ note: any }>(`/api/notes/${selectedNoteId}`, {
          method: 'PUT',
          body: JSON.stringify({
            title: noteTitle.trim(),
            content: noteContent,
            topic_id: topicId,
            roadmap_id: roadmapId,
          }),
        });
        const updatedNotes = (workspace?.notes || []).map((n: any) =>
          n.id === res.note.id ? res.note : n
        );
        setWorkspace((prev: any) => ({ ...prev, notes: updatedNotes }));
        setNoteDirty(false);
        addToast('Saved personal note changes!', 'success');
      }
    } catch (err: any) {
      addToast(err.message || 'Could not save note.', 'error');
    } finally {
      setSavingNote(false);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await apiRequest(`/api/notes/${noteId}`, { method: 'DELETE' });
      const remaining = (workspace?.notes || []).filter((n: any) => n.id !== noteId);
      setWorkspace((prev: any) => ({ ...prev, notes: remaining }));
      if (selectedNoteId === noteId) {
        if (remaining.length > 0) {
          setSelectedNoteId(remaining[0].id);
          setNoteTitle(remaining[0].title);
          setNoteContent(remaining[0].content);
        } else {
          setSelectedNoteId(null);
          setNoteTitle('');
          setNoteContent('');
        }
        setNoteDirty(false);
      }
      addToast('Deleted personal note. Reading material is preserved.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Delete note failed.', 'error');
    }
  };

  // --- SECTION C: 20-MCQ EXAM HANDLERS ---
  const handleStartExam = () => {
    setSelectedAnswers({});
    setCurrentQuestionIdx(0);
    setExamElapsedSeconds(0);
    setActiveAttemptResult(null);
    setExamPhase('active');
  };

  const handleSubmitExam = async () => {
    if (!topicId || submittingQuiz) return;
    setSubmittingQuiz(true);
    try {
      const res = await apiRequest<{ attempt: any }>(`/api/topics/${topicId}/quiz/submit`, {
        method: 'POST',
        body: JSON.stringify({
          answers: selectedAnswers,
          duration_seconds: Math.max(1, examElapsedSeconds),
        }),
      });
      setActiveAttemptResult(res.attempt);
      setExamPhase('results');
      fetchWorkspace(true);
      addToast(
        `Exam submitted! Score: ${res.attempt.score}/${res.attempt.max_score} (${res.attempt.percentage}%)`,
        res.attempt.passed ? 'success' : 'info'
      );
    } catch (err: any) {
      addToast(err.message || 'Failed to submit exam.', 'error');
    } finally {
      setSubmittingQuiz(false);
    }
  };

  const handleReviewHistoricalAttempt = async (attemptId: string) => {
    try {
      const res = await apiRequest<{ attempt: any }>(`/api/quizzes/attempts/${attemptId}`);
      setActiveAttemptResult(res.attempt);
      setExamPhase('results');
    } catch (err: any) {
      addToast(err.message || 'Could not load attempt review.', 'error');
    }
  };

  const handleDeleteAttempt = async (attemptId: string) => {
    try {
      await apiRequest(`/api/quizzes/attempts/${attemptId}`, { method: 'DELETE' });
      const remaining = (workspace?.attempts || []).filter((a: any) => a.id !== attemptId);
      setWorkspace((prev: any) => ({ ...prev, attempts: remaining }));
      if (activeAttemptResult?.id === attemptId) {
        setActiveAttemptResult(null);
        setExamPhase('instructions');
      }
      addToast('Deleted quiz attempt.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Failed to delete attempt.', 'error');
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s < 10 ? '0' : ''}${s}s`;
  };

  if (loading || !workspace) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>
          Preparing Topic Workspace (Tutorial, Reading Guide & 20-MCQ Examination)...
        </p>
      </div>
    );
  }

  const { topic, roadmap, phase, tutorials = [], reading, notes = [], quiz, attempts = [] } =
    workspace;
  const currentTutorial = tutorials[activeTutorialIdx] || tutorials[0] || null;
  const quizQuestions = quiz?.questions || [];
  const currentQuestion = quizQuestions[currentQuestionIdx] || null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Top Workspace Header */}
      <div className="card card-elevated">
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => navigate(`/roadmaps/${topic.roadmap_id}`)}
          >
            <ArrowLeft size={15} />
            <span>Back to {roadmap?.title || 'Roadmap'}</span>
          </button>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className="badge badge-indigo">
              Phase {phase?.phase_order}: {phase?.title}
            </span>
            <span className="badge badge-blue">{topic.difficulty}</span>
            <span
              className={`badge ${
                topic.status === 'completed' ? 'badge-success' : 'badge-warning'
              }`}
            >
              {topic.status.replace('_', ' ').toUpperCase()}
            </span>
          </div>
        </div>

        <h1 style={{ fontSize: '1.65rem', marginBottom: '6px' }}>{topic.title}</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '18px' }}>
          {topic.description}
        </p>

        {/* Three Distinct Learning Section Tabs */}
        <div className="tabs-bar">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'tutorial' ? 'active' : ''}`}
            onClick={() => switchTab('tutorial')}
          >
            <Video size={16} />
            <span>Section A: Video Tutorial ({tutorials.length})</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'reading' ? 'active' : ''}`}
            onClick={() => switchTab('reading')}
          >
            <BookOpen size={16} />
            <span>Section B: Reading Material & Personal Notes ({notes.length})</span>
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
            onClick={() => switchTab('quiz')}
          >
            <CheckSquare size={16} />
            <span>
              Section C: {quiz?.question_count || 20}-Question MCQ Examination ({attempts.length}{' '}
              attempts)
            </span>
          </button>
        </div>
      </div>

      {/* ====================================================================
          SECTION A — TUTORIAL WORKSPACE
         ==================================================================== */}
      {activeTab === 'tutorial' && (
        <div className="grid-2" style={{ gridTemplateColumns: '1.55fr 1fr', alignItems: 'start' }}>
          {/* Left: Embedded Video Player & Metadata */}
          <div className="card">
            {currentTutorial ? (
              <>
                <div
                  style={{
                    position: 'relative',
                    width: '100%',
                    paddingTop: '56.25%',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    background: '#000',
                    border: '1px solid var(--border-default)',
                    marginBottom: '16px',
                  }}
                >
                  <iframe
                    src={`https://www.youtube.com/embed/${currentTutorial.video_id}?rel=0`}
                    title={currentTutorial.title}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '100%',
                      border: 0,
                    }}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  />
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                      <span
                        className={`badge ${
                          currentTutorial.source_type === 'user_custom'
                            ? 'badge-success'
                            : 'badge-indigo'
                        }`}
                      >
                        {currentTutorial.source_type === 'user_custom'
                          ? 'User-Added Custom Link'
                          : 'AI-Recommended Verified Lecture'}
                      </span>
                      {currentTutorial.duration_label && (
                        <span className="badge badge-blue">{currentTutorial.duration_label}</span>
                      )}
                    </div>
                    <h2 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>
                      {currentTutorial.title}
                    </h2>
                    <div style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
                      Channel / Publisher: <strong>{currentTutorial.channel_name}</strong>
                    </div>
                    {currentTutorial.notes && (
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                        {currentTutorial.notes}
                      </p>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <a
                      href={currentTutorial.video_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary btn-sm"
                    >
                      <ExternalLink size={14} />
                      <span>Watch on YouTube</span>
                    </a>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setReplacingTutorialId(currentTutorial.id);
                        setCustomYtUrl(currentTutorial.video_url);
                        setCustomYtTitle(currentTutorial.title);
                        setCustomYtChannel(currentTutorial.channel_name);
                      }}
                    >
                      <Edit3 size={14} />
                      <span>Edit / Replace</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDeleteTutorial(currentTutorial.id)}
                    >
                      <Trash2 size={14} />
                      <span>Remove Link</span>
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '48px 20px' }}>
                <Video size={42} color="var(--text-subtle)" style={{ marginBottom: '12px' }} />
                <h3 style={{ marginBottom: '6px' }}>No Tutorial Currently Attached</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  Use the Custom YouTube URL panel on the right to attach your preferred lecture or
                  tutorial video for <strong>{topic.title}</strong>.
                </p>
              </div>
            )}
          </div>

          {/* Right: Tutorial List & Custom YouTube URL Manager */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', marginBottom: '12px' }}>
                {replacingTutorialId
                  ? 'Replace Existing Tutorial Video'
                  : 'Add Custom YouTube Tutorial URL'}
              </h3>
              <form onSubmit={handleSaveCustomTutorial}>
                <div className="form-group">
                  <label className="form-label" htmlFor="yt-url-input">
                    YouTube Video URL (watch?v=..., youtu.be/..., or embed)
                  </label>
                  <input
                    id="yt-url-input"
                    type="text"
                    className="form-input"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={customYtUrl}
                    onChange={(e) => setCustomYtUrl(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="yt-title-input">
                    Custom Video Title (Optional — auto-detected when possible)
                  </label>
                  <input
                    id="yt-title-input"
                    type="text"
                    className="form-input"
                    placeholder={`e.g., ${topic.title} Deep Dive`}
                    value={customYtTitle}
                    onChange={(e) => setCustomYtTitle(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="yt-channel-input">
                    Channel / Publisher (Optional)
                  </label>
                  <input
                    id="yt-channel-input"
                    type="text"
                    className="form-input"
                    placeholder="e.g., MIT OpenCourseWare / freeCodeCamp"
                    value={customYtChannel}
                    onChange={(e) => setCustomYtChannel(e.target.value)}
                  />
                </div>
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  {replacingTutorialId && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setReplacingTutorialId(null);
                        setCustomYtUrl('');
                        setCustomYtTitle('');
                        setCustomYtChannel('');
                      }}
                    >
                      Cancel Replace
                    </button>
                  )}
                  <button
                    type="submit"
                    className="btn btn-primary btn-sm"
                    disabled={savingTutorial}
                  >
                    <Save size={14} />
                    <span>
                      {savingTutorial
                        ? 'Validating & Saving...'
                        : replacingTutorialId
                        ? 'Save Replacement Video'
                        : 'Save Custom Tutorial'}
                    </span>
                  </button>
                </div>
              </form>
            </div>

            {tutorials.length > 0 && (
              <div className="card">
                <h3 style={{ fontSize: '1rem', marginBottom: '12px' }}>
                  Saved Tutorials for This Topic ({tutorials.length})
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {tutorials.map((tut: any, idx: number) => (
                    <div
                      key={tut.id}
                      onClick={() => setActiveTutorialIdx(idx)}
                      style={{
                        padding: '10px',
                        borderRadius: '10px',
                        background:
                          idx === activeTutorialIdx
                            ? 'rgba(99, 102, 241, 0.16)'
                            : 'var(--bg-charcoal)',
                        border:
                          idx === activeTutorialIdx
                            ? '1px solid var(--accent-indigo)'
                            : '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        display: 'flex',
                        gap: '10px',
                        alignItems: 'center',
                      }}
                    >
                      {tut.thumbnail_url && (
                        <img
                          src={tut.thumbnail_url}
                          alt={tut.title}
                          style={{
                            width: 84,
                            height: 48,
                            objectFit: 'cover',
                            borderRadius: '6px',
                            flexShrink: 0,
                          }}
                        />
                      )}
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.84rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {tut.title}
                        </div>
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {tut.channel_name} •{' '}
                          {tut.source_type === 'user_custom' ? 'Custom' : 'AI Recommended'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ====================================================================
          SECTION B — READING MATERIAL & PERSONAL NOTES
         ==================================================================== */}
      {activeTab === 'reading' && (
        <div className="grid-2" style={{ gridTemplateColumns: '1.65fr 1fr', alignItems: 'start' }}>
          {/* Left: Structured Reading Guide */}
          <div className="card">
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '10px', marginBottom: '18px', paddingBottom: '14px', borderBottom: '1px solid var(--border-subtle)' }}>
              <div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                  <span className="badge badge-indigo">Comprehensive Study Material</span>
                  {reading?.is_user_edited && (
                    <span className="badge badge-success">Personal Edits Saved (v{reading.version})</span>
                  )}
                </div>
                <h2 style={{ fontSize: '1.35rem' }}>{reading?.title || topic.title}</h2>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setIsEditingReading((e) => !e)}
                >
                  <Edit3 size={14} />
                  <span>{isEditingReading ? 'Cancel Edit' : 'Edit Reading Material'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleRegenerateReading(false)}
                  disabled={regeneratingReading}
                >
                  <RefreshCw size={14} />
                  <span>{regeneratingReading ? 'Regenerating...' : 'Regenerate'}</span>
                </button>
              </div>
            </div>

            {isEditingReading ? (
              <div>
                <div className="form-group">
                  <label className="form-label">Overview</label>
                  <textarea
                    className="form-textarea"
                    value={editReadingOverview}
                    onChange={(e) => setEditReadingOverview(e.target.value)}
                  />
                </div>
                {editReadingSections.map((sec, idx) => (
                  <div key={idx} className="form-group">
                    <label className="form-label">{sec.heading}</label>
                    <textarea
                      className="form-textarea"
                      style={{ minHeight: 130 }}
                      value={sec.content}
                      onChange={(e) => {
                        const updated = [...editReadingSections];
                        updated[idx] = { ...updated[idx], content: e.target.value };
                        setEditReadingSections(updated);
                      }}
                    />
                  </div>
                ))}
                <div className="form-group">
                  <label className="form-label">Summary</label>
                  <textarea
                    className="form-textarea"
                    value={editReadingSummary}
                    onChange={(e) => setEditReadingSummary(e.target.value)}
                  />
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSaveReadingEdits}
                >
                  <Save size={16} />
                  <span>Save Reading Modifications</span>
                </button>
              </div>
            ) : reading ? (
              <div className="reading-prose">
                {/* Table of Contents */}
                <div
                  style={{
                    padding: '14px 18px',
                    borderRadius: '10px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                    marginBottom: '22px',
                  }}
                >
                  <strong style={{ fontSize: '0.82rem', textTransform: 'uppercase', color: 'var(--accent-blue)' }}>
                    Table of Contents
                  </strong>
                  <ul style={{ paddingLeft: '18px', marginTop: '8px', fontSize: '0.88rem' }}>
                    {(reading.sections || []).map((sec: any, idx: number) => (
                      <li key={idx}>
                        <a href={`#${sec.id || `sec-${idx + 1}`}`}>{sec.heading}</a>
                      </li>
                    ))}
                    <li>
                      <a href="#key-definitions">Important Definitions & Terminology</a>
                    </li>
                    <li>
                      <a href="#code-examples">Code Examples & Implementation</a>
                    </li>
                    <li>
                      <a href="#comparison-tables">Architectural Comparison Tables</a>
                    </li>
                    <li>
                      <a href="#common-mistakes">Common Mistakes & Interview Prep</a>
                    </li>
                  </ul>
                </div>

                {/* Overview */}
                <p style={{ fontSize: '1.03rem', color: 'var(--text-primary)' }}>
                  {reading.overview}
                </p>

                {/* Learning Objectives & Prerequisites */}
                <div className="grid-2" style={{ marginBottom: '22px' }}>
                  <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                    <strong style={{ fontSize: '0.84rem', color: 'var(--accent-blue)' }}>
                      Learning Objectives
                    </strong>
                    <ul style={{ paddingLeft: '18px', marginTop: '6px', fontSize: '0.86rem' }}>
                      {(topic.learning_objectives || []).map((obj: string, i: number) => (
                        <li key={i}>{obj}</li>
                      ))}
                    </ul>
                  </div>
                  <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                    <strong style={{ fontSize: '0.84rem', color: 'var(--accent-indigo)' }}>
                      Prerequisites & Subtopics
                    </strong>
                    <ul style={{ paddingLeft: '18px', marginTop: '6px', fontSize: '0.86rem' }}>
                      {(topic.subtopics || []).map((sub: string, i: number) => (
                        <li key={i}>{sub}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Main Progressive Sections */}
                {(reading.sections || []).map((sec: any, idx: number) => (
                  <section
                    key={idx}
                    id={sec.id || `sec-${idx + 1}`}
                    style={{ marginBottom: '26px' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <h3 style={{ margin: 0 }}>{sec.heading}</h3>
                      {sec.level_tag && <span className="badge badge-blue">{sec.level_tag}</span>}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{sec.content}</div>
                    {sec.key_takeaway && (
                      <div
                        style={{
                          marginTop: '10px',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          background: 'rgba(99, 102, 241, 0.12)',
                          borderLeft: '3px solid var(--accent-indigo)',
                          fontSize: '0.88rem',
                          color: 'var(--text-primary)',
                        }}
                      >
                        <strong>Key Takeaway:</strong> {sec.key_takeaway}
                      </div>
                    )}
                  </section>
                ))}

                {/* Key Definitions */}
                {reading.key_definitions?.length > 0 && (
                  <section id="key-definitions" style={{ marginBottom: '26px' }}>
                    <h3>Important Definitions & Terminology</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {reading.key_definitions.map((def: any, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            padding: '12px 14px',
                            borderRadius: '10px',
                            background: 'var(--bg-charcoal)',
                            border: '1px solid var(--border-subtle)',
                          }}
                        >
                          <strong style={{ color: 'var(--accent-blue)' }}>{def.term}:</strong>{' '}
                          <span>{def.definition}</span>
                          {def.context && (
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                              Context: {def.context}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Code Examples */}
                {reading.code_examples?.length > 0 && (
                  <section id="code-examples" style={{ marginBottom: '26px' }}>
                    <h3>Step-by-Step Code & Implementation Examples</h3>
                    {reading.code_examples.map((ex: any, idx: number) => (
                      <div key={idx} style={{ marginBottom: '16px' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '4px' }}>
                          {ex.title} ({ex.language})
                        </div>
                        <pre className="code-block">
                          <code>{ex.code}</code>
                        </pre>
                        <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>
                          {ex.explanation}
                        </p>
                      </div>
                    ))}
                  </section>
                )}

                {/* Comparison Tables */}
                {reading.comparison_tables?.length > 0 && (
                  <section id="comparison-tables" style={{ marginBottom: '26px' }}>
                    <h3>Comparisons & Trade-off Matrix</h3>
                    {reading.comparison_tables.map((tbl: any, idx: number) => (
                      <div key={idx} className="table-wrapper" style={{ marginTop: '10px' }}>
                        <table className="data-table">
                          <thead>
                            <tr>
                              {(tbl.headers || []).map((h: string, hi: number) => (
                                <th key={hi}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(tbl.rows || []).map((r: string[], ri: number) => (
                              <tr key={ri}>
                                {r.map((cell: string, ci: number) => (
                                  <td key={ci}>{cell}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ))}
                  </section>
                )}

                {/* Common Mistakes & Interview Questions */}
                <section id="common-mistakes" style={{ marginBottom: '26px' }}>
                  <h3>Common Pitfalls & Exam / Interview Readiness</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '18px' }}>
                    {(reading.common_mistakes || []).map((m: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          padding: '12px 14px',
                          borderRadius: '10px',
                          background: 'rgba(239, 68, 68, 0.08)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                        }}
                      >
                        <strong style={{ color: '#fca5a5' }}>Pitfall: {m.mistake}</strong>
                        <div style={{ fontSize: '0.86rem', marginTop: 4 }}>
                          <em>Why it happens:</em> {m.why_it_happens}
                        </div>
                        <div style={{ fontSize: '0.86rem', color: '#6ee7b7', marginTop: 4 }}>
                          <strong>Engineering Fix:</strong> {m.fix}
                        </div>
                      </div>
                    ))}
                  </div>

                  {(reading.interview_questions || []).map((iq: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        padding: '14px',
                        borderRadius: '10px',
                        background: 'var(--bg-charcoal)',
                        border: '1px solid var(--border-subtle)',
                        marginBottom: '10px',
                      }}
                    >
                      <strong style={{ color: 'var(--text-primary)' }}>Q: {iq.question}</strong>
                      <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: 6 }}>
                        <strong>Model Answer:</strong> {iq.model_answer}
                      </div>
                    </div>
                  ))}
                </section>

                {/* Summary */}
                <section style={{ padding: '16px', borderRadius: '12px', background: 'var(--surface-2)' }}>
                  <h3 style={{ marginTop: 0 }}>Topic Summary</h3>
                  <p style={{ marginBottom: 0 }}>{reading.summary}</p>
                </section>
              </div>
            ) : null}
          </div>

          {/* Right: Dedicated Personal Notes Manager (Independent Lifecycle) */}
          <div className="card" style={{ position: 'sticky', top: '84px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.08rem' }}>Personal Topic Notes</h3>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  Saved independently — never overwrites reading material
                </span>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleStartNewNote}
              >
                <Plus size={14} />
                <span>New Note</span>
              </button>
            </div>

            {/* Saved Notes List */}
            {notes.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px', maxHeight: 160, overflowY: 'auto' }}>
                {notes.map((n: any) => (
                  <div
                    key={n.id}
                    onClick={() => handleSelectNote(n)}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '8px',
                      background:
                        selectedNoteId === n.id
                          ? 'rgba(56, 189, 248, 0.14)'
                          : 'var(--bg-charcoal)',
                      border:
                        selectedNoteId === n.id
                          ? '1px solid var(--accent-blue)'
                          : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.84rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {n.title}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Updated {new Date(n.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteNote(n.id);
                      }}
                      title="Delete note"
                      aria-label={`Delete note ${n.title}`}
                    >
                      <Trash2 size={14} color="#fca5a5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Note Editor Form */}
            <form onSubmit={handleSaveNote}>
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label className="form-label" htmlFor="note-title-input">
                    Note Title
                  </label>
                  {noteDirty && (
                    <span className="badge badge-warning">Unsaved changes</span>
                  )}
                </div>
                <input
                  id="note-title-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g., Key Revision Points & Edge Cases"
                  value={noteTitle}
                  onChange={(e) => {
                    setNoteTitle(e.target.value);
                    setNoteDirty(true);
                  }}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="note-content-textarea">
                  Personal Study Notes
                </label>
                <textarea
                  id="note-content-textarea"
                  className="form-textarea"
                  style={{ minHeight: 220 }}
                  placeholder="Write your own takeaways, formulas, code snippets, or exam reminders here..."
                  value={noteContent}
                  onChange={(e) => {
                    setNoteContent(e.target.value);
                    setNoteDirty(true);
                  }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%' }}
                disabled={savingNote}
              >
                <Save size={16} />
                <span>{savingNote ? 'Saving Note...' : 'Save Personal Note'}</span>
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          SECTION C — EXACTLY 20 MCQs & ATTEMPT HISTORY
         ==================================================================== */}
      {activeTab === 'quiz' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
          {/* 1. EXAM INSTRUCTIONS PORTAL */}
          {examPhase === 'instructions' && (
            <div className="card card-elevated" style={{ maxWidth: 860, margin: '0 auto', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                <Award size={24} color="var(--accent-blue)" />
                <span className="badge badge-indigo">Official Topic Mastery Assessment Portal</span>
              </div>

              <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>
                {quiz?.title || `${topic.title} — 20-Question Mastery Examination`}
              </h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Verify your conceptual and practical mastery of <strong>{topic.title}</strong>. Read
                the examination specifications carefully before starting your attempt.
              </p>

              <div className="grid-4" style={{ marginBottom: '22px' }}>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>QUESTIONS</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800 }}>
                    {quiz?.question_count || 20}
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--accent-blue)' }}>
                    Validated MCQs
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>QUESTION TYPE</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>4-Option MCQ</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    Single best answer
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MAX SCORE</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800 }}>
                    {quiz?.max_score || 20} / 20
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--status-success)' }}>
                    Pass mark: {quiz?.passing_score || 14}/20 (70%)
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MARKING SCHEME</div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700 }}>+1 / 0</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    No negative marking
                  </div>
                </div>
              </div>

              <div
                style={{
                  padding: '16px',
                  borderRadius: '10px',
                  background: 'var(--bg-charcoal)',
                  border: '1px solid var(--border-subtle)',
                  marginBottom: '22px',
                }}
              >
                <strong style={{ display: 'block', marginBottom: '8px', fontSize: '0.9rem' }}>
                  Attempt Instructions:
                </strong>
                <ul style={{ paddingLeft: '20px', fontSize: '0.86rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <li>
                    This assessment contains <strong>exactly 20 multiple-choice questions</strong>{' '}
                    tailored specifically to <strong>{topic.title}</strong>.
                  </li>
                  <li>
                    Each question presents four distinct options (A, B, C, D) with one validated
                    correct answer.
                  </li>
                  <li>
                    You can navigate freely between questions 1 to 20 using the Question Palette or
                    Previous/Next controls before submitting.
                  </li>
                  <li>
                    Correct answers and explanations are strictly hidden during the active exam and
                    revealed only after submission.
                  </li>
                  <li>
                    Opening this screen does not record an attempt; an attempt is persisted only
                    when you click <strong>Submit Examination</strong>.
                  </li>
                </ul>
              </div>

              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={handleStartExam}
              >
                <Play size={18} />
                <span>Start 20-Question Examination</span>
              </button>
            </div>
          )}

          {/* 2. ACTIVE 20-QUESTION EXAM INTERFACE */}
          {examPhase === 'active' && currentQuestion && (
            <div className="grid-2" style={{ gridTemplateColumns: '1.8fr 1fr', alignItems: 'start' }}>
              {/* Question Card */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span className="badge badge-indigo">
                      Question {currentQuestionIdx + 1} of {quizQuestions.length}
                    </span>
                    <span className="badge badge-blue">{currentQuestion.category}</span>
                  </div>
                  <span className="badge badge-warning">
                    <Clock size={13} />
                    <span>Elapsed: {formatTime(examElapsedSeconds)}</span>
                  </span>
                </div>

                <div className="progress-track" style={{ marginBottom: '20px' }}>
                  <div
                    className="progress-fill"
                    style={{
                      width: `${Math.round(
                        ((currentQuestionIdx + 1) / quizQuestions.length) * 100
                      )}%`,
                    }}
                  />
                </div>

                <h3 style={{ fontSize: '1.18rem', marginBottom: '20px', lineHeight: 1.5 }}>
                  {currentQuestion.number}. {currentQuestion.question}
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
                  {currentQuestion.options.map((optText: string, optIdx: number) => {
                    const isSelected = selectedAnswers[currentQuestion.id] === optIdx;
                    const optionLetter = String.fromCharCode(65 + optIdx);
                    return (
                      <button
                        key={optIdx}
                        type="button"
                        onClick={() =>
                          setSelectedAnswers((prev) => ({
                            ...prev,
                            [currentQuestion.id]: optIdx,
                          }))
                        }
                        style={{
                          textAlign: 'left',
                          padding: '14px 16px',
                          borderRadius: '10px',
                          background: isSelected
                            ? 'rgba(56, 189, 248, 0.16)'
                            : 'var(--bg-charcoal)',
                          border: isSelected
                            ? '2px solid var(--accent-blue)'
                            : '1px solid var(--border-default)',
                          color: 'var(--text-primary)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '12px',
                          fontSize: '0.94rem',
                        }}
                      >
                        <span
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: '50%',
                            background: isSelected
                              ? 'var(--accent-blue)'
                              : 'var(--surface-2)',
                            color: isSelected ? '#070a14' : 'var(--text-secondary)',
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          {optionLetter}
                        </span>
                        <span style={{ paddingTop: 2 }}>{optText}</span>
                      </button>
                    );
                  })}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setCurrentQuestionIdx((i) => Math.max(0, i - 1))}
                    disabled={currentQuestionIdx === 0}
                  >
                    <ChevronLeft size={16} />
                    <span>Previous</span>
                  </button>

                  {currentQuestionIdx < quizQuestions.length - 1 ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() =>
                        setCurrentQuestionIdx((i) =>
                          Math.min(quizQuestions.length - 1, i + 1)
                        )
                      }
                    >
                      <span>Next Question</span>
                      <ChevronRight size={16} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleSubmitExam}
                      disabled={submittingQuiz}
                    >
                      <CheckCircle2 size={16} />
                      <span>{submittingQuiz ? 'Grading Exam...' : 'Submit Examination'}</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Question Navigator Palette & Submit Box */}
              <div className="card">
                <h3 style={{ fontSize: '1.05rem', marginBottom: '8px' }}>
                  Question Palette (1–{quizQuestions.length})
                </h3>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  Answered: <strong>{Object.keys(selectedAnswers).length}</strong> /{' '}
                  {quizQuestions.length} • Unanswered:{' '}
                  <strong>{quizQuestions.length - Object.keys(selectedAnswers).length}</strong>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(5, 1fr)',
                    gap: '8px',
                    marginBottom: '20px',
                  }}
                >
                  {quizQuestions.map((q: any, idx: number) => {
                    const answered = selectedAnswers[q.id] !== undefined;
                    const isCurrent = idx === currentQuestionIdx;
                    return (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => setCurrentQuestionIdx(idx)}
                        style={{
                          height: 38,
                          borderRadius: '8px',
                          fontWeight: 700,
                          fontSize: '0.84rem',
                          cursor: 'pointer',
                          border: isCurrent
                            ? '2px solid var(--accent-blue)'
                            : '1px solid var(--border-subtle)',
                          background: answered
                            ? 'var(--accent-indigo)'
                            : 'var(--bg-charcoal)',
                          color: '#fff',
                        }}
                      >
                        {idx + 1}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleSubmitExam}
                  disabled={submittingQuiz}
                >
                  <CheckCircle2 size={16} />
                  <span>
                    {submittingQuiz ? 'Submitting & Grading...' : 'Submit Examination Now'}
                  </span>
                </button>
              </div>
            </div>
          )}

          {/* 3. GRADED EXAM RESULTS & DETAILED 20-QUESTION ANSWER REVIEW */}
          {examPhase === 'results' && activeAttemptResult && (
            <div className="card card-elevated">
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '14px', marginBottom: '20px' }}>
                <div>
                  <span
                    className={`badge ${
                      activeAttemptResult.passed ? 'badge-success' : 'badge-warning'
                    }`}
                    style={{ marginBottom: '6px' }}
                  >
                    {activeAttemptResult.passed
                      ? 'PASSED — TOPIC MASTERY VERIFIED'
                      : 'COMPLETED — REVIEW EXPLANATIONS & RETAKE'}
                  </span>
                  <h2 style={{ fontSize: '1.5rem' }}>
                    Score: {activeAttemptResult.score} / {activeAttemptResult.max_score} (
                    {activeAttemptResult.percentage}%)
                  </h2>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setExamPhase('instructions')}
                  >
                    Exam Overview
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleStartExam}
                  >
                    <RefreshCw size={15} />
                    <span>Retake 20-MCQ Exam</span>
                  </button>
                </div>
              </div>

              <div className="grid-4" style={{ marginBottom: '24px' }}>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <div style={{ fontSize: '0.75rem', color: '#6ee7b7' }}>CORRECT ANSWERS</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#6ee7b7' }}>
                    {activeAttemptResult.correct_count}
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <div style={{ fontSize: '0.75rem', color: '#fca5a5' }}>INCORRECT ANSWERS</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fca5a5' }}>
                    {activeAttemptResult.incorrect_count}
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                  <div style={{ fontSize: '0.75rem', color: '#fcd34d' }}>UNANSWERED</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fcd34d' }}>
                    {activeAttemptResult.unanswered_count}
                  </div>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-charcoal)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TIME TAKEN</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800 }}>
                    {formatTime(activeAttemptResult.duration_seconds || 0)}
                  </div>
                </div>
              </div>

              <h3 style={{ fontSize: '1.15rem', marginBottom: '14px' }}>
                Detailed Question-by-Question Review & Explanations
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {(activeAttemptResult.review_items || []).map((item: any, idx: number) => {
                  const statusColor =
                    item.status === 'correct'
                      ? 'rgba(16, 185, 129, 0.35)'
                      : item.status === 'incorrect'
                      ? 'rgba(239, 68, 68, 0.35)'
                      : 'rgba(245, 158, 11, 0.35)';

                  return (
                    <div
                      key={idx}
                      style={{
                        padding: '16px',
                        borderRadius: '12px',
                        background: 'var(--bg-charcoal)',
                        border: `1px solid ${statusColor}`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <strong>
                          Question {item.number}: {item.question}
                        </strong>
                        <span
                          className={`badge ${
                            item.status === 'correct'
                              ? 'badge-success'
                              : item.status === 'incorrect'
                              ? 'badge-danger'
                              : 'badge-warning'
                          }`}
                        >
                          {item.status.toUpperCase()}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '8px', margin: '10px 0' }}>
                        {(item.options || []).map((opt: string, oIdx: number) => {
                          const isCorrectOpt = oIdx === item.correct_index;
                          const isUserSelected = oIdx === item.selected_index;
                          let bg = 'var(--surface-1)';
                          let border = '1px solid var(--border-subtle)';
                          if (isCorrectOpt) {
                            bg = 'rgba(16, 185, 129, 0.16)';
                            border = '1px solid var(--status-success)';
                          } else if (isUserSelected && !isCorrectOpt) {
                            bg = 'rgba(239, 68, 68, 0.16)';
                            border = '1px solid var(--status-danger)';
                          }
                          return (
                            <div
                              key={oIdx}
                              style={{
                                padding: '8px 12px',
                                borderRadius: '8px',
                                background: bg,
                                border,
                                fontSize: '0.85rem',
                              }}
                            >
                              <strong>{String.fromCharCode(65 + oIdx)}.</strong> {opt}{' '}
                              {isCorrectOpt && (
                                <strong style={{ color: '#6ee7b7', marginLeft: 6 }}>
                                  ✓ Correct Answer
                                </strong>
                              )}
                              {isUserSelected && !isCorrectOpt && (
                                <strong style={{ color: '#fca5a5', marginLeft: 6 }}>
                                  ✗ Your Choice
                                </strong>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
                        <strong style={{ color: 'var(--accent-blue)' }}>Explanation:</strong>{' '}
                        {item.explanation}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* PRACTICE ATTEMPTS HISTORY */}
          <div className="card">
            <h3 style={{ fontSize: '1.15rem', marginBottom: '12px' }}>
              Practice Attempts History for {topic.title} ({attempts.length})
            </h3>
            {attempts.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                No completed attempts recorded for this topic yet. Complete and submit the 20-MCQ
                exam above to track your progress across retakes.
              </p>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Attempt Date</th>
                      <th>Score</th>
                      <th>Breakdown (Correct / Wrong / Unanswered)</th>
                      <th>Duration</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempts.map((att: any) => (
                      <tr key={att.id}>
                        <td>{new Date(att.created_at).toLocaleString()}</td>
                        <td>
                          <strong>
                            {att.score} / {att.max_score}
                          </strong>{' '}
                          ({att.percentage}%)
                        </td>
                        <td>
                          <span style={{ color: '#6ee7b7' }}>{att.correct_count} Correct</span> •{' '}
                          <span style={{ color: '#fca5a5' }}>{att.incorrect_count} Wrong</span> •{' '}
                          <span style={{ color: '#fcd34d' }}>
                            {att.unanswered_count} Unanswered
                          </span>
                        </td>
                        <td>{formatTime(att.duration_seconds || 0)}</td>
                        <td>
                          <span
                            className={`badge ${
                              att.passed ? 'badge-success' : 'badge-warning'
                            }`}
                          >
                            {att.passed ? 'Passed' : 'Below 70%'}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleReviewHistoricalAttempt(att.id)}
                            >
                              <Eye size={14} />
                              <span>Review Answers</span>
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDeleteAttempt(att.id)}
                              title="Delete this attempt"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Overwrite Confirmation Modal when Regenerating User-Edited Reading Material */}
      {showOverwriteModal && (
        <div className="modal-backdrop" onClick={() => setShowOverwriteModal(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', color: 'var(--status-warning)' }}>
              <AlertTriangle size={22} />
              <h3 style={{ margin: 0 }}>Overwrite Your Personal Edits?</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              You have saved custom modifications to this topic's reading material. Regenerating
              will replace the reading guide with a fresh AI generation (your separate Personal
              Notes will remain untouched). Do you want to proceed?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowOverwriteModal(false)}
              >
                Keep My Edits
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => handleRegenerateReading(true)}
              >
                Confirm Overwrite & Regenerate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

