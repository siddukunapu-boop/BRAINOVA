import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  CheckSquare,
  Award,
  Clock,
  Eye,
  Trash2,
  RotateCcw,
  Sparkles,
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
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s}s`;
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
            Review your recorded 20-question topic MCQ attempts and AI Studio quiz results, inspect
            detailed question explanations, or retake assessments.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/studio?tool=quiz')}
        >
          <Sparkles size={16} />
          <span>Generate Custom Studio Quiz</span>
        </button>
      </div>

      {/* Attempt History Table */}
      <div className="card">
        <h2 style={{ fontSize: '1.2rem', marginBottom: '14px' }}>
          Recorded Examination Attempts ({attempts.length})
        </h2>

        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Loading attempts...</p>
        ) : attempts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <CheckSquare size={42} color="var(--text-subtle)" style={{ marginBottom: '12px' }} />
            <h3 style={{ marginBottom: '6px' }}>No Quiz Attempts Recorded Yet</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '16px' }}>
              Open any Topic Workspace inside your roadmaps to take its 20-question MCQ exam, or
              generate a source-grounded quiz in AI Studio.
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
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Topic / Examination Title</th>
                  <th>Score</th>
                  <th>Correct / Wrong / Unanswered</th>
                  <th>Time Taken</th>
                  <th>Status</th>
                  <th>Submitted At</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((att) => (
                  <tr key={att.id}>
                    <td>
                      <strong style={{ color: 'var(--text-primary)' }}>{att.topic_title}</strong>
                    </td>
                    <td>
                      <strong>
                        {att.score} / {att.max_score}
                      </strong>{' '}
                      ({att.percentage}%)
                    </td>
                    <td>
                      <span style={{ color: '#6ee7b7' }}>{att.correct_count}✓</span> •{' '}
                      <span style={{ color: '#fca5a5' }}>{att.incorrect_count}✗</span> •{' '}
                      <span style={{ color: '#fcd34d' }}>{att.unanswered_count}—</span>
                    </td>
                    <td>
                      <Clock size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      {formatTime(att.duration_seconds || 0)}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          att.passed ? 'badge-success' : 'badge-warning'
                        }`}
                      >
                        {att.passed ? 'Passed (70%+)' : 'Needs Retake'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {new Date(att.created_at).toLocaleString()}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => inspectAttempt(att.id)}
                        >
                          <Eye size={14} />
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
                            <RotateCcw size={13} />
                            <span>Retake</span>
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDeleteAttempt(att.id)}
                          title="Delete attempt"
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

