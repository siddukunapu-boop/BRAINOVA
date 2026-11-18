import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = path.resolve(import.meta.dirname, '..', '..');

test('CelebrationCursor is mounted globally once in App.tsx and imported in main.tsx', () => {
  const appTsx = fs.readFileSync(path.join(repoRoot, 'src', 'App.tsx'), 'utf-8');
  const mainTsx = fs.readFileSync(path.join(repoRoot, 'src', 'main.tsx'), 'utf-8');
  assert.match(appTsx, /<CelebrationCursor\s*\/>/);
  assert.match(mainTsx, /celebration-cursor\.css/);
});

test('CelebrationCursor enforces bounded particle pool, touch/reduced-motion guards, and pointer-events: none', () => {
  const cursorTsx = fs.readFileSync(
    path.join(repoRoot, 'src', 'components', 'CelebrationCursor.tsx'),
    'utf-8'
  );
  const cursorCss = fs.readFileSync(
    path.join(repoRoot, 'src', 'styles', 'celebration-cursor.css'),
    'utf-8'
  );

  assert.match(cursorTsx, /SPARKLE_POOL_SIZE\s*=\s*24/);
  assert.match(cursorTsx, /\(pointer: coarse\)/);
  assert.match(cursorTsx, /\(prefers-reduced-motion: reduce\)/);
  assert.match(cursorTsx, /data-reduced-motion/);
  assert.match(cursorTsx, /isTextEditableTarget/);
  assert.match(cursorTsx, /hasSpecializedNativeCursor/);
  assert.match(cursorCss, /pointer-events:\s*none;/);
  assert.match(cursorCss, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(cursorCss, /@media\s*\(hover:\s*none\),\s*\(pointer:\s*coarse\)/);
});
