import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Compass,
  FolderOpen,
  PlayCircle,
  ArrowRight,
  Clock,
  Award,
  TrendingUp,
  RotateCcw,
  BookOpen,
  FileText,
  AlertCircle,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const DashboardPage: React.FC = () => {
  const { user, addToast } = useApp();
  const navigate = useNavigate();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiRequest('/api/dashboard');
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading your personalized dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ padding: '32px' }}>
        <p style={{ color: 'var(--status-danger)', marginBottom: '12px' }}>{error}</p>
        <button type="button" className="btn btn-primary" onClick={loadDashboard}>
          Retry
        </button>
      </div>
    );
  }

  const metrics = data?.metrics || {};
  const continueLearning = data?.continue_learning;
  const roadmaps = data?.roadmaps || [];
  const todaysTasks = data?.todays_tasks || [];
  const upcomingRevisions = data?.upcoming_revisions || [];
  const recentSources = data?.recent_sources || [];
  const recentAttempts = data?.recent_quiz_attempts || [];
  const weeklyActivity = data?.weekly_activity || [];
  const demoData = data?.demo_data;

  const maxMinutes = Math.max(30, ...weeklyActivity.map((d: any) => d.minutes || 0));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Optional Isolated Demonstration Data Banner */}
      {demoData?.is_demo && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.14)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            borderRadius: '12px',
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#fcd34d', fontSize: '0.88rem' }}>
            <AlertCircle size={18} />
            <span>{demoData.banner}</span>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => navigate('/settings')}
          >
            Manage in Settings
          </button>
        </div>
      )}

      {/* Hero Welcome & Quick Actions */}
      <div
        className="card card-elevated"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '20px',
          padding: '28px',
        }}
      >
        <div>
          <span className="badge badge-blue" style={{ marginBottom: '8px' }}>
            Target Track: {user?.target_role || 'Full Stack Developer'}
          </span>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '6px' }}>
            Welcome back, {user?.name || 'Scholar'}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Track your active roadmaps, study source-grounded materials, and verify mastery with
            20-question assessments.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/roadmaps?new=1')}
          >
            <Compass size={16} />
            <span>Create Roadmap</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/sources?upload=1')}
          >
            <FolderOpen size={16} />
            <span>Upload Source</span>
          </button>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid-4">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontWeight: 600 }}>
              OVERALL PROGRESS
            </span>
            <TrendingUp size={18} color="var(--accent-blue)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
            {metrics.overall_progress_percent || 0}%
          </div>
          <div className="progress-track" style={{ margin: '10px 0 6px' }}>
            <div
              className="progress-fill"
              style={{ width: `${metrics.overall_progress_percent || 0}%` }}
            />
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {metrics.completed_topics || 0} of {metrics.total_topics || 0} topics completed
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontWeight: 600 }}>
              ACTIVE ROADMAPS
            </span>
            <Compass size={18} color="var(--accent-indigo)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
            {metrics.active_roadmaps || 0}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '12px' }}>
            Structured career & subject plans
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontWeight: 600 }}>
              QUIZ MASTERY AVG
            </span>
            <Award size={18} color="var(--status-success)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
            {metrics.quiz_attempts_count > 0 ? `${metrics.average_quiz_percentage}%` : '—'}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '12px' }}>
            Across {metrics.quiz_attempts_count || 0} recorded exam attempt(s)
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontWeight: 600 }}>
              STUDY SOURCES
            </span>
            <FolderOpen size={18} color="var(--accent-violet)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
            {metrics.total_sources || 0}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '12px' }}>
            {metrics.total_sources || 0} indexed study source(s)
          </div>
        </div>
      </div>

      {/* Continue Learning & Weekly Activity */}
      <div className="grid-2">
        {/* Continue Learning Banner */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <span className="badge badge-indigo">Continue Learning</span>
              {continueLearning && (
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  <Clock size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                  {continueLearning.estimated_hours || 6}h module
                </span>
              )}
            </div>

            {continueLearning ? (
              <>
                <h2 style={{ fontSize: '1.3rem', marginBottom: '8px' }}>
                  {continueLearning.title}
                </h2>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '18px' }}>
                  Roadmap: <strong>{continueLearning.roadmap_title}</strong> •{' '}
                  {continueLearning.phase_title}
                </p>
              </>
            ) : (
              <div style={{ padding: '16px 0' }}>
                <h3 style={{ fontSize: '1.15rem', marginBottom: '6px' }}>
                  No active study topic yet
                </h3>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                  Generate and save your first AI Career Roadmap to unlock structured topic
                  tutorials, reading guides, and 20-MCQ exams.
                </p>
              </div>
            )}
          </div>

          <div>
            {continueLearning ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() =>
                  navigate(
                    `/roadmaps/${continueLearning.roadmap_id}?expand=${
                      continueLearning.topic_id || continueLearning.id
                    }`
                  )
                }
              >
                <PlayCircle size={16} />
                <span>Resume Topic on Roadmap</span>
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate('/roadmaps?new=1')}
              >
                <Compass size={16} />
                <span>Launch AI Roadmap Agent</span>
              </button>
            )}
          </div>
        </div>

        {/* Weekly Activity Visualization */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1.05rem' }}>Weekly Learning Activity</h3>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Recorded study minutes over the past 7 days
              </span>
            </div>
            <span className="badge badge-blue">
              {weeklyActivity.reduce((acc: number, d: any) => acc + (d.minutes || 0), 0)} mins total
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gap: '10px',
              alignItems: 'end',
              height: 130,
              paddingTop: '16px',
            }}
          >
            {weeklyActivity.map((day: any, idx: number) => {
              const heightPct = Math.max(8, Math.round(((day.minutes || 0) / maxMinutes) * 100));
              return (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '6px',
                    height: '100%',
                    justifyContent: 'flex-end',
                  }}
                >
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {day.minutes > 0 ? `${day.minutes}m` : ''}
                  </span>
                  <div
                    style={{
                      width: '100%',
                      maxWidth: 34,
                      height: `${heightPct}%`,
                      borderRadius: '6px 6px 2px 2px',
                      background:
                        day.minutes > 0
                          ? 'linear-gradient(180deg, var(--accent-blue) 0%, var(--accent-indigo) 100%)'
                          : 'rgba(148, 163, 184, 0.14)',
                    }}
                    title={`${day.date}: ${day.minutes} mins (${day.actions} actions)`}
                  />
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                    {day.day_label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Active Roadmaps & Today's Tasks / Revisions */}
      <div className="grid-2">
        {/* Active Roadmaps */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem' }}>Active Roadmaps</h3>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => navigate('/roadmaps')}
            >
              View All <ArrowRight size={14} />
            </button>
          </div>

          {roadmaps.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
              <p style={{ marginBottom: '12px', fontSize: '0.9rem' }}>
                You haven't saved any learning roadmaps yet.
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => navigate('/roadmaps?new=1')}
              >
                Generate Your First Roadmap
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {roadmaps.map((rm: any) => (
                <div
                  key={rm.id}
                  onClick={() => navigate(`/roadmaps/${rm.id}`)}
                  style={{
                    padding: '14px',
                    borderRadius: '10px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <strong style={{ fontSize: '0.95rem' }}>{rm.title}</strong>
                    <span className="badge badge-indigo">{rm.progress_percent}%</span>
                  </div>
                  <div className="progress-track" style={{ marginBottom: '8px' }}>
                    <div className="progress-fill" style={{ width: `${rm.progress_percent}%` }} />
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                    <span>
                      {rm.completed_topics}/{rm.total_topics} topics • {rm.skill_level}
                    </span>
                    <span>{rm.total_estimated_hours}h total</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Today's Study Tasks & Upcoming Revisions */}
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', marginBottom: '14px' }}>
            Today's Study Tasks & Upcoming Revisions
          </h3>

          {todaysTasks.length === 0 && upcomingRevisions.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Create a roadmap or flashcard deck to populate your daily study queue.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {todaysTasks.map((task: any) => (
                <div
                  key={task.topic_id}
                  onClick={() => navigate(`/roadmaps/${task.roadmap_id}?expand=${task.topic_id}`)}
                  style={{
                    padding: '11px 14px',
                    borderRadius: '10px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{task.title}</div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                      {task.roadmap_title} • {task.phase_title}
                    </div>
                  </div>
                  <span className="badge badge-blue">{task.estimated_hours}h</span>
                </div>
              ))}

              {upcomingRevisions.map((rev: any, idx: number) => (
                <div
                  key={idx}
                  onClick={() => navigate(rev.link)}
                  style={{
                    padding: '11px 14px',
                    borderRadius: '10px',
                    background: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    cursor: 'pointer',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem', color: '#fcd34d' }}>
                      <RotateCcw size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                      {rev.title}
                    </div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      {rev.subtitle}
                    </div>
                  </div>
                  <ArrowRight size={15} color="#fcd34d" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom 2-Column Section: Recent Sources, Recent Quiz Attempts */}
      <div className="grid-2">
        {/* Recently Opened Sources */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '1rem' }}>Recent Study Sources</h3>
            <button type="button" className="btn-ghost btn-sm" onClick={() => navigate('/sources')}>
              Open Library
            </button>
          </div>
          {recentSources.length === 0 ? (
            <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
              No documents uploaded yet. Upload PDFs or Markdown notes in My Sources.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentSources.map((src: any) => (
                <div
                  key={src.id}
                  onClick={() => navigate(`/sources?open=${src.id}`)}
                  style={{
                    padding: '10px',
                    borderRadius: '8px',
                    background: 'var(--bg-charcoal)',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <FileText size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                      {src.title}
                    </div>
                    <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)' }}>
                      {src.word_count} words • {src.page_count} page(s)
                    </div>
                  </div>
                  <span className={`badge ${src.status === 'ready' ? 'badge-success' : 'badge-warning'}`}>
                    {src.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Quiz Attempts & Scores */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '1rem' }}>Recent Quiz Attempts</h3>
            <button type="button" className="btn-ghost btn-sm" onClick={() => navigate('/quizzes')}>
              All Results
            </button>
          </div>
          {recentAttempts.length === 0 ? (
            <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
              No quiz attempts recorded yet. Complete a 20-MCQ topic exam to see your score history.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentAttempts.map((att: any) => (
                <div
                  key={att.id}
                  onClick={() => navigate(`/quizzes?attempt=${att.id}`)}
                  style={{
                    padding: '10px',
                    borderRadius: '8px',
                    background: 'var(--bg-charcoal)',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {att.topic_title}
                    </div>
                    <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)' }}>
                      Score: {att.score}/{att.max_score} ({att.percentage}%)
                    </div>
                  </div>
                  <span className={`badge ${att.passed ? 'badge-success' : 'badge-danger'}`}>
                    {att.passed ? 'Passed' : 'Needs Review'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

