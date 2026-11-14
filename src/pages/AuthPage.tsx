import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  CheckCircle2,
  Mail,
  RotateCcw,
  ArrowLeft,
  Eye,
  EyeOff,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp, UserProfile } from '../context/AppContext';
import { OtpCodeInput } from '../components/OtpCodeInput';
import { BrainovaLogo } from '../components/BrainovaLogo';
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

  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
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
      if (name.trim().length > 40) {
        setError('Full name must be 40 characters or fewer.');
        return;
      }
      if (password.length < 6 || password.length > 25) {
        setError('Password must be between 6 and 25 characters.');
        return;
      }
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

  const switchMode = (nextMode: 'login' | 'signup') => {
    setMode(nextMode);
    setError('');
    setShowPassword(false);
    setShowConfirmPassword(false);
  };

  return (
    <div className="auth-page-shell">
      <div className="auth-center-stack">
        <div className="auth-brand-header">
          <BrainovaLogo size={42} variant="auth" alt="BRAINOVA Logo" />
          <span className="auth-brand-wordmark">BRAINOVA</span>
        </div>

        <div className="auth-card">
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
                <h1 className="auth-heading">Verify Your Email</h1>
                <p className="auth-subheading" style={{ marginBottom: 0 }}>
                  We&apos;ve sent a secure verification code to your email address. Enter the
                  six-digit code to activate your BRAINOVA account.
                </p>
              </div>

              <div className="otp-masked-email-pill" data-testid="otp-masked-email">
                <Mail size={15} aria-hidden="true" />
                <span>{pending.masked_email}</span>
              </div>

              {error && (
                <div className="auth-error-banner" role="alert">
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
              <div className="auth-mode-tabs" role="tablist" aria-label="Authentication mode">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'login'}
                  className={`auth-mode-tab ${mode === 'login' ? 'active' : ''}`}
                  onClick={() => switchMode('login')}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'signup'}
                  className={`auth-mode-tab ${mode === 'signup' ? 'active' : ''}`}
                  onClick={() => switchMode('signup')}
                >
                  Create Account
                </button>
              </div>

              <h1 className="auth-heading">
                {mode === 'signup' ? 'Create your account' : 'Welcome back'}
              </h1>
              <p className="auth-subheading">
                {mode === 'signup'
                  ? 'Enter your details to get started with BRAINOVA.'
                  : 'Sign in with your email and password to continue.'}
              </p>

              {error && (
                <div className="auth-error-banner" role="alert">
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
                      autoComplete="name"
                      maxLength={40}
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
                    placeholder="name@example.com"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="auth-password">
                    Password
                  </label>
                  <div className="auth-input-wrap">
                    <input
                      id="auth-password"
                      type={showPassword ? 'text' : 'password'}
                      className="form-input"
                      placeholder="••••••••"
                      autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                      maxLength={mode === 'signup' ? 25 : undefined}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={6}
                      required
                    />
                    <button
                      type="button"
                      className="auth-password-toggle"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                    >
                      {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                    </button>
                  </div>
                </div>

                {mode === 'signup' && (
                  <div className="form-group">
                    <label className="form-label" htmlFor="auth-confirm-password">
                      Confirm Password
                    </label>
                    <div className="auth-input-wrap">
                      <input
                        id="auth-confirm-password"
                        type={showConfirmPassword ? 'text' : 'password'}
                        className="form-input"
                        placeholder="••••••••"
                        autoComplete="new-password"
                        maxLength={25}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        minLength={6}
                        required
                      />
                      <button
                        type="button"
                        className="auth-password-toggle"
                        onClick={() => setShowConfirmPassword((v) => !v)}
                        aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                        aria-pressed={showConfirmPassword}
                      >
                        {showConfirmPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                      </button>
                    </div>
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
                  className="btn btn-primary btn-lg auth-submit-btn"
                  disabled={submitting}
                >
                  <CheckCircle2 size={18} aria-hidden="true" />
                  <span>
                    {submitting
                      ? mode === 'signup'
                        ? 'Sending Verification Code...'
                        : 'Signing In...'
                      : mode === 'signup'
                      ? 'Continue & Verify Email'
                      : 'Sign In'}
                  </span>
                </button>
              </form>

              <div className="auth-footer-switch">
                {mode === 'login' ? (
                  <>
                    <span>Don&apos;t have an account?</span>
                    <button
                      type="button"
                      className="auth-footer-link"
                      onClick={() => switchMode('signup')}
                    >
                      Create Account
                    </button>
                  </>
                ) : (
                  <>
                    <span>Already have an account?</span>
                    <button
                      type="button"
                      className="auth-footer-link"
                      onClick={() => switchMode('login')}
                    >
                      Sign In
                    </button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
