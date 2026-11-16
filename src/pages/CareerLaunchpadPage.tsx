import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  BarChart3,
  Briefcase,
  CheckCircle2,
  Compass,
  ExternalLink,
  Rocket,
  Save,
  Sparkles,
  Target,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { deduplicatedGet, getCachedEntry, invalidateQueryCache } from '../lib/queryCache';
import { useApp } from '../context/AppContext';
import { CareerMentorPanel } from '../components/CareerMentorPanel';
import { CareerRoadmapPayload, CareerRoadmapView } from '../components/CareerRoadmapView';
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
  career_roadmap?: CareerRoadmapPayload;
  readiness_intelligence?: {
    competency_dimensions: { category: string; label: string; current: number; target: number }[];
    prioritized_gaps: {
      category: string;
      label: string;
      current: number | null;
      target: number;
      gap: number;
      tier: 'critical' | 'important' | 'optional';
      estimated_hours_to_improve: number;
    }[];
    evidence_breakdown: {
      category: string;
      label: string;
      verdict: string;
      reason: string;
    }[];
    top_next_actions: {
      title: string;
      why_it_matters: string;
      what_to_study: string;
      what_to_practice: string;
      expected_hours: number;
      success_metric: string;
    }[];
    has_empirical_data: boolean;
  };
  weekly_tasks?: {
    id: string;
    day_of_week: string;
    topic: string;
    skill_category: string;
    learning_objective: string;
    activity_type: string;
    planned_minutes: number;
    actual_minutes: number;
    priority: string;
    completion_criteria: string;
    status: 'pending' | 'completed' | 'missed' | 'rescheduled';
    source_type: string;
  }[];
  revision_queue?: {
    id: string;
    topic_key: string;
    topic_title: string;
    skill_category: string;
    mastery_score: number;
    interval_days: number;
    repetitions: number;
    next_review_at: string;
    is_due: boolean;
  }[];
  due_revisions_count?: number;
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

  const cachedOv = getCachedEntry<OverviewPayload>('/api/career-launchpad/overview');
  const [activeTab, setActiveTab] = useState<LaunchpadTab>('overview');
  const [overview, setOverview] = useState<OverviewPayload | null>(cachedOv?.data || null);
  const [loading, setLoading] = useState(!cachedOv);
  const [error, setError] = useState('');
  const [newRevTopic, setNewRevTopic] = useState('');
  const [newRevScore, setNewRevScore] = useState<number>(55);
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);
  const [pendingTopicIds, setPendingTopicIds] = useState<Record<string, boolean>>({});
  const [isSwitchingRole, setIsSwitchingRole] = useState(false);
  const roleEpochRef = useRef(0);

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

  const loadData = useCallback(async (force: boolean = false) => {
    if (!getCachedEntry('/api/career-launchpad/overview')) {
      setLoading(true);
    }
    setError('');
    const epochAtStart = roleEpochRef.current;
    try {
      const ov = await deduplicatedGet<OverviewPayload>('/api/career-launchpad/overview', { force });
      if (epochAtStart !== roleEpochRef.current) return;
      setOverview(ov);
      setProfileForm(ov.profile);
      setDailyHoursInput(String(weeklyToDailyHours(ov.profile?.available_hours_per_week)));
      setDailyHoursError('');
    } catch (err: any) {
      if (epochAtStart !== roleEpochRef.current) return;
      setError(err.message || 'Failed to load Career Launchpad.');
    } finally {
      if (epochAtStart === roleEpochRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'assessment' && questions.length === 0) {
      deduplicatedGet<{ questions: AssessmentQuestion[] }>('/api/career-launchpad/assessment')
        .then((res) => setQuestions(res.questions || []))
        .catch(() => {});
    }
  }, [activeTab, questions.length]);

  const handleToggleRoadmapTopic = async (topicId: string, nextCompleted: boolean) => {
    if (pendingTopicIds[topicId] || !overview?.career_roadmap) return;
    const epochAtStart = roleEpochRef.current;
    const activeRole = overview.profile.target_career;

    setPendingTopicIds((prev) => ({ ...prev, [topicId]: true }));

    // Optimistic UI update for instant feedback
    setOverview((prev) => {
      if (!prev?.career_roadmap?.categories) return prev;
      let totalCompleted = 0;
      let totalTopics = 0;
      let completedHours = 0;
      const nextCats = prev.career_roadmap.categories.map((cat) => {
        let catCompleted = 0;
        const nextTopics = cat.topics.map((t) => {
          const isDone = t.topic_id === topicId ? nextCompleted : t.completed;
          if (isDone) {
            catCompleted += 1;
            totalCompleted += 1;
            completedHours += t.estimated_hours || 0;
          }
          totalTopics += 1;
          return t.topic_id === topicId ? { ...t, completed: nextCompleted } : t;
        });
        const catTotal = nextTopics.length;
        return {
          ...cat,
          completed_count: catCompleted,
          progress_percent: catTotal > 0 ? Math.round((catCompleted / catTotal) * 100) : 0,
          topics: nextTopics,
        };
      });
      return {
        ...prev,
        career_roadmap: {
          ...prev.career_roadmap,
          completed_topics: totalCompleted,
          completed_hours: completedHours,
          overall_progress_percent: totalTopics > 0 ? Math.round((totalCompleted / totalTopics) * 100) : 0,
          categories: nextCats,
        },
      };
    });

    try {
      const res = await apiRequest<{
        roadmap: CareerRoadmapPayload;
        weekly_tasks: OverviewPayload['weekly_tasks'];
      }>(`/api/career-launchpad/roadmap/topics/${encodeURIComponent(topicId)}/toggle`, {
        method: 'POST',
        body: JSON.stringify({ completed: nextCompleted, target_career: activeRole }),
      });
      if (epochAtStart !== roleEpochRef.current) return;
      invalidateQueryCache('/api/career-launchpad');
      setOverview((prev) =>
        prev
          ? {
              ...prev,
              career_roadmap: res.roadmap,
              weekly_tasks: res.weekly_tasks,
            }
          : prev
      );
    } catch (err: any) {
      addToast(err.message || 'Failed to update topic progress.', 'error');
      await loadData(true);
    } finally {
      setPendingTopicIds((prev) => {
        const next = { ...prev };
        delete next[topicId];
        return next;
      });
    }
  };

  const handleTaskUpdate = async (
    taskId: string,
    payload: { status?: string; day_of_week?: string; actual_minutes?: number }
  ) => {
    setUpdatingTaskId(taskId);
    const epochAtStart = roleEpochRef.current;
    try {
      const res = await apiRequest<{
        task: any;
        career_roadmap?: CareerRoadmapPayload;
        weekly_tasks?: OverviewPayload['weekly_tasks'];
      }>(`/api/career-launchpad/weekly-plan/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      if (epochAtStart !== roleEpochRef.current) return;
      invalidateQueryCache('/api/career-launchpad');
      setOverview((prev) =>
        prev
          ? {
              ...prev,
              career_roadmap: res.career_roadmap ?? prev.career_roadmap,
              weekly_tasks: res.weekly_tasks ?? prev.weekly_tasks,
            }
          : prev
      );
    } catch (err: any) {
      addToast(err.message || 'Failed to update weekly task.', 'error');
    } finally {
      setUpdatingTaskId(null);
    }
  };

  const handleRegenerateWeeklyPlan = async (preserveExisting: boolean) => {
    try {
      await apiRequest('/api/career-launchpad/weekly-plan/generate', {
        method: 'POST',
        body: JSON.stringify({ preserve_existing: preserveExisting }),
      });
      addToast('Adaptive weekly schedule updated.', 'success');
      await loadData(true);
    } catch (err: any) {
      addToast(err.message || 'Failed to update weekly schedule.', 'error');
    }
  };

  const handleRecordRevision = async (topicTitle: string, skillCat: string, scorePct: number) => {
    const cleanTitle = topicTitle.trim();
    if (!cleanTitle) {
      addToast('Enter a topic name to log revision mastery.', 'error');
      return;
    }
    try {
      await apiRequest('/api/career-launchpad/revisions/record', {
        method: 'POST',
        body: JSON.stringify({
          topic_key: cleanTitle.toLowerCase().replace(/\s+/g, '_'),
          topic_title: cleanTitle,
          skill_category: skillCat,
          score_percent: scorePct,
        }),
      });
      addToast(
        scorePct < 60
          ? `Logged ${scorePct}% — urgent revision scheduled in Weekly Planner.`
          : `Logged ${scorePct}% — next review interval expanded.`,
        'success'
      );
      setNewRevTopic('');
      await loadData(true);
    } catch (err: any) {
      addToast(err.message || 'Failed to record revision.', 'error');
    }
  };

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

  const syncRoleProfileUpdate = async (nextPayload: CareerProfile) => {
    const nextEpoch = ++roleEpochRef.current;
    setSavingProfile(true);
    setIsSwitchingRole(true);
    invalidateQueryCache('/api/career-launchpad');
    try {
      const res = await apiRequest<{
        profile: CareerProfile;
        career_roadmap?: CareerRoadmapPayload;
        weekly_tasks?: OverviewPayload['weekly_tasks'];
      }>('/api/career-launchpad/profile', {
        method: 'PUT',
        body: JSON.stringify(nextPayload),
      });
      if (nextEpoch !== roleEpochRef.current) return;
      setProfileForm(res.profile);
      setDailyHoursInput(String(weeklyToDailyHours(res.profile.available_hours_per_week)));
      setOverview((prev) =>
        prev
          ? {
              ...prev,
              profile: res.profile,
              career_roadmap: res.career_roadmap ?? prev.career_roadmap,
              weekly_tasks: res.weekly_tasks ?? prev.weekly_tasks,
            }
          : prev
      );
      addToast(`Career profile & roadmap synchronized to ${res.profile.target_career}.`, 'success');
      await loadData(true);
    } catch (err: any) {
      if (nextEpoch !== roleEpochRef.current) return;
      addToast(err.message || 'Failed to save career profile.', 'error');
    } finally {
      if (nextEpoch === roleEpochRef.current) {
        setSavingProfile(false);
        setIsSwitchingRole(false);
      }
    }
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
    await syncRoleProfileUpdate(nextPayload);
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
      addToast('Preparation plan draft generated using StudyOS AI Roadmap engine.', 'success');
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

  if (loading && !overview) {
    return (
      <div className="bnv-launchpad-page">
        <section className="bnv-launchpad-hero">
          <div className="bnv-launchpad-hero-copy">
            <span className="bnv-launchpad-badge">
              <Rocket size={13} />
              <span>StudyOS Career Launchpad &amp; AI Mentor</span>
            </span>
            <h1>Internship &amp; Fresher Engineering Launchpad</h1>
            <p>
              Follow your role-specific Career Roadmap, synchronize weekly execution, and get AI mentorship.
            </p>
          </div>
        </section>
        <div className="card bnv-launchpad-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ height: '22px', width: '240px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)' }} />
          <div style={{ height: '64px', width: '100%', borderRadius: '10px', background: 'rgba(255,255,255,0.04)' }} />
          <div style={{ height: '64px', width: '100%', borderRadius: '10px', background: 'rgba(255,255,255,0.04)' }} />
        </div>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="card" style={{ padding: '32px' }}>
        <p style={{ color: 'var(--status-danger)', marginBottom: '12px' }}>
          {error || 'Unable to load Career Launchpad.'}
        </p>
        <button type="button" className="btn btn-primary" onClick={() => loadData(true)}>
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
            <span>StudyOS Career Launchpad &amp; AI Mentor</span>
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
          <span>Career Roadmap</span>
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

      {/* TAB 3: COMPLETE ROLE-SPECIFIC CAREER ROADMAP */}
      {activeTab === 'gaps' && (
        <CareerRoadmapView
          roadmap={overview.career_roadmap}
          pendingTopicIds={pendingTopicIds}
          isSwitchingRole={isSwitchingRole}
          onToggleTopic={handleToggleRoadmapTopic}
          onSelectSupportedRole={(role) =>
            syncRoleProfileUpdate({ ...profileForm, target_career: role })
          }
        />
      )}

      {/* TAB 4: PERSONALIZED PREPARATION PLAN & WEEKLY PERFORMANCE */}
      {activeTab === 'plan' && (
        <div className="bnv-launchpad-grid">
          <div className="card bnv-launchpad-card">
            <h2 className="bnv-section-title">Personalized Preparation Plan</h2>
            <p className="bnv-section-sub">
              Uses the existing StudyOS AI Roadmap engine with your career profile, skill gaps, and deadline.
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

          {/* FEATURE 1: Adaptive Weekly Execution Planner */}
          <div className="card bnv-launchpad-card" style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
              <div>
                <h2 className="bnv-section-title">Adaptive Weekly Execution Planner</h2>
                <p className="bnv-section-sub">
                  Calibrated to your {overview.profile.available_hours_per_week} hrs/week availability and {overview.profile.target_career} roadmap.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleRegenerateWeeklyPlan(false)}
              >
                Rebalance Pending Tasks
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {(overview.weekly_tasks || []).length === 0 ? (
                <p className="bnv-section-sub">No weekly tasks scheduled yet.</p>
              ) : (
                (overview.weekly_tasks || []).map((task) => (
                  <div
                    key={task.id}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '10px',
                      background: 'var(--bg-charcoal)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                    }}
                  >
                    <div style={{ flex: '1 1 280px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span className="badge badge-indigo">{task.day_of_week}</span>
                        <strong>{task.topic}</strong>
                        <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                          {task.skill_category} · {task.priority} · {task.planned_minutes}m planned ({task.actual_minutes}m logged) · {task.status}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        {task.learning_objective} · Criteria: {task.completion_criteria}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                      <select
                        className="form-select"
                        style={{ width: '82px', padding: '4px 6px', fontSize: '0.8rem' }}
                        value={task.day_of_week}
                        disabled={updatingTaskId === task.id}
                        onChange={(e) => handleTaskUpdate(task.id, { day_of_week: e.target.value, status: 'rescheduled' })}
                      >
                        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={updatingTaskId === task.id || task.status === 'completed'}
                        onClick={() => handleTaskUpdate(task.id, { status: 'completed', actual_minutes: task.planned_minutes })}
                      >
                        {task.status === 'completed' ? 'Completed' : 'Complete'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={updatingTaskId === task.id}
                        onClick={() => handleTaskUpdate(task.id, { status: 'missed' })}
                      >
                        Missed
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* FEATURE 2: Spaced-Repetition Mastery Tracker */}
          <div className="card bnv-launchpad-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="bnv-section-title">
              Spaced-Repetition Mastery Tracker ({overview.due_revisions_count || 0} Due)
            </h2>
            <p className="bnv-section-sub">
              Tracks topic-level retention using explainable intervals. Scores under 60% automatically schedule urgent revision in your Weekly Planner.
            </p>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '14px', alignItems: 'center' }}>
              <input
                type="text"
                className="form-input"
                style={{ flex: '1 1 220px', maxWidth: '340px' }}
                placeholder="Topic reviewed (e.g. Dynamic Programming)"
                value={newRevTopic}
                onChange={(e) => setNewRevTopic(e.target.value)}
              />
              <input
                type="number"
                min={0}
                max={100}
                className="form-input"
                style={{ width: '96px' }}
                value={newRevScore}
                onChange={(e) => setNewRevScore(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                title="Revision Quiz / Practice Score (%)"
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleRecordRevision(newRevTopic, 'dsa', newRevScore)}
              >
                Log Revision Score
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {(overview.revision_queue || []).length === 0 ? (
                <p className="bnv-section-sub">No spaced-repetition items logged yet. Log a topic revision above to start tracking intervals.</p>
              ) : (
                (overview.revision_queue || []).map((rev) => (
                  <div
                    key={rev.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '10px',
                      background: 'var(--bg-charcoal)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '10px',
                      fontSize: '0.84rem',
                    }}
                  >
                    <div>
                      <strong>{rev.topic_title}</strong>{' '}
                      <span style={{ color: 'var(--text-muted)' }}>
                        · Mastery {rev.mastery_score}% · Interval {rev.interval_days}d · Repetitions {rev.repetitions}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className="badge badge-indigo">
                        {rev.is_due ? 'Due Now' : `Next: ${rev.next_review_at.slice(0, 10)}`}
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleRecordRevision(rev.topic_title, rev.skill_category, 85)}
                      >
                        Mark Strong (85%)
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: INTEGRATED AI MENTOR */}
      {activeTab === 'mentor' && <CareerMentorPanel />}
    </div>
  );
};

