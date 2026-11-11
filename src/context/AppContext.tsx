import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { apiRequest, getStoredToken, setStoredToken } from '../services/api';

export type BrainovaTheme = 'neural_night' | 'dark_light' | 'quantum_violet' | 'focus_forest';

export const BRAINOVA_THEMES: Array<{
  id: BrainovaTheme;
  name: string;
  description: string;
  swatches: [string, string, string];
}> = [
  {
    id: 'neural_night',
    name: 'Neural Night',
    description: 'Deep midnight-navy, electric blue & cyan-violet',
    swatches: ['#070a14', '#161f3d', '#38bdf8'],
  },
  {
    id: 'dark_light',
    name: 'Dark Light',
    description: 'Pure black & charcoal with high-contrast bright accents',
    swatches: ['#040405', '#18181e', '#22d3ee'],
  },
  {
    id: 'quantum_violet',
    name: 'Quantum Violet',
    description: 'Deep violet backgrounds with bright purple & lavender',
    swatches: ['#0b0616', '#211340', '#c084fc'],
  },
  {
    id: 'focus_forest',
    name: 'Focus Forest',
    description: 'Deep forest-green with calm emerald & teal accents',
    swatches: ['#04100b', '#113023', '#34d399'],
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

function getInitialTheme(): BrainovaTheme {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (saved === 'neural_night' || saved === 'dark_light' || saved === 'quantum_violet' || saved === 'focus_forest') {
    return saved;
  }
  return 'neural_night';
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
        const userTheme = res.user.preferences.theme as BrainovaTheme;
        if (['neural_night', 'dark_light', 'quantum_violet', 'focus_forest'].includes(userTheme)) {
          applyDomTheme(userTheme);
        }
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
      const userTheme = userData.preferences.theme as BrainovaTheme;
      if (['neural_night', 'dark_light', 'quantum_violet', 'focus_forest'].includes(userTheme)) {
        applyDomTheme(userTheme);
      }
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
