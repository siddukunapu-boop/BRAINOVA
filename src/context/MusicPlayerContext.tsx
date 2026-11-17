import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { apiRequest, getStoredToken, resolveApiUrl } from '../services/api';
import { useApp } from './AppContext';

export type MusicCategoryFilter =
  | 'all'
  | 'default'
  | 'study_music'
  | 'deep_focus'
  | 'focus_noise'
  | 'nature_ambient'
  | 'uploaded';

export interface MusicCategoryInfo {
  id: string;
  name: string;
  description: string;
}

export interface MusicTrack {
  id: string;
  title: string;
  original_filename?: string;
  subtitle: string;
  category: string;
  category_label: string;
  source_type?: 'default' | 'personal';
  read_only?: boolean;
  file_format: string;
  mime_type: string;
  file_size?: number;
  duration_seconds: number;
  is_builtin: boolean;
  stream_url: string;
  api_stream_url?: string;
  license?: string;
  created_at?: string;
}

export interface MusicPlayerContextValue {
  categories: MusicCategoryInfo[];
  defaultTracks: MusicTrack[];
  builtinTracks: MusicTrack[];
  uploadedTracks: MusicTrack[];
  allTracks: MusicTrack[];
  filteredTracks: MusicTrack[];
  currentTrack: MusicTrack | null;
  selectedCategory: MusicCategoryFilter;
  isPlaying: boolean;
  isLoadingTrack: boolean;
  playbackError: string | null;
  volume: number;
  isMuted: boolean;
  currentTime: number;
  duration: number;
  isLooping: boolean;
  maxUploadBytes: number;
  maxUploadKb: number;
  maxUploadMb: number;
  storageNotice: string;
  uploading: boolean;
  uploadProgress: number | null;
  deletingTrackId: string | null;
  setCategory: (category: MusicCategoryFilter) => void;
  selectTrack: (trackId: string, autoPlay?: boolean) => Promise<void>;
  play: () => Promise<void>;
  pause: () => void;
  togglePlay: () => Promise<void>;
  nextTrack: () => Promise<void>;
  prevTrack: () => Promise<void>;
  seekTo: (seconds: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  toggleLoop: () => void;
  uploadTrack: (file: File, customTitle?: string) => Promise<MusicTrack | null>;
  cancelUpload: () => void;
  deleteTrack: (trackId: string) => Promise<boolean>;
  refreshLibrary: () => Promise<void>;
}

export const INITIAL_CATEGORIES: MusicCategoryInfo[] = [
  {
    id: 'uploaded',
    name: 'Personal Music Library',
    description: 'Your private uploaded MP3, WAV, and OGG audio tracks.',
  },
];

export const INITIAL_BUILTIN_TRACKS: MusicTrack[] = [];

function synthesizeClientFallbackWavBlob(trackId: string, durationSec = 10): Blob {
  const sampleRate = 16000;
  const numSamples = Math.floor(sampleRate * durationSec);
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, numSamples * 2, true);

  let seed = 1337;
  for (let i = 0; i < trackId.length; i += 1) {
    seed = (seed * 31 + trackId.charCodeAt(i)) >>> 0;
  }
  const nextRand = () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return (seed / 0xffffffff) * 2 - 1;
  };

  let lp = 0;
  let b0 = 0;
  let b1 = 0;
  let b2 = 0;
  const twoPi = 2 * Math.PI;

  for (let i = 0; i < numSamples; i += 1) {
    const t = i / sampleRate;
    const env =
      t < 0.25
        ? 0.5 * (1 - Math.cos(Math.PI * (t / 0.25)))
        : t > durationSec - 0.25
        ? 0.5 * (1 - Math.cos(Math.PI * ((durationSec - t) / 0.25)))
        : 1.0;

    let sample = 0;
    if (trackId.includes('noise_brown')) {
      lp = (lp + 0.035 * nextRand()) * 0.992;
      sample = Math.max(-0.9, Math.min(0.9, lp * 1.4)) * 0.5;
    } else if (trackId.includes('noise_white')) {
      lp = 0.65 * lp + 0.35 * nextRand();
      sample = lp * 0.34;
    } else if (trackId.includes('noise_pink')) {
      const w = nextRand();
      b0 = 0.99765 * b0 + w * 0.099046;
      b1 = 0.963 * b1 + w * 0.2965164;
      b2 = 0.57 * b2 + w * 1.0526913;
      sample = Math.max(-0.9, Math.min(0.9, (b0 + b1 + b2 + w * 0.1848) * 0.14)) * 0.45;
    } else if (trackId.includes('nature_')) {
      const w = nextRand();
      lp = 0.94 * lp + 0.06 * w;
      const swell = 0.5 + 0.5 * Math.sin(twoPi * (t / 5.0));
      sample = (lp * 0.65 * swell + 0.12 * Math.sin(twoPi * 174.61 * t)) * 0.5;
    } else if (trackId.includes('focus_')) {
      sample =
        (0.42 * Math.sin(twoPi * 110 * t) +
          0.28 * Math.sin(twoPi * 165 * t) +
          0.18 * Math.sin(twoPi * 220.5 * t)) *
        0.5;
    } else {
      sample =
        (0.28 * Math.sin(twoPi * 174.61 * t) +
          0.24 * Math.sin(twoPi * 220.0 * t) +
          0.2 * Math.sin(twoPi * 261.63 * t) +
          0.16 * Math.sin(twoPi * 329.63 * t)) *
        0.5;
    }

    const pcm = Math.max(-32767, Math.min(32767, Math.floor(sample * env * 32767)));
    view.setInt16(44 + i * 2, pcm, true);
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

const VALID_CATEGORIES: MusicCategoryFilter[] = [
  'all',
  'study_music',
  'deep_focus',
  'focus_noise',
  'nature_ambient',
  'uploaded',
];

function isValidCategoryFilter(val: unknown): val is MusicCategoryFilter {
  return typeof val === 'string' && VALID_CATEGORIES.includes(val as MusicCategoryFilter);
}

const MusicPlayerContext = createContext<MusicPlayerContextValue | undefined>(undefined);

export const MusicPlayerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, addToast } = useApp();

  const [categories, setCategories] = useState<MusicCategoryInfo[]>(INITIAL_CATEGORIES);
  const [builtinTracks, setBuiltinTracks] = useState<MusicTrack[]>(INITIAL_BUILTIN_TRACKS);
  const [uploadedTracks, setUploadedTracks] = useState<MusicTrack[]>([]);
  const [selectedCategory, setSelectedCategoryState] = useState<MusicCategoryFilter>('all');
  const [currentTrackId, setCurrentTrackId] = useState<string>('builtin_study_gentle');

  // CRITICAL REQUIREMENT: Playback MUST be OFF by default and after any full page reload or new session.
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isLoadingTrack, setIsLoadingTrack] = useState<boolean>(false);
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [volume, setVolumeState] = useState<number>(0.65);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(12);
  const [isLooping, setIsLooping] = useState<boolean>(true);
  const [maxUploadBytes, setMaxUploadBytes] = useState<number>(40000 * 1024);
  const [maxUploadKb, setMaxUploadKb] = useState<number>(40000);
  const [maxUploadMb, setMaxUploadMb] = useState<number>(40);
  const [chunkSizeBytes, setChunkSizeBytes] = useState<number>(2 * 1024 * 1024);
  const [storageNotice, setStorageNotice] = useState<string>(
    'Uploaded audio files are stored in authenticated per-user storage.'
  );
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [deletingTrackId, setDeletingTrackId] = useState<string | null>(null);

  // Persistent single Audio instance at root level — never destroyed on route navigation
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const activeObjectUrlRef = useRef<string | null>(null);
  const loadedTrackIdRef = useRef<string | null>(null);
  const savedResumePositionRef = useRef<number>(0);
  const syncTimeoutRef = useRef<number | null>(null);
  const deletingInFlightRef = useRef<Set<string>>(new Set());
  const uploadAbortRef = useRef<AbortController | null>(null);
  const activeUploadIdRef = useRef<string | null>(null);
  const volumeRef = useRef<number>(0.65);
  const isMutedRef = useRef<boolean>(false);
  const isLoopingRef = useRef<boolean>(true);

  const localPrefKey = useMemo(
    () => (user?.id ? `brainova_music_prefs_${user.id}` : null),
    [user?.id]
  );

  const allTracks = useMemo(
    () => [...builtinTracks, ...uploadedTracks],
    [builtinTracks, uploadedTracks]
  );

  const filteredTracks = useMemo(() => {
    if (selectedCategory === 'all') {
      return allTracks;
    }
    return allTracks.filter((t) => t.category === selectedCategory);
  }, [allTracks, selectedCategory]);

  const currentTrack = useMemo(() => {
    return (
      allTracks.find((t) => t.id === currentTrackId) ||
      builtinTracks[0] ||
      null
    );
  }, [allTracks, builtinTracks, currentTrackId]);

  const revokeActiveObjectUrl = useCallback(() => {
    if (activeObjectUrlRef.current) {
      try {
        URL.revokeObjectURL(activeObjectUrlRef.current);
      } catch {
        // ignore revoke error
      }
      activeObjectUrlRef.current = null;
    }
  }, []);

  const persistPreferences = useCallback(
    (patch: {
      music_last_track_id?: string;
      music_last_category?: string;
      music_volume?: number;
      music_playback_enabled?: boolean;
      music_last_position?: number;
    }) => {
      if (localPrefKey) {
        try {
          const existingRaw = localStorage.getItem(localPrefKey);
          const existing = existingRaw ? JSON.parse(existingRaw) : {};
          const merged = { ...existing, ...patch };
          localStorage.setItem(localPrefKey, JSON.stringify(merged));
        } catch {
          // ignore localStorage errors
        }
      }

      if (!getStoredToken()) return;

      if (syncTimeoutRef.current) {
        window.clearTimeout(syncTimeoutRef.current);
      }
      syncTimeoutRef.current = window.setTimeout(() => {
        apiRequest('/api/music/preferences', {
          method: 'PUT',
          body: JSON.stringify(patch),
        }).catch(() => {
          // Non-fatal if offline
        });
      }, 350);
    },
    [localPrefKey]
  );

  // Initialize the single persistent HTMLAudioElement once
  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.loop = isLoopingRef.current;
    audio.volume = isMutedRef.current ? 0 : volumeRef.current;
    audioRef.current = audio;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime || 0);
    };

    const handleLoadedMetadata = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        setDuration(audio.duration);
      }
      if (savedResumePositionRef.current > 0) {
        const targetPos = savedResumePositionRef.current;
        savedResumePositionRef.current = 0;
        if (
          Number.isFinite(audio.duration) &&
          targetPos < audio.duration - 0.5
        ) {
          try {
            audio.currentTime = targetPos;
            setCurrentTime(targetPos);
          } catch {
            // ignore seek error prior to buffered range
          }
        }
      }
    };

    const handlePlay = () => {
      setIsPlaying(true);
      setPlaybackError(null);
    };

    const handlePause = () => {
      setIsPlaying(false);
    };

    const handleEnded = () => {
      if (!audio.loop) {
        setIsPlaying(false);
        setCurrentTime(0);
      }
    };

    const handleError = () => {
      setIsPlaying(false);
      setIsLoadingTrack(false);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      if (syncTimeoutRef.current) {
        window.clearTimeout(syncTimeoutRef.current);
      }
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
      audioRef.current = null;
      revokeActiveObjectUrl();
    };
  }, [revokeActiveObjectUrl]);

  // Load user's library & saved preferences on login, keeping playback strictly OFF
  const refreshLibrary = useCallback(async () => {
    if (!user?.id || !getStoredToken()) {
      return;
    }

    // Read local cached preferences first (never auto-start playback)
    let localPrefs: Record<string, any> = {};
    if (localPrefKey) {
      try {
        const raw = localStorage.getItem(localPrefKey);
        if (raw) {
          localPrefs = JSON.parse(raw);
        }
      } catch {
        localPrefs = {};
      }
    }

    try {
      const res = await apiRequest<{
        categories: MusicCategoryInfo[];
        default_tracks?: MusicTrack[];
        builtin_tracks: MusicTrack[];
        uploaded_tracks: MusicTrack[];
        max_upload_bytes?: number;
        max_upload_kb?: number;
        max_upload_mb: number;
        chunk_size_bytes?: number;
        storage_notice: string;
        preferences?: {
          music_last_track_id?: string;
          music_last_category?: string;
          music_volume?: number;
          music_playback_enabled?: boolean;
          music_last_position?: number;
        };
      }>('/api/music/tracks');

      if (Array.isArray(res.categories) && res.categories.length > 0) {
        setCategories(res.categories);
      }
      const rawDefaults = Array.isArray(res.default_tracks)
        ? res.default_tracks
        : Array.isArray(res.builtin_tracks)
          ? res.builtin_tracks
          : [];
      const nextBuiltin =
        rawDefaults.length > 0 ? rawDefaults : INITIAL_BUILTIN_TRACKS;
      const nextUploaded = Array.isArray(res.uploaded_tracks) ? res.uploaded_tracks : [];

      setBuiltinTracks(nextBuiltin);
      setUploadedTracks(nextUploaded);
      if (typeof res.max_upload_bytes === 'number' && res.max_upload_bytes > 0) {
        setMaxUploadBytes(res.max_upload_bytes);
      }
      if (typeof res.max_upload_kb === 'number' && res.max_upload_kb > 0) {
        setMaxUploadKb(res.max_upload_kb);
      }
      if (typeof res.max_upload_mb === 'number' && res.max_upload_mb > 0) {
        setMaxUploadMb(res.max_upload_mb);
      }
      if (typeof res.chunk_size_bytes === 'number' && res.chunk_size_bytes > 0) {
        setChunkSizeBytes(res.chunk_size_bytes);
      }
      if (res.storage_notice) {
        setStorageNotice(res.storage_notice);
      }

      const srvPrefs = res.preferences || {};
      const combinedAll = [...nextBuiltin, ...nextUploaded];

      const preferredTrackId =
        localPrefs.music_last_track_id ||
        srvPrefs.music_last_track_id ||
        user?.preferences?.music_last_track_id ||
        'builtin_study_gentle';
      const resolvedTrack =
        combinedAll.find((t) => t.id === preferredTrackId) || nextBuiltin[0];

      if (resolvedTrack && !audioRef.current?.src) {
        setCurrentTrackId(resolvedTrack.id);
        setDuration(resolvedTrack.duration_seconds || 12);
      }

      const preferredCat =
        localPrefs.music_last_category ||
        srvPrefs.music_last_category ||
        user?.preferences?.music_last_category ||
        'all';
      if (isValidCategoryFilter(preferredCat) && !audioRef.current?.src) {
        setSelectedCategoryState(preferredCat);
      }

      const rawVol =
        typeof localPrefs.music_volume === 'number'
          ? localPrefs.music_volume
          : typeof srvPrefs.music_volume === 'number'
          ? srvPrefs.music_volume
          : typeof user?.preferences?.music_volume === 'number'
          ? user.preferences.music_volume
          : 0.65;
      const clampedVol = Math.max(0, Math.min(1, rawVol));
      if (!audioRef.current?.src) {
        volumeRef.current = clampedVol;
        setVolumeState(clampedVol);
        if (audioRef.current) {
          audioRef.current.volume = isMutedRef.current ? 0 : clampedVol;
        }
      }

      const savedPos =
        typeof localPrefs.music_last_position === 'number'
          ? localPrefs.music_last_position
          : typeof srvPrefs.music_last_position === 'number'
          ? srvPrefs.music_last_position
          : 0;
      if (savedPos > 0 && !audioRef.current?.src) {
        savedResumePositionRef.current = savedPos;
        setCurrentTime(savedPos);
      }
    } catch {
      // Keep built-in defaults if offline
    }
  }, [localPrefKey, user?.id, user?.preferences]);

  useEffect(() => {
    if (!user?.id) {
      // User logged out: stop playback and clean up audio resources immediately
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.removeAttribute('src');
        audioRef.current.load();
      }
      loadedTrackIdRef.current = null;
      revokeActiveObjectUrl();
      setIsPlaying(false);
      setCurrentTime(0);
      setUploadedTracks([]);
      return;
    }
    refreshLibrary();
  }, [refreshLibrary, revokeActiveObjectUrl, user?.id]);

  const loadTrackIntoAudioElement = useCallback(
    async (track: MusicTrack): Promise<boolean> => {
      const audio = audioRef.current;
      if (!audio) return false;

      if (loadedTrackIdRef.current === track.id && audio.src) {
        return true;
      }

      setIsLoadingTrack(true);
      setPlaybackError(null);

      // Stop any previous track before loading new source
      audio.pause();
      revokeActiveObjectUrl();

      // Shared static default MP3s (/audio/*) stream natively with full HTTP Range seeking
      if (track.is_builtin && track.stream_url.startsWith('/audio/')) {
        loadedTrackIdRef.current = track.id;
        audio.src = resolveApiUrl(track.stream_url);
        audio.loop = isLoopingRef.current;
        audio.volume = isMutedRef.current ? 0 : volumeRef.current;
        if (track.duration_seconds > 0) {
          setDuration(track.duration_seconds);
        }
        audio.load();
        setIsLoadingTrack(false);
        return true;
      }

      const token = getStoredToken();
      let blob: Blob | null = null;

      try {
        const headers: Record<string, string> = {};
        if (token) {
          headers.Authorization = `Bearer ${token}`;
        }
        const streamUrl = resolveApiUrl(track.stream_url);
        const rangeLimit = 2 * 1024 * 1024;
        const trackFileSize = track.file_size ?? 0;
        if (!track.is_builtin && trackFileSize > rangeLimit) {
          const parts: Blob[] = [];
          let offset = 0;
          while (offset < trackFileSize) {
            const end = Math.min(trackFileSize - 1, offset + rangeLimit - 1);
            const rangeResp = await fetch(streamUrl, {
              headers: {
                ...headers,
                Range: `bytes=${offset}-${end}`,
              },
            });
            if (!rangeResp.ok) {
              let errMsg = `Unable to load audio track (${rangeResp.status}).`;
              try {
                const errJson = await rangeResp.json();
                if (errJson?.detail) {
                  errMsg = String(errJson.detail);
                }
              } catch {
                // ignore json parse failure
              }
              setPlaybackError(errMsg);
              setIsLoadingTrack(false);
              return false;
            }
            const partBlob = await rangeResp.blob();
            if (partBlob.size === 0) break;
            parts.push(partBlob);
            offset += partBlob.size;
            if (rangeResp.status === 200) {
              break;
            }
          }
          blob = new Blob(parts, { type: track.mime_type || 'audio/mpeg' });
        } else {
          const response = await fetch(streamUrl, { headers });
          if (!response.ok) {
            let errMsg = `Unable to load audio track (${response.status}).`;
            try {
              const errJson = await response.json();
              if (errJson?.detail) {
                errMsg = String(errJson.detail);
              }
            } catch {
              // ignore json parse failure
            }
            if (!track.is_builtin) {
              setPlaybackError(errMsg);
              setIsLoadingTrack(false);
              return false;
            }
          } else {
            blob = await response.blob();
          }
        }
      } catch {
        if (!track.is_builtin) {
          setPlaybackError('Network error while loading uploaded audio track.');
          setIsLoadingTrack(false);
          return false;
        }
      }

      if (!blob && track.is_builtin) {
        blob = synthesizeClientFallbackWavBlob(track.id, track.duration_seconds || 10);
      }

      if (!blob) {
        setIsLoadingTrack(false);
        return false;
      }

      const objectUrl = URL.createObjectURL(blob);
      activeObjectUrlRef.current = objectUrl;
      loadedTrackIdRef.current = track.id;
      audio.src = objectUrl;
      audio.loop = isLoopingRef.current;
      audio.volume = isMutedRef.current ? 0 : volumeRef.current;
      if (track.duration_seconds > 0) {
        setDuration(track.duration_seconds);
      }
      audio.load();
      setIsLoadingTrack(false);
      return true;
    },
    [revokeActiveObjectUrl]
  );

  const play = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio || !currentTrack) return;

    const ready = await loadTrackIntoAudioElement(currentTrack);
    if (!ready) return;

    try {
      await audio.play();
      setIsPlaying(true);
      persistPreferences({
        music_last_track_id: currentTrack.id,
        music_playback_enabled: true,
      });
    } catch (err: any) {
      setIsPlaying(false);
      setPlaybackError(
        err?.message || 'Playback could not start. Click Play again to start audio.'
      );
    }
  }, [currentTrack, loadTrackIntoAudioElement, persistPreferences]);

  const pause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    setIsPlaying(false);
    persistPreferences({
      music_playback_enabled: false,
      music_last_position: Math.round((audio.currentTime || 0) * 10) / 10,
    });
  }, [persistPreferences]);

  const togglePlay = useCallback(async () => {
    if (isPlaying) {
      pause();
    } else {
      await play();
    }
  }, [isPlaying, pause, play]);

  const selectTrack = useCallback(
    async (trackId: string, autoPlay = true) => {
      const target = allTracks.find((t) => t.id === trackId);
      if (!target) return;

      const audio = audioRef.current;
      if (audio && loadedTrackIdRef.current === trackId && autoPlay) {
        if (audio.paused) {
          await play();
        } else {
          pause();
        }
        return;
      }

      if (audio) {
        audio.pause();
        setCurrentTime(0);
      }
      savedResumePositionRef.current = 0;
      setCurrentTrackId(target.id);
      setDuration(target.duration_seconds || 12);
      persistPreferences({
        music_last_track_id: target.id,
        music_last_position: 0,
        music_playback_enabled: autoPlay,
      });

      if (autoPlay) {
        const ready = await loadTrackIntoAudioElement(target);
        if (ready && audioRef.current) {
          try {
            await audioRef.current.play();
            setIsPlaying(true);
          } catch {
            setIsPlaying(false);
          }
        }
      } else {
        setIsPlaying(false);
      }
    },
    [allTracks, loadTrackIntoAudioElement, pause, persistPreferences, play]
  );

  const nextTrack = useCallback(async () => {
    const list = filteredTracks.length > 0 ? filteredTracks : allTracks;
    if (list.length === 0) return;
    const idx = list.findIndex((t) => t.id === currentTrack?.id);
    const nextIdx = idx >= 0 ? (idx + 1) % list.length : 0;
    await selectTrack(list[nextIdx].id, isPlaying);
  }, [allTracks, currentTrack?.id, filteredTracks, isPlaying, selectTrack]);

  const prevTrack = useCallback(async () => {
    const list = filteredTracks.length > 0 ? filteredTracks : allTracks;
    if (list.length === 0) return;
    const idx = list.findIndex((t) => t.id === currentTrack?.id);
    const prevIdx = idx > 0 ? idx - 1 : list.length - 1;
    await selectTrack(list[prevIdx].id, isPlaying);
  }, [allTracks, currentTrack?.id, filteredTracks, isPlaying, selectTrack]);

  const seekTo = useCallback(
    (seconds: number) => {
      const clamped = Math.max(0, Math.min(duration || 0, seconds));
      setCurrentTime(clamped);
      if (audioRef.current && audioRef.current.src) {
        try {
          audioRef.current.currentTime = clamped;
        } catch {
          // ignore if unbuffered
        }
      } else {
        savedResumePositionRef.current = clamped;
      }
      persistPreferences({
        music_last_position: Math.round(clamped * 10) / 10,
      });
    },
    [duration, persistPreferences]
  );

  const setVolume = useCallback(
    (nextVol: number) => {
      const clamped = Math.max(0, Math.min(1, nextVol));
      volumeRef.current = clamped;
      setVolumeState(clamped);
      if (clamped > 0 && isMutedRef.current) {
        isMutedRef.current = false;
        setIsMuted(false);
      }
      if (audioRef.current) {
        audioRef.current.volume = isMutedRef.current ? 0 : clamped;
      }
      persistPreferences({
        music_volume: Math.round(clamped * 100) / 100,
      });
    },
    [persistPreferences]
  );

  const toggleMute = useCallback(() => {
    const nextMuted = !isMutedRef.current;
    isMutedRef.current = nextMuted;
    setIsMuted(nextMuted);
    if (audioRef.current) {
      audioRef.current.volume = nextMuted ? 0 : volumeRef.current;
    }
  }, []);

  const toggleLoop = useCallback(() => {
    const nextLoop = !isLoopingRef.current;
    isLoopingRef.current = nextLoop;
    setIsLooping(nextLoop);
    if (audioRef.current) {
      audioRef.current.loop = nextLoop;
    }
  }, []);

  const setCategory = useCallback(
    (category: MusicCategoryFilter) => {
      setSelectedCategoryState(category);
      persistPreferences({
        music_last_category: category,
      });
    },
    [persistPreferences]
  );

  const cancelUpload = useCallback(() => {
    if (uploadAbortRef.current) {
      uploadAbortRef.current.abort();
    }
  }, []);

  const uploadTrack = useCallback(
    async (file: File, customTitle?: string): Promise<MusicTrack | null> => {
      if (!file) return null;
      const ext = file.name.includes('.')
        ? `.${file.name.split('.').pop()?.toLowerCase()}`
        : '';
      if (!['.mp3', '.wav', '.ogg'].includes(ext)) {
        addToast(
          'Unsupported audio format. Please upload an MP3 (.mp3), WAV (.wav), or OGG (.ogg) file.',
          'error'
        );
        return null;
      }
      if (file.size === 0) {
        addToast('Selected audio file is empty.', 'error');
        return null;
      }
      if (file.size > maxUploadBytes) {
        const displayMb = maxUploadKb % 1000 === 0 ? maxUploadKb / 1000 : Number((maxUploadKb / 1000).toFixed(1));
        const fileKb = Math.ceil(file.size / 1024);
        addToast(
          `Audio file (${fileKb.toLocaleString()} KB) exceeds the ${maxUploadKb.toLocaleString()} KB (${displayMb} MB) maximum upload limit.`,
          'error'
        );
        return null;
      }

      const controller = new AbortController();
      uploadAbortRef.current = controller;
      activeUploadIdRef.current = null;
      setUploading(true);
      setUploadProgress(0);
      setPlaybackError(null);

      try {
        const effectiveChunkSize = Math.min(chunkSizeBytes || 2 * 1024 * 1024, 3 * 1024 * 1024);
        const totalChunks = Math.max(1, Math.ceil(file.size / effectiveChunkSize));
        const initRes = await apiRequest<{
          upload_id: string;
          chunk_size_bytes: number;
        }>('/api/music/upload/init', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            file_size: file.size,
            total_chunks: totalChunks,
            title: customTitle?.trim() || undefined,
            content_type: file.type || undefined,
          }),
          signal: controller.signal,
        });

        const uploadId = initRes.upload_id;
        activeUploadIdRef.current = uploadId;

        for (let idx = 0; idx < totalChunks; idx += 1) {
          if (controller.signal.aborted) {
            throw new DOMException('Aborted', 'AbortError');
          }
          const start = idx * effectiveChunkSize;
          const end = Math.min(file.size, start + effectiveChunkSize);
          const chunkBlob = file.slice(start, end);
          const formData = new FormData();
          formData.append('upload_id', uploadId);
          formData.append('chunk_index', String(idx));
          formData.append('file', chunkBlob, file.name);

          await apiRequest<{ upload_id: string; chunk_index: number }>('/api/music/upload/chunk', {
            method: 'POST',
            body: formData,
            signal: controller.signal,
          });
          setUploadProgress(Math.round(((idx + 1) / totalChunks) * 95));
        }

        const completeRes = await apiRequest<{ track: MusicTrack }>('/api/music/upload/complete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ upload_id: uploadId }),
          signal: controller.signal,
        });

        setUploadProgress(100);
        if (completeRes.track) {
          setUploadedTracks((prev) => [
            completeRes.track,
            ...prev.filter((t) => t.id !== completeRes.track.id),
          ]);
          addToast(`Uploaded "${completeRes.track.title}" to your focus library.`, 'success');
          return completeRes.track;
        }
        return null;
      } catch (err: any) {
        const uploadIdToCleanup = activeUploadIdRef.current;
        if (err?.name === 'AbortError' || controller.signal.aborted) {
          if (uploadIdToCleanup) {
            apiRequest(`/api/music/upload/${encodeURIComponent(uploadIdToCleanup)}`, {
              method: 'DELETE',
            }).catch(() => {});
          }
          addToast('Audio upload cancelled.', 'info');
          return null;
        }
        if (uploadIdToCleanup) {
          apiRequest(`/api/music/upload/${encodeURIComponent(uploadIdToCleanup)}`, {
            method: 'DELETE',
          }).catch(() => {});
        }
        addToast(err?.message || 'Audio upload failed.', 'error');
        return null;
      } finally {
        uploadAbortRef.current = null;
        activeUploadIdRef.current = null;
        setUploading(false);
        setUploadProgress(null);
      }
    },
    [addToast, chunkSizeBytes, maxUploadBytes, maxUploadKb]
  );

  const deleteTrack = useCallback(
    async (trackId: string): Promise<boolean> => {
      if (!trackId || deletingInFlightRef.current.has(trackId)) {
        return false;
      }
      deletingInFlightRef.current.add(trackId);
      setDeletingTrackId(trackId);
      try {
        await apiRequest(`/api/music/tracks/${encodeURIComponent(trackId)}`, {
          method: 'DELETE',
        });

        // If the deleted track was active, stop playback immediately, release ObjectURL, and reset state
        if (currentTrackId === trackId || loadedTrackIdRef.current === trackId) {
          if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.removeAttribute('src');
            audioRef.current.load();
          }
          loadedTrackIdRef.current = null;
          savedResumePositionRef.current = 0;
          revokeActiveObjectUrl();
          setIsPlaying(false);
          setCurrentTime(0);
          setCurrentTrackId('builtin_study_gentle');
          setDuration(12);
          persistPreferences({
            music_last_track_id: 'builtin_study_gentle',
            music_last_position: 0,
            music_playback_enabled: false,
          });
        }

        setUploadedTracks((prev) => prev.filter((t) => t.id !== trackId));
        addToast('Song permanently removed from your uploaded music library.', 'success');
        return true;
      } catch (err: any) {
        addToast(err?.message || 'Failed to delete uploaded song.', 'error');
        return false;
      } finally {
        deletingInFlightRef.current.delete(trackId);
        setDeletingTrackId(null);
      }
    },
    [addToast, currentTrackId, persistPreferences, revokeActiveObjectUrl]
  );

  const contextValue = useMemo<MusicPlayerContextValue>(
    () => ({
      categories,
      defaultTracks: builtinTracks,
      builtinTracks,
      uploadedTracks,
      allTracks,
      filteredTracks,
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
      maxUploadMb,
      storageNotice,
      uploading,
      uploadProgress,
      deletingTrackId,
      setCategory,
      selectTrack,
      play,
      pause,
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
      refreshLibrary,
    }),
    [
      categories,
      builtinTracks,
      uploadedTracks,
      allTracks,
      filteredTracks,
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
      maxUploadMb,
      storageNotice,
      uploading,
      uploadProgress,
      deletingTrackId,
      setCategory,
      selectTrack,
      play,
      pause,
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
      refreshLibrary,
    ]
  );

  return (
    <MusicPlayerContext.Provider value={contextValue}>
      {children}
    </MusicPlayerContext.Provider>
  );
};

export function useMusicPlayer(): MusicPlayerContextValue {
  const ctx = useContext(MusicPlayerContext);
  if (!ctx) {
    throw new Error('useMusicPlayer must be used within a MusicPlayerProvider');
  }
  return ctx;
}
