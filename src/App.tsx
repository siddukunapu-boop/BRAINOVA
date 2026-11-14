import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppProvider, useApp } from './context/AppContext';
import { FocusProvider } from './context/FocusContext';
import { AppShell } from './components/AppShell';
import { AuthPage } from './pages/AuthPage';
import { DashboardPage } from './pages/DashboardPage';
import { SourcesPage } from './pages/SourcesPage';
import { RoadmapsPage } from './pages/RoadmapsPage';
import { RoadmapDetailPage } from './pages/RoadmapDetailPage';
import { CustomizedRoadmapPage } from './pages/CustomizedRoadmapPage';
import { TopicWorkspacePage } from './pages/TopicWorkspacePage';
import { ResourcesPage } from './pages/ResourcesPage';
import { DiaryPage } from './pages/DiaryPage';
import { StudyJournalPage } from './pages/StudyJournalPage';
import { QuizzesPage } from './pages/QuizzesPage';
import { SettingsPage } from './pages/SettingsPage';
import { FocusModePage } from './pages/FocusModePage';

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
        Initializing BRAINOVA Workspace...
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    );
  }

  return (
    <FocusProvider>
      <AppShell>
        <RouteErrorBoundary>
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
          <Route path="/quizzes" element={<QuizzesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/analytics" element={<Navigate to="/dashboard" replace />} />
          <Route path="/auth" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </RouteErrorBoundary>
      </AppShell>
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
