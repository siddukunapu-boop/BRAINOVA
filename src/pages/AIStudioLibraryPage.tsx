import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Library,
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
  Play,
  Pause,
  Volume2,
  VolumeX,
  Subtitles,
  Download,
  Trash2,
  Edit3,
  RefreshCw,
  Plus,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  CheckCircle2,
  AlertTriangle,
  ArrowUp,
  ArrowDown,
  Save,
  Search,
  Globe,
  Clock,
  FileText,
  X,
  Eye,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const STUDIO_TOOL_META: Record<
  string,
  { name: string; badge: string; icon: any; accent: string }
> = {
  audio_overview: {
    name: 'Audio Overview',
    badge: 'Playable Podcast',
    icon: Headphones,
    accent: '#38bdf8',
  },
  video_overview: {
    name: 'Video Overview',
    badge: '1080p HD Video',
    icon: Film,
    accent: '#a855f7',
  },
  slide_deck: {
    name: 'Slide Deck',
    badge: 'Presentation',
    icon: Presentation,
    accent: '#6366f1',
  },
  mind_map: {
    name: 'Mind Map',
    badge: 'Knowledge Graph',
    icon: GitBranch,
    accent: '#10b981',
  },
  study_guide: {
    name: 'Study Guide / Report',
    badge: 'Deep Report',
    icon: BookOpen,
    accent: '#3b82f6',
  },
  flashcards: {
    name: 'Flashcards',
    badge: 'Active Recall',
    icon: Layers,
    accent: '#f59e0b',
  },
  quiz: {
    name: 'Quiz',
    badge: '20-MCQ Exam',
    icon: CheckSquare,
    accent: '#ec4899',
  },
  infographic: {
    name: 'Infographic',
    badge: 'Visual Poster',
    icon: LayoutGrid,
    accent: '#14b8a6',
  },
  data_table: {
    name: 'Data Table',
    badge: 'CSV & Sortable',
    icon: Table,
    accent: '#8b5cf6',
  },
};

export const LANGUAGE_LABELS: Record<string, string> = {
  English: 'English',
  Telugu: 'Telugu • తెలుగు',
  Hindi: 'Hindi • हिन्दी',
  Kannada: 'Kannada • ಕನ್ನಡ',
  Tamil: 'Tamil • தமிழ்',
  Marathi: 'Marathi • मराठी',
};

const formatTime = (sec: number) => {
  const s = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem < 10 ? '0' : ''}${rem}`;
};

export const AIStudioLibraryPage: React.FC = () => {
  const { addToast } = useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [outputs, setOutputs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeOutput, setActiveOutput] = useState<any | null>(null);

  // Filters & Sorting
  const [searchQuery, setSearchQuery] = useState('');
  const [toolFilter, setToolFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'title'>('newest');

  // Delete Confirmation Modal
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Rename & Regeneration States
  const [isRenaming, setIsRenaming] = useState(false);
  const [renamingTitle, setRenamingTitle] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);

  // Tool 1: Audio Player States
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1);

  // Tool 2: Genuine 1080p Video Overview Player States
  const videoAudioRef = useRef<HTMLAudioElement | null>(null);
  const videoStageRef = useRef<HTMLDivElement | null>(null);
  const videoCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const loadedFrameImagesRef = useRef<Record<number, HTMLImageElement>>({});
  const [videoPlaying, setVideoPlaying] = useState(false);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [videoMuted, setVideoMuted] = useState(false);
  const [videoVolume, setVideoVolume] = useState(1);
  const [videoSpeed, setVideoSpeed] = useState(1);
  const [showCaptions, setShowCaptions] = useState(true);
  const [activeSceneIdx, setActiveSceneIdx] = useState(0);

  // Tool 3: Slide Deck States
  const [currentSlideIdx, setCurrentSlideIdx] = useState(0);
  const [slideFullscreen, setSlideFullscreen] = useState(false);
  const [editingSlide, setEditingSlide] = useState(false);

  // Tool 4: Mind Map States
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});
  const [selectedMindNode, setSelectedMindNode] = useState<any | null>(null);
  const [mapZoom, setMapZoom] = useState(1);

  // Tool 5: Study Guide States
  const [editingGuide, setEditingGuide] = useState(false);
  const [guideOverviewEdit, setGuideOverviewEdit] = useState('');
  const [guideSummaryEdit, setGuideSummaryEdit] = useState('');

  // Tool 6: Flashcards States
  const [currentCardIdx, setCurrentCardIdx] = useState(0);
  const [cardFlipped, setCardFlipped] = useState(false);
  const [showAddCardModal, setShowAddCardModal] = useState(false);
  const [newCardFront, setNewCardFront] = useState('');
  const [newCardBack, setNewCardBack] = useState('');
  const [newCardHint, setNewCardHint] = useState('');

  // Tool 7: Studio Quiz States
  const [studioQuizAnswers, setStudioQuizAnswers] = useState<Record<string, number>>({});
  const [studioQuizResult, setStudioQuizResult] = useState<any | null>(null);
  const [submittingStudioQuiz, setSubmittingStudioQuiz] = useState(false);

  // Tool 9: Data Table States
  const [tableSearch, setTableSearch] = useState('');
  const [sortColIdx, setSortColIdx] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const loadOutputs = async () => {
    setLoading(true);
    try {
      const res = await apiRequest<{ outputs: any[] }>('/api/studio/outputs');
      const list = res.outputs || [];
      setOutputs(list);

      const openId = searchParams.get('open') || searchParams.get('output');
      if (openId) {
        const found = list.find((o) => o.id === openId);
        if (found) {
          selectOutputItem(found, false);
        }
      }
    } catch (err: any) {
      addToast(err.message || 'Failed to load AI Studio Library.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOutputs();
  }, []);

  const selectOutputItem = (out: any, updateUrl = true) => {
    // Stop any running audio/video narration
    if (videoAudioRef.current) {
      videoAudioRef.current.pause();
      videoAudioRef.current.currentTime = 0;
    }
    setVideoPlaying(false);
    setVideoCurrentTime(0);
    setActiveSceneIdx(0);
    setActiveOutput(out);
    setRenamingTitle(out.title);
    setIsRenaming(false);
    setCurrentSlideIdx(0);
    setCurrentCardIdx(0);
    setCardFlipped(false);
    setStudioQuizAnswers({});
    setStudioQuizResult(null);

    if (out.tool_type === 'mind_map' && out.content?.root) {
      setSelectedMindNode(out.content.root);
    }
    if (out.tool_type === 'study_guide' && out.content) {
      setGuideOverviewEdit(out.content.overview || '');
      setGuideSummaryEdit(out.content.summary || '');
    }
    if (out.tool_type === 'video_overview') {
      const totalDur =
        out.content?.video?.duration_seconds ||
        out.content?.total_duration_seconds ||
        (out.content?.scenes || []).reduce(
          (acc: number, s: any) => acc + (Number(s.duration_seconds) || 12),
          0
        ) ||
        48;
      setVideoDuration(totalDur);
    }
    if (updateUrl) {
      setSearchParams({ open: out.id });
    }
  };

  // Preload 1080p slide frames and draw active scene onto the 1920x1080 HTML5 Canvas
  useEffect(() => {
    if (!activeOutput || activeOutput.tool_type !== 'video_overview') return;
    const frames: any[] = activeOutput.content?.video?.slide_frames || [];
    loadedFrameImagesRef.current = {};
    frames.forEach((f, idx) => {
      if (f.image_data_url) {
        const img = new Image();
        img.onload = () => {
          loadedFrameImagesRef.current[idx] = img;
          if (idx === activeSceneIdx) {
            drawVideoFrame(idx);
          }
        };
        img.src = f.image_data_url;
      }
    });
    drawVideoFrame(0);
  }, [activeOutput]);

  useEffect(() => {
    if (activeOutput?.tool_type === 'video_overview') {
      drawVideoFrame(activeSceneIdx);
    }
  }, [activeSceneIdx, videoCurrentTime, activeOutput]);

  const drawVideoFrame = (sceneIndex: number) => {
    const canvas = videoCanvasRef.current;
    if (!canvas || !activeOutput) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const scenes = activeOutput.content?.scenes || [];
    const scene = scenes[sceneIndex] || scenes[0];
    const preloadedImg = loadedFrameImagesRef.current[sceneIndex];

    if (preloadedImg && preloadedImg.complete) {
      ctx.drawImage(preloadedImg, 0, 0, 1920, 1080);
    } else {
      // Fallback high-definition 1920x1080 procedural slide rendering
      const grad = ctx.createLinearGradient(0, 0, 1920, 1080);
      grad.addColorStop(0, '#070b18');
      grad.addColorStop(1, '#151f3f');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 1920, 1080);

      // Header bar
      ctx.fillStyle = 'rgba(56, 189, 248, 0.16)';
      ctx.fillRect(80, 64, 420, 48);
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 22px Inter, Segoe UI, sans-serif';
      ctx.fillText(
        `BRAINOVA 1080p HD • SCENE ${sceneIndex + 1} OF ${Math.max(1, scenes.length)}`,
        100,
        96
      );

      // Title
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 52px Inter, Nirmala UI, Segoe UI, sans-serif';
      ctx.fillText(String(scene?.title || activeOutput.title).slice(0, 56), 80, 195);

      // Visual diagram box
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.55)';
      ctx.lineWidth = 3;
      ctx.strokeRect(80, 250, 1760, 290);
      ctx.fillStyle = 'rgba(17, 25, 54, 0.85)';
      ctx.fillRect(80, 250, 1760, 290);

      // Draw 3 connected architecture nodes inside the visual box
      const nodes = [
        { x: 150, label: '1. Core Concept & Input' },
        { x: 730, label: '2. Architecture & Mechanism' },
        { x: 1310, label: '3. Production Verification' },
      ];
      nodes.forEach((n, i) => {
        ctx.fillStyle = i === sceneIndex % 3 ? '#312e81' : '#1e293b';
        ctx.fillRect(n.x, 325, 440, 140);
        ctx.strokeStyle = i === sceneIndex % 3 ? '#38bdf8' : '#6366f1';
        ctx.lineWidth = 3;
        ctx.strokeRect(n.x, 325, 440, 140);
        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 24px Inter, Nirmala UI, Segoe UI, sans-serif';
        ctx.fillText(n.label, n.x + 28, 385);
        ctx.fillStyle = '#cbd5e1';
        ctx.font = '20px Inter, Nirmala UI, Segoe UI, sans-serif';
        ctx.fillText(String(scene?.title || '').slice(0, 32), n.x + 28, 428);
      });

      // Narration card
      ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
      ctx.fillRect(80, 580, 1760, 320);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
      ctx.strokeRect(80, 580, 1760, 320);

      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 24px Inter, Nirmala UI, Segoe UI, sans-serif';
      ctx.fillText(
        `VISUAL STORYBOARD & EXPLANATION (${activeOutput.language || 'English'})`,
        115,
        635
      );

      ctx.fillStyle = '#e2e8f0';
      ctx.font = '28px Inter, Nirmala UI, Segoe UI, sans-serif';
      const words = String(scene?.narration || '').split(' ');
      let line = '';
      let y = 695;
      for (let i = 0; i < words.length; i++) {
        const test = line + words[i] + ' ';
        if (test.length > 88 && i > 0) {
          ctx.fillText(line, 115, y);
          line = words[i] + ' ';
          y += 44;
          if (y > 860) break;
        } else {
          line = test;
        }
      }
      if (line && y <= 860) ctx.fillText(line, 115, y);
    }

    // Bottom progress bar overlay on canvas
    const total = Math.max(1, videoDuration || 48);
    const pct = Math.min(1, Math.max(0, videoCurrentTime / total));
    ctx.fillStyle = 'rgba(56, 189, 248, 0.25)';
    ctx.fillRect(0, 1068, 1920, 12);
    ctx.fillStyle = '#38bdf8';
    ctx.fillRect(0, 1068, Math.round(1920 * pct), 12);
  };

  // Sync activeSceneIdx with videoCurrentTime
  const handleVideoTimeUpdate = () => {
    const audioEl = videoAudioRef.current;
    if (!audioEl || !activeOutput) return;
    const t = audioEl.currentTime;
    const dur = audioEl.duration || videoDuration || 48;
    setVideoCurrentTime(t);
    if (audioEl.duration && !isNaN(audioEl.duration)) {
      setVideoDuration(audioEl.duration);
    }

    const scenes: any[] = activeOutput.content?.scenes || [];
    if (scenes.length > 0) {
      const idx = Math.min(
        scenes.length - 1,
        Math.floor((t / Math.max(1, dur)) * scenes.length)
      );
      if (idx !== activeSceneIdx) {
        setActiveSceneIdx(idx);
      }
    }
  };

  const toggleVideoPlay = () => {
    const audioEl = videoAudioRef.current;
    if (!audioEl) return;
    if (videoPlaying) {
      audioEl.pause();
      setVideoPlaying(false);
    } else {
      audioEl.play().catch(() => {
        addToast('Click play again to start audio-visual playback.', 'info');
      });
      setVideoPlaying(true);
    }
  };

  const handleVideoSeek = (newTime: number) => {
    const audioEl = videoAudioRef.current;
    setVideoCurrentTime(newTime);
    if (audioEl) {
      audioEl.currentTime = newTime;
    }
    const scenes: any[] = activeOutput?.content?.scenes || [];
    if (scenes.length > 0 && videoDuration > 0) {
      const idx = Math.min(
        scenes.length - 1,
        Math.floor((newTime / videoDuration) * scenes.length)
      );
      setActiveSceneIdx(idx);
    }
  };

  const handleJumpToScene = (sceneIdx: number) => {
    setActiveSceneIdx(sceneIdx);
    const scenes: any[] = activeOutput?.content?.scenes || [];
    if (scenes.length > 0 && videoDuration > 0) {
      const targetTime = (sceneIdx / scenes.length) * videoDuration;
      handleVideoSeek(targetTime);
    }
  };

  const handleToggleFullscreen = () => {
    if (!videoStageRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      videoStageRef.current.requestFullscreen().catch(() => {});
    }
  };

  // --- CRUD & Helper Handlers ---
  const handleConfirmDelete = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await apiRequest(`/api/studio/outputs/${deleteTarget.id}`, { method: 'DELETE' });
      setOutputs((prev) => prev.filter((o) => o.id !== deleteTarget.id));
      if (activeOutput?.id === deleteTarget.id) {
        setActiveOutput(null);
        setSearchParams({});
      }
      setDeleteTarget(null);
      addToast('Deleted output from your AI Studio Library.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const handleSaveRename = async () => {
    if (!activeOutput || !renamingTitle.trim()) return;
    try {
      const res = await apiRequest<{ output: any }>(
        `/api/studio/outputs/${activeOutput.id}`,
        {
          method: 'PUT',
          body: JSON.stringify({ title: renamingTitle.trim() }),
        }
      );
      setActiveOutput(res.output);
      setOutputs((prev) => prev.map((o) => (o.id === res.output.id ? res.output : o)));
      setIsRenaming(false);
      addToast('Renamed output in AI Studio Library.', 'success');
    } catch (err: any) {
      addToast(err.message || 'Rename failed.', 'error');
    }
  };

  const handleSaveContentUpdate = async (newContent: any) => {
    if (!activeOutput) return;
    try {
      const res = await apiRequest<{ output: any }>(
        `/api/studio/outputs/${activeOutput.id}`,
        {
          method: 'PUT',
          body: JSON.stringify({ content: newContent }),
        }
      );
      setActiveOutput(res.output);
      setOutputs((prev) => prev.map((o) => (o.id === res.output.id ? res.output : o)));
      addToast('Saved your changes to AI Studio Library!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Save failed.', 'error');
    }
  };

  const handleRegenerateOutput = async (confirmOverwrite = false) => {
    if (!activeOutput) return;
    setRegenerating(true);
    try {
      const res = await apiRequest<{ output: any }>(
        `/api/studio/outputs/${activeOutput.id}/regenerate`,
        {
          method: 'POST',
          body: JSON.stringify({ confirm_overwrite: confirmOverwrite }),
        }
      );
      setActiveOutput(res.output);
      setOutputs((prev) => prev.map((o) => (o.id === res.output.id ? res.output : o)));
      setShowRegenConfirm(false);
      addToast('Regenerated AI Studio output!', 'success');
    } catch (err: any) {
      if (err.status === 409) {
        setShowRegenConfirm(true);
      } else {
        addToast(err.message || 'Regeneration failed.', 'error');
      }
    } finally {
      setRegenerating(false);
    }
  };

  // Flashcard helpers
  const handleRateFlashcard = async (card: any, newStatus: 'known' | 'learning' | 'review') => {
    try {
      const res = await apiRequest<{ flashcard: any }>(`/api/flashcards/${card.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      });
      const updatedCards = (activeOutput.content.cards || []).map((c: any) =>
        c.id === card.id ? res.flashcard : c
      );
      setActiveOutput({
        ...activeOutput,
        content: { ...activeOutput.content, cards: updatedCards },
      });
      addToast(`Marked card as "${newStatus.toUpperCase()}".`, 'success');
    } catch (err: any) {
      addToast(err.message || 'Could not update card status.', 'error');
    }
  };

  const handleAddFlashcard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOutput || !newCardFront.trim() || !newCardBack.trim()) return;
    try {
      const res = await apiRequest<{ flashcard: any }>('/api/flashcards', {
        method: 'POST',
        body: JSON.stringify({
          studio_output_id: activeOutput.id,
          front: newCardFront.trim(),
          back: newCardBack.trim(),
          hint: newCardHint.trim(),
        }),
      });
      const updatedCards = [...(activeOutput.content.cards || []), res.flashcard];
      setActiveOutput({
        ...activeOutput,
        content: { ...activeOutput.content, cards: updatedCards },
      });
      setNewCardFront('');
      setNewCardBack('');
      setNewCardHint('');
      setShowAddCardModal(false);
      addToast('Added custom flashcard to deck!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to add card.', 'error');
    }
  };

  const handleDeleteFlashcard = async (cardId: string) => {
    try {
      await apiRequest(`/api/flashcards/${cardId}`, { method: 'DELETE' });
      const updatedCards = (activeOutput.content.cards || []).filter(
        (c: any) => c.id !== cardId
      );
      setActiveOutput({
        ...activeOutput,
        content: { ...activeOutput.content, cards: updatedCards },
      });
      setCurrentCardIdx(0);
      addToast('Removed flashcard.', 'info');
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
  };

  // Studio Quiz Submit
  const handleSubmitStudioQuiz = async () => {
    if (!activeOutput || submittingStudioQuiz) return;
    setSubmittingStudioQuiz(true);
    try {
      const res = await apiRequest<{ attempt: any }>(
        `/api/studio/outputs/${activeOutput.id}/quiz-submit`,
        {
          method: 'POST',
          body: JSON.stringify({
            answers: studioQuizAnswers,
            duration_seconds: 120,
          }),
        }
      );
      setStudioQuizResult(res.attempt);
      addToast(
        `Quiz Graded! Score: ${res.attempt.score}/${res.attempt.max_score} (${res.attempt.percentage}%)`,
        res.attempt.passed ? 'success' : 'info'
      );
    } catch (err: any) {
      addToast(err.message || 'Quiz grading failed.', 'error');
    } finally {
      setSubmittingStudioQuiz(false);
    }
  };

  // Export Helpers
  const downloadFile = (filename: string, content: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    if (!activeOutput || activeOutput.tool_type !== 'data_table') return;
    const cols: string[] = activeOutput.content.columns || [];
    const rows: any[] = activeOutput.content.rows || [];
    const escapeCsv = (val: string) => `"${String(val || '').replace(/"/g, '""')}"`;
    const csvLines = [
      cols.map(escapeCsv).join(','),
      ...rows.map((r) => (r.cells || []).map(escapeCsv).join(',')),
    ];
    downloadFile(`${activeOutput.title.replace(/\s+/g, '_')}.csv`, csvLines.join('\n'), 'text/csv');
    addToast('Exported Data Table to CSV!', 'success');
  };

  const handleExportSlidesHtml = () => {
    if (!activeOutput || activeOutput.tool_type !== 'slide_deck') return;
    const slides = activeOutput.content.slides || [];
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>${activeOutput.title}</title>
    <style>body{font-family:sans-serif;background:#070a14;color:#f8fafc;padding:40px}.slide{border:1px solid #334155;border-radius:16px;padding:36px;margin-bottom:32px;background:#10172d;page-break-after:always}h1,h2{color:#38bdf8}</style></head><body>
    <h1>${activeOutput.title}</h1>
    ${slides
      .map(
        (s: any) => `<div class="slide"><h2>Slide ${s.slide_number}: ${s.title}</h2><h4>${
          s.subtitle || ''
        }</h4><ul>${(s.bullets || []).map((b: string) => `<li>${b}</li>`).join('')}</ul><p><em>${
          s.example || ''
        }</em></p></div>`
      )
      .join('')}
    </body></html>`;
    downloadFile(`${activeOutput.title.replace(/\s+/g, '_')}_slides.html`, html, 'text/html');
    addToast('Exported printable Slide Deck!', 'success');
  };

  // Filtered & sorted outputs
  const filteredOutputs = outputs
    .filter((o) => {
      if (toolFilter !== 'all' && o.tool_type !== toolFilter) return false;
      const outLang = o.language || o.config?.language || 'English';
      if (languageFilter !== 'all' && outLang.toLowerCase() !== languageFilter.toLowerCase()) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchTitle = String(o.title || '').toLowerCase().includes(q);
        const matchType = String(o.tool_type || '').toLowerCase().includes(q);
        const matchSource = (o.source_titles || []).some((s: string) =>
          String(s).toLowerCase().includes(q)
        );
        return matchTitle || matchType || matchSource;
      }
      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'oldest') {
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
      }
      if (sortBy === 'title') {
        return String(a.title || '').localeCompare(String(b.title || ''));
      }
      return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Library Hero Header */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span className="badge badge-indigo">
              <Library size={12} /> CENTRAL SAVED OUTPUTS REPOSITORY
            </span>
            <span className="badge badge-blue">{outputs.length} Total Saved Outputs</span>
          </div>
          <h1 style={{ fontSize: '1.7rem', marginBottom: '4px' }}>AI Studio Library</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Access, watch, listen to, study, filter, and manage every AI-generated learning asset
            across all 9 tools and 6 languages.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/studio')}
        >
          <Sparkles size={16} />
          <span>Generate New Output in AI Studio</span>
        </button>
      </div>

      {/* Active Interactive Output Viewer (Opens automatically after generation or when clicking Open/View) */}
      {activeOutput && (
        <div
          className="card"
          style={{
            border: '2px solid var(--accent-blue)',
            boxShadow: 'var(--shadow-glow)',
          }}
        >
          {/* Output Viewer Top Bar */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '12px',
              paddingBottom: '16px',
              marginBottom: '20px',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '6px' }}>
                <span className="badge badge-indigo">
                  {STUDIO_TOOL_META[activeOutput.tool_type]?.name ||
                    activeOutput.tool_type.replace(/_/g, ' ').toUpperCase()}
                </span>
                <span className="badge badge-blue">
                  <Globe size={11} />{' '}
                  {LANGUAGE_LABELS[activeOutput.language || activeOutput.config?.language || 'English'] ||
                    activeOutput.language ||
                    'English'}
                </span>
                {activeOutput.duration_label && (
                  <span className="badge badge-success">
                    <Clock size={11} /> {activeOutput.duration_label}
                  </span>
                )}
                {activeOutput.is_user_edited && (
                  <span className="badge badge-warning">Edited by User</span>
                )}
              </div>

              {isRenaming ? (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '6px' }}>
                  <input
                    type="text"
                    className="form-input"
                    value={renamingTitle}
                    onChange={(e) => setRenamingTitle(e.target.value)}
                  />
                  <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveRename}>
                    Save
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setIsRenaming(false)}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <h2 style={{ fontSize: '1.45rem' }}>{activeOutput.title}</h2>
              )}
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setRenamingTitle(activeOutput.title);
                  setIsRenaming(true);
                }}
              >
                <Edit3 size={14} />
                <span>Rename</span>
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleRegenerateOutput(false)}
                disabled={regenerating}
              >
                <RefreshCw size={14} />
                <span>{regenerating ? 'Regenerating...' : 'Regenerate'}</span>
              </button>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => setDeleteTarget(activeOutput)}
              >
                <Trash2 size={14} />
                <span>Delete</span>
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  if (videoAudioRef.current) videoAudioRef.current.pause();
                  setVideoPlaying(false);
                  setActiveOutput(null);
                  setSearchParams({});
                }}
                title="Close Viewer"
              >
                <X size={16} />
                <span>Close Viewer</span>
              </button>
            </div>
          </div>

          {/* ============================================================
              1. AUDIO OVERVIEW VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'audio_overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div
                style={{
                  padding: '20px',
                  borderRadius: '14px',
                  background:
                    'linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(56, 189, 248, 0.12) 100%)',
                  border: '1px solid var(--border-strong)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                  <div>
                    <span className="badge badge-blue" style={{ marginBottom: 4 }}>
                      Synthesized Spoken Audio ({activeOutput.content.audio?.provider || 'WAV'}) •{' '}
                      {activeOutput.language || 'English'}
                    </span>
                    <h3 style={{ fontSize: '1.15rem' }}>
                      Podcast Episode Player — Duration:{' '}
                      {activeOutput.content.audio?.duration_seconds || 18}s
                    </h3>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <select
                      className="form-select"
                      style={{ width: 'auto', padding: '5px 10px' }}
                      value={playbackRate}
                      onChange={(e) => {
                        const rate = Number(e.target.value);
                        setPlaybackRate(rate);
                        if (audioRef.current) audioRef.current.playbackRate = rate;
                      }}
                      aria-label="Audio playback speed"
                    >
                      <option value={0.75}>0.75x Speed</option>
                      <option value={1}>1.0x Speed</option>
                      <option value={1.25}>1.25x Speed</option>
                      <option value={1.5}>1.5x Speed</option>
                    </select>

                    {activeOutput.content.audio?.audio_url && (
                      <a
                        href={activeOutput.content.audio.audio_url}
                        download={`${activeOutput.title.replace(/\s+/g, '_')}.wav`}
                        className="btn btn-secondary btn-sm"
                      >
                        <Download size={14} />
                        <span>Download WAV</span>
                      </a>
                    )}
                  </div>
                </div>

                {activeOutput.content.audio?.audio_url && (
                  <audio
                    ref={audioRef}
                    controls
                    src={activeOutput.content.audio.audio_url}
                    style={{ width: '100%', marginTop: '6px' }}
                  />
                )}
              </div>

              <div>
                <h3 style={{ fontSize: '1.05rem', marginBottom: '12px' }}>
                  Source-Grounded Podcast Script & Dialogue Transcript ({activeOutput.language || 'English'})
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {(activeOutput.content.dialogue || []).map((turn: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        padding: '12px 16px',
                        borderRadius: '10px',
                        background: 'var(--bg-charcoal)',
                        borderLeft:
                          turn.speaker === 'Alex'
                            ? '3px solid var(--accent-blue)'
                            : '3px solid var(--accent-violet)',
                      }}
                    >
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: turn.speaker === 'Alex' ? 'var(--accent-blue)' : '#c4b5fd', marginBottom: '4px' }}>
                        {turn.speaker} ({turn.role || 'Host'})
                      </div>
                      <div style={{ fontSize: '0.92rem', color: 'var(--text-secondary)' }}>
                        {turn.text}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              2. VIDEO OVERVIEW VIEWER — GENUINE PLAYABLE 1080p HD VIDEO PLAYER
             ============================================================ */}
          {activeOutput.tool_type === 'video_overview' && (() => {
            const scenes: any[] = activeOutput.content?.scenes || [];
            const currentScene = scenes[activeSceneIdx] || scenes[0];
            const videoMeta = activeOutput.content?.video || {};
            const audioUrl = videoMeta.audio_url || '';
            const mp4Url = videoMeta.video_url || '';

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {/* Hidden Synchronized Spoken Audio Engine */}
                {audioUrl && (
                  <audio
                    ref={videoAudioRef}
                    src={audioUrl}
                    onTimeUpdate={handleVideoTimeUpdate}
                    onLoadedMetadata={() => {
                      if (videoAudioRef.current?.duration) {
                        setVideoDuration(videoAudioRef.current.duration);
                      }
                    }}
                    onEnded={() => setVideoPlaying(false)}
                    style={{ display: 'none' }}
                  />
                )}

                {/* 1080p Full HD Interactive Video Player Stage */}
                <div
                  ref={videoStageRef}
                  style={{
                    position: 'relative',
                    borderRadius: '16px',
                    overflow: 'hidden',
                    background: '#050811',
                    border: '2px solid var(--border-strong)',
                    boxShadow: 'var(--shadow-lg)',
                  }}
                >
                  {/* 16:9 1920x1080 Canvas Viewport */}
                  <div
                    onClick={toggleVideoPlay}
                    style={{
                      position: 'relative',
                      width: '100%',
                      aspectRatio: '16 / 9',
                      cursor: 'pointer',
                      background: '#050811',
                    }}
                  >
                    <canvas
                      ref={videoCanvasRef}
                      width={1920}
                      height={1080}
                      style={{
                        width: '100%',
                        height: '100%',
                        display: 'block',
                        objectFit: 'contain',
                      }}
                    />

                    {/* Center Play Overlay when Paused */}
                    {!videoPlaying && (
                      <div
                        style={{
                          position: 'absolute',
                          inset: 0,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: 'rgba(5, 8, 17, 0.32)',
                        }}
                      >
                        <div
                          style={{
                            width: 74,
                            height: 74,
                            borderRadius: '50%',
                            background: 'var(--gradient-brand)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: '0 12px 32px rgba(56, 189, 248, 0.45)',
                            color: '#fff',
                          }}
                        >
                          <Play size={32} fill="#fff" />
                        </div>
                      </div>
                    )}

                    {/* Top-Right Resolution & Language Overlay Badge */}
                    <div
                      style={{
                        position: 'absolute',
                        top: 14,
                        right: 16,
                        display: 'flex',
                        gap: '8px',
                      }}
                    >
                      <span
                        className="badge badge-blue"
                        style={{ background: 'rgba(7, 11, 24, 0.85)', backdropFilter: 'blur(8px)' }}
                      >
                        1080p Full HD
                      </span>
                      <span
                        className="badge badge-indigo"
                        style={{ background: 'rgba(7, 11, 24, 0.85)', backdropFilter: 'blur(8px)' }}
                      >
                        {activeOutput.language || 'English'}
                      </span>
                    </div>

                    {/* Live Closed Captions Overlay */}
                    {showCaptions && currentScene && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: 18,
                          left: '8%',
                          right: '8%',
                          padding: '10px 18px',
                          borderRadius: '10px',
                          background: 'rgba(4, 7, 15, 0.88)',
                          border: '1px solid rgba(56, 189, 248, 0.35)',
                          color: '#fde68a',
                          fontSize: '0.94rem',
                          fontWeight: 600,
                          textAlign: 'center',
                          pointerEvents: 'none',
                        }}
                      >
                        [CC] {currentScene.caption || currentScene.narration}
                      </div>
                    )}
                  </div>

                  {/* Full Video Player Control Bar */}
                  <div
                    style={{
                      padding: '12px 18px',
                      background: 'rgba(9, 13, 28, 0.98)',
                      borderTop: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                    }}
                  >
                    {/* Interactive Seek Bar */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)', minWidth: 42 }}>
                        {formatTime(videoCurrentTime)}
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={Math.max(1, videoDuration)}
                        step={0.1}
                        value={Math.min(videoCurrentTime, Math.max(1, videoDuration))}
                        onChange={(e) => handleVideoSeek(Number(e.target.value))}
                        style={{ flex: 1, cursor: 'pointer', accentColor: 'var(--accent-blue)' }}
                        aria-label="Video timeline seek bar"
                      />
                      <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', minWidth: 42 }}>
                        {formatTime(videoDuration)}
                      </span>
                    </div>

                    {/* Transport & Utility Controls */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={toggleVideoPlay}
                        >
                          {videoPlaying ? <Pause size={15} /> : <Play size={15} />}
                          <span>{videoPlaying ? 'Pause' : 'Play Video'}</span>
                        </button>

                        {/* Volume Control */}
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            const nextMute = !videoMuted;
                            setVideoMuted(nextMute);
                            if (videoAudioRef.current) videoAudioRef.current.muted = nextMute;
                          }}
                          title="Mute / Unmute"
                        >
                          {videoMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
                        </button>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={videoMuted ? 0 : videoVolume}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            setVideoVolume(v);
                            setVideoMuted(v === 0);
                            if (videoAudioRef.current) {
                              videoAudioRef.current.volume = v;
                              videoAudioRef.current.muted = v === 0;
                            }
                          }}
                          style={{ width: 75, cursor: 'pointer', accentColor: 'var(--accent-blue)' }}
                          aria-label="Volume"
                        />

                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                          Scene {activeSceneIdx + 1} / {Math.max(1, scenes.length)}:{' '}
                          <strong>{currentScene?.title}</strong>
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        {/* Playback Speed */}
                        <select
                          className="form-select"
                          style={{ width: 'auto', padding: '4px 10px', fontSize: '0.8rem' }}
                          value={videoSpeed}
                          onChange={(e) => {
                            const sp = Number(e.target.value);
                            setVideoSpeed(sp);
                            if (videoAudioRef.current) videoAudioRef.current.playbackRate = sp;
                          }}
                          aria-label="Video playback speed"
                        >
                          <option value={0.75}>0.75x</option>
                          <option value={1}>1.0x</option>
                          <option value={1.25}>1.25x</option>
                          <option value={1.5}>1.5x</option>
                          <option value={2}>2.0x</option>
                        </select>

                        {/* Captions Toggle */}
                        <button
                          type="button"
                          className={`btn btn-sm ${showCaptions ? 'btn-primary' : 'btn-secondary'}`}
                          onClick={() => setShowCaptions((c) => !c)}
                          title="Toggle Subtitles / Captions"
                        >
                          <Subtitles size={14} />
                          <span>CC</span>
                        </button>

                        {/* Fullscreen Button */}
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={handleToggleFullscreen}
                          title="Fullscreen"
                        >
                          <Maximize2 size={14} />
                          <span>Fullscreen</span>
                        </button>

                        {/* Download MP4 Video */}
                        {mp4Url && (
                          <a
                            href={mp4Url}
                            download={`${activeOutput.title.replace(/\s+/g, '_')}_1080p.mp4`}
                            className="btn btn-secondary btn-sm"
                          >
                            <Download size={14} />
                            <span>Download MP4</span>
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Interactive Scene Chapters & Storyboard Breakdown */}
                <div>
                  <h3 style={{ fontSize: '1.05rem', marginBottom: '10px' }}>
                    Interactive Video Chapters & Visual Explanations (Click any scene to jump)
                  </h3>
                  <div className="grid-2">
                    {scenes.map((sc: any, idx: number) => (
                      <div
                        key={idx}
                        onClick={() => handleJumpToScene(idx)}
                        style={{
                          padding: '14px',
                          borderRadius: '12px',
                          background:
                            idx === activeSceneIdx
                              ? 'rgba(56, 189, 248, 0.15)'
                              : 'var(--bg-charcoal)',
                          border:
                            idx === activeSceneIdx
                              ? '1px solid var(--accent-blue)'
                              : '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.9rem', color: idx === activeSceneIdx ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                            Scene {sc.scene_number || idx + 1}: {sc.title}
                          </span>
                          <span className="badge badge-indigo">{sc.duration_seconds}s</span>
                        </div>
                        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                          {sc.narration}
                        </p>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Visual: {sc.visual_description}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ============================================================
              3. SLIDE DECK VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'slide_deck' && (() => {
            const slides = activeOutput.content.slides || [];
            const currentSlide = slides[currentSlideIdx] || slides[0];
            if (!currentSlide) return null;

            const moveSlide = (dir: -1 | 1) => {
              const target = currentSlideIdx + dir;
              if (target < 0 || target >= slides.length) return;
              const nextSlides = [...slides];
              const tmp = nextSlides[currentSlideIdx];
              nextSlides[currentSlideIdx] = nextSlides[target];
              nextSlides[target] = tmp;
              nextSlides.forEach((s, idx) => (s.slide_number = idx + 1));
              handleSaveContentUpdate({ ...activeOutput.content, slides: nextSlides });
              setCurrentSlideIdx(target);
            };

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setEditingSlide((e) => !e)}
                    >
                      <Edit3 size={14} />
                      <span>{editingSlide ? 'Done Editing Slide' : 'Edit Slide Text'}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => moveSlide(-1)}
                      disabled={currentSlideIdx === 0}
                    >
                      <ArrowUp size={14} />
                      <span>Move Earlier</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => moveSlide(1)}
                      disabled={currentSlideIdx === slides.length - 1}
                    >
                      <ArrowDown size={14} />
                      <span>Move Later</span>
                    </button>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setSlideFullscreen((f) => !f)}
                    >
                      <Maximize2 size={14} />
                      <span>{slideFullscreen ? 'Exit Presentation' : 'Presentation Mode'}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleExportSlidesHtml}
                    >
                      <Download size={14} />
                      <span>Export Printable Deck</span>
                    </button>
                  </div>
                </div>

                <div
                  style={{
                    minHeight: slideFullscreen ? 460 : 340,
                    padding: '36px',
                    borderRadius: '16px',
                    background: 'linear-gradient(145deg, #111834 0%, #090d1f 100%)',
                    border: '1px solid var(--border-strong)',
                    boxShadow: 'var(--shadow-lg)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  {editingSlide ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <input
                        type="text"
                        className="form-input"
                        value={currentSlide.title}
                        onChange={(e) => {
                          const nextSlides = [...slides];
                          nextSlides[currentSlideIdx] = {
                            ...currentSlide,
                            title: e.target.value,
                          };
                          setActiveOutput({
                            ...activeOutput,
                            content: { ...activeOutput.content, slides: nextSlides },
                          });
                        }}
                      />
                      <textarea
                        className="form-textarea"
                        value={(currentSlide.bullets || []).join('\n')}
                        onChange={(e) => {
                          const nextSlides = [...slides];
                          nextSlides[currentSlideIdx] = {
                            ...currentSlide,
                            bullets: e.target.value.split('\n'),
                          };
                          setActiveOutput({
                            ...activeOutput,
                            content: { ...activeOutput.content, slides: nextSlides },
                          });
                        }}
                      />
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => {
                          handleSaveContentUpdate(activeOutput.content);
                          setEditingSlide(false);
                        }}
                      >
                        <Save size={14} />
                        <span>Save Slide Changes</span>
                      </button>
                    </div>
                  ) : (
                    <>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                          <span className="badge badge-blue">
                            Slide {currentSlideIdx + 1} of {slides.length}
                          </span>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            BRAINOVA Slide Studio • {activeOutput.language || 'English'}
                          </span>
                        </div>
                        <h2 style={{ fontSize: '1.75rem', marginBottom: '6px' }}>
                          {currentSlide.title}
                        </h2>
                        <p style={{ color: 'var(--accent-blue)', fontSize: '0.95rem', marginBottom: '20px' }}>
                          {currentSlide.subtitle}
                        </p>
                        <ul style={{ paddingLeft: '22px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '1.02rem' }}>
                          {(currentSlide.bullets || []).map((b: string, i: number) => (
                            <li key={i}>{b}</li>
                          ))}
                        </ul>
                      </div>

                      <div
                        style={{
                          marginTop: '24px',
                          paddingTop: '14px',
                          borderTop: '1px solid var(--border-subtle)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: '0.82rem',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <span>Example: {currentSlide.example}</span>
                        <span>Visual Layout: {currentSlide.visual_suggestion}</span>
                      </div>
                    </>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setCurrentSlideIdx((i) => Math.max(0, i - 1))}
                    disabled={currentSlideIdx === 0}
                  >
                    <ChevronLeft size={16} />
                    <span>Previous Slide</span>
                  </button>

                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {slides.map((_: any, idx: number) => (
                      <button
                        key={idx}
                        type="button"
                        className={`btn btn-sm ${
                          idx === currentSlideIdx ? 'btn-primary' : 'btn-secondary'
                        }`}
                        onClick={() => setCurrentSlideIdx(idx)}
                      >
                        {idx + 1}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setCurrentSlideIdx((i) => Math.min(slides.length - 1, i + 1))}
                    disabled={currentSlideIdx === slides.length - 1}
                  >
                    <span>Next Slide</span>
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            );
          })()}

          {/* ============================================================
              4. INTERACTIVE MIND MAP VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'mind_map' && (() => {
            const root = activeOutput.content.root;
            if (!root) return null;
            const branches = root.children || [];

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setMapZoom((z) => Math.min(1.4, +(z + 0.15).toFixed(2)))}
                    >
                      <ZoomIn size={14} />
                      <span>Zoom In</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setMapZoom((z) => Math.max(0.7, +(z - 0.15).toFixed(2)))}
                    >
                      <ZoomOut size={14} />
                      <span>Zoom Out</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setMapZoom(1);
                        setCollapsedNodes({});
                      }}
                    >
                      Reset View
                    </button>
                  </div>

                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() =>
                      downloadFile(
                        `${activeOutput.title.replace(/\s+/g, '_')}_mindmap.json`,
                        JSON.stringify(activeOutput.content, null, 2),
                        'application/json'
                      )
                    }
                  >
                    <Download size={14} />
                    <span>Export Mind Map JSON</span>
                  </button>
                </div>

                <div
                  style={{
                    width: '100%',
                    overflowX: 'auto',
                    borderRadius: '14px',
                    background: '#060913',
                    border: '1px solid var(--border-default)',
                    padding: '16px',
                  }}
                >
                  <svg
                    width={Math.round(820 * mapZoom)}
                    height={Math.round(440 * mapZoom)}
                    viewBox="0 0 820 440"
                    style={{ display: 'block', margin: '0 auto' }}
                  >
                    {branches.map((br: any, bIdx: number) => {
                      const by = 70 + bIdx * 100;
                      const isCollapsed = collapsedNodes[br.id];
                      return (
                        <g key={br.id}>
                          <path
                            d={`M 190 220 C 260 220, 260 ${by}, 330 ${by}`}
                            fill="none"
                            stroke="#6366f1"
                            strokeWidth="2.5"
                          />
                          {!isCollapsed &&
                            (br.children || []).map((leaf: any, lIdx: number) => {
                              const ly = by - 22 + lIdx * 44;
                              return (
                                <g key={leaf.id}>
                                  <path
                                    d={`M 520 ${by} C 565 ${by}, 565 ${ly}, 605 ${ly}`}
                                    fill="none"
                                    stroke="#38bdf8"
                                    strokeWidth="1.8"
                                  />
                                  <g
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => setSelectedMindNode(leaf)}
                                  >
                                    <rect
                                      x={605}
                                      y={ly - 16}
                                      width={195}
                                      height={32}
                                      rx={8}
                                      fill="#161f3d"
                                      stroke={
                                        selectedMindNode?.id === leaf.id ? '#38bdf8' : '#334155'
                                      }
                                      strokeWidth="1.5"
                                    />
                                    <text
                                      x={615}
                                      y={ly + 4}
                                      fill="#e2e8f0"
                                      fontSize="11.5"
                                      fontWeight="600"
                                    >
                                      {leaf.label.slice(0, 25)}
                                    </text>
                                  </g>
                                </g>
                              );
                            })}

                          <g style={{ cursor: 'pointer' }} onClick={() => setSelectedMindNode(br)}>
                            <rect
                              x={330}
                              y={by - 20}
                              width={190}
                              height={40}
                              rx={10}
                              fill="#1e2a52"
                              stroke={selectedMindNode?.id === br.id ? '#38bdf8' : '#6366f1'}
                              strokeWidth="2"
                            />
                            <text x={342} y={by + 4} fill="#ffffff" fontSize="12" fontWeight="700">
                              {br.label.slice(0, 22)}
                            </text>
                          </g>

                          <g
                            style={{ cursor: 'pointer' }}
                            onClick={() =>
                              setCollapsedNodes((prev) => ({
                                ...prev,
                                [br.id]: !prev[br.id],
                              }))
                            }
                          >
                            <circle cx={520} cy={by} r={10} fill="#38bdf8" />
                            <text x={516} y={by + 4} fill="#070a14" fontSize="12" fontWeight="800">
                              {isCollapsed ? '+' : '−'}
                            </text>
                          </g>
                        </g>
                      );
                    })}

                    <g style={{ cursor: 'pointer' }} onClick={() => setSelectedMindNode(root)}>
                      <rect
                        x={20}
                        y={192}
                        width={170}
                        height={56}
                        rx={14}
                        fill="#4f46e5"
                        stroke="#38bdf8"
                        strokeWidth="2.5"
                      />
                      <text x={34} y={224} fill="#ffffff" fontSize="13" fontWeight="800">
                        {root.label.slice(0, 20)}
                      </text>
                    </g>
                  </svg>
                </div>

                {selectedMindNode && (
                  <div
                    style={{
                      padding: '16px',
                      borderRadius: '12px',
                      background: 'var(--bg-charcoal)',
                      border: '1px solid var(--accent-blue)',
                    }}
                  >
                    <div style={{ fontSize: '0.76rem', color: 'var(--accent-blue)', fontWeight: 700 }}>
                      SELECTED NODE INSPECTOR ({selectedMindNode.category?.toUpperCase()})
                    </div>
                    <h4 style={{ fontSize: '1.1rem', margin: '4px 0 6px' }}>
                      {selectedMindNode.label}
                    </h4>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      {selectedMindNode.details}
                    </p>
                  </div>
                )}
              </div>
            );
          })()}

          {/* ============================================================
              5. STUDY GUIDE / REPORT VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'study_guide' && (
            <div className="reading-prose" style={{ maxWidth: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setEditingGuide((e) => !e)}
                >
                  <Edit3 size={14} />
                  <span>{editingGuide ? 'Cancel Edit' : 'Edit Study Guide'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() =>
                    downloadFile(
                      `${activeOutput.title.replace(/\s+/g, '_')}.md`,
                      `# ${activeOutput.title}\n\n${activeOutput.content.overview}\n\n${(
                        activeOutput.content.sections || []
                      )
                        .map((s: any) => `## ${s.heading}\n${s.content}`)
                        .join('\n\n')}`,
                      'text/markdown'
                    )
                  }
                >
                  <Download size={14} />
                  <span>Export Markdown</span>
                </button>
              </div>

              {editingGuide ? (
                <div>
                  <div className="form-group">
                    <label className="form-label">Overview</label>
                    <textarea
                      className="form-textarea"
                      value={guideOverviewEdit}
                      onChange={(e) => setGuideOverviewEdit(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Summary</label>
                    <textarea
                      className="form-textarea"
                      value={guideSummaryEdit}
                      onChange={(e) => setGuideSummaryEdit(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      handleSaveContentUpdate({
                        ...activeOutput.content,
                        overview: guideOverviewEdit,
                        summary: guideSummaryEdit,
                      });
                      setEditingGuide(false);
                    }}
                  >
                    <Save size={14} />
                    <span>Save Study Guide Edits</span>
                  </button>
                </div>
              ) : (
                <>
                  <p style={{ color: 'var(--text-primary)', fontSize: '1.02rem' }}>
                    {activeOutput.content.overview}
                  </p>
                  {(activeOutput.content.sections || []).map((sec: any, idx: number) => (
                    <div key={idx} style={{ marginBottom: '20px' }}>
                      <h3>{sec.heading}</h3>
                      <p style={{ whiteSpace: 'pre-wrap' }}>{sec.content}</p>
                    </div>
                  ))}
                  {activeOutput.content.terminology?.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h3>Important Terminology</h3>
                      {activeOutput.content.terminology.map((t: any, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            padding: '10px 14px',
                            borderRadius: '8px',
                            background: 'var(--bg-charcoal)',
                            marginBottom: '8px',
                          }}
                        >
                          <strong style={{ color: 'var(--accent-blue)' }}>{t.term}:</strong>{' '}
                          {t.definition}
                        </div>
                      ))}
                    </div>
                  )}
                  <div style={{ padding: '16px', borderRadius: '12px', background: 'var(--surface-2)' }}>
                    <strong>Summary:</strong> {activeOutput.content.summary}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ============================================================
              6. FLASHCARDS VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'flashcards' && (() => {
            const cards = activeOutput.content.cards || [];
            const currentCard = cards[currentCardIdx] || cards[0];
            const knownCount = cards.filter((c: any) => c.status === 'known').length;
            const learningCount = cards.filter((c: any) => c.status === 'learning').length;
            const reviewCount = cards.filter((c: any) => c.status === 'review').length;
            const newCount = cards.filter((c: any) => !c.status || c.status === 'new').length;

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                <div className="grid-4">
                  <div style={{ padding: '10px 14px', borderRadius: '10px', background: 'var(--bg-charcoal)' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>NEW / UNSEEN</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>{newCount}</div>
                  </div>
                  <div style={{ padding: '10px 14px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.12)' }}>
                    <div style={{ fontSize: '0.72rem', color: '#6ee7b7' }}>KNOWN</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#6ee7b7' }}>{knownCount}</div>
                  </div>
                  <div style={{ padding: '10px 14px', borderRadius: '10px', background: 'rgba(56, 189, 248, 0.12)' }}>
                    <div style={{ fontSize: '0.72rem', color: '#7dd3fc' }}>LEARNING</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#7dd3fc' }}>{learningCount}</div>
                  </div>
                  <div style={{ padding: '10px 14px', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.12)' }}>
                    <div style={{ fontSize: '0.72rem', color: '#fcd34d' }}>NEEDS REVIEW</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fcd34d' }}>{reviewCount}</div>
                  </div>
                </div>

                {currentCard && (
                  <>
                    <div
                      onClick={() => setCardFlipped((f) => !f)}
                      style={{
                        minHeight: 260,
                        padding: '32px',
                        borderRadius: '16px',
                        background: cardFlipped
                          ? 'linear-gradient(145deg, #162447 0%, #0f172a 100%)'
                          : 'linear-gradient(145deg, #171e3d 0%, #0b1020 100%)',
                        border: '2px solid var(--border-strong)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        boxShadow: 'var(--shadow-md)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="badge badge-indigo">
                          Card {currentCardIdx + 1} of {cards.length} •{' '}
                          {cardFlipped ? 'ANSWER (BACK)' : 'QUESTION (FRONT)'}
                        </span>
                        <span className="badge badge-blue">
                          Status: {(currentCard.status || 'new').toUpperCase()}
                        </span>
                      </div>

                      <div style={{ fontSize: '1.25rem', fontWeight: 600, textAlign: 'center', margin: '24px 0' }}>
                        {cardFlipped ? currentCard.back : currentCard.front}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        <span>Click card to flip</span>
                        {currentCard.hint && !cardFlipped && <span>Hint: {currentCard.hint}</span>}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            setCardFlipped(false);
                            setCurrentCardIdx((i) => Math.max(0, i - 1));
                          }}
                          disabled={currentCardIdx === 0}
                        >
                          <ChevronLeft size={15} />
                          <span>Prev</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            setCardFlipped(false);
                            setCurrentCardIdx((i) => Math.min(cards.length - 1, i + 1));
                          }}
                          disabled={currentCardIdx === cards.length - 1}
                        >
                          <span>Next</span>
                          <ChevronRight size={15} />
                        </button>
                      </div>

                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => handleRateFlashcard(currentCard, 'review')}
                        >
                          Needs Review
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRateFlashcard(currentCard, 'learning')}
                        >
                          Still Learning
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleRateFlashcard(currentCard, 'known')}
                        >
                          <CheckCircle2 size={14} />
                          <span>Mark Known</span>
                        </button>
                      </div>

                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => setShowAddCardModal(true)}
                        >
                          <Plus size={14} />
                          <span>Add Card</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDeleteFlashcard(currentCard.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            );
          })()}

          {/* ============================================================
              7. QUIZ VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'quiz' && (() => {
            const questions = activeOutput.content.questions || [];
            const allowPracticeHints = Boolean(activeOutput.content.practice_mode_allowed);
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {studioQuizResult && (
                  <div
                    style={{
                      padding: '16px',
                      borderRadius: '12px',
                      background: 'rgba(16, 185, 129, 0.14)',
                      border: '1px solid var(--status-success)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <strong>
                        Submitted Score: {studioQuizResult.score} / {studioQuizResult.max_score} (
                        {studioQuizResult.percentage}%)
                      </strong>
                      <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        Correct: {studioQuizResult.correct_count} • Wrong:{' '}
                        {studioQuizResult.incorrect_count} • Unanswered:{' '}
                        {studioQuizResult.unanswered_count}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setStudioQuizAnswers({});
                        setStudioQuizResult(null);
                      }}
                    >
                      Retake Quiz
                    </button>
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxHeight: 540, overflowY: 'auto', paddingRight: '4px' }}>
                  {questions.map((q: any, qIdx: number) => {
                    const chosen = studioQuizAnswers[q.id];
                    return (
                      <div
                        key={q.id}
                        style={{
                          padding: '14px',
                          borderRadius: '10px',
                          background: 'var(--bg-charcoal)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: '10px' }}>
                          {q.number || qIdx + 1}. {q.question}
                        </div>
                        <div className="grid-2" style={{ gap: '8px' }}>
                          {(q.options || []).map((opt: string, oIdx: number) => {
                            const isSel = chosen === oIdx;
                            return (
                              <button
                                key={oIdx}
                                type="button"
                                onClick={() =>
                                  !studioQuizResult &&
                                  setStudioQuizAnswers((prev) => ({
                                    ...prev,
                                    [q.id]: oIdx,
                                  }))
                                }
                                style={{
                                  textAlign: 'left',
                                  padding: '10px 12px',
                                  borderRadius: '8px',
                                  background: isSel
                                    ? 'rgba(56, 189, 248, 0.18)'
                                    : 'var(--surface-1)',
                                  border: isSel
                                    ? '1px solid var(--accent-blue)'
                                    : '1px solid var(--border-subtle)',
                                  color: 'var(--text-primary)',
                                  cursor: 'pointer',
                                  fontSize: '0.86rem',
                                }}
                              >
                                <strong>{String.fromCharCode(65 + oIdx)}.</strong> {opt}
                              </button>
                            );
                          })}
                        </div>
                        {(studioQuizResult || allowPracticeHints) && (
                          <div style={{ fontSize: '0.82rem', color: 'var(--accent-blue)', marginTop: '8px' }}>
                            <strong>Answer & Explanation:</strong> Option{' '}
                            {String.fromCharCode(65 + q.correct_index)} — {q.explanation}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {!studioQuizResult && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleSubmitStudioQuiz}
                    disabled={submittingStudioQuiz}
                  >
                    <CheckCircle2 size={16} />
                    <span>
                      {submittingStudioQuiz
                        ? 'Grading Assessment...'
                        : `Submit ${questions.length}-Question Quiz`}
                    </span>
                  </button>
                )}
              </div>
            );
          })()}

          {/* ============================================================
              8. INFOGRAPHIC VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'infographic' && (() => {
            const info = activeOutput.content;
            return (
              <div
                style={{
                  padding: '28px',
                  borderRadius: '16px',
                  background: 'linear-gradient(180deg, #0e1630 0%, #080c1c 100%)',
                  border: '2px solid rgba(56, 189, 248, 0.35)',
                }}
              >
                <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                  <span className="badge badge-blue" style={{ marginBottom: 6 }}>
                    VISUAL EDUCATIONAL SUMMARY INFOGRAPHIC • {activeOutput.language || 'English'}
                  </span>
                  <h2 style={{ fontSize: '1.7rem' }}>{info.title}</h2>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                    {info.subtitle}
                  </p>
                </div>

                <div className="grid-4" style={{ marginBottom: '24px' }}>
                  {(info.hero_stat_cards || []).map((st: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        padding: '14px',
                        borderRadius: '12px',
                        background: 'rgba(99, 102, 241, 0.14)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        textAlign: 'center',
                      }}
                    >
                      <div style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--accent-blue)' }}>
                        {st.value}
                      </div>
                      <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>{st.label}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {st.detail}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="grid-2" style={{ marginBottom: '24px' }}>
                  {(info.visual_sections || []).map((sec: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        padding: '16px',
                        borderRadius: '12px',
                        background: 'var(--surface-1)',
                        borderLeft: '4px solid var(--accent-indigo)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <strong style={{ color: 'var(--accent-blue)', fontSize: '1.05rem' }}>
                          STAGE {sec.step}: {sec.title}
                        </strong>
                        <span className="badge badge-indigo">{sec.badge}</span>
                      </div>
                      <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
                        {sec.summary}
                      </p>
                    </div>
                  ))}
                </div>

                {info.comparison_callout && (
                  <div className="grid-2" style={{ marginBottom: '18px' }}>
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.09)', border: '1px solid rgba(239, 68, 68, 0.28)' }}>
                      <strong style={{ color: '#fca5a5' }}>
                        {info.comparison_callout.left_title}
                      </strong>
                      <ul style={{ paddingLeft: '18px', marginTop: '8px', fontSize: '0.84rem' }}>
                        {(info.comparison_callout.left_points || []).map((pt: string, i: number) => (
                          <li key={i}>{pt}</li>
                        ))}
                      </ul>
                    </div>
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.09)', border: '1px solid rgba(16, 185, 129, 0.28)' }}>
                      <strong style={{ color: '#6ee7b7' }}>
                        {info.comparison_callout.right_title}
                      </strong>
                      <ul style={{ paddingLeft: '18px', marginTop: '8px', fontSize: '0.84rem' }}>
                        {(info.comparison_callout.right_points || []).map(
                          (pt: string, i: number) => (
                            <li key={i}>{pt}</li>
                          )
                        )}
                      </ul>
                    </div>
                  </div>
                )}

                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: '10px',
                    background: 'var(--surface-2)',
                    textAlign: 'center',
                    fontSize: '0.88rem',
                  }}
                >
                  <strong>Key Takeaway:</strong> {info.footer_takeaway}
                </div>
              </div>
            );
          })()}

          {/* ============================================================
              9. DATA TABLE VIEWER
             ============================================================ */}
          {activeOutput.tool_type === 'data_table' && (() => {
            const cols: string[] = activeOutput.content.columns || [];
            let rows: any[] = [...(activeOutput.content.rows || [])];

            if (tableSearch.trim()) {
              const q = tableSearch.trim().toLowerCase();
              rows = rows.filter((r) =>
                (r.cells || []).some((c: string) => String(c).toLowerCase().includes(q))
              );
            }
            if (sortColIdx !== null) {
              rows.sort((a, b) => {
                const va = String(a.cells?.[sortColIdx] || '').toLowerCase();
                const vb = String(b.cells?.[sortColIdx] || '').toLowerCase();
                return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
              });
            }

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <input
                    type="search"
                    className="form-input"
                    style={{ maxWidth: 320 }}
                    placeholder="Search extracted rows..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleExportCSV}
                  >
                    <Download size={14} />
                    <span>Export to CSV</span>
                  </button>
                </div>

                {activeOutput.content.missing_data_notes && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {activeOutput.content.missing_data_notes}
                  </div>
                )}

                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {cols.map((col, cIdx) => (
                          <th
                            key={cIdx}
                            style={{ cursor: 'pointer' }}
                            onClick={() => {
                              if (sortColIdx === cIdx) {
                                setSortAsc((a) => !a);
                              } else {
                                setSortColIdx(cIdx);
                                setSortAsc(true);
                              }
                            }}
                          >
                            {col} {sortColIdx === cIdx ? (sortAsc ? '▲' : '▼') : ''}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r: any, rIdx: number) => (
                        <tr key={r.id || rIdx}>
                          {(r.cells || []).map((cell: string, cIdx: number) => (
                            <td key={cIdx}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Search, Tool Filter, Language Filter & Sort Controls */}
      <div className="card">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: '14px',
            alignItems: 'end',
          }}
        >
          <div>
            <label className="form-label">Search Saved Outputs</label>
            <div style={{ position: 'relative' }}>
              <Search
                size={15}
                style={{
                  position: 'absolute',
                  left: 12,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="search"
                className="form-input"
                style={{ paddingLeft: 34 }}
                placeholder="Search title, tool, or source..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="form-label">Output Tool Category</label>
            <select
              className="form-select"
              value={toolFilter}
              onChange={(e) => setToolFilter(e.target.value)}
              aria-label="Filter by Output Type"
            >
              <option value="all">All 9 AI Studio Tools</option>
              <option value="audio_overview">1. Audio Overview</option>
              <option value="video_overview">2. Video Overview</option>
              <option value="slide_deck">3. Slide Deck</option>
              <option value="mind_map">4. Mind Map</option>
              <option value="study_guide">5. Study Guide / Report</option>
              <option value="flashcards">6. Flashcards</option>
              <option value="quiz">7. Quiz</option>
              <option value="infographic">8. Infographic</option>
              <option value="data_table">9. Data Table</option>
            </select>
          </div>

          <div>
            <label className="form-label">Language Filter</label>
            <select
              className="form-select"
              value={languageFilter}
              onChange={(e) => setLanguageFilter(e.target.value)}
              aria-label="Filter by Language"
            >
              <option value="all">All 6 Languages</option>
              <option value="English">English</option>
              <option value="Telugu">Telugu (తెలుగు)</option>
              <option value="Hindi">Hindi (हिन्दी)</option>
              <option value="Kannada">Kannada (ಕನ್ನಡ)</option>
              <option value="Tamil">Tamil (தமிழ்)</option>
              <option value="Marathi">Marathi (मराठी)</option>
            </select>
          </div>

          <div>
            <label className="form-label">Sort Order</label>
            <select
              className="form-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              aria-label="Sort Outputs"
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="title">Alphabetical (A–Z)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Saved Outputs Grid */}
      {loading ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 24px' }}>
          <p style={{ color: 'var(--text-secondary)' }}>Loading your AI Studio Library...</p>
        </div>
      ) : filteredOutputs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '64px 24px' }}>
          <Library size={44} color="var(--accent-blue)" style={{ marginBottom: '12px' }} />
          <h3 style={{ fontSize: '1.25rem', marginBottom: '6px' }}>
            {outputs.length === 0
              ? 'Your AI Studio Library is Empty'
              : 'No Saved Outputs Match Your Current Filters'}
          </h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: 460, margin: '0 auto 18px' }}>
            {outputs.length === 0
              ? 'Generate your first Audio Overview, 1080p Video Overview, Slide Deck, Mind Map, Study Guide, Flashcards, Quiz, Infographic, or Data Table in AI Studio.'
              : 'Try clearing your search query or switching the tool/language filters above.'}
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/studio')}
          >
            <Sparkles size={16} />
            <span>Open AI Studio to Generate</span>
          </button>
        </div>
      ) : (
        <div className="grid-3">
          {filteredOutputs.map((out) => {
            const meta = STUDIO_TOOL_META[out.tool_type] || {
              name: out.tool_type,
              badge: 'Studio Output',
              icon: Sparkles,
              accent: '#38bdf8',
            };
            const Icon = meta.icon;
            const outLang = out.language || out.config?.language || 'English';
            const thumbUrl = out.content?.video?.thumbnail_data_url;
            const isSelected = activeOutput?.id === out.id;

            return (
              <div
                key={out.id}
                className="card card-interactive"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  padding: 0,
                  overflow: 'hidden',
                  borderColor: isSelected ? 'var(--accent-blue)' : 'var(--border-subtle)',
                }}
              >
                {/* Visual Preview / Thumbnail Header */}
                <div
                  onClick={() => selectOutputItem(out)}
                  style={{
                    height: 140,
                    position: 'relative',
                    cursor: 'pointer',
                    background: thumbUrl
                      ? `url(${thumbUrl}) center/cover no-repeat`
                      : `linear-gradient(135deg, rgba(16, 24, 52, 0.96) 0%, rgba(9, 13, 28, 0.98) 100%)`,
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {!thumbUrl && (
                    <div
                      style={{
                        width: 54,
                        height: 54,
                        borderRadius: '14px',
                        background: 'rgba(56, 189, 248, 0.14)',
                        border: '1px solid rgba(56, 189, 248, 0.35)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: meta.accent,
                      }}
                    >
                      <Icon size={26} />
                    </div>
                  )}

                  <div
                    style={{
                      position: 'absolute',
                      top: 10,
                      left: 12,
                      display: 'flex',
                      gap: '6px',
                    }}
                  >
                    <span className="badge badge-indigo">{meta.name}</span>
                  </div>

                  <div
                    style={{
                      position: 'absolute',
                      top: 10,
                      right: 12,
                    }}
                  >
                    <span className="badge badge-blue">{outLang}</span>
                  </div>

                  {out.duration_label && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: 8,
                        right: 12,
                        padding: '2px 8px',
                        borderRadius: '6px',
                        background: 'rgba(5, 8, 17, 0.85)',
                        fontSize: '0.72rem',
                        color: '#e2e8f0',
                      }}
                    >
                      {out.duration_label}
                    </div>
                  )}
                </div>

                {/* Card Body */}
                <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '12px' }}>
                  <div>
                    <h3
                      onClick={() => selectOutputItem(out)}
                      style={{
                        fontSize: '1.02rem',
                        marginBottom: '6px',
                        cursor: 'pointer',
                        lineHeight: 1.35,
                      }}
                    >
                      {out.title}
                    </h3>

                    <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Created {new Date(out.created_at).toLocaleDateString()} •{' '}
                      {LANGUAGE_LABELS[outLang] || outLang}
                    </div>

                    {out.source_titles && out.source_titles.length > 0 && (
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {out.source_titles.slice(0, 2).map((st: string, i: number) => (
                          <span
                            key={i}
                            style={{
                              fontSize: '0.72rem',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'var(--bg-charcoal)',
                              color: 'var(--text-secondary)',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <FileText size={11} />
                            {st.slice(0, 26)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Card Actions: Open / View & Delete */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)' }}>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      style={{ flex: 1 }}
                      onClick={() => selectOutputItem(out)}
                    >
                      <Eye size={14} />
                      <span>Open / View</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => setDeleteTarget(out)}
                      title="Delete Output"
                    >
                      <Trash2 size={14} />
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Output Confirmation Modal */}
      {deleteTarget && (
        <div className="modal-backdrop" onClick={() => !deleting && setDeleteTarget(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', color: 'var(--status-danger)' }}>
              <AlertTriangle size={22} />
              <h3 style={{ margin: 0 }}>Delete Saved Output?</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginBottom: '18px' }}>
              Are you sure you want to permanently delete{' '}
              <strong>"{deleteTarget.title}"</strong> from your AI Studio Library? This action
              removes the record and associated media files from the database.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={deleting}
              >
                <Trash2 size={14} />
                <span>{deleting ? 'Deleting...' : 'Confirm Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Flashcard Modal */}
      {showAddCardModal && (
        <div className="modal-backdrop" onClick={() => setShowAddCardModal(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '12px' }}>Add Custom Flashcard</h3>
            <form onSubmit={handleAddFlashcard}>
              <div className="form-group">
                <label className="form-label">Question (Front)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newCardFront}
                  onChange={(e) => setNewCardFront(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Answer (Back)</label>
                <textarea
                  className="form-textarea"
                  value={newCardBack}
                  onChange={(e) => setNewCardBack(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Hint (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={newCardHint}
                  onChange={(e) => setNewCardHint(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddCardModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Card
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Overwrite Confirmation Modal */}
      {showRegenConfirm && (
        <div className="modal-backdrop" onClick={() => setShowRegenConfirm(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', color: 'var(--status-warning)' }}>
              <AlertTriangle size={22} />
              <h3 style={{ margin: 0 }}>Overwrite Personal Edits?</h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              You have saved custom edits to this AI Studio output. Regenerating will replace your
              modifications with a newly generated version. Proceed?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowRegenConfirm(false)}
              >
                Keep My Edits
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => handleRegenerateOutput(true)}
              >
                Confirm Overwrite
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

