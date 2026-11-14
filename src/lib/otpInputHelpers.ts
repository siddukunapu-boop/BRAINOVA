export const OTP_DIGIT_COUNT = 6;

export function sanitizeOtpDigits(raw: string): string {
  return (raw || '').replace(/\D/g, '').slice(0, OTP_DIGIT_COUNT);
}

export function applyOtpDigitChange(
  digits: string[],
  index: number,
  rawValue: string
): { nextDigits: string[]; nextFocusIndex: number } {
  const clean = sanitizeOtpDigits(rawValue);
  const next = [...digits];
  while (next.length < OTP_DIGIT_COUNT) next.push('');

  if (!clean) {
    next[index] = '';
    return { nextDigits: next, nextFocusIndex: index };
  }

  // Handle multi-digit paste or autofill into any box
  if (clean.length > 1) {
    for (let i = 0; i < OTP_DIGIT_COUNT; i++) {
      next[i] = clean[i] ?? '';
    }
    const lastFilled = Math.min(clean.length, OTP_DIGIT_COUNT - 1);
    return { nextDigits: next, nextFocusIndex: lastFilled };
  }

  next[index] = clean[0];
  const nextFocus = Math.min(index + 1, OTP_DIGIT_COUNT - 1);
  return { nextDigits: next, nextFocusIndex: nextFocus };
}

export function applyOtpBackspace(
  digits: string[],
  index: number
): { nextDigits: string[]; nextFocusIndex: number } {
  const next = [...digits];
  while (next.length < OTP_DIGIT_COUNT) next.push('');

  if (next[index]) {
    next[index] = '';
    return { nextDigits: next, nextFocusIndex: index };
  }

  if (index > 0) {
    next[index - 1] = '';
    return { nextDigits: next, nextFocusIndex: index - 1 };
  }

  return { nextDigits: next, nextFocusIndex: 0 };
}

export function formatOtpCountdown(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

