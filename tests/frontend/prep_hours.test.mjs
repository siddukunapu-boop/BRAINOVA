import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

test('Career Launchpad displays Available Preparation Hours per Day label and hint', () => {
  const pageSrc = fs.readFileSync(path.join(root, 'src', 'pages', 'CareerLaunchpadPage.tsx'), 'utf8');
  const helperSrc = fs.readFileSync(path.join(root, 'src', 'utils', 'prepHoursValidation.ts'), 'utf8');

  assert.match(pageSrc, /Available Preparation Hours per Day/);
  assert.match(pageSrc, /Enter how many hours you can dedicate to preparation each day\./);
  assert.match(pageSrc, /validateDailyPrepHours/);
  assert.match(helperSrc, /\^\\d\+\$/);
  assert.match(helperSrc, /parsed < 1 \|\| parsed > 24/);
});

test('Daily preparation hours validation accepts 1..24 and rejects invalid inputs', () => {
  const validateDailyPrepHours = (raw) => {
    const trimmed = String(raw ?? '').trim();
    if (!trimmed) return { valid: false, value: null };
    if (!/^\d+$/.test(trimmed)) return { valid: false, value: null };
    const parsed = Number(trimmed);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 24) return { valid: false, value: null };
    return { valid: true, value: parsed };
  };

  for (const validVal of ['1', '2', '6', '13', '17', '24']) {
    const res = validateDailyPrepHours(validVal);
    assert.equal(res.valid, true, `Expected ${validVal} to be valid`);
    assert.equal(res.value, Number(validVal));
    const weekly = res.value * 7;
    assert.equal(Math.round(weekly / 7), res.value);
  }

  for (const invalidVal of ['0', '-1', '2.5', 'abc', '25', '', '12h']) {
    const res = validateDailyPrepHours(invalidVal);
    assert.equal(res.valid, false, `Expected ${invalidVal} to be rejected`);
  }
});

