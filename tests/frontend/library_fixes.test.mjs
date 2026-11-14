// Frontend regression tests using Node's built-in test runner (no new dependencies).
// Run: node --test tests/frontend/library_fixes.test.mjs   (Node >= 22.18 strips TypeScript types)
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  sourceTitleText,
  normalizeSourceTitles,
  sourceTitlesMatch,
  safeLabel,
} from '../../src/lib/sourceTitles.ts';
import { ErrorBoundary, ErrorFallback } from '../../src/components/ErrorBoundary.ts';

// Mirrors the Library card logic: normalize, then show at most two titles truncated to 26 chars.
const cardLabels = (entries) => normalizeSourceTitles(entries).slice(0, 2).map((t) => t.slice(0, 26));

test('backend-shaped source objects render their title (the crash case)', () => {
  const entries = [{ id: 'src_1', title: 'Raft Consensus Architecture Notes', file_type: '.md' }];
  assert.deepEqual(cardLabels(entries), ['Raft Consensus Architectur']);
});

test('two-source limit and 26-character truncation are preserved', () => {
  const entries = [
    { id: '1', title: 'A'.repeat(40), file_type: '.md' },
    { id: '2', title: 'Second', file_type: '.txt' },
    { id: '3', title: 'Third', file_type: '.pdf' },
  ];
  const labels = cardLabels(entries);
  assert.equal(labels.length, 2);
  assert.equal(labels[0].length, 26);
  assert.equal(labels[1], 'Second');
});

test('legacy string entries still work', () => {
  assert.deepEqual(cardLabels(['Legacy Notes', 'Other']), ['Legacy Notes', 'Other']);
  assert.equal(sourceTitleText('  padded  '), 'padded');
});

test('empty and malformed entries are dropped without throwing', () => {
  const malformed = [null, undefined, '', '   ', 42, {}, { title: 123 }, { title: null }, [], { id: 'x' }];
  assert.deepEqual(normalizeSourceTitles(malformed), []);
  assert.deepEqual(normalizeSourceTitles(null), []);
  assert.deepEqual(normalizeSourceTitles(undefined), []);
  assert.deepEqual(normalizeSourceTitles('not-an-array'), []);
  assert.deepEqual(normalizeSourceTitles({ title: 'x' }), []);
  assert.deepEqual(cardLabels([null, { title: 'Valid' }, 7]), ['Valid']);
});

test('search matches object titles and legacy strings, never "[object Object]"', () => {
  const objs = [{ id: '1', title: 'Raft Consensus Notes', file_type: '.md' }];
  assert.equal(sourceTitlesMatch(objs, 'raft'), true);
  assert.equal(sourceTitlesMatch(objs, 'consensus'), true);
  assert.equal(sourceTitlesMatch(objs, 'paxos'), false);
  assert.equal(sourceTitlesMatch(['Legacy Raft'], 'raft'), true);
  assert.equal(sourceTitlesMatch(objs, 'object'), false);
  assert.equal(sourceTitlesMatch(objs, '[object'), false);
  assert.equal(sourceTitlesMatch([null, {}, 5], 'raft'), false);
  assert.equal(sourceTitlesMatch(undefined, 'raft'), false);
});

test('safeLabel guards missing and non-string mind-map labels', () => {
  assert.equal(safeLabel('Distributed Consensus', 20), 'Distributed Consensus'.slice(0, 20));
  assert.equal(safeLabel(undefined, 20), '');
  assert.equal(safeLabel(null, 22), '');
  assert.equal(safeLabel(123, 25), '');
  assert.equal(safeLabel({ text: 'x' }, 25), '');
});

test('ErrorFallback shows a useful message with retry and reload actions', () => {
  const html = renderToStaticMarkup(
    React.createElement(ErrorFallback, { error: new Error('slice is not a function'), onRetry: () => {} })
  );
  assert.match(html, /Something went wrong/);
  assert.match(html, /slice is not a function/);
  assert.match(html, /Try again/);
  assert.match(html, /Reload page/);
  assert.match(html, /role="alert"/);
});

test('ErrorBoundary converts a thrown error into fallback state and renders children otherwise', () => {
  const err = new Error('boom');
  assert.deepEqual(ErrorBoundary.getDerivedStateFromError(err), { error: err });

  const ok = renderToStaticMarkup(
    React.createElement(ErrorBoundary, null, React.createElement('p', null, 'healthy child'))
  );
  assert.match(ok, /healthy child/);

  const boundary = new ErrorBoundary({ children: React.createElement('p', null, 'child') });
  boundary.state = { error: err };
  const fallback = renderToStaticMarkup(boundary.render());
  assert.match(fallback, /boom/);
  assert.match(fallback, /Try again/);
});

