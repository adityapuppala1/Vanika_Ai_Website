import { defineConfig } from 'vite';
import { resolve } from 'path';

// Custom plugin to rewrite URLs during local development
function cleanUrls() {
  return {
    name: 'clean-urls',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url.split('?')[0];
        
        if (url === '/demo' || url === '/admin') {
          req.url = `${url}.html`;
          return next();
        }
        
        // Vite internals (/@vite/client, /@fs/...) and source modules must pass through
        if (url !== '/' && !url.includes('.') && !url.startsWith('/@') && !url.startsWith('/src/') && !url.startsWith('/node_modules/')) {
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
        demo: resolve(__dirname, 'demo.html'),
        admin: resolve(__dirname, 'admin.html')
      }
    }
  }
});
