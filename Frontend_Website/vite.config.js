import { defineConfig } from 'vite';
import { resolve } from 'path';

// Custom plugin to rewrite URLs during local development
function cleanUrls() {
  return {
    name: 'clean-urls',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url.split('?')[0];
        
        if (url === '/demo') {
          req.url = '/demo.html';
          return next();
        }
        
        if (url !== '/' && !url.includes('.')) {
          // Unknown navigation path, redirect to root
          res.writeHead(302, { Location: '/' });
          res.end();
          return;
        }
        
        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [cleanUrls()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        demo: resolve(__dirname, 'demo.html')
      }
    }
  }
});
