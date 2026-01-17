// Install event
self.addEventListener("install", event => {
  self.skipWaiting(); // Activate worker immediately
});

// Activate event
self.addEventListener("activate", event => {
  clients.claim(); // Control all pages
});

// Fetch event (basic proxy for now)
self.addEventListener("fetch", event => {
  event.respondWith(fetch(event.request));
});
