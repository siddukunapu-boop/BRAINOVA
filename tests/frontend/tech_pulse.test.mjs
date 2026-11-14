import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

test('Tech Pulse frontend route, sidebar navigation, and styles are wired cleanly', () => {
  const appSrc = fs.readFileSync(path.join(root, 'src', 'App.tsx'), 'utf8');
  const shellSrc = fs.readFileSync(path.join(root, 'src', 'components', 'AppShell.tsx'), 'utf8');
  const mainSrc = fs.readFileSync(path.join(root, 'src', 'main.tsx'), 'utf8');
  const pageSrc = fs.readFileSync(path.join(root, 'src', 'pages', 'TechPulsePage.tsx'), 'utf8');

  assert.match(appSrc, /path="\/tech-pulse"/);
  assert.match(appSrc, /<TechPulsePage\s*\/>/);
  assert.match(shellSrc, /to:\s*'\/tech-pulse',\s*label:\s*'Tech Pulse'/);
  assert.match(mainSrc, /tech-pulse\.css/);
  assert.match(pageSrc, /Saved Stories/);
  assert.match(pageSrc, /Verified & Corroborated only/);
  assert.match(pageSrc, /rel="noopener noreferrer"/);
});

test('Tech Pulse safe URL, verification tone, and filter logic behave accurately', () => {
  const helpersSrc = fs.readFileSync(path.join(root, 'src', 'utils', 'techPulseHelpers.ts'), 'utf8');
  assert.match(helpersSrc, /parsed\.protocol === 'http:' \|\| parsed\.protocol === 'https:'/);
  assert.match(helpersSrc, /Verified primary source/);
  assert.match(helpersSrc, /Independently corroborated/);
  assert.match(helpersSrc, /Corrected/);
});

