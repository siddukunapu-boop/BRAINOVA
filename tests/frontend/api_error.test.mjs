import test from 'node:test';
import assert from 'node:assert/strict';

import { ApiError, extractApiError } from '../../src/services/api.ts';

test('extractApiError unwraps structured FastAPI detail objects with code and message', () => {
  const payload = {
    detail: {
      code: 'llm_required_for_language',
      message:
        'Generating a source-grounded Audio Overview in Telugu requires an active Gemini, OpenAI, or Anthropic API key configured in Settings.',
    },
  };
  const parsed = extractApiError(payload, 422);
  assert.equal(parsed.code, 'llm_required_for_language');
  assert.match(parsed.message, /Telugu/);
  assert.match(parsed.message, /Settings/);
});

test('extractApiError preserves string details and falls back cleanly on empty payloads', () => {
  assert.deepEqual(extractApiError({ detail: 'Plain error' }, 400), {
    message: 'Plain error',
  });
  assert.deepEqual(extractApiError(null, 500), {
    message: 'Request failed (500)',
  });
});

test('ApiError stores status and optional structured code', () => {
  const err = new ApiError('Needs API key', 422, 'llm_required_for_language');
  assert.equal(err.message, 'Needs API key');
  assert.equal(err.status, 422);
  assert.equal(err.code, 'llm_required_for_language');
});

