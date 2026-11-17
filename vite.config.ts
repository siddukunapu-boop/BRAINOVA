import fs from 'node:fs';
import path from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

function defaultAudioManifestPlugin(): Plugin {
  const writeManifest = () => {
    const defaultDir = path.resolve(__dirname, 'public', 'audio');
    const manifestPath = path.resolve(__dirname, 'backend', 'default_music_manifest.json');
    let entries: Array<{ filename: string; file_size: number }> = [];
    if (fs.existsSync(defaultDir)) {
      const files = fs
        .readdirSync(defaultDir, { withFileTypes: true })
        .filter((d) => d.isFile() && !d.name.startsWith('.') && d.name.toLowerCase().endsWith('.mp3'))
        .sort((a, b) => a.name.localeCompare(b.name));
      entries = files
        .map((d) => {
          const stat = fs.statSync(path.join(defaultDir, d.name));
          return { filename: d.name, file_size: stat.size };
        })
        .filter((e) => e.file_size > 0);
    }
    fs.writeFileSync(manifestPath, JSON.stringify(entries, null, 2) + '\n', 'utf-8');
  };

  return {
    name: 'default-audio-manifest',
    buildStart() {
      writeManifest();
    },
  };
}

export default defineConfig({
  plugins: [react(), defaultAudioManifestPlugin()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 750,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
});
