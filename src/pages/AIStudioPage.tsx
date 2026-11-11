import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  Headphones,
  Film,
  Presentation,
  GitBranch,
  BookOpen,
  Layers,
  CheckSquare,
  LayoutGrid,
  Table,
  Upload,
  FileText,
  X,
  Library,
  Globe,
  Clock,
  CheckCircle2,
  ArrowRight,
  Plus,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

interface StudioToolMeta {
  id: string;
  name: string;
  tagline: string;
  icon: any;
  badge: string;
}

const STUDIO_TOOLS: StudioToolMeta[] = [
  {
    id: 'audio_overview',
    name: '1. Audio Overview',
    tagline: 'Two-host spoken podcast dialogue with playable WAV synthesis in 6 languages',
    icon: Headphones,
    badge: 'Playable Podcast',
  },
  {
    id: 'video_overview',
    name: '2. Video Overview',
    tagline: '1080p HD educational video with rendered visual slides, diagrams & spoken voiceover',
    icon: Film,
    badge: '1080p HD Video',
  },
  {
    id: 'slide_deck',
    name: '3. Slide Deck',
    tagline: 'Structured presentation slides with speaker notes, reordering & HTML export',
    icon: Presentation,
    badge: 'Presentation',
  },
  {
    id: 'mind_map',
    name: '4. Mind Map',
    tagline: 'Interactive expandable knowledge graph with pan, zoom & node inspector',
    icon: GitBranch,
    badge: 'Knowledge Graph',
  },
  {
    id: 'study_guide',
    name: '5. Study Guide / Report',
    tagline: 'Comprehensive study guide with architecture, terminology, examples & summary',
    icon: BookOpen,
    badge: 'Deep Report',
  },
  {
    id: 'flashcards',
    name: '6. Flashcards',
    tagline: 'Spaced-repetition flip cards with Known / Learning / Review mastery tracking',
    icon: Layers,
    badge: 'Active Recall',
  },
  {
    id: 'quiz',
    name: '7. Quiz',
    tagline: '20-question validated 4-option MCQ examination with server-side grading',
    icon: CheckSquare,
    badge: '20-MCQ Exam',
  },
  {
    id: 'infographic',
    name: '8. Infographic',
    tagline: 'Visual educational poster with stat metrics, stage hierarchy & comparisons',
    icon: LayoutGrid,
    badge: 'Visual Poster',
  },
  {
    id: 'data_table',
    name: '9. Data Table',
    tagline: 'Structured concept, formula & comparison matrix with sorting & CSV export',
    icon: Table,
    badge: 'CSV & Sortable',
  },
];

const SUPPORTED_LANGUAGES = [
  { value: 'English', label: 'English' },
  { value: 'Telugu', label: 'Telugu (తెలుగు)' },
  { value: 'Hindi', label: 'Hindi (हिन्दी)' },
  { value: 'Kannada', label: 'Kannada (ಕನ್ನಡ)' },
  { value: 'Tamil', label: 'Tamil (தமிழ்)' },
  { value: 'Marathi', label: 'Marathi (मराठी)' },
];

export const AIStudioPage: React.FC = () => {
  const { user, addToast } = useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedTool, setSelectedTool] = useState<string>(
    searchParams.get('tool') || 'audio_overview'
  );
  const [sources, setSources] = useState<any[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [recentOutputs, setRecentOutputs] = useState<any[]>([]);
  const [generating, setGenerating] = useState(false);

  // Direct Inline Resource Upload / Paste Modal State (Step 1)
  const [showInlineUpload, setShowInlineUpload] = useState(false);
  const [inlineTab, setInlineTab] = useState<'file' | 'text'>('file');
  const [uploadFileObj, setUploadFileObj] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteText, setPasteText] = useState('');
  const [uploadingResource, setUploadingResource] = useState(false);

  // Step 2: Tool Configuration Inputs
  const [customTitle, setCustomTitle] = useState('');
  const [topicFocus, setTopicFocus] = useState('');
  const [audienceLevel, setAudienceLevel] = useState('Intermediate');
  const [language, setLanguage] = useState(user?.preferences?.preferred_language || 'English');

  // Video Overview Specific Controls (Part 6)
  const [videoDuration, setVideoDuration] = useState('3–5 minutes');
  const [videoStyle, setVideoStyle] = useState('Concept Breakdown & Architecture');

  // Audio Overview Specific Controls
  const [audioDuration, setAudioDuration] = useState('Standard (3-5 min)');
  const [audioStyle, setAudioStyle] = useState('Deep-Dive Conversational Podcast');

  // Quiz Specific Controls
  const [quizCount, setQuizCount] = useState(20);
  const [practiceMode, setPracticeMode] = useState(false);

  // Data Table Specific Controls
  const [extractionType, setExtractionType] = useState('Concept Comparisons & Definitions');
  const [extractionInstructions, setExtractionInstructions] = useState('');

  const loadStudioData = async () => {
    try {
      const [srcRes, outRes] = await Promise.all([
        apiRequest<{ sources: any[] }>('/api/sources?status_filter=ready'),
        apiRequest<{ outputs: any[] }>('/api/studio/outputs'),
      ]);
      const readySources = srcRes.sources || [];
      setSources(readySources);
      setRecentOutputs((outRes.outputs || []).slice(0, 6));

      const paramSources = searchParams.get('sources');
      if (paramSources) {
        setSelectedSourceIds(paramSources.split(',').filter(Boolean));
      } else if (readySources.length > 0 && selectedSourceIds.length === 0) {
        setSelectedSourceIds([readySources[0].id]);
      }
    } catch (err: any) {
      addToast(err.message || 'Failed to load AI Studio workspace.', 'error');
    }
  };

  useEffect(() => {
    loadStudioData();
  }, []);

  // Inline File or Text Resource Upload inside Step 1
  const handleInlineResourceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadingResource(true);
    try {
      if (inlineTab === 'file') {
        if (!uploadFileObj) {
          addToast('Please select a file (.txt, .md, .pdf, .docx) to upload.', 'error');
          setUploadingResource(false);
          return;
        }
        const formData = new FormData();
        formData.append('file', uploadFileObj);
        if (uploadTitle.trim()) formData.append('title', uploadTitle.trim());
        const res = await apiRequest<{ source: any }>('/api/sources/upload', {
          method: 'POST',
          body: formData,
        });
        const newSrc = res.source;
        setSources((prev) => [newSrc, ...prev]);
        setSelectedSourceIds((prev) =>
          prev.includes(newSrc.id) ? prev : [...prev, newSrc.id]
        );
        setUploadFileObj(null);
        setUploadTitle('');
        setShowInlineUpload(false);
        addToast(`Uploaded and selected "${newSrc.title}"!`, 'success');
      } else {
        if (!pasteTitle.trim() || !pasteText.trim()) {
          addToast('Please provide both a title and study content.', 'error');
          setUploadingResource(false);
          return;
        }
        const res = await apiRequest<{ source: any }>('/api/sources/text', {
          method: 'POST',
          body: JSON.stringify({
            title: pasteTitle.trim(),
            raw_text: pasteText.trim(),
            source_type: 'notes',
          }),
        });
        const newSrc = res.source;
        setSources((prev) => [newSrc, ...prev]);
        setSelectedSourceIds((prev) =>
          prev.includes(newSrc.id) ? prev : [...prev, newSrc.id]
        );
        setPasteTitle('');
        setPasteText('');
        setShowInlineUpload(false);
        addToast(`Saved and selected "${newSrc.title}"!`, 'success');
      }
    } catch (err: any) {
      addToast(err.message || 'Could not add learning resource.', 'error');
    } finally {
      setUploadingResource(false);
    }
  };

  // Standard 5-Step Generation Handler -> Saves to DB & Automatically Navigates to /studio-library
  const handleGenerateTool = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const isVideo = selectedTool === 'video_overview';
      const config: Record<string, any> = {
        topic: topicFocus.trim() || undefined,
        audience_level: audienceLevel,
        language,
        duration: isVideo ? videoDuration : audioDuration,
        style: isVideo ? videoStyle : audioStyle,
        question_count: Number(quizCount) || 20,
        difficulty: audienceLevel,
        practice_mode: practiceMode,
        extraction_type: extractionType,
        instructions: extractionInstructions,
      };
      const res = await apiRequest<{ output: any }>('/api/studio/generate', {
        method: 'POST',
        body: JSON.stringify({
          tool_type: selectedTool,
          title: customTitle.trim() || undefined,
          source_ids: selectedSourceIds,
          config,
        }),
      });
      addToast(
        `Generated "${res.output.title}" (${language})! Opening in AI Studio Library...`,
        'success'
      );
      // Step 5: Automatically navigate to the dedicated AI Studio Library and open the generated output
      navigate(`/studio-library?open=${res.output.id}`);
    } catch (err: any) {
      addToast(err.message || 'Generation failed.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  const currentToolMeta =
    STUDIO_TOOLS.find((t) => t.id === selectedTool) || STUDIO_TOOLS[0];

  const selectedSourceObjects = sources.filter((s) => selectedSourceIds.includes(s.id));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Studio Header */}
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
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
            <span className="badge badge-indigo">BRAINOVA MULTI-LANGUAGE AI STUDIO</span>
            <span className="badge badge-blue">
              <Globe size={11} /> 6 Languages Supported
            </span>
          </div>
          <h1 style={{ fontSize: '1.68rem', marginBottom: '4px' }}>
            AI Studio — Nine Source-Grounded Learning Generators
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Select your study resources, choose any of the 6 supported languages (English, Telugu,
            Hindi, Kannada, Tamil, Marathi), generate your asset, and view it automatically in the{' '}
            <strong>AI Studio Library</strong>.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/studio-library')}
        >
          <Library size={16} color="var(--accent-blue)" />
          <span>Open AI Studio Library ({recentOutputs.length}+)</span>
        </button>
      </div>

      {/* Nine Tools Selector Grid */}
      <div className="grid-3">
        {STUDIO_TOOLS.map((tool) => {
          const Icon = tool.icon;
          const isSelected = selectedTool === tool.id;
          return (
            <div
              key={tool.id}
              onClick={() => {
                setSelectedTool(tool.id);
                setSearchParams({ tool: tool.id });
              }}
              className="card card-interactive"
              style={{
                cursor: 'pointer',
                padding: '16px',
                background: isSelected
                  ? 'linear-gradient(145deg, rgba(56, 189, 248, 0.16) 0%, rgba(16, 23, 45, 0.96) 100%)'
                  : 'var(--surface-1)',
                borderColor: isSelected ? 'var(--accent-blue)' : 'var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '10px',
                    background: isSelected
                      ? 'var(--gradient-brand)'
                      : 'rgba(99, 102, 241, 0.14)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                  }}
                >
                  <Icon size={18} />
                </div>
                <span className={`badge ${isSelected ? 'badge-blue' : 'badge-indigo'}`}>
                  {tool.badge}
                </span>
              </div>
              <h3 style={{ fontSize: '1rem', marginBottom: '4px' }}>{tool.name}</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{tool.tagline}</p>
            </div>
          );
        })}
      </div>

      {/* Main 5-Step Generation Workspace + Recent Library Sidebar */}
      <div className="grid-2" style={{ gridTemplateColumns: '1.55fr 1fr', alignItems: 'start' }}>
        {/* Left: 5-Step Generation Form */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div>
              <span className="badge badge-blue" style={{ marginBottom: '4px' }}>
                5-STEP GENERATION WORKFLOW
              </span>
              <h2 style={{ fontSize: '1.28rem' }}>Configure {currentToolMeta.name}</h2>
            </div>
            <span className="badge badge-indigo">{currentToolMeta.badge}</span>
          </div>

          <form onSubmit={handleGenerateTool}>
            {/* ============================================================
                STEP 1: SELECT LEARNING RESOURCES
               ============================================================ */}
            <div
              style={{
                padding: '16px',
                borderRadius: '12px',
                background: 'var(--bg-charcoal)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '18px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                <label className="form-label" style={{ margin: 0, fontSize: '0.9rem' }}>
                  Step 1 — Select Learning Resources ({selectedSourceIds.length} Selected)
                </label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowInlineUpload((v) => !v)}
                >
                  <Upload size={13} />
                  <span>{showInlineUpload ? 'Hide Upload Box' : '+ Upload / Paste New Resource'}</span>
                </button>
              </div>

              {/* Selected Resource Pills (with Remove action) */}
              {selectedSourceObjects.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                  {selectedSourceObjects.map((src) => (
                    <span
                      key={src.id}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '999px',
                        background: 'rgba(56, 189, 248, 0.15)',
                        border: '1px solid rgba(56, 189, 248, 0.4)',
                        fontSize: '0.78rem',
                        color: 'var(--text-primary)',
                      }}
                    >
                      <FileText size={12} color="var(--accent-blue)" />
                      <span>{src.title}</span>
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedSourceIds((prev) => prev.filter((id) => id !== src.id))
                        }
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#fca5a5',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          padding: 0,
                        }}
                        title={`Remove ${src.title} from selection`}
                      >
                        <X size={13} />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Direct Inline Upload / Paste Panel */}
              {showInlineUpload && (
                <div
                  style={{
                    padding: '14px',
                    borderRadius: '10px',
                    background: 'var(--surface-1)',
                    border: '1px solid var(--accent-blue)',
                    marginBottom: '12px',
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                    <button
                      type="button"
                      className={`btn btn-sm ${inlineTab === 'file' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setInlineTab('file')}
                    >
                      Upload Document (.txt, .md, .pdf, .docx)
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${inlineTab === 'text' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setInlineTab('text')}
                    >
                      Paste Study Text / Notes
                    </button>
                  </div>

                  {inlineTab === 'file' ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Optional custom title for document"
                        value={uploadTitle}
                        onChange={(e) => setUploadTitle(e.target.value)}
                      />
                      <input
                        type="file"
                        accept=".txt,.md,.pdf,.docx"
                        className="form-input"
                        onChange={(e) => setUploadFileObj(e.target.files?.[0] || null)}
                      />
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={handleInlineResourceSubmit}
                        disabled={uploadingResource}
                      >
                        <Plus size={14} />
                        <span>{uploadingResource ? 'Uploading...' : 'Upload & Select Resource'}</span>
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Resource Title (e.g., Operating Systems Virtual Memory Notes)"
                        value={pasteTitle}
                        onChange={(e) => setPasteTitle(e.target.value)}
                      />
                      <textarea
                        className="form-textarea"
                        style={{ minHeight: 80 }}
                        placeholder="Paste your lecture notes, article text, or syllabus content here..."
                        value={pasteText}
                        onChange={(e) => setPasteText(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={handleInlineResourceSubmit}
                        disabled={uploadingResource}
                      >
                        <Plus size={14} />
                        <span>{uploadingResource ? 'Saving...' : 'Save & Select Resource'}</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Existing Sources Checkbox List */}
              {sources.length === 0 ? (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  No saved sources yet. Click <strong>+ Upload / Paste New Resource</strong> above
                  or enter a Topic Focus below.
                </div>
              ) : (
                <div
                  style={{
                    maxHeight: 145,
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    paddingTop: '4px',
                  }}
                >
                  {sources.map((src) => (
                    <label
                      key={src.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.84rem',
                        cursor: 'pointer',
                        padding: '4px 6px',
                        borderRadius: '6px',
                        background: selectedSourceIds.includes(src.id)
                          ? 'rgba(99, 102, 241, 0.14)'
                          : 'transparent',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.includes(src.id)}
                        onChange={() =>
                          setSelectedSourceIds((prev) =>
                            prev.includes(src.id)
                              ? prev.filter((id) => id !== src.id)
                              : [...prev, src.id]
                          )
                        }
                      />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {src.title}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {src.word_count} words
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* ============================================================
                STEP 2: CONFIGURE GENERATION & 6-LANGUAGE OPTIONS
               ============================================================ */}
            <div style={{ marginBottom: '12px' }}>
              <label className="form-label" style={{ fontSize: '0.9rem', color: 'var(--accent-blue)' }}>
                Step 2 — Configure Output & Language Settings
              </label>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Output Title (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder={`e.g., ${currentToolMeta.name.slice(3)} — Distributed Consensus`}
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Topic Focus / Subject Context</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., Database Indexing, B-Trees & ACID Transactions"
                  value={topicFocus}
                  onChange={(e) => setTopicFocus(e.target.value)}
                />
              </div>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">
                  Output Language (All 6 Indian & Global Languages)
                </label>
                <select
                  className="form-select"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  aria-label="Output Language"
                >
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <option key={lang.value} value={lang.value}>
                      {lang.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Audience / Difficulty Level</label>
                <select
                  className="form-select"
                  value={audienceLevel}
                  onChange={(e) => setAudienceLevel(e.target.value)}
                >
                  <option value="Beginner">Beginner</option>
                  <option value="Intermediate">Intermediate</option>
                  <option value="Advanced">Advanced</option>
                </select>
              </div>
            </div>

            {/* Tool 2: Video Overview Specific Controls (Part 6) */}
            {selectedTool === 'video_overview' && (
              <div
                style={{
                  padding: '14px',
                  borderRadius: '12px',
                  background: 'rgba(168, 85, 247, 0.1)',
                  border: '1px solid rgba(168, 85, 247, 0.35)',
                  marginBottom: '16px',
                }}
              >
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#d8b4fe', marginBottom: '10px' }}>
                  1080p HD Educational Video Synthesis Settings
                </div>
                <div className="grid-2">
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Desired Video Duration</label>
                    <select
                      className="form-select"
                      value={videoDuration}
                      onChange={(e) => setVideoDuration(e.target.value)}
                      aria-label="Desired Video Duration"
                    >
                      <option value="1–3 minutes">1–3 minutes</option>
                      <option value="3–5 minutes">3–5 minutes</option>
                      <option value="5–10 minutes">5–10 minutes</option>
                      <option value="10–15 minutes">10–15 minutes</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Visual Explanation Style</label>
                    <select
                      className="form-select"
                      value={videoStyle}
                      onChange={(e) => setVideoStyle(e.target.value)}
                      aria-label="Visual Explanation Style"
                    >
                      <option value="Concept Breakdown & Architecture">
                        Concept Breakdown & Architecture
                      </option>
                      <option value="Step-by-Step Visual Walkthrough">
                        Step-by-Step Visual Walkthrough
                      </option>
                      <option value="Exam Revision Crash Course">
                        Exam Revision Crash Course
                      </option>
                      <option value="Deep Technical Dive">Deep Technical Dive</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Tool 1: Audio Overview Specific Controls */}
            {selectedTool === 'audio_overview' && (
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Podcast Duration Target</label>
                  <select
                    className="form-select"
                    value={audioDuration}
                    onChange={(e) => setAudioDuration(e.target.value)}
                  >
                    <option value="Concise (1-2 min)">Concise (1-2 min)</option>
                    <option value="Standard (3-5 min)">Standard (3-5 min)</option>
                    <option value="Deep Dive (6-10 min)">Deep Dive (6-10 min)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Explanation Style</label>
                  <select
                    className="form-select"
                    value={audioStyle}
                    onChange={(e) => setAudioStyle(e.target.value)}
                  >
                    <option value="Deep-Dive Conversational Podcast">
                      Conversational Podcast
                    </option>
                    <option value="Exam Revision Briefing">Exam Revision Briefing</option>
                    <option value="Socratic Q&A Breakdown">Socratic Q&A Breakdown</option>
                  </select>
                </div>
              </div>
            )}

            {/* Tool 7: Quiz Specific Controls */}
            {selectedTool === 'quiz' && (
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Question Count</label>
                  <select
                    className="form-select"
                    value={quizCount}
                    onChange={(e) => setQuizCount(Number(e.target.value))}
                  >
                    <option value={20}>Standard 20-Question MCQ Exam</option>
                    <option value={15}>15-Question Assessment</option>
                    <option value={10}>Quick 10-Question Check</option>
                  </select>
                </div>
                <div className="form-group" style={{ justifyContent: 'center' }}>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.84rem',
                      cursor: 'pointer',
                      marginTop: '22px',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={practiceMode}
                      onChange={(e) => setPracticeMode(e.target.checked)}
                    />
                    <span>Practice Mode (Allow Instant Explanations)</span>
                  </label>
                </div>
              </div>
            )}

            {/* Tool 9: Data Table Specific Controls */}
            {selectedTool === 'data_table' && (
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Table Extraction Schema</label>
                  <select
                    className="form-select"
                    value={extractionType}
                    onChange={(e) => setExtractionType(e.target.value)}
                  >
                    <option value="Concept Comparisons & Definitions">
                      Concept Comparisons & Definitions
                    </option>
                    <option value="Formulas & Their Applications">
                      Formulas & Their Applications
                    </option>
                    <option value="Programming Concepts & Complexity">
                      Programming Concepts & Complexity
                    </option>
                    <option value="Important Dates, Events & Milestones">
                      Important Dates, Events & Milestones
                    </option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Custom Extraction Instructions</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g., Focus on Big-O complexity and edge cases"
                    value={extractionInstructions}
                    onChange={(e) => setExtractionInstructions(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* ============================================================
                STEPS 3, 4 & 5: GENERATE -> AUTO-SAVE -> AUTO-NAVIGATE TO LIBRARY
               ============================================================ */}
            <button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{ width: '100%', marginTop: '6px' }}
              disabled={generating}
            >
              <Sparkles size={18} />
              <span>
                {generating
                  ? `Synthesizing ${currentToolMeta.name.slice(3)} in ${language} & Saving to Library...`
                  : `Step 3 — Generate ${currentToolMeta.name.slice(3)} (${language}) & Open in Library`}
              </span>
            </button>
          </form>
        </div>

        {/* Right: Workflow Overview & Recent AI Studio Library Items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card">
            <h3 style={{ fontSize: '1.05rem', marginBottom: '12px' }}>
              Standard 5-Step AI Studio Pipeline
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--accent-blue)" />
                <span>
                  <strong>1. Select Resources:</strong> Upload a file or select existing sources.
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--accent-blue)" />
                <span>
                  <strong>2. Configure Options:</strong> Choose any of the 6 languages & duration.
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--accent-blue)" />
                <span>
                  <strong>3. Generate Asset:</strong> Real AI + multi-language audio/video synthesis.
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--accent-blue)" />
                <span>
                  <strong>4. Save Automatically:</strong> Persisted in your database library.
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--accent-blue)" />
                <span>
                  <strong>5. Open in AI Studio Library:</strong> Instant redirect to view & play!
                </span>
              </div>
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '1.05rem' }}>Recent Saved Outputs</h3>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => navigate('/studio-library')}
              >
                <span>View All</span>
                <ArrowRight size={14} />
              </button>
            </div>

            {recentOutputs.length === 0 ? (
              <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                Generated outputs will appear in your AI Studio Library automatically.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {recentOutputs.map((out) => (
                  <div
                    key={out.id}
                    onClick={() => navigate(`/studio-library?open=${out.id}`)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '10px',
                      background: 'var(--bg-charcoal)',
                      border: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.86rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {out.title}
                      </div>
                      <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)' }}>
                        {out.tool_type.replace(/_/g, ' ').toUpperCase()} •{' '}
                        {out.language || out.config?.language || 'English'}
                      </div>
                    </div>
                    <ArrowRight size={15} color="var(--accent-blue)" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
