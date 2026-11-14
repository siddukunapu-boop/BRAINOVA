import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  OTP_DIGIT_COUNT,
  applyOtpBackspace,
  applyOtpDigitChange,
  formatOtpCountdown,
  sanitizeOtpDigits,
} from '../../src/lib/otpInputHelpers.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..', '..');

test('sanitizeOtpDigits strips non-digits and clamps to 6 digits', () => {
  assert.equal(OTP_DIGIT_COUNT, 6);
  assert.equal(sanitizeOtpDigits('0a4-8 1b9c234'), '048192');
  assert.equal(sanitizeOtpDigits('abc'), '');
});

test('applyOtpDigitChange supports single-digit entry with auto-advance and full 6-digit paste', () => {
  let digits = Array(6).fill('');
  const step1 = applyOtpDigitChange(digits, 0, '0');
  assert.deepEqual(step1.nextDigits, ['0', '', '', '', '', '']);
  assert.equal(step1.nextFocusIndex, 1);

  const pasted = applyOtpDigitChange(step1.nextDigits, 1, '482913');
  assert.deepEqual(pasted.nextDigits, ['4', '8', '2', '9', '1', '3']);
  assert.equal(pasted.nextFocusIndex, 5);

  const pastedFromStart = applyOtpDigitChange(Array(6).fill(''), 0, '004819');
  assert.deepEqual(pastedFromStart.nextDigits, ['0', '0', '4', '8', '1', '9']);
  assert.equal(pastedFromStart.nextFocusIndex, 5);
});

test('applyOtpBackspace clears current digit or moves back to previous filled slot', () => {
  const filled = ['1', '2', '3', '', '', ''];
  const clearCurrent = applyOtpBackspace(filled, 2);
  assert.deepEqual(clearCurrent.nextDigits, ['1', '2', '', '', '', '']);
  assert.equal(clearCurrent.nextFocusIndex, 2);

  const moveBack = applyOtpBackspace(['1', '2', '', '', '', ''], 2);
  assert.deepEqual(moveBack.nextDigits, ['1', '', '', '', '', '']);
  assert.equal(moveBack.nextFocusIndex, 1);

  const atStart = applyOtpBackspace(['', '', '', '', '', ''], 0);
  assert.deepEqual(atStart.nextDigits, ['', '', '', '', '', '']);
  assert.equal(atStart.nextFocusIndex, 0);
});

test('formatOtpCountdown formats mm:ss accurately', () => {
  assert.equal(formatOtpCountdown(300), '05:00');
  assert.equal(formatOtpCountdown(65), '01:05');
  assert.equal(formatOtpCountdown(0), '00:00');
  assert.equal(formatOtpCountdown(-12), '00:00');
});

test('AuthPage wires strict Email OTP flow endpoints, sessionStorage recovery, and welcome transition', () => {
  const authPage = fs.readFileSync(path.join(repoRoot, 'src', 'pages', 'AuthPage.tsx'), 'utf8');
  assert.match(authPage, /\/api\/auth\/register/);
  assert.match(authPage, /\/api\/auth\/verify-email/);
  assert.match(authPage, /\/api\/auth\/resend-verification/);
  assert.match(authPage, /\/api\/auth\/pending-registration\//);
  assert.match(authPage, /sessionStorage/);
  assert.match(authPage, /brainova_pending_reg_token/);
  assert.match(authPage, /Welcome to BRAINOVA!/);
  assert.match(authPage, /Your email has been verified\. Your learning journey starts now\./);
});
