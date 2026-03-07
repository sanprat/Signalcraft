// Custom service worker for better PWA debugging
/* eslint-disable no-restricted-globals */

self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activated');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== 'static-resources' && cacheName !== 'api-cache') {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip chrome-extension and other non-http requests
  if (!event.request.url.startsWith('http')) return;

  // Handle manifest.json - always network first
  if (event.request.url.includes('/manifest.json')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          console.log('[Service Worker] Manifest fetched from network');
          return response;
        })
        .catch(() => {
          console.log('[Service Worker] Manifest fetch failed, returning cached');
          return caches.match(event.request);
        })
    );
    return;
  }

  // Handle API requests - network first
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const responseClone = response.clone();
          caches.open('api-cache').then((cache) => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Handle static resources - stale while revalidate
  if (event.request.url.match(/\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/)) {
    event.respondWith(
      caches.open('static-resources').then((cache) => {
        return cache.match(event.request).then((cached) => {
          const fetchPromise = fetch(event.request).then((networkResponse) => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
          return cached || fetchPromise;
        });
      })
    );
    return;
  }

  // Default - network first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const responseClone = response.clone();
        caches.open('static-resources').then((cache) => {
          cache.put(event.request, responseClone);
        });
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Handle PWA installation
self.addEventListener('beforeinstallprompt', (event) => {
  console.log('[Service Worker] beforeinstallprompt fired');
  event.preventDefault();
  self.clients.matchAll().then((clients) => {
    clients.forEach((client) => {
      client.postMessage({
        type: 'PWA_INSTALL_AVAILABLE',
        message: 'App installation available'
      });
    });
  });
});

// Handle successful installation
self.addEventListener('appinstalled', (event) => {
  console.log('[Service Worker] PWA installed successfully');
  self.clients.matchAll().then((clients) => {
    clients.forEach((client) => {
      client.postMessage({
        type: 'PWA_INSTALLED',
        message: 'App installed successfully'
      });
    });
  });
});
