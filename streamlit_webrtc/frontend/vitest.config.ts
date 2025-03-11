import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(async () => {
  const viteTsconfigPaths = (await import('vite-tsconfig-paths')).default;
  
  return {
    plugins: [react(), viteTsconfigPaths()],
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.js'],
      transformIgnorePatterns: ['/node_modules/(?!streamlit-component-lib)'],
    },
  };
});
