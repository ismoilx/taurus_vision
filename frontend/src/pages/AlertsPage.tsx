/**
 * Alerts Page — Sprint 4 (yangi sahifa)
 *
 * Ferma alertlarini ko'rish, filter, resolve/dismiss qilish.
 */

import { useState, useEffect } from 'react';
import {
  Bell, AlertCircle, CheckCircle, Clock,
  RefreshCw, AlertTriangle, X, Eye,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import config from '../config';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Alert {
  id: number;
  alert_type: string;
  status: string;
  severity: string;
  title: string;
  message: string;
  animal_id?: number;
  animal_tag?: string;
  camera_id?: string;
  created_at: string;
  resolved_at?: string;
}

interface AlertStats {
  total: number;
  open: number;
  seen: number;
  resolved: number;
  by_severity: { critical?: number; high?: number; medium?: number; low?: number };
  by_type: Record<string, number>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const API = config.apiUrl;

function severityColor(s: string) {
  switch (s) {
    case 'critical': return 'bg-red-100 text-red-800 border-red-200';
    case 'high':     return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium':   return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    default:         return 'bg-blue-100 text-blue-800 border-blue-200';
  }
}

function statusIcon(s: string) {
  switch (s) {
    case 'OPEN':     return <AlertCircle className="w-4 h-4 text-red-500" />;
    case 'SEEN':     return <Eye className="w-4 h-4 text-yellow-500" />;
    case 'RESOLVED': return <CheckCircle className="w-4 h-4 text-green-500" />;
    default:         return <X className="w-4 h-4 text-gray-400" />;
  }
}

function alertTypeLabel(t: string) {
  const m: Record<string, string> = {
    animal_missing:       '🐄 Jonivor yo\'qolgan',
    animal_missing_long:  '🐄 Uzoq vaqt yo\'q',
    weight_loss:          '⚖️  Vazn kamaydi',
    weight_loss_critical: '⚖️  Kritik vazn kamayishi',
    adi_warning:          '📊 ADI ogohlantirish',
    adi_critical:         '📊 ADI kritik',
    camera_offline:       '📷 Kamera o\'chdi',
    never_detected:       '🔍 Hech qachon aniqlanmagan',
    manual:               '✏️  Qo\'lda yaratilgan',
  };
  return m[t] ?? t;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const [alerts, setAlerts]       = useState<Alert[]>([]);
  const [stats,  setStats]        = useState<AlertStats | null>(null);
  const [filter, setFilter]       = useState<'all' | 'OPEN' | 'SEEN' | 'RESOLVED'>('all');
  const [loading, setLoading]     = useState(true);
  const [actionId, setActionId]   = useState<number | null>(null);

  useEffect(() => { loadData(); }, [filter]);

  async function loadData() {
    setLoading(true);
    try {
      const params = filter === 'all' ? '' : `?status=${filter}`;
      const [alertsResp, statsResp] = await Promise.all([
        apiFetch<any>(`/api/v1/alerts/${params}`),
        apiFetch<AlertStats>('/api/v1/alerts/stats'),
      ]);
      const arr: Alert[] = Array.isArray(alertsResp)
        ? alertsResp
        : (alertsResp?.items ?? alertsResp?.alerts ?? []);
      setAlerts(arr);
      setStats(statsResp);
    } catch (e) {
      console.error('Alerts load error:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkSeen(id: number) {
    setActionId(id);
    try {
      await apiFetch(`/api/v1/alerts/${id}/seen`, { method: 'PATCH' });
      await loadData();
    } catch (e) { console.error(e); }
    finally { setActionId(null); }
  }

  async function handleResolve(id: number) {
    setActionId(id);
    try {
      await apiFetch(`/api/v1/alerts/${id}/resolve`, {
        method: 'PATCH',
        body: JSON.stringify({ note: 'Frontend orqali yopildi' }),
      });
      await loadData();
    } catch (e) { console.error(e); }
    finally { setActionId(null); }
  }

  async function handleDismiss(id: number) {
    setActionId(id);
    try {
      await apiFetch(`/api/v1/alerts/${id}/dismiss`, { method: 'PATCH' });
      await loadData();
    } catch (e) { console.error(e); }
    finally { setActionId(null); }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Bell className="w-8 h-8 text-yellow-500" />
            Alertlar
          </h1>
          <p className="text-gray-500 mt-1">Ferma xabardorliklari va ogohlantirishlar</p>
        </div>
        <button onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Yangilash
        </button>
      </div>

      {/* ── Stats kartlari ── */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Jami',      val: stats.total,    color: 'bg-gray-50    border-gray-200',   text: 'text-gray-800'  },
            { label: 'Ochiq',     val: stats.open,     color: 'bg-red-50     border-red-200',    text: 'text-red-700'   },
            { label: "Ko'rildi",  val: stats.seen,     color: 'bg-yellow-50  border-yellow-200', text: 'text-yellow-700'},
            { label: 'Yopilgan',  val: stats.resolved, color: 'bg-green-50   border-green-200',  text: 'text-green-700' },
          ].map(c => (
            <div key={c.label} className={`rounded-xl border p-5 ${c.color}`}>
              <div className={`text-3xl font-bold ${c.text} mb-1`}>{c.val}</div>
              <div className="text-sm text-gray-600">{c.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Filter tabs ── */}
      <div className="flex gap-2 mb-6 border-b border-gray-200 pb-0">
        {(['all','OPEN','SEEN','RESOLVED'] as const).map(f => (
          <button key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === f
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {f === 'all' ? 'Barchasi' : f === 'OPEN' ? 'Ochiq'
              : f === 'SEEN' ? "Ko'rildi" : 'Yopilgan'}
            {stats && f === 'OPEN' && stats.open > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">
                {stats.open}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Alert ro'yxati ── */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">
          <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin opacity-50" />
          <p>Yuklanmoqda...</p>
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-400" />
          <p className="text-gray-500 font-medium">Alertlar yo'q</p>
          <p className="text-sm text-gray-400 mt-1">Hamma narsa yaxshi! ✅</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <div key={alert.id}
              className={`bg-white rounded-xl border p-5 transition-all ${
                alert.status === 'OPEN'
                  ? 'border-red-200 shadow-sm'
                  : 'border-gray-200 opacity-80'
              }`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {/* Status icon */}
                  <div className="mt-0.5 shrink-0">{statusIcon(alert.status)}</div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-semibold text-gray-900">
                        {alertTypeLabel(alert.alert_type)}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${severityColor(alert.severity)}`}>
                        {alert.severity}
                      </span>
                      {alert.animal_tag && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-mono">
                          {alert.animal_tag}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600">{alert.message}</p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {(alert.created_at || (alert as any).triggered_at)
                          ? formatDistanceToNow(new Date(alert.created_at || (alert as any).triggered_at), { addSuffix: true })
                          : "Noma'lum vaqt"}
                      </span>
                      {alert.camera_id && (
                        <span>Kamera: {alert.camera_id}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                {alert.status !== 'RESOLVED' && alert.status !== 'DISMISSED' && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    {alert.status === 'OPEN' && (
                      <button onClick={() => handleMarkSeen(alert.id)}
                        disabled={actionId === alert.id}
                        className="flex items-center gap-1 px-3 py-1.5 bg-yellow-50 text-yellow-700 hover:bg-yellow-100 rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
                        <Eye className="w-3.5 h-3.5" /> Ko'rdim
                      </button>
                    )}
                    <button onClick={() => handleResolve(alert.id)}
                      disabled={actionId === alert.id}
                      className="flex items-center gap-1 px-3 py-1.5 bg-green-50 text-green-700 hover:bg-green-100 rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
                      <CheckCircle className="w-3.5 h-3.5" /> Yopish
                    </button>
                    <button onClick={() => handleDismiss(alert.id)}
                      disabled={actionId === alert.id}
                      className="p-1.5 bg-gray-50 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Severity statistikasi */}
      {stats && Object.keys(stats.by_severity || {}).length > 0 && (
        <div className="mt-8 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            Jiddiylik bo'yicha taqsimot
          </h3>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(stats.by_severity).map(([s, count]) => (
              <div key={s} className={`px-3 py-1.5 rounded-lg border text-sm font-medium ${severityColor(s)}`}>
                {s}: {count}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}