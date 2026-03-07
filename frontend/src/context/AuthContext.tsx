/**
 * AuthContext — Global autentifikatsiya holati
 *
 * Tokenlar tokenStore orqali saqlanadi:
 *   - In-memory (har doim ishlaydi)
 *   - localStorage fallback (sessiyalar orasida tiklanish uchun)
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
import { tokenStore } from '../utils/tokenStore';

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

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user:            null,
    accessToken:     null,
    isAuthenticated: false,
    isLoading:       true,   // tokenStore tekshirilguncha true
  });

  // Sahifa yuklanganda tokenStore dan tiklash (localStorage → in-memory)
  useEffect(() => {
    const { accessToken, user: rawUser } = tokenStore.hydrate();

    if (accessToken && rawUser) {
      try {
        const user: AuthUser = JSON.parse(rawUser);
        setState({ user, accessToken, isAuthenticated: true, isLoading: false });
        return;
      } catch {
        // Buzilgan ma'lumot — tozalash
        tokenStore.clear();
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

    // Saqlash — in-memory + localStorage
    tokenStore.set('ACCESS',  data.access_token);
    tokenStore.set('REFRESH', data.refresh_token);
    tokenStore.set('USER',    JSON.stringify(data.user));

    setState({
      user:            data.user,
      accessToken:     data.access_token,
      isAuthenticated: true,
      isLoading:       false,
    });
  }, []);

  // ── Logout ────────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    const token = tokenStore.get('ACCESS');

    // Backend ga logout xabari (token bekor qilish)
    if (token) {
      await fetch(`${config.apiUrl}/api/v1/auth/logout`, {
        method:  'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});  // Network xato bo'lsa ham local state tozalanadi
    }

    tokenStore.clear();

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