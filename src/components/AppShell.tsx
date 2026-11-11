import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Sparkles,
  FolderOpen,
  Compass,
  Sliders,
  BookMarked,
  CheckSquare,
  Settings,
  Search,
  Library,
  Palette,
  Bell,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  X,
  RefreshCw,
  Check,
} from 'lucide-react';
import { useApp, BRAINOVA_THEMES } from '../context/AppContext';
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

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [showThemePopover, setShowThemePopover] = useState(false);
  const [showJobsPopover, setShowJobsPopover] = useState(false);
  const [activeJobs, setActiveJobs] = useState<any[]>([]);

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

  const fetchRecentJobs = async () => {
    try {
      const res = await apiRequest<{ jobs: any[] }>('/api/jobs');
      setActiveJobs((res.jobs || []).slice(0, 8));
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchRecentJobs();
  }, [location.pathname]);

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
    { to: '/studio', label: 'AI Studio', icon: Sparkles },
    { to: '/roadmaps', label: 'AI Roadmaps', icon: Compass },
    { to: '/customized-roadmap', label: 'Customized Roadmap', icon: Sliders },
    { to: '/sources', label: 'My Sources', icon: FolderOpen },
    { to: '/resources', label: 'My Learning Resources', icon: BookMarked },
    { to: '/quizzes', label: 'Quizzes & Results', icon: CheckSquare },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  const runningJobsCount = activeJobs.filter(
    (j) => j.status === 'queued' || j.status === 'processing'
  ).length;

  const isLibraryActive = location.pathname.startsWith('/studio-library');

  return (
    <div className="app-shell">
      {/* Left Navigation Sidebar */}
      <aside
        className={`app-sidebar ${collapsed ? 'collapsed' : ''} ${
          mobileOpen ? 'mobile-open' : ''
        }`}
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
            {!collapsed && (
              <div style={{ minWidth: 0 }}>
                <span className="brand-title brainova-brand-text" style={{ fontSize: '1.08rem', display: 'block', lineHeight: 1.15 }}>
                  BRAINOVA
                </span>
                <span className="brand-subtitle" style={{ fontSize: '0.68rem', color: 'var(--text-muted)', display: 'block' }}>
                  Learn Smarter. Think Bigger.
                </span>
              </div>
            )}
          </div>
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {!collapsed && <div className="nav-section-label">BRAINOVA Platform</div>}
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <Icon size={18} style={{ flexShrink: 0 }} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom-Left Profile Section — Clicking navigates directly to Profile Settings (/settings) */}
        <div className="sidebar-footer">
          {user && (
            <div
              role="button"
              tabIndex={0}
              onClick={() => navigate('/settings')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') navigate('/settings');
              }}
              title="Open Profile Settings"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'space-between',
                gap: '10px',
                padding: '9px 10px',
                borderRadius: '10px',
                background: 'var(--surface-2)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
                transition: 'border-color 150ms ease, background 150ms ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name}
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: '50%',
                      objectFit: 'cover',
                      border: '1px solid var(--accent-blue)',
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: '50%',
                      background: user.avatar_color || 'var(--accent-indigo)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.86rem',
                      color: '#fff',
                      flexShrink: 0,
                    }}
                  >
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                )}
                {!collapsed && (
                  <div style={{ overflow: 'hidden' }}>
                    <div
                      style={{
                        fontSize: '0.83rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {user.name}
                    </div>
                    <div
                      style={{
                        fontSize: '0.72rem',
                        color: 'var(--text-muted)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {user.target_role || 'Profile Settings'}
                    </div>
                  </div>
                )}
              </div>
              {!collapsed && (
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    logoutUser();
                  }}
                  title="Sign out"
                  aria-label="Sign out"
                >
                  <LogOut size={15} />
                </button>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Wrapper */}
      <div className={`app-main-wrapper ${collapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Global Navbar (Part 2) */}
        <header className="app-topbar">
          {/* LEFT: Exact BRAINOVA Logo + BRAINOVA Name + Global Search */}
          <div className="topbar-left" style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm mobile-menu-btn"
              onClick={() => setMobileOpen((m) => !m)}
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <div
              onClick={() => navigate('/dashboard')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                cursor: 'pointer',
                paddingRight: '8px',
                flexShrink: 0,
              }}
            >
              <div className="brainova-logo-wrap" style={{ width: 34, height: 34 }}>
                <img
                  src="/brainova-logo.jpg"
                  alt="BRAINOVA"
                  className="brainova-logo-img"
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="brainova-brand-text" style={{ fontSize: '0.98rem', lineHeight: 1.1 }}>
                  BRAINOVA
                </span>
                <span style={{ fontSize: '0.66rem', color: 'var(--text-muted)', letterSpacing: '0.02em' }}>
                  Learn Smarter. Think Bigger.
                </span>
              </div>
            </div>

            {/* Global Search */}
            <div className="global-search-box" ref={searchRef}>
              <Search size={16} className="global-search-icon" />
              <input
                type="search"
                className="global-search-input"
                placeholder="Search roadmaps, topics, sources, AI Studio library..."
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

          {/* RIGHT: AI Studio Library Direct Navigation Button + Theme Switcher Icon + Account Controls */}
          <div className="topbar-right" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Direct AI Studio Library Navigation Button */}
            <button
              type="button"
              className={`btn ${isLibraryActive ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              onClick={() => navigate('/studio-library')}
              title="Open saved AI Studio Library"
              data-testid="navbar-studio-library-btn"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '7px',
                fontWeight: 600,
              }}
            >
              <Library size={15} />
              <span>AI Studio Library</span>
            </button>

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

            {/* Background Jobs Status Popover */}
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  fetchRecentJobs();
                  setShowJobsPopover((p) => !p);
                }}
                aria-label="Generation Queue Status"
                title="Generation Queue Status"
              >
                <Bell size={15} />
                {runningJobsCount > 0 && (
                  <span className="badge badge-blue" style={{ padding: '1px 6px' }}>
                    {runningJobsCount}
                  </span>
                )}
              </button>
              {showJobsPopover && (
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 8px)',
                    width: '320px',
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border-default)',
                    borderRadius: '12px',
                    boxShadow: 'var(--shadow-lg)',
                    padding: '12px',
                    zIndex: 200,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px',
                    }}
                  >
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                      Resource Generation Queue
                    </span>
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      onClick={fetchRecentJobs}
                      title="Refresh queue"
                    >
                      <RefreshCw size={13} />
                    </button>
                  </div>
                  {activeJobs.length === 0 ? (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '8px 0' }}>
                      No recent background jobs.
                    </div>
                  ) : (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        maxHeight: '240px',
                        overflowY: 'auto',
                      }}
                    >
                      {activeJobs.map((j) => (
                        <div
                          key={j.id}
                          style={{
                            padding: '8px',
                            borderRadius: '8px',
                            background: 'var(--surface-2)',
                            fontSize: '0.78rem',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '8px',
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                              {j.resource_type} Generation
                            </div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                              Topic #{j.topic_id?.slice(-6)}
                            </div>
                          </div>
                          <span
                            className={`badge ${
                              j.status === 'completed'
                                ? 'badge-success'
                                : j.status === 'failed'
                                ? 'badge-danger'
                                : 'badge-blue'
                            }`}
                          >
                            {j.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="app-content-container">{children}</main>
      </div>
    </div>
  );
};
