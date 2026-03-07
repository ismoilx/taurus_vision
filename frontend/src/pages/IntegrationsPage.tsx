/**
 * Taurus Vision — Integrations Page (Q5)
 *
 * 2 tab:
 *  1. API Kalitlar  — IoT/ERP/Bot uchun kalitlar boshqaruvi
 *  2. Webhooklar    — Voqea bildirishnomalari
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Key, Webhook, Plus, Trash2, Edit2, Copy, Check,
  Eye, EyeOff, Zap, Shield, AlertCircle, X,
  CheckCircle, XCircle, Clock, Activity, RefreshCw,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface APIKeyResponse {
  id:            number;
  name:          string;
  description:   string | null;
  key_prefix:    string;
  display_key:   string;
  scopes:        string[];
  is_active:     boolean;
  expires_at:    string | null;
  last_used_at:  string | null;
  request_count: number;
  creator_name:  string | null;
  created_at:    string;
}

interface APIKeyCreated extends APIKeyResponse {
  raw_key: string;
}

interface WebhookResponse {
  id:                number;
  name:              string;
  description:       string | null;
  url:               string;
  events:            string[];
  is_active:         boolean;
  failure_count:     number;
  success_count:     number;
  last_triggered_at: string | null;
  last_status_code:  number | null;
  last_error:        string | null;
  health_status:     string;
  creator_name:      string | null;
  created_at:        string;
}

interface Meta {
  scopes: { value: string; label: string; group: string }[];
  events: { value: string; label: string; icon: string }[];
}

interface WebhookTestResult {
  success:     boolean;
  status_code: number | null;
  latency_ms:  number | null;
  error:       string | null;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SCOPE_GROUPS = ['O\'qish', 'Yozish (IoT)', 'Admin'];

const HEALTH_CONFIG: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  healthy:  { color: '#059669', bg: '#ECFDF5', icon: <CheckCircle size={13} />, label: 'Sog\'lom' },
  degraded: { color: '#D97706', bg: '#FFFBEB', icon: <AlertCircle size={13} />, label: 'Muammo' },
  inactive: { color: '#6B7280', bg: '#F3F4F6', icon: <XCircle size={13} />,    label: 'Nofaol' },
  unknown:  { color: '#3B82F6', bg: '#EFF6FF', icon: <Clock size={13} />,      label: 'Yangi' },
};

// =============================================================================
// HELPERS
// =============================================================================

function fmtDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short', year: 'numeric' });
}

function fmtDateTime(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short' }) + ' ' +
         d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={copy} title="Nusxa olish" style={{
      background: 'none', border: 'none', cursor: 'pointer',
      color: copied ? '#10B981' : '#6B7280', padding: '2px 4px',
      display: 'inline-flex', alignItems: 'center',
    }}>
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

// =============================================================================
// API KEY MODAL
// =============================================================================

function APIKeyModal({
  meta, onClose, onCreated,
}: {
  meta:      Meta;
  onClose:   () => void;
  onCreated: (k: APIKeyCreated) => void;
}) {
  const [name,    setName]    = useState('');
  const [desc,    setDesc]    = useState('');
  const [scopes,  setScopes]  = useState<string[]>([]);
  const [expires, setExpires] = useState('');
  const [err,     setErr]     = useState<string | null>(null);

  const mutation = useMutation<APIKeyCreated, Error>({
    mutationFn: () => apiFetch<APIKeyCreated>('/api/v1/integrations/api-keys', {
      method: 'POST',
      body: JSON.stringify({
        name,
        description: desc || null,
        scopes,
        expires_at: expires || null,
      }),
    }),
    onSuccess: (data) => onCreated(data),
    onError:   (e) => setErr(e.message),
  });

  const toggleScope = (s: string) => {
    setScopes(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  };

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
    border: '1px solid #D1D5DB', outline: 'none', background: '#FAFAFA',
    fontFamily: "'Outfit', sans-serif", boxSizing: 'border-box',
  };

  return (
    <Overlay onClose={onClose}>
      <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: '0 0 20px' }}>Yangi API Kalit</h2>

      {err && <ErrBox msg={err} />}

      <div style={{ display: 'grid', gap: 12 }}>
        <div>
          <Label>NOMI *</Label>
          <input value={name} onChange={e => setName(e.target.value)}
            placeholder="Masalan: Telegram Bot" style={inp} />
        </div>
        <div>
          <Label>TAVSIF</Label>
          <input value={desc} onChange={e => setDesc(e.target.value)}
            placeholder="Ixtiyoriy..." style={inp} />
        </div>
        <div>
          <Label>MUDDATI (ixtiyoriy)</Label>
          <input type="date" value={expires} onChange={e => setExpires(e.target.value)} style={inp} />
        </div>

        <div>
          <Label>HUQUQLAR * (kamida bittasini tanlang)</Label>
          <div style={{ display: 'grid', gap: 8, marginTop: 4 }}>
            {SCOPE_GROUPS.map(group => {
              const groupScopes = meta.scopes.filter(s => s.group === group);
              if (!groupScopes.length) return null;
              return (
                <div key={group}>
                  <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 5, textTransform: 'uppercase' }}>
                    {group}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {groupScopes.map(s => {
                      const active = scopes.includes(s.value);
                      return (
                        <button key={s.value} onClick={() => toggleScope(s.value)} style={{
                          padding: '5px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                          fontSize: 12, fontWeight: active ? 700 : 400,
                          background: active ? (s.value === 'admin' ? '#FEF2F2' : '#EFF6FF') : '#F3F4F6',
                          color:      active ? (s.value === 'admin' ? '#DC2626' : '#1D4ED8') : '#6B7280',
                          boxShadow:  active ? `0 0 0 2px ${s.value === 'admin' ? '#EF4444' : '#3B82F6'}` : 'none',
                          fontFamily: "'Outfit', sans-serif", transition: 'all .15s',
                        }}>
                          {active && '✓ '}{s.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
        <button onClick={onClose} style={cancelBtn}>Bekor</button>
        <button
          onClick={() => {
            if (!name.trim()) { setErr('Nom kiritilishi shart'); return; }
            if (!scopes.length) { setErr('Kamida bitta huquq tanlang'); return; }
            setErr(null);
            mutation.mutate();
          }}
          disabled={mutation.isPending}
          style={{ ...primaryBtn, flex: 2 }}>
          {mutation.isPending ? 'Yaratilmoqda...' : 'Kalit yaratish'}
        </button>
      </div>
    </Overlay>
  );
}

// =============================================================================
// RAW KEY SHOW MODAL
// =============================================================================

function RawKeyModal({ rawKey, onClose }: { rawKey: string; onClose: () => void }) {
  const [visible, setVisible] = useState(false);
  return (
    <Overlay onClose={onClose}>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ width: 52, height: 52, borderRadius: 16, background: '#ECFDF5', display: 'grid', placeItems: 'center', margin: '0 auto 12px' }}>
          <Key size={22} color="#10B981" />
        </div>
        <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: '0 0 6px' }}>Kalit yaratildi!</h2>
        <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>
          Bu kalit <strong>QAYTA KO'RSATILMAYDI</strong>. Hoziroq xavfsiz joyga saqlang.
        </p>
      </div>

      <div style={{
        background: '#F0FDF4', border: '1px solid #86EFAC', borderRadius: 10,
        padding: '14px 16px', fontFamily: "'JetBrains Mono', monospace",
        fontSize: 12, wordBreak: 'break-all', color: '#065F46',
        position: 'relative', marginBottom: 16,
        filter: visible ? 'none' : 'blur(4px)',
        userSelect: visible ? 'auto' : 'none',
        transition: 'filter .2s',
      }}>
        {rawKey}
        <div style={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 4 }}>
          <button onClick={() => setVisible(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#059669' }}>
            {visible ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
          {visible && <CopyButton text={rawKey} />}
        </div>
      </div>

      <button onClick={() => setVisible(v => !v)} style={{
        width: '100%', padding: '9px', borderRadius: 10,
        background: visible ? '#F3F4F6' : '#ECFDF5',
        border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
        color: visible ? '#374151' : '#059669', marginBottom: 10,
        fontFamily: "'Outfit', sans-serif",
      }}>
        {visible ? '🙈 Yashirish' : '👁 Ko\'rish va Nusxa olish'}
      </button>

      <button onClick={onClose} style={{ ...primaryBtn, width: '100%' }}>
        Saqladim, yopish
      </button>
    </Overlay>
  );
}

// =============================================================================
// WEBHOOK MODAL
// =============================================================================

function WebhookModal({
  meta, wh, onClose,
}: {
  meta:    Meta;
  wh?:     WebhookResponse | null;
  onClose: () => void;
}) {
  const qc     = useQueryClient();
  const isEdit = !!wh;

  const [name,   setName]   = useState(wh?.name ?? '');
  const [desc,   setDesc]   = useState(wh?.description ?? '');
  const [url,    setUrl]    = useState(wh?.url ?? '');
  const [events, setEvents] = useState<string[]>(wh?.events ?? []);
  const [err,    setErr]    = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const body = JSON.stringify({
        name: name.trim(),
        description: desc || null,
        url: url.trim(),
        events,
      });
      if (isEdit) {
        return apiFetch(`/api/v1/integrations/webhooks/${wh!.id}`, { method: 'PATCH', body });
      }
      return apiFetch('/api/v1/integrations/webhooks', { method: 'POST', body });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['integrations'] });
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const toggleEvent = (e: string) =>
    setEvents(prev => prev.includes(e) ? prev.filter(x => x !== e) : [...prev, e]);

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
    border: '1px solid #D1D5DB', outline: 'none', background: '#FAFAFA',
    fontFamily: "'Outfit', sans-serif", boxSizing: 'border-box',
  };

  return (
    <Overlay onClose={onClose}>
      <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: '0 0 20px' }}>
        {isEdit ? 'Webhookni tahrirlash' : 'Yangi Webhook'}
      </h2>

      {err && <ErrBox msg={err} />}

      <div style={{ display: 'grid', gap: 12 }}>
        <div>
          <Label>NOMI *</Label>
          <input value={name} onChange={e => setName(e.target.value)}
            placeholder="Masalan: Telegram Alert Bot" style={inp} />
        </div>
        <div>
          <Label>URL * (faqat HTTPS)</Label>
          <input value={url} onChange={e => setUrl(e.target.value)}
            placeholder="https://example.com/webhook" style={inp} />
        </div>
        <div>
          <Label>TAVSIF</Label>
          <input value={desc} onChange={e => setDesc(e.target.value)}
            placeholder="Ixtiyoriy..." style={inp} />
        </div>

        <div>
          <Label>KUZATILADIGAN VOQEALAR *</Label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 4 }}>
            {meta.events.map(ev => {
              const active = events.includes(ev.value);
              return (
                <button key={ev.value} onClick={() => toggleEvent(ev.value)} style={{
                  padding: '8px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  fontSize: 12, fontWeight: active ? 700 : 400, textAlign: 'left',
                  background: active ? '#EFF6FF' : '#F3F4F6',
                  color:      active ? '#1D4ED8' : '#6B7280',
                  boxShadow:  active ? '0 0 0 2px #3B82F6' : 'none',
                  fontFamily: "'Outfit', sans-serif", transition: 'all .15s',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <span>{ev.icon}</span>
                  <span>{ev.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
        <button onClick={onClose} style={cancelBtn}>Bekor</button>
        <button
          onClick={() => {
            if (!name.trim()) { setErr('Nom kiritilishi shart'); return; }
            if (!url.trim().startsWith('https://')) { setErr('URL https:// bilan boshlanishi kerak'); return; }
            if (!events.length) { setErr('Kamida bitta voqea tanlang'); return; }
            setErr(null);
            mutation.mutate();
          }}
          disabled={mutation.isPending}
          style={{ ...primaryBtn, flex: 2 }}>
          {mutation.isPending ? 'Saqlanmoqda...' : (isEdit ? 'Saqlash' : 'Webhook yaratish')}
        </button>
      </div>
    </Overlay>
  );
}

// =============================================================================
// SHARED STYLE HELPERS
// =============================================================================

const cardStyle: React.CSSProperties = {
  background: '#fff', borderRadius: 14, padding: '18px 22px',
  border: '1px solid #E4E7ED',
};

const cancelBtn: React.CSSProperties = {
  flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid #E4E7ED',
  background: '#F7F8FA', cursor: 'pointer', fontSize: 13, fontWeight: 600,
  color: '#374151', fontFamily: "'Outfit', sans-serif",
};

const primaryBtn: React.CSSProperties = {
  padding: '10px 0', borderRadius: 10, border: 'none',
  background: '#1E3EB4', color: '#fff', cursor: 'pointer',
  fontSize: 13, fontWeight: 700, fontFamily: "'Outfit', sans-serif",
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
      {children}
    </label>
  );
}

function ErrBox({ msg }: { msg: string }) {
  return (
    <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
      <AlertCircle size={14} color="#EF4444" />
      <span style={{ fontSize: 12, color: '#DC2626' }}>{msg}</span>
    </div>
  );
}

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.45)', display: 'grid', placeItems: 'center' }}
      onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 18, padding: '28px 30px', width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.18)' }}
        onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

type Tab = 'keys' | 'webhooks' | 'logs';

export default function IntegrationsPage() {
  const [tab,       setTab]       = useState<Tab>('keys');
  const [keyModal,  setKeyModal]  = useState(false);
  const [rawKey,    setRawKey]    = useState<string | null>(null);
  const [whModal,   setWhModal]   = useState<{ open: boolean; wh: WebhookResponse | null }>({ open: false, wh: null });
  const [deleteId,  setDeleteId]  = useState<{ type: 'key' | 'wh'; id: number } | null>(null);
  const [testId,    setTestId]    = useState<number | null>(null);
  const [testResult, setTestResult] = useState<WebhookTestResult | null>(null);
  const [logsWhId,  setLogsWhId]  = useState<number | null>(null);

  const qc = useQueryClient();

  const { data: meta } = useQuery<Meta>({
    queryKey: ['integrations', 'meta'],
    queryFn:  () => apiFetch('/api/v1/integrations/meta'),
    staleTime: Infinity,
  });

  const { data: keys, isLoading: keysLoading } = useQuery<{ items: APIKeyResponse[]; total: number }>({
    queryKey: ['integrations', 'keys'],
    queryFn:  () => apiFetch('/api/v1/integrations/api-keys'),
    staleTime: 30_000,
  });

  const { data: webhooks, isLoading: whsLoading } = useQuery<{ items: WebhookResponse[]; total: number }>({
    queryKey: ['integrations', 'webhooks'],
    queryFn:  () => apiFetch('/api/v1/integrations/webhooks'),
    staleTime: 30_000,
  });

  const deleteKeyMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/integrations/api-keys/${id}`, { method: 'DELETE' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['integrations'] }); setDeleteId(null); },
  });

  const deleteWhMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/integrations/webhooks/${id}`, { method: 'DELETE' }),
    onSuccess:  () => { qc.invalidateQueries({ queryKey: ['integrations'] }); setDeleteId(null); },
  });

  const testMutation = useMutation<WebhookTestResult, Error, number>({
    mutationFn: (id) => apiFetch<WebhookTestResult>(`/api/v1/integrations/webhooks/${id}/test`, { method: 'POST' }),
    onSuccess:  (data) => { setTestResult(data); setTestId(null); },
    onError:    (e)    => setTestResult({ success: false, status_code: null, latency_ms: null, error: e.message }),
  });

  const tabBtn = (t: Tab): React.CSSProperties => ({
    padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontSize: 13, fontWeight: tab === t ? 600 : 400,
    background: tab === t ? '#1E3EB4' : 'transparent',
    color:      tab === t ? '#fff'    : '#6B7280',
    fontFamily: "'Outfit', sans-serif", transition: 'all .15s',
    display: 'flex', alignItems: 'center', gap: 6,
  });

  const scopeBadge = (s: string) => (
    <span key={s} style={{
      padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700,
      background: s === 'admin' ? '#FEF2F2' : s.startsWith('write') ? '#FFFBEB' : '#EFF6FF',
      color:      s === 'admin' ? '#DC2626' : s.startsWith('write') ? '#D97706' : '#1D4ED8',
    }}>{s}</span>
  );

  const eventBadge = (e: string) => {
    const ev = meta?.events.find(x => x.value === e);
    return (
      <span key={e} style={{
        padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700,
        background: '#F3F4F6', color: '#374151',
      }}>
        {ev?.icon} {ev?.label ?? e}
      </span>
    );
  };

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1300, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0D1117', margin: 0 }}>🔌 Integratsiyalar</h1>
          <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0' }}>
            API kalitlar va webhook bildirishnomalari boshqaruvi
          </p>
        </div>
        <button
          onClick={() => tab === 'keys' ? setKeyModal(true) : tab === 'webhooks' ? setWhModal({ open: true, wh: null }) : undefined}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '9px 18px', borderRadius: 10, border: 'none',
            background: '#1E3EB4', color: '#fff', cursor: 'pointer',
            fontSize: 13, fontWeight: 600, fontFamily: "'Outfit', sans-serif",
          }}>
          <Plus size={15} />
          {tab === 'keys' ? 'Yangi kalit' : tab === 'webhooks' ? 'Yangi webhook' : null}
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 20 }}>
        {[
          { icon: <Key size={16} color="#1D4ED8" />, bg: '#EFF6FF', label: 'API Kalitlar', value: keys?.total ?? 0 },
          { icon: <Webhook size={16} color="#059669" />, bg: '#ECFDF5', label: 'Webhooklar', value: webhooks?.total ?? 0 },
          { icon: <Activity size={16} color="#D97706" />, bg: '#FFFBEB', label: 'Faol kalitlar', value: keys?.items.filter(k => k.is_active).length ?? 0 },
          { icon: <CheckCircle size={16} color="#059669" />, bg: '#ECFDF5', label: 'Sog\'lom webhooklar', value: webhooks?.items.filter(w => w.health_status === 'healthy').length ?? 0 },
        ].map(s => (
          <div key={s.label} style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9, background: s.bg, display: 'grid', placeItems: 'center' }}>{s.icon}</div>
            <div>
              <div style={{ fontSize: 11, color: '#9CA3AF' }}>{s.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#0D1117' }}>{s.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 18, background: '#F7F8FA', padding: 4, borderRadius: 12, width: 'fit-content' }}>
        <button onClick={() => setTab('keys')} style={tabBtn('keys')}>
          <Key size={13} /> API Kalitlar
        </button>
        <button onClick={() => setTab('webhooks')} style={tabBtn('webhooks')}>
          <Webhook size={13} /> Webhooklar
        </button>
        <button onClick={() => setTab('logs')} style={tabBtn('logs')}>
          <Activity size={13} /> Delivery Logs
        </button>
      </div>

      {/* ═══════════════ API KEYS ═══════════════ */}
      {tab === 'keys' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {keysLoading ? (
            <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Yuklanmoqda...</p>
          ) : !keys?.items.length ? (
            <div style={{ ...cardStyle, textAlign: 'center', padding: '48px 20px' }}>
              <Key size={36} color="#D1D5DB" style={{ margin: '0 auto 12px', display: 'block' }} />
              <p style={{ color: '#9CA3AF', fontSize: 14, margin: 0 }}>API kalit yo'q. Yangi kalit yarating.</p>
            </div>
          ) : (
            keys.items.map(key => (
              <div key={key.id} style={{ ...cardStyle, display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'start' }}>
                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>{key.name}</span>
                    <span style={{
                      padding: '3px 9px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                      background: key.is_active ? '#ECFDF5' : '#F3F4F6',
                      color:      key.is_active ? '#059669' : '#6B7280',
                    }}>
                      {key.is_active ? 'Faol' : 'Nofaol'}
                    </span>
                  </div>

                  {key.description && (
                    <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>{key.description}</p>
                  )}

                  {/* Key display */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#F8FAFC', borderRadius: 8, padding: '7px 12px', width: 'fit-content' }}>
                    <Shield size={12} color="#9CA3AF" />
                    <code style={{ fontSize: 12, color: '#374151', fontFamily: "'JetBrains Mono', monospace" }}>
                      {key.display_key}
                    </code>
                    <CopyButton text={key.display_key} />
                  </div>

                  {/* Scopes */}
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {key.scopes.map(scopeBadge)}
                  </div>

                  {/* Meta */}
                  <div style={{ display: 'flex', gap: 18, fontSize: 11, color: '#9CA3AF' }}>
                    <span>📊 {key.request_count.toLocaleString()} so'rov</span>
                    <span>⏱ Oxirgi: {fmtDateTime(key.last_used_at)}</span>
                    {key.expires_at && <span>📅 Muddati: {fmtDate(key.expires_at)}</span>}
                    <span>👤 {key.creator_name ?? '—'}</span>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => setDeleteId({ type: 'key', id: key.id })}
                    style={{ background: 'none', border: '1px solid #FCA5A5', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: '#EF4444' }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ═══════════════ WEBHOOKS ═══════════════ */}
      {tab === 'webhooks' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {whsLoading ? (
            <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Yuklanmoqda...</p>
          ) : !webhooks?.items.length ? (
            <div style={{ ...cardStyle, textAlign: 'center', padding: '48px 20px' }}>
              <Zap size={36} color="#D1D5DB" style={{ margin: '0 auto 12px', display: 'block' }} />
              <p style={{ color: '#9CA3AF', fontSize: 14, margin: 0 }}>Webhook yo'q. Yangi webhook yarating.</p>
            </div>
          ) : (
            webhooks.items.map(wh => {
              const hc = HEALTH_CONFIG[wh.health_status] ?? HEALTH_CONFIG.unknown;
              return (
                <div key={wh.id} style={{ ...cardStyle, display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'start' }}>
                  <div style={{ display: 'grid', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>{wh.name}</span>
                      <span style={{ padding: '3px 9px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: hc.bg, color: hc.color, display: 'flex', alignItems: 'center', gap: 4 }}>
                        {hc.icon} {hc.label}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <code style={{ fontSize: 12, color: '#374151', background: '#F8FAFC', padding: '4px 10px', borderRadius: 6, fontFamily: "'JetBrains Mono', monospace" }}>
                        {wh.url.length > 60 ? wh.url.slice(0, 60) + '...' : wh.url}
                      </code>
                      <CopyButton text={wh.url} />
                    </div>

                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      {wh.events.map(eventBadge)}
                    </div>

                    <div style={{ display: 'flex', gap: 18, fontSize: 11, color: '#9CA3AF' }}>
                      <span style={{ color: '#059669' }}>✅ {wh.success_count}</span>
                      <span style={{ color: wh.failure_count > 0 ? '#EF4444' : '#9CA3AF' }}>❌ {wh.failure_count}</span>
                      <span>Oxirgi: {fmtDateTime(wh.last_triggered_at)}</span>
                      {wh.last_status_code && <span>HTTP {wh.last_status_code}</span>}
                    </div>

                    {wh.last_error && (
                      <div style={{ fontSize: 11, color: '#DC2626', background: '#FEF2F2', borderRadius: 6, padding: '4px 8px' }}>
                        {wh.last_error}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => { setTestId(wh.id); testMutation.mutate(wh.id); }}
                      disabled={testMutation.isPending && testId === wh.id}
                      title="Test ping"
                      style={{ background: 'none', border: '1px solid #BBF7D0', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: '#059669' }}>
                      {testMutation.isPending && testId === wh.id ? <RefreshCw size={14} className="spin" /> : <Zap size={14} />}
                    </button>
                    <button
                      onClick={() => setWhModal({ open: true, wh })}
                      style={{ background: 'none', border: '1px solid #E4E7ED', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: '#374151' }}>
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => setDeleteId({ type: 'wh', id: wh.id })}
                      style={{ background: 'none', border: '1px solid #FCA5A5', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: '#EF4444' }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ═══ API KEY MODAL ═══ */}
      {keyModal && meta && (
        <APIKeyModal
          meta={meta}
          onClose={() => setKeyModal(false)}
          onCreated={k => {
            qc.invalidateQueries({ queryKey: ['integrations'] });
            setKeyModal(false);
            setRawKey(k.raw_key);
          }}
        />
      )}

      {/* ═══ RAW KEY SHOW ═══ */}
      {rawKey && <RawKeyModal rawKey={rawKey} onClose={() => setRawKey(null)} />}

      {/* ═══ WEBHOOK MODAL ═══ */}
      {whModal.open && meta && (
        <WebhookModal meta={meta} wh={whModal.wh} onClose={() => setWhModal({ open: false, wh: null })} />
      )}

      {/* ═══ TEST RESULT ═══ */}
      {testResult && (
        <Overlay onClose={() => setTestResult(null)}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 52, height: 52, borderRadius: 16, background: testResult.success ? '#ECFDF5' : '#FEF2F2', display: 'grid', placeItems: 'center', margin: '0 auto 14px' }}>
              {testResult.success ? <CheckCircle size={24} color="#10B981" /> : <XCircle size={24} color="#EF4444" />}
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0D1117', margin: '0 0 8px' }}>
              {testResult.success ? 'Test muvaffaqiyatli!' : 'Test muvaffaqiyatsiz'}
            </h3>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 20, marginBottom: 16 }}>
              {testResult.status_code && <div><span style={{ fontSize: 11, color: '#9CA3AF' }}>HTTP Status</span><br /><b>{testResult.status_code}</b></div>}
              {testResult.latency_ms  && <div><span style={{ fontSize: 11, color: '#9CA3AF' }}>Kechikish</span><br /><b>{testResult.latency_ms} ms</b></div>}
            </div>
            {testResult.error && <p style={{ fontSize: 13, color: '#DC2626', background: '#FEF2F2', borderRadius: 8, padding: '10px 14px' }}>{testResult.error}</p>}
            <button onClick={() => setTestResult(null)} style={{ ...primaryBtn, width: '100%', marginTop: 12 }}>Yopish</button>
          </div>
        </Overlay>
      )}

      {/* ═══ DELIVERY LOGS TAB ═══ */}
      {tab === 'logs' && (
        <DeliveryLogsTab
          webhooks={webhooks?.items ?? []}
          selectedId={logsWhId}
          onSelect={setLogsWhId}
        />
      )}

      {/* ═══ DELETE CONFIRM ═══ */}
      {deleteId && (
        <Overlay onClose={() => setDeleteId(null)}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: '#FEF2F2', display: 'grid', placeItems: 'center', margin: '0 auto 14px' }}>
              <Trash2 size={20} color="#DC2626" />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 8px' }}>O'chirishni tasdiqlang</h3>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 22 }}>
              {deleteId.type === 'key'
                ? 'Bu API kalit butunlay o\'chiriladi. Undan foydalanuvchi tizimlar ishlamay qoladi.'
                : 'Bu webhook o\'chiriladi. Voqealar bundan keyin bu URLga yuborilmaydi.'}
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setDeleteId(null)} style={{ ...cancelBtn, flex: 1 }}>Bekor</button>
              <button
                onClick={() => deleteId.type === 'key'
                  ? deleteKeyMutation.mutate(deleteId.id)
                  : deleteWhMutation.mutate(deleteId.id)
                }
                style={{ flex: 2, padding: '10px 0', borderRadius: 10, border: 'none', background: '#DC2626', color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 700, fontFamily: "'Outfit', sans-serif" }}>
                O'chirish
              </button>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  );
}
// =============================================================================
// DELIVERY LOGS COMPONENT
// =============================================================================

interface DeliveryLog {
  id:              number;
  event_type:      string;
  success:         boolean;
  status_code:     number | null;
  latency_ms:      number | null;
  error_message:   string | null;
  payload_preview: string | null;
  delivery_id:     string | null;
  created_at:      string;
}

interface DeliveryLogsResponse {
  webhook_id:   number;
  webhook_name: string;
  stats: {
    total:          number;
    success_count:  number;
    failure_count:  number;
    success_rate:   number;
    avg_latency_ms: number | null;
  };
  total: number;
  items: DeliveryLog[];
}

function DeliveryLogsTab({
  webhooks, selectedId, onSelect,
}: {
  webhooks:   WebhookResponse[];
  selectedId: number | null;
  onSelect:   (id: number | null) => void;
}) {
  const [filterSuccess, setFilterSuccess] = useState<string>('all');

  const whId = selectedId ?? webhooks[0]?.id ?? null;

  const { data, isLoading, refetch } = useQuery<DeliveryLogsResponse>({
    queryKey: ['integrations', 'delivery-logs', whId, filterSuccess],
    queryFn:  () => {
      if (!whId) return Promise.resolve(null as any);
      const s = filterSuccess === 'all' ? '' : `&success=${filterSuccess === 'success'}`;
      return apiFetch<DeliveryLogsResponse>(
        `/api/v1/integrations/webhooks/${whId}/deliveries?limit=50${s}`
      );
    },
    enabled: !!whId,
    refetchInterval: 30_000,
  });

  const card: React.CSSProperties = {
    background: '#fff', border: '1px solid #E4E7ED',
    borderRadius: 12, padding: '16px 18px', marginBottom: 10,
  };

  return (
    <div>
      {/* Webhook selector */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 18, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {webhooks.map(wh => (
            <button key={wh.id} onClick={() => onSelect(wh.id)} style={{
              padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              border: '1px solid', cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
              background: (selectedId ?? webhooks[0]?.id) === wh.id ? '#EFF6FF' : '#fff',
              borderColor: (selectedId ?? webhooks[0]?.id) === wh.id ? '#93C5FD' : '#E4E7ED',
              color: (selectedId ?? webhooks[0]?.id) === wh.id ? '#1D4ED8' : '#374151',
            }}>
              {wh.name}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          {['all', 'success', 'error'].map(f => (
            <button key={f} onClick={() => setFilterSuccess(f)} style={{
              padding: '5px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600,
              border: '1px solid', cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
              background: filterSuccess === f ? '#1E3EB4' : '#fff',
              borderColor: filterSuccess === f ? '#1E3EB4' : '#E4E7ED',
              color: filterSuccess === f ? '#fff' : '#6B7280',
            }}>
              {f === 'all' ? 'Hammasi' : f === 'success' ? '✅ Muvaffaqiyatli' : '❌ Xatolar'}
            </button>
          ))}
          <button onClick={() => refetch()} style={{
            padding: '5px 10px', border: '1px solid #E4E7ED',
            borderRadius: 7, background: '#fff', cursor: 'pointer',
          }}>
            <RefreshCw size={13} color="#6B7280" />
          </button>
        </div>
      </div>

      {/* Stats */}
      {data?.stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
          {[
            { label: 'Jami',            value: data.stats.total,          color: '#1E3EB4', bg: '#EFF6FF' },
            { label: 'Muvaffaqiyatli',  value: data.stats.success_count,  color: '#059669', bg: '#ECFDF5' },
            { label: 'Xatolar',         value: data.stats.failure_count,  color: '#DC2626', bg: '#FEF2F2' },
            { label: 'O\'rtacha',       value: data.stats.avg_latency_ms ? `${data.stats.avg_latency_ms}ms` : '—', color: '#D97706', bg: '#FFFBEB' },
          ].map(({ label, value, color, bg }) => (
            <div key={label} style={{ ...card, marginBottom: 0, background: bg, border: 'none', padding: '12px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color }}>{value}</div>
              <div style={{ fontSize: 11, color: '#6B7280', marginTop: 3 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Success rate bar */}
      {data?.stats && data.stats.total > 0 && (
        <div style={{ ...card, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: '#6B7280' }}>Muvaffaqiyat darajasi</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: data.stats.success_rate >= 90 ? '#059669' : data.stats.success_rate >= 70 ? '#D97706' : '#DC2626' }}>
              {data.stats.success_rate}%
            </span>
          </div>
          <div style={{ height: 6, background: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 3,
              width: `${data.stats.success_rate}%`,
              background: data.stats.success_rate >= 90 ? '#10B981' : data.stats.success_rate >= 70 ? '#F59E0B' : '#EF4444',
              transition: 'width .4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Logs list */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>Yuklanmoqda...</div>
      ) : !data?.items.length ? (
        <div style={{ ...card, textAlign: 'center', padding: '40px 20px' }}>
          <Activity size={32} color="#D1D5DB" style={{ margin: '0 auto 12px', display: 'block' }} />
          <p style={{ color: '#9CA3AF', margin: 0 }}>
            {webhooks.length === 0
              ? 'Hech qanday webhook yo\'q. Avval webhook qo\'shing.'
              : 'Delivery log yo\'q. Webhook ishga tushganda bu yerda ko\'rinadi.'}
          </p>
        </div>
      ) : (
        data.items.map(log => (
          <div key={log.id} style={{
            ...card,
            borderLeft: `3px solid ${log.success ? '#10B981' : '#EF4444'}`,
            display: 'grid', gridTemplateColumns: '28px 1fr auto', gap: 12, alignItems: 'start',
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: log.success ? '#ECFDF5' : '#FEF2F2',
              display: 'grid', placeItems: 'center',
            }}>
              {log.success
                ? <CheckCircle size={14} color="#10B981" />
                : <XCircle    size={14} color="#EF4444" />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: 12, fontWeight: 700,
                  background: '#F3F4F6', padding: '2px 8px', borderRadius: 5,
                  fontFamily: 'JetBrains Mono, monospace', color: '#374151',
                }}>
                  {log.event_type}
                </span>
                {log.status_code && (
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 5, fontWeight: 600,
                    background: log.success ? '#ECFDF5' : '#FEF2F2',
                    color: log.success ? '#059669' : '#DC2626',
                  }}>
                    HTTP {log.status_code}
                  </span>
                )}
                {log.latency_ms && (
                  <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                    ⏱ {log.latency_ms}ms
                  </span>
                )}
              </div>
              {log.error_message && (
                <div style={{
                  fontSize: 12, color: '#DC2626',
                  background: '#FEF2F2', borderRadius: 6,
                  padding: '4px 8px', marginBottom: 4,
                }}>
                  {log.error_message}
                </div>
              )}
              {log.payload_preview && (
                <details style={{ fontSize: 11, color: '#6B7280' }}>
                  <summary style={{ cursor: 'pointer' }}>Payload ko'rish</summary>
                  <pre style={{
                    margin: '6px 0 0', padding: '8px',
                    background: '#F8FAFC', borderRadius: 6,
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11, overflowX: 'auto', whiteSpace: 'pre-wrap',
                  }}>
                    {log.payload_preview}
                  </pre>
                </details>
              )}
            </div>
            <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'right', whiteSpace: 'nowrap' }}>
              {new Date(log.created_at).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              <br />
              {new Date(log.created_at).toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short' })}
            </div>
          </div>
        ))
      )}
    </div>
  );
}