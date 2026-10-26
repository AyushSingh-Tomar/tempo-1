import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAiStatus } from '../../hooks/useAi';
import { SettingsDialog } from '../settings/SettingsDialog';
import { DevIdentitySwitcher } from './DevIdentitySwitcher';

function SettingsButton({ onClick }: { onClick: () => void }) {
  const { data } = useAiStatus();
  // A small dot says at a glance whether AI is usable; the detail lives in the dialog.
  const dot = data?.available ? 'bg-emerald-500' : 'bg-slate-300';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      className="flex items-center gap-1.5 rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
    >
      <span aria-hidden="true">⚙</span>
      Settings
      <span
        className={`h-2 w-2 rounded-full ${dot}`}
        role="img"
        aria-label={data?.available ? 'AI connected' : 'AI not connected'}
      />
    </button>
  );
}

/**
 * The one persistent application shell. Pages render inside `children`;
 * the sidebar slot (run progress) is supplied per-page since it only
 * applies while a run is open.
 */
export function AppShell({ sidebar, children }: { sidebar?: ReactNode; children: ReactNode }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 flex h-12 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4">
        <Link to="/" className="font-semibold text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500">
          Bordereaux Processing Accelerator
        </Link>
        <div className="flex items-center gap-4">
          <DevIdentitySwitcher />
          <SettingsButton onClick={() => setSettingsOpen(true)} />
        </div>
      </header>
      <div className="flex flex-1 items-start">
        {sidebar}
        <main id="main-content" className="flex-1 p-6">
          {children}
        </main>
      </div>
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
