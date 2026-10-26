import { useState, type FormEvent } from 'react';
import type { DerivedFigure, DerivedTreatyInputs, FxRateEntry, TreatyFiguresRequest } from '../../api/types';
import { fractionToPercentDisplay, parseDecimalInput, percentInputToFraction } from '../../utils/percent';

interface FieldDef {
  key: 'commission_pct' | 'brokerage_pct' | 'tax_pct' | 'cession_pct' | 'order_pct';
  label: string;
  description: string;
  required: boolean;
}

const PERCENT_FIELDS: FieldDef[] = [
  {
    key: 'commission_pct',
    label: 'Commission %',
    description: 'The ceding commission percentage agreed in the treaty.',
    required: true,
  },
  {
    key: 'brokerage_pct',
    label: 'Brokerage %',
    description: 'The broker fee percentage, if separate from commission.',
    required: false,
  },
  {
    key: 'tax_pct',
    label: 'Tax / IPT %',
    description: 'Insurance premium tax or equivalent levy percentage.',
    required: true,
  },
  {
    key: 'cession_pct',
    label: 'Cession %',
    description: "The reinsurer's share of the risk ceded under the treaty.",
    required: true,
  },
  {
    key: 'order_pct',
    label: 'Order %',
    description: "This participant's order/signed share of the placement.",
    required: false,
  },
];

type FormState = Record<string, string>;

function pct(fraction: string): string {
  return `${fractionToPercentDisplay(fraction)}%`;
}

/** "Derived from file" badge, a not-found note, or an alert when the file disagrees with itself. */
function FigureSourceNote({ figure, edited }: { figure?: DerivedFigure; edited: boolean }) {
  if (!figure) return null;
  if (figure.status === 'NOT_FOUND') {
    return <p className="mt-1 text-xs text-slate-400">Not found in the file - enter it manually.</p>;
  }
  const badge = edited ? (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">Entered by you</span>
  ) : (
    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
      Derived from file{figure.source_column ? ` (${figure.source_column})` : ''}
    </span>
  );
  return (
    <div className="mt-1 space-y-1">
      <div>{badge}</div>
      {figure.status === 'VARIES' && (
        <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
          Not the same on all rows: {figure.distinct.map((d) => `${pct(d.value)} on ${d.row_count} row(s)`).join(', ')}.
          {figure.value ? ` ${pct(figure.value)} (the most common) is pre-filled - confirm the correct figure.` : ''}
          {figure.example_rows.length > 0 &&
            ` Differing rows: ${figure.example_rows.join(', ')}${figure.example_rows.length >= 8 ? ', ...' : ''}.`}
        </p>
      )}
    </div>
  );
}

interface FxRow {
  key: number;
  currency: string;
  rate: string;
  source: 'FILE' | 'USER';
}

function initialFxRows(derived: DerivedTreatyInputs | null): FxRow[] {
  return (derived?.currencies ?? []).map((c, i) => ({
    key: i,
    currency: c.currency,
    rate: c.rate ?? '',
    source: c.rate && c.source === 'FILE' ? 'FILE' : 'USER',
  }));
}

export function TreatyFiguresForm({
  derived = null,
  onSubmit,
  submitting,
  serverFieldErrors,
}: {
  derived?: DerivedTreatyInputs | null;
  onSubmit: (body: TreatyFiguresRequest) => void;
  submitting: boolean;
  serverFieldErrors?: Record<string, string>;
}) {
  const derivedFigures = Object.fromEntries((derived?.figures ?? []).map((f) => [f.figure, f]));
  const [values, setValues] = useState<FormState>(() =>
    Object.fromEntries(
      PERCENT_FIELDS.map((f) => {
        const d = derivedFigures[f.key];
        return [f.key, d && d.status !== 'NOT_FOUND' && d.value ? fractionToPercentDisplay(d.value) : ''];
      }),
    ),
  );
  // Which percentages still hold the value read from the file (edits make them the user's own).
  const [edited, setEdited] = useState<Record<string, boolean>>({});
  const [settlement, setSettlement] = useState(derived?.settlement_currency ?? '');
  const [fxRows, setFxRows] = useState<FxRow[]>(() => initialFxRows(derived));
  const [nextKey, setNextKey] = useState(1000);
  const [siRate, setSiRate] = useState('');
  const [touched, setTouched] = useState(false);
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  function updateFx(key: number, patch: Partial<FxRow>) {
    // Any edit makes the value the user's own, no longer "derived from file".
    setFxRows((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch, source: 'USER' } : r)));
  }

  function set(key: string, value: string) {
    setEdited((e) => ({ ...e, [key]: true }));
    setValues((v) => ({ ...v, [key]: value }));
  }

  function validate(): { body: TreatyFiguresRequest | null; errors: Record<string, string> } {
    const errors: Record<string, string> = {};
    const fractions: Record<string, number | null> = {};

    for (const field of PERCENT_FIELDS) {
      const { fraction, error } = percentInputToFraction(values[field.key], { required: field.required });
      if (error) errors[field.key] = error;
      fractions[field.key] = fraction;
    }

    const fxEntries: FxRateEntry[] = [];
    const seen = new Set<string>();
    const settle = settlement.trim().toUpperCase();
    if (fxRows.length > 0 && !/^[A-Z]{3}$/.test(settle)) errors.settlement_currency = 'Enter the 3-letter settlement currency (e.g. EUR).';
    for (const row of fxRows) {
      const code = row.currency.trim().toUpperCase();
      if (!/^[A-Z]{3}$/.test(code)) {
        errors.fx_rates = 'Every currency needs a 3-letter code.';
        continue;
      }
      if (seen.has(code)) {
        errors.fx_rates = `${code} is listed more than once.`;
        continue;
      }
      seen.add(code);
      const rate = code === settle && !row.rate.trim() ? { fraction: 1, error: null } : parseDecimalInput(row.rate, { required: true, min: 0 });
      if (rate.error || rate.fraction === null || rate.fraction <= 0) {
        errors.fx_rates = `Enter an FX rate greater than 0 for ${code}.`;
        continue;
      }
      fxEntries.push({ currency: code, rate: String(rate.fraction), source: row.source });
    }

    const si = percentInputToFraction(siRate, { required: false });
    if (si.error) errors.expected_si_rate = si.error;

    if (Object.keys(errors).length > 0) return { body: null, errors };

    const body: TreatyFiguresRequest = {
      commission_pct: String(fractions.commission_pct ?? 0),
      tax_pct: String(fractions.tax_pct ?? 0),
      cession_pct: String(fractions.cession_pct ?? 0),
      brokerage_pct: fractions.brokerage_pct !== null ? String(fractions.brokerage_pct) : null,
      order_pct: fractions.order_pct !== null ? String(fractions.order_pct) : null,
      expected_si_rate: si.fraction !== null ? String(si.fraction) : null,
      settlement_currency: fxEntries.length > 0 ? settle : null,
      fx_rates: fxEntries,
    };
    return { body, errors: {} };
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    const { body, errors } = validate();
    setClientErrors(errors);
    if (body) onSubmit(body);
  }

  const errors = { ...clientErrors, ...(serverFieldErrors ?? {}) };

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-5" noValidate>
      {PERCENT_FIELDS.map((field) => (
        <div key={field.key}>
          <label htmlFor={field.key} className="block text-sm font-medium text-slate-800">
            {field.label} {field.required && <span className="text-red-600">*</span>}
          </label>
          <p className="text-xs text-slate-500">{field.description}</p>
          <FigureSourceNote figure={derivedFigures[field.key]} edited={!!edited[field.key]} />
          <div className="mt-1 flex items-center gap-1">
            <input
              id={field.key}
              type="text"
              inputMode="decimal"
              placeholder="e.g. 25"
              value={values[field.key]}
              onChange={(e) => set(field.key, e.target.value)}
              aria-required={field.required}
              aria-invalid={touched && !!errors[field.key]}
              aria-describedby={errors[field.key] ? `${field.key}-error` : undefined}
              className="w-32 rounded border border-slate-300 px-2 py-1.5"
            />
            <span className="text-slate-500">%</span>
          </div>
          {touched && errors[field.key] && (
            <p id={`${field.key}-error`} role="alert" className="mt-1 text-xs text-red-700">
              {errors[field.key]}
            </p>
          )}
        </div>
      ))}

      <div>
        <label htmlFor="expected_si_rate" className="block text-sm font-medium text-slate-800">
          Expected premium rate on sum insured
        </label>
        <p className="text-xs text-slate-500">
          Optional. Your technical gross rate (e.g. 5 for 5% of sum insured). When given, a row whose gross premium is
          only about the cession % of the implied gross is flagged as a possible gross-is-ceded error (MCR-D1).
        </p>
        <div className="mt-1 flex items-center gap-1">
          <input
            id="expected_si_rate"
            type="text"
            inputMode="decimal"
            placeholder="e.g. 5"
            value={siRate}
            onChange={(e) => setSiRate(e.target.value)}
            aria-invalid={touched && !!errors.expected_si_rate}
            className="w-32 rounded border border-slate-300 px-2 py-1.5"
          />
          <span className="text-slate-500">%</span>
        </div>
        {touched && errors.expected_si_rate && (
          <p role="alert" className="mt-1 text-xs text-red-700">
            {errors.expected_si_rate}
          </p>
        )}
      </div>

      <fieldset className="space-y-3 rounded border border-slate-200 p-3">
        <legend className="px-1 text-sm font-medium text-slate-800">Currencies &amp; FX rates</legend>
        <p className="text-xs text-slate-500">
          One rate per currency, converting 1 unit of that currency into the settlement currency (e.g. 1 GBP = 1.175
          EUR). Values read from the uploaded file are marked <em>Derived from file</em>; you can change any of them.
        </p>
        <div>
          <label htmlFor="settlement_currency" className="block text-sm font-medium text-slate-800">
            Settlement currency
          </label>
          <input
            id="settlement_currency"
            type="text"
            placeholder="e.g. EUR"
            value={settlement}
            maxLength={3}
            onChange={(e) => setSettlement(e.target.value.toUpperCase())}
            aria-invalid={touched && !!errors.settlement_currency}
            className="mt-1 w-24 rounded border border-slate-300 px-2 py-1.5 uppercase"
          />
          {touched && errors.settlement_currency && (
            <p role="alert" className="mt-1 text-xs text-red-700">
              {errors.settlement_currency}
            </p>
          )}
        </div>

        {fxRows.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1 font-medium">Currency</th>
                <th className="py-1 font-medium">Rate</th>
                <th className="py-1 font-medium">Source</th>
                <th className="py-1" />
              </tr>
            </thead>
            <tbody>
              {fxRows.map((row) => (
                <tr key={row.key}>
                  <td className="py-1 pr-2">
                    <input
                      aria-label="Currency code"
                      value={row.currency}
                      maxLength={3}
                      onChange={(e) => updateFx(row.key, { currency: e.target.value.toUpperCase() })}
                      className="w-20 rounded border border-slate-300 px-2 py-1 uppercase"
                    />
                  </td>
                  <td className="py-1 pr-2">
                    <input
                      aria-label={`FX rate for ${row.currency || 'currency'}`}
                      inputMode="decimal"
                      value={row.rate}
                      onChange={(e) => updateFx(row.key, { rate: e.target.value })}
                      className="w-28 rounded border border-slate-300 px-2 py-1"
                    />
                  </td>
                  <td className="py-1 pr-2 text-xs">
                    {row.source === 'FILE' ? (
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-800">Derived from file</span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">Entered by you</span>
                    )}
                  </td>
                  <td className="py-1">
                    <button
                      type="button"
                      onClick={() => setFxRows((rows) => rows.filter((r) => r.key !== row.key))}
                      className="text-xs text-slate-500 underline hover:text-slate-800"
                      aria-label={`Remove ${row.currency || 'currency'}`}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {derived?.currencies.some((c) => c.conflicting_rates.length > 0) && (
          <p className="text-xs text-amber-800">
            The file lists more than one rate for{' '}
            {derived.currencies
              .filter((c) => c.conflicting_rates.length > 0)
              .map((c) => `${c.currency} (${c.conflicting_rates.join(', ')})`)
              .join('; ')}
            ; the most common one is pre-filled. Confirm the correct rate.
          </p>
        )}
        {fxRows.length === 0 && derived?.has_currency_column === false && (
          <p className="text-xs text-slate-500">
            No currency column was mapped, so none could be read from the file. Add currencies below if needed.
          </p>
        )}
        <button
          type="button"
          onClick={() => {
            setFxRows((rows) => [...rows, { key: nextKey, currency: '', rate: '', source: 'USER' }]);
            setNextKey((k) => k + 1);
          }}
          className="rounded border border-slate-300 px-2 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          + Add currency
        </button>
        {touched && errors.fx_rates && (
          <p role="alert" className="text-xs text-red-700">
            {errors.fx_rates}
          </p>
        )}
      </fieldset>

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
      >
        {submitting ? 'Submitting...' : 'Submit treaty figures'}
      </button>
      <p className="text-xs text-slate-500">* Required. Enter percentages as whole numbers (25 for 25%).</p>
    </form>
  );
}
