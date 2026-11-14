import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bookmark,
  BookmarkCheck,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Newspaper,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import {
  filterTechPulseStories,
  getVerificationBadgeTone,
  isSafeExternalUrl,
  TechPulseFeedResponse,
  TechPulseStory,
} from '../utils/techPulseHelpers';

function formatUtcToIstLabel(utcString?: string): string {
  if (!utcString) return 'Not yet collected';
  try {
    const dt = new Date(utcString);
    if (Number.isNaN(dt.getTime())) return utcString;
    return (
      new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(dt) + ' IST'
    );
  } catch {
    return utcString;
  }
}

export const TechPulsePage: React.FC = () => {
  const [feed, setFeed] = useState<TechPulseFeedResponse | null>(null);
  const [savedStories, setSavedStories] = useState<TechPulseStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setError('');
    try {
      const [feedRes, savedRes] = await Promise.all([
        apiRequest<TechPulseFeedResponse>('/api/tech-pulse/feed'),
        apiRequest<{ stories: TechPulseStory[] }>('/api/tech-pulse/saved'),
      ]);
      setFeed(feedRes);
      setSavedStories(savedRes.stories || []);
    } catch (err: any) {
      setError(err?.message || 'Unable to load Tech Pulse intelligence feed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setError('');
    try {
      await apiRequest('/api/tech-pulse/refresh', { method: 'POST' });
      await loadData();
    } catch (err: any) {
      setError(err?.message || 'Refresh failed. Showing cached stories.');
    } finally {
      setRefreshing(false);
    }
  };

  const toggleExpand = (storyId: string) => {
    setExpandedIds((prev) => ({ ...prev, [storyId]: !prev[storyId] }));
  };

  const handleToggleBookmark = async (story: TechPulseStory) => {
    if (savingId === story.id) return;
    setSavingId(story.id);
    try {
      if (story.is_saved) {
        await apiRequest(`/api/tech-pulse/saved/${encodeURIComponent(story.id)}`, {
          method: 'DELETE',
        });
        setSavedStories((prev) => prev.filter((item) => item.id !== story.id));
        setFeed((prev) =>
          prev
            ? {
                ...prev,
                stories: prev.stories.map((item) =>
                  item.id === story.id ? { ...item, is_saved: false } : item
                ),
              }
            : prev
        );
      } else {
        const res = await apiRequest<{ saved: boolean; story: TechPulseStory }>(
          `/api/tech-pulse/saved/${encodeURIComponent(story.id)}`,
          { method: 'POST' }
        );
        const savedCopy: TechPulseStory = { ...(res.story || story), is_saved: true };
        setSavedStories((prev) => [
          savedCopy,
          ...prev.filter((item) => item.id !== story.id),
        ]);
        setFeed((prev) =>
          prev
            ? {
                ...prev,
                stories: prev.stories.map((item) =>
                  item.id === story.id ? { ...item, is_saved: true } : item
                ),
              }
            : prev
        );
      }
    } catch (err: any) {
      setError(err?.message || 'Could not update bookmark state.');
    } finally {
      setSavingId(null);
    }
  };

  const categories = useMemo(
    () => ['All', ...(feed?.categories || [])],
    [feed?.categories]
  );

  const visibleStories = useMemo(() => {
    return filterTechPulseStories(feed?.stories || [], {
      category: selectedCategory,
      verifiedOnly,
      query: searchQuery,
    });
  }, [feed?.stories, selectedCategory, verifiedOnly, searchQuery]);

  const showLiveIndicator =
    refreshing ||
    (Boolean(feed?.last_collection_at) && feed?.last_collection_status === 'completed');

  const renderStoryCard = (story: TechPulseStory, isSavedSection = false) => {
    const tone = getVerificationBadgeTone(story.verification_status);
    const expanded = Boolean(expandedIds[story.id]);
    const hasSafeOriginalUrl = isSafeExternalUrl(story.original_source_url);
    const keyPrefix = isSavedSection ? `saved-${story.id}` : story.id;

    return (
      <article key={keyPrefix} className={`tp-story-card tp-tone-${tone}`}>
        <div className="tp-story-meta-top">
          <div className="tp-badges-row">
            <span className={`tp-verif-badge tp-verif-${tone}`}>
              {tone === 'verified' && <CheckCircle2 size={13} />}
              {tone === 'corroborated' && <ShieldCheck size={13} />}
              {tone === 'corrected' && <AlertTriangle size={13} />}
              {story.verification_status}
            </span>
            <span className="tp-category-pill">{story.category}</span>
            {story.is_late_update && story.late_update_label && (
              <span className="tp-late-badge">
                <Clock size={12} />
                {story.late_update_label}
              </span>
            )}
          </div>

          <button
            type="button"
            className={`tp-save-btn ${story.is_saved ? 'is-saved' : ''}`}
            onClick={() => handleToggleBookmark(story)}
            disabled={savingId === story.id}
            aria-label={story.is_saved ? 'Remove from saved stories' : 'Save story'}
          >
            {story.is_saved ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
            <span>{story.is_saved ? 'Saved' : 'Save'}</span>
          </button>
        </div>

        <h3 className="tp-story-title">{story.title}</h3>

        <div className="tp-attribution-row">
          <span className="tp-source-name">{story.original_source_name}</span>
          <span className="tp-dot">•</span>
          <span>Published {story.published_at_ist}</span>
          <span className="tp-dot">•</span>
          <span>Discovered {story.discovered_at_ist}</span>
        </div>

        {story.verification_status === 'Corrected' && story.correction_note && (
          <div className="tp-correction-banner">
            <AlertTriangle size={15} />
            <span>
              <strong>Correction Notice:</strong> {story.correction_note}
            </span>
          </div>
        )}

        <div className="tp-summary-grid">
          <div className="tp-summary-block">
            <span className="tp-summary-label">What Happened</span>
            <p>{story.summary?.what_happened || 'Summary pending verification.'}</p>
          </div>
          <div className="tp-summary-block">
            <span className="tp-summary-label">Why It Matters</span>
            <p>{story.summary?.why_it_matters || 'Impact assessment pending.'}</p>
          </div>
          <div className="tp-summary-block tp-summary-student">
            <span className="tp-summary-label">
              <Sparkles size={12} /> Student & Developer Relevance
            </span>
            <p>
              {story.summary?.student_perspective ||
                'Review the primary source for implementation notes.'}
            </p>
          </div>
        </div>

        {expanded && (
          <div className="tp-expanded-drawer">
            {Array.isArray(story.summary?.important_details) &&
              story.summary.important_details.length > 0 && (
                <div className="tp-drawer-section">
                  <h4>Important Details</h4>
                  <ul>
                    {story.summary.important_details.map((detail, idx) => (
                      <li key={idx}>{detail}</li>
                    ))}
                  </ul>
                </div>
              )}

            {story.summary?.technical_explanation && (
              <div className="tp-drawer-section">
                <h4>Technical Explanation</h4>
                <p>{story.summary.technical_explanation}</p>
              </div>
            )}

            {story.summary?.what_happens_next && (
              <div className="tp-drawer-section">
                <h4>What Happens Next</h4>
                <p>{story.summary.what_happens_next}</p>
              </div>
            )}

            {Array.isArray(story.supporting_sources) && story.supporting_sources.length > 0 && (
              <div className="tp-drawer-section">
                <h4>Supporting Sources ({story.supporting_sources.length})</h4>
                <div className="tp-sources-list">
                  {story.supporting_sources.map((src, idx) =>
                    isSafeExternalUrl(src.url) ? (
                      <a
                        key={`${src.name}-${idx}`}
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="tp-supporting-link"
                      >
                        {src.name} {src.is_official ? '(Official)' : ''}
                        <ExternalLink size={12} />
                      </a>
                    ) : (
                      <span key={`${src.name}-${idx}`} className="tp-supporting-link">
                        {src.name}
                      </span>
                    )
                  )}
                </div>
              </div>
            )}

            {story.summary?.fallback_notice && (
              <p className="tp-fallback-note">{story.summary.fallback_notice}</p>
            )}
          </div>
        )}

        <div className="tp-story-actions">
          <button
            type="button"
            className="tp-expand-btn"
            onClick={() => toggleExpand(story.id)}
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            <span>{expanded ? 'Collapse Technical Brief' : 'Deep Dive & Sources'}</span>
          </button>

          {hasSafeOriginalUrl && (
            <a
              href={story.original_source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="tp-original-link"
            >
              <span>Read Original Source</span>
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </article>
    );
  };

  return (
    <div className="tp-root">
      <div className="tp-shell">
        <header className="tp-header">
          <div className="tp-header-top">
            <div className="tp-brand-block">
              <div className="tp-icon-badge">
                <Newspaper size={22} />
              </div>
              <div>
                <div className="tp-eyebrow-row">
                  <span className="tp-eyebrow">BRAINOVA INTELLIGENCE</span>
                  {showLiveIndicator && (
                    <span className="tp-live-indicator">
                      <span className="tp-live-dot" />
                      {refreshing ? 'Syncing sources' : 'IST Feed Active'}
                    </span>
                  )}
                </div>
                <h1>TECH PULSE</h1>
                <p className="tp-subtitle">
                  Verified daily technology intelligence for students, engineers, and builders.
                </p>
              </div>
            </div>

            <button
              type="button"
              className="tp-refresh-btn"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw size={15} className={refreshing ? 'tp-spin' : ''} />
              <span>{refreshing ? 'Collecting…' : 'Refresh Feed'}</span>
            </button>
          </div>

          <div className="tp-header-divider" />

          <div className="tp-header-meta">
            <div className="tp-meta-chip">
              <Clock size={14} />
              <span>
                IST Date: <strong>{feed?.ist_display_date || 'Today (IST)'}</strong>
              </span>
            </div>
            <div className="tp-meta-chip">
              <ShieldCheck size={14} />
              <span>
                <strong>{feed?.active_source_count ?? 0}</strong> Monitored Sources
              </span>
            </div>
            <div className="tp-meta-chip">
              <span>
                Last Updated: <strong>{formatUtcToIstLabel(feed?.last_collection_at)}</strong>
              </span>
            </div>
          </div>
        </header>

        <section className="tp-controls">
          <div className="tp-search-row">
            <div className="tp-search-box">
              <Search size={16} />
              <input
                type="search"
                placeholder="Search today's verified tech developments, models, CVEs, frameworks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search Tech Pulse stories"
              />
            </div>

            <label className="tp-verified-toggle">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
              />
              <span>Verified & Corroborated only</span>
            </label>
          </div>

          <div className="tp-category-bar" role="tablist" aria-label="Tech Pulse Categories">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                role="tab"
                aria-selected={selectedCategory === cat}
                className={`tp-cat-pill ${selectedCategory === cat ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </section>

        {error && (
          <div className="tp-error-banner" role="alert">
            <AlertTriangle size={16} />
            <span>{error}</span>
            <button type="button" onClick={loadData}>
              Retry
            </button>
          </div>
        )}

        <section className="tp-feed-section">
          <div className="tp-section-heading">
            <h2>
              Today&apos;s Intelligence Feed
              <span className="tp-count-pill">{visibleStories.length}</span>
            </h2>
            <span className="tp-lifecycle-hint">
              00:00–23:59 IST • Unsaved stories expire at midnight IST
            </span>
          </div>

          {loading ? (
            <div className="tp-skeleton-grid" aria-busy="true" aria-label="Loading Tech Pulse stories">
              {[1, 2, 3].map((idx) => (
                <div key={idx} className="tp-skeleton-card" />
              ))}
            </div>
          ) : visibleStories.length === 0 ? (
            <div className="tp-empty-state">
              <div className="tp-empty-emblem">
                <Newspaper size={26} />
              </div>
              <h3>No matching stories in today&apos;s IST feed yet</h3>
              <p>
                Clear active filters or select <strong>Refresh Feed</strong> to collect the latest
                verified updates from official engineering blogs and research feeds.
              </p>
            </div>
          ) : (
            <div className="tp-stories-grid">
              {visibleStories.map((story) => renderStoryCard(story, false))}
            </div>
          )}
        </section>

        <section className="tp-saved-section" aria-label="Saved Stories">
          <div className="tp-section-heading">
            <h2>
              <BookmarkCheck size={18} />
              Saved Stories
              <span className="tp-count-pill">{savedStories.length}</span>
            </h2>
            <span className="tp-lifecycle-hint">
              Private to your account • Preserved across daily IST resets
            </span>
          </div>

          {savedStories.length === 0 ? (
            <div className="tp-saved-empty">
              Bookmark any story above to preserve its structured summary and verified source link in
              your personal intelligence archive.
            </div>
          ) : (
            <div className="tp-stories-grid">
              {savedStories.map((story) => renderStoryCard(story, true))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
