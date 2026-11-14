import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Loader2, Shield } from 'lucide-react';
import {
  resolveYouTubeEmbed,
  YOUTUBE_EMBED_ALLOW,
  YOUTUBE_EMBED_SANDBOX,
} from '../lib/youtubeEmbed';

interface InlineYouTubePlayerProps {
  url?: string | null;
  videoId?: string | null;
  title: string;
  maxWidth?: number | string;
}

export const InlineYouTubePlayer: React.FC<InlineYouTubePlayerProps> = ({
  url,
  videoId,
  title,
  maxWidth,
}) => {
  const resolution = useMemo(
    () => resolveYouTubeEmbed({ url, videoId }),
    [url, videoId]
  );

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasLoadError, setHasLoadError] = useState<boolean>(false);

  const embedSrc = resolution.valid ? resolution.embedUrl : '';

  useEffect(() => {
    setIsLoading(true);
    setHasLoadError(false);
  }, [embedSrc]);

  if (!resolution.valid || hasLoadError) {
    return (
      <div
        className="yt-inline-shell yt-inline-unavailable"
        style={maxWidth ? { maxWidth } : undefined}
        role="status"
        data-testid="inline-youtube-unavailable"
      >
        <div className="yt-inline-unavailable-inner">
          <AlertCircle size={28} className="yt-inline-error-icon" aria-hidden="true" />
          <div className="yt-inline-unavailable-title">Video Unavailable for Inline Playback</div>
          <p className="yt-inline-unavailable-desc">
            {!resolution.valid
              ? resolution.reason
              : 'This video could not be embedded. Its owner may have disabled embedding or the video may be unavailable.'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="yt-inline-wrapper"
      style={maxWidth ? { maxWidth } : undefined}
      data-testid="inline-youtube-player"
    >
      <div className="yt-inline-shell">
        {isLoading && (
          <div className="yt-inline-loading" aria-live="polite" data-testid="inline-youtube-loading">
            <Loader2 size={24} className="yt-inline-spinner" aria-hidden="true" />
            <span>Loading tutorial video...</span>
          </div>
        )}
        <iframe
          src={resolution.embedUrl}
          title={title || 'BRAINOVA Tutorial Video'}
          className="yt-inline-iframe"
          sandbox={YOUTUBE_EMBED_SANDBOX}
          allow={YOUTUBE_EMBED_ALLOW}
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
          loading="lazy"
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setHasLoadError(true);
          }}
        />
      </div>
      <div className="yt-inline-guard-bar">
        <Shield size={13} aria-hidden="true" />
        <span>Inline BRAINOVA playback · External navigation &amp; popups restricted</span>
      </div>
    </div>
  );
};
