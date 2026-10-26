import { useState } from 'react';
import { DEV_ROLES, buildDevToken, parseDevToken, setAuthToken, useAuthToken } from '../../stores/devAuth';

/**
 * Dev-only control to switch the `Authorization` header's user/role so
 * reviewer-only actions (overrides) can be exercised without a real auth
 * system. Not part of the production auth model.
 */
export function DevIdentitySwitcher() {
  const token = useAuthToken();
  const parsed = parseDevToken(token);
  const [userId, setUserId] = useState(parsed?.userId ?? 'analyst1');
  const [role, setRole] = useState(parsed?.role ?? 'analyst');

  function apply() {
    setAuthToken(buildDevToken(userId, role as (typeof DEV_ROLES)[number]));
  }

  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <label htmlFor="dev-user-id" className="sr-only">
        Dev user id
      </label>
      <input
        id="dev-user-id"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
        className="w-24 rounded border border-slate-300 px-1.5 py-1"
        aria-label="Dev user id"
      />
      <label htmlFor="dev-role" className="sr-only">
        Dev role
      </label>
      <select
        id="dev-role"
        value={role}
        onChange={(e) => setRole(e.target.value as (typeof DEV_ROLES)[number])}
        className="rounded border border-slate-300 px-1.5 py-1"
        aria-label="Dev role"
      >
        {DEV_ROLES.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={apply}
        className="rounded border border-slate-300 bg-white px-2 py-1 font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
      >
        Apply
      </button>
      <span className="hidden text-slate-400 sm:inline" title={token}>
        {token}
      </span>
    </div>
  );
}
