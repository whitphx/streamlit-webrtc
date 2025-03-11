import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(async () => {
  const viteTsconfigPaths = (await import('vite-tsconfig-paths')).default;
  
  return {
    plugins: [react(), viteTsconfigPaths()],
    server: {
      port: 3001,
      open: false,
    },
    build: {
      outDir: 'build',
    },
  };
});
