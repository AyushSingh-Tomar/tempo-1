import type { MoneyRelationTerm, RelationFieldOption, TreatyFactorOption } from '../api/types';

export type LabelOf = (field: string) => string;

export function labelResolver(fields: RelationFieldOption[]): LabelOf {
  const map = new Map(fields.map((f) => [f.field, f.label]));
  return (field) => map.get(field) ?? field;
}

const FACTOR_WORDS: Record<string, string> = {
  commission_pct: 'commission %',
  brokerage_pct: 'brokerage %',
  tax_pct: 'tax %',
  cession_pct: 'cession %',
  order_pct: 'order %',
  fx_rate: 'FX rate',
};

export function factorText(factor: string, treaty: TreatyFactorOption[] = []): string {
  const word = FACTOR_WORDS[factor];
  if (!word) return factor; // a plain number
  const value = treaty.find((t) => t.name === factor)?.value;
  return value != null ? `${word} (${value})` : word;
}

/** "Net Premium = Gross Premium − Commission − Tax" with readable column labels. */
export function relationText(
  target: string,
  terms: MoneyRelationTerm[],
  labelOf: LabelOf,
  treaty: TreatyFactorOption[] = [],
): string {
  const parts = terms.map((t, i) => {
    const body = [labelOf(t.field), ...t.factors.map((f) => factorText(f, treaty))].join(' × ');
    if (i === 0) return t.sign > 0 ? body : `−${body}`;
    return `${t.sign > 0 ? '+' : '−'} ${body}`;
  });
  return `${labelOf(target)} = ${parts.join(' ')}`;
}

/** Treaty figures a relation needs that the user has not entered (fx_rate may come per currency, so it is not flagged). */
export function missingTreatyFigures(terms: MoneyRelationTerm[], treaty: TreatyFactorOption[]): string[] {
  const missing = new Set<string>();
  for (const t of terms) {
    for (const f of t.factors) {
      if (f === 'fx_rate' || !(f in FACTOR_WORDS)) continue;
      if (treaty.find((x) => x.name === f)?.value == null) missing.add(f);
    }
  }
  return [...missing];
}

export const TREATY_FACTOR_NAMES = Object.keys(FACTOR_WORDS);

export const ORIGIN_LABEL: Record<string, string> = {
  USER: 'Declared by you',
  STANDARD: 'Standard relation',
  AI_SUGGESTED: 'AI-suggested',
};
