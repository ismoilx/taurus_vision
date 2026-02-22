/**
 * Taurus Vision — Markaziy API fetch utility
 *
 * Barcha API so'rovlari shu funksiya orqali o'tadi:
 *   - JWT token avtomatik qo'shiladi
 *   - 401 → login sahifasiga yo'naltirish
 *   - JSON parse xatolarini ushlab olish
 */

import config from '../config';

const STORAGE_KEY = 'tv_access_token';

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = localStorage.getItem(STORAGE_KEY);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${config.apiUrl}${path}`, {
    ...init,
    headers,
  });

  // 401 — token muddati tugagan yoki yaroqsiz → loginга
  if (res.status === 401) {
    localStorage.removeItem('tv_access_token');
    localStorage.removeItem('tv_refresh_token');
    localStorage.removeItem('tv_user');
    window.location.href = '/login';
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