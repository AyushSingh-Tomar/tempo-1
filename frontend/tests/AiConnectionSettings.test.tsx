import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AppShell } from '../src/components/shell/AppShell';
import { api } from '../src/api/endpoints';
import type { AiKeySaveResult, AiStatus } from '../src/api/types';

afterEach(() => vi.restoreAllMocks());

const base: AiStatus = {
  available: false,
  enabled: false,
  provider: 'dial',
  model: 'gpt-5-mini',
  timeout_seconds: 60,
  reason: 'AI is switched off (LLM_ENABLED=false).',
  key_source: 'none',
  user_key: { configured: false, hint: null, validated_at: null },
};
const withKey: AiStatus = {
  ...base,
  available: true,
  reason: null,
  key_source: 'user',
  user_key: { configured: true, hint: 'wxyz', validated_at: '2026-10-27T10:00:00Z' },
};

function mount(initial: AiStatus) {
  const status = vi.spyOn(api.ai, 'status').mockResolvedValue(initial);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AppShell>
          <p>page</p>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return status;
}

async function openSettings() {
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  return screen.findByRole('dialog', { name: 'Settings' });
}

describe('Settings -> AI connection', () => {
  it('opens from the header, shows the no-key state, and closes with Escape', async () => {
    mount(base);
    await openSettings();
    expect(await screen.findByText('No API key - AI features are off')).toBeInTheDocument();
    expect(screen.getByLabelText('AI not connected')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('keeps the key masked by default, with a show toggle and no autofill', async () => {
    mount(base);
    await openSettings();
    const input = screen.getByLabelText('Your API key') as HTMLInputElement;
    expect(input.type).toBe('password');
    expect(input.autocomplete).toBe('off');
    fireEvent.click(screen.getByRole('button', { name: 'Show' }));
    expect(input.type).toBe('text');
    expect(screen.getByRole('button', { name: /verify and save/i })).toBeDisabled();
  });

  it('verifies, saves, clears the field and never displays the key again', async () => {
    const status = mount(base);
    const save = vi.spyOn(api.ai.myKey, 'save').mockResolvedValue({
      ...withKey,
      saved: true,
      test: { status: 'ok', message: 'AI answered.', model: 'gpt-5-mini', latency_ms: 900 },
    } as AiKeySaveResult);
    await openSettings();
    const input = screen.getByLabelText('Your API key') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'sk-secret-1234567890-wxyz' } });
    status.mockResolvedValue(withKey);
    fireEvent.click(screen.getByRole('button', { name: /verify and save/i }));
    expect(await screen.findByText(/Key verified and saved/)).toBeInTheDocument();
    expect(save).toHaveBeenCalledWith('sk-secret-1234567890-wxyz', { skipTest: false });
    expect(input.value).toBe('');
    expect(await screen.findByText('Using your API key ending in wxyz')).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('sk-secret');
  });

  it('explains a rejected key and does not claim it was saved', async () => {
    mount(base);
    vi.spyOn(api.ai.myKey, 'save').mockResolvedValue({
      ...base,
      saved: false,
      test: { status: 'auth_error', message: 'The AI API key was rejected.', model: null, latency_ms: 300 },
    } as AiKeySaveResult);
    await openSettings();
    fireEvent.change(screen.getByLabelText('Your API key'), { target: { value: 'bad-key-12345678' } });
    fireEvent.click(screen.getByRole('button', { name: /verify and save/i }));
    expect(await screen.findByText('Key not saved.')).toBeInTheDocument();
    expect(screen.getByText('The AI API key was rejected.')).toBeInTheDocument();
    expect(screen.getByText('AI key rejected')).toBeInTheDocument();
    expect(screen.queryByText(/save it without testing/i)).toBeNull(); // pointless for a rejected key
  });

  it('offers "save without testing" only when the provider could not be reached', async () => {
    mount(base);
    const save = vi.spyOn(api.ai.myKey, 'save');
    save.mockResolvedValueOnce({
      ...base,
      saved: false,
      test: { status: 'unavailable', message: 'The AI provider is unreachable.', model: null, latency_ms: 0 },
    } as AiKeySaveResult);
    await openSettings();
    fireEvent.change(screen.getByLabelText('Your API key'), { target: { value: 'maybe-ok-12345678' } });
    fireEvent.click(screen.getByRole('button', { name: /verify and save/i }));
    fireEvent.click(await screen.findByRole('button', { name: /save it without testing/i }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith('maybe-ok-12345678', { skipTest: true }));
  });

  it('lets the user test and remove a saved key (with confirmation)', async () => {
    mount(withKey);
    const test = vi.spyOn(api.ai.myKey, 'test').mockResolvedValue({
      ...withKey,
      test: { status: 'rate_limited', message: 'The AI limit has been reached.', model: null, latency_ms: 10 },
    });
    const remove = vi.spyOn(api.ai.myKey, 'remove').mockResolvedValue({ ...base, removed: true });
    await openSettings();
    expect(await screen.findByText('Using your API key ending in wxyz')).toBeInTheDocument();
    expect(screen.getByLabelText('AI connected')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Test key' }));
    expect(await screen.findByText('The key could not be verified.')).toBeInTheDocument();
    expect(screen.getByText('The AI limit has been reached.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove my key' }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Yes, remove' }));
    await waitFor(() => expect(remove).toHaveBeenCalledOnce());
    expect(test).toHaveBeenCalledOnce();
    expect(await screen.findByText('Your key was removed.')).toBeInTheDocument();
  });

  it('says when the shared server key is in use', async () => {
    mount({ ...base, available: true, reason: null, key_source: 'server' });
    await openSettings();
    expect(await screen.findByText("Using the application's shared API key")).toBeInTheDocument();
  });
});
