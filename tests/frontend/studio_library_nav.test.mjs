// Frontend navigation tests for AI Studio Library `?open=` synchronization.
// Run: node --test tests/frontend/studio_library_nav.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';

import { getRequestedOutputId, mergeFetchedOutput } from '../../src/lib/studioLibraryNav.ts';

test('getRequestedOutputId extracts open or output query param and trims blanks', () => {
  assert.equal(getRequestedOutputId(new URLSearchParams('?open=std_123')), 'std_123');
  assert.equal(getRequestedOutputId(new URLSearchParams('?output=std_456')), 'std_456');
  assert.equal(getRequestedOutputId(new URLSearchParams('?open=  std_789  ')), 'std_789');
  assert.equal(getRequestedOutputId(new URLSearchParams('')), null);
  assert.equal(getRequestedOutputId(new URLSearchParams('?open=   ')), null);
});

test('mergeFetchedOutput updates existing output in place or prepends new one', () => {
  const initial = [
    { id: 'std_1', title: 'Old 1' },
    { id: 'std_2', title: 'Old 2' },
  ];
  const updated = mergeFetchedOutput(initial, { id: 'std_2', title: 'New 2' });
  assert.deepEqual(updated, [
    { id: 'std_1', title: 'Old 1' },
    { id: 'std_2', title: 'New 2' },
  ]);

  const prepended = mergeFetchedOutput(initial, { id: 'std_3', title: 'Fresh 3' });
  assert.deepEqual(prepended, [
    { id: 'std_3', title: 'Fresh 3' },
    { id: 'std_1', title: 'Old 1' },
    { id: 'std_2', title: 'Old 2' },
  ]);
});

