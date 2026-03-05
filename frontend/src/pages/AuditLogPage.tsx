/**
 * Taurus Vision — Audit Log Page
 *
 * Tizim xavfsizlik loglari. Faqat ADMIN uchun.
 *
 * IMKONIYATLAR:
 *   - Barcha login/logout/parol o'zgarish voqealarini ko'rish
 *   - Filtr: event_type, severity, username
 *   - Sahifalash
 *   - Real-time yangilanish (30s)
 *   - Voqea detail modal
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Shield, Search, RefreshCw, ChevronLeft, ChevronRight,
  LogIn, LogOut, Key, User, AlertTriangle, Activity,
  CheckCircle, XCircle, Clock, Filter, Eye, X,
  UserCheck, UserX, Lock,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuditLogEntry {
  id: number;
  event_type: string;
  severity: string;
  user_id: number | null;
  username: string | null;
  ip_address: string;
  user_agent: string | null;
  endpoint: string | null;
  http_method: string | null;
  details: Record<string, unknown> | null;
  occurred_at: string;
}

interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ─── Config ───────────────────────────────────────────────────────────────────

const EVENT_CONFIG: Record<string, { label: string; icon: typeof LogIn; color: string; bg: string }> = {
  LOGIN_SUCCESS:     { label: 'Login muvaffaqiyatli', icon: LogIn,       color: '#059669', bg: '#ECFDF5' },
  LOGIN_FAILED:      { label: 'Login muvaffaqiyatsiz', icon: XCircle,     color: '#DC2626', bg: '#FEF2F2' },
  LOGIN_LOCKED:      { label: 'Hisob bloklandi',       icon: Lock,        color: '#7C3AED', bg: '#F5F3FF' },
  LOGOUT:            { label: 'Chiqish',               icon: LogOut,      color: '#6B7280', bg: '#F9FAFB' },
  TOKEN_REFRESH:     { label: 'Token yangilandi',      icon: RefreshCw,   color: '#0891B2', bg: '#ECFEFF' },
  PASSWORD_CHANGED:  { label: 'Parol o\'zgardi',       icon: Key,         color: '#D97706', bg: '#FFFBEB' },
  USER_CREATED:      { label: 'Foydalanuvchi yaratildi', icon: UserCheck, color: '#1E3EB4', bg: '#EEF2FF' },
  USER_UPDATED:      { label: 'Foydalanuvchi yangilandi', icon: User,     color: '#1E3EB4', bg: '#EEF2FF' },
  USER_ACTIVATED:    { label: 'Foydalanuvchi faollashtirildi', icon: UserCheck, color: '#059669', bg: '#ECFDF5' },
  USER_DEACTIVATED:  { label: 'Foydalanuvchi bloklandi', icon: UserX,    color: '#DC2626', bg: '#FEF2F2' },
  PERMISSION_DENIED: { label: 'Ruxsat rad etildi',     icon: AlertTriangle, color: '#DC2626', bg: '#FEF2F2' },
  SUSPICIOUS:        { label: 'Shubhali faollik',      icon: AlertTriangle, color: '#7C3AED', bg: '#F5F3FF' },
};

const SEVERITY_CONFIG = {
  info:     { label: 'Info',     color: '#0891B2', bg: '#ECFEFF', border: '#A5F3FC' },
  warning:  { label: 'Ogohlantirish', color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  critical: { label: 'Kritik',   color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
};

const EVENT_TYPES = Object.entries(EVENT_CONFIG).map(([key, v]) => ({ key, label: v.label }));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return format(new Date(iso), 'dd.MM.yyyy HH:mm:ss');
  } catch { return iso; }
}

function timeAgo(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch { return ''; }
}

function shortUA(ua: string | null): string {
  if (!ua) return '—';
  if (ua.includes('Chrome')) return 'Chrome';
  if (ua.includes('Firefox')) return 'Firefox';
  if (ua.includes('Safari')) return 'Safari';
  if (ua.includes('curl')) return 'cURL';
  return ua.slice(0, 30) + '...';
}

// ─── Detail Modal ─────────────────────────────────────────────────────────────

function DetailModal({ entry, onClose }: { entry: AuditLogEntry; onClose: () => void }) {
  const cfg = EVENT_CONFIG[entry.event_type] ?? EVENT_CONFIG.LOGIN_SUCCESS;
  const Icon = cfg.icon;
  const sev = SEVERITY_CONFIG[entry.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 520,
        maxHeight: '90vh', overflow: 'auto',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid #F3F4F6',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: cfg.bg, display: 'grid', placeItems: 'center',
            }}>
              <Icon size={16} color={cfg.color} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>{cfg.label}</div>
              <div style={{ fontSize: 12, color: '#6B7280' }}>ID: #{entry.id}</div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          }}>
            <X size={18} color="#6B7280" />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Severity badge */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={{
              padding: '4px 10px', borderRadius: 6,
              background: sev.bg, color: sev.color,
              border: `1px solid ${sev.border}`,
              fontSize: 12, fontWeight: 700,
            }}>
              {sev.label.toUpperCase()}
            </span>
            <span style={{
              padding: '4px 10px', borderRadius: 6,
              background: '#F1F5F9', color: '#475569',
              fontSize: 12, fontWeight: 600,
            }}>
              {entry.event_type}
            </span>
          </div>

          {/* Info grid */}
          {[
            { label: 'Foydalanuvchi', value: entry.username ?? '—' },
            { label: 'IP manzil', value: entry.ip_address },
            { label: 'Vaqt', value: formatDate(entry.occurred_at) },
            { label: 'Endpoint', value: entry.endpoint ?? '—' },
            { label: 'Metod', value: entry.http_method ?? '—' },
            { label: 'Brauzer', value: entry.user_agent ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} style={{
              display: 'grid', gridTemplateColumns: '130px 1fr', gap: 8,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#6B7280' }}>{label}</span>
              <span style={{
                fontSize: 13, color: '#0D1117',
                wordBreak: 'break-all',
              }}>{value}</span>
            </div>
          ))}

          {/* Details JSON */}
          {entry.details && Object.keys(entry.details).length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#6B7280', marginBottom: 6 }}>
                Qo'shimcha ma'lumotlar
              </div>
              <pre style={{
                background: '#F8FAFC', border: '1px solid #E2E8F0',
                borderRadius: 8, padding: '12px 14px',
                fontSize: 12, color: '#334155',
                overflow: 'auto', maxHeight: 160,
                margin: 0, fontFamily: 'monospace',
              }}>
                {JSON.stringify(entry.details, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div style={{ padding: '12px 24px', borderTop: '1px solid #F3F4F6', textAlign: 'right' }}>
          <button onClick={onClose} style={{
            padding: '8px 20px', background: '#1E3EB4', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 700,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            Yopish
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AuditLogPage() {
  const [page, setPage]             = useState(1);
  const [eventType, setEventType]   = useState('');
  const [severity, setSeverity]     = useState('');
  const [username, setUsername]     = useState('');
  const [inputUser, setInputUser]   = useState('');
  const [selected, setSelected]     = useState<AuditLogEntry | null>(null);
  const [showFilter, setShowFilter] = useState(false);

  const { data, isLoading, isError, refetch, isFetching } = useQuery<AuditLogListResponse>({
    queryKey: ['audit-logs', page, eventType, severity, username],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), size: '50' });
      if (eventType) params.set('event_type', eventType);
      if (severity)  params.set('severity', severity);
      if (username)  params.set('username', username);
      return apiFetch<AuditLogListResponse>(`/api/v1/auth/audit-logs?${params}`);
    },
    refetchInterval: 30_000,
  });

  // Stats from data
  const items    = data?.items ?? [];
  const total    = data?.total ?? 0;
  const pages    = data?.pages ?? 1;
  const critical = items.filter(i => i.severity === 'critical').length;
  const warning  = items.filter(i => i.severity === 'warning').length;
  const failed   = items.filter(i => i.event_type === 'LOGIN_FAILED').length;

  function applyFilter() {
    setUsername(inputUser);
    setPage(1);
  }
  function clearFilter() {
    setEventType(''); setSeverity(''); setUsername(''); setInputUser(''); setPage(1);
  }
  const hasFilter = !!(eventType || severity || username);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: '24px', minHeight: '100vh', background: '#F8FAFC' }}>

      {/* Page Header */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: '#1E3EB4', display: 'grid', placeItems: 'center',
            }}>
              <Shield size={18} color="#fff" />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#0D1117', margin: 0 }}>
              Xavfsizlik Audit Logi
            </h1>
          </div>
          <p style={{ fontSize: 13, color: '#6B7280', margin: 0, paddingLeft: 46 }}>
            Tizimda ro'y bergan barcha xavfsizlik voqealari — Kim, Nima, Qachon
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px', border: '1px solid #E4E7ED',
            borderRadius: 10, background: '#fff', cursor: 'pointer',
            fontSize: 13, fontWeight: 600, color: '#374151',
          }}
        >
          <RefreshCw size={14} style={{ animation: isFetching ? 'spin 1s linear infinite' : 'none' }} />
          Yangilash
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
        {[
          { label: "Jami (joriy sahifa)", value: total, icon: Activity,      color: '#1E3EB4', bg: '#EEF2FF' },
          { label: 'Kritik voqealar',      value: critical, icon: AlertTriangle, color: '#DC2626', bg: '#FEF2F2' },
          { label: 'Ogohlantirishlar',      value: warning,  icon: Clock,        color: '#D97706', bg: '#FFFBEB' },
          { label: "Xato loginlar",         value: failed,   icon: XCircle,      color: '#DC2626', bg: '#FEF2F2' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} style={{
            background: '#fff', border: '1px solid #E4E7ED',
            borderRadius: 12, padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 8,
              background: bg, display: 'grid', placeItems: 'center', flexShrink: 0,
            }}>
              <Icon size={17} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>{label}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#0D1117' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 12, padding: '14px 16px',
        marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <button
          onClick={() => setShowFilter(!showFilter)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', border: `1px solid ${hasFilter ? '#1E3EB4' : '#E4E7ED'}`,
            borderRadius: 8, background: hasFilter ? '#EEF2FF' : '#fff',
            cursor: 'pointer', fontSize: 13, fontWeight: 600,
            color: hasFilter ? '#1E3EB4' : '#374151',
          }}
        >
          <Filter size={13} />
          Filtr {hasFilter && '(aktiv)'}
        </button>

        {showFilter && (
          <>
            <select
              value={eventType}
              onChange={e => { setEventType(e.target.value); setPage(1); }}
              style={{
                padding: '7px 12px', border: '1px solid #E4E7ED',
                borderRadius: 8, fontSize: 13, color: '#374151',
                background: '#fff', cursor: 'pointer',
              }}
            >
              <option value="">Barcha voqealar</option>
              {EVENT_TYPES.map(({ key, label }) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>

            <select
              value={severity}
              onChange={e => { setSeverity(e.target.value); setPage(1); }}
              style={{
                padding: '7px 12px', border: '1px solid #E4E7ED',
                borderRadius: 8, fontSize: 13, color: '#374151',
                background: '#fff', cursor: 'pointer',
              }}
            >
              <option value="">Barcha daraja</option>
              <option value="info">Info</option>
              <option value="warning">Ogohlantirish</option>
              <option value="critical">Kritik</option>
            </select>

            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={inputUser}
                onChange={e => setInputUser(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && applyFilter()}
                placeholder="Username qidirish..."
                style={{
                  padding: '7px 12px', border: '1px solid #E4E7ED',
                  borderRadius: 8, fontSize: 13, color: '#374151',
                  outline: 'none', width: 180,
                }}
              />
              <button onClick={applyFilter} style={{
                padding: '7px 12px', border: 'none',
                background: '#1E3EB4', borderRadius: 8,
                color: '#fff', cursor: 'pointer',
              }}>
                <Search size={14} />
              </button>
            </div>

            {hasFilter && (
              <button onClick={clearFilter} style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '7px 12px', border: '1px solid #FECACA',
                borderRadius: 8, background: '#FEF2F2',
                color: '#DC2626', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}>
                <X size={12} /> Tozalash
              </button>
            )}
          </>
        )}

        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#6B7280' }}>
          Jami: <strong>{total}</strong> yozuv
        </span>
      </div>

      {/* Table */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {isLoading ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#6B7280', fontSize: 14 }}>
            <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px', display: 'block' }} />
            Yuklanmoqda...
          </div>
        ) : isError ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#DC2626', fontSize: 14 }}>
            <AlertTriangle size={24} style={{ margin: '0 auto 12px', display: 'block' }} />
            Yuklashda xato. Faqat ADMIN ko'ra oladi.
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#6B7280', fontSize: 14 }}>
            <Shield size={32} color="#D1D5DB" style={{ margin: '0 auto 12px', display: 'block' }} />
            Hech qanday yozuv topilmadi
          </div>
        ) : (
          <>
            {/* Table Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '44px 1fr 130px 110px 130px 130px 44px',
              padding: '10px 16px',
              borderBottom: '1px solid #F3F4F6',
              background: '#F8FAFC',
            }}>
              {['', 'Voqea', 'Foydalanuvchi', 'Daraja', 'IP manzil', 'Vaqt', ''].map((h, i) => (
                <div key={i} style={{ fontSize: 11, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' }}>
                  {h}
                </div>
              ))}
            </div>

            {/* Table Rows */}
            {items.map(entry => {
              const cfg = EVENT_CONFIG[entry.event_type] ?? EVENT_CONFIG.LOGIN_SUCCESS;
              const Icon = cfg.icon;
              const sev = SEVERITY_CONFIG[entry.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info;

              return (
                <div
                  key={entry.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '44px 1fr 130px 110px 130px 130px 44px',
                    padding: '12px 16px',
                    borderBottom: '1px solid #F9FAFB',
                    alignItems: 'center',
                    transition: 'background 0.15s',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#F8FAFC')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  onClick={() => setSelected(entry)}
                >
                  {/* Icon */}
                  <div style={{
                    width: 28, height: 28, borderRadius: 6,
                    background: cfg.bg, display: 'grid', placeItems: 'center',
                  }}>
                    <Icon size={13} color={cfg.color} />
                  </div>

                  {/* Event type */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>
                      {cfg.label}
                    </div>
                    <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 1 }}>
                      {entry.endpoint ? `${entry.http_method ?? ''} ${entry.endpoint}` : entry.event_type}
                    </div>
                  </div>

                  {/* Username */}
                  <div style={{ fontSize: 13, color: '#374151', fontWeight: 500 }}>
                    {entry.username ?? <span style={{ color: '#9CA3AF' }}>—</span>}
                  </div>

                  {/* Severity */}
                  <div>
                    <span style={{
                      padding: '2px 8px', borderRadius: 5,
                      background: sev.bg, color: sev.color,
                      border: `1px solid ${sev.border}`,
                      fontSize: 11, fontWeight: 700,
                    }}>
                      {sev.label}
                    </span>
                  </div>

                  {/* IP */}
                  <div style={{ fontSize: 12, color: '#6B7280', fontFamily: 'monospace' }}>
                    {entry.ip_address}
                  </div>

                  {/* Time */}
                  <div>
                    <div style={{ fontSize: 12, color: '#374151' }}>
                      {formatDate(entry.occurred_at).split(' ')[0]}
                    </div>
                    <div style={{ fontSize: 11, color: '#9CA3AF' }}>
                      {timeAgo(entry.occurred_at)}
                    </div>
                  </div>

                  {/* Detail button */}
                  <button
                    onClick={e => { e.stopPropagation(); setSelected(entry); }}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      padding: 4, color: '#9CA3AF',
                    }}
                  >
                    <Eye size={15} />
                  </button>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 8, marginTop: 16,
        }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '7px 12px', border: '1px solid #E4E7ED',
              borderRadius: 8, background: '#fff', cursor: page === 1 ? 'not-allowed' : 'pointer',
              opacity: page === 1 ? 0.4 : 1, display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 13, color: '#374151',
            }}
          >
            <ChevronLeft size={14} /> Oldingi
          </button>

          <span style={{ fontSize: 13, color: '#6B7280' }}>
            <strong>{page}</strong> / {pages}
          </span>

          <button
            onClick={() => setPage(p => Math.min(pages, p + 1))}
            disabled={page === pages}
            style={{
              padding: '7px 12px', border: '1px solid #E4E7ED',
              borderRadius: 8, background: '#fff', cursor: page === pages ? 'not-allowed' : 'pointer',
              opacity: page === pages ? 0.4 : 1, display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 13, color: '#374151',
            }}
          >
            Keyingi <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <DetailModal entry={selected} onClose={() => setSelected(null)} />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}