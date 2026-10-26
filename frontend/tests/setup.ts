import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// @testing-library/react's auto-cleanup relies on detecting a global
// `afterEach`, which isn't present since this project's Vitest config does
// not set `test.globals: true`. Register it explicitly so each test starts
// with a clean DOM (otherwise text queries match leftover elements from
// previous renders).
afterEach(() => {
  cleanup();
});
