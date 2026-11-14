// Frontend unit tests for BRAINOVA Inline YouTube URL validation, sandbox security,
// and Focus Mode conditional tutorial-action policy.
// Run: node --test tests/frontend/youtube_embed.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import {
  extractYouTubeVideoId,
  getTutorialActionPolicy,
  isValidYouTubeVideoId,
  resolveYouTubeEmbed,
  validateExternalYouTubeUrl,
  YOUTUBE_EMBED_ALLOW,
  YOUTUBE_EMBED_SANDBOX,
} from '../../src/lib/youtubeEmbed.ts';

test('extracts valid 11-char video IDs from watch, youtu.be, embed, shorts, and mobile URLs', () => {
  assert.equal(extractYouTubeVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
  assert.equal(extractYouTubeVideoId('https://youtube.com/watch?v=abc_DEF-123&t=42s'), 'abc_DEF-123');
  assert.equal(extractYouTubeVideoId('https://m.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
  assert.equal(extractYouTubeVideoId('https://youtu.be/dQw4w9WgXcQ?si=test123'), 'dQw4w9WgXcQ');
  assert.equal(extractYouTubeVideoId('https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0'), 'dQw4w9WgXcQ');
  assert.equal(extractYouTubeVideoId('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
});

test('rejects untrusted domains, javascript:/data: URLs, malformed URLs, and invalid IDs', () => {
  for (const bad of [
    '',
    '   ',
    'not-a-url',
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'https://evil.example.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ',
    'https://vimeo.com/12345678901',
    'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/watch?v=too_long_id_12345',
    'https://www.youtube.com/watch?v=bad$char!12',
    'https://youtu.be/',
    'https://www.youtube.com/shorts/',
  ]) {
    assert.equal(extractYouTubeVideoId(bad), null, `Expected null for invalid URL: ${bad}`);
    assert.equal(validateExternalYouTubeUrl(bad, null), null, `Expected null for invalid URL: ${bad}`);
    if (bad.trim()) {
      assert.equal(
        validateExternalYouTubeUrl(bad, 'dQw4w9WgXcQ'),
        null,
        `Non-empty invalid URL must not fall back to videoId: ${bad}`
      );
    }
  }

  assert.equal(isValidYouTubeVideoId('dQw4w9WgXcQ'), true);
  assert.equal(isValidYouTubeVideoId('short'), false);
  assert.equal(isValidYouTubeVideoId('bad/char123'), false);
});

test('resolveYouTubeEmbed constructs privacy-enhanced youtube-nocookie.com embed URL', () => {
  const res = resolveYouTubeEmbed({ url: 'https://youtu.be/dQw4w9WgXcQ' });
  assert.equal(res.valid, true);
  if (res.valid) {
    assert.equal(res.videoId, 'dQw4w9WgXcQ');
    assert.equal(
      res.embedUrl,
      'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1&playsinline=1'
    );
  }

  const fallback = resolveYouTubeEmbed({ videoId: 'dQw4w9WgXcQ' });
  assert.equal(fallback.valid, true);

  const untrusted = resolveYouTubeEmbed({
    url: 'https://evil.example.com/watch?v=dQw4w9WgXcQ',
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(untrusted.valid, false);
});

test('iframe sandbox permits playback and fullscreen while forbidding top-level navigation and popups', () => {
  const tokens = new Set(YOUTUBE_EMBED_SANDBOX.split(/\s+/).filter(Boolean));
  assert.equal(tokens.has('allow-scripts'), true);
  assert.equal(tokens.has('allow-same-origin'), true);
  assert.equal(tokens.has('allow-presentation'), true);

  for (const forbidden of [
    'allow-top-navigation',
    'allow-top-navigation-by-user-activation',
    'allow-popups',
    'allow-popups-to-escape-sandbox',
  ]) {
    assert.equal(tokens.has(forbidden), false, `Forbidden sandbox token present: ${forbidden}`);
  }

  assert.match(YOUTUBE_EMBED_ALLOW, /fullscreen/);
  assert.match(YOUTUBE_EMBED_ALLOW, /encrypted-media/);
});

test('Focus Mode conditional tutorial-action policy covers inactive, active, completed, aborted, and recovery', () => {
  const validUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';

  // 1. Focus Mode inactive -> both Watch on YouTube and Play Inline Here available
  const inactive = getTutorialActionPolicy({
    focusPhase: 'idle',
    hasActiveSession: false,
    isReconciling: false,
    url: validUrl,
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(inactive.allowExternalWatch, true);
  assert.equal(inactive.externalWatchUrl, validUrl);
  assert.equal(inactive.isRestrictedByFocus, false);

  // 2. Focus Mode activating or active -> only inline playback allowed
  for (const phase of ['activating', 'active']) {
    const active = getTutorialActionPolicy({
      focusPhase: phase,
      hasActiveSession: true,
      isReconciling: false,
      url: validUrl,
      videoId: 'dQw4w9WgXcQ',
    });
    assert.equal(active.allowExternalWatch, false);
    assert.equal(active.isRestrictedByFocus, true);
    assert.equal(active.isFocusActive, true);
  }

  // 3. Focus Mode completed -> both actions restored immediately
  const completed = getTutorialActionPolicy({
    focusPhase: 'completed',
    hasActiveSession: false,
    isReconciling: false,
    url: validUrl,
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(completed.allowExternalWatch, true);
  assert.equal(completed.isRestrictedByFocus, false);

  // 4. Focus Mode manually stopped / aborted -> phase returns to idle, both actions restored
  const aborted = getTutorialActionPolicy({
    focusPhase: 'idle',
    hasActiveSession: false,
    isReconciling: false,
    url: validUrl,
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(aborted.allowExternalWatch, true);

  // 5. Session recovery in progress -> never briefly exposes external Watch on YouTube
  const recovering = getTutorialActionPolicy({
    focusPhase: 'idle',
    hasActiveSession: false,
    isReconciling: true,
    url: validUrl,
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(recovering.allowExternalWatch, false);
  assert.equal(recovering.isCheckingFocus, true);
  assert.equal(recovering.isRestrictedByFocus, true);

  // 6. Invalid / untrusted URL never generates external link even when Focus Mode is inactive
  const untrusted = getTutorialActionPolicy({
    focusPhase: 'idle',
    hasActiveSession: false,
    isReconciling: false,
    url: 'javascript:alert(1)',
    videoId: 'dQw4w9WgXcQ',
  });
  assert.equal(untrusted.allowExternalWatch, false);
  assert.equal(untrusted.externalWatchUrl, null);
});

test('all three Roadmap tutorial surfaces use YouTubeTutorialActions and InlineYouTubePlayer', () => {
  for (const relPath of [
    'src/pages/RoadmapDetailPage.tsx',
    'src/pages/TopicWorkspacePage.tsx',
    'src/pages/CustomizedRoadmapPage.tsx',
  ]) {
    const content = fs.readFileSync(path.resolve(relPath), 'utf8');
    assert.match(content, /YouTubeTutorialActions/, `${relPath} missing YouTubeTutorialActions`);
    assert.match(content, /InlineYouTubePlayer/, `${relPath} missing InlineYouTubePlayer`);
  }
});
