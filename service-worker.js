const CACHE = 'watchdog-shell-v8';
const SHELL = [
  './',
  './app.html',
  './index.html',
  './assistant.html',
  './map-intel.html',
  './exposure-scanner.html',
  './vehicle-intelligence.html',
  './scam-defense.html',
  './media-forensics.html',
  './privacy.html',
  './impersonation.html',
  './manifest.json',
  './app-icon.svg'
];

const SHELL_PATHS = new Set(SHELL.map(path => new URL(path, self.location.origin).pathname));

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  if (!SHELL_PATHS.has(url.pathname)) return;
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then(hit => hit || caches.match('./app.html')))
  );
});
