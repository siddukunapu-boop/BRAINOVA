import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Clock,
  Edit3,
  Trash2,
  Plus,
  RefreshCw,
  BookOpen,
  Video,
  CheckSquare,
  ExternalLink,
  Sliders,
  Play,
  Award,
  Sparkles,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const RoadmapDetailPage: React.FC = () => {
  const { roadmapId } = useParams<{ roadmapId: string }>();
  const [searchParams] = useSearchParams();
  const { addToast } = useApp();
  const navigate = useNavigate();

  const [roadmap, setRoadmap] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({});

  // Same-Page Expandable Topic Accordion State (Part 7)
  const [expandedTopics, setExpandedTopics] = useState<Record<string, boolean>>({});
  const [topicDetailsMap, setTopicDetailsMap] = useState<Record<string, any>>({});
  const [loadingTopicMap, setLoadingTopicMap] = useState<Record<string, boolean>>({});
  const [activeTopicTabMap, setActiveTopicTabMap] = useState<
    Record<string, 'tutorial' | 'reading' | 'mcqs'>
  >({});
  const [showInlineEmbedMap, setShowInlineEmbedMap] = useState<Record<string, boolean>>({});

  // Inline Topic 20-MCQ Quiz States (keyed by topicId)
  const [quizAnswersMap, setQuizAnswersMap] = useState<Record<string, Record<string, number>>>({});
  const [quizResultMap, setQuizResultMap] = useState<Record<string, any>>({});
  const [submittingQuizMap, setSubmittingQuizMap] = useState<Record<string, boolean>>({});

  // Edit Roadmap Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');

  // Add Topic Modal
  const [addingTopicPhaseId, setAddingTopicPhaseId] = useState<string | null>(null);
  const [newTopicTitle, setNewTopicTitle] = useState('');
  const [newTopicDesc, setNewTopicDesc] = useState('');
  const [newTopicHours, setNewTopicHours] = useState(8);

  // Delete Topic Confirmation
  const [deletingTopic, setDeletingTopic] = useState<any | null>(null);

  const fetchRoadmap = async (silent = false) => {
    if (!roadmapId) return;
    if (!silent) setLoading(true);
    try {
      const res = await apiRequest<{ roadmap: any }>(`/api/roadmaps/${roadmapId}`);
      setRoadmap(res.roadmap);
      setEditTitle(res.roadmap.title);
      setEditDesc(res.roadmap.description);
      const exp: Record<string, boolean> = {};
      (res.roadmap.phases || []).forEach((p: any) => {
        exp[p.id] = true;
      });
      setExpandedPhases((prev) => (Object.keys(prev).length > 0 ? prev : exp));

      // Check if URL requests auto-expanding a specific topic (?expand=<topicId>&tab=...)
      const expandTopicId = searchParams.get('expand');
      const requestedTab = searchParams.get('tab') as 'tutorial' | 'reading' | 'mcqs' | null;
      if (expandTopicId && !expandedTopics[expandTopicId]) {
        handleToggleExpandTopic(expandTopicId, requestedTab || 'tutorial', true);
      }
    } catch (err: any) {
      addToast(err.message || 'Roadmap not found.', 'error');
      navigate('/roadmaps');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRoadmap();
  }, [roadmapId]);

  // Auto-refresh if background jobs are still running
  useEffect(() => {
    if (!roadmap) return;
    const summary = roadmap.jobs_summary || {};
    if ((summary.queued || 0) + (summary.processing || 0) > 0) {
      const timer = setTimeout(() => {
        fetchRoadmap(true);
      }, 2800);
      return () => clearTimeout(timer);
    }
  }, [roadmap]);

  const loadTopicDetails = async (topicId: string) => {
    setLoadingTopicMap((prev) => ({ ...prev, [topicId]: true }));
    try {
      const res = await apiRequest<{ topic: any }>(`/api/topics/${topicId}?auto_prepare=true`);
      setTopicDetailsMap((prev) => ({ ...prev, [topicId]: res.topic }));
    } catch (err: any) {
      addToast(err.message || 'Failed to load topic resources.', 'error');
    } finally {
      setLoadingTopicMap((prev) => ({ ...prev, [topicId]: false }));
    }
  };

  const handleToggleExpandTopic = (
    topicId: string,
    defaultTab: 'tutorial' | 'reading' | 'mcqs' = 'tutorial',
    forceOpen = false
  ) => {
    const currentlyOpen = Boolean(expandedTopics[topicId]);
    const nextOpen = forceOpen ? true : !currentlyOpen;
    setExpandedTopics((prev) => ({ ...prev, [topicId]: nextOpen }));
    if (nextOpen) {
      setActiveTopicTabMap((prev) => ({
        ...prev,
        [topicId]: prev[topicId] || defaultTab,
      }));
      loadTopicDetails(topicId);
    }
  };

  const handleSubmitTopicQuiz = async (topicId: string, quizId: string) => {
    if (submittingQuizMap[topicId]) return;
    setSubmittingQuizMap((prev) => ({ ...prev, [topicId]: true }));
    try {
      const answers = quizAnswersMap[topicId] || {};
      const res = await apiRequest<{ attempt: any }>(`/api/topics/${topicId}/quiz/submit`, {
        method: 'POST',
        body: JSON.stringify({
          answers,
          duration_seconds: 180,
        }),
      });
      setQuizResultMap((prev) => ({ ...prev, [topicId]: res.attempt }));
      addToast(
        `Exam Graded: ${res.attempt.score}/${res.attempt.max_score} (${res.attempt.percentage}%)`,
        res.attempt.passed ? 'success' : 'info'
      );
      loadTopicDetails(topicId);
      fetchRoadmap(true);
    } catch (err: any) {
      addToast(err.message || 'Failed to grade quiz.', 'error');
    } finally {
      setSubmittingQuizMap((prev) => ({ ...prev, [topicId]: false }));
    }
  };

  const handleRegenerateTopicQuiz = async (topicId: string) => {
    setLoadingTopicMap((prev) => ({ ...prev, [topicId]: true }));
    try {
      await apiRequest(`/api/topics/${topicId}/quiz/regenerate`, { method: 'POST' });
      setQuizAnswersMap((prev) => ({ ...prev, [topicId]: {} }));
      setQuizResultMap((prev) => ({ ...prev, [topicId]: null }));
      await loadTopicDetails(topicId);
      addToast('Generated fresh 20-question MCQ examination!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Quiz regeneration failed.', 'error');
    } finally {
      setLoadingTopicMap((prev) => ({ ...prev, [topicId]: false }));
    }
  };

  const handleSaveRoadmapEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roadmapId || !editTitle.trim()) return;
    try {
      const res = await apiRequest<{ roadmap: any }>(`/api/roadmaps/${roadmapId}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: editTitle.trim(),
          description: editDesc.trim(),
        }),
      });
      setRoadmap(res.roadmap);
      setShowEditModal(false);
      addToast('Updated roadmap details.', 'success');
    } catch (err: any) {
      addToast(err.message || 'Update failed.', 'error');
    }
  };

  const handleAddTopicSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roadmapId || !addingTopicPhaseId || !newTopicTitle.trim()) return;
    try {
      const res = await apiRequest<{ roadmap: any }>(`/api/roadmaps/${roadmapId}/topics`, {
        method: 'POST',
        body: JSON.stringify({
          phase_id: addingTopicPhaseId,
          title: newTopicTitle.trim(),
          description: newTopicDesc.trim() || `Study module on ${newTopicTitle.trim()}`,
          estimated_hours: Number(newTopicHours) || 6,
        }),
      });
      setRoadmap(res.roadmap);
      setAddingTopicPhaseId(null);
      setNewTopicTitle('');
      setNewTopicDesc('');
      addToast('Added topic and prepared learning resources!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Could not add topic.', 'error');
    }
  };

  const handleToggleTopicStatus = async (topic: any) => {
    const nextStatus = topic.status === 'completed' ? 'in_progress' : 'completed';
    try {
      await apiRequest(`/api/topics/${topic.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: nextStatus }),
      });
      addToast(
        nextStatus === 'completed'
          ? `Marked "${topic.title}" as completed!`
          : `Reopened "${topic.title}".`,
        'success'
      );
      fetchRoadmap(true);
    } catch (err: any) {
      addToast(err.message || 'Failed to update status.', 'error');
    }
  };

  const handleDeleteTopicConfirm = async () => {
    if (!deletingTopic) return;
    try {
      await apiRequest(`/api/topics/${deletingTopic.id}`, { method: 'DELETE' });
      addToast(`Deleted topic "${deletingTopic.title}".`, 'info');
      setDeletingTopic(null);
      fetchRoadmap(true);
    } catch (err: any) {
      addToast(err.message || 'Could not delete topic.', 'error');
    }
  };

  // Render Educational SVG Diagram for Topic Reading Material (Part 7)
  const renderEducationalDiagram = (diag: any, idx: number) => {
    const nodes: any[] = diag.nodes || [];
    return (
      <div
        key={diag.id || idx}
        style={{
          padding: '18px',
          borderRadius: '14px',
          background: 'var(--bg-charcoal)',
          border: '1px solid var(--border-strong)',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
          <strong style={{ color: 'var(--accent-blue)', fontSize: '0.96rem' }}>
            {diag.title || 'Educational Architecture Diagram'}
          </strong>
          <span className="badge badge-indigo">
            {diag.type === 'process' ? 'Step-by-Step Process Flow' : 'System Architecture Diagram'}
          </span>
        </div>

        <div style={{ width: '100%', overflowX: 'auto', padding: '6px 0' }}>
          <svg
            width={780}
            height={145}
            viewBox="0 0 780 145"
            style={{ display: 'block', margin: '0 auto' }}
          >
            <defs>
              <linearGradient id={`nodeGrad_${idx}`} x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#172347" />
                <stop offset="100%" stopColor="#0d142c" />
              </linearGradient>
            </defs>
            {nodes.slice(0, 4).map((nd: any, nIdx: number) => {
              const x = 14 + nIdx * 192;
              const y = 18;
              return (
                <g key={nIdx}>
                  {nIdx < Math.min(3, nodes.length - 1) && (
                    <g>
                      <line
                        x1={x + 168}
                        y1={y + 48}
                        x2={x + 190}
                        y2={y + 48}
                        stroke="#38bdf8"
                        strokeWidth="2.5"
                      />
                      <polygon
                        points={`${x + 190},${y + 48} ${x + 182},${y + 43} ${x + 182},${y + 53}`}
                        fill="#38bdf8"
                      />
                    </g>
                  )}
                  <rect
                    x={x}
                    y={y}
                    width={168}
                    height={96}
                    rx={12}
                    fill={`url(#nodeGrad_${idx})`}
                    stroke={nIdx === 0 ? '#38bdf8' : '#6366f1'}
                    strokeWidth="2"
                  />
                  <text
                    x={x + 12}
                    y={y + 28}
                    fill="#38bdf8"
                    fontSize="11.5"
                    fontWeight="800"
                  >
                    {String(nd.label || `Stage ${nIdx + 1}`).slice(0, 22)}
                  </text>
                  <foreignObject x={x + 12} y={y + 36} width={144} height={54}>
                    <div
                      style={{
                        color: '#cbd5e1',
                        fontSize: '10.5px',
                        lineHeight: 1.3,
                        overflow: 'hidden',
                      }}
                    >
                      {String(nd.detail || '').slice(0, 68)}
                    </div>
                  </foreignObject>
                </g>
              );
            })}
          </svg>
        </div>

        {diag.caption && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '6px', textAlign: 'center' }}>
            {diag.caption}
          </div>
        )}
      </div>
    );
  };

  if (loading || !roadmap) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading roadmap curriculum...</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Breadcrumb & Overview Card */}
      <div className="card card-elevated">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '12px' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => navigate('/roadmaps')}
          >
            <ArrowLeft size={15} />
            <span>Back to AI Roadmaps</span>
          </button>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => navigate(`/customized-roadmap?roadmap=${roadmap.id}`)}
            >
              <Sliders size={14} color="var(--accent-blue)" />
              <span>Customize Roadmap Resources</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => fetchRoadmap(true)}
            >
              <RefreshCw size={14} />
              <span>Refresh</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowEditModal(true)}
            >
              <Edit3 size={14} />
              <span>Edit Roadmap</span>
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
          <span className="badge badge-indigo">{roadmap.target_role}</span>
          <span className="badge badge-blue">{roadmap.skill_level}</span>
          <span className="badge badge-success">
            {roadmap.completed_topics} / {roadmap.total_topics} Topics Completed (
            {roadmap.progress_percent}%)
          </span>
        </div>

        <h1 style={{ fontSize: '1.75rem', marginBottom: '8px' }}>{roadmap.title}</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '14px' }}>
          {roadmap.description}
        </p>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${roadmap.progress_percent}%` }} />
        </div>
      </div>

      {/* Expandable Phases & Same-Page Expandable Topic Accordions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {(roadmap.phases || []).map((phase: any) => {
          const isPhaseOpen = expandedPhases[phase.id] !== false;
          return (
            <div key={phase.id} className="card" style={{ padding: '20px' }}>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px',
                  cursor: 'pointer',
                }}
                onClick={() =>
                  setExpandedPhases((prev) => ({ ...prev, [phase.id]: !isPhaseOpen }))
                }
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <span className="badge badge-indigo">Phase {phase.phase_order}</span>
                    <h2 style={{ fontSize: '1.22rem' }}>{phase.title}</h2>
                  </div>
                  <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>
                    {phase.description}
                  </p>
                </div>

                <div
                  style={{ display: 'flex', alignItems: 'center', gap: '10px' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="badge badge-blue">
                    {phase.completed_topics}/{phase.total_topics} completed ({phase.progress_percent}
                    %)
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setAddingTopicPhaseId(phase.id)}
                  >
                    <Plus size={14} />
                    <span>Add Topic</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() =>
                      setExpandedPhases((prev) => ({ ...prev, [phase.id]: !isPhaseOpen }))
                    }
                    aria-label="Toggle phase"
                  >
                    {isPhaseOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>
              </div>

              {isPhaseOpen && (
                <div style={{ marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {(phase.topics || []).map((topic: any) => {
                    const resStatus = topic.resources_status || {};
                    const isTopicExpanded = Boolean(expandedTopics[topic.id]);
                    const detail = topicDetailsMap[topic.id];
                    const isTopicLoading = Boolean(loadingTopicMap[topic.id]);
                    const activeTab = activeTopicTabMap[topic.id] || 'tutorial';

                    return (
                      <div
                        key={topic.id}
                        className={`topic-accordion-card ${isTopicExpanded ? 'expanded' : ''}`}
                      >
                        {/* Topic Summary Row (Clicking expands inline on the same page!) */}
                        <div
                          className="topic-accordion-header"
                          onClick={() => handleToggleExpandTopic(topic.id, 'tutorial')}
                        >
                          <div style={{ flex: 1, minWidth: 260 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
                              <span className="badge badge-indigo">
                                Topic {phase.phase_order}.{topic.topic_order}
                              </span>
                              <span className="badge badge-blue">{topic.difficulty}</span>
                              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                                <Clock size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                                {topic.estimated_hours}h
                              </span>
                              {resStatus.best_attempt && (
                                <span
                                  className={`badge ${
                                    resStatus.best_attempt.passed
                                      ? 'badge-success'
                                      : 'badge-warning'
                                  }`}
                                >
                                  Best Exam: {resStatus.best_attempt.score}/
                                  {resStatus.best_attempt.max_score} (
                                  {resStatus.best_attempt.percentage}%)
                                </span>
                              )}
                            </div>

                            <h3 style={{ fontSize: '1.1rem', marginBottom: '4px' }}>
                              {topic.title}
                            </h3>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                              {topic.description}
                            </p>

                            {/* Quick Section Pill Triggers (Click any pill to expand straight to that section inline) */}
                            <div
                              style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                className={`btn btn-sm ${
                                  isTopicExpanded && activeTab === 'tutorial'
                                    ? 'btn-primary'
                                    : 'btn-secondary'
                                }`}
                                onClick={() => handleToggleExpandTopic(topic.id, 'tutorial', true)}
                              >
                                <Video size={13} />
                                <span>1. Tutorial</span>
                              </button>

                              <button
                                type="button"
                                className={`btn btn-sm ${
                                  isTopicExpanded && activeTab === 'reading'
                                    ? 'btn-primary'
                                    : 'btn-secondary'
                                }`}
                                onClick={() => handleToggleExpandTopic(topic.id, 'reading', true)}
                              >
                                <BookOpen size={13} />
                                <span>2. Reading Material</span>
                              </button>

                              <button
                                type="button"
                                className={`btn btn-sm ${
                                  isTopicExpanded && activeTab === 'mcqs'
                                    ? 'btn-primary'
                                    : 'btn-secondary'
                                }`}
                                onClick={() => handleToggleExpandTopic(topic.id, 'mcqs', true)}
                              >
                                <CheckSquare size={13} />
                                <span>3. MCQs (20 Questions)</span>
                              </button>
                            </div>
                          </div>

                          <div
                            style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              className={`btn btn-sm ${
                                topic.status === 'completed' ? 'btn-secondary' : 'btn-ghost'
                              }`}
                              onClick={() => handleToggleTopicStatus(topic)}
                            >
                              <CheckCircle2
                                size={15}
                                color={
                                  topic.status === 'completed'
                                    ? 'var(--status-success)'
                                    : 'var(--text-muted)'
                                }
                              />
                              <span>
                                {topic.status === 'completed' ? 'Completed' : 'Mark Complete'}
                              </span>
                            </button>

                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleToggleExpandTopic(topic.id, activeTab)}
                            >
                              {isTopicExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                              <span>{isTopicExpanded ? 'Collapse Topic' : 'Expand Topic'}</span>
                            </button>

                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => setDeletingTopic(topic)}
                              title="Delete topic"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>

                        {/* ============================================================
                            INLINE EXPANDED TOPIC BODY (SAME-PAGE ACCORDION — PART 7)
                           ============================================================ */}
                        {isTopicExpanded && (
                          <div className="topic-accordion-body">
                            {/* Sub-navigation bar inside expanded topic */}
                            <div
                              style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                gap: '10px',
                                paddingBottom: '14px',
                                marginBottom: '18px',
                                borderBottom: '1px solid var(--border-subtle)',
                              }}
                            >
                              <div className="tabs-bar">
                                <button
                                  type="button"
                                  className={`tab-btn ${activeTab === 'tutorial' ? 'active' : ''}`}
                                  onClick={() =>
                                    setActiveTopicTabMap((prev) => ({
                                      ...prev,
                                      [topic.id]: 'tutorial',
                                    }))
                                  }
                                >
                                  <Video size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                                  1. Tutorial
                                </button>
                                <button
                                  type="button"
                                  className={`tab-btn ${activeTab === 'reading' ? 'active' : ''}`}
                                  onClick={() =>
                                    setActiveTopicTabMap((prev) => ({
                                      ...prev,
                                      [topic.id]: 'reading',
                                    }))
                                  }
                                >
                                  <BookOpen size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                                  2. Reading Material
                                </button>
                                <button
                                  type="button"
                                  className={`tab-btn ${activeTab === 'mcqs' ? 'active' : ''}`}
                                  onClick={() =>
                                    setActiveTopicTabMap((prev) => ({
                                      ...prev,
                                      [topic.id]: 'mcqs',
                                    }))
                                  }
                                >
                                  <CheckSquare size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                                  3. MCQs (20 Questions)
                                </button>
                              </div>

                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() =>
                                  navigate(
                                    `/customized-roadmap?roadmap=${roadmap.id}&topic=${topic.id}`
                                  )
                                }
                              >
                                <Sliders size={14} color="var(--accent-blue)" />
                                <span>Customize Tutorial / Reading</span>
                              </button>
                            </div>

                            {isTopicLoading && !detail ? (
                              <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                Loading topic Tutorial, Reading Material, and 20-MCQ Exam...
                              </div>
                            ) : detail ? (
                              <>
                                {/* ====================================================
                                    SECTION 1: TUTORIAL (CONCISE, CLUTTER-FREE, DIRECT YOUTUBE)
                                   ==================================================== */}
                                {activeTab === 'tutorial' && (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                                    {(detail.tutorials || []).slice(0, 1).map((tut: any) => {
                                      const badgeType =
                                        tut.source_badge ||
                                        (tut.is_user_added ? 'CUSTOMIZED' : 'ORIGINAL');
                                      const showEmbed = Boolean(showInlineEmbedMap[tut.id]);

                                      return (
                                        <div
                                          key={tut.id}
                                          style={{
                                            padding: '18px',
                                            borderRadius: '14px',
                                            background: 'var(--surface-1)',
                                            border: '1px solid var(--border-default)',
                                          }}
                                        >
                                          <div
                                            style={{
                                              display: 'flex',
                                              flexWrap: 'wrap',
                                              gap: '18px',
                                              alignItems: 'center',
                                              justifyContent: 'space-between',
                                            }}
                                          >
                                            {/* Clean Thumbnail Preview */}
                                            <a
                                              href={tut.url}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              style={{
                                                width: 240,
                                                height: 135,
                                                borderRadius: '12px',
                                                overflow: 'hidden',
                                                position: 'relative',
                                                flexShrink: 0,
                                                border: '1px solid var(--border-strong)',
                                                background: '#050811',
                                                display: 'block',
                                              }}
                                            >
                                              {tut.video_id && (
                                                <img
                                                  src={`https://i.ytimg.com/vi/${tut.video_id}/hqdefault.jpg`}
                                                  alt={tut.title}
                                                  style={{
                                                    width: '100%',
                                                    height: '100%',
                                                    objectFit: 'cover',
                                                  }}
                                                />
                                              )}
                                              <div
                                                style={{
                                                  position: 'absolute',
                                                  inset: 0,
                                                  background: 'rgba(5, 8, 17, 0.35)',
                                                  display: 'flex',
                                                  alignItems: 'center',
                                                  justifyContent: 'center',
                                                }}
                                              >
                                                <div
                                                  style={{
                                                    width: 46,
                                                    height: 46,
                                                    borderRadius: '50%',
                                                    background: 'var(--gradient-brand)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    color: '#fff',
                                                  }}
                                                >
                                                  <Play size={20} fill="#fff" />
                                                </div>
                                              </div>
                                            </a>

                                            {/* Concise Metadata (Title, Channel, Badge, Duration) */}
                                            <div style={{ flex: 1, minWidth: 240 }}>
                                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                                                <span
                                                  className={
                                                    badgeType === 'CUSTOMIZED'
                                                      ? 'badge-customized'
                                                      : 'badge-original'
                                                  }
                                                >
                                                  {badgeType}
                                                </span>
                                                <span className="badge badge-indigo">
                                                  {tut.duration || '25m'}
                                                </span>
                                              </div>

                                              <h4 style={{ fontSize: '1.18rem', marginBottom: '6px' }}>
                                                {tut.title}
                                              </h4>

                                              <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                                                Channel: <strong>{tut.channel}</strong>
                                              </div>

                                              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                                                <a
                                                  href={tut.url}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className="btn btn-primary btn-sm"
                                                >
                                                  <ExternalLink size={14} />
                                                  <span>Watch Tutorial on YouTube</span>
                                                </a>

                                                <button
                                                  type="button"
                                                  className="btn btn-secondary btn-sm"
                                                  onClick={() =>
                                                    setShowInlineEmbedMap((prev) => ({
                                                      ...prev,
                                                      [tut.id]: !showEmbed,
                                                    }))
                                                  }
                                                >
                                                  <Play size={14} />
                                                  <span>
                                                    {showEmbed
                                                      ? 'Hide Inline Player'
                                                      : 'Play Inline Here'}
                                                  </span>
                                                </button>
                                              </div>
                                            </div>
                                          </div>

                                          {showEmbed && tut.video_id && (
                                            <div
                                              style={{
                                                marginTop: '16px',
                                                borderRadius: '12px',
                                                overflow: 'hidden',
                                                aspectRatio: '16 / 9',
                                                maxWidth: 760,
                                                border: '1px solid var(--border-strong)',
                                              }}
                                            >
                                              <iframe
                                                title={tut.title}
                                                width="100%"
                                                height="100%"
                                                src={`https://www.youtube.com/embed/${tut.video_id}?rel=0`}
                                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                allowFullScreen
                                                style={{ border: 0 }}
                                              />
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}

                                {/* ====================================================
                                    SECTION 2: READING MATERIAL (WITH DIAGRAMS & BADGE)
                                   ==================================================== */}
                                {activeTab === 'reading' && detail.reading && (() => {
                                  const r = detail.reading;
                                  const badgeType =
                                    r.source_badge ||
                                    (r.has_custom_reading ? 'CUSTOMIZED' : 'ORIGINAL');

                                  return (
                                    <div
                                      className="reading-prose"
                                      style={{
                                        maxWidth: '100%',
                                        padding: '20px',
                                        borderRadius: '14px',
                                        background: 'var(--surface-1)',
                                        border: '1px solid var(--border-default)',
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: 'flex',
                                          justifyContent: 'space-between',
                                          alignItems: 'center',
                                          flexWrap: 'wrap',
                                          gap: '10px',
                                          marginBottom: '16px',
                                          paddingBottom: '12px',
                                          borderBottom: '1px solid var(--border-subtle)',
                                        }}
                                      >
                                        <div>
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                            <span
                                              className={
                                                badgeType === 'CUSTOMIZED'
                                                  ? 'badge-customized'
                                                  : 'badge-original'
                                              }
                                            >
                                              {badgeType}
                                            </span>
                                            <span className="badge badge-indigo">
                                              Topic Reading Material
                                            </span>
                                          </div>
                                          <h3 style={{ margin: 0, fontSize: '1.35rem' }}>
                                            {r.has_custom_reading && r.custom_title
                                              ? r.custom_title
                                              : r.title}
                                          </h3>
                                        </div>

                                        <button
                                          type="button"
                                          className="btn btn-secondary btn-sm"
                                          onClick={() =>
                                            navigate(
                                              `/customized-roadmap?roadmap=${roadmap.id}&topic=${topic.id}`
                                            )
                                          }
                                        >
                                          <Edit3 size={14} />
                                          <span>
                                            {r.has_custom_reading
                                              ? 'Edit / Restore Reading in Customized Roadmap'
                                              : 'Add Customized Reading Material'}
                                          </span>
                                        </button>
                                      </div>

                                      {/* If user saved Customized Reading Material, render it prominently */}
                                      {r.has_custom_reading && r.custom_markdown ? (
                                        <div
                                          style={{
                                            padding: '18px',
                                            borderRadius: '12px',
                                            background: 'var(--bg-charcoal)',
                                            border: '1px solid rgba(168, 85, 247, 0.45)',
                                            whiteSpace: 'pre-wrap',
                                            lineHeight: 1.75,
                                            color: 'var(--text-primary)',
                                            marginBottom: '20px',
                                          }}
                                        >
                                          {r.custom_markdown}
                                        </div>
                                      ) : (
                                        <>
                                          {/* Topic Introduction */}
                                          <div style={{ marginBottom: '20px' }}>
                                            <h3>Topic Introduction & Overview</h3>
                                            <p style={{ color: 'var(--text-primary)', fontSize: '1.02rem' }}>
                                              {r.overview}
                                            </p>
                                          </div>

                                          {/* Educational SVG Diagrams */}
                                          {r.diagrams && r.diagrams.length > 0 && (
                                            <div style={{ marginBottom: '22px' }}>
                                              <h3>Visual Architecture & Process Diagrams</h3>
                                              {r.diagrams.map((diag: any, idx: number) =>
                                                renderEducationalDiagram(diag, idx)
                                              )}
                                            </div>
                                          )}

                                          {/* Core Concepts & Step-by-Step Explanations */}
                                          {(r.sections || []).map((sec: any, idx: number) => (
                                            <div key={idx} style={{ marginBottom: '20px' }}>
                                              <h3>{sec.heading}</h3>
                                              <p style={{ whiteSpace: 'pre-wrap' }}>{sec.content}</p>
                                            </div>
                                          ))}

                                          {/* Key Definitions */}
                                          {r.terminology && r.terminology.length > 0 && (
                                            <div style={{ marginBottom: '20px' }}>
                                              <h3>Key Definitions & Terminology</h3>
                                              <div className="grid-2">
                                                {r.terminology.map((t: any, i: number) => (
                                                  <div
                                                    key={i}
                                                    style={{
                                                      padding: '12px',
                                                      borderRadius: '10px',
                                                      background: 'var(--bg-charcoal)',
                                                      border: '1px solid var(--border-subtle)',
                                                    }}
                                                  >
                                                    <strong style={{ color: 'var(--accent-blue)' }}>
                                                      {t.term}:
                                                    </strong>{' '}
                                                    <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                                                      {t.definition}
                                                    </span>
                                                  </div>
                                                ))}
                                              </div>
                                            </div>
                                          )}

                                          {/* Code Examples */}
                                          {r.code_examples && r.code_examples.length > 0 && (
                                            <div style={{ marginBottom: '20px' }}>
                                              <h3>Technical Implementation Examples</h3>
                                              {r.code_examples.map((ex: any, idx: number) => (
                                                <div key={idx} style={{ marginBottom: '12px' }}>
                                                  <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--accent-blue)', marginBottom: '4px' }}>
                                                    {ex.title} ({ex.language})
                                                  </div>
                                                  <pre>
                                                    <code>{ex.code}</code>
                                                  </pre>
                                                  {ex.explanation && (
                                                    <p style={{ fontSize: '0.85rem' }}>
                                                      {ex.explanation}
                                                    </p>
                                                  )}
                                                </div>
                                              ))}
                                            </div>
                                          )}

                                          {/* Common Mistakes & Key Takeaways */}
                                          <div className="grid-2" style={{ marginBottom: '18px' }}>
                                            {r.mistakes && r.mistakes.length > 0 && (
                                              <div
                                                style={{
                                                  padding: '14px',
                                                  borderRadius: '12px',
                                                  background: 'rgba(239, 68, 68, 0.08)',
                                                  border: '1px solid rgba(239, 68, 68, 0.28)',
                                                }}
                                              >
                                                <strong style={{ color: '#fca5a5' }}>
                                                  Common Mistakes to Avoid
                                                </strong>
                                                <ul style={{ paddingLeft: '18px', marginTop: '8px', fontSize: '0.86rem' }}>
                                                  {r.mistakes.map((m: string, i: number) => (
                                                    <li key={i}>{m}</li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}

                                            {r.takeaways && r.takeaways.length > 0 && (
                                              <div
                                                style={{
                                                  padding: '14px',
                                                  borderRadius: '12px',
                                                  background: 'rgba(16, 185, 129, 0.08)',
                                                  border: '1px solid rgba(16, 185, 129, 0.28)',
                                                }}
                                              >
                                                <strong style={{ color: '#6ee7b7' }}>
                                                  Key Takeaways
                                                </strong>
                                                <ul style={{ paddingLeft: '18px', marginTop: '8px', fontSize: '0.86rem' }}>
                                                  {r.takeaways.map((tk: string, i: number) => (
                                                    <li key={i}>{tk}</li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                          </div>

                                          {/* Quick Revision Summary */}
                                          <div
                                            style={{
                                              padding: '14px 18px',
                                              borderRadius: '12px',
                                              background: 'var(--bg-charcoal)',
                                              borderLeft: '4px solid var(--accent-blue)',
                                            }}
                                          >
                                            <strong>Quick Revision Summary:</strong> {r.summary}
                                          </div>
                                        </>
                                      )}
                                    </div>
                                  );
                                })()}

                                {/* ====================================================
                                    SECTION 3: MCQs (20-QUESTION AI ASSESSMENT INLINE)
                                   ==================================================== */}
                                {activeTab === 'mcqs' && detail.quiz && (() => {
                                  const quiz = detail.quiz;
                                  const questions: any[] = quiz.questions || [];
                                  const chosenMap = quizAnswersMap[topic.id] || {};
                                  const result = quizResultMap[topic.id];
                                  const isSubmitting = Boolean(submittingQuizMap[topic.id]);

                                  return (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                      <div
                                        style={{
                                          display: 'flex',
                                          flexWrap: 'wrap',
                                          justifyContent: 'space-between',
                                          alignItems: 'center',
                                          gap: '10px',
                                          padding: '14px 18px',
                                          borderRadius: '12px',
                                          background: 'var(--surface-1)',
                                          border: '1px solid var(--border-default)',
                                        }}
                                      >
                                        <div>
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                                            <span className="badge-original">ORIGINAL AI MCQS</span>
                                            <span className="badge badge-indigo">
                                              {questions.length} Questions • Pass: 70%
                                            </span>
                                          </div>
                                          <h4 style={{ margin: 0, fontSize: '1.1rem' }}>
                                            {quiz.title}
                                          </h4>
                                        </div>

                                        <div style={{ display: 'flex', gap: '8px' }}>
                                          {result && (
                                            <button
                                              type="button"
                                              className="btn btn-secondary btn-sm"
                                              onClick={() => {
                                                setQuizAnswersMap((prev) => ({
                                                  ...prev,
                                                  [topic.id]: {},
                                                }));
                                                setQuizResultMap((prev) => ({
                                                  ...prev,
                                                  [topic.id]: null,
                                                }));
                                              }}
                                            >
                                              Retake Exam
                                            </button>
                                          )}
                                          <button
                                            type="button"
                                            className="btn btn-secondary btn-sm"
                                            onClick={() => handleRegenerateTopicQuiz(topic.id)}
                                          >
                                            <Sparkles size={14} />
                                            <span>New 20-MCQ Set</span>
                                          </button>
                                        </div>
                                      </div>

                                      {/* Score Result Banner */}
                                      {result && (
                                        <div
                                          style={{
                                            padding: '16px 20px',
                                            borderRadius: '12px',
                                            background: result.passed
                                              ? 'rgba(16, 185, 129, 0.14)'
                                              : 'rgba(245, 158, 11, 0.14)',
                                            border: `1px solid ${
                                              result.passed
                                                ? 'var(--status-success)'
                                                : 'var(--status-warning)'
                                            }`,
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            flexWrap: 'wrap',
                                            gap: '12px',
                                          }}
                                        >
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <Award
                                              size={28}
                                              color={
                                                result.passed
                                                  ? 'var(--status-success)'
                                                  : 'var(--status-warning)'
                                              }
                                            />
                                            <div>
                                              <div style={{ fontWeight: 800, fontSize: '1.1rem' }}>
                                                Score: {result.score} / {result.max_score} (
                                                {result.percentage}%) —{' '}
                                                {result.passed ? 'PASSED' : 'REVIEW NEEDED'}
                                              </div>
                                              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                                Correct: {result.correct_count} • Wrong:{' '}
                                                {result.incorrect_count} • Unanswered:{' '}
                                                {result.unanswered_count}
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      )}

                                      {/* 20 Questions List */}
                                      <div
                                        style={{
                                          display: 'flex',
                                          flexDirection: 'column',
                                          gap: '12px',
                                          maxHeight: 540,
                                          overflowY: 'auto',
                                          paddingRight: '4px',
                                        }}
                                      >
                                        {questions.map((q: any, qIdx: number) => {
                                          const sel = chosenMap[q.id];
                                          const reviewItem = result?.question_results?.find(
                                            (r: any) => r.question_id === q.id
                                          );

                                          return (
                                            <div
                                              key={q.id}
                                              style={{
                                                padding: '14px',
                                                borderRadius: '12px',
                                                background: 'var(--surface-1)',
                                                border: '1px solid var(--border-subtle)',
                                              }}
                                            >
                                              <div style={{ fontWeight: 600, marginBottom: '10px', fontSize: '0.94rem' }}>
                                                {q.number || qIdx + 1}. {q.question}
                                              </div>
                                              <div className="grid-2" style={{ gap: '8px' }}>
                                                {(q.options || []).map((opt: string, oIdx: number) => {
                                                  const isChosen = sel === oIdx;
                                                  const isCorrectOpt =
                                                    reviewItem && reviewItem.correct_index === oIdx;
                                                  const isWrongChosen =
                                                    reviewItem && isChosen && !reviewItem.is_correct;

                                                  return (
                                                    <button
                                                      key={oIdx}
                                                      type="button"
                                                      onClick={() => {
                                                        if (result) return;
                                                        setQuizAnswersMap((prev) => ({
                                                          ...prev,
                                                          [topic.id]: {
                                                            ...(prev[topic.id] || {}),
                                                            [q.id]: oIdx,
                                                          },
                                                        }));
                                                      }}
                                                      style={{
                                                        textAlign: 'left',
                                                        padding: '10px 12px',
                                                        borderRadius: '8px',
                                                        background: isCorrectOpt
                                                          ? 'rgba(16, 185, 129, 0.18)'
                                                          : isWrongChosen
                                                          ? 'rgba(239, 68, 68, 0.18)'
                                                          : isChosen
                                                          ? 'rgba(56, 189, 248, 0.18)'
                                                          : 'var(--bg-charcoal)',
                                                        border: isCorrectOpt
                                                          ? '1px solid var(--status-success)'
                                                          : isWrongChosen
                                                          ? '1px solid var(--status-danger)'
                                                          : isChosen
                                                          ? '1px solid var(--accent-blue)'
                                                          : '1px solid var(--border-subtle)',
                                                        color: 'var(--text-primary)',
                                                        cursor: result ? 'default' : 'pointer',
                                                        fontSize: '0.85rem',
                                                      }}
                                                    >
                                                      <strong>
                                                        {String.fromCharCode(65 + oIdx)}.
                                                      </strong>{' '}
                                                      {opt}
                                                    </button>
                                                  );
                                                })}
                                              </div>

                                              {reviewItem && (
                                                <div
                                                  style={{
                                                    marginTop: '8px',
                                                    fontSize: '0.82rem',
                                                    color: reviewItem.is_correct
                                                      ? '#6ee7b7'
                                                      : '#fcd34d',
                                                  }}
                                                >
                                                  <strong>
                                                    {reviewItem.is_correct ? 'Correct!' : 'Explanation:'}
                                                  </strong>{' '}
                                                  {reviewItem.explanation}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>

                                      {!result && (
                                        <button
                                          type="button"
                                          className="btn btn-primary"
                                          onClick={() => handleSubmitTopicQuiz(topic.id, quiz.id)}
                                          disabled={isSubmitting}
                                        >
                                          <CheckCircle2 size={16} />
                                          <span>
                                            {isSubmitting
                                              ? 'Grading 20-MCQ Examination...'
                                              : `Submit ${questions.length}-Question Examination (${
                                                  Object.keys(chosenMap).length
                                                }/${questions.length} Answered)`}
                                          </span>
                                        </button>
                                      )}
                                    </div>
                                  );
                                })()}
                              </>
                            ) : null}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Edit Roadmap Modal */}
      {showEditModal && (
        <div className="modal-backdrop" onClick={() => setShowEditModal(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '14px' }}>Edit Roadmap Details</h3>
            <form onSubmit={handleSaveRoadmapEdit}>
              <div className="form-group">
                <label className="form-label">Roadmap Title</label>
                <input
                  type="text"
                  className="form-input"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEditModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Topic Modal */}
      {addingTopicPhaseId && (
        <div className="modal-backdrop" onClick={() => setAddingTopicPhaseId(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '14px' }}>Add Topic to Phase</h3>
            <form onSubmit={handleAddTopicSubmit}>
              <div className="form-group">
                <label className="form-label">Topic Title</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., Distributed Caching & Redis Internals"
                  value={newTopicTitle}
                  onChange={(e) => setNewTopicTitle(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  placeholder="Describe the learning objectives for this topic..."
                  value={newTopicDesc}
                  onChange={(e) => setNewTopicDesc(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Estimated Study Hours</label>
                <input
                  type="number"
                  min={1}
                  max={60}
                  className="form-input"
                  value={newTopicHours}
                  onChange={(e) => setNewTopicHours(Number(e.target.value))}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setAddingTopicPhaseId(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Add Topic & Generate Resources
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Topic Confirmation Modal */}
      {deletingTopic && (
        <div className="modal-backdrop" onClick={() => setDeletingTopic(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '10px' }}>Delete Topic "{deletingTopic.title}"?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '16px' }}>
              Deleting this topic will also remove its associated tutorial links, generated reading
              material, personal notes, and 20-MCQ attempt history for this topic.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeletingTopic(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDeleteTopicConfirm}
              >
                Delete Topic
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
