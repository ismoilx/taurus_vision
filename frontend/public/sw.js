/**
 * Taurus Vision — Service Worker (PWA)
 *
 * Strategiya:
 *   - App shell (HTML, CSS, JS) → Cache First (offline ishlaydi)
 *   - API so'rovlari → Network First (yangi ma'lumot, offline da cache)
 *   - Rasmlar → Cache First with network fallback
 *
 * Cache nomlanishi:
 *   tv-shell-v1   — statik fayllar (app shell)
 *   tv-api-v1     — API javoblari (qisqa muddatli)
 *   tv-images-v1  — rasmlar (uzun muddatli)
 *
 * YANGILANISH JARAYONI:
 *   Yangi SW o'rnatilganda → eski cache tozalanadi → yangi versiya faollashadi.
 */

const SHELL_CACHE    = 'tv-shell-v1';
const API_CACHE      = 'tv-api-v1';
const IMAGES_CACHE   = 'tv-images-v1';
const ALL_CACHES     = [SHELL_CACHE, API_CACHE, IMAGES_CACHE];

// App shell fayllar — har doim cache da bo'lishi kerak
const SHELL_URLS = [
  '/',
  '/offline.html',
];

// ─── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
      .catch((err) => console.warn('[SW] Install cache error:', err))
  );
});

// ─── Activate — eski cache larni tozalash ────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => !ALL_CACHES.includes(k))
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ─── Fetch — so'rovlarni ushlab olish ────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Chrome extension va non-http so'rovlarni o'tkazib yuborish
  if (!request.url.startsWith('http')) return;

  // WebSocket so'rovlarini o'tkazib yuborish
  if (request.headers.get('upgrade') === 'websocket') return;

  // ── API so'rovlari: Network First ──────────────────────────────────────────
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  // ── Rasm va media: Cache First ──────────────────────────────────────────────
  if (
    request.destination === 'image' ||
    url.pathname.match(/\.(png|jpg|jpeg|gif|webp|svg|ico)$/)
  ) {
    event.respondWith(cacheFirst(request, IMAGES_CACHE));
    return;
  }

  // ── App Shell (HTML, JS, CSS, fonts): Cache First ─────────────────────────
  event.respondWith(cacheFirst(request, SHELL_CACHE));
});

// ─── Strategiyalar ────────────────────────────────────────────────────────────

/**
 * Network First: tarmoqdan olishga urinadi, muvaffaqiyatsiz bo'lsa cache dan.
 * API so'rovlari uchun — har doim yangi ma'lumot kerak.
 */
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);

    // Muvaffaqiyatli GET so'rovlarni cache ga yozish
    if (networkResponse.ok && request.method === 'GET') {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch {
    // Tarmoq yo'q → cache dan
    const cached = await caches.match(request);
    if (cached) return cached;

    // Cache ham yo'q → offline sahifasi
    if (request.destination === 'document') {
      return caches.match('/offline.html') || offlineFallback();
    }

    // API uchun offline JSON
    return new Response(
      JSON.stringify({ error: 'Offline', message: 'Internet aloqasi yo\'q' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

/**
 * Cache First: avval cache dan, yo'q bo'lsa tarmoqdan.
 * Statik fayllar va rasmlar uchun — tez yuklash.
 */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch {
    // HTML so'rovi → offline sahifasi
    if (request.destination === 'document') {
      return caches.match('/offline.html') || offlineFallback();
    }
    return new Response('', { status: 503 });
  }
}

/**
 * Offline fallback — cache da ham yo'q bo'lsa.
 */
function offlineFallback() {
  return new Response(
    `<!DOCTYPE html>
    <html lang="uz">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Taurus Vision — Offline</title>
      <style>
        * { box-sizing: border-box; margin: 0; }
        body {
          min-height: 100vh; display: grid; place-items: center;
          background: #F7F8FA; font-family: 'Outfit', sans-serif;
          padding: 20px;
        }
        .card {
          background: white; border-radius: 16px; padding: 40px 32px;
          text-align: center; max-width: 360px; width: 100%;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08);
          border: 1px solid #E4E7ED;
        }
        .icon {
          width: 64px; height: 64px; margin: 0 auto 20px;
          background: #F7F8FA; border-radius: 16px;
          display: grid; place-items: center;
        }
        h1 { font-size: 20px; font-weight: 600; color: #0D1117; margin-bottom: 8px; }
        p  { font-size: 14px; color: #6B7280; line-height: 1.6; margin-bottom: 24px; }
        button {
          background: #1E3EB4; color: white; border: none;
          padding: 12px 28px; border-radius: 8px; font-size: 14px;
          font-weight: 500; cursor: pointer; font-family: inherit;
        }
        button:hover { background: #1a35a0; }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="1.5">
            <path d="M1 6l4-4 14 14-4 4zM1 18l4 4 14-14-4-4"/>
            <circle cx="18.5" cy="5.5" r="2.5" fill="none"/>
          </svg>
        </div>
        <h1>Internet aloqasi yo'q</h1>
        <p>Taurus Vision ga ulanish mumkin emas. Internet aloqangizni tekshiring va qayta urinib ko'ring.</p>
        <button onclick="window.location.reload()">Qayta urinish</button>
      </div>
    </body>
    </html>`,
    {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    }
  );
}

// ─── Message Handler — SKIP_WAITING ──────────────────────────────────────────
// usePWA hook dan keladi: "Yangilash" tugmasi bosilganda
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// ─── Push Notifications ───────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: 'Taurus Vision', body: event.data.text() };
  }

  const title   = data.title || 'Taurus Vision';
  const options = {
    body:    data.body || data.message || 'Yangi xabar',
    icon:    '/icons/icon-192.png',
    badge:   '/icons/icon-72.png',
    tag:     data.tag || 'tv-notification',
    renotify: true,
    data:    { url: data.url || '/' },
    actions: data.alert_id ? [
      { action: 'view',    title: 'Ko\'rish' },
      { action: 'dismiss', title: 'Yopish'   },
    ] : [],
    vibrate: data.severity === 'critical' ? [200, 100, 200, 100, 400] : [200],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ─── Notification Click ───────────────────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clients) => {
        // Mavjud tab bor → fokusga olish
        const existing = clients.find((c) => c.url.includes(self.location.origin));
        if (existing) {
          existing.focus();
          existing.navigate(targetUrl);
          return;
        }
        // Yo'q → yangi oyna ochish
        return self.clients.openWindow(targetUrl);
      })
  );
});