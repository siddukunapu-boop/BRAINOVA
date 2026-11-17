import React, { useRef, useState } from 'react';
import {
  Headphones,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Repeat,
  Upload,
  Trash2,
  Music,
  Sparkles,
  Waves,
  CloudRain,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import {
  useMusicPlayer,
  type MusicCategoryFilter,
  type MusicTrack,
} from '../context/MusicPlayerContext';

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const totalSec = Math.floor(seconds);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

function formatFocusTrackTitle(track: MusicTrack): string {
  const rawSource = track.original_filename
    ? track.original_filename.replace(/\.[^/.]+$/, '')
    : track.title || 'Focus Track';
  const withoutTrailingId = rawSource.replace(/(?:[-_\s]+\d{4,8})+$/, '');
  const spaced = (withoutTrailingId || rawSource).replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (!spaced) return 'Focus Track';
  return spaced
    .split(' ')
    .map((word) => (word ? word.charAt(0).toUpperCase() + word.slice(1) : ''))
    .join(' ');
}

function getCategoryIcon(category: string) {
  switch (category) {
    case 'study_music':
      return <Music size={15} />;
    case 'deep_focus':
      return <Sparkles size={15} />;
    case 'focus_noise':
      return <Waves size={15} />;
    case 'nature_ambient':
      return <CloudRain size={15} />;
    default:
      return <Headphones size={15} />;
  }
}

export const MusicFocusSoundsSection: React.FC = () => {
  const {
    defaultTracks,
    uploadedTracks,
    allTracks,
    currentTrack,
    selectedCategory,
    isPlaying,
    isLoadingTrack,
    playbackError,
    volume,
    isMuted,
    currentTime,
    duration,
    isLooping,
    maxUploadBytes,
    maxUploadKb,
    storageNotice,
    uploading,
    uploadProgress,
    deletingTrackId,
    setCategory,
    selectTrack,
    togglePlay,
    nextTrack,
    prevTrack,
    seekTo,
    setVolume,
    toggleMute,
    toggleLoop,
    uploadTrack,
    cancelUpload,
    deleteTrack,
  } = useMusicPlayer();

  const [customTitle, setCustomTitle] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);
  const [confirmDeleteTrack, setConfirmDeleteTrack] = useState<MusicTrack | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const displayMaxMb =
    maxUploadKb % 1000 === 0 ? maxUploadKb / 1000 : Number((maxUploadKb / 1000).toFixed(1));
  const maxLimitLabel = `${maxUploadKb.toLocaleString()} KB (${displayMaxMb} MB)`;

  const handleConfirmDeleteSong = async () => {
    if (!confirmDeleteTrack || deletingTrackId) return;
    const ok = await deleteTrack(confirmDeleteTrack.id);
    if (ok) {
      setConfirmDeleteTrack(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    if (!file) {
      setFileValidationError(null);
      return;
    }
    const ext = file.name.includes('.')
      ? `.${file.name.split('.').pop()?.toLowerCase()}`
      : '';
    if (!['.mp3', '.wav', '.ogg'].includes(ext)) {
      setFileValidationError(
        'Unsupported audio format. Please select an MP3 (.mp3), WAV (.wav), or OGG (.ogg) file.'
      );
    } else if (file.size === 0) {
      setFileValidationError('Selected audio file is empty.');
    } else if (file.size > maxUploadBytes) {
      const fileKb = Math.ceil(file.size / 1024);
      setFileValidationError(
        `Selected file (${fileKb.toLocaleString()} KB) exceeds the ${maxLimitLabel} maximum upload limit.`
      );
    } else {
      setFileValidationError(null);
    }
    if (!customTitle.trim()) {
      const stem = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]+/g, ' ');
      setCustomTitle(stem.slice(0, 60));
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    const created = await uploadTrack(selectedFile, customTitle);
    if (created) {
      setSelectedFile(null);
      setFileValidationError(null);
      setCustomTitle('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const categoryTabs: Array<{ id: MusicCategoryFilter; label: string; count: number }> = [
    {
      id: 'all',
      label: 'All Libraries',
      count: allTracks.length,
    },
    {
      id: 'default',
      label: 'Default Music',
      count: defaultTracks.length,
    },
    {
      id: 'uploaded',
      label: 'Personal Library',
      count: uploadedTracks.length,
    },
  ];

  const effectiveDuration =
    duration > 0 ? duration : currentTrack?.duration_seconds || 12;
  const progressPercent =
    effectiveDuration > 0
      ? Math.min(100, Math.max(0, (currentTime / effectiveDuration) * 100))
      : 0;

  return (
    <section
      className="card mfs-section"
      aria-labelledby="music-focus-sounds-heading"
      data-testid="music-focus-sounds-section"
    >
      {/* Header Banner */}
      <div className="mfs-header">
        <div className="mfs-header-title-group">
          <div className="mfs-icon-badge" aria-hidden="true">
            <Headphones size={20} color="var(--accent-blue)" />
          </div>
          <div>
            <div className="mfs-eyebrow">PERSONAL AUDIO WORKSPACE</div>
            <h2 id="music-focus-sounds-heading" className="mfs-title">
              Music &amp; Focus Sounds
            </h2>
            <p className="mfs-subtitle">
              Your private personal music library. Upload your own MP3, WAV, or OGG tracks, play
              them across StudyOS navigation, or delete them anytime. Playback always remains off
              after a fresh page reload until you press Play.
            </p>
          </div>
        </div>

        <div
          className={`mfs-status-pill ${isPlaying ? 'is-playing' : 'is-paused'}`}
          data-testid="music-playback-status"
          role="status"
          aria-live="polite"
        >
          <span className="mfs-status-dot" />
          <span>{isPlaying ? 'Playing Across Workspace' : 'Music Off / Paused'}</span>
        </div>
      </div>

      {/* Master Transport & Now Playing Deck */}
      <div className="mfs-transport-deck" data-testid="music-transport-deck">
        <div className="mfs-now-playing-meta">
          <div className="mfs-now-playing-badge-row">
            <span className="mfs-cat-tag">
              {currentTrack ? currentTrack.category_label : 'Study Music'}
            </span>
            <span className="mfs-format-tag">
              {currentTrack ? currentTrack.file_format : 'WAV'}
            </span>
            {currentTrack && !currentTrack.is_builtin && (
              <span className="mfs-user-tag">User Upload</span>
            )}
          </div>
          <div className="mfs-now-playing-title" data-testid="music-current-title">
            {currentTrack
              ? currentTrack.is_builtin
                ? formatFocusTrackTitle(currentTrack)
                : currentTrack.title
              : 'Select a focus track'}
          </div>
          <div className="mfs-now-playing-subtitle">
            {currentTrack
              ? currentTrack.is_builtin
                ? 'Focus Music · Shared Library'
                : currentTrack.subtitle
              : 'Choose any track below and click Play to begin.'}
          </div>
        </div>

        {/* Transport Controls + Scrubber */}
        <div className="mfs-transport-center">
          <div className="mfs-transport-buttons">
            <button
              type="button"
              className="mfs-ctrl-btn"
              onClick={prevTrack}
              aria-label="Previous track"
              data-testid="music-prev-btn"
              title="Previous track"
            >
              <SkipBack size={17} />
            </button>

            <button
              type="button"
              className={`mfs-play-btn ${isPlaying ? 'active' : ''}`}
              onClick={togglePlay}
              disabled={isLoadingTrack || !currentTrack}
              aria-label={isPlaying ? 'Pause focus audio' : 'Play focus audio'}
              data-testid="music-play-toggle-btn"
            >
              {isLoadingTrack ? (
                <Loader2 size={18} className="mfs-spin" />
              ) : isPlaying ? (
                <>
                  <Pause size={17} />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play size={17} />
                  <span>Play</span>
                </>
              )}
            </button>

            <button
              type="button"
              className="mfs-ctrl-btn"
              onClick={nextTrack}
              aria-label="Next track"
              data-testid="music-next-btn"
              title="Next track"
            >
              <SkipForward size={17} />
            </button>

            <button
              type="button"
              className={`mfs-ctrl-btn ${isLooping ? 'is-active' : ''}`}
              onClick={toggleLoop}
              aria-label={isLooping ? 'Loop track enabled' : 'Loop track disabled'}
              aria-pressed={isLooping}
              data-testid="music-loop-btn"
              title={isLooping ? 'Seamless loop enabled' : 'Loop disabled'}
            >
              <Repeat size={15} />
            </button>
          </div>

          <div className="mfs-progress-row">
            <span className="mfs-time-label" data-testid="music-current-time">
              {formatTime(currentTime)}
            </span>
            <div className="mfs-slider-wrap">
              <input
                type="range"
                min={0}
                max={effectiveDuration}
                step={0.1}
                value={Math.min(currentTime, effectiveDuration)}
                onChange={(e) => seekTo( parseFloat(e.target.value) )}
                className="mfs-range-slider"
                aria-label="Track progress"
                data-testid="music-progress-slider"
                style={{
                  background: `linear-gradient(90deg, var(--accent-blue) ${progressPercent}%, var(--surface-3) ${progressPercent}%)`,
                }}
              />
            </div>
            <span className="mfs-time-label" data-testid="music-duration">
              {formatTime(effectiveDuration)}
            </span>
          </div>
        </div>

        {/* Volume Control */}
        <div className="mfs-volume-panel">
          <button
            type="button"
            className="mfs-ctrl-btn"
            onClick={toggleMute}
            aria-label={isMuted || volume === 0 ? 'Unmute audio' : 'Mute audio'}
            data-testid="music-mute-btn"
          >
            {isMuted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={isMuted ? 0 : volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="mfs-range-slider mfs-volume-slider"
            aria-label="Master volume"
            data-testid="music-volume-slider"
            style={{
              background: `linear-gradient(90deg, var(--accent-blue) ${
                (isMuted ? 0 : volume) * 100
              }%, var(--surface-3) ${(isMuted ? 0 : volume) * 100}%)`,
            }}
          />
          <span className="mfs-volume-pct" data-testid="music-volume-label">
            {Math.round((isMuted ? 0 : volume) * 100)}%
          </span>
        </div>
      </div>

      {playbackError && (
        <div className="mfs-error-banner" role="alert" data-testid="music-error-banner">
          <AlertCircle size={16} />
          <span>{playbackError}</span>
        </div>
      )}

      {/* Category Filter Tabs */}
      <div
        className="mfs-category-bar"
        role="tablist"
        aria-label="Focus sound categories"
        data-testid="music-category-tabs"
      >
        {categoryTabs.map((tab) => {
          const active = selectedCategory === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`mfs-cat-pill ${active ? 'active' : ''}`}
              onClick={() => setCategory(tab.id)}
              data-testid={`music-cat-${tab.id}`}
            >
              <span>{tab.label}</span>
              <span className="mfs-cat-count">{tab.count}</span>
            </button>
          );
        })}
      </div>

      {/* Sound Library Sections (Strict Separation: Default Music vs. Personal Library) */}
      {(() => {
        const showDefault = selectedCategory === 'all' || selectedCategory === 'default';
        const showPersonal = selectedCategory === 'all' || selectedCategory === 'uploaded';

        const renderTrackCard = (track: MusicTrack) => {
          const isSelected = currentTrack?.id === track.id;
          const isTrackPlaying = isSelected && isPlaying;
          return (
            <div
              key={track.id}
              className={`mfs-track-card ${isSelected ? 'is-selected' : ''} ${
                isTrackPlaying ? 'is-playing' : ''
              } ${track.is_builtin ? 'is-default-shared' : 'is-personal-private'}`}
              data-testid={`music-track-card-${track.id}`}
            >
              <div className="mfs-track-card-top">
                <div className="mfs-track-icon-wrap" aria-hidden="true">
                  {getCategoryIcon(track.category)}
                </div>
                <div className="mfs-track-badges">
                  <span className="mfs-badge-cat">
                    {track.is_builtin ? 'Shared · Read-Only' : 'Private'}
                  </span>
                  <span className="mfs-badge-fmt" data-testid={`music-track-format-${track.id}`}>
                    {track.file_format}
                  </span>
                </div>
              </div>

              <div className="mfs-track-body">
                <div className="mfs-track-title" data-testid={`music-track-title-${track.id}`}>
                  {track.title}
                </div>
                <div className="mfs-track-desc">
                  {track.original_filename ? `${track.original_filename} · ` : ''}
                  {track.subtitle}
                </div>
              </div>

              <div className="mfs-track-footer">
                <div className="mfs-track-duration">
                  {track.duration_seconds > 0 ? formatTime(track.duration_seconds) : 'MP3 Audio'}
                  {track.created_at
                    ? ` · ${new Date(track.created_at).toLocaleDateString()}`
                    : ''}
                </div>

                <div className="mfs-track-actions">
                  {!track.is_builtin && (
                    <button
                      type="button"
                      className="mfs-delete-btn"
                      onClick={() => setConfirmDeleteTrack(track)}
                      disabled={deletingTrackId === track.id}
                      aria-label={`Delete ${track.title}`}
                      data-testid={`music-delete-btn-${track.id}`}
                      title="Delete uploaded song"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                      <span>{deletingTrackId === track.id ? 'Deleting...' : 'Delete'}</span>
                    </button>
                  )}

                  <button
                    type="button"
                    className={`mfs-card-play-btn ${isTrackPlaying ? 'playing' : ''}`}
                    onClick={() => selectTrack(track.id, true)}
                    aria-label={isTrackPlaying ? `Pause ${track.title}` : `Play ${track.title}`}
                    data-testid={`music-card-play-${track.id}`}
                  >
                    {isTrackPlaying ? (
                      <>
                        <Pause size={14} />
                        <span>Pause</span>
                      </>
                    ) : (
                      <>
                        <Play size={14} />
                        <span>{isSelected ? 'Resume' : 'Play'}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        };

        const renderDefaultFocusCard = (track: MusicTrack) => {
          const isSelected = currentTrack?.id === track.id;
          const isTrackPlaying = isSelected && isPlaying;
          const displayTitle = formatFocusTrackTitle(track);

          return (
            <div
              key={track.id}
              className={`mfs-focus-card ${isSelected ? 'is-selected' : ''} ${
                isTrackPlaying ? 'is-playing' : ''
              }`}
              data-testid={`music-track-card-${track.id}`}
            >
              <div className="mfs-focus-card-left">
                <div
                  className={`mfs-focus-icon-wrap ${isTrackPlaying ? 'is-playing' : ''}`}
                  aria-hidden="true"
                >
                  {isTrackPlaying ? (
                    <span className="mfs-eq" aria-hidden="true">
                      <span className="mfs-eq-bar" />
                      <span className="mfs-eq-bar" />
                      <span className="mfs-eq-bar" />
                    </span>
                  ) : (
                    <Music size={17} />
                  )}
                </div>

                <div className="mfs-focus-meta">
                  <div
                    className="mfs-focus-title"
                    title={displayTitle}
                    data-testid={`music-track-title-${track.id}`}
                  >
                    {displayTitle}
                  </div>
                </div>
              </div>

              <button
                type="button"
                className={`mfs-focus-play-btn ${isTrackPlaying ? 'is-playing' : ''}`}
                onClick={() => selectTrack(track.id, true)}
                aria-label={isTrackPlaying ? `Pause ${displayTitle}` : `Play ${displayTitle}`}
                data-testid={`music-card-play-${track.id}`}
              >
                {isTrackPlaying ? <Pause size={15} /> : <Play size={15} />}
              </button>
            </div>
          );
        };

        return (
          <div className="mfs-libraries-stack" data-testid="music-tracks-grid">
            {showDefault && (
              <div
                className="mfs-library-group mfs-focus-library-group"
                data-testid="music-default-library-section"
              >
                <div className="mfs-library-group-header mfs-focus-header">
                  <div>
                    <h3 className="mfs-focus-heading">Focus Music</h3>
                    <p className="mfs-focus-subheading">Find your focus. Stay in flow.</p>
                  </div>
                  <div className="mfs-focus-header-pills">
                    <span className="mfs-shared-readonly-pill">Shared · Read-Only</span>
                    <span className="mfs-group-pill mfs-group-pill-gold">
                      {defaultTracks.length} {defaultTracks.length === 1 ? 'TRACK' : 'TRACKS'}
                    </span>
                  </div>
                </div>
                {defaultTracks.length === 0 ? (
                  <div className="mfs-empty-state" data-testid="music-default-empty-state">
                    <Headphones size={22} color="var(--text-muted)" />
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      No shared default MP3 tracks found
                    </div>
                    <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                      Place MP3 files inside <code>public/audio/</code> to make them
                      available to all users automatically.
                    </div>
                  </div>
                ) : (
                  <div className="mfs-focus-grid">{defaultTracks.map(renderDefaultFocusCard)}</div>
                )}
              </div>
            )}

            {showPersonal && (
              <div className="mfs-library-group" data-testid="music-personal-library-section">
                <div className="mfs-library-group-header">
                  <div>
                    <h3 className="mfs-library-group-title">Personal Library — Private to You</h3>
                    <p className="mfs-library-group-sub">
                      Authenticated tracks uploaded by your account. Never visible to other users.
                    </p>
                  </div>
                  <span className="mfs-group-pill mfs-group-pill-charcoal">
                    {uploadedTracks.length} {uploadedTracks.length === 1 ? 'Track' : 'Tracks'}
                  </span>
                </div>
                {uploadedTracks.length === 0 ? (
                  <div className="mfs-empty-state" data-testid="music-empty-state">
                    <Headphones size={24} color="var(--text-muted)" />
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      No personal tracks uploaded yet
                    </div>
                    <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                      Upload a personal MP3, WAV, or OGG focus track below.
                    </div>
                  </div>
                ) : (
                  <div className="mfs-tracks-grid">{uploadedTracks.map(renderTrackCard)}</div>
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* User Audio Upload & Personal Tracks Management */}
      <div className="mfs-upload-panel" data-testid="music-upload-panel">
        <div className="mfs-upload-header">
          <div>
            <h3 className="mfs-upload-title">
              <Upload size={16} color="var(--accent-blue)" />
              <span>Upload Custom Focus Audio</span>
            </h3>
            <p className="mfs-upload-desc">
              Add your own study tracks or ambient recordings (supported formats:{' '}
              <strong>MP3, WAV, OGG</strong> · max <strong>{maxLimitLabel}</strong> per file).
              Uploaded tracks are private to your account.
            </p>
          </div>
        </div>

        <form onSubmit={handleUploadSubmit} className="mfs-upload-form">
          <div className="mfs-upload-field">
            <label className="form-label" htmlFor="mfs-custom-title-input">
              Track Title (Optional)
            </label>
            <input
              id="mfs-custom-title-input"
              type="text"
              className="form-input"
              placeholder="e.g., Lo-Fi Study Session or Rainy Library"
              maxLength={80}
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              data-testid="music-upload-title-input"
            />
          </div>

          <div className="mfs-upload-field">
            <label className="form-label" htmlFor="mfs-audio-file-input">
              Audio File (.mp3, .wav, .ogg) — Max {maxLimitLabel}
            </label>
            <input
              ref={fileInputRef}
              id="mfs-audio-file-input"
              type="file"
              accept=".mp3,.wav,.ogg,audio/mpeg,audio/wav,audio/ogg"
              onChange={handleFileChange}
              className="form-input mfs-file-input"
              data-testid="music-upload-file-input"
            />
          </div>

          <div className="mfs-upload-submit-wrap" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!selectedFile || uploading || Boolean(fileValidationError)}
              data-testid="music-upload-submit-btn"
            >
              {uploading ? (
                <>
                  <Loader2 size={15} className="mfs-spin" />
                  <span>
                    {typeof uploadProgress === 'number'
                      ? `Uploading (${uploadProgress}%)...`
                      : 'Uploading...'}
                  </span>
                </>
              ) : (
                <>
                  <Upload size={15} />
                  <span>Upload Audio</span>
                </>
              )}
            </button>
            {uploading && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={cancelUpload}
                data-testid="music-upload-cancel-btn"
              >
                Cancel
              </button>
            )}
          </div>
        </form>

        {fileValidationError && (
          <div
            role="alert"
            data-testid="music-upload-validation-error"
            style={{
              marginTop: '10px',
              padding: '10px 12px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              color: '#fca5a5',
              fontSize: '0.88rem',
            }}
          >
            {fileValidationError}
          </div>
        )}

        {uploading && typeof uploadProgress === 'number' && (
          <div
            data-testid="music-upload-progress"
            style={{
              marginTop: '10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            <div
              style={{
                width: '100%',
                height: '6px',
                borderRadius: '999px',
                background: 'rgba(255,255,255,0.1)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, uploadProgress))}%`,
                  height: '100%',
                  background: 'var(--accent-blue)',
                  transition: 'width 180ms ease',
                }}
              />
            </div>
          </div>
        )}

        {/* Dedicated Uploaded Tracks List Summary */}
        {uploadedTracks.length > 0 && (
          <div className="mfs-uploaded-list" data-testid="music-uploaded-tracks-list">
            <div className="mfs-uploaded-list-header">
              <span>Your Uploaded Audio Tracks ({uploadedTracks.length})</span>
            </div>
            <div className="mfs-uploaded-rows">
              {uploadedTracks.map((ut) => {
                const isThisPlaying = currentTrack?.id === ut.id && isPlaying;
                return (
                  <div
                    key={ut.id}
                    className="mfs-uploaded-row"
                    data-testid={`music-uploaded-row-${ut.id}`}
                  >
                    <div className="mfs-uploaded-row-info">
                      <span className="mfs-uploaded-row-name">{ut.title}</span>
                      <span className="mfs-badge-fmt">{ut.file_format}</span>
                    </div>
                    <div className="mfs-uploaded-row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => selectTrack(ut.id, true)}
                        data-testid={`music-uploaded-play-${ut.id}`}
                      >
                        {isThisPlaying ? <Pause size={13} /> : <Play size={13} />}
                        <span>{isThisPlaying ? 'Pause' : 'Play'}</span>
                      </button>
                      <button
                        type="button"
                        className="mfs-delete-btn"
                        onClick={() => setConfirmDeleteTrack(ut)}
                        disabled={deletingTrackId === ut.id}
                        aria-label={`Delete uploaded track ${ut.title}`}
                        data-testid={`music-uploaded-delete-${ut.id}`}
                      >
                        <Trash2 size={13} aria-hidden="true" />
                        <span>{deletingTrackId === ut.id ? 'Deleting...' : 'Delete'}</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mfs-footnote">
          <CheckCircle2 size={14} color="var(--accent-blue)" style={{ flexShrink: 0 }} />
          <span>
            {storageNotice} Built-in tracks are original StudyOS procedural acoustic soundscapes
            (CC0 / royalty-free).
          </span>
        </div>
      </div>

      {/* Delete Uploaded Song Confirmation Dialog */}
      {confirmDeleteTrack && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!deletingTrackId) setConfirmDeleteTrack(null);
          }}
          data-testid="music-delete-confirm-backdrop"
        >
          <div
            className="modal-panel mfs-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mfs-delete-dialog-title"
            data-testid="music-delete-confirm-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mfs-confirm-header">
              <div className="mfs-confirm-icon-wrap" aria-hidden="true">
                <Trash2 size={18} />
              </div>
              <h3 id="mfs-delete-dialog-title" className="mfs-confirm-title">
                Delete this uploaded song?
              </h3>
            </div>

            <p className="mfs-confirm-body">
              This song will be permanently removed from your uploaded music library.
            </p>

            <div className="mfs-confirm-track-pill">
              <span className="mfs-confirm-track-name">{confirmDeleteTrack.title}</span>
              <span className="mfs-badge-fmt">{confirmDeleteTrack.file_format}</span>
            </div>

            <div className="mfs-confirm-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmDeleteTrack(null)}
                disabled={Boolean(deletingTrackId)}
                data-testid="music-delete-cancel-btn"
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDeleteSong}
                disabled={Boolean(deletingTrackId)}
                data-testid="music-delete-confirm-btn"
              >
                {deletingTrackId === confirmDeleteTrack.id ? (
                  <>
                    <Loader2 size={15} className="mfs-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={15} />
                    <span>Delete Song</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
