/**
 * Taurus Vision — Token Store
 *
 * JWT tokenlarni xavfsiz saqlash uchun ikki qatlamli store:
 *   1. In-memory (har doim ishlaydi — asosiy manbaa)
 *   2. localStorage (sessiyalar orasida tiklanish uchun — fallback)
 *
 * NIMA UCHUN KERAK:
 *   - localStorage ba'zi muhitlarda (sandbox iframe, strict browser) o'chirilgan bo'ladi
 *   - In-memory store har doim ishlaydi
 *   - localStorage faqat "bonus" — yo'q bo'lsa ham tizim ishlaydi
 *
 * XAVFSIZLIK:
 *   - Tokenlar faqat shu modul orqali o'qiladi/yoziladi
 *   - Tashqi kod to'g'ridan localStorage ga murojaat qilmasin
 *   - clear() — logout da bir joydan barcha tokenlarni o'chirish
 */

const KEYS = {
  ACCESS:  'tv_access_token',
  REFRESH: 'tv_refresh_token',
  USER:    'tv_user',
} as const;

// ─── In-memory store ──────────────────────────────────────────────────────────
// Asosiy manbaa — hamma joyda ishlaydi

const _mem: Record<string, string> = {};

// ─── localStorage helpers ─────────────────────────────────────────────────────
// try-catch — localStorage o'chirilgan bo'lsa xato bermaydi

function lsGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

function lsSet(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* silent */ }
}

function lsRemove(key: string): void {
  try { localStorage.removeItem(key); } catch { /* silent */ }
}

// ─── Public API ───────────────────────────────────────────────────────────────

export const tokenStore = {
  /**
   * Token o'qish: avval in-memory, yo'q bo'lsa localStorage dan.
   */
  get(key: keyof typeof KEYS): string | null {
    const k = KEYS[key];
    return _mem[k] ?? lsGet(k);
  },

  /**
   * Token yozish: in-memory + localStorage ga bir vaqtda.
   */
  set(key: keyof typeof KEYS, value: string): void {
    const k = KEYS[key];
    _mem[k]  = value;
    lsSet(k, value);
  },

  /**
   * Token o'chirish: ikkala joydan ham.
   */
  remove(key: keyof typeof KEYS): void {
    const k = KEYS[key];
    delete _mem[k];
    lsRemove(k);
  },

  /**
   * Barcha tokenlarni o'chirish (logout uchun).
   */
  clear(): void {
    for (const key of Object.keys(KEYS) as Array<keyof typeof KEYS>) {
      this.remove(key);
    }
  },

  /**
   * Sahifa yuklanishida localStorage dan in-memory ga ko'chirish.
   * AuthProvider mount bo'lganda bir marta chaqiriladi.
   */
  hydrate(): { accessToken: string | null; user: string | null } {
    const accessToken = lsGet(KEYS.ACCESS);
    const refreshToken = lsGet(KEYS.REFRESH);
    const user = lsGet(KEYS.USER);

    if (accessToken) _mem[KEYS.ACCESS]  = accessToken;
    if (refreshToken) _mem[KEYS.REFRESH] = refreshToken;
    if (user)         _mem[KEYS.USER]    = user;

    return { accessToken, user };
  },
};