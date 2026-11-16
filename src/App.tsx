import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppProvider, useApp } from './context/AppContext';
import { FocusProvider } from './context/FocusContext';
import { MusicPlayerProvider } from './context/MusicPlayerContext';
import { AppShell } from './components/AppShell';
import { pageLoaders } from './lib/routePrefetch';

const AuthPage = lazy(pageLoaders.auth);
const DashboardPage = lazy(pageLoaders.dashboard);
const RoadmapsPage = lazy(pageLoaders.roadmaps);
const RoadmapDetailPage = lazy(pageLoaders.roadmapDetail);
const CustomizedRoadmapPage = lazy(pageLoaders.customizedRoadmap);
const TopicWorkspacePage = lazy(pageLoaders.topicWorkspace);
const SourcesPage = lazy(pageLoaders.sources);
const ResourcesPage = lazy(pageLoaders.resources);
const DiaryPage = lazy(pageLoaders.diary);
const StudyJournalPage = lazy(pageLoaders.studyJournal);
const FocusModePage = lazy(pageLoaders.focus);
const CareerLaunchpadPage = lazy(pageLoaders.careerLaunchpad);
const TechPulsePage = lazy(pageLoaders.techPulse);
const QuizzesPage = lazy(pageLoaders.quizzes);
const SettingsPage = lazy(pageLoaders.settings);

const RouteLoadingFallback: React.FC = () => (
  <div
    className="route-loading-fallback"
    role="status"
    aria-live="polite"
    style={{
      padding: '1.5rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.85rem',
      minHeight: '220px',
    }}
  >
    <div
      style={{
        height: '24px',
        width: '240px',
        borderRadius: '8px',
        background: 'var(--surface-elevated, rgba(255,255,255,0.06))',
      }}
    />
    <div
      style={{
        height: '110px',
        width: '100%',
        borderRadius: '12px',
        background: 'var(--surface-elevated, rgba(255,255,255,0.04))',
      }}
    />
  </div>
);

// Keyed by location so navigating away from a crashed page resets the boundary.
const RouteErrorBoundary: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  return (
    <ErrorBoundary key={`${location.pathname}${location.search}`}>{children}</ErrorBoundary>
  );
};

const ProtectedRoutes: React.FC = () => {
  const { user, loadingAuth } = useApp();

  if (loadingAuth) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-secondary)',
        }}
      >
        Initializing StudyOS Workspace...
      </div>
    );
  }

  if (!user) {
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="*" element={<Navigate to="/auth" replace />} />
        </Routes>
      </Suspense>
    );
  }

  return (
    <FocusProvider>
      <MusicPlayerProvider>
        <AppShell>
          <RouteErrorBoundary>
            <Suspense fallback={<RouteLoadingFallback />}>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/roadmaps" element={<RoadmapsPage />} />
                <Route path="/roadmaps/:roadmapId" element={<RoadmapDetailPage />} />
                <Route path="/customized-roadmap" element={<CustomizedRoadmapPage />} />
                <Route
                  path="/roadmaps/:roadmapId/topics/:topicId"
                  element={<TopicWorkspacePage />}
                />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/resources" element={<ResourcesPage />} />
                <Route path="/diary" element={<DiaryPage />} />
                <Route path="/study-journal" element={<StudyJournalPage />} />
                <Route path="/focus" element={<FocusModePage />} />
                <Route path="/career-launchpad" element={<CareerLaunchpadPage />} />
                <Route path="/tech-pulse" element={<TechPulsePage />} />
                <Route path="/quizzes" element={<QuizzesPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/analytics" element={<Navigate to="/dashboard" replace />} />
                <Route path="/auth" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
          </RouteErrorBoundary>
        </AppShell>
      </MusicPlayerProvider>
    </FocusProvider>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppProvider>
        <ProtectedRoutes />
      </AppProvider>
    </BrowserRouter>
  );
};
export default App;
