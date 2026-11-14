import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ShieldCheck,
  Compass,
  BookOpen,
  CheckCircle2,
  Mail,
  RotateCcw,
  ArrowLeft,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp, UserProfile } from '../context/AppContext';
import { OtpCodeInput } from '../components/OtpCodeInput';
import { formatOtpCountdown, OTP_DIGIT_COUNT } from '../lib/otpInputHelpers';

const PENDING_REG_STORAGE_KEY = 'brainova_pending_reg_token';

interface PendingVerificationState {
  pending_token: string;
  masked_email: string;
  expires_at: string;
  resend_available_at: string;
  attempts_remaining: number;
  resends_remaining: number;
  expired: boolean;
  otp_invalidated?: boolean;
}

export const AuthPage: React.FC = () => {
  const { loginWithToken, addToast } = useApp();
  const navigate = useNavigate();

  const [mode, setMode] = useState<'login' | 'signup'>('signup');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [targetRole, setTargetRole] = useState('Full Stack Developer');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Pending Email OTP Verification state (only opaque pending_token persisted in sessionStorage)
  const [pending, setPending] = useState<PendingVerificationState | null>(null);
  const [recoveringPending, setRecoveringPending] = useState<boolean>(false);
  const [otpDigits, setOtpDigits] = useState<string[]>(Array(OTP_DIGIT_COUNT).fill(''));
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [expiresInSeconds, setExpiresInSeconds] = useState<number>(0);
  const [resendCooldownSeconds, setResendCooldownSeconds] = useState<number>(0);
  const [verifiedSuccess, setVerifiedSuccess] = useState(false);

  const syncCountdowns = (state: PendingVerificationState) => {
    const nowMs = Date.now();
    const expMs = Date.parse(state.expires_at);
    const resMs = Date.parse(state.resend_available_at);
    setExpiresInSeconds(Number.isFinite(expMs) ? Math.max(0, Math.floor((expMs - nowMs) / 1000)) : 0);
    setResendCooldownSeconds(
      Number.isFinite(resMs) ? Math.max(0, Math.floor((resMs - nowMs) / 1000)) : 0
    );
  };

  // Recover pending registration safely on page refresh
  useEffect(() => {
    const savedToken = sessionStorage.getItem(PENDING_REG_STORAGE_KEY);
    if (!savedToken) return;
    let active = true;
    setRecoveringPending(true);
    apiRequest<PendingVerificationState>(`/api/auth/pending-registration/${encodeURIComponent(savedToken)}`)
      .then((res) => {
        if (!active) return;
        setPending(res);
        syncCountdowns(res);
        setMode('signup');
      })
      .catch(() => {
        sessionStorage.removeItem(PENDING_REG_STORAGE_KEY);
      })
      .finally(() => {
        if (active) setRecoveringPending(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Visual countdown timer (backend timestamps remain authoritative)
  useEffect(() => {
    if (!pending || verifiedSuccess) return;
    syncCountdowns(pending);
    const id = window.setInterval(() => {
      syncCountdowns(pending);
    }, 1000);
    return () => window.clearInterval(id);
  }, [pending, verifiedSuccess]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError('');

    if (mode === 'signup') {
      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
      setSubmitting(true);
      try {
        const res = await apiRequest<PendingVerificationState>('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            name: name.trim(),
            email: email.trim(),
            password,
            confirm_password: confirmPassword,
            target_role: targetRole.trim() || 'Full Stack Developer',
          }),
        });
        sessionStorage.setItem(PENDING_REG_STORAGE_KEY, res.pending_token);
        setOtpDigits(Array(OTP_DIGIT_COUNT).fill(''));
        setPending(res);
        syncCountdowns(res);
        addToast('Verification code sent to your email.', 'info');
      } catch (err: any) {
        setError(err.message || 'Unable to start account registration.');
      } finally {
        setSubmitting(false);
      }
      return;
    }

    setSubmitting(true);
    try {
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
    } catch (err: any) {
      setError(err.message || 'Authentication failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const otpCode = otpDigits.join('');

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pending || verifying || otpCode.length !== OTP_DIGIT_COUNT) return;
    setError('');
    setVerifying(true);
    try {
      const res = await apiRequest<{ token: string; user: UserProfile }>('/api/auth/verify-email', {
        method: 'POST',
        body: JSON.stringify({
          pending_token: pending.pending_token,
          otp_code: otpCode,
        }),
      });
      sessionStorage.removeItem(PENDING_REG_STORAGE_KEY);
      setVerifiedSuccess(true);
      const reducedMotion =
        typeof window !== 'undefined' &&
        window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      window.setTimeout(() => {
        loginWithToken(res.token, res.user);
        addToast(`Welcome to BRAINOVA, ${res.user.name}!`, 'success');
        navigate('/dashboard');
      }, reducedMotion ? 100 : 900);
    } catch (err: any) {
      setError(err.message || 'Verification failed.');
    } finally {
      setVerifying(false);
    }
  };

  const handleResendCode = async () => {
    if (!pending || resending || resendCooldownSeconds > 0) return;
    setError('');
    setResending(true);
    try {
      const res = await apiRequest<PendingVerificationState>('/api/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({
          pending_token: pending.pending_token,
        }),
      });
      setPending(res);
      syncCountdowns(res);
      setOtpDigits(Array(OTP_DIGIT_COUNT).fill(''));
      addToast('A new 6-digit verification code has been sent.', 'success');
    } catch (err: any) {
      setError(err.message || 'Unable to resend verification code.');
    } finally {
      setResending(false);
    }
  };

  const handleChangeEmail = async () => {
    if (pending) {
      try {
        await apiRequest(`/api/auth/pending-registration/${encodeURIComponent(pending.pending_token)}`, {
          method: 'DELETE',
        });
      } catch {
        // Ignore network errors while resetting local pending state
      }
    }
    sessionStorage.removeItem(PENDING_REG_STORAGE_KEY);
    setPending(null);
    setOtpDigits(Array(OTP_DIGIT_COUNT).fill(''));
    setError('');
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
                  LEARN SMARTER. THINK BIG.
                </div>
              </div>
            </div>

            <h2 style={{ fontSize: '1.82rem', marginBottom: '16px', lineHeight: 1.25 }}>
              Master any engineering or academic discipline with source-grounded AI workflows.
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '28px', fontSize: '0.96rem' }}>
              Upload and index your study documents for source-grounded Q&A, build personalized
              career roadmaps, customize tutorials and reading guides, and verify mastery with
              20-question MCQ examinations.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <Sparkles size={20} color="var(--accent-blue)" style={{ marginTop: 3, flexShrink: 0 }} />
                <div>
                  <strong>Source-Grounded Q&A & Document Library</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Upload PDF, DOCX, PPTX, Markdown, and text study materials with automatic
                    indexing, citation-backed answers, and personal learning notes.
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
              Private personal workspaces for your saved study materials and progress.
            </span>
          </div>
        </div>

        {/* Right Form / Verification / Success Card */}
        <div className="card" style={{ padding: '36px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          {verifiedSuccess ? (
            <div className="auth-success-card" data-testid="auth-verified-success">
              <div className="auth-success-emblem" aria-hidden="true">
                <CheckCircle2 size={34} />
              </div>
              <h2 className="auth-success-title">Welcome to BRAINOVA!</h2>
              <p className="auth-success-subtitle">
                Your email has been verified. Your learning journey starts now.
              </p>
            </div>
          ) : recoveringPending ? (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
              Restoring email verification session...
            </div>
          ) : pending ? (
            <div data-testid="email-otp-verification-screen">
              <div className="otp-verify-header">
                <span className="otp-kicker">
                  <ShieldCheck size={13} aria-hidden="true" />
                  <span>BRAINOVA · Account Verification</span>
                </span>
                <h2 style={{ fontSize: '1.45rem', margin: 0 }}>Verify Your Email</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0, lineHeight: 1.5 }}>
                  We&apos;ve sent a secure verification code to your email address. Enter the
                  six-digit code to activate your BRAINOVA account.
                </p>
              </div>

              <div className="otp-masked-email-pill" data-testid="otp-masked-email">
                <Mail size={15} aria-hidden="true" />
                <span>{pending.masked_email}</span>
              </div>

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

              <form onSubmit={handleVerifyOtp}>
                <OtpCodeInput
                  digits={otpDigits}
                  onChange={setOtpDigits}
                  disabled={verifying}
                  hasError={Boolean(error)}
                />

                <div className="otp-meta-timers">
                  <span>
                    Code expires in{' '}
                    <strong>
                      {expiresInSeconds > 0 ? formatOtpCountdown(expiresInSeconds) : 'Expired'}
                    </strong>
                  </span>
                  <span>
                    {resendCooldownSeconds > 0 ? (
                      <>
                        Resend available in <strong>{resendCooldownSeconds}s</strong>
                      </>
                    ) : (
                      'Ready to resend if needed'
                    )}
                  </span>
                </div>

                <div className="otp-actions-stack">
                  <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    disabled={verifying || otpCode.length !== OTP_DIGIT_COUNT || expiresInSeconds <= 0}
                    data-testid="verify-otp-submit-btn"
                  >
                    <CheckCircle2 size={18} aria-hidden="true" />
                    <span>{verifying ? 'Verifying Code...' : 'Verify & Continue'}</span>
                  </button>

                  <div className="otp-secondary-row">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={resending || resendCooldownSeconds > 0}
                      onClick={handleResendCode}
                      data-testid="resend-otp-btn"
                    >
                      <RotateCcw size={15} aria-hidden="true" />
                      <span>
                        {resending
                          ? 'Sending...'
                          : resendCooldownSeconds > 0
                          ? `Resend (${resendCooldownSeconds}s)`
                          : 'Resend Code'}
                      </span>
                    </button>

                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={verifying || resending}
                      onClick={handleChangeEmail}
                      data-testid="change-email-btn"
                    >
                      <ArrowLeft size={15} aria-hidden="true" />
                      <span>Change Email</span>
                    </button>
                  </div>
                </div>
              </form>
            </div>
          ) : (
            <>
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
                  ? 'Start building career roadmaps and indexing your study sources.'
                  : 'Enter your credentials to access your saved roadmaps, sources, and quiz history.'}
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
                    <label className="form-label" htmlFor="auth-confirm-password">
                      Confirm Password
                    </label>
                    <input
                      id="auth-confirm-password"
                      type="password"
                      className="form-input"
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      minLength={6}
                      required
                    />
                  </div>
                )}

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
                      ? mode === 'signup'
                        ? 'Sending Verification Code...'
                        : 'Authenticating...'
                      : mode === 'signup'
                      ? 'Continue & Verify Email'
                      : 'Sign In to BRAINOVA'}
                  </span>
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
