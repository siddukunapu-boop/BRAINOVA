/**
 * StudyOS — Route Chunk & Data Prefetcher
 * Preloads lazy route bundles and primary API payloads on hover/focus/idle.
 */

import { prefetchQuery } from './queryCache';

export const pageLoaders = {
  auth: () => import('../pages/AuthPage').then((m) => ({ default: m.AuthPage })),
  dashboard: () => import('../pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
  roadmaps: () => import('../pages/RoadmapsPage').then((m) => ({ default: m.RoadmapsPage })),
  roadmapDetail: () =>
    import('../pages/RoadmapDetailPage').then((m) => ({ default: m.RoadmapDetailPage })),
  customizedRoadmap: () =>
    import('../pages/CustomizedRoadmapPage').then((m) => ({ default: m.CustomizedRoadmapPage })),
  topicWorkspace: () =>
    import('../pages/TopicWorkspacePage').then((m) => ({ default: m.TopicWorkspacePage })),
  sources: () => import('../pages/SourcesPage').then((m) => ({ default: m.SourcesPage })),
  resources: () => import('../pages/ResourcesPage').then((m) => ({ default: m.ResourcesPage })),
  diary: () => import('../pages/DiaryPage').then((m) => ({ default: m.DiaryPage })),
  studyJournal: () =>
    import('../pages/StudyJournalPage').then((m) => ({ default: m.StudyJournalPage })),
  focus: () => import('../pages/FocusModePage').then((m) => ({ default: m.FocusModePage })),
  careerLaunchpad: () =>
    import('../pages/CareerLaunchpadPage').then((m) => ({ default: m.CareerLaunchpadPage })),
  techPulse: () => import('../pages/TechPulsePage').then((m) => ({ default: m.TechPulsePage })),
  quizzes: () => import('../pages/QuizzesPage').then((m) => ({ default: m.QuizzesPage })),
  settings: () => import('../pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
};

const ROUTE_PREFETCH_MAP: Record<
  string,
  { loader: () => Promise<unknown>; apiPaths?: string[] }
> = {
  '/dashboard': {
    loader: pageLoaders.dashboard,
    apiPaths: ['/api/dashboard'],
  },
  '/roadmaps': {
    loader: pageLoaders.roadmaps,
    apiPaths: ['/api/roadmaps'],
  },
  '/customized-roadmap': {
    loader: pageLoaders.customizedRoadmap,
    apiPaths: ['/api/roadmaps'],
  },
  '/sources': {
    loader: pageLoaders.sources,
    apiPaths: ['/api/sources'],
  },
  '/resources': {
    loader: pageLoaders.resources,
    apiPaths: ['/api/resources'],
  },
  '/diary': {
    loader: pageLoaders.diary,
    apiPaths: ['/api/diary'],
  },
  '/study-journal': {
    loader: pageLoaders.studyJournal,
    apiPaths: ['/api/study-journal'],
  },
  '/focus': {
    loader: pageLoaders.focus,
  },
  '/career-launchpad': {
    loader: pageLoaders.careerLaunchpad,
    apiPaths: ['/api/career-launchpad/overview'],
  },
  '/tech-pulse': {
    loader: pageLoaders.techPulse,
    apiPaths: ['/api/tech-pulse/feed'],
  },
  '/quizzes': {
    loader: pageLoaders.quizzes,
    apiPaths: ['/api/quizzes/history'],
  },
  '/settings': {
    loader: pageLoaders.settings,
  },
};

const _prefetchedRoutes = new Set<string>();

export function prefetchRoute(path: string): void {
  const basePath = path.split('?')[0];
  const target = ROUTE_PREFETCH_MAP[basePath];
  if (!target) return;

  if (!_prefetchedRoutes.has(basePath)) {
    _prefetchedRoutes.add(basePath);
    target.loader().catch(() => {
      _prefetchedRoutes.delete(basePath);
    });
  }

  if (target.apiPaths) {
    for (const apiPath of target.apiPaths) {
      prefetchQuery(apiPath);
    }
  }
}

export function scheduleIdleRoutePrefetch(): () => void {
  const routesToWarm = ['/dashboard', '/roadmaps', '/career-launchpad', '/tech-pulse'];
  const win = window as unknown as {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
    cancelIdleCallback?: (id: number) => void;
  };

  if (typeof win.requestIdleCallback === 'function') {
    const id = win.requestIdleCallback(
      () => {
        routesToWarm.forEach((r) => prefetchRoute(r));
      },
      { timeout: 2000 }
    );
    return () => win.cancelIdleCallback?.(id);
  }

  const timer = window.setTimeout(() => {
    routesToWarm.forEach((r) => prefetchRoute(r));
  }, 1200);
  return () => window.clearTimeout(timer);
}
