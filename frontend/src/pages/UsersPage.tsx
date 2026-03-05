/**
 * Taurus Vision — Users Page (Sprint 12)
 *
 * Foydalanuvchilar boshqaruvi. Faqat ADMIN uchun.
 *
 * IMKONIYATLAR:
 *   - Foydalanuvchilar ro'yxati (rol, holat, oxirgi login)
 *   - Yangi foydalanuvchi qo'shish
 *   - Rol o'zgartirish (admin/manager/viewer)
 *   - Bloklash / blokdan chiqarish
 *   - Parol tiklash (admin tomonidan)
 *   - Foydalanuvchi o'chirish (deactivate)
 *   - Qidirish va filtr
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users, Plus, Search, Shield, Eye, RefreshCw,
  AlertCircle, CheckCircle, XCircle, Lock,
  MoreVertical, UserCheck, UserX, Key,
  Crown, Settings, User,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UserData {
  id:            number;
  email:         string;
  username:      string;
  full_name:     string | null;
  role:          'admin' | 'manager' | 'viewer';
  is_active:     boolean;
  created_at:    string;
  last_login_at: string | null;
}

// ---------------------------------------------------------------------------
// Role config
// ---------------------------------------------------------------------------

const ROLE_CONFIG = {
  admin: {
    label:  'Admin',
    color:  '#7C3AED',
    bg:     '#F5F3FF',
    border: '#DDD6FE',
    icon:   Crown,
    desc:   "To'liq huquq",
  },
  manager: {
    label:  'Menejer',
    color:  '#1E3EB4',
    bg:     '#EEF2FF',
    border: '#C7D2FE',
    icon:   Settings,
    desc:   'Boshqaruv huquqi',
  },
  viewer: {
    label:  'Kuzatuvchi',
    color:  '#059669',
    bg:     '#F0FDF4',
    border: '#A7F3D0',
    icon:   Eye,
    desc:   "Faqat ko'rish",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

function getInitials(user: UserData): string {
  if (user.full_name) {
    return user.full_name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }
  return user.username.slice(0, 2).toUpperCase();
}

// ---------------------------------------------------------------------------
// Role Badge
// ---------------------------------------------------------------------------

function RoleBadge({ role }: { role: 'admin' | 'manager' | 'viewer' }) {
  const cfg = ROLE_CONFIG[role];
  const Icon = cfg.icon;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px',
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: 20,
    }}>
      <Icon size={11} color={cfg.color} />
      <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, letterSpacing: '0.03em' }}>
        {cfg.label}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add User Modal
// ---------------------------------------------------------------------------

function AddUserModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    username: '', email: '', full_name: '',
    password: '', role: 'viewer' as 'admin' | 'manager' | 'viewer',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [showPass, setShowPass] = useState(false);

  async function handleSubmit() {
    if (!form.username.trim() || !form.email.trim() || !form.password.trim()) {
      setError("Username, email va parol majburiy");
      return;
    }
    setLoading(true); setError('');
    try {
      await apiFetch('/api/v1/auth/users', {
        method: 'POST',
        body: JSON.stringify({
          username:  form.username,
          email:     form.email,
          full_name: form.full_name || null,
          password:  form.password,
          role:      form.role,
        }),
      });
      onSaved(); onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato yuz berdi');
    } finally { setLoading(false); }
  }

  const inp: React.CSSProperties = {
    width: '100%', padding: '10px 14px',
    border: '1px solid #D1D5DB', borderRadius: 8,
    fontSize: 14, color: '#0D1117', outline: 'none',
    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 480,
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #F3F4F6' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            Yangi foydalanuvchi qo'shish
          </h2>
        </div>

        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {error && (
            <div style={{
              display: 'flex', gap: 8, padding: '10px 14px',
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8,
            }}>
              <AlertCircle size={14} color="#DC2626" style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                Username *
              </label>
              <input type="text" value={form.username}
                onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                placeholder="john_doe" style={inp} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                Ism
              </label>
              <input type="text" value={form.full_name}
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                placeholder="John Doe" style={inp} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Email *
            </label>
            <input type="email" value={form.email}
              onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
              placeholder="john@farm.uz" style={inp} />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Parol *
            </label>
            <div style={{ position: 'relative' }}>
              <input type={showPass ? 'text' : 'password'} value={form.password}
                onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                placeholder="Kamida 8 ta belgi" style={{ ...inp, paddingRight: 44 }} />
              <button onClick={() => setShowPass(p => !p)} style={{
                position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF',
              }}>
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
              Rol
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {(['viewer', 'manager', 'admin'] as const).map(role => {
                const cfg = ROLE_CONFIG[role];
                const Icon = cfg.icon;
                const selected = form.role === role;
                return (
                  <button key={role} onClick={() => setForm(p => ({ ...p, role }))}
                    style={{
                      padding: '10px 8px',
                      border: `2px solid ${selected ? cfg.color : '#E5E7EB'}`,
                      borderRadius: 8, cursor: 'pointer',
                      background: selected ? cfg.bg : '#fff',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
                      transition: 'all .15s',
                    }}>
                    <Icon size={16} color={selected ? cfg.color : '#9CA3AF'} />
                    <span style={{ fontSize: 12, fontWeight: selected ? 700 : 500, color: selected ? cfg.color : '#6B7280' }}>
                      {cfg.label}
                    </span>
                    <span style={{ fontSize: 10, color: '#9CA3AF' }}>{cfg.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 10 }}>
          <button onClick={onClose} disabled={loading} style={{
            flex: 1, padding: '10px', border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            Bekor
          </button>
          <button onClick={handleSubmit} disabled={loading} style={{
            flex: 2, padding: '10px',
            background: loading ? '#9CA3AF' : '#1E3EB4',
            border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 14, fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            {loading ? "Qo'shilmoqda..." : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// EyeOff inline
function EyeOff({ size, ...props }: { size: number; [key: string]: any }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Reset Password Modal
// ---------------------------------------------------------------------------

function ResetPasswordModal({
  user, onClose,
}: { user: UserData; onClose: () => void }) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState(false);

  async function handleReset() {
    if (password.length < 8) { setError("Parol kamida 8 ta belgi bo'lishi kerak"); return; }
    if (!/[A-Z]/.test(password)) { setError("Parol kamida 1 ta katta harf (A-Z) bo'lishi kerak"); return; }
    if (!/[a-z]/.test(password)) { setError("Parol kamida 1 ta kichik harf (a-z) bo'lishi kerak"); return; }
    if (!/\d/.test(password)) { setError("Parol kamida 1 ta raqam bo'lishi kerak"); return; }
    if (password !== confirm) { setError("Parollar mos kelmaydi"); return; }
    setLoading(true); setError('');
    try {
      await apiFetch(`/api/v1/auth/users/${user.id}/reset-password`, {
        method: 'POST',
        body: JSON.stringify({ new_password: password }),
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally { setLoading(false); }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 400,
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #F3F4F6' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Key size={16} color="#1E3EB4" />
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: 0 }}>
              Parol tiklash
            </h2>
          </div>
          <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0' }}>
            {user.username} uchun yangi parol
          </p>
        </div>

        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {success ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
              padding: '24px', textAlign: 'center',
            }}>
              <CheckCircle size={40} color="#10B981" />
              <p style={{ fontSize: 14, color: '#065F46', fontWeight: 600, margin: 0 }}>
                Parol muvaffaqiyatli yangilandi!
              </p>
              <button onClick={onClose} style={{
                marginTop: 8, padding: '8px 24px',
                background: '#1E3EB4', color: '#fff', border: 'none',
                borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                fontFamily: 'Outfit, sans-serif',
              }}>
                Yopish
              </button>
            </div>
          ) : (
            <>
              {error && (
                <div style={{
                  display: 'flex', gap: 8, padding: '10px 14px',
                  background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8,
                }}>
                  <AlertCircle size={14} color="#DC2626" />
                  <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
                </div>
              )}
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                  Yangi parol
                </label>
                <input type="password" value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Kamida 8 ta belgi"
                  style={{
                    width: '100%', padding: '10px 14px',
                    border: '1px solid #D1D5DB', borderRadius: 8,
                    fontSize: 14, color: '#0D1117', outline: 'none',
                    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
                  }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                  Tasdiqlash
                </label>
                <input type="password" value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  placeholder="Parolni qaytaring"
                  style={{
                    width: '100%', padding: '10px 14px',
                    border: `1px solid ${confirm && confirm !== password ? '#FECACA' : '#D1D5DB'}`,
                    borderRadius: 8, fontSize: 14, color: '#0D1117', outline: 'none',
                    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
                  }} />
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                <button onClick={onClose} style={{
                  flex: 1, padding: '10px', border: '1px solid #D1D5DB', borderRadius: 8,
                  background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600,
                  cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                }}>
                  Bekor
                </button>
                <button onClick={handleReset} disabled={loading} style={{
                  flex: 2, padding: '10px',
                  background: loading ? '#9CA3AF' : '#1E3EB4',
                  border: 'none', borderRadius: 8,
                  color: '#fff', fontSize: 14, fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontFamily: 'Outfit, sans-serif',
                }}>
                  {loading ? 'Saqlanmoqda...' : 'Parolni Yangilash'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// User Row Actions Menu
// ---------------------------------------------------------------------------

function UserActions({
  user,
  currentUserId,
  onRoleChange,
  onToggleActive,
  onResetPassword,
}: {
  user:             UserData;
  currentUserId:    number;
  onRoleChange:     (id: number, role: 'admin' | 'manager' | 'viewer') => void;
  onToggleActive:   (user: UserData) => void;
  onResetPassword:  (user: UserData) => void;
}) {
  const [open, setOpen] = useState(false);
  const isSelf = user.id === currentUserId;

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen(p => !p)} style={{
        padding: '6px 8px', background: 'none',
        border: '1px solid #E5E7EB', borderRadius: 7,
        cursor: 'pointer', display: 'flex', alignItems: 'center',
        color: '#6B7280',
      }}>
        <MoreVertical size={14} />
      </button>

      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setOpen(false)} />
          <div style={{
            position: 'absolute', right: 0, top: 'calc(100% + 4px)',
            minWidth: 200, background: '#fff',
            border: '1px solid #E4E7ED', borderRadius: 10,
            boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
            zIndex: 50, overflow: 'hidden',
          }}>
            {/* Rol o'zgartirish */}
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #F3F4F6' }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Rol o'zgartirish
              </p>
            </div>
            {(['viewer', 'manager', 'admin'] as const).map(role => {
              const cfg = ROLE_CONFIG[role];
              const Icon = cfg.icon;
              const isCurrent = user.role === role;
              return (
                <button key={role} onClick={() => { onRoleChange(user.id, role); setOpen(false); }}
                  disabled={isCurrent || isSelf}
                  style={{
                    width: '100%', padding: '8px 14px',
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: isCurrent ? cfg.bg : 'none',
                    border: 'none', cursor: isCurrent || isSelf ? 'default' : 'pointer',
                    fontSize: 13, color: isCurrent ? cfg.color : '#374151',
                    fontFamily: 'Outfit, sans-serif',
                    opacity: isSelf ? 0.4 : 1,
                  }}>
                  <Icon size={13} color={isCurrent ? cfg.color : '#9CA3AF'} />
                  {cfg.label}
                  {isCurrent && <span style={{ marginLeft: 'auto', fontSize: 10, color: cfg.color }}>✓ joriy</span>}
                </button>
              );
            })}

            <div style={{ borderTop: '1px solid #F3F4F6' }}>
              {/* Parol tiklash */}
              <button onClick={() => { onResetPassword(user); setOpen(false); }}
                style={{
                  width: '100%', padding: '9px 14px',
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 13, color: '#374151', fontFamily: 'Outfit, sans-serif',
                }}>
                <Key size={13} color="#6B7280" />
                Parol tiklash
              </button>

              {/* Bloklash / blokdan chiqarish */}
              {!isSelf && (
                <button onClick={() => { onToggleActive(user); setOpen(false); }}
                  style={{
                    width: '100%', padding: '9px 14px',
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 13, fontFamily: 'Outfit, sans-serif',
                    color: user.is_active ? '#DC2626' : '#059669',
                  }}>
                  {user.is_active
                    ? <><UserX size={13} /> Bloklash</>
                    : <><UserCheck size={13} /> Blokdan chiqarish</>}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function UsersPage() {
  const qClient = useQueryClient();
  const [search, setSearch]         = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [showAdd, setShowAdd]       = useState(false);
  const [resetUser, setResetUser]   = useState<UserData | null>(null);
  const [toast, setToast]           = useState('');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const invalidate = () => qClient.invalidateQueries({ queryKey: ['users'] });

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: usersData, isLoading: loading, isError, error } = useQuery({
    queryKey: ['users'],
    queryFn:  () => apiFetch<{ items: UserData[]; total: number }>('/api/v1/auth/users'),
  });
  const users = usersData?.items ?? [];

  const { data: meData } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn:  () => apiFetch<{ id: number }>('/api/v1/auth/me'),
  });
  const currentUserId = meData?.id ?? 0;

  // ── Mutations ─────────────────────────────────────────────────────────────
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      apiFetch(`/api/v1/auth/users/${userId}`, { method: 'PUT', body: JSON.stringify({ role }) }),
    onSuccess: () => { invalidate(); showToast("✅ Rol muvaffaqiyatli o'zgartirildi"); },
    onError:   (e: Error) => showToast('❌ ' + e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: (user: UserData) => {
      const ep = user.is_active
        ? `/api/v1/auth/users/${user.id}/deactivate`
        : `/api/v1/auth/users/${user.id}/activate`;
      return apiFetch(ep, { method: 'POST' });
    },
    onSuccess: (_d, user) => {
      invalidate();
      showToast(user.is_active ? '🔒 Foydalanuvchi bloklandi' : '✅ Blok olib tashlandi');
    },
    onError: (e: Error) => showToast('❌ ' + e.message),
  });

  const handleRoleChange   = (userId: number, role: 'admin'|'manager'|'viewer') => roleMutation.mutate({ userId, role });
  const handleToggleActive = (user: UserData) => toggleMutation.mutate(user);

  // Filter
  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    const matchSearch = !q
      || u.username.toLowerCase().includes(q)
      || u.email.toLowerCase().includes(q)
      || (u.full_name || '').toLowerCase().includes(q);
    const matchRole = roleFilter === 'all' || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  // Stats
  const stats = {
    total:   users.length,
    active:  users.filter(u => u.is_active).length,
    admins:  users.filter(u => u.role === 'admin').length,
    managers: users.filter(u => u.role === 'manager').length,
    viewers: users.filter(u => u.role === 'viewer').length,
  };

  return (
    <div style={{
      maxWidth: 1200, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 100,
          padding: '12px 20px',
          background: '#0D1117', color: '#fff',
          borderRadius: 10, fontSize: 14, fontWeight: 500,
          boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
          animation: 'fadeIn .2s ease',
        }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
            Foydalanuvchilar
          </h1>
          <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
            {stats.total} ta foydalanuvchi · {stats.active} ta faol
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => qClient.invalidateQueries({ queryKey: ["users"] })} style={{
            padding: '9px 12px', border: '1px solid #D1D5DB',
            borderRadius: 8, background: '#fff', cursor: 'pointer',
            display: 'flex', alignItems: 'center',
          }}>
            <RefreshCw size={15} color="#6B7280"
              style={{ animation: loading ? 'spin .7s linear infinite' : 'none' }} />
          </button>
          <button onClick={() => setShowAdd(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 18px',
            background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={16} />
            Foydalanuvchi qo'shish
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Jami',      value: stats.total,    icon: Users,    color: '#1E3EB4', bg: '#EEF2FF' },
          { label: 'Faol',      value: stats.active,   icon: CheckCircle, color: '#10B981', bg: '#ECFDF5' },
          { label: 'Admin',     value: stats.admins,   icon: Crown,    color: '#7C3AED', bg: '#F5F3FF' },
          { label: 'Menejer',   value: stats.managers, icon: Settings, color: '#1E3EB4', bg: '#EEF2FF' },
          { label: 'Kuzatuvchi', value: stats.viewers, icon: Eye,      color: '#059669', bg: '#F0FDF4' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} style={{
            background: '#fff', border: '1px solid #E4E7ED',
            borderRadius: 12, padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: bg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
              <Icon size={16} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280' }}>{label}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#0D1117' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={14} color="#9CA3AF" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text" value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Username, email yoki ism qidirish..."
            style={{
              width: '100%', padding: '10px 12px 10px 36px',
              border: '1px solid #D1D5DB', borderRadius: 8,
              fontSize: 13, outline: 'none', boxSizing: 'border-box',
              fontFamily: 'Outfit, sans-serif',
            }}
          />
        </div>

        {/* Role filter */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { key: 'all',     label: 'Hammasi' },
            { key: 'admin',   label: 'Admin' },
            { key: 'manager', label: 'Menejer' },
            { key: 'viewer',  label: 'Kuzatuvchi' },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => setRoleFilter(key)} style={{
              padding: '8px 14px',
              border: `1px solid ${roleFilter === key ? '#1E3EB4' : '#D1D5DB'}`,
              borderRadius: 8, background: roleFilter === key ? '#EEF2FF' : '#fff',
              color: roleFilter === key ? '#1E3EB4' : '#6B7280',
              fontSize: 13, fontWeight: roleFilter === key ? 700 : 500,
              cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
            }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {isError && (
        <div style={{
          display: 'flex', gap: 10, padding: '12px 16px',
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: 10, marginBottom: 20,
        }}>
          <AlertCircle size={16} color="#DC2626" />
          <span style={{ fontSize: 13, color: '#DC2626' }}>{error instanceof Error ? error.message : 'Xato'}</span>
        </div>
      )}

      {/* Table */}
      <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, overflow: 'hidden' }}>

        {/* Table header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1.5fr 80px',
          padding: '12px 20px',
          background: '#F9FAFB',
          borderBottom: '1px solid #E4E7ED',
          gap: 12,
        }}>
          {['Foydalanuvchi', 'Email', 'Rol', 'Holat', 'Oxirgi login', ''].map((h, i) => (
            <div key={i} style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {h}
            </div>
          ))}
        </div>

        {/* Rows */}
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
            Yuklanmoqda...
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center' }}>
            <Users size={36} color="#D1D5DB" style={{ margin: '0 auto 12px' }} />
            <p style={{ color: '#9CA3AF', fontSize: 14, margin: 0 }}>
              {search || roleFilter !== 'all' ? 'Qidiruv natijasi topilmadi' : 'Hali foydalanuvchi qo\'shilmagan'}
            </p>
          </div>
        ) : filtered.map((user, idx) => {
          const isSelf = user.id === currentUserId;
          return (
            <div key={user.id} style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1.5fr 80px',
              padding: '14px 20px',
              borderBottom: idx < filtered.length - 1 ? '1px solid #F3F4F6' : 'none',
              alignItems: 'center', gap: 12,
              background: isSelf ? '#FAFBFF' : '#fff',
              transition: 'background .1s',
            }}
              onMouseEnter={e => { if (!isSelf) e.currentTarget.style.background = '#FAFAFA'; }}
              onMouseLeave={e => { e.currentTarget.style.background = isSelf ? '#FAFBFF' : '#fff'; }}
            >
              {/* Avatar + name */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 38, height: 38, borderRadius: 9,
                  background: ROLE_CONFIG[user.role].bg,
                  border: `1px solid ${ROLE_CONFIG[user.role].border}`,
                  display: 'grid', placeItems: 'center',
                  fontSize: 13, fontWeight: 700, color: ROLE_CONFIG[user.role].color,
                  flexShrink: 0,
                }}>
                  {getInitials(user)}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>
                    {user.full_name || user.username}
                    {isSelf && (
                      <span style={{
                        marginLeft: 8, fontSize: 10, color: '#1E3EB4',
                        background: '#EEF2FF', padding: '1px 6px', borderRadius: 10,
                      }}>
                        Siz
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>
                    @{user.username}
                  </div>
                </div>
              </div>

              {/* Email */}
              <div style={{ fontSize: 13, color: '#6B7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.email}
              </div>

              {/* Role */}
              <div><RoleBadge role={user.role} /></div>

              {/* Status */}
              <div>
                {user.is_active ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#10B981' }} />
                    <span style={{ fontSize: 12, color: '#059669', fontWeight: 600 }}>Faol</span>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#9CA3AF' }} />
                    <span style={{ fontSize: 12, color: '#9CA3AF', fontWeight: 600 }}>Bloklangan</span>
                  </div>
                )}
              </div>

              {/* Last login */}
              <div style={{ fontSize: 12, color: '#9CA3AF' }}>
                {formatDate(user.last_login_at)}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <UserActions
                  user={user}
                  currentUserId={currentUserId}
                  onRoleChange={handleRoleChange}
                  onToggleActive={handleToggleActive}
                  onResetPassword={setResetUser}
                />
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length > 0 && (
        <p style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', marginTop: 12 }}>
          {filtered.length} ta ko'rsatilmoqda · {users.length} ta jami
        </p>
      )}

      {/* Modals */}
      {showAdd && (
        <AddUserModal
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); invalidate(); showToast("✅ Foydalanuvchi qo'shildi!"); }}
        />
      )}
      {resetUser && (
        <ResetPasswordModal
          user={resetUser}
          onClose={() => setResetUser(null)}
        />
      )}

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes fadeIn  { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}