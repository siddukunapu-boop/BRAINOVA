import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

test('Exactly four new BRAINOVA themes are configured with Midnight Luxe as default', () => {
  const ctxSrc = fs.readFileSync(path.join(root, 'src', 'context', 'AppContext.tsx'), 'utf8');
  const cssSrc = fs.readFileSync(path.join(root, 'src', 'styles', 'design-system.css'), 'utf8');
  const dbSrc = fs.readFileSync(path.join(root, 'backend', 'database.py'), 'utf8');
  const authSrc = fs.readFileSync(path.join(root, 'backend', 'auth.py'), 'utf8');

  for (const oldId of ['neural_night', 'dark_light', 'quantum_violet', 'focus_forest']) {
    assert.equal(ctxSrc.includes(oldId), false, `Old theme ${oldId} must not remain in AppContext.tsx`);
    assert.equal(cssSrc.includes(oldId), false, `Old theme ${oldId} must not remain in design-system.css`);
    assert.equal(dbSrc.includes(oldId), false, `Old theme ${oldId} must not remain in database.py`);
    assert.equal(authSrc.includes(oldId), false, `Old theme ${oldId} must not remain in auth.py`);
  }

  for (const newId of ['midnight_luxe', 'obsidian_emerald', 'midnight_sapphire', 'onyx_burgundy']) {
    assert.match(ctxSrc, new RegExp(newId));
    assert.match(cssSrc, new RegExp(`\\[data-theme="${newId}"\\]`));
  }

  // Verify exact palette tokens
  assert.match(cssSrc, /--bg-midnight:\s*#080808/i);
  assert.match(cssSrc, /--accent-indigo:\s*#d6b56d/i);
  assert.match(cssSrc, /--bg-midnight:\s*#080d0b/i);
  assert.match(cssSrc, /--bg-midnight:\s*#080f1c/i);
  assert.match(cssSrc, /--bg-midnight:\s*#10090c/i);
});

test('Sidebar preserves all 12 navigation items and uses theme-adaptive animated styles', () => {
  const shellSrc = fs.readFileSync(path.join(root, 'src', 'components', 'AppShell.tsx'), 'utf8');
  const cssSrc = fs.readFileSync(path.join(root, 'src', 'styles', 'design-system.css'), 'utf8');

  const expectedNav = [
    ['/dashboard', 'Dashboard'],
    ['/roadmaps', 'AI Roadmaps'],
    ['/customized-roadmap', 'Customized Roadmap'],
    ['/sources', 'My Sources'],
    ['/resources', 'My Learning Resources'],
    ['/diary', 'Diary'],
    ['/study-journal', 'Study Journal'],
    ['/focus', 'Focus Mode'],
    ['/career-launchpad', 'Career Launchpad'],
    ['/tech-pulse', 'Tech Pulse'],
    ['/quizzes', 'Quizzes & Results'],
    ['/settings', 'Settings'],
  ];
  for (const [route, label] of expectedNav) {
    assert.ok(shellSrc.includes(`to: '${route}', label: '${label}'`), `Missing nav item ${label} -> ${route}`);
  }

  assert.match(cssSrc, /@keyframes navItemStagger/);
  assert.match(cssSrc, /@keyframes navIndicatorIn/);
  assert.match(cssSrc, /\.app-sidebar\.collapsed/);
});

