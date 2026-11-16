import React, { useMemo, useState } from 'react';
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Layers,
  Search,
  ShieldCheck,
} from 'lucide-react';

export interface CareerRoadmapTopic {
  topic_id: string;
  title: string;
  difficulty: string;
  estimated_hours: number;
  prerequisites: string[];
  learning_objective: string;
  subtopics: string[];
  category_id: string;
  category_title: string;
  completed: boolean;
  completed_at?: string;
}

export interface CareerRoadmapCategory {
  category_id: string;
  title: string;
  description: string;
  completed_count: number;
  total_count: number;
  progress_percent: number;
  topics: CareerRoadmapTopic[];
}

export interface CareerRoadmapPayload {
  verified: boolean;
  role_key: string | null;
  role_title: string;
  description?: string;
  curriculum_version: string;
  authority_sources?: string[];
  coverage_audit?: {
    category_count: number;
    topic_count: number;
    total_estimated_hours: number;
    prerequisites_valid: boolean;
  };
  completed_topics?: number;
  total_topics?: number;
  overall_progress_percent?: number;
  completed_hours?: number;
  total_hours?: number;
  categories: CareerRoadmapCategory[];
  unavailable_reason?: string;
  supported_roles?: string[];
}

interface CareerRoadmapViewProps {
  roadmap: CareerRoadmapPayload | null | undefined;
  pendingTopicIds: Record<string, boolean>;
  isSwitchingRole?: boolean;
  onToggleTopic: (topicId: string, nextCompleted: boolean) => void;
  onSelectSupportedRole?: (role: string) => void;
}

export const CareerRoadmapView: React.FC<CareerRoadmapViewProps> = ({
  roadmap,
  pendingTopicIds,
  isSwitchingRole = false,
  onToggleTopic,
  onSelectSupportedRole,
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});
  const [expandedSubtopics, setExpandedSubtopics] = useState<Record<string, boolean>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'incomplete' | 'completed'>('all');

  const categories = roadmap?.categories || [];

  // Default: expand first 2 categories on initial render if user hasn't toggled any yet
  const isCategoryExpanded = (categoryId: string, index: number): boolean => {
    if (searchQuery.trim()) return true;
    if (categoryId in expandedCategories) {
      return expandedCategories[categoryId];
    }
    return index < 2;
  };

  const toggleCategory = (categoryId: string, index: number) => {
    const currentlyExpanded = isCategoryExpanded(categoryId, index);
    setExpandedCategories((prev) => ({ ...prev, [categoryId]: !currentlyExpanded }));
  };

  const expandAll = () => {
    const next: Record<string, boolean> = {};
    categories.forEach((c) => {
      next[c.category_id] = true;
    });
    setExpandedCategories(next);
  };

  const collapseAll = () => {
    const next: Record<string, boolean> = {};
    categories.forEach((c) => {
      next[c.category_id] = false;
    });
    setExpandedCategories(next);
  };

  const filteredCategories = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return categories
      .map((cat) => {
        const matchingTopics = cat.topics.filter((t) => {
          if (statusFilter === 'completed' && !t.completed) return false;
          if (statusFilter === 'incomplete' && t.completed) return false;
          if (!q) return true;
          return (
            t.title.toLowerCase().includes(q) ||
            t.learning_objective.toLowerCase().includes(q) ||
            cat.title.toLowerCase().includes(q) ||
            t.subtopics.some((s) => s.toLowerCase().includes(q))
          );
        });
        return { ...cat, visibleTopics: matchingTopics };
      })
      .filter((cat) => !q && statusFilter === 'all' ? true : cat.visibleTopics.length > 0);
  }, [categories, searchQuery, statusFilter]);

  if (!roadmap) {
    return (
      <div className="card bnv-launchpad-card">
        <p className="bnv-section-sub">Loading your role-specific career roadmap...</p>
      </div>
    );
  }

  if (!roadmap.verified) {
    return (
      <div className="card bnv-launchpad-card" data-testid="career-roadmap-unavailable">
        <h2 className="bnv-section-title">Verified Curriculum Unavailable</h2>
        <p className="bnv-section-sub" style={{ marginBottom: '14px' }}>
          {roadmap.unavailable_reason ||
            `A verified curriculum is not yet available for "${roadmap.role_title}".`}
        </p>
        {roadmap.supported_roles && roadmap.supported_roles.length > 0 && (
          <div>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
              Select a verified career role to load its complete roadmap:
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {roadmap.supported_roles.map((r) => (
                <button
                  key={r}
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => onSelectSupportedRole?.(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const overallPct = roadmap.overall_progress_percent ?? 0;
  const completedTopics = roadmap.completed_topics ?? 0;
  const totalTopics = roadmap.total_topics ?? 0;
  const completedHours = roadmap.completed_hours ?? 0;
  const totalHours = roadmap.total_hours ?? 0;
  const ringRadius = 24;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringOffset = ringCircumference - (overallPct / 100) * ringCircumference;

  return (
    <div className="cr-roadmap-root" data-testid="career-roadmap-view">
      {/* Header Summary Card */}
      <div className="card cr-header-card">
        <div className="cr-header-top">
          <div className="cr-header-identity">
            <div className="cr-role-eyebrow">
              <ShieldCheck size={13} />
              <span>
                VERIFIED CURRICULUM · v{roadmap.curriculum_version}
                {isSwitchingRole ? ' · Synchronizing…' : ''}
              </span>
            </div>
            <h2 className="cr-role-title" data-testid="career-roadmap-role-title">
              {roadmap.role_title.toUpperCase()}
            </h2>
            <div className="cr-header-metrics">
              <span className="cr-metric-pill">
                <strong>{completedTopics}</strong> / {totalTopics} mastered
              </span>
              <span className="cr-metric-pill">
                <Clock size={12} />
                ~{totalHours}h est. ({completedHours}h done)
              </span>
            </div>
          </div>

          <div className="cr-overall-stat" data-testid="career-roadmap-overall-progress">
            <div className="cr-ring-wrap" aria-hidden="true">
              <svg className="cr-ring-svg" viewBox="0 0 60 60">
                <circle className="cr-ring-bg" cx="30" cy="30" r={ringRadius} />
                <circle
                  className="cr-ring-fg"
                  cx="30"
                  cy="30"
                  r={ringRadius}
                  strokeDasharray={ringCircumference}
                  strokeDashoffset={ringOffset}
                />
              </svg>
              <span className="cr-ring-label">{overallPct}%</span>
            </div>
          </div>
        </div>

        <div className="cr-overall-bar-track" role="progressbar" aria-valuenow={overallPct} aria-valuemin={0} aria-valuemax={100}>
          <div className="cr-overall-bar-fill" style={{ width: `${overallPct}%` }} />
        </div>

        {/* Filter & Expand Controls */}
        <div className="cr-controls-row">
          <div className="cr-search-wrap">
            <Search size={15} className="cr-search-icon" />
            <input
              type="text"
              className="form-input cr-search-input"
              placeholder="Search categories, topics, or subtopics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search career roadmap topics"
            />
          </div>

          <div className="cr-filter-group">
            {(['all', 'incomplete', 'completed'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`btn btn-sm ${statusFilter === mode ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setStatusFilter(mode)}
              >
                {mode === 'all' ? 'All' : mode === 'incomplete' ? 'Remaining' : 'Completed'}
              </button>
            ))}
            <button type="button" className="btn btn-secondary btn-sm" onClick={expandAll}>
              Expand All
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={collapseAll}>
              Collapse All
            </button>
          </div>
        </div>
      </div>

      {/* Expandable Category Cards */}
      <div className="cr-categories-list">
        {filteredCategories.length === 0 ? (
          <div className="card bnv-launchpad-card">
            <p className="bnv-section-sub">No topics match your current filter.</p>
          </div>
        ) : (
          filteredCategories.map((cat, idx) => {
            const expanded = isCategoryExpanded(cat.category_id, idx);
            return (
              <section
                key={cat.category_id}
                className={`cr-category-card ${expanded ? 'is-expanded' : ''}`}
                data-testid={`cr-category-${cat.category_id}`}
              >
                <button
                  type="button"
                  className="cr-category-header"
                  aria-expanded={expanded}
                  onClick={() => toggleCategory(cat.category_id, idx)}
                >
                  <div className="cr-category-left">
                    <span className="cr-cat-book-icon" aria-hidden="true">
                      <BookOpen size={15} />
                    </span>
                    <div>
                      <div className="cr-category-title">{cat.title}</div>
                      {cat.description && (
                        <div className="cr-category-desc">{cat.description}</div>
                      )}
                    </div>
                  </div>

                  <div className="cr-category-right">
                    <span
                      className="cr-category-count"
                      data-testid={`cr-category-count-${cat.category_id}`}
                    >
                      {cat.completed_count}/{cat.total_count} mastered · {cat.progress_percent}%
                    </span>
                    <div className="cr-cat-bar-track" aria-hidden="true">
                      <div
                        className="cr-cat-bar-fill"
                        style={{ width: `${cat.progress_percent}%` }}
                      />
                    </div>
                    <span className={`cr-chevron ${expanded ? 'is-open' : ''}`} aria-hidden="true">
                      {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    </span>
                  </div>
                </button>

                {expanded && (
                  <div className="cr-topics-list">
                    {cat.visibleTopics.map((topic) => {
                      const isPending = Boolean(pendingTopicIds[topic.topic_id]);
                      const showSubs = Boolean(expandedSubtopics[topic.topic_id]);
                      return (
                        <div
                          key={topic.topic_id}
                          className={`cr-topic-row ${topic.completed ? 'is-completed' : ''}`}
                          data-testid={`cr-topic-row-${topic.topic_id}`}
                        >
                          <button
                            type="button"
                            className={`cr-topic-circle ${topic.completed ? 'is-checked' : ''}`}
                            aria-pressed={topic.completed}
                            aria-label={
                              topic.completed
                                ? `Mark ${topic.title} incomplete`
                                : `Mark ${topic.title} complete`
                            }
                            data-testid={`cr-topic-toggle-${topic.topic_id}`}
                            disabled={isPending}
                            onClick={() => onToggleTopic(topic.topic_id, !topic.completed)}
                          >
                            {topic.completed && <Check size={13} strokeWidth={3} />}
                          </button>

                          <div className="cr-topic-content">
                            <div className="cr-topic-head">
                              <span className="cr-topic-title">{topic.title}</span>
                              <div className="cr-topic-meta">
                                <span
                                  className={`cr-diff-badge cr-diff-${topic.difficulty.toLowerCase()}`}
                                >
                                  {topic.difficulty}
                                </span>
                                <span className="cr-hours-badge">
                                  <Clock size={12} />
                                  {topic.estimated_hours}h
                                </span>
                              </div>
                            </div>

                            {topic.learning_objective && (
                              <p className="cr-topic-obj">{topic.learning_objective}</p>
                            )}

                            {topic.subtopics && topic.subtopics.length > 0 && (
                              <div className="cr-subtopics-wrap">
                                <button
                                  type="button"
                                  className="cr-subtopics-toggle"
                                  onClick={() =>
                                    setExpandedSubtopics((prev) => ({
                                      ...prev,
                                      [topic.topic_id]: !prev[topic.topic_id],
                                    }))
                                  }
                                >
                                  <Layers size={12} />
                                  <span>
                                    {showSubs
                                      ? `Hide ${topic.subtopics.length} subtopics`
                                      : `${topic.subtopics.length} subtopics`}
                                  </span>
                                </button>
                                {showSubs && (
                                  <ul className="cr-subtopics-list">
                                    {topic.subtopics.map((sub, sIdx) => (
                                      <li key={sIdx}>
                                        <BookOpen size={11} />
                                        <span>{sub}</span>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })
        )}
      </div>
    </div>
  );
};
