import { useQuery } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { api } from './api/endpoints';
import { router } from './router';

function AiStatusBanner() {
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    retry: 1,
    refetchInterval: 60000,
  });

  const llmStatus = typeof data?.checks?.llm === 'string' ? data.checks.llm : null;

  if (isError) {
    return (
      <div
        role="alert"
        className="border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      >
        AI status unavailable: the backend health check failed, so AI-assisted hints may be temporarily unavailable.
      </div>
    );
  }

  if (!llmStatus) return null;

  const bannerMap: Record<string, { tone: string; message: string }> = {
    configured: {
      tone: 'border-emerald-200 bg-emerald-50 text-emerald-900',
      message: 'AI hints are enabled and configured for this environment.',
    },
    not_configured: {
      tone: 'border-amber-200 bg-amber-50 text-amber-900',
      message:
        'AI hints are disabled because no LLM provider is configured. The deterministic workflow remains fully available.',
    },
    rate_limited: {
      tone: 'border-orange-200 bg-orange-50 text-orange-900',
      message:
        'AI provider rate limit or quota exhausted. The deterministic workflow continues without AI assistance.',
    },
    invalid_api_key: {
      tone: 'border-red-200 bg-red-50 text-red-900',
      message: 'AI provider rejected the API key or credentials. Please review the configured key before retrying.',
    },
    provider_unavailable: {
      tone: 'border-red-200 bg-red-50 text-red-900',
      message: 'AI provider is temporarily unavailable. The deterministic workflow remains active.',
    },
    provider_error: {
      tone: 'border-red-200 bg-red-50 text-red-900',
      message: 'AI provider returned a runtime error. Please retry later or review the provider configuration.',
    },
  };

  const banner = bannerMap[llmStatus] ?? {
    tone: 'border-slate-200 bg-slate-50 text-slate-800',
    message: `AI status: ${llmStatus}`,
  };

  return (
    <div role="alert" className={`border px-4 py-3 text-sm ${banner.tone}`}>
      {banner.message}
    </div>
  );
}

export function App() {
  return (
    <>
      <AiStatusBanner />
      <RouterProvider router={router} />
    </>
  );
}
