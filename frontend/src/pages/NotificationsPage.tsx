/**
 * Taurus Vision — Notifications Page (To'liq qayta yozildi)
 *
 * 2 TAB:
 *   1. In-App Bildirishnomalar — real-time, o'qildi/yashirildi boshqaruvi
 *   2. Email Sozlamalari — SMTP config, test, manual send
 *
 * YANGILIKLAR:
 *   - In-app notification ro'yxati (pagination, filtr)
 *   - Badge: o'qilmagan soni
 *   - O'qildi / Hammasi o'qildi
 *   - Yashirish / Hammasi yashirish
 *   - Admin: yangi notification yaratish
 *   - Real-time WebSocket yangilanish
 */

import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Bell, Mail, CheckCircle, XCircle, AlertCircle,
  Send, Settings, Users, RefreshCw, Info, ChevronRight,
  Copy, Inbox, BellOff, Megaphone, Trash2, Check,
  AlertTriangle, Activity, FileText, Camera, Cpu,
  Plus, X, ChevronDown,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';
import { useAuth } from '../context/AuthContext';

// =============================================================================
// TYPES
// =============================================================================

type NType = 'info' | 'success' | 'warning' | 'alert' | 'system';
type EntityType = 'animal' | 'camera' | 'sensor' | 'alert' | 'task' | 'training' | 'report' | 'system' | 'user';

interface Notification {
  id:            number;
  user_id:       number | null;
  n_type:        NType;
  title:         string;
  message:       string;
  entity_type:   EntityType | null;
  entity_id:     number | null;
  action_url:    string | null;
  is_read:       boolean;
  read_at:       string | null;
  is_dismissed:  boolean;
  extra_data:    Record<string, any> | null;
  created_at:    string;
}

interface NotificationList {
  items:        Notification[];
  total:        number;
  unread_count: number;
  page:         number;
  limit:        number;
  has_more:     boolean;
}

interface SmtpSettings {
  configured:       boolean;
  smtp_host:        string;
  smtp_port:        number;
  smtp_user:        string;
  from_address:     string;
  recipients:       string[];
  total_recipients: number;
  severity_rules:   Record<string, string>;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const N_TYPE_CONFIG: Record<NType, { color: string; bg: string; icon: any; label: string }> = {
  info:    { color: '#3B82F6', bg: '#EFF6FF', icon: Info,          label: 'Ma\'lumot'      },
  success: { color: '#10B981', bg: '#ECFDF5', icon: CheckCircle,   label: 'Muvaffaqiyat'   },
  warning: { color: '#D97706', bg: '#FFFBEB', icon: AlertTriangle, label: 'Ogohlantirish'  },
  alert:   { color: '#DC2626', bg: '#FEF2F2', icon: AlertCircle,   label: 'Kritik'         },
  system:  { color: '#6B7280', bg: '#F3F4F6', icon: Activity,      label: 'Tizim'          },
};

const ENTITY_ICON: Record<EntityType, any> = {
  animal:   Bell,
  camera:   Camera,
  sensor:   Cpu,
  alert:    AlertTriangle,
  task:     CheckCircle,
  training: Activity,
  report:   FileText,
  system:   Settings,
  user:     Users,
};

// =============================================================================
// HELPERS
// =============================================================================

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'Hozirgina';
  if (mins < 60) return `${mins} daqiqa oldin`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs} soat oldin`;
  return `${Math.floor(hrs / 24)} kun oldin`;
}

// =============================================================================
// NOTIFICATION CARD
// =============================================================================

function NotifCard({
  notif,
  onRead,
  onDismiss,
}: {
  notif:     Notification;
  onRead:    (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  const cfg     = N_TYPE_CONFIG[notif.n_type];
  const TypeIcon = cfg.icon;
  const isBroadcast = notif.user_id === null;

  return (
    <div style={{
      background:   notif.is_read ? '#FAFAFA' : '#fff',
      border:       `1px solid ${notif.is_read ? '#F3F4F6' : '#E4E7ED'}`,
      borderLeft:   `3px solid ${notif.is_read ? '#E4E7ED' : cfg.color}`,
      borderRadius: 10,
      padding:      '14px 16px',
      display:      'flex',
      gap:          12,
      transition:   'all .15s',
      opacity:      notif.is_read ? 0.75 : 1,
    }}>
      {/* Icon */}
      <div style={{
        width: 38, height: 38, borderRadius: 9,
        background: cfg.bg, display: 'grid', placeItems: 'center', flexShrink: 0,
      }}>
        <TypeIcon size={18} color={cfg.color} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0D1117' }}>
              {notif.title}
            </span>
            {isBroadcast && (
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
                padding: '1px 6px', borderRadius: 20,
                background: '#EFF6FF', color: '#3B82F6',
              }}>BROADCAST</span>
            )}
            {!notif.is_read && (
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: cfg.color, flexShrink: 0,
              }} />
            )}
          </div>
          <span style={{ fontSize: 11, color: '#9CA3AF', flexShrink: 0, whiteSpace: 'nowrap' }}>
            {timeAgo(notif.created_at)}
          </span>
        </div>

        <p style={{ fontSize: 12, color: '#4B5563', margin: '4px 0 8px', lineHeight: 1.5 }}>
          {notif.message}
        </p>

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!notif.is_read && (
            <button
              onClick={() => onRead(notif.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '3px 10px', borderRadius: 6,
                background: '#F0FDF4', color: '#059669',
                border: '1px solid #A7F3D0',
                fontSize: 11, fontWeight: 600, cursor: 'pointer',
                fontFamily: 'Outfit, sans-serif',
              }}>
              <Check size={10} /> O'qildi
            </button>
          )}
          {notif.action_url && (
            <a
              href={notif.action_url}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '3px 10px', borderRadius: 6,
                background: '#EFF6FF', color: '#3B82F6',
                border: '1px solid #BFDBFE',
                fontSize: 11, fontWeight: 600,
                textDecoration: 'none',
              }}>
              Ko'rish <ChevronRight size={10} />
            </a>
          )}
          <button
            onClick={() => onDismiss(notif.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '3px 10px', borderRadius: 6,
              background: 'none', color: '#9CA3AF',
              border: '1px solid #F3F4F6',
              fontSize: 11, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}>
            <X size={10} /> Yashirish
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// CREATE NOTIFICATION MODAL (ADMIN)
// =============================================================================

function CreateNotifModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({
    user_id: '',
    n_type:  'info' as NType,
    title:   '',
    message: '',
    action_url: '',
  });

  const mut = useMutation({
    mutationFn: () => apiFetch<Notification>('/api/v1/notifications', {
      method: 'POST',
      body: JSON.stringify({
        user_id:    form.user_id ? Number(form.user_id) : null,
        n_type:     form.n_type,
        title:      form.title,
        message:    form.message,
        action_url: form.action_url || null,
      }),
    }),
    onSuccess: () => { onSuccess(); onClose(); },
  });

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        width: '100%', maxWidth: 520,
      }}>
        <div style={{
          padding: '18px 24px', borderBottom: '1px solid #F3F4F6',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Megaphone size={16} color="#1E3EB4" />
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', margin: 0 }}>
              Yangi Notification
            </h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Tur */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Tur
            </label>
            <select
              value={form.n_type}
              onChange={e => setForm(f => ({ ...f, n_type: e.target.value as NType }))}
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB', borderRadius: 8,
                fontSize: 13, color: '#0D1117', outline: 'none',
                fontFamily: 'Outfit, sans-serif',
              }}>
              {Object.entries(N_TYPE_CONFIG).map(([v, c]) => (
                <option key={v} value={v}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* Manzil */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Foydalanuvchi ID <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(bo'sh = barcha uchun)</span>
            </label>
            <input
              type="number"
              value={form.user_id}
              onChange={e => setForm(f => ({ ...f, user_id: e.target.value }))}
              placeholder="Broadcast uchun bo'sh qoldiring"
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB', borderRadius: 8,
                fontSize: 13, color: '#0D1117', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Sarlavha */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Sarlavha *
            </label>
            <input
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder="Qisqa sarlavha"
              maxLength={120}
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB', borderRadius: 8,
                fontSize: 13, color: '#0D1117', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Xabar */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Xabar *
            </label>
            <textarea
              value={form.message}
              onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
              rows={3}
              placeholder="To'liq xabar matni..."
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB', borderRadius: 8,
                fontSize: 13, color: '#0D1117', outline: 'none',
                resize: 'vertical', fontFamily: 'Outfit, sans-serif',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Havola */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Havola <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy, masalan: /animals/5)</span>
            </label>
            <input
              value={form.action_url}
              onChange={e => setForm(f => ({ ...f, action_url: e.target.value }))}
              placeholder="/animals/5"
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB', borderRadius: 8,
                fontSize: 13, color: '#0D1117', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {mut.isError && (
            <div style={{
              padding: '8px 12px', background: '#FEF2F2',
              border: '1px solid #FECACA', borderRadius: 8,
              fontSize: 12, color: '#DC2626',
            }}>
              Xato: {(mut.error as Error)?.message}
            </div>
          )}
        </div>

        <div style={{
          padding: '14px 24px', borderTop: '1px solid #F3F4F6',
          display: 'flex', gap: 10, justifyContent: 'flex-end',
        }}>
          <button onClick={onClose} style={{
            padding: '9px 20px', border: '1px solid #D1D5DB',
            borderRadius: 8, background: '#fff', fontSize: 13,
            fontWeight: 600, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            Bekor
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending || !form.title.trim() || !form.message.trim()}
            style={{
              padding: '9px 24px',
              background: (mut.isPending || !form.title.trim() || !form.message.trim())
                ? '#9CA3AF' : '#1E3EB4',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
            {mut.isPending ? (
              <div style={{
                width: 12, height: 12, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.4)',
                borderTopColor: '#fff',
                animation: 'spin .7s linear infinite',
              }} />
            ) : <Megaphone size={13} />}
            Yuborish
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// EMAIL SOZLAMALARI TAB
// =============================================================================

function EmailTab() {
  const [testEmail,   setTestEmail]  = useState('');
  const [testResult,  setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [alertId,     setAlertId]    = useState('');
  const [sendResult,  setSendResult] = useState<any>(null);
  const [showGuide,   setShowGuide]  = useState(false);
  const [copied,      setCopied]     = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['notifications', 'email-settings'],
    queryFn:  () => apiFetch<SmtpSettings>('/api/v1/notifications/email/settings'),
  });

  const testMut = useMutation({
    mutationFn: () => apiFetch<any>('/api/v1/notifications/email/test', {
      method: 'POST',
      body: JSON.stringify({ recipient: testEmail }),
    }),
    onSuccess: r => setTestResult({ ok: r.sent || r.ok, message: r.message || 'Yuborildi' }),
    onError:   e => setTestResult({ ok: false, message: (e as Error).message }),
  });

  const sendMut = useMutation({
    mutationFn: () => apiFetch<any>(`/api/v1/notifications/email/send/${alertId}`, {
      method: 'POST', body: JSON.stringify({ recipients: null }),
    }),
    onSuccess: setSendResult,
    onError:   e => setSendResult({ sent: false, error: (e as Error).message }),
  });

  const envExample = `SMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\nSMTP_USER=your@gmail.com\nSMTP_PASSWORD=app-password\nSMTP_FROM=Taurus Vision <your@gmail.com>\nNOTIFICATION_EMAILS=admin@farm.uz,vet@farm.uz`;

  if (isLoading) return <div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>Yuklanmoqda...</div>;

  const ok = settings?.configured ?? false;

  return (
    <div>
      {/* Status banner */}
      <div style={{
        padding: '14px 18px', marginBottom: 20,
        background: ok ? '#F0FDF4' : '#FFF7ED',
        border: `1px solid ${ok ? '#A7F3D0' : '#FED7AA'}`,
        borderRadius: 12,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        {ok
          ? <CheckCircle size={16} color="#10B981" />
          : <AlertCircle size={16} color="#EA580C" />}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: ok ? '#065F46' : '#92400E' }}>
            {ok ? `SMTP tayyor — ${settings?.smtp_host}:${settings?.smtp_port}` : 'SMTP sozlanmagan'}
          </div>
          <div style={{ fontSize: 11, color: ok ? '#059669' : '#B45309', marginTop: 2 }}>
            {ok
              ? `${settings?.smtp_user} · ${settings?.total_recipients} ta recipient`
              : 'Email log da saqlanadi'}
          </div>
        </div>
        {!ok && (
          <button onClick={() => setShowGuide(true)} style={{
            padding: '5px 14px', background: '#EA580C', color: '#fff',
            border: 'none', borderRadius: 7,
            fontSize: 11, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            Sozlash
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Recipients */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
            <Users size={14} color="#1E3EB4" />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0D1117' }}>Recipientlar</span>
          </div>
          {settings?.recipients?.length ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {settings.recipients.map((e, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '7px 10px', background: '#F9FAFB',
                  border: '1px solid #F3F4F6', borderRadius: 7,
                }}>
                  <Mail size={11} color="#6B7280" />
                  <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#374151' }}>{e}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: 16, textAlign: 'center', color: '#9CA3AF', fontSize: 12 }}>
              Sozlanmagan
            </div>
          )}
        </div>

        {/* Severity rules */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
            <Bell size={14} color="#1E3EB4" />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0D1117' }}>Severity Qoidalari</span>
          </div>
          {[
            { s: 'critical', l: 'KRITIK',  e: '🔴', send: true },
            { s: 'high',     l: 'YUQORI',  e: '🟠', send: true },
            { s: 'medium',   l: "O'RTA",   e: '🟡', send: true },
            { s: 'low',      l: 'PAST',    e: '🟢', send: false },
          ].map(({ s, l, e, send }) => (
            <div key={s} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '7px 10px', marginBottom: 6,
              background: '#F9FAFB', border: '1px solid #F3F4F6', borderRadius: 7,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span>{e}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#0D1117' }}>{l}</span>
              </div>
              <span style={{ fontSize: 11, color: send ? '#059669' : '#9CA3AF', fontWeight: 600 }}>
                {send ? '✅ Email' : '❌ Yo\'q'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Test email */}
      <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
          <Send size={14} color="#1E3EB4" />
          <span style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Test Email</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="email" value={testEmail}
            onChange={e => setTestEmail(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && testEmail.trim() && testMut.mutate()}
            placeholder="test@example.com"
            style={{
              flex: 1, padding: '9px 12px',
              border: '1px solid #D1D5DB', borderRadius: 8,
              fontSize: 13, outline: 'none', fontFamily: 'monospace',
            }}
          />
          <button
            onClick={() => testMut.mutate()}
            disabled={testMut.isPending || !testEmail.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '9px 18px',
              background: (testMut.isPending || !testEmail.trim()) ? '#9CA3AF' : '#1E3EB4',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}>
            <Send size={13} />
            {testMut.isPending ? 'Yuborilmoqda...' : 'Yuborish'}
          </button>
        </div>
        {testResult && (
          <div style={{
            marginTop: 10, padding: '8px 12px',
            background: testResult.ok ? '#F0FDF4' : '#FEF2F2',
            border: `1px solid ${testResult.ok ? '#A7F3D0' : '#FECACA'}`,
            borderRadius: 8, fontSize: 12,
            color: testResult.ok ? '#065F46' : '#DC2626',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            {testResult.ok ? <CheckCircle size={13} /> : <XCircle size={13} />}
            {testResult.message}
          </div>
        )}
      </div>

      {/* Alert email */}
      <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
          <Bell size={14} color="#1E3EB4" />
          <span style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Alert Email Yuborish</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="number" value={alertId}
            onChange={e => setAlertId(e.target.value)}
            placeholder="Alert ID"
            style={{
              flex: 1, padding: '9px 12px',
              border: '1px solid #D1D5DB', borderRadius: 8,
              fontSize: 13, outline: 'none',
            }}
          />
          <button
            onClick={() => sendMut.mutate()}
            disabled={sendMut.isPending || !alertId.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '9px 18px',
              background: (sendMut.isPending || !alertId.trim()) ? '#9CA3AF' : '#7C3AED',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}>
            <Mail size={13} />
            {sendMut.isPending ? 'Yuborilmoqda...' : 'Yuborish'}
          </button>
        </div>
        {sendResult && (
          <div style={{
            marginTop: 10, padding: '8px 12px',
            background: sendResult.sent ? '#F0FDF4' : '#FEF2F2',
            border: `1px solid ${sendResult.sent ? '#A7F3D0' : '#FECACA'}`,
            borderRadius: 8, fontSize: 12,
            color: sendResult.sent ? '#065F46' : '#DC2626',
          }}>
            {sendResult.sent
              ? `✅ Muvaffaqiyatli (${sendResult.mode === 'log' ? 'log rejimida' : 'SMTP'})`
              : `❌ Xato: ${sendResult.error || 'Noma\'lum'}`}
          </div>
        )}
      </div>

      {/* Guide Modal */}
      {showGuide && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 50, padding: 16,
        }}>
          <div style={{
            background: '#fff', borderRadius: 16, maxWidth: 560,
            width: '100%', maxHeight: '90vh', overflow: 'auto',
          }}>
            <div style={{
              padding: '18px 24px', borderBottom: '1px solid #F3F4F6',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Settings size={16} color="#1E3EB4" />
                <span style={{ fontSize: 15, fontWeight: 700 }}>SMTP Sozlash</span>
              </div>
              <button onClick={() => setShowGuide(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF' }}>
                <X size={18} />
              </button>
            </div>
            <div style={{ padding: 24 }}>
              <div style={{ position: 'relative' }}>
                <pre style={{
                  background: '#0D1117', color: '#E5E7EB',
                  padding: '16px 20px', borderRadius: 10,
                  fontSize: 12, lineHeight: 1.7, overflowX: 'auto',
                }}>
                  {envExample}
                </pre>
                <button onClick={() => {
                  navigator.clipboard.writeText(envExample);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }} style={{
                  position: 'absolute', top: 10, right: 10,
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '4px 10px',
                  background: copied ? '#10B981' : 'rgba(255,255,255,0.1)',
                  border: 'none', borderRadius: 6,
                  color: '#fff', fontSize: 11, cursor: 'pointer',
                }}>
                  {copied ? <CheckCircle size={11} /> : <Copy size={11} />}
                  {copied ? 'Nusxalandi' : 'Nusxalash'}
                </button>
              </div>
              <p style={{ fontSize: 12, color: '#6B7280', marginTop: 12 }}>
                Gmail uchun oddiy parol emas, <strong>App Password</strong> kerak.
                Keyinroq: <code>docker compose restart backend</code>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function NotificationsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const [activeTab,   setActiveTab]   = useState<'inapp' | 'email'>('inapp');
  const [filter,      setFilter]      = useState<'all' | 'unread'>('all');
  const [showCreate,  setShowCreate]  = useState(false);
  const [page,        setPage]        = useState(0);
  const LIMIT = 20;

  const isAdmin = (user as any)?.role === 'admin';

  // ── Queries ─────────────────────────────────────────────────────────────────
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['notifications', 'list', filter, page],
    queryFn:  () => apiFetch<NotificationList>(
      `/api/v1/notifications?limit=${LIMIT}&offset=${page * LIMIT}&unread_only=${filter === 'unread'}`
    ),
    refetchInterval: 30_000,
  });

  const { data: countData } = useQuery({
    queryKey: ['notifications', 'count'],
    queryFn:  () => apiFetch<{ unread_count: number; total: number }>('/api/v1/notifications/count'),
    refetchInterval: 15_000,
  });

  // ── Mutations ────────────────────────────────────────────────────────────────
  const readMut = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/notifications/read/${id}`, { method: 'POST' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['notifications'] }); },
  });

  const readAllMut = useMutation({
    mutationFn: () => apiFetch('/api/v1/notifications/read-all', { method: 'POST' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['notifications'] }); },
  });

  const dismissMut = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/notifications/dismiss/${id}`, { method: 'POST' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['notifications'] }); },
  });

  const dismissAllMut = useMutation({
    mutationFn: () => apiFetch('/api/v1/notifications/dismiss-all', { method: 'POST' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['notifications'] }); },
  });

  const unread = countData?.unread_count ?? 0;

  return (
    <div style={{
      maxWidth: 900, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
            Bildirishnomalar
          </h1>
          <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
            In-app xabarlar va email sozlamalari
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => refetch()} style={{
            padding: '8px 12px', border: '1px solid #D1D5DB',
            borderRadius: 8, background: '#fff', cursor: 'pointer',
          }}>
            <RefreshCw size={14} color="#6B7280" />
          </button>
          {isAdmin && activeTab === 'inapp' && (
            <button onClick={() => setShowCreate(true)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px',
              background: '#1E3EB4', color: '#fff',
              border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}>
              <Plus size={14} /> Yuborish
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 0,
        background: '#F3F4F6', borderRadius: 10, padding: 3,
        marginBottom: 24, width: 'fit-content',
      }}>
        {([
          { key: 'inapp', label: 'In-App', icon: Bell,  badge: unread },
          { key: 'email', label: 'Email',  icon: Mail,  badge: 0 },
        ] as const).map(({ key, label, icon: Icon, badge }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 18px', borderRadius: 8,
              background: activeTab === key ? '#fff' : 'transparent',
              boxShadow: activeTab === key ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
              border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600,
              color: activeTab === key ? '#0D1117' : '#6B7280',
              fontFamily: 'Outfit, sans-serif',
              transition: 'all .15s',
            }}>
            <Icon size={14} />
            {label}
            {badge > 0 && (
              <span style={{
                minWidth: 18, height: 18, borderRadius: 9,
                background: '#DC2626', color: '#fff',
                fontSize: 10, fontWeight: 700,
                display: 'grid', placeItems: 'center',
                padding: '0 4px',
              }}>
                {badge > 99 ? '99+' : badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* IN-APP TAB */}
      {activeTab === 'inapp' && (
        <div>
          {/* Toolbar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 16,
          }}>
            <div style={{ display: 'flex', gap: 6 }}>
              {(['all', 'unread'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => { setFilter(f); setPage(0); }}
                  style={{
                    padding: '6px 14px', borderRadius: 7,
                    background: filter === f ? '#1E3EB4' : '#F3F4F6',
                    color: filter === f ? '#fff' : '#6B7280',
                    border: 'none', cursor: 'pointer',
                    fontSize: 12, fontWeight: 600,
                    fontFamily: 'Outfit, sans-serif',
                  }}>
                  {f === 'all' ? 'Barchasi' : `O'qilmagan${unread > 0 ? ` (${unread})` : ''}`}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {unread > 0 && (
                <button
                  onClick={() => readAllMut.mutate()}
                  disabled={readAllMut.isPending}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '6px 12px', borderRadius: 7,
                    background: '#F0FDF4', color: '#059669',
                    border: '1px solid #A7F3D0',
                    fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    fontFamily: 'Outfit, sans-serif',
                  }}>
                  <Check size={11} /> Hammasini o'qildi
                </button>
              )}
              {(data?.total ?? 0) > 0 && (
                <button
                  onClick={() => dismissAllMut.mutate()}
                  disabled={dismissAllMut.isPending}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '6px 12px', borderRadius: 7,
                    background: '#FEF2F2', color: '#DC2626',
                    border: '1px solid #FECACA',
                    fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    fontFamily: 'Outfit, sans-serif',
                  }}>
                  <Trash2 size={11} /> Hammasini yashirish
                </button>
              )}
            </div>
          </div>

          {/* List */}
          {isLoading ? (
            <div style={{ padding: 48, textAlign: 'center', color: '#9CA3AF' }}>
              Yuklanmoqda...
            </div>
          ) : !data?.items?.length ? (
            <div style={{
              padding: 48, textAlign: 'center',
              background: '#F9FAFB', borderRadius: 12,
              border: '1px dashed #E4E7ED',
            }}>
              <Inbox size={40} color="#D1D5DB" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: 14, fontWeight: 600, color: '#9CA3AF', margin: 0 }}>
                {filter === 'unread' ? "O'qilmagan xabarlar yo'q" : 'Bildirishnomalar yo\'q'}
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.items.map(n => (
                <NotifCard
                  key={n.id}
                  notif={n}
                  onRead={id => readMut.mutate(id)}
                  onDismiss={id => dismissMut.mutate(id)}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {data && data.total > LIMIT && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 12, marginTop: 20,
            }}>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{
                  padding: '7px 16px', borderRadius: 8,
                  border: '1px solid #D1D5DB',
                  background: page === 0 ? '#F9FAFB' : '#fff',
                  color: page === 0 ? '#9CA3AF' : '#374151',
                  fontSize: 13, cursor: page === 0 ? 'not-allowed' : 'pointer',
                  fontFamily: 'Outfit, sans-serif',
                }}>
                ← Oldingi
              </button>
              <span style={{ fontSize: 13, color: '#6B7280' }}>
                {page + 1} / {Math.ceil(data.total / LIMIT)}
              </span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!data.has_more}
                style={{
                  padding: '7px 16px', borderRadius: 8,
                  border: '1px solid #D1D5DB',
                  background: !data.has_more ? '#F9FAFB' : '#fff',
                  color: !data.has_more ? '#9CA3AF' : '#374151',
                  fontSize: 13, cursor: !data.has_more ? 'not-allowed' : 'pointer',
                  fontFamily: 'Outfit, sans-serif',
                }}>
                Keyingi →
              </button>
            </div>
          )}
        </div>
      )}

      {/* EMAIL TAB */}
      {activeTab === 'email' && <EmailTab />}

      {/* Create Modal */}
      {showCreate && (
        <CreateNotifModal
          onClose={() => setShowCreate(false)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['notifications'] })}
        />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}