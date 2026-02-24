/**
 * Taurus Vision — Markaziy API fetch utility
 *
 * Barcha API so'rovlari shu funksiya orqali o'tadi:
 *   - JWT access token avtomatik qo'shiladi
 *   - 401 → refresh token bilan yangi access token olishga urinish
 *   - Refresh ham ishlamasa → login sahifasiga yo'naltirish
 *   - JSON parse xatolarni ushlab olish
 *
 * TOKEN REFRESH OQIMI:
 *   1. API so'rovi → 401
 *   2. Refresh token mavjudmi? → POST /auth/refresh
 *   3. Yangi tokenlar saqlandi → asl so'rovni qayta yuborish
 *   4. Refresh ham 401 → localStorage tozalash → /login
 */

import config from '../config';

const STORAGE = {
  ACCESS:  'tv_access_token',
  REFRESH: 'tv_refresh_token',
  USER:    'tv_user',
} as const;

// Bir vaqtda faqat bitta refresh so'rovi bo'lishi uchun
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeToRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function notifySubscribers(token: string) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

/**
 * Refresh token yordamida yangi access token olish.
 *
 * Returns:
 *   Yangi access token string
 *
 * Throws:
 *   Error — refresh muvaffaqiyatsiz bo'lsa (foydalanuvchi logout bo'ladi)
 */
async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem(STORAGE.REFRESH);

  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const res = await fetch(`${config.apiUrl}/api/v1/auth/refresh`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    throw new Error('Token refresh failed');
  }

  const data = await res.json();

  // Yangi tokenlarni saqlash
  localStorage.setItem(STORAGE.ACCESS,  data.access_token);
  localStorage.setItem(STORAGE.REFRESH, data.refresh_token);
  if (data.user) {
    localStorage.setItem(STORAGE.USER, JSON.stringify(data.user));
  }

  return data.access_token;
}

/**
 * Foydalanuvchini tizimdan chiqarish va login sahifasiga yo'naltirish.
 */
function forceLogout(): void {
  localStorage.removeItem(STORAGE.ACCESS);
  localStorage.removeItem(STORAGE.REFRESH);
  localStorage.removeItem(STORAGE.USER);
  window.location.href = '/login';
}

/**
 * Barcha himoyalangan API so'rovlari uchun asosiy fetch funksiya.
 *
 * Args:
 *   path: API endpoint yo'li, masalan '/api/v1/animals'
 *   init: RequestInit (method, body, headers va h.k.)
 *
 * Returns:
 *   JSON javob T tipida
 *
 * Throws:
 *   Error — tarmoq xatosi yoki server xatosi
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const makeRequest = async (token: string | null) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(`${config.apiUrl}${path}`, { ...init, headers });
  };

  // Birinchi urinish
  const currentToken = localStorage.getItem(STORAGE.ACCESS);
  let res = await makeRequest(currentToken);

  // 401 → token refresh urinish
  if (res.status === 401) {
    if (isRefreshing) {
      // Boshqa refresh davom etayapti — uning tugashini kutish
      const newToken = await new Promise<string>((resolve, reject) => {
        subscribeToRefresh(resolve);
        // Agar refresh 10 sekunddan ko'p ketsa — reject
        setTimeout(() => reject(new Error('Refresh timeout')), 10_000);
      });

      res = await makeRequest(newToken);
    } else {
      isRefreshing = true;

      try {
        const newToken = await refreshAccessToken();
        notifySubscribers(newToken);
        res = await makeRequest(newToken);
      } catch {
        // Refresh muvaffaqiyatsiz → logout
        forceLogout();
        throw new Error('Sessiya muddati tugadi. Qayta login qiling.');
      } finally {
        isRefreshing = false;
      }
    }
  }

  // Refresh dan keyin ham 401 → logout
  if (res.status === 401) {
    forceLogout();
    throw new Error('Sessiya muddati tugadi. Qayta login qiling.');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || err.detail || `HTTP ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export default apiFetch;