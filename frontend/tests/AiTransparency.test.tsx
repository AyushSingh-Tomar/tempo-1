import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { AiProgressBox } from '../src/components/ai/AiProgressBox';
import { AiResultNotice } from '../src/components/ai/AiResultNotice';
import { AiMappingOption } from '../src/components/ai/AiMappingOption';
import { aiStatusMeta } from '../src/utils/ai';
import type { AiInteraction, AiStatus } from '../src/api/types';

afterEach(() => {
  vi.useRealTimers();
});

function interaction(over: Partial<AiInteraction>): AiInteraction {
  return {
    id: 'i1',
    run_id: 'r1',
    purpose: 'MAPPING',
    status: 'ok',
    message: 'AI reviewed 18 unresolved column(s) and suggested a field for 5.',
    model: 'gpt-5-mini',
    provider: 'dial',
    latency_ms: 14300,
    timeout_seconds: 60,
    items_sent: 18,
    items_resolved: 5,
    created_at: null,
    ...over,
  };
}

describe('AiResultNotice', () => {
  it('shows what the AI did with model, time and counts', () => {
    render(<AiResultNotice interaction={interaction({})} itemNoun="columns" />);
    expect(screen.getByText('AI used')).toBeInTheDocument();
    expect(screen.getByText(/gpt-5-mini · 14.3 s · 5 of 18 columns/)).toBeInTheDocument();
  });

  it.each([
    ['timeout', 'AI timed out', true],
    ['rate_limited', 'AI limit reached', true],
    ['unavailable', 'AI unavailable', true],
    ['auth_error', 'AI key rejected', false],
    ['disabled', 'AI not configured', false],
  ])('explains a %s outcome and only offers retry when it could help', (status, label, retriable) => {
    const onRetry = vi.fn();
    render(
      <AiResultNotice
        interaction={interaction({ status, message: `reason for ${status}`, items_sent: 0, items_resolved: 0, latency_ms: 0 })}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(`reason for ${status}`)).toBeInTheDocument();
    expect(screen.getByText(/carry on without AI/i)).toBeInTheDocument();
    const retry = screen.queryByRole('button', { name: /try ai again/i });
    expect(!!retry).toBe(retriable);
    if (retry) {
      fireEvent.click(retry);
      expect(onRetry).toHaveBeenCalledOnce();
    }
  });

  it('knows every backend status', () => {
    for (const s of ['ok', 'disabled', 'skipped', 'timeout', 'rate_limited', 'auth_error', 'unavailable', 'bad_response', 'invalid_request', 'error']) {
      expect(aiStatusMeta(s).label).not.toMatch(/^AI: /);
    }
  });
});

describe('AiProgressBox', () => {
  it('counts the seconds and says when the AI is slower than expected', () => {
    vi.useFakeTimers();
    render(<AiProgressBox title="Asking the AI" timeoutSeconds={10} model="gpt-5-mini" />);
    expect(screen.getByRole('status')).toHaveTextContent('Asking the AI');
    expect(screen.getByRole('status')).toHaveTextContent('0s of up to 10s');
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByRole('status')).toHaveTextContent('4s of up to 10s');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '4');
    act(() => {
      vi.advanceTimersByTime(8000);
    });
    expect(screen.getByRole('status')).toHaveTextContent(/taking longer than expected/i);
    expect(screen.getByRole('status')).toHaveTextContent(/continues without AI/i);
  });
});

describe('AiMappingOption', () => {
  const available: AiStatus = { available: true, enabled: true, provider: 'dial', model: 'gpt-5-mini', timeout_seconds: 60, reason: null };

  it('lets the user opt out and states the wait and what is sent', () => {
    const onChange = vi.fn();
    render(<AiMappingOption status={available} loading={false} checked onChange={onChange} />);
    expect(screen.getByText(/up to about 60s/)).toBeInTheDocument();
    expect(screen.getByText(/you approve every one/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('explains why AI is unavailable and that nothing is blocked', () => {
    const off: AiStatus = { ...available, available: false, reason: 'AI is switched off (LLM_ENABLED=false).' };
    render(<AiMappingOption status={off} loading={false} checked onChange={() => undefined} />);
    expect(screen.getByText(/LLM_ENABLED=false/)).toBeInTheDocument();
    expect(screen.getByText(/nothing is blocked/i)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
});
