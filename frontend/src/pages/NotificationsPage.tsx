/**
 * Taurus Vision — Notifications Page (Sprint 11)
 *
 * Email bildirishnomalar sozlamalari va boshqaruvi.
 *
 * SECTIONS:
 *   1. SMTP Holati — sozlanganmi, qanday rejimda ishlayapti
 *   2. Recipient ro'yxati — kim email oladi
 *   3. Severity qoidalari — qaysi darajada email yuboriladi
 *   4. Test Email — SMTP ni sinab ko'rish
 *   5. Alert Email — bitta alertga qo'lda email yuborish
 *   6. .env sozlash yo'riqnomasi
 */

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Mail, CheckCircle, XCircle, AlertCircle,
  Send, Settings, Users, Bell, RefreshCw,
  Info, ChevronRight, Copy, Eye, EyeOff,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------
function StatCard({
  icon: Icon, label, value, color, bg,
}: {
  icon: any; label: string; value: string; color: string; bg: string;
}) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #E4E7ED',
      borderRadius: 12,
      padding: '18px 20px',
      display: 'flex', alignItems: 'center', gap: 14,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        background: bg, display: 'grid', placeItems: 'center', flexShrink: 0,
      }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#0D1117', marginTop: 2 }}>{value}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Env Guide Modal
// ---------------------------------------------------------------------------
function EnvGuideModal({ onClose }: { onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  const envExample = `# .env fayliga qo'shing:

# Gmail uchun:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=Taurus Vision <your-email@gmail.com>

# Yandex uchun:
# SMTP_HOST=smtp.yandex.ru
# SMTP_PORT=587

# Bildirishnoma oluvchilar (vergul bilan ajrating):
NOTIFICATION_EMAILS=admin@farm.uz,vet@farm.uz,manager@farm.uz`;

  function copyEnv() {
    navigator.clipboard.writeText(envExample);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        width: '100%', maxWidth: 600, maxHeight: '90vh', overflow: 'auto',
      }}>
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid #F3F4F6',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Settings size={18} color="#1E3EB4" />
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: 0 }}>
              SMTP Sozlash Yo'riqnomasi
            </h2>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 18, color: '#9CA3AF',
          }}>✕</button>
        </div>

        <div style={{ padding: '20px 24px' }}>

          {/* Steps */}
          {[
            {
              step: '1',
              title: 'Gmail App Password yarating',
              content: 'Google Account → Security → 2-Step Verification → App Passwords → "Mail" uchun parol yarating',
            },
            {
              step: '2',
              title: '.env faylini tahrirlang',
              content: '~/taurus-vision/backend/.env faylini oching va quyidagi qatorlarni qo\'shing:',
            },
            {
              step: '3',
              title: 'Backend restart qiling',
              content: 'cd ~/taurus-vision && docker compose restart backend',
            },
            {
              step: '4',
              title: 'Test Email yuborib ko\'ring',
              content: 'Sahifadagi "Test Email" tugmasini bosing',
            },
          ].map(({ step, title, content }) => (
            <div key={step} style={{
              display: 'flex', gap: 14, marginBottom: 20,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: '#EEF2FF', color: '#1E3EB4',
                display: 'grid', placeItems: 'center',
                fontSize: 13, fontWeight: 700, flexShrink: 0,
              }}>
                {step}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#0D1117', marginBottom: 4 }}>
                  {title}
                </div>
                <div style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.5 }}>{content}</div>
              </div>
            </div>
          ))}

          {/* Code block */}
          <div style={{ position: 'relative' }}>
            <pre style={{
              background: '#0D1117', color: '#E5E7EB',
              padding: '16px 20px', borderRadius: 10,
              fontSize: 12, lineHeight: 1.7,
              overflowX: 'auto', margin: 0,
            }}>
              {envExample}
            </pre>
            <button
              onClick={copyEnv}
              style={{
                position: 'absolute', top: 10, right: 10,
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 10px',
                background: copied ? '#10B981' : 'rgba(255,255,255,0.1)',
                border: 'none', borderRadius: 6,
                color: '#fff', fontSize: 11, fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {copied ? <CheckCircle size={12} /> : <Copy size={12} />}
              {copied ? 'Nusxalandi!' : 'Nusxalash'}
            </button>
          </div>

          {/* Note */}
          <div style={{
            display: 'flex', gap: 10, marginTop: 16,
            background: '#FFF7ED', border: '1px solid #FED7AA',
            borderRadius: 8, padding: '10px 14px',
          }}>
            <Info size={14} color="#EA580C" style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 12, color: '#92400E', margin: 0, lineHeight: 1.5 }}>
              Gmail uchun odatiy parol emas, <strong>App Password</strong> kerak.
              2-Step Verification yoqilgan bo'lishi shart.
            </p>
          </div>
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid #F3F4F6' }}>
          <button onClick={onClose} style={{
            width: '100%', padding: '10px',
            background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8,
            fontSize: 14, fontWeight: 700, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            Tushunarli
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function NotificationsPage() {
  const [testEmail,   setTestEmail]  = useState('');
  const [testResult,  setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [alertId,     setAlertId]    = useState('');
  const [sendResult,  setSendResult] = useState<any>(null);
  const [showGuide,   setShowGuide]  = useState(false);

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: settings, isLoading: loading, refetch } = useQuery({
    queryKey: ['notifications', 'settings'],
    queryFn:  () => apiFetch<SmtpSettings>('/api/v1/notifications/settings'),
  });

  // ── Mutations ─────────────────────────────────────────────────────────────
  const testMutation = useMutation({
    mutationFn: () => apiFetch<any>('/api/v1/notifications/test', {
      method: 'POST',
      body: JSON.stringify({ recipient: testEmail }),
    }),
    onSuccess: (result) => setTestResult({
      ok: result.sent || result.ok,
      message: result.message || (result.sent ? 'Email yuborildi!' : 'Xato yuz berdi'),
    }),
    onError: (e: Error) => setTestResult({ ok: false, message: e.message }),
  });

  const sendMutation = useMutation({
    mutationFn: () => apiFetch<any>(`/api/v1/notifications/send/${alertId}`, {
      method: 'POST',
      body: JSON.stringify({ recipients: null }),
    }),
    onSuccess: setSendResult,
    onError: (e: Error) => setSendResult({ sent: false, error: e.message }),
  });

  function handleTestEmail()  { if (testEmail.trim())  testMutation.mutate(); }
  function handleSendAlert()  { if (alertId.trim())    sendMutation.mutate(); }
  function handleRefresh()    { refetch(); }

  const testLoading = testMutation.isPending;
  const sendLoading = sendMutation.isPending;
  const refreshing  = false;

  if (loading) {
    return (
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '48px 24px', textAlign: 'center', color: '#9CA3AF', fontFamily: 'Outfit, sans-serif' }}>
        Yuklanmoqda...
      </div>
    );
  }

  const isConfigured = settings?.configured ?? false;

  return (
    <div style={{
      maxWidth: 1000, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
            Bildirishnomalar
          </h1>
          <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
            Email xabarnomalar sozlamalari va boshqaruvi
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={handleRefresh} disabled={refreshing} style={{
            padding: '9px 12px',
            border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff',
            cursor: 'pointer', display: 'flex', alignItems: 'center',
          }}>
            <RefreshCw size={15} color="#6B7280"
              style={{ animation: refreshing ? 'spin .7s linear infinite' : 'none' }} />
          </button>
          <button onClick={() => setShowGuide(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 18px',
            background: '#F9FAFB', color: '#374151',
            border: '1px solid #D1D5DB', borderRadius: 8,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            <Settings size={15} />
            SMTP Sozlash
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
        <StatCard
          icon={isConfigured ? CheckCircle : XCircle}
          label="SMTP Holati"
          value={isConfigured ? 'Sozlangan' : 'Sozlanmagan'}
          color={isConfigured ? '#10B981' : '#9CA3AF'}
          bg={isConfigured ? '#ECFDF5' : '#F3F4F6'}
        />
        <StatCard
          icon={Users}
          label="Recipient soni"
          value={String(settings?.total_recipients ?? 0)}
          color="#3B82F6"
          bg="#EFF6FF"
        />
        <StatCard
          icon={Mail}
          label="Email rejimi"
          value={isConfigured ? 'SMTP' : 'Log rejimi'}
          color={isConfigured ? '#8B5CF6' : '#F59E0B'}
          bg={isConfigured ? '#F5F3FF' : '#FFF7ED'}
        />
        <StatCard
          icon={Bell}
          label="Kunlik digest"
          value="07:00 UTC"
          color="#059669"
          bg="#F0FDF4"
        />
      </div>

      {/* SMTP Status Banner */}
      <div style={{
        padding: '16px 20px',
        background: isConfigured ? '#F0FDF4' : '#FFF7ED',
        border: `1px solid ${isConfigured ? '#A7F3D0' : '#FED7AA'}`,
        borderRadius: 12, marginBottom: 24,
        display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        {isConfigured
          ? <CheckCircle size={18} color="#10B981" style={{ flexShrink: 0, marginTop: 1 }} />
          : <AlertCircle size={18} color="#EA580C" style={{ flexShrink: 0, marginTop: 1 }} />}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: isConfigured ? '#065F46' : '#92400E', marginBottom: 4 }}>
            {isConfigured
              ? `SMTP tayyor — ${settings?.smtp_host}:${settings?.smtp_port}`
              : 'SMTP sozlanmagan — email log da saqlanadi'}
          </div>
          <div style={{ fontSize: 12, color: isConfigured ? '#059669' : '#B45309' }}>
            {isConfigured
              ? `${settings?.smtp_user} orqali yuboriladi · ${settings?.total_recipients} ta recipient`
              : 'Alert emaillar log faylda ko\'rinadi. SMTP sozlash uchun "SMTP Sozlash" tugmasini bosing.'}
          </div>
        </div>
        {!isConfigured && (
          <button onClick={() => setShowGuide(true)} style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '6px 14px',
            background: '#EA580C', color: '#fff',
            border: 'none', borderRadius: 7,
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif', flexShrink: 0,
          }}>
            Sozlash <ChevronRight size={12} />
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>

        {/* Recipients */}
        <div style={{
          background: '#fff', border: '1px solid #E4E7ED',
          borderRadius: 14, padding: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Users size={15} color="#1E3EB4" />
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: 0 }}>
              Email Recipientlar
            </h3>
          </div>

          {settings?.recipients && settings.recipients.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {settings.recipients.map((email, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px',
                  background: '#F9FAFB', border: '1px solid #F3F4F6',
                  borderRadius: 8,
                }}>
                  <Mail size={13} color="#6B7280" />
                  <span style={{ fontSize: 13, color: '#0D1117', fontFamily: 'monospace' }}>
                    {email}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              padding: '20px', textAlign: 'center',
              background: '#F9FAFB', borderRadius: 8,
            }}>
              <Mail size={24} color="#D1D5DB" style={{ margin: '0 auto 8px' }} />
              <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
                Recipient sozlanmagan.<br />
                .env da NOTIFICATION_EMAILS ni kiriting.
              </p>
            </div>
          )}

          <p style={{ fontSize: 11, color: '#9CA3AF', margin: '10px 0 0' }}>
            Tahrirlash: .env → NOTIFICATION_EMAILS=email1,email2
          </p>
        </div>

        {/* Severity Rules */}
        <div style={{
          background: '#fff', border: '1px solid #E4E7ED',
          borderRadius: 14, padding: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Bell size={15} color="#1E3EB4" />
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: 0 }}>
              Severity Qoidalari
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { sev: 'critical', label: 'KRITIK',  emoji: '🔴', send: true },
              { sev: 'high',     label: 'YUQORI',  emoji: '🟠', send: true },
              { sev: 'medium',   label: "O'RTA",   emoji: '🟡', send: true },
              { sev: 'low',      label: 'PAST',    emoji: '🟢', send: false },
            ].map(({ sev, label, emoji, send }) => (
              <div key={sev} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 12px',
                background: '#F9FAFB', border: '1px solid #F3F4F6',
                borderRadius: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 14 }}>{emoji}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>{label}</span>
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  fontSize: 11, fontWeight: 600,
                  color: send ? '#059669' : '#9CA3AF',
                }}>
                  {send
                    ? <><CheckCircle size={12} /> Email yuboriladi</>
                    : <><XCircle size={12} /> Yuborilmaydi</>}
                </div>
              </div>
            ))}
          </div>

          <p style={{ fontSize: 11, color: '#9CA3AF', margin: '10px 0 0' }}>
            LOW darajali alertlar email yubormasdan log da qoladi.
          </p>
        </div>
      </div>

      {/* Test Email */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 14, padding: 24, marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Send size={15} color="#1E3EB4" />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            Test Email Yuborish
          </h3>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <input
            type="email"
            value={testEmail}
            onChange={e => setTestEmail(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleTestEmail()}
            placeholder="test@example.com"
            style={{
              flex: 1, padding: '10px 14px',
              border: '1px solid #D1D5DB', borderRadius: 8,
              fontSize: 13, color: '#0D1117', outline: 'none',
              fontFamily: 'monospace',
            }}
          />
          <button
            onClick={handleTestEmail}
            disabled={testLoading || !testEmail.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '10px 20px',
              background: testLoading || !testEmail.trim() ? '#9CA3AF' : '#1E3EB4',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700,
              cursor: testLoading || !testEmail.trim() ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}
          >
            {testLoading ? (
              <div style={{
                width: 14, height: 14, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.4)',
                borderTopColor: '#fff',
                animation: 'spin .7s linear infinite',
              }} />
            ) : <Send size={14} />}
            {testLoading ? 'Yuborilmoqda...' : 'Test Yuborish'}
          </button>
        </div>

        {testResult && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            marginTop: 12,
            padding: '10px 14px',
            background: testResult.ok ? '#F0FDF4' : '#FEF2F2',
            border: `1px solid ${testResult.ok ? '#A7F3D0' : '#FECACA'}`,
            borderRadius: 8,
          }}>
            {testResult.ok
              ? <CheckCircle size={14} color="#10B981" style={{ flexShrink: 0, marginTop: 1 }} />
              : <XCircle size={14} color="#DC2626" style={{ flexShrink: 0, marginTop: 1 }} />}
            <span style={{ fontSize: 13, color: testResult.ok ? '#065F46' : '#DC2626' }}>
              {testResult.message}
            </span>
          </div>
        )}
      </div>

      {/* Manual Alert Send */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 14, padding: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Bell size={15} color="#1E3EB4" />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            Alert Email Yuborish
          </h3>
        </div>

        <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 14px' }}>
          Mavjud alert ID ni kiriting — o'sha alert uchun email yuboriladi.
        </p>

        <div style={{ display: 'flex', gap: 12 }}>
          <input
            type="number"
            value={alertId}
            onChange={e => setAlertId(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSendAlert()}
            placeholder="Alert ID (masalan: 1)"
            style={{
              flex: 1, padding: '10px 14px',
              border: '1px solid #D1D5DB', borderRadius: 8,
              fontSize: 13, color: '#0D1117', outline: 'none',
              fontFamily: 'monospace',
            }}
          />
          <button
            onClick={handleSendAlert}
            disabled={sendLoading || !alertId.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '10px 20px',
              background: sendLoading || !alertId.trim() ? '#9CA3AF' : '#7C3AED',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700,
              cursor: sendLoading || !alertId.trim() ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}
          >
            {sendLoading ? (
              <div style={{
                width: 14, height: 14, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.4)',
                borderTopColor: '#fff',
                animation: 'spin .7s linear infinite',
              }} />
            ) : <Mail size={14} />}
            {sendLoading ? 'Yuborilmoqda...' : 'Email Yuborish'}
          </button>
        </div>

        {sendResult && (
          <div style={{
            marginTop: 12,
            padding: '10px 14px',
            background: sendResult.sent ? '#F0FDF4' : '#FEF2F2',
            border: `1px solid ${sendResult.sent ? '#A7F3D0' : '#FECACA'}`,
            borderRadius: 8,
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginBottom: sendResult.recipients?.length ? 6 : 0,
            }}>
              {sendResult.sent
                ? <CheckCircle size={14} color="#10B981" />
                : <XCircle size={14} color="#DC2626" />}
              <span style={{ fontSize: 13, fontWeight: 600, color: sendResult.sent ? '#065F46' : '#DC2626' }}>
                {sendResult.sent
                  ? `Email ${sendResult.mode === 'log' ? '(log rejimda)' : ''} muvaffaqiyatli yuborildi`
                  : `Xato: ${sendResult.error || 'Noma\'lum xato'}`}
              </span>
            </div>
            {sendResult.recipients?.length > 0 && (
              <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>
                Recipientlar: {sendResult.recipients.join(', ')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Guide Modal */}
      {showGuide && <EnvGuideModal onClose={() => setShowGuide(false)} />}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}