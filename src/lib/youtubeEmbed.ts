const YOUTUBE_VIDEO_ID_RE = /^[a-zA-Z0-9_-]{11}$/;

export const YOUTUBE_EMBED_SANDBOX =
  'allow-scripts allow-same-origin allow-presentation';

export const YOUTUBE_EMBED_ALLOW =
  'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen';

const ALLOWED_YOUTUBE_HOSTS = new Set([
  'youtube.com',
  'www.youtube.com',
  'm.youtube.com',
  'youtu.be',
  'youtube-nocookie.com',
  'www.youtube-nocookie.com',
]);

export type YouTubeEmbedResolution =
  | {
      valid: true;
      videoId: string;
      embedUrl: string;
    }
  | {
      valid: false;
      reason: string;
    };

/**
 * Validates a raw 11-character YouTube video ID.
 */
export function isValidYouTubeVideoId(videoId: string | null | undefined): boolean {
  if (!videoId || typeof videoId !== 'string') return false;
  return YOUTUBE_VIDEO_ID_RE.test(videoId.trim());
}

/**
 * Strictly parses a YouTube URL and extracts a validated 11-character video ID.
 * Rejects non-HTTP(S) protocols (javascript:, data:, etc.), untrusted hosts,
 * malformed URLs, and invalid video IDs.
 */
export function extractYouTubeVideoId(rawUrl: string | null | undefined): string | null {
  if (!rawUrl || typeof rawUrl !== 'string') return null;
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }

  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return null;
  }

  const host = parsed.hostname.toLowerCase();
  if (!ALLOWED_YOUTUBE_HOSTS.has(host)) {
    return null;
  }

  let candidateId: string | null = null;
  const segments = parsed.pathname.split('/').filter(Boolean);

  if (host === 'youtu.be') {
    candidateId = segments[0] ?? null;
  } else if (parsed.pathname === '/watch' || parsed.pathname === '/watch/') {
    candidateId = parsed.searchParams.get('v');
  } else if (
    segments.length >= 2 &&
    (segments[0] === 'embed' || segments[0] === 'shorts' || segments[0] === 'live')
  ) {
    candidateId = segments[1];
  }

  if (!candidateId) return null;
  const cleaned = candidateId.trim();
  return isValidYouTubeVideoId(cleaned) ? cleaned : null;
}

/**
 * Resolves a validated privacy-enhanced YouTube embed URL (`youtube-nocookie.com`)
 * from a tutorial URL and/or stored video ID.
 * If `url` is provided and non-empty, it must pass strict YouTube URL validation.
 */
export function resolveYouTubeEmbed(input: {
  url?: string | null;
  videoId?: string | null;
}): YouTubeEmbedResolution {
  const rawUrl = typeof input.url === 'string' ? input.url.trim() : '';
  const rawVideoId = typeof input.videoId === 'string' ? input.videoId.trim() : '';

  let validatedId: string | null = null;

  if (rawUrl) {
    validatedId = extractYouTubeVideoId(rawUrl);
    if (!validatedId) {
      return {
        valid: false,
        reason: 'This tutorial URL is not a valid or supported YouTube video link.',
      };
    }
  } else if (rawVideoId) {
    if (!isValidYouTubeVideoId(rawVideoId)) {
      return {
        valid: false,
        reason: 'The tutorial video identifier is invalid.',
      };
    }
    validatedId = rawVideoId;
  } else {
    return {
      valid: false,
      reason: 'No playable YouTube tutorial video is attached.',
    };
  }

  return {
    valid: true,
    videoId: validatedId,
    embedUrl: `https://www.youtube-nocookie.com/embed/${validatedId}?rel=0&modestbranding=1&playsinline=1`,
  };
}

/**
 * Validates an external YouTube URL for safe "Watch on YouTube" links.
 * Returns null for untrusted domains, javascript:/data: URLs, malformed URLs,
 * or invalid video IDs. If `rawUrl` is provided and invalid, never falls back to `videoId`.
 */
export function validateExternalYouTubeUrl(
  rawUrl?: string | null,
  rawVideoId?: string | null
): string | null {
  const trimmedUrl = typeof rawUrl === 'string' ? rawUrl.trim() : '';
  const trimmedId = typeof rawVideoId === 'string' ? rawVideoId.trim() : '';

  if (trimmedUrl) {
    const validId = extractYouTubeVideoId(trimmedUrl);
    if (!validId) return null;
    try {
      const parsed = new URL(trimmedUrl);
      if (parsed.protocol === 'http:') {
        parsed.protocol = 'https:';
      }
      return parsed.toString();
    } catch {
      return null;
    }
  }

  if (trimmedId && isValidYouTubeVideoId(trimmedId)) {
    return `https://www.youtube.com/watch?v=${trimmedId}`;
  }

  return null;
}

export interface TutorialActionPolicy {
  allowExternalWatch: boolean;
  externalWatchUrl: string | null;
  isFocusActive: boolean;
  isCheckingFocus: boolean;
  isRestrictedByFocus: boolean;
}

/**
 * Computes the authoritative Roadmap tutorial action policy from FocusContext state.
 * - While Focus Mode is active (`active` / `activating` / `hasActiveSession`) OR recovering (`isReconciling`),
 *   external "Watch on YouTube" navigation is hidden/disabled.
 * - Immediately when Focus Mode ends (`idle` / `completed` with no active session and not reconciling),
 *   both "Watch on YouTube" (for valid URLs) and "Play Inline Here" are available.
 */
export function getTutorialActionPolicy(input: {
  focusPhase: 'idle' | 'activating' | 'active' | 'completed';
  hasActiveSession: boolean;
  isReconciling: boolean;
  url?: string | null;
  videoId?: string | null;
}): TutorialActionPolicy {
  const isFocusActive =
    input.focusPhase === 'active' ||
    input.focusPhase === 'activating' ||
    input.hasActiveSession;
  const isCheckingFocus = input.isReconciling && !isFocusActive;
  const isRestrictedByFocus = isFocusActive || isCheckingFocus;
  const externalWatchUrl = validateExternalYouTubeUrl(input.url, input.videoId);

  return {
    allowExternalWatch: !isRestrictedByFocus && Boolean(externalWatchUrl),
    externalWatchUrl,
    isFocusActive,
    isCheckingFocus,
    isRestrictedByFocus,
  };
}
