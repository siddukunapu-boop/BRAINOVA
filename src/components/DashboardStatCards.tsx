import React, { useEffect, useRef, useState } from 'react';
import { Award, BookOpen, Compass, TrendingUp } from 'lucide-react';

export interface DashboardMetrics {
  overall_progress_percent?: number;
  completed_topics?: number;
  total_topics?: number;
  active_roadmaps?: number;
  quiz_attempts_count?: number;
  average_quiz_percentage?: number;
  total_sources?: number;
}

interface DashboardStatCardsProps {
  metrics?: DashboardMetrics;
  loading?: boolean;
}

// Play card entrance stagger only once on initial app load; avoid replaying on rerenders or route changes.
let statsEntranceCompleted = false;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

function useAnimatedNumber(target: number | null, durationMs = 700): number | null {
  const [display, setDisplay] = useState<number | null>(() =>
    target === null ? null : prefersReducedMotion() ? target : 0
  );
  const currentRef = useRef<number>(target === null ? 0 : prefersReducedMotion() ? target : 0);

  useEffect(() => {
    if (target === null) {
      currentRef.current = 0;
      setDisplay(null);
      return;
    }

    if (prefersReducedMotion()) {
      currentRef.current = target;
      setDisplay(target);
      return;
    }

    const startValue = currentRef.current;
    if (startValue === target) {
      setDisplay(target);
      return;
    }

    let rafId = 0;
    const startTime = performance.now();

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / durationMs);
      // Cubic ease-out
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = Math.round(startValue + (target - startValue) * eased);
      currentRef.current = next;
      setDisplay(next);

      if (progress < 1) {
        rafId = window.requestAnimationFrame(step);
      } else {
        currentRef.current = target;
        setDisplay(target);
      }
    };

    rafId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(rafId);
  }, [target, durationMs]);

  return display;
}

export const DashboardStatCards: React.FC<DashboardStatCardsProps> = ({
  metrics = {},
  loading = false,
}) => {
  const [shouldEnter] = useState(() => !statsEntranceCompleted);
  const [barsReady, setBarsReady] = useState(() => prefersReducedMotion());

  useEffect(() => {
    if (!statsEntranceCompleted) {
      const timer = window.setTimeout(() => {
        statsEntranceCompleted = true;
      }, 750);
      return () => window.clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    if (loading || prefersReducedMotion()) {
      setBarsReady(prefersReducedMotion());
      return;
    }
    const raf = window.requestAnimationFrame(() => setBarsReady(true));
    return () => window.cancelAnimationFrame(raf);
  }, [loading]);

  const rawProgress = Math.max(0, Math.min(100, Math.round(Number(metrics.overall_progress_percent ?? 0))));
  const rawCompletedTopics = Number(metrics.completed_topics ?? 0);
  const rawTotalTopics = Number(metrics.total_topics ?? 0);
  const rawRoadmaps = Number(metrics.active_roadmaps ?? 0);
  const rawQuizAttempts = Number(metrics.quiz_attempts_count ?? 0);
  const rawQuizAvg =
    rawQuizAttempts > 0 && metrics.average_quiz_percentage !== undefined && metrics.average_quiz_percentage !== null
      ? Math.max(0, Math.min(100, Math.round(Number(metrics.average_quiz_percentage))))
      : null;
  const rawSources = Number(metrics.total_sources ?? 0);

  const animatedProgress = useAnimatedNumber(loading ? null : rawProgress, 720);
  const animatedRoadmaps = useAnimatedNumber(loading ? null : rawRoadmaps, 650);
  const animatedQuizAvg = useAnimatedNumber(loading ? null : rawQuizAvg, 760);
  const animatedSources = useAnimatedNumber(loading ? null : rawSources, 650);

  if (loading) {
    return (
      <div className="grid-4 bnv-stats-grid" aria-busy="true" aria-label="Loading dashboard statistics">
        {[0, 1, 2, 3].map((idx) => (
          <div key={idx} className="bnv-stat-card bnv-stat-card--skeleton">
            <div className="bnv-stat-head">
              <span className="bnv-skeleton-line bnv-skeleton-line--sm" />
              <span className="bnv-skeleton-icon" />
            </div>
            <div className="bnv-skeleton-line bnv-skeleton-line--lg" />
            <div className="bnv-skeleton-line bnv-skeleton-line--md" />
          </div>
        ))}
      </div>
    );
  }

  const ringSize = 44;
  const ringStroke = 3.5;
  const ringRadius = (ringSize - ringStroke) / 2;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringTargetPercent = barsReady && rawQuizAvg !== null ? rawQuizAvg : 0;
  const ringDashOffset = ringCircumference * (1 - ringTargetPercent / 100);

  return (
    <div className={`grid-4 bnv-stats-grid${shouldEnter ? ' is-entering' : ''}`}>
      {/* 1. OVERALL PROGRESS */}
      <div className="bnv-stat-card bnv-stat-card--progress" style={{ ['--stat-delay' as string]: '0ms' }}>
        <div className="bnv-stat-head">
          <span className="bnv-stat-label">OVERALL PROGRESS</span>
          <span className="bnv-stat-icon-badge bnv-stat-icon-badge--cyan" aria-hidden="true">
            <TrendingUp size={16} />
          </span>
        </div>
        <div className="bnv-stat-value">{animatedProgress ?? 0}%</div>
        <div className="bnv-stat-progress-track" aria-hidden="true">
          <div
            className="bnv-stat-progress-fill"
            style={{ width: `${barsReady ? rawProgress : 0}%` }}
          />
        </div>
        <div className="bnv-stat-sub">
          {rawCompletedTopics} of {rawTotalTopics} topics completed
        </div>
      </div>

      {/* 2. ACTIVE ROADMAPS */}
      <div className="bnv-stat-card bnv-stat-card--roadmaps" style={{ ['--stat-delay' as string]: '70ms' }}>
        <div className="bnv-stat-head">
          <span className="bnv-stat-label">ACTIVE ROADMAPS</span>
          <span className="bnv-stat-icon-badge bnv-stat-icon-badge--violet" aria-hidden="true">
            <Compass size={16} />
          </span>
        </div>
        <div className="bnv-stat-value">{animatedRoadmaps ?? 0}</div>
        <div className="bnv-stat-sub bnv-stat-sub--spaced">
          Structured career &amp; subject plans
        </div>
      </div>

      {/* 3. QUIZ MASTERY AVG */}
      <div className="bnv-stat-card bnv-stat-card--quiz" style={{ ['--stat-delay' as string]: '140ms' }}>
        <div className="bnv-stat-head">
          <span className="bnv-stat-label">QUIZ MASTERY AVG</span>
          <span className="bnv-stat-icon-badge bnv-stat-icon-badge--gold" aria-hidden="true">
            <Award size={16} />
          </span>
        </div>
        <div className="bnv-stat-quiz-row">
          <div className="bnv-stat-value">
            {rawQuizAvg !== null ? `${animatedQuizAvg ?? rawQuizAvg}%` : '—'}
          </div>
          <svg
            className="bnv-stat-ring"
            width={ringSize}
            height={ringSize}
            viewBox={`0 0 ${ringSize} ${ringSize}`}
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="bnvQuizGoldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#fde68a" />
                <stop offset="55%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#f59e0b" />
              </linearGradient>
            </defs>
            <circle
              className="bnv-stat-ring-track"
              cx={ringSize / 2}
              cy={ringSize / 2}
              r={ringRadius}
              strokeWidth={ringStroke}
            />
            <circle
              className="bnv-stat-ring-fill"
              cx={ringSize / 2}
              cy={ringSize / 2}
              r={ringRadius}
              strokeWidth={ringStroke}
              stroke="url(#bnvQuizGoldGrad)"
              strokeDasharray={ringCircumference}
              strokeDashoffset={ringDashOffset}
            />
          </svg>
        </div>
        <div className="bnv-stat-sub">
          Across {rawQuizAttempts} recorded exam attempt(s)
        </div>
      </div>

      {/* 4. STUDY SOURCES */}
      <div className="bnv-stat-card bnv-stat-card--sources" style={{ ['--stat-delay' as string]: '210ms' }}>
        <div className="bnv-stat-head">
          <span className="bnv-stat-label">STUDY SOURCES</span>
          <span className="bnv-stat-icon-badge bnv-stat-icon-badge--emerald" aria-hidden="true">
            <BookOpen size={16} />
          </span>
        </div>
        <div className="bnv-stat-value">{animatedSources ?? 0}</div>
        <div className="bnv-stat-sub bnv-stat-sub--spaced">
          {rawSources} indexed study source(s)
        </div>
      </div>
    </div>
  );
};

