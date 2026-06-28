const CACHE = "cleanrun-iq-shell-v22";
const SHELL = [
  "/",
  "/index.html",
  "/assets/icon-mark.png",
  "/assets/chevrons.svg",
  "/assets/enhancements.css?v=cards22",
  "/assets/enhancements.js?v=cards22",
  "/manifest.webmanifest",
];
const NETWORK_FIRST = new Set([
  "/",
  "/index.html",
  "/assets/enhancements.css",
  "/assets/enhancements.css?v=cards22",
  "/assets/enhancements.js",
  "/assets/enhancements.js?v=cards22",
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
    cache.put(cacheKey, response.clone());
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
  cache.put(request, response.clone());
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
