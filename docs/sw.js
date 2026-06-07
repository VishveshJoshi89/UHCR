const CACHE_NAME = 'uhcr-docs-v1';
const BASE_URL = self.location.pathname.replace(/sw\.js$/, '');
const OFFLINE_URL = BASE_URL + 'offline.html';
const ASSETS = [
  BASE_URL,
  BASE_URL + 'index.html',
  BASE_URL + 'manifest.webmanifest',
  BASE_URL + 'favicon.svg',
  BASE_URL + 'assets/css/custom.css',
  BASE_URL + 'assets/js/custom.js',
  BASE_URL + 'assets/js/animations.js',
  BASE_URL + 'assets/icons/icon-192.png',
  BASE_URL + 'assets/icons/icon-512.png',
  BASE_URL + 'assets/icons/apple-touch-icon.png',
  OFFLINE_URL,
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const acceptHeader = event.request.headers.get('accept') || '';
  const isHtmlPage = event.request.mode === 'navigate' || acceptHeader.includes('text/html');

  if (isHtmlPage) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request).then(match => match || caches.match(OFFLINE_URL)))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cacheResponse => {
      return cacheResponse || fetch(event.request).then(networkResponse => {
        if (event.request.url.startsWith(self.location.origin + BASE_URL)) {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }
        return networkResponse;
      }).catch(() => {
        if (event.request.destination === 'image') {
          return new Response('', { status: 404 });
        }
      });
    })
  );
});
