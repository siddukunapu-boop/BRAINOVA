import React, { useRef } from 'react';
import {
  applyOtpBackspace,
  applyOtpDigitChange,
  OTP_DIGIT_COUNT,
  sanitizeOtpDigits,
} from '../lib/otpInputHelpers';

interface OtpCodeInputProps {
  digits: string[];
  onChange: (nextDigits: string[]) => void;
  disabled?: boolean;
  hasError?: boolean;
}

export const OtpCodeInput: React.FC<OtpCodeInputProps> = ({
  digits,
  onChange,
  disabled = false,
  hasError = false,
}) => {
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  const focusBox = (idx: number) => {
    const clamped = Math.max(0, Math.min(OTP_DIGIT_COUNT - 1, idx));
    inputRefs.current[clamped]?.focus();
    inputRefs.current[clamped]?.select();
  };

  const handleChange = (index: number, value: string) => {
    const { nextDigits, nextFocusIndex } = applyOtpDigitChange(digits, index, value);
    onChange(nextDigits);
    if (value && nextFocusIndex !== index) {
      focusBox(nextFocusIndex);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const { nextDigits, nextFocusIndex } = applyOtpBackspace(digits, index);
      onChange(nextDigits);
      focusBox(nextFocusIndex);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      focusBox(index - 1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      focusBox(index + 1);
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = sanitizeOtpDigits(e.clipboardData.getData('text'));
    if (!pasted) return;
    e.preventDefault();
    const { nextDigits, nextFocusIndex } = applyOtpDigitChange(digits, 0, pasted);
    onChange(nextDigits);
    focusBox(nextFocusIndex);
  };

  return (
    <div
      className={`otp-boxes-row ${hasError ? 'is-error' : ''}`}
      role="group"
      aria-label="Six-digit verification code"
    >
      {Array.from({ length: OTP_DIGIT_COUNT }).map((_, idx) => (
        <input
          key={idx}
          ref={(el) => {
            inputRefs.current[idx] = el;
          }}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={OTP_DIGIT_COUNT}
          autoComplete={idx === 0 ? 'one-time-code' : 'off'}
          aria-label={`Verification digit ${idx + 1} of ${OTP_DIGIT_COUNT}`}
          className="otp-digit-box"
          value={digits[idx] || ''}
          disabled={disabled}
          onChange={(e) => handleChange(idx, e.target.value)}
          onKeyDown={(e) => handleKeyDown(idx, e)}
          onPaste={handlePaste}
          data-testid={`otp-digit-${idx}`}
        />
      ))}
    </div>
  );
};

