import React from 'react';
import { ExternalLink, Play, Shield } from 'lucide-react';
import { useFocus } from '../context/FocusContext';
import { getTutorialActionPolicy } from '../lib/youtubeEmbed';

interface YouTubeTutorialActionsProps {
  url?: string | null;
  videoId?: string | null;
  isInlineOpen?: boolean;
  onToggleInline?: () => void;
  showInlineToggle?: boolean;
  inlineLabelOpen?: string;
  inlineLabelClosed?: string;
}

export const YouTubeTutorialActions: React.FC<YouTubeTutorialActionsProps> = ({
  url,
  videoId,
  isInlineOpen = false,
  onToggleInline,
  showInlineToggle = true,
  inlineLabelOpen = 'Hide Inline Player',
  inlineLabelClosed = 'Play Inline Here',
}) => {
  const { phase, activeSession, isReconciling } = useFocus();

  const policy = getTutorialActionPolicy({
    focusPhase: phase,
    hasActiveSession: Boolean(activeSession),
    isReconciling,
    url,
    videoId,
  });

  return (
    <>
      {policy.allowExternalWatch && policy.externalWatchUrl && (
        <a
          href={policy.externalWatchUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary btn-sm"
          data-testid="watch-on-youtube-link"
        >
          <ExternalLink size={14} aria-hidden="true" />
          <span>Watch on YouTube</span>
        </a>
      )}

      {showInlineToggle && onToggleInline && (
        <button
          type="button"
          className={`btn ${policy.isRestrictedByFocus ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={onToggleInline}
          data-testid="play-inline-btn"
        >
          <Play size={14} aria-hidden="true" />
          <span>{isInlineOpen ? inlineLabelOpen : inlineLabelClosed}</span>
        </button>
      )}

      {policy.isRestrictedByFocus && (
        <span
          className="badge badge-indigo"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          data-testid="focus-inline-only-badge"
        >
          <Shield size={12} aria-hidden="true" />
          <span>
            {policy.isCheckingFocus
              ? 'Checking Focus session...'
              : 'Focus Mode: Inline playback only'}
          </span>
        </span>
      )}
    </>
  );
};

