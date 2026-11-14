import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  CheckSquare,
  Award,
  Clock,
  Eye,
  Trash2,
  RotateCcw,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const QuizzesPage: React.FC = () => {
  const { addToast } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [attempts, setAttempts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAttempt, setSelectedAttempt] = useState<any | null>(null);

  const loadAttempts = async () => {
    setLoading(true);
    try {
      const res = await apiRequest<{ attempts: any[] }>('/api/quizzes/attempts');
      setAttempts(res.attempts || []);
      const openId = searchParams.get('attempt');
      if (openId) {
        inspectAttempt(openId);
      }
    } catch (err: any) {
      addToast(err.message || 'Failed to load quiz history.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAttempts();
  }, []);

  const inspectAttempt = async (attemptId: string) => {
    try {
      const res = await apiRequest<{ attempt: any }>(`/api/quizzes/attempts/${attemptId}`);
      setSelectedAttempt(res.attempt);
    } catch (err: any) {
      addToast(err.message || 'Could not load attempt details.', 'error');
    }
  };

  const handleDeleteAttempt = async (attemptId: string) => {
    try {
      await apiRequest(`/api/quizzes/attempts/${attemptId}`, { method: 'DELETE' });
      setAttempts((prev) => prev.filter((a) => a.id !== attemptId));
      if (selectedAttempt?.id === attemptId) setSelectedAttempt(null);
      addToast('Deleted quiz attempt. Other attempts remain intact.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
  };

  const formatTime = (secs: number) => {
    const clamped = Math.max(0, Math.floor(secs));
    const m = Math.floor(clamped / 60);
    const s = clamped % 60;
    return `${m}m ${String(s).padStart(2, '0')}s`;
  };

  const formatSubmittedParts = (iso: string) => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) {
      return { date: '—', time: '' };
    }
    return {
      date: d.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }),
      time: d.toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
      }),
    };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div
        className="card card-elevated"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div>
          <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
            Assessment & Examination History
          </span>
          <h1 style={{ fontSize: '1.65rem' }}>Quizzes and Results</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Review your recorded 20-question topic MCQ attempts, inspect detailed question
            explanations, or retake assessments.
          </p>
        </div>
      </div>

      {/* Attempt History */}
      <div className="card exam-history-shell">
        <div className="exam-history-header">
          <div className="exam-history-heading-group">
            <h2 className="exam-history-heading">Recorded Examination Attempts</h2>
            <span className="exam-attempt-count-badge" aria-label={`${attempts.length} attempts`}>
              {attempts.length}
            </span>
          </div>
        </div>

        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Loading attempts...</p>
        ) : attempts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <CheckSquare size={42} color="var(--text-subtle)" style={{ marginBottom: '12px' }} />
            <h3 style={{ marginBottom: '6px' }}>No Quiz Attempts Recorded Yet</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '16px' }}>
              Open any Topic Workspace inside your roadmaps to take its 20-question MCQ exam.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/roadmaps')}
            >
              Go to Roadmaps
            </button>
          </div>
        ) : (
          <>
            {/* Desktop Table */}
            <div className="exam-table-shell">
              <table className="exam-table">
                <thead>
                  <tr>
                    <th className="exam-col-title">Examination / Topic</th>
                    <th className="exam-col-score">Score</th>
                    <th className="exam-col-summary">Answer Summary</th>
                    <th className="exam-col-time">Time Taken</th>
                    <th className="exam-col-result">Result</th>
                    <th className="exam-col-date">Submitted At</th>
                    <th className="exam-col-action">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {attempts.map((att) => {
                    const submitted = formatSubmittedParts(att.created_at);
                    return (
                      <tr key={att.id}>
                        <td className="exam-col-title">
                          <span className="exam-title-text">{att.topic_title}</span>
                        </td>
                        <td className="exam-col-score">
                          <div className="exam-score-cell">
                            <span className="exam-score-main">
                              {att.score} / {att.max_score}
                            </span>
                            <span
                              className={`exam-score-pct ${
                                att.passed ? 'is-pass' : 'is-fail'
                              }`}
                            >
                              {att.percentage}%
                            </span>
                          </div>
                        </td>
                        <td className="exam-col-summary">
                          <div className="exam-summary-row">
                            <span className="exam-sum-token exam-sum-correct">
                              {att.correct_count} ✓
                            </span>
                            <span className="exam-sum-sep" aria-hidden="true">
                              ·
                            </span>
                            <span className="exam-sum-token exam-sum-wrong">
                              {att.incorrect_count} ✕
                            </span>
                            <span className="exam-sum-sep" aria-hidden="true">
                              ·
                            </span>
                            <span className="exam-sum-token exam-sum-unanswered">
                              {att.unanswered_count} —
                            </span>
                          </div>
                        </td>
                        <td className="exam-col-time">
                          <span className="exam-time-cell">
                            <Clock size={13} aria-hidden="true" />
                            <span>{formatTime(att.duration_seconds || 0)}</span>
                          </span>
                        </td>
                        <td className="exam-col-result">
                          <span
                            className={`badge ${
                              att.passed ? 'badge-success' : 'badge-danger'
                            }`}
                          >
                            {att.passed ? 'Passed' : 'Failed'}
                          </span>
                        </td>
                        <td className="exam-col-date">
                          <div className="exam-date-cell">
                            <span className="exam-date-day">{submitted.date}</span>
                            {submitted.time && (
                              <span className="exam-date-time">{submitted.time}</span>
                            )}
                          </div>
                        </td>
                        <td className="exam-col-action">
                          <div className="exam-action-group">
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => inspectAttempt(att.id)}
                            >
                              <Eye size={14} aria-hidden="true" />
                              <span>Review</span>
                            </button>
                            {att.roadmap_id && att.topic_id && (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() =>
                                  navigate(
                                    `/roadmaps/${att.roadmap_id}?expand=${att.topic_id}&tab=mcqs`
                                  )
                                }
                                title="Retake examination"
                                aria-label={`Retake ${att.topic_title}`}
                              >
                                <RotateCcw size={13} aria-hidden="true" />
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDeleteAttempt(att.id)}
                              title="Delete attempt"
                              aria-label={`Delete attempt ${att.topic_title}`}
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Tablet & Mobile Cards */}
            <div className="exam-cards-list">
              {attempts.map((att) => {
                const submitted = formatSubmittedParts(att.created_at);
                const pct = Math.max(0, Math.min(100, Number(att.percentage) || 0));
                return (
                  <article key={att.id} className="exam-mobile-card">
                    <div className="exam-mobile-top">
                      <span className="exam-title-text">{att.topic_title}</span>
                      <span
                        className={`badge ${att.passed ? 'badge-success' : 'badge-danger'}`}
                      >
                        {att.passed ? 'Passed' : 'Failed'}
                      </span>
                    </div>

                    <div className="exam-mobile-score-box">
                      <div className="exam-mobile-score-row">
                        <span className="exam-score-main">
                          {att.score} / {att.max_score}
                        </span>
                        <span
                          className={`exam-score-pct ${att.passed ? 'is-pass' : 'is-fail'}`}
                        >
                          {att.percentage}%
                        </span>
                      </div>
                      <div className="exam-score-bar-track" aria-hidden="true">
                        <div
                          className={`exam-score-bar-fill ${att.passed ? 'is-pass' : 'is-fail'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    <div className="exam-mobile-summary-grid">
                      <div className="exam-mobile-stat">
                        <span>Correct</span>
                        <strong className="exam-sum-correct">{att.correct_count} ✓</strong>
                      </div>
                      <div className="exam-mobile-stat">
                        <span>Wrong</span>
                        <strong className="exam-sum-wrong">{att.incorrect_count} ✕</strong>
                      </div>
                      <div className="exam-mobile-stat">
                        <span>Unanswered</span>
                        <strong className="exam-sum-unanswered">{att.unanswered_count} —</strong>
                      </div>
                    </div>

                    <div className="exam-mobile-bottom">
                      <div className="exam-mobile-meta">
                        <span className="exam-time-cell">
                          <Clock size={13} aria-hidden="true" />
                          <span>{formatTime(att.duration_seconds || 0)}</span>
                        </span>
                        <span>
                          {submitted.date}
                          {submitted.time ? ` · ${submitted.time}` : ''}
                        </span>
                      </div>
                      <div className="exam-action-group">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => inspectAttempt(att.id)}
                        >
                          <Eye size={14} aria-hidden="true" />
                          <span>Review</span>
                        </button>
                        {att.roadmap_id && att.topic_id && (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() =>
                              navigate(
                                `/roadmaps/${att.roadmap_id}?expand=${att.topic_id}&tab=mcqs`
                              )
                            }
                          >
                            <RotateCcw size={13} aria-hidden="true" />
                            <span>Retake</span>
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDeleteAttempt(att.id)}
                          title="Delete attempt"
                          aria-label={`Delete attempt ${att.topic_title}`}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Detailed Historical Review Section */}
      {selectedAttempt && (
        <div className="card card-elevated">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <span className="badge badge-blue" style={{ marginBottom: 4 }}>
                HISTORICAL ATTEMPT SNAPSHOT REVIEW
              </span>
              <h2 style={{ fontSize: '1.4rem' }}>
                {selectedAttempt.topic_title} — {selectedAttempt.score}/{selectedAttempt.max_score}{' '}
                ({selectedAttempt.percentage}%)
              </h2>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setSelectedAttempt(null)}
            >
              Close Review
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(selectedAttempt.review_items || []).map((item: any, idx: number) => (
              <div
                key={idx}
                style={{
                  padding: '14px',
                  borderRadius: '10px',
                  background: 'var(--bg-charcoal)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong>
                    Q{item.number || idx + 1}: {item.question}
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
                <div style={{ fontSize: '0.84rem', color: '#6ee7b7' }}>
                  Correct Option: {String.fromCharCode(65 + item.correct_index)} —{' '}
                  {item.options?.[item.correct_index]}
                </div>
                {item.selected_index !== null &&
                  item.selected_index !== undefined &&
                  item.selected_index !== item.correct_index && (
                    <div style={{ fontSize: '0.84rem', color: '#fca5a5' }}>
                      Your Answer: {String.fromCharCode(65 + item.selected_index)} —{' '}
                      {item.options?.[item.selected_index]}
                    </div>
                  )}
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 6 }}>
                  <strong>Explanation:</strong> {item.explanation}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

