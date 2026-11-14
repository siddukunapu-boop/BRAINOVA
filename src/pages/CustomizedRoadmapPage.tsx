import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sliders,
  Video,
  BookOpen,
  CheckCircle2,
  Trash2,
  Save,
  RotateCcw,
  Search,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';
import { InlineYouTubePlayer } from '../components/InlineYouTubePlayer';
import { YouTubeTutorialActions } from '../components/YouTubeTutorialActions';

export const CustomizedRoadmapPage: React.FC = () => {
  const { addToast } = useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [roadmaps, setRoadmaps] = useState<any[]>([]);
  const [selectedRoadmapId, setSelectedRoadmapId] = useState<string>(
    searchParams.get('roadmap') || ''
  );
  const [roadmapDetail, setRoadmapDetail] = useState<any | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<string>(
    searchParams.get('topic') || ''
  );
  const [topicDetail, setTopicDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingTopic, setLoadingTopic] = useState(false);

  // Customized Tutorial Form State
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [customTutTitle, setCustomTutTitle] = useState('');
  const [customTutChannel, setCustomTutChannel] = useState('');
  const [customTutDuration, setCustomTutDuration] = useState('25m');
  const [validatedVideo, setValidatedVideo] = useState<any | null>(null);
  const [validatingUrl, setValidatingUrl] = useState(false);
  const [savingTutorial, setSavingTutorial] = useState(false);
  const [confirmRestoreTutorial, setConfirmRestoreTutorial] = useState(false);
  const [showInlinePlayer, setShowInlinePlayer] = useState(false);

  // Customized Reading Material Form State
  const [customReadingTitle, setCustomReadingTitle] = useState('');
  const [customReadingMarkdown, setCustomReadingMarkdown] = useState('');
  const [savingReading, setSavingReading] = useState(false);
  const [confirmRestoreReading, setConfirmRestoreReading] = useState(false);

  // Load all user roadmaps
  useEffect(() => {
    const loadRoadmapsList = async () => {
      setLoading(true);
      try {
        const res = await apiRequest<{ roadmaps: any[] }>('/api/roadmaps');
        const list = res.roadmaps || [];
        setRoadmaps(list);
        if (list.length > 0) {
          const initialRmId =
            searchParams.get('roadmap') &&
            list.some((r) => r.id === searchParams.get('roadmap'))
              ? (searchParams.get('roadmap') as string)
              : list[0].id;
          setSelectedRoadmapId(initialRmId);
        }
      } catch (err: any) {
        addToast(err.message || 'Could not load roadmaps.', 'error');
      } finally {
        setLoading(false);
      }
    };
    loadRoadmapsList();
  }, []);

  // Load selected roadmap phases & topics
  useEffect(() => {
    if (!selectedRoadmapId) return;
    const loadRmDetail = async () => {
      try {
        const res = await apiRequest<{ roadmap: any }>(`/api/roadmaps/${selectedRoadmapId}`);
        const rm = res.roadmap;
        setRoadmapDetail(rm);

        const allTopics: any[] = [];
        (rm.phases || []).forEach((p: any) => {
          (p.topics || []).forEach((t: any) => {
            allTopics.push({ ...t, phase_order: p.phase_order, phase_title: p.title });
          });
        });

        const paramTopic = searchParams.get('topic');
        if (paramTopic && allTopics.some((t) => t.id === paramTopic)) {
          setSelectedTopicId(paramTopic);
        } else if (allTopics.length > 0) {
          setSelectedTopicId(allTopics[0].id);
        }
      } catch (err: any) {
        addToast(err.message || 'Could not load roadmap topics.', 'error');
      }
    };
    loadRmDetail();
  }, [selectedRoadmapId]);

  // Load selected topic detail
  const fetchSelectedTopic = async (topicId: string) => {
    if (!topicId) return;
    setLoadingTopic(true);
    try {
      const res = await apiRequest<{ topic: any }>(`/api/topics/${topicId}?auto_prepare=true`);
      const t = res.topic;
      setTopicDetail(t);

      // Populate custom reading form if custom reading exists
      if (t.reading) {
        setCustomReadingTitle(
          t.reading.has_custom_reading && t.reading.custom_title
            ? t.reading.custom_title
            : `${t.title} — Customized Study Guide`
        );
        setCustomReadingMarkdown(
          t.reading.has_custom_reading && t.reading.custom_markdown
            ? t.reading.custom_markdown
            : ''
        );
      }

      // Populate custom tutorial form if custom tutorial is active
      const activeTut = (t.tutorials || [])[0];
      if (activeTut && activeTut.is_user_added) {
        setYoutubeUrl(activeTut.url || '');
        setCustomTutTitle(activeTut.title || '');
        setCustomTutChannel(activeTut.channel || '');
        setCustomTutDuration(activeTut.duration || '25m');
      } else {
        setYoutubeUrl('');
        setCustomTutTitle('');
        setCustomTutChannel('');
        setValidatedVideo(null);
      }
    } catch (err: any) {
      addToast(err.message || 'Could not load topic details.', 'error');
    } finally {
      setLoadingTopic(false);
    }
  };

  useEffect(() => {
    if (selectedTopicId) {
      setSearchParams({ roadmap: selectedRoadmapId, topic: selectedTopicId });
      fetchSelectedTopic(selectedTopicId);
    }
  }, [selectedTopicId]);

  // Validate YouTube URL via Backend oEmbed & Video ID Validator
  const handleValidateYoutubeUrl = async () => {
    if (!youtubeUrl.trim()) {
      addToast('Please paste a YouTube tutorial URL first.', 'error');
      return;
    }
    setValidatingUrl(true);
    try {
      const res = await apiRequest<any>('/api/tutorials/validate-url', {
        method: 'POST',
        body: JSON.stringify({ url: youtubeUrl.trim() }),
      });
      setValidatedVideo(res);
      if (res.title && !customTutTitle.trim()) setCustomTutTitle(res.title);
      if (res.channel && !customTutChannel.trim()) setCustomTutChannel(res.channel);
      addToast('Validated YouTube Tutorial URL!', 'success');
    } catch (err: any) {
      setValidatedVideo(null);
      addToast(err.message || 'Invalid YouTube URL.', 'error');
    } finally {
      setValidatingUrl(false);
    }
  };

  // Save Customized Tutorial
  const handleSaveCustomTutorial = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTopicId || !youtubeUrl.trim()) {
      addToast('Please enter a valid YouTube URL.', 'error');
      return;
    }
    setSavingTutorial(true);
    try {
      await apiRequest(`/api/topics/${selectedTopicId}/tutorials`, {
        method: 'POST',
        body: JSON.stringify({
          url: youtubeUrl.trim(),
          title:
            customTutTitle.trim() ||
            validatedVideo?.title ||
            `${topicDetail?.title || 'Topic'} — Customized Tutorial`,
          channel:
            customTutChannel.trim() || validatedVideo?.channel || 'Custom YouTube Educator',
          duration: customTutDuration.trim() || '25m',
          notes: '',
        }),
      });
      await fetchSelectedTopic(selectedTopicId);
      addToast(
        'Saved Customized Tutorial! Original AI tutorial remains safely preserved.',
        'success'
      );
    } catch (err: any) {
      addToast(err.message || 'Failed to save customized tutorial.', 'error');
    } finally {
      setSavingTutorial(false);
    }
  };

  // Remove Customized Tutorial & Restore Original AI Tutorial
  const handleRestoreOriginalTutorial = async () => {
    if (!selectedTopicId) return;
    setSavingTutorial(true);
    try {
      await apiRequest(`/api/topics/${selectedTopicId}/custom-tutorial`, {
        method: 'DELETE',
      });
      setConfirmRestoreTutorial(false);
      await fetchSelectedTopic(selectedTopicId);
      addToast('Removed Customized Tutorial and restored Original AI Tutorial!', 'info');
    } catch (err: any) {
      addToast(err.message || 'Could not restore original tutorial.', 'error');
    } finally {
      setSavingTutorial(false);
    }
  };

  // Pre-fill Custom Reading Editor from Original AI Reading
  const handlePreFillFromOriginalReading = () => {
    if (!topicDetail?.reading) return;
    const r = topicDetail.reading;
    const blocks = [
      `# ${r.title}`,
      '',
      `## Overview`,
      r.overview || '',
      '',
      ...(r.sections || []).map((s: any) => `## ${s.heading}\n${s.content}\n`),
      `## Key Takeaways`,
      ...(r.takeaways || []).map((tk: string) => `- ${tk}`),
      '',
      `## Quick Revision Summary`,
      r.summary || '',
    ];
    setCustomReadingTitle(`${topicDetail.title} — Customized Study Notes`);
    setCustomReadingMarkdown(blocks.join('\n'));
    addToast('Loaded Original AI Reading into editor as a starting template.', 'info');
  };

  // Save Customized Reading Material
  const handleSaveCustomReading = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTopicId || !customReadingMarkdown.trim()) {
      addToast('Please write or paste your customized reading material.', 'error');
      return;
    }
    setSavingReading(true);
    try {
      await apiRequest(`/api/topics/${selectedTopicId}/custom-reading`, {
        method: 'PUT',
        body: JSON.stringify({
          title:
            customReadingTitle.trim() || `${topicDetail?.title} — Customized Reading Material`,
          markdown_content: customReadingMarkdown.trim(),
        }),
      });
      await fetchSelectedTopic(selectedTopicId);
      addToast(
        'Saved Customized Reading Material! Original AI reading remains safely preserved.',
        'success'
      );
    } catch (err: any) {
      addToast(err.message || 'Failed to save customized reading material.', 'error');
    } finally {
      setSavingReading(false);
    }
  };

  // Delete Customized Reading & Restore Original AI Reading
  const handleRestoreOriginalReading = async () => {
    if (!selectedTopicId) return;
    setSavingReading(true);
    try {
      await apiRequest(`/api/topics/${selectedTopicId}/custom-reading`, {
        method: 'DELETE',
      });
      setConfirmRestoreReading(false);
      await fetchSelectedTopic(selectedTopicId);
      addToast('Deleted Customized Reading and restored Original AI Reading!', 'info');
    } catch (err: any) {
      addToast(err.message || 'Could not restore original reading.', 'error');
    } finally {
      setSavingReading(false);
    }
  };

  // Flatten all topics for the selector dropdown
  const allRoadmapTopics: any[] = [];
  if (roadmapDetail?.phases) {
    roadmapDetail.phases.forEach((p: any) => {
      (p.topics || []).forEach((t: any) => {
        allRoadmapTopics.push({
          ...t,
          phase_order: p.phase_order,
          phase_title: p.title,
        });
      });
    });
  }

  const activeTutorial = (topicDetail?.tutorials || [])[0];
  const isCustomTutorialActive = Boolean(activeTutorial?.is_user_added);
  const isCustomReadingActive = Boolean(topicDetail?.reading?.has_custom_reading);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-indigo">
              <Sliders size={12} /> CUSTOMIZED ROADMAP RESOURCE STUDIO
            </span>
            <span className="badge-original">ORIGINAL PRESERVED</span>
            <span className="badge-customized">CUSTOMIZED OVERRIDES</span>
          </div>
          <h1 style={{ fontSize: '1.68rem', marginBottom: '4px' }}>
            Customized Roadmap — Personalize Topic Tutorials & Reading Material
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Select any roadmap and topic to attach your own preferred YouTube tutorial or write custom
            reading notes. Original AI resources are non-destructively preserved and can be restored
            anytime.
          </p>
        </div>

        {selectedRoadmapId && selectedTopicId && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() =>
              navigate(`/roadmaps/${selectedRoadmapId}?expand=${selectedTopicId}`)
            }
          >
            <span>View Topic Inline on Roadmap</span>
            <ArrowRight size={16} />
          </button>
        )}
      </div>

      {loading ? (
        <div className="card" style={{ padding: '48px', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)' }}>Loading roadmaps...</p>
        </div>
      ) : roadmaps.length === 0 ? (
        <div className="card" style={{ padding: '48px', textAlign: 'center' }}>
          <h3 style={{ marginBottom: '8px' }}>No AI Roadmaps Found Yet</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
            Generate a career learning roadmap first, then customize any topic's tutorials or
            reading materials here.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/roadmaps')}
          >
            Go to AI Roadmaps
          </button>
        </div>
      ) : (
        <>
          {/* Step 1: Select Roadmap & Topic */}
          <div className="card">
            <div className="grid-2">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">1. Select Learning Roadmap</label>
                <select
                  className="form-select"
                  value={selectedRoadmapId}
                  onChange={(e) => setSelectedRoadmapId(e.target.value)}
                  aria-label="Select Learning Roadmap"
                >
                  {roadmaps.map((rm) => (
                    <option key={rm.id} value={rm.id}>
                      {rm.title} ({rm.target_role})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">2. Select Roadmap Topic to Customize</label>
                <select
                  className="form-select"
                  value={selectedTopicId}
                  onChange={(e) => setSelectedTopicId(e.target.value)}
                  aria-label="Select Roadmap Topic"
                >
                  {allRoadmapTopics.map((t) => (
                    <option key={t.id} value={t.id}>
                      Phase {t.phase_order}.{t.topic_order}: {t.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Current Topic Status Summary Bar */}
          {topicDetail && (
            <div
              className="card"
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '16px',
                background: 'var(--surface-1)',
              }}
            >
              <div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  SELECTED TOPIC RESOURCE STATUS
                </div>
                <h2 style={{ fontSize: '1.3rem', marginBottom: '6px' }}>{topicDetail.title}</h2>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem' }}>
                    <Video size={14} color="var(--accent-blue)" />
                    <span>Tutorial:</span>
                    <span
                      className={isCustomTutorialActive ? 'badge-customized' : 'badge-original'}
                    >
                      {isCustomTutorialActive ? 'CUSTOMIZED' : 'ORIGINAL'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem' }}>
                    <BookOpen size={14} color="var(--accent-blue)" />
                    <span>Reading Material:</span>
                    <span
                      className={isCustomReadingActive ? 'badge-customized' : 'badge-original'}
                    >
                      {isCustomReadingActive ? 'CUSTOMIZED' : 'ORIGINAL'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem' }}>
                    <ShieldCheck size={14} color="var(--status-success)" />
                    <span>20-MCQ Exam:</span>
                    <span className="badge-original">ORIGINAL (LOCKED FOR INTEGRITY)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {loadingTopic ? (
            <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-secondary)' }}>Loading topic resources...</p>
            </div>
          ) : (
            <div className="grid-2" style={{ alignItems: 'start' }}>
              {/* ============================================================
                  LEFT COLUMN: CUSTOMIZED TUTORIAL EDITOR (YOUTUBE VALIDATION)
                 ============================================================ */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Video size={18} color="var(--accent-blue)" />
                    <h3 style={{ fontSize: '1.15rem', margin: 0 }}>
                      1. Customized YouTube Tutorial
                    </h3>
                  </div>
                  <span
                    className={isCustomTutorialActive ? 'badge-customized' : 'badge-original'}
                  >
                    Active: {isCustomTutorialActive ? 'CUSTOMIZED' : 'ORIGINAL'}
                  </span>
                </div>

                {/* Active Tutorial Preview Card */}
                {activeTutorial && (
                  <div
                    style={{
                      padding: '14px',
                      borderRadius: '12px',
                      background: 'var(--bg-charcoal)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      gap: '14px',
                      alignItems: 'center',
                    }}
                  >
                    {activeTutorial.video_id && (
                      <img
                        src={`https://i.ytimg.com/vi/${activeTutorial.video_id}/hqdefault.jpg`}
                        alt={activeTutorial.title}
                        style={{
                          width: 120,
                          height: 68,
                          borderRadius: '8px',
                          objectFit: 'cover',
                          flexShrink: 0,
                        }}
                      />
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', gap: '6px', marginBottom: '4px' }}>
                        <span
                          className={
                            activeTutorial.is_user_added ? 'badge-customized' : 'badge-original'
                          }
                        >
                          {activeTutorial.is_user_added ? 'CUSTOMIZED' : 'ORIGINAL'}
                        </span>
                        <span className="badge badge-indigo">{activeTutorial.duration}</span>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {activeTutorial.title}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {activeTutorial.channel}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                      <YouTubeTutorialActions
                        url={activeTutorial.url}
                        videoId={activeTutorial.video_id}
                        isInlineOpen={showInlinePlayer}
                        onToggleInline={() => setShowInlinePlayer((v) => !v)}
                        inlineLabelOpen="Hide Player"
                        inlineLabelClosed="Play Inline Here"
                      />
                    </div>
                  </div>
                )}

                {activeTutorial && showInlinePlayer && (
                  <InlineYouTubePlayer
                    url={activeTutorial.url}
                    videoId={activeTutorial.video_id}
                    title={activeTutorial.title}
                  />
                )}

                <form onSubmit={handleSaveCustomTutorial}>
                  <div className="form-group">
                    <label className="form-label">YouTube Video URL</label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="url"
                        className="form-input"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={handleValidateYoutubeUrl}
                        disabled={validatingUrl}
                        style={{ flexShrink: 0 }}
                      >
                        <Search size={14} />
                        <span>{validatingUrl ? 'Checking...' : 'Validate & Preview'}</span>
                      </button>
                    </div>
                  </div>

                  {validatedVideo && (
                    <div
                      style={{
                        padding: '12px',
                        borderRadius: '10px',
                        background: 'rgba(16, 185, 129, 0.1)',
                        border: '1px solid rgba(16, 185, 129, 0.35)',
                        marginBottom: '14px',
                        display: 'flex',
                        gap: '12px',
                        alignItems: 'center',
                      }}
                    >
                      <img
                        src={validatedVideo.thumbnail_url}
                        alt="Validated preview"
                        style={{ width: 96, height: 54, borderRadius: '6px', objectFit: 'cover' }}
                      />
                      <div style={{ fontSize: '0.82rem' }}>
                        <div style={{ color: '#6ee7b7', fontWeight: 700 }}>
                          Verified YouTube Video ID: {validatedVideo.video_id}
                        </div>
                        {validatedVideo.title && <div>Title: {validatedVideo.title}</div>}
                        {validatedVideo.channel && <div>Channel: {validatedVideo.channel}</div>}
                      </div>
                    </div>
                  )}

                  <div className="form-group">
                    <label className="form-label">Tutorial Title (Auto-filled or Custom)</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g., Complete System Design & Caching Masterclass"
                      value={customTutTitle}
                      onChange={(e) => setCustomTutTitle(e.target.value)}
                    />
                  </div>

                  <div className="grid-2">
                    <div className="form-group">
                      <label className="form-label">Channel Name</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g., freeCodeCamp.org"
                        value={customTutChannel}
                        onChange={(e) => setCustomTutChannel(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Estimated Duration</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g., 35m"
                        value={customTutDuration}
                        onChange={(e) => setCustomTutDuration(e.target.value)}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      style={{ flex: 1 }}
                      disabled={savingTutorial}
                    >
                      <Save size={15} />
                      <span>
                        {savingTutorial
                          ? 'Saving Tutorial...'
                          : isCustomTutorialActive
                          ? 'Update Customized Tutorial'
                          : 'Save Customized Tutorial'}
                      </span>
                    </button>

                    {isCustomTutorialActive && (
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => setConfirmRestoreTutorial(true)}
                        disabled={savingTutorial}
                      >
                        <RotateCcw size={15} />
                        <span>Remove & Restore Original</span>
                      </button>
                    )}
                  </div>
                </form>
              </div>

              {/* ============================================================
                  RIGHT COLUMN: CUSTOMIZED READING MATERIAL EDITOR
                 ============================================================ */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BookOpen size={18} color="var(--accent-blue)" />
                    <h3 style={{ fontSize: '1.15rem', margin: 0 }}>
                      2. Customized Reading Material
                    </h3>
                  </div>
                  <span
                    className={isCustomReadingActive ? 'badge-customized' : 'badge-original'}
                  >
                    Active: {isCustomReadingActive ? 'CUSTOMIZED' : 'ORIGINAL'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    Write your own study notes or customize the AI reading guide for this topic.
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handlePreFillFromOriginalReading}
                  >
                    <span>Load Original AI Reading as Template</span>
                  </button>
                </div>

                <form onSubmit={handleSaveCustomReading}>
                  <div className="form-group">
                    <label className="form-label">Customized Reading Title</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g., My Custom Study Guide & Exam Notes"
                      value={customReadingTitle}
                      onChange={(e) => setCustomReadingTitle(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      Customized Reading Content (Markdown / Structured Notes)
                    </label>
                    <textarea
                      className="form-textarea"
                      style={{ minHeight: 230, fontFamily: 'var(--font-sans)' }}
                      placeholder="Write or paste your customized topic reading material, key formulas, architecture notes, and revision points here..."
                      value={customReadingMarkdown}
                      onChange={(e) => setCustomReadingMarkdown(e.target.value)}
                      required
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      style={{ flex: 1 }}
                      disabled={savingReading}
                    >
                      <Save size={15} />
                      <span>
                        {savingReading
                          ? 'Saving Reading Material...'
                          : isCustomReadingActive
                          ? 'Update Customized Reading'
                          : 'Save Customized Reading Material'}
                      </span>
                    </button>

                    {isCustomReadingActive && (
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => setConfirmRestoreReading(true)}
                        disabled={savingReading}
                      >
                        <Trash2 size={15} />
                        <span>Delete & Restore Original</span>
                      </button>
                    )}
                  </div>
                </form>
              </div>
            </div>
          )}
        </>
      )}

      {/* Restore Original Tutorial Confirmation Modal */}
      {confirmRestoreTutorial && (
        <div className="modal-backdrop" onClick={() => setConfirmRestoreTutorial(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', color: 'var(--status-warning)' }}>
              <AlertTriangle size={22} />
              <h3 style={{ margin: 0 }}>Remove Customized Tutorial?</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              Removing your customized tutorial will automatically restore the{' '}
              <strong>Original AI-Recommended Tutorial</strong> for this topic.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmRestoreTutorial(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleRestoreOriginalTutorial}
              >
                Remove & Restore Original Tutorial
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restore Original Reading Confirmation Modal */}
      {confirmRestoreReading && (
        <div className="modal-backdrop" onClick={() => setConfirmRestoreReading(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', color: 'var(--status-warning)' }}>
              <AlertTriangle size={22} />
              <h3 style={{ margin: 0 }}>Delete Customized Reading Material?</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              Deleting your customized reading material will automatically restore the{' '}
              <strong>Original AI-Generated Reading Guide & Diagrams</strong> for this topic.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmRestoreReading(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleRestoreOriginalReading}
              >
                Delete & Restore Original Reading
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

