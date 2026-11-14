import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderOpen,
  Compass,
  Sliders,
  BookMarked,
  BookText,
  GraduationCap,
  CheckSquare,
  Settings,
  Search,
  Palette,
  LogOut,
  Menu,
  X,
  Check,
  ShieldCheck,
} from 'lucide-react';
import { useApp, BRAINOVA_THEMES } from '../context/AppContext';
import { FocusModalsOverlay, FocusStatusBar } from './FocusOverlayUI';
import { apiRequest } from '../services/api';

interface SearchResultItem {
  type: string;
  title: string;
  subtitle: string;
  link: string;
}

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logoutUser, theme, setTheme } = useApp();
  const navigate = useNavigate();
  const location = useLocation();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [showThemePopover, setShowThemePopover] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMobileOpen(false);
    setShowSearchDropdown(false);
    setShowThemePopover(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await apiRequest<{ results: SearchResultItem[] }>(
          `/api/search?q=${encodeURIComponent(searchQuery.trim())}`
        );
        setSearchResults(res.results || []);
        setShowSearchDropdown(true);
      } catch {
        setSearchResults([]);
      }
    }, 220);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearchDropdown(false);
      }
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) {
        setShowThemePopover(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Part 3 — Complete Website Navigation (Progress & Analytics removed per Part 10)
  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/roadmaps', label: 'AI Roadmaps', icon: Compass },
    { to: '/customized-roadmap', label: 'Customized Roadmap', icon: Sliders },
    { to: '/sources', label: 'My Sources', icon: FolderOpen },
    { to: '/resources', label: 'My Learning Resources', icon: BookMarked },
    { to: '/diary', label: 'Diary', icon: BookText },
    { to: '/study-journal', label: 'Study Journal', icon: GraduationCap },
    { to: '/focus', label: 'Focus Mode', icon: ShieldCheck },
    { to: '/quizzes', label: 'Quizzes & Results', icon: CheckSquare },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="app-shell">
      {/* Left Navigation Sidebar */}
      <aside
        className={`app-sidebar ${mobileOpen ? 'mobile-open' : ''}`}
        aria-label="Primary Sidebar Navigation"
      >
        <div className="sidebar-brand">
          <div
            className="brand-logo-group"
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '11px' }}
            onClick={() => navigate('/dashboard')}
          >
            <div className="brainova-logo-wrap" style={{ width: 38, height: 38 }}>
              <img
                src="/brainova-logo.jpg"
                alt="BRAINOVA Logo"
                className="brainova-logo-img"
              />
            </div>
            <div style={{ minWidth: 0 }}>
              <span className="brand-title brainova-brand-text" style={{ fontSize: '1.08rem', display: 'block', lineHeight: 1.15 }}>
                BRAINOVA
              </span>
              <span
                className="brand-subtitle"
                style={{
                  fontSize: '0.64rem',
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  letterSpacing: '0.025em',
                  wordSpacing: '0.06em',
                  display: 'block',
                  whiteSpace: 'nowrap',
                  marginTop: '1px',
                }}
              >
                LEARN SMARTER. THINK BIGGER.
              </span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">BRAINOVA Platform</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={18} style={{ flexShrink: 0 }} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom-Left Profile Section — Identity opens Profile Settings (/settings); Sign Out logs out */}
        <div className="sidebar-footer">
          {user && (
            <div className="sidebar-account-card">
              <button
                type="button"
                className="sidebar-account-identity"
                onClick={() => navigate('/settings')}
                title="Open Profile Settings"
              >
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name}
                    className="sidebar-avatar-img"
                  />
                ) : (
                  <div
                    className="sidebar-avatar-initials"
                    style={{
                      background:
                        user.avatar_color ||
                        'linear-gradient(135deg, #06b6d4 0%, #6366f1 55%, #8b5cf6 100%)',
                    }}
                    aria-hidden="true"
                  >
                    {user.name
                      .trim()
                      .split(/\s+/)
                      .slice(0, 2)
                      .map((part) => part.charAt(0).toUpperCase())
                      .join('') || 'U'}
                  </div>
                )}
                <div className="sidebar-account-text">
                  <div className="sidebar-account-name" title={user.name}>
                    {user.name}
                  </div>
                  <div
                    className="sidebar-account-role"
                    title={user.target_role || 'Profile Settings'}
                  >
                    {user.target_role || 'Profile Settings'}
                  </div>
                </div>
              </button>

              <button
                type="button"
                className="sidebar-signout-btn"
                onClick={logoutUser}
                title="Sign out"
                aria-label="Sign out"
                data-testid="sidebar-signout-btn"
              >
                <LogOut size={16} aria-hidden="true" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Wrapper */}
      <div className="app-main-wrapper">
        {/* Global Navbar (Part 2) */}
        <header className="app-topbar">
          {/* LEFT: Exact BRAINOVA Logo + BRAINOVA Name + Global Search */}
          <div className="topbar-left">
            <button
              type="button"
              className="btn btn-secondary btn-sm mobile-menu-btn"
              onClick={() => setMobileOpen((m) => !m)}
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <div
              className="topbar-brand"
              onClick={() => navigate('/dashboard')}
            >
              <div className="brainova-logo-wrap" style={{ width: 34, height: 34 }}>
                <img
                  src="/brainova-logo.jpg"
                  alt="BRAINOVA"
                  className="brainova-logo-img"
                />
              </div>
              <div className="topbar-brand-text">
                <span className="brainova-brand-text" style={{ fontSize: '1.02rem', lineHeight: 1.15 }}>
                  BRAINOVA
                </span>
                <span className="topbar-brand-tagline">
                  LEARN SMARTER. THINK BIGGER.
                </span>
              </div>
            </div>

            {/* Global Search */}
            <div className="global-search-box" ref={searchRef}>
              <Search size={16} className="global-search-icon" />
              <input
                type="search"
                className="global-search-input"
                placeholder="Search roadmaps, topics, sources..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  if (searchQuery.trim()) setShowSearchDropdown(true);
                }}
                aria-label="Global platform search"
              />
              {showSearchDropdown && searchQuery.trim() && (
                <div className="search-dropdown">
                  {searchResults.length === 0 ? (
                    <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No matching items found for "{searchQuery}".
                    </div>
                  ) : (
                    searchResults.map((item, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          navigate(item.link);
                          setShowSearchDropdown(false);
                        }}
                        style={{
                          padding: '9px 12px',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '12px',
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = 'var(--surface-hover)')
                        }
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.86rem' }}>{item.title}</div>
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: 'var(--text-muted)',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {item.subtitle}
                          </div>
                        </div>
                        <span className="badge badge-indigo">{item.type}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT: Theme Switcher Icon + Account Controls */}
          <div className="topbar-right" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Four-Theme Switcher (Color-Palette Icon) */}
            <div style={{ position: 'relative' }} ref={themeRef}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowThemePopover((p) => !p)}
                aria-label="Switch Theme"
                title="Switch Color Theme"
                data-testid="navbar-theme-switcher-btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Palette size={16} />
              </button>

              {showThemePopover && (
                <div className="theme-popover" role="menu" aria-label="Theme Selector">
                  <div
                    style={{
                      padding: '4px 8px 8px',
                      marginBottom: '6px',
                      borderBottom: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                      BRAINOVA Themes
                    </span>
                    <span className="badge badge-blue" style={{ fontSize: '0.68rem' }}>
                      4 Palettes
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {BRAINOVA_THEMES.map((t) => {
                      const isCurrent = theme === t.id;
                      return (
                        <button
                          key={t.id}
                          type="button"
                          className={`theme-option-btn ${isCurrent ? 'active' : ''}`}
                          data-testid={`theme-option-${t.id}`}
                          onClick={() => {
                            setTheme(t.id);
                            setShowThemePopover(false);
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: '0.84rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>{t.name}</span>
                              {isCurrent && <Check size={14} style={{ color: 'var(--accent-blue)' }} />}
                            </div>
                            <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>
                              {t.description}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                            {t.swatches.map((hex, i) => (
                              <span
                                key={i}
                                style={{
                                  width: 13,
                                  height: 13,
                                  borderRadius: '50%',
                                  background: hex,
                                  border: '1px solid rgba(255,255,255,0.28)',
                                }}
                              />
                            ))}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

          </div>
        </header>

        {/* Active Strict Focus Mode Status Dock */}
        <FocusStatusBar />

        {/* Page Content */}
        <main className="app-content-container">{children}</main>
      </div>
      <FocusModalsOverlay />
    </div>
  );
};
