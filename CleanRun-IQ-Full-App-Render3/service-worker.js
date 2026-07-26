const CACHE = "cleanrun-iq-shell-v26";
const SHELL = [
  "/",
  "/index.html",
  "/assets/favicon-32.png",
  "/assets/icon-192.png",
  "/assets/apple-touch-icon.png",
  "/assets/chevrons.svg",
  "/assets/enhancements.css?v=cards67",
  "/assets/enhancements.js?v=cards67",
  "/manifest.webmanifest",
];
const NETWORK_FIRST = new Set([
  "/",
  "/index.html",
  "/assets/enhancements.css",
  "/assets/enhancements.css?v=cards67",
  "/assets/enhancements.js",
  "/assets/enhancements.js?v=cards67",
  "/service-worker.js",
  "/manifest.webmanifest",
]);

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: "window", includeUncontrolled: true }))
      .then(clients => Promise.all(clients.map(client => client.navigate(client.url))))
  );
});

self.addEventListener("message", event => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

async function networkFirst(request, cacheKey = request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request, { cache: "no-store" });
    // Only cache successful responses (SW-01): caching a 401 here (e.g. an
    // expired /api/state token) means the next offline load replays that
    // stale 401, and the client's api() wrapper reads it as a real
    // "logged out" signal — logging an offline user out on cached data.
    if (response.ok) cache.put(cacheKey, response.clone());
    return response;
  } catch {
    return (await cache.match(cacheKey)) || Response.error();
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    if (url.pathname === "/api/state" || url.pathname.startsWith("/api/reports/")) {
      event.respondWith(networkFirst(request));
    }
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, "/"));
    return;
  }

  if (NETWORK_FIRST.has(url.pathname)) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(cacheFirst(request));
});
