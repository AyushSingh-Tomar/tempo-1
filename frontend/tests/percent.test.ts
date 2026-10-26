import { describe, expect, it } from 'vitest';
import { fractionToPercentDisplay, parseDecimalInput, percentInputToFraction } from '../src/utils/percent';

describe('percentInputToFraction', () => {
  it('converts a plain percentage-style number to a fraction', () => {
    expect(percentInputToFraction('25').fraction).toBe(0.25);
    expect(percentInputToFraction('25').error).toBeNull();
  });

  it('converts a value with a trailing % sign', () => {
    expect(percentInputToFraction('25%').fraction).toBe(0.25);
  });

  it('handles decimals', () => {
    expect(percentInputToFraction('12.5').fraction).toBeCloseTo(0.125);
  });

  it('rejects non-numeric input', () => {
    const result = percentInputToFraction('abc');
    expect(result.fraction).toBeNull();
    expect(result.error).toMatch(/number/i);
  });

  it('rejects values outside 0-100', () => {
    expect(percentInputToFraction('150').error).toMatch(/between 0 and 100/i);
    expect(percentInputToFraction('-5').error).toMatch(/between 0 and 100/i);
  });

  it('treats empty input as missing, required or not', () => {
    expect(percentInputToFraction('', { required: true }).error).toMatch(/required/i);
    expect(percentInputToFraction('', { required: false }).error).toBeNull();
    expect(percentInputToFraction('', { required: false }).fraction).toBeNull();
  });
});

describe('fractionToPercentDisplay', () => {
  it('converts a fraction back into the percentage users expect', () => {
    expect(fractionToPercentDisplay(0.25)).toBe('25');
    expect(fractionToPercentDisplay('0.125')).toBe('12.5');
  });

  it('round-trips through percentInputToFraction', () => {
    const { fraction } = percentInputToFraction('25');
    expect(fractionToPercentDisplay(fraction)).toBe('25');
  });

  it('handles null/undefined gracefully', () => {
    expect(fractionToPercentDisplay(null)).toBe('');
    expect(fractionToPercentDisplay(undefined)).toBe('');
  });
});

describe('parseDecimalInput (non-percentage fields like FX rate)', () => {
  it('does not scale the value', () => {
    expect(parseDecimalInput('1.1').fraction).toBe(1.1);
  });

  it('enforces a minimum when provided', () => {
    expect(parseDecimalInput('-1', { min: 0 }).error).toMatch(/at least 0/i);
  });
});
