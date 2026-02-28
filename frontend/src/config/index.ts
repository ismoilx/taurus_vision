/**
 * Application configuration.
 *
 * Centralizes environment variables and app constants.
 *
 * VITE_API_URL va VITE_WS_URL — odatda bo'sh ("") qoldiriladi.
 * Bo'sh bo'lsa:
 *   - apiFetch "/api/..." nisbiy yo'ldan foydalanadi (Vite proksi yoki Nginx proksi)
 *   - WebSocket ham joriy host orqali bog'lanadi
 * Agar set qilingan bo'lsa (masalan "https://api.zxzx.uz") — to'g'ridan-to'g'ri ishlatiladi.
 */

// WebSocket URL ni dinamik hisoblash:
// - Agar VITE_WS_URL berilgan bo'lsa → uni ishlatamiz
// - Aks holda → joriy sahifa protokoli va hostidan quramiz
//   http://  → ws://   (lokal yoki HTTP server)
//   https:// → wss://  (SSL server)
function buildWsBaseUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicit) return explicit;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

export const config = {
  // API base URL.
  // Bo'sh ("") = nisbiy so'rovlar → Vite proksi (dev) yoki Nginx (prod) ishlaydi.
  // Set qilingan = to'g'ridan-to'g'ri o'sha URLga so'rov ketadi.
  apiUrl: (import.meta.env.VITE_API_URL as string) ?? '',

  // WebSocket base URL — dinamik hisoblanadi (yuqoridagi funksiya)
  get wsUrl(): string {
    return buildWsBaseUrl();
  },

  // Application
  appName:    (import.meta.env.VITE_APP_NAME    as string) ?? 'Taurus Vision',
  appVersion: (import.meta.env.VITE_APP_VERSION as string) ?? '0.1.0',

  // WebSocket reconnect settings (exponential backoff)
  ws: {
    reconnectInterval:    1000,   // Birinchi urinish: 1 soniya
    reconnectIntervalMax: 30000,  // Maksimum: 30 soniya
    reconnectDecay:       1.5,    // Eksponensial koeffitsient
    maxReconnectAttempts: 10,     // Shundan keyin to'xtaydi
  },

  // UI
  ui: {
    maxRecentMeasurements:  50,   // Live feed da saqlanadigan maksimal yozuvlar
    updateAnimationDuration: 300, // ms
  },
} as const;

export default config;