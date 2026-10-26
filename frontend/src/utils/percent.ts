/**
 * Treaty figure percentage fields are stored server-side as fractions
 * (0.25 for 25%) but users think and type in percentage terms ("25" or
 * "25%"). All conversion happens here, client-side, so the rest of the app
 * never has to think in fractions.
 */

export interface PercentParseResult {
  /** The fraction to send to the API (0-1), or null if the input was empty. */
  fraction: number | null;
  error: string | null;
}

/**
 * Parses a user-entered percentage string ("25", "25%", "12.5") into a
 * fraction (0.25, 0.25, 0.125). Returns a validation error for anything
 * outside the plausible 0-100% range or non-numeric input.
 */
export function percentInputToFraction(raw: string, opts: { required?: boolean } = {}): PercentParseResult {
  const trimmed = raw.trim();
  if (trimmed === '') {
    return { fraction: null, error: opts.required ? 'This field is required.' : null };
  }
  const cleaned = trimmed.replace(/%\s*$/, '');
  const value = Number(cleaned);
  if (!Number.isFinite(value)) {
    return { fraction: null, error: 'Enter a number, e.g. 25 for 25%.' };
  }
  const fraction = value / 100;
  if (fraction < 0 || fraction > 1) {
    return { fraction: null, error: 'Enter a percentage between 0 and 100.' };
  }
  return { fraction, error: null };
}

/** Formats a fraction (0.25) back into the percentage string users expect ("25"). */
export function fractionToPercentDisplay(fraction: number | string | null | undefined): string {
  if (fraction === null || fraction === undefined) return '';
  const n = typeof fraction === 'string' ? Number(fraction) : fraction;
  if (!Number.isFinite(n)) return '';
  // Avoid floating point artifacts like 24.999999999999996.
  const pct = Math.round(n * 100 * 1e6) / 1e6;
  return String(pct);
}

/** Non-percentage decimal fields (e.g. FX rate): validated but not scaled. */
export function parseDecimalInput(raw: string, opts: { required?: boolean; min?: number } = {}): PercentParseResult {
  const trimmed = raw.trim();
  if (trimmed === '') {
    return { fraction: null, error: opts.required ? 'This field is required.' : null };
  }
  const value = Number(trimmed);
  if (!Number.isFinite(value)) {
    return { fraction: null, error: 'Enter a valid number.' };
  }
  if (opts.min !== undefined && value < opts.min) {
    return { fraction: null, error: `Must be at least ${opts.min}.` };
  }
  return { fraction: value, error: null };
}
