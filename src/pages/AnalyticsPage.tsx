import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
  Award,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const AnalyticsPage: React.FC = () => {
  const { addToast } = useApp();
  const navigate = useNavigate();

  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest('/api/analytics')
      .then((res) => setData(res))
      .catch((err) => addToast(err.message || 'Failed to load analytics.', 'error'))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading recorded progress & analytics...</p>
      </div>
    );
  }

  const {
    roadmaps = [],
    quiz_trend = [],
    weak_topics = [],
    strong_topics = [],
    flashcard_breakdown = {},
    topic_status_counts = {},
    total_time_spent_minutes = 0,
    recent_activities = [],
  } = data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="card card-elevated">
        <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
          Empirical Learning Telemetry
        </span>
        <h1 style={{ fontSize: '1.65rem', marginBottom: '6px' }}>Progress and Analytics</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
          All metrics below are computed directly from your actual recorded topic completions,
          submitted 20-MCQ assessments, and spaced-repetition flashcard reviews.
        </p>
      </div>

      {/* Top KPI Cards */}
      <div className="grid-4">
        <div className="card">
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>TOPICS COMPLETED</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
            {topic_status_counts.completed || 0} / {topic_status_counts.total || 0}
          </div>
          <div style={{ fontSize: '0.76rem', color: 'var(--accent-blue)', marginTop: 4 }}>
            {topic_status_counts.in_progress || 0} currently in progress
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>QUIZ ATTEMPTS</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>{quiz_trend.length}</div>
          <div style={{ fontSize: '0.76rem', color: 'var(--status-success)', marginTop: 4 }}>
            {quiz_trend.filter((q: any) => q.passed).length} passed (&ge;70%)
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>FLASHCARD MASTERY</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
            {flashcard_breakdown.known || 0} / {flashcard_breakdown.total || 0}
          </div>
          <div style={{ fontSize: '0.76rem', color: 'var(--accent-violet)', marginTop: 4 }}>
            {flashcard_breakdown.review || 0} flagged for review
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>RECORDED STUDY TIME</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>{total_time_spent_minutes}m</div>
          <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 4 }}>
            Measured across exams & topics
          </div>
        </div>
      </div>

      {/* Weak Topics vs Strong Topics Identification */}
      <div className="grid-2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <AlertTriangle size={18} color="var(--status-warning)" />
            <h3 style={{ fontSize: '1.1rem' }}>Topics Needing Revision (&lt; 70% Avg Score)</h3>
          </div>
          {weak_topics.length === 0 ? (
            <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>
              No weak topics detected from your submitted quizzes! Any topic where your average quiz
              score falls below 70% will appear here automatically.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {weak_topics.map((wt: any, idx: number) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px',
                    borderRadius: '10px',
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{wt.topic_title}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      Avg: {wt.average_percentage}% across {wt.attempt_count} attempt(s)
                    </div>
                  </div>
                  {wt.roadmap_id && wt.topic_id && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => navigate(`/roadmaps/${wt.roadmap_id}/topics/${wt.topic_id}`)}
                    >
                      Revise Topic
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <CheckCircle2 size={18} color="var(--status-success)" />
            <h3 style={{ fontSize: '1.1rem' }}>Mastered Topics (&ge; 70% Avg Score)</h3>
          </div>
          {strong_topics.length === 0 ? (
            <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>
              Pass a 20-question topic examination with 70% or higher to verify mastery.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {strong_topics.map((st: any, idx: number) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px',
                    borderRadius: '10px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{st.topic_title}</div>
                    <div style={{ fontSize: '0.78rem', color: '#6ee7b7' }}>
                      Avg: {st.average_percentage}% ({st.attempt_count} attempt(s))
                    </div>
                  </div>
                  <span className="badge badge-success">Verified</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quiz Score Trend Visualization */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', marginBottom: '14px' }}>
          Quiz Score Progression Across Attempts
        </h3>
        {quiz_trend.length === 0 ? (
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>
            Submit your first quiz attempt to visualize your score trend over time.
          </p>
        ) : (
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: '14px',
              height: 170,
              padding: '20px 10px 0',
              overflowX: 'auto',
            }}
          >
            {quiz_trend.map((qt: any, idx: number) => (
              <div
                key={qt.id || idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '6px',
                  minWidth: 72,
                  height: '100%',
                  justifyContent: 'flex-end',
                }}
              >
                <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{qt.percentage}%</span>
                <div
                  style={{
                    width: 42,
                    height: `${Math.max(10, qt.percentage)}%`,
                    borderRadius: '8px 8px 2px 2px',
                    background: qt.passed
                      ? 'linear-gradient(180deg, #10b981 0%, #059669 100%)'
                      : 'linear-gradient(180deg, #f59e0b 0%, #d97706 100%)',
                  }}
                  title={`${qt.topic_title}: ${qt.score}/${qt.max_score} (${qt.percentage}%)`}
                />
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-muted)',
                    maxWidth: 70,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {qt.topic_title}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Roadmap Phase Breakdown */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', marginBottom: '14px' }}>Roadmap & Phase Completion</h3>
        {roadmaps.length === 0 ? (
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)' }}>No saved roadmaps yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {roadmaps.map((rm: any) => (
              <div
                key={rm.id}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  background: 'var(--bg-charcoal)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong>{rm.title}</strong>
                  <span className="badge badge-indigo">
                    {rm.completed_topics}/{rm.total_topics} topics ({rm.progress_percent}%)
                  </span>
                </div>
                <div className="progress-track" style={{ marginBottom: '12px' }}>
                  <div className="progress-fill" style={{ width: `${rm.progress_percent}%` }} />
                </div>
                <div className="grid-3">
                  {(rm.phases || []).map((ph: any) => (
                    <div
                      key={ph.id}
                      style={{
                        padding: '10px',
                        borderRadius: '8px',
                        background: 'var(--surface-1)',
                        fontSize: '0.8rem',
                      }}
                    >
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{ph.title}</div>
                      <div style={{ color: 'var(--text-muted)' }}>
                        {ph.completed_topics}/{ph.total_topics} completed ({ph.progress_percent}%)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

