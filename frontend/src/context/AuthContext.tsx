/**
 * AuthContext — Global autentifikatsiya holati
 *
 * Token localStorage da saqlanadi.
 * Barcha himoyalangan sahifalar shu context orqali tekshiriladi.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import config from '../config';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  role: 'admin' | 'manager' | 'viewer';
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

// ─── Storage keys ─────────────────────────────────────────────────────────────

const STORAGE_KEYS = {
  ACCESS_TOKEN:  'tv_access_token',
  REFRESH_TOKEN: 'tv_refresh_token',
  USER:          'tv_user',
} as const;

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user:            null,
    accessToken:     null,
    isAuthenticated: false,
    isLoading:       true,   // localStorage tekshirilguncha true
  });

  // Sahifa yuklanganda localStorage dan tiklash
  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    const raw   = localStorage.getItem(STORAGE_KEYS.USER);

    if (token && raw) {
      try {
        const user: AuthUser = JSON.parse(raw);
        setState({ user, accessToken: token, isAuthenticated: true, isLoading: false });
        return;
      } catch {
        // Buzilgan ma'lumot — tozalash
        localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.USER);
      }
    }

    setState(prev => ({ ...prev, isLoading: false }));
  }, []);

  // ── Login ─────────────────────────────────────────────────────────────────

  const login = useCallback(async (identifier: string, password: string) => {
    // identifier — email yoki username
    const isEmail = identifier.includes('@');

    const res = await fetch(`${config.apiUrl}/api/v1/auth/login`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        [isEmail ? 'email' : 'username']: identifier,
        password,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || 'Login amalga oshmadi.');
    }

    const data = await res.json();

    // Saqlash
    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN,  data.access_token);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token);
    localStorage.setItem(STORAGE_KEYS.USER,          JSON.stringify(data.user));

    setState({
      user:            data.user,
      accessToken:     data.access_token,
      isAuthenticated: true,
      isLoading:       false,
    });
  }, []);

  // ── Logout ────────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);

    // Backend ga logout xabari (token bekor qilish)
    if (token) {
      await fetch(`${config.apiUrl}/api/v1/auth/logout`, {
        method:  'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});  // Network xato bo'lsa ham local state tozalanadi
    }

    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);

    setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}