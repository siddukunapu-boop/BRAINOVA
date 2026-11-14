import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  Award,
  BarChart3,
  Briefcase,
  CheckCircle2,
  Compass,
  ExternalLink,
  Rocket,
  Save,
  ShieldAlert,
  Sparkles,
  Target,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';
import { CareerMentorPanel } from '../components/CareerMentorPanel';
import {
  dailyToWeeklyHours,
  validateDailyPrepHours,
  weeklyToDailyHours,
} from '../utils/prepHoursValidation';

type LaunchpadTab = 'overview' | 'assessment' | 'gaps' | 'plan' | 'mentor';

interface CareerProfile {
  target_career: string;
  target_job_role: string;
  target_company: string;
  graduation_year: number;
  current_skill_level: string;
  available_hours_per_week: number;
  target_deadline: string;
}

interface AssessmentQuestion {
  id: string;
  category: string;
  question: string;
  options: string[];
}

interface GapItem {
  category: string;
  label: string;
  current: number | null;
  target: number;
  gap: number;
  status: 'unassessed' | 'on_track' | 'moderate_gap' | 'priority_gap';
}

interface WeeklyPoint {
  week_label: string;
  study_minutes: number;
  quizzes_completed: number;
  focus_minutes: number;
  assessments_taken: number;
}

interface OverviewPayload {
  profile: CareerProfile;
  careers: string[];
  skill_categories: { key: string; label: string }[];
  latest_assessment: {
    id: string;
    target_career: string;
    total_questions: number;
    correct_count: number;
    overall_score: number;
    category_scores: Record<string, number>;
    project_evidence: {
      deployed_projects?: number;
      has_github_portfolio?: boolean;
      has_automated_tests?: boolean;
    };
    created_at: string;
  } | null;
  gap_analysis: {
    has_assessment: boolean;
    target_career: string;
    gap_items: GapItem[];
    missing_skills: string[];
    priority_areas: { category: string; label: string; gap: number; current: number; target: number }[];
    recommended_actions: string[];
    readiness: {
      overall_indicator: number;
      assessment_coverage_percent: number;
      demonstrated_skill_percent: number;
      project_evidence_percent: number;
      interview_practice_percent: number;
      roadmap_progress_percent: number;
      outstanding_weaknesses: string[];
      disclaimer: string;
    };
  };
  weekly_performance: WeeklyPoint[];
  saved_plans: {
    id: string;
    title: string;
    target_role: string;
    skill_level: string;
    hours_per_week: number;
    target_completion_date: string;
    total_estimated_hours: number;
    created_at: string;
  }[];
}

export const CareerLaunchpadPage: React.FC = () => {
  const { user, addToast } = useApp();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<LaunchpadTab>('overview');
  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Profile form state
  const [profileForm, setProfileForm] = useState<CareerProfile>({
    target_career: 'Software Engineer',
    target_job_role: 'Fresher Software Engineer',
    target_company: '',
    graduation_year: 2026,
    current_skill_level: 'Intermediate',
    available_hours_per_week: 14,
    target_deadline: '',
  });
  const [savingProfile, setSavingProfile] = useState(false);

  // Assessment state
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [deployedProjects, setDeployedProjects] = useState(0);
  const [hasGithubPortfolio, setHasGithubPortfolio] = useState(false);
  const [hasAutomatedTests, setHasAutomatedTests] = useState(false);
  const [submittingAssessment, setSubmittingAssessment] = useState(false);
  const [assessmentError, setAssessmentError] = useState('');

  // Plan generation state
  const [focusNote, setFocusNote] = useState('');
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [savingPlan, setSavingPlan] = useState(false);
  const [draftPlan, setDraftPlan] = useState<any>(null);
  const [dailyHoursInput, setDailyHoursInput] = useState<string>('2');
  const [dailyHoursError, setDailyHoursError] = useState<string>('');

  const draftStorageKey = `brainova_career_assess_draft_${user?.id || 'anon'}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [ov, assess] = await Promise.all([
        apiRequest<OverviewPayload>('/api/career-launchpad/overview'),
        apiRequest<{ questions: AssessmentQuestion[] }>('/api/career-launchpad/assessment'),
      ]);
      setOverview(ov);
      setProfileForm(ov.profile);
      setDailyHoursInput(String(weeklyToDailyHours(ov.profile?.available_hours_per_week)));
      setDailyHoursError('');
      setQuestions(assess.questions || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load Career Launchpad.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Restore saved assessment draft from sessionStorage
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(draftStorageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.answers === 'object') {
          setAnswers(parsed.answers);
        }
      }
    } catch {
      // ignore storage errors
    }
  }, [draftStorageKey]);

  const handleSelectAnswer = (qid: string, optionIdx: number) => {
    setAssessmentError('');
    setAnswers((prev) => {
      const next = { ...prev, [qid]: optionIdx };
      try {
        sessionStorage.setItem(draftStorageKey, JSON.stringify({ answers: next }));
      } catch {
        // ignore storage quota errors
      }
      return next;
    });
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (savingProfile) return;
    const check = validateDailyPrepHours(dailyHoursInput);
    if (!check.valid || check.value === null) {
      setDailyHoursError(check.error);
      return;
    }
    setDailyHoursError('');
    const nextPayload: CareerProfile = {
      ...profileForm,
      available_hours_per_week: dailyToWeeklyHours(check.value),
    };
    setSavingProfile(true);
    try {
      const res = await apiRequest<{ profile: CareerProfile }>('/api/career-launchpad/profile', {
        method: 'PUT',
        body: JSON.stringify(nextPayload),
      });
      setProfileForm(res.profile);
      setDailyHoursInput(String(weeklyToDailyHours(res.profile.available_hours_per_week)));
      addToast('Career profile saved.', 'success');
      await loadData();
    } catch (err: any) {
      addToast(err.message || 'Failed to save career profile.', 'error');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSubmitAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submittingAssessment) return;
    const unanswered = questions.filter((q) => typeof answers[q.id] !== 'number');
    if (unanswered.length > 0) {
      setAssessmentError(
        `Please answer all ${questions.length} questions before submitting (${unanswered.length} remaining).`
      );
      return;
    }
    setSubmittingAssessment(true);
    setAssessmentError('');
    try {
      await apiRequest('/api/career-launchpad/assessment/submit', {
        method: 'POST',
        body: JSON.stringify({
          answers,
          project_evidence: {
            deployed_projects: deployedProjects,
            has_github_portfolio: hasGithubPortfolio,
            has_automated_tests: hasAutomatedTests,
          },
        }),
      });
      try {
        sessionStorage.removeItem(draftStorageKey);
      } catch {
        // ignore
      }
      addToast('Skill assessment graded and saved.', 'success');
      await loadData();
      setActiveTab('gaps');
    } catch (err: any) {
      setAssessmentError(err.message || 'Failed to submit assessment.');
    } finally {
      setSubmittingAssessment(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (generatingPlan) return;
    setGeneratingPlan(true);
    try {
      const res = await apiRequest<{ draft_roadmap: any }>('/api/career-launchpad/plan/generate', {
        method: 'POST',
        body: JSON.stringify({ focus_note: focusNote }),
      });
      setDraftPlan(res.draft_roadmap);
      addToast('Preparation plan draft generated using BRAINOVA AI Roadmap engine.', 'success');
    } catch (err: any) {
      addToast(err.message || 'Unable to generate preparation plan.', 'error');
    } finally {
      setGeneratingPlan(false);
    }
  };

  const handleSavePlanToRoadmaps = async () => {
    if (!draftPlan || savingPlan) return;
    setSavingPlan(true);
    try {
      const res = await apiRequest<{ roadmap: { id: string } }>('/api/roadmaps', {
        method: 'POST',
        body: JSON.stringify({
          title: draftPlan.title,
          target_role: profileForm.target_job_role || profileForm.target_career,
          description: draftPlan.description || '',
          skill_level: profileForm.current_skill_level,
          existing_knowledge: overview?.latest_assessment
            ? `Assessed score: ${overview.latest_assessment.overall_score}%`
            : '',
          target_completion_date: profileForm.target_deadline,
          hours_per_week: profileForm.available_hours_per_week,
          preferred_stack: profileForm.target_career,
          priorities: focusNote,
          exam_goals: profileForm.target_company,
          phases: draftPlan.phases || [],
        }),
      });
      addToast('Preparation plan saved to AI Roadmaps.', 'success');
      setDraftPlan(null);
      await loadData();
      if (res.roadmap?.id) {
        navigate(`/roadmaps/${res.roadmap.id}`);
      }
    } catch (err: any) {
      addToast(err.message || 'Failed to save preparation plan.', 'error');
    } finally {
      setSavingPlan(false);
    }
  };

  const categoryLabels = useMemo(() => {
    const map: Record<string, string> = {};
    (overview?.skill_categories || []).forEach((c) => {
      map[c.key] = c.label;
    });
    return map;
  }, [overview]);

  if (loading) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Loading Career Launchpad…</p>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="card" style={{ padding: '32px' }}>
        <p style={{ color: 'var(--status-danger)', marginBottom: '12px' }}>
          {error || 'Unable to load Career Launchpad.'}
        </p>
        <button type="button" className="btn btn-primary" onClick={loadData}>
          Retry
        </button>
      </div>
    );
  }

  const readiness = overview.gap_analysis.readiness;
  const answeredCount = Object.keys(answers).filter((k) => typeof answers[k] === 'number').length;
  const maxWeeklyMinutes = Math.max(
    30,
    ...overview.weekly_performance.map((w) => w.study_minutes + w.focus_minutes)
  );
  const hasAnyWeeklyActivity = overview.weekly_performance.some(
    (w) => w.study_minutes > 0 || w.focus_minutes > 0 || w.quizzes_completed > 0 || w.assessments_taken > 0
  );

  return (
    <div className="bnv-launchpad-page">
      {/* Hero Banner */}
      <section className="bnv-launchpad-hero">
        <div className="bnv-launchpad-hero-copy">
          <span className="bnv-launchpad-badge">
            <Rocket size={13} />
            <span>BRAINOVA Career Launchpad &amp; AI Mentor</span>
          </span>
          <h1>Internship &amp; Fresher Engineering Launchpad</h1>
          <p>
            Diagnose real technical skill gaps, build a personalized preparation roadmap, track weekly
            momentum, and get visual AI mentorship across programming, CS fundamentals, and general topics.
          </p>
        </div>

        <div className="bnv-readiness-pill-card">
          <div className="bnv-readiness-pill-label">Preparation Indicator</div>
          <div className="bnv-readiness-pill-value">{readiness.overall_indicator}%</div>
          <div className="bnv-readiness-pill-sub">
            {overview.gap_analysis.has_assessment
              ? `${readiness.assessment_coverage_percent}% skills assessed`
              : 'Assessment pending'}
          </div>
        </div>
      </section>

      {/* Section Navigation Tabs */}
      <div className="tabs-bar bnv-launchpad-tabs" role="tablist" aria-label="Career Launchpad sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'overview'}
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          <Briefcase size={15} />
          <span>Career Profile</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'assessment'}
          className={`tab-btn ${activeTab === 'assessment' ? 'active' : ''}`}
          onClick={() => setActiveTab('assessment')}
        >
          <Target size={15} />
          <span>Skill Assessment</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'gaps'}
          className={`tab-btn ${activeTab === 'gaps' ? 'active' : ''}`}
          onClick={() => setActiveTab('gaps')}
        >
          <BarChart3 size={15} />
          <span>Gap Analysis &amp; Readiness</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'plan'}
          className={`tab-btn ${activeTab === 'plan' ? 'active' : ''}`}
          onClick={() => setActiveTab('plan')}
        >
          <Compass size={15} />
          <span>Prep Plan &amp; Weekly</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'mentor'}
          className={`tab-btn ${activeTab === 'mentor' ? 'active' : ''}`}
          onClick={() => setActiveTab('mentor')}
        >
          <Sparkles size={15} />
          <span>AI Mentor</span>
        </button>
      </div>

      {/* TAB 1: CAREER PROFILE */}
      {activeTab === 'overview' && (
        <form className="card bnv-launchpad-card" onSubmit={handleSaveProfile}>
          <h2 className="bnv-section-title">Career Profile</h2>
          <p className="bnv-section-sub">
            Configure your target engineering track, role objective, and preparation timeline.
          </p>

          <div className="bnv-form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="lp-target-career">
                  Target Career Track
                </label>
                <select
                  id="lp-target-career"
                  className="form-select"
                  value={profileForm.target_career}
                  onChange={(e) => setProfileForm((p) => ({ ...p, target_career: e.target.value }))}
                >
                  {overview.careers.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-target-role">
                  Target Job Role / Objective
                </label>
                <input
                  id="lp-target-role"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Software Engineer Intern / Fresher SDE-1"
                  value={profileForm.target_job_role}
                  onChange={(e) => setProfileForm((p) => ({ ...p, target_job_role: e.target.value }))}
                  maxLength={120}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-target-company">
                  Target Company (Optional)
                </label>
                <input
                  id="lp-target-company"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Google, Atlassian, Product Startups"
                  value={profileForm.target_company}
                  onChange={(e) => setProfileForm((p) => ({ ...p, target_company: e.target.value }))}
                  maxLength={120}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-grad-year">
                  Graduation Year
                </label>
                <input
                  id="lp-grad-year"
                  type="number"
                  min={2020}
                  max={2035}
                  className="form-input"
                  value={profileForm.graduation_year}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, graduation_year: Number(e.target.value) || 2026 }))
                  }
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-skill-level">
                  Current Skill Level
                </label>
                <select
                  id="lp-skill-level"
                  className="form-select"
                  value={profileForm.current_skill_level}
                  onChange={(e) => setProfileForm((p) => ({ ...p, current_skill_level: e.target.value }))}
                >
                  <option value="Beginner">Beginner</option>
                  <option value="Intermediate">Intermediate</option>
                  <option value="Advanced">Advanced</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-hours">
                  Available Preparation Hours per Day
                </label>
                <input
                  id="lp-hours"
                  type="text"
                  inputMode="numeric"
                  className="form-input"
                  value={dailyHoursInput}
                  aria-invalid={Boolean(dailyHoursError)}
                  aria-describedby={dailyHoursError ? 'lp-hours-hint lp-hours-error' : 'lp-hours-hint'}
                  onChange={(e) => {
                    const nextRaw = e.target.value;
                    setDailyHoursInput(nextRaw);
                    if (nextRaw.trim() === '') {
                      setDailyHoursError('');
                      return;
                    }
                    const check = validateDailyPrepHours(nextRaw);
                    if (check.valid && check.value !== null) {
                      setDailyHoursError('');
                      setProfileForm((p) => ({
                        ...p,
                        available_hours_per_week: dailyToWeeklyHours(check.value!),
                      }));
                    } else {
                      setDailyHoursError(check.error);
                    }
                  }}
                />
                <span
                  id="lp-hours-hint"
                  style={{ display: 'block', marginTop: '5px', fontSize: '0.76rem', color: 'var(--text-muted)' }}
                >
                  Enter how many hours you can dedicate to preparation each day.
                </span>
                {dailyHoursError && (
                  <span
                    id="lp-hours-error"
                    role="alert"
                    style={{ display: 'block', marginTop: '4px', fontSize: '0.78rem', color: '#f87171', fontWeight: 500 }}
                  >
                    {dailyHoursError}
                  </span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="lp-deadline">
                  Target Preparation Deadline
                </label>
                <input
                  id="lp-deadline"
                  type="date"
                  className="form-input"
                  value={profileForm.target_deadline}
                  onChange={(e) => setProfileForm((p) => ({ ...p, target_deadline: e.target.value }))}
                />
              </div>
            </div>

            <div className="bnv-form-actions">
              <button type="submit" className="btn btn-primary" disabled={savingProfile}>
                <Save size={15} />
                <span>{savingProfile ? 'Saving…' : 'Save Career Profile'}</span>
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setActiveTab('assessment')}
              >
                <Target size={15} />
                <span>Take Skill Assessment</span>
              </button>
            </div>
        </form>
      )}

      {/* TAB 2: SKILL ASSESSMENT */}
      {activeTab === 'assessment' && (
        <form className="card bnv-launchpad-card" onSubmit={handleSubmitAssessment}>
          <div className="bnv-assess-header">
            <div>
              <h2 className="bnv-section-title">9-Domain Technical Skill Assessment</h2>
              <p className="bnv-section-sub">
                Demonstrated proficiency across Programming, DSA, OOP, DBMS, OS, Networks, Web Dev,
                Git, and Practical Projects.
              </p>
            </div>
            <div className="bnv-assess-progress-pill">
              {answeredCount} / {questions.length} answered
            </div>
          </div>

          <div className="progress-track" style={{ marginBottom: '20px' }}>
            <div
              className="progress-fill"
              style={{
                width: `${questions.length > 0 ? Math.round((answeredCount / questions.length) * 100) : 0}%`,
              }}
            />
          </div>

          <div className="bnv-assess-questions">
            {questions.map((q, idx) => (
              <div key={q.id} className="bnv-question-card">
                <div className="bnv-question-meta">
                  <span className="bnv-question-num">Q{idx + 1}</span>
                  <span className="bnv-question-cat">{categoryLabels[q.category] || q.category}</span>
                </div>
                <p className="bnv-question-text">{q.question}</p>
                <div className="bnv-options-list">
                  {q.options.map((opt, optIdx) => {
                    const selected = answers[q.id] === optIdx;
                    return (
                      <button
                        key={optIdx}
                        type="button"
                        className={`bnv-option-btn ${selected ? 'active' : ''}`}
                        onClick={() => handleSelectAnswer(q.id, optIdx)}
                      >
                        <span className="bnv-option-letter">{String.fromCharCode(65 + optIdx)}</span>
                        <span>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="bnv-evidence-box">
            <h3>Practical Project Evidence</h3>
            <div className="bnv-form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="lp-deployed-count">
                  Deployed / Complete Portfolio Projects
                </label>
                <input
                  id="lp-deployed-count"
                  type="number"
                  min={0}
                  max={20}
                  className="form-input"
                  value={deployedProjects}
                  onChange={(e) => setDeployedProjects(Math.max(0, Number(e.target.value) || 0))}
                />
              </div>
              <label className="bnv-checkbox-row">
                <input
                  type="checkbox"
                  checked={hasGithubPortfolio}
                  onChange={(e) => setHasGithubPortfolio(e.target.checked)}
                />
                <span>Public GitHub portfolio with clean READMEs</span>
              </label>
              <label className="bnv-checkbox-row">
                <input
                  type="checkbox"
                  checked={hasAutomatedTests}
                  onChange={(e) => setHasAutomatedTests(e.target.checked)}
                />
                <span>Projects include automated unit/integration tests</span>
              </label>
            </div>
          </div>

          {assessmentError && (
            <div className="bnv-mentor-error-banner" role="alert" style={{ marginTop: '14px' }}>
              <AlertCircle size={16} />
              <span>{assessmentError}</span>
            </div>
          )}

          <div className="bnv-form-actions" style={{ marginTop: '18px' }}>
            <button type="submit" className="btn btn-primary" disabled={submittingAssessment}>
              <CheckCircle2 size={15} />
              <span>{submittingAssessment ? 'Grading…' : 'Submit Assessment'}</span>
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: SKILL GAP ANALYSIS & JOB READINESS */}
      {activeTab === 'gaps' && (
        <div className="bnv-launchpad-grid">
          <div className="card bnv-launchpad-card">
            <h2 className="bnv-section-title">
              Skill Gap Analysis ({overview.gap_analysis.target_career})
            </h2>
            <p className="bnv-section-sub">
              {overview.gap_analysis.has_assessment
                ? 'Comparing your demonstrated assessment scores against target-role benchmarks.'
                : 'No assessment submitted yet. Complete the Skill Assessment to replace unassessed placeholders with real scores.'}
            </p>

            <div className="bnv-gap-list">
              {overview.gap_analysis.gap_items.map((item) => (
                <div key={item.category} className="bnv-gap-row">
                  <div className="bnv-gap-row-head">
                    <span>{item.label}</span>
                    <span className={`bnv-gap-status bnv-gap-status--${item.status}`}>
                      {item.current === null
                        ? `Unassessed · Target ${item.target}%`
                        : `${item.current}% / ${item.target}% target`}
                    </span>
                  </div>
                  <div className="bnv-gap-bar-track">
                    <div
                      className="bnv-gap-bar-target"
                      style={{ left: `${item.target}%` }}
                      title={`Target benchmark: ${item.target}%`}
                    />
                    <div
                      className="bnv-gap-bar-current"
                      style={{ width: `${item.current ?? 0}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card bnv-launchpad-card">
            <h2 className="bnv-section-title">
              <Award size={18} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Job Readiness Indicator
            </h2>
            <div className="bnv-readiness-hero">
              <span className="bnv-readiness-big">{readiness.overall_indicator}%</span>
              <span className="bnv-readiness-caption">Evidence-Based Preparation Score</span>
            </div>

            <div className="bnv-summary-list">
              <div className="bnv-summary-item">
                <span>Assessment Coverage</span>
                <strong>{readiness.assessment_coverage_percent}%</strong>
              </div>
              <div className="bnv-summary-item">
                <span>Demonstrated Skill Avg</span>
                <strong>{readiness.demonstrated_skill_percent}%</strong>
              </div>
              <div className="bnv-summary-item">
                <span>Project Evidence</span>
                <strong>{readiness.project_evidence_percent}%</strong>
              </div>
              <div className="bnv-summary-item">
                <span>Interview / Quiz Practice</span>
                <strong>{readiness.interview_practice_percent}%</strong>
              </div>
              <div className="bnv-summary-item">
                <span>Roadmap Progress</span>
                <strong>{readiness.roadmap_progress_percent}%</strong>
              </div>
            </div>

            {overview.gap_analysis.recommended_actions.length > 0 && (
              <div className="bnv-rec-box">
                <h4>Recommended Next Actions</h4>
                <ul>
                  {overview.gap_analysis.recommended_actions.map((act, i) => (
                    <li key={i}>{act}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bnv-disclaimer-box">
              <ShieldAlert size={16} />
              <span>{readiness.disclaimer}</span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: PERSONALIZED PREPARATION PLAN & WEEKLY PERFORMANCE */}
      {activeTab === 'plan' && (
        <div className="bnv-launchpad-grid">
          <div className="card bnv-launchpad-card">
            <h2 className="bnv-section-title">Personalized Preparation Plan</h2>
            <p className="bnv-section-sub">
              Uses the existing BRAINOVA AI Roadmap engine with your career profile, skill gaps, and deadline.
            </p>

            <div className="form-group">
              <label className="form-label" htmlFor="lp-plan-focus">
                Optional Focus Note
              </label>
              <input
                id="lp-plan-focus"
                type="text"
                className="form-input"
                placeholder="e.g. Emphasize system design and dynamic programming"
                value={focusNote}
                onChange={(e) => setFocusNote(e.target.value)}
                maxLength={400}
              />
            </div>

            <div className="bnv-form-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleGeneratePlan}
                disabled={generatingPlan}
              >
                <Compass size={15} />
                <span>{generatingPlan ? 'Generating Plan…' : 'Generate Preparation Plan'}</span>
              </button>
            </div>

            {draftPlan && (
              <div className="bnv-draft-plan-box">
                <h3>{draftPlan.title}</h3>
                <p className="bnv-section-sub">
                  {(draftPlan.phases || []).length} phases · {draftPlan.total_estimated_hours || 0}h estimated
                </p>
                <ul className="bnv-draft-phase-list">
                  {(draftPlan.phases || []).map((p: any, i: number) => (
                    <li key={i}>
                      <strong>{p.title}</strong> ({(p.topics || []).length} topics)
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSavePlanToRoadmaps}
                  disabled={savingPlan}
                >
                  <Save size={15} />
                  <span>{savingPlan ? 'Saving…' : 'Save to AI Roadmaps'}</span>
                </button>
              </div>
            )}

            <div className="bnv-saved-plans">
              <h4>Your Saved Roadmaps</h4>
              {overview.saved_plans.length === 0 ? (
                <p className="bnv-section-sub">No roadmaps saved yet.</p>
              ) : (
                overview.saved_plans.map((rm) => (
                  <button
                    key={rm.id}
                    type="button"
                    className="bnv-saved-plan-row"
                    onClick={() => navigate(`/roadmaps/${rm.id}`)}
                  >
                    <div>
                      <strong>{rm.title}</strong>
                      <span>
                        {rm.target_role} · {rm.hours_per_week}h/wk
                      </span>
                    </div>
                    <ExternalLink size={14} />
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="card bnv-launchpad-card">
            <h2 className="bnv-section-title">
              <Activity size={18} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Weekly Performance Tracking
            </h2>
            <p className="bnv-section-sub">
              Real activity across study logs, focus sessions, 20-MCQ quizzes, and skill assessments (last 6 weeks).
            </p>

            {!hasAnyWeeklyActivity ? (
              <div className="bnv-empty-weekly">
                No recorded study, focus, or quiz activity in the last 6 weeks yet. Complete a Focus
                session, quiz, or skill assessment to populate your weekly chart.
              </div>
            ) : (
              <div className="bnv-weekly-bars">
                {overview.weekly_performance.map((wk) => {
                  const totalMins = wk.study_minutes + wk.focus_minutes;
                  const pct = Math.max(6, Math.round((totalMins / maxWeeklyMinutes) * 100));
                  return (
                    <div key={wk.week_label} className="bnv-weekly-col">
                      <div className="bnv-weekly-bar-wrap">
                        <div
                          className="bnv-weekly-bar"
                          style={{ height: `${totalMins > 0 ? pct : 4}%` }}
                          title={`${wk.week_label}: ${totalMins}m study/focus, ${wk.quizzes_completed} quizzes, ${wk.assessments_taken} assessments`}
                        />
                      </div>
                      <span className="bnv-weekly-label">{wk.week_label}</span>
                      <span className="bnv-weekly-meta">{totalMins}m</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: INTEGRATED AI MENTOR */}
      {activeTab === 'mentor' && <CareerMentorPanel />}
    </div>
  );
};

