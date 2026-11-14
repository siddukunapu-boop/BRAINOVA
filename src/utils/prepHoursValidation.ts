export interface DailyPrepHoursValidation {
  valid: boolean;
  value: number | null;
  error: string;
}

export function weeklyToDailyHours(weeklyHours: number | undefined | null): number {
  const num = Number(weeklyHours);
  if (!Number.isFinite(num) || num <= 0) return 2;
  return Math.max(1, Math.min(24, Math.round(num / 7)));
}

export function dailyToWeeklyHours(dailyHours: number): number {
  return Math.max(1, Math.min(168, Math.round(dailyHours) * 7));
}

export function validateDailyPrepHours(raw: string): DailyPrepHoursValidation {
  const trimmed = String(raw ?? '').trim();
  if (!trimmed) {
    return {
      valid: false,
      value: null,
      error: 'Please enter a whole number of hours between 1 and 24.',
    };
  }
  if (!/^\d+$/.test(trimmed)) {
    return {
      valid: false,
      value: null,
      error: 'Use positive whole numbers only (1 to 24).',
    };
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 24) {
    return {
      valid: false,
      value: null,
      error: 'Enter a whole number between 1 and 24 hours per day.',
    };
  }
  return { valid: true, value: parsed, error: '' };
}

