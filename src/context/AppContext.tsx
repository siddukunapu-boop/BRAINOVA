import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { apiRequest, getStoredToken, setStoredToken } from '../services/api';

export type BrainovaTheme =
  | 'midnight_luxe'
  | 'obsidian_emerald'
  | 'midnight_sapphire'
  | 'onyx_burgundy';

export const BRAINOVA_THEMES: Array<{
  id: BrainovaTheme;
  name: string;
  description: string;
  swatches: [string, string, string];
}> = [
  {
    id: 'midnight_luxe',
    name: 'Midnight Luxe',
    description: 'Obsidian black, warm charcoal surfaces & brushed gold accent (Default)',
    swatches: ['#080808', '#171717', '#D6B56D'],
  },
  {
    id: 'obsidian_emerald',
    name: 'Obsidian Emerald',
    description: 'Deep forest obsidian, rich emerald surfaces & muted gold accent',
    swatches: ['#080D0B', '#123C32', '#C5A46D'],
  },
  {
    id: 'midnight_sapphire',
    name: 'Midnight Sapphire',
    description: 'Deep nocturnal navy, sapphire surfaces & crisp ice-blue accent',
    swatches: ['#080F1C', '#14243A', '#78A9E8'],
  },
  {
    id: 'onyx_burgundy',
    name: 'Onyx Burgundy',
    description: 'Velvet onyx, deep claret surfaces & warm rose-bronze accent',
    swatches: ['#10090C', '#321923', '#C58A78'],
  },
];

export interface CredentialsStatus {
  gemini_configured: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
  any_llm_configured: boolean;
  youtube_api_configured: boolean;
  elevenlabs_configured: boolean;
  local_sapi_tts_available: boolean;
  video_provider_configured: boolean;
  local_video_renderer_available?: boolean;
}

export interface UserPreferences {
  user_id: string;
  ai_provider: string;
  gemini_model: string;
  openai_model: string;
  anthropic_model: string;
  default_skill_level: string;
  study_hours_per_week: number;
  auto_generate_policy: string;
  show_demo_data: boolean;
  reduced_motion: boolean;
  theme?: BrainovaTheme;
  preferred_language?: string;
  credentials_status: CredentialsStatus;
  updated_at: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  target_role: string;
  bio: string;
  avatar_color: string;
  avatar_url?: string;
  created_at: string;
  updated_at: string;
  preferences: UserPreferences;
}

export interface ToastMessage {
  id: string;
  type: 'info' | 'success' | 'error';
  text: string;
}

interface AppContextValue {
  user: UserProfile | null;
  loadingAuth: boolean;
  theme: BrainovaTheme;
  setTheme: (theme: BrainovaTheme) => Promise<void>;
  loginWithToken: (token: string, user: UserProfile) => void;
  logoutUser: () => void;
  refreshUser: () => Promise<void>;
  toasts: ToastMessage[];
  addToast: (text: string, type?: 'info' | 'success' | 'error') => void;
  removeToast: (id: string) => void;
}

const THEME_STORAGE_KEY = 'brainova_theme';

const VALID_THEMES: BrainovaTheme[] = [
  'midnight_luxe',
  'obsidian_emerald',
  'midnight_sapphire',
  'onyx_burgundy',
];

function isValidTheme(value: unknown): value is BrainovaTheme {
  return typeof value === 'string' && VALID_THEMES.includes(value as BrainovaTheme);
}

function getInitialTheme(): BrainovaTheme {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (isValidTheme(saved)) {
    return saved;
  }
  return 'midnight_luxe';
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loadingAuth, setLoadingAuth] = useState<boolean>(true);
  const [theme, setThemeState] = useState<BrainovaTheme>(getInitialTheme);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const applyDomTheme = useCallback((nextTheme: BrainovaTheme) => {
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    setThemeState(nextTheme);
  }, []);

  useEffect(() => {
    applyDomTheme(theme);
  }, [applyDomTheme, theme]);

  const addToast = useCallback((text: string, type: 'info' | 'success' | 'error' = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, type, text }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const setTheme = useCallback(
    async (nextTheme: BrainovaTheme) => {
      applyDomTheme(nextTheme);
      if (getStoredToken()) {
        try {
          await apiRequest('/api/settings/preferences', {
            method: 'PUT',
            body: JSON.stringify({ theme: nextTheme }),
          });
        } catch {
          // Keep local theme active even if network is offline
        }
      }
    },
    [applyDomTheme]
  );

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setLoadingAuth(false);
      return;
    }
    try {
      const res = await apiRequest<{ user: UserProfile }>('/api/auth/me');
      setUser(res.user);
      if (res.user?.preferences?.theme) {
        const userTheme = res.user.preferences.theme;
        applyDomTheme(isValidTheme(userTheme) ? userTheme : 'midnight_luxe');
      }
      if (res.user?.preferences?.reduced_motion) {
        document.body.setAttribute('data-reduced-motion', 'true');
      } else {
        document.body.removeAttribute('data-reduced-motion');
      }
    } catch {
      setStoredToken(null);
      setUser(null);
    } finally {
      setLoadingAuth(false);
    }
  }, [applyDomTheme]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const loginWithToken = (token: string, userData: UserProfile) => {
    setStoredToken(token);
    setUser(userData);
    if (userData?.preferences?.theme) {
      const userTheme = userData.preferences.theme;
      applyDomTheme(isValidTheme(userTheme) ? userTheme : 'midnight_luxe');
    }
    if (userData?.preferences?.reduced_motion) {
      document.body.setAttribute('data-reduced-motion', 'true');
    } else {
      document.body.removeAttribute('data-reduced-motion');
    }
  };

  const logoutUser = () => {
    apiRequest('/api/auth/logout', { method: 'POST' }).catch(() => {});
    setStoredToken(null);
    setUser(null);
    addToast('Signed out safely.', 'info');
  };

  return (
    <AppContext.Provider
      value={{
        user,
        loadingAuth,
        theme,
        setTheme,
        loginWithToken,
        logoutUser,
        refreshUser,
        toasts,
        addToast,
        removeToast,
      }}
    >
      {children}
      {/* Toast Notifications */}
      <div className="toast-container" role="region" aria-label="Notifications">
        {toasts.map((t) => (
          <div key={t.id} className={`toast-item ${t.type}`}>
            <span>{t.text}</span>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => removeToast(t.id)}
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </AppContext.Provider>
  );
};

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useApp must be used within AppProvider');
  }
  return ctx;
}
