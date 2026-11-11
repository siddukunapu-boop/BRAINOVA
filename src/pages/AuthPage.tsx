import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ShieldCheck, Compass, BookOpen, CheckCircle2 } from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp, UserProfile } from '../context/AppContext';

export const AuthPage: React.FC = () => {
  const { loginWithToken, addToast } = useApp();
  const navigate = useNavigate();

  const [mode, setMode] = useState<'login' | 'signup'>('signup');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [targetRole, setTargetRole] = useState('Full Stack Developer');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'signup') {
        const res = await apiRequest<{ token: string; user: UserProfile }>('/api/auth/signup', {
          method: 'POST',
          body: JSON.stringify({
            name: name.trim(),
            email: email.trim(),
            password,
            target_role: targetRole.trim() || 'Full Stack Developer',
          }),
        });
        loginWithToken(res.token, res.user);
        addToast(`Welcome to BRAINOVA, ${res.user.name}!`, 'success');
        navigate('/dashboard');
      } else {
        const res = await apiRequest<{ token: string; user: UserProfile }>('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: email.trim(),
            password,
          }),
        });
        loginWithToken(res.token, res.user);
        addToast(`Welcome back to BRAINOVA, ${res.user.name}!`, 'success');
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        className="grid-2"
        style={{
          maxWidth: 1060,
          width: '100%',
          alignItems: 'stretch',
          gap: '32px',
        }}
      >
        {/* Left Brand Showcase */}
        <div
          className="card card-elevated"
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            padding: '36px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '26px' }}>
              <div
                className="brainova-logo-wrap"
                style={{ width: 64, height: 64, borderRadius: '16px' }}
              >
                <img
                  src="/brainova-logo.jpg"
                  alt="BRAINOVA Logo"
                  className="brainova-logo-img"
                />
              </div>
              <div>
                <h1 className="brainova-brand-text" style={{ fontSize: '1.7rem', margin: 0 }}>
                  BRAINOVA
                </h1>
                <div className="brainova-tagline" style={{ fontSize: '0.84rem', marginTop: 2 }}>
                  Learn Smarter. Think Bigger.
                </div>
              </div>
            </div>

            <h2 style={{ fontSize: '1.82rem', marginBottom: '16px', lineHeight: 1.25 }}>
              Master any engineering or academic discipline with source-grounded AI workflows.
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '28px', fontSize: '0.96rem' }}>
              Transform your study documents with 9 specialized AI Studio tools across 6 languages,
              build personalized career roadmaps, customize tutorials and reading guides, and verify
              mastery with 20-question MCQ examinations.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <Sparkles size={20} color="var(--accent-blue)" style={{ marginTop: 3, flexShrink: 0 }} />
                <div>
                  <strong>Nine AI Studio Tools & Dedicated Library</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Playable Audio Overviews, 1080p HD Video Overviews, Slide Decks, Mind Maps,
                    Study Guides, Flashcards, 20-MCQ Quizzes, Infographics, and Data Tables in
                    English, Telugu, Hindi, Kannada, Tamil, and Marathi.
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <Compass size={20} color="var(--accent-indigo)" style={{ marginTop: 3, flexShrink: 0 }} />
                <div>
                  <strong>Expandable AI Roadmaps & Customized Resources</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Expand any topic inline on the same page to access its Tutorial, Reading Material
                    with architecture diagrams, and 20-MCQ Exam, or personalize tutorials and
                    readings in Customized Roadmap.
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <BookOpen size={20} color="var(--status-success)" style={{ marginTop: 3, flexShrink: 0 }} />
                <div>
                  <strong>Four Premium Dark & High-Contrast Themes</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Switch seamlessly between Neural Night, Dark Light, Quantum Violet, and Focus
                    Forest.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '32px',
              paddingTop: '18px',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
            }}
          >
            <ShieldCheck size={16} color="var(--status-success)" />
            <span>
              BRAINOVA private user workspaces with server-side ownership enforcement & SQLite
              persistence.
            </span>
          </div>
        </div>

        {/* Right Form Card */}
        <div className="card" style={{ padding: '36px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div className="tabs-bar" style={{ marginBottom: '24px' }}>
            <button
              type="button"
              className={`tab-btn ${mode === 'signup' ? 'active' : ''}`}
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={() => {
                setMode('signup');
                setError('');
              }}
            >
              Create Account
            </button>
            <button
              type="button"
              className={`tab-btn ${mode === 'login' ? 'active' : ''}`}
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={() => {
                setMode('login');
                setError('');
              }}
            >
              Sign In
            </button>
          </div>

          <h2 style={{ fontSize: '1.4rem', marginBottom: '6px' }}>
            {mode === 'signup' ? 'Create Your BRAINOVA Account' : 'Sign In to BRAINOVA'}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '22px' }}>
            {mode === 'signup'
              ? 'Start building career roadmaps and multi-language AI Studio outputs.'
              : 'Enter your credentials to access your saved roadmaps, AI Studio Library, and quiz history.'}
          </p>

          {error && (
            <div
              style={{
                background: 'var(--status-danger-bg)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#fca5a5',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                marginBottom: '16px',
              }}
              role="alert"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {mode === 'signup' && (
              <div className="form-group">
                <label className="form-label" htmlFor="auth-name">
                  Full Name
                </label>
                <input
                  id="auth-name"
                  type="text"
                  className="form-input"
                  placeholder="e.g., Aarav Sharma"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="auth-email">
                Email Address
              </label>
              <input
                id="auth-email"
                type="email"
                className="form-input"
                placeholder="student@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="auth-password">
                Password (min 6 characters)
              </label>
              <input
                id="auth-password"
                type="password"
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
              />
            </div>

            {mode === 'signup' && (
              <div className="form-group">
                <label className="form-label" htmlFor="auth-role">
                  Primary Career / Learning Goal
                </label>
                <select
                  id="auth-role"
                  className="form-select"
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                >
                  <option value="Full Stack Developer">Full Stack Developer</option>
                  <option value="Backend Developer">Backend Developer</option>
                  <option value="Frontend Developer">Frontend Developer</option>
                  <option value="Data Scientist">Data Scientist</option>
                  <option value="Machine Learning Engineer">Machine Learning Engineer</option>
                  <option value="Competitive Programming">Competitive Programming</option>
                  <option value="Cybersecurity & Cloud Engineer">Cybersecurity & Cloud Engineer</option>
                </select>
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{ width: '100%', marginTop: '8px' }}
              disabled={submitting}
            >
              <CheckCircle2 size={18} />
              <span>
                {submitting
                  ? 'Authenticating...'
                  : mode === 'signup'
                  ? 'Create Account & Launch BRAINOVA'
                  : 'Sign In to BRAINOVA'}
              </span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
