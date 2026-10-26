import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// The API base URL is NOT configured here: it comes from VITE_API_BASE_URL
// (see .env.example) and is read at runtime in src/config/env.ts.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/setup.ts'],
    css: false,
    env: {
      VITE_API_BASE_URL: 'http://api.test',
      VITE_DEV_AUTH_TOKEN: 'dev-tester-reviewer',
    },
  },
});
