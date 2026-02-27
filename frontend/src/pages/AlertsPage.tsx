/**
 * Alerts Page — Taurus Vision
 *
 * Barcha tuzatilgan buglar:
 *   ✅ alert.description (oldin: .message)
 *   ✅ alert.animal_tag_id (oldin: .animal_tag)
 *   ✅ Status lowercase: 'open'|'seen'|'resolved' (oldin uppercase)
 *   ✅ AlertListResponse.items array (oldin to'g'ridan array deb qabul qilgan)
 *   ✅ AlertStatsResponse to'g'ri maydonlar: total_open, critical_open va h.k.
 *   ✅ Resolve: { resolved_by, resolution_note } (oldin: { note })
 *   ✅ Dismiss: { dismissed_by, reason }
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Bell, AlertCircle, CheckCircle, Clock,
  RefreshCw, AlertTriangle, X, Eye, Shield,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Alert {
  id: number;
  alert_type: string;
  status: string;           // 'open' | 'seen' | 'resolved' | 'dismissed'
  severity: string;         // 'low' | 'medium' | 'high' | 'critical'
  title: string;
  description: string;      // ← to'g'ri maydon nomi
  animal_id?: number;
  animal_tag_id?: string;   // ← to'g'ri maydon nomi
  camera_id?: string;
  triggered_at: string;
  resolved_at?: string;
  resolved_by?: string;
}

interface AlertListResponse {
  total: number;
  limit: number;
  offset: number;
  items: Alert[];           // ← items ichida
}

// AlertStatsResponse — backend tomonidan qaytariladigan haqiqiy maydonlar
interface AlertStats {
  total_open: number;
  critical_open: number;
  high_open: number;
  medium_open: number;
  low_open: number;
  resolved_today: number;
  avg_resolution_minutes?: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function severityColor(s: string): string {
  switch (s) {
    case 'critical': return 'bg-red-100 text-red-800 border-red-200';
    case 'high':     return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium':   return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    default:         return 'bg-blue-100 text-blue-800 border-blue-200';
  }
}

function severityDot(s: string): string {
  switch (s) {
    case 'critical': return 'bg-red-500';
    case 'high':     return 'bg-orange-500';
    case 'medium':   return 'bg-yellow-500';
    default:         return 'bg-blue-500';
  }
}

function statusIcon(s: string) {
  // Status API dan lowercase keladi: 'open', 'seen', 'resolved', 'dismissed'
  switch (s) {
    case 'open':      return <AlertCircle className="w-4 h-4 text-red-500" />;
    case 'seen':      return <Eye className="w-4 h-4 text-yellow-500" />;
    case 'resolved':  return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'dismissed': return <X className="w-4 h-4 text-gray-400" />;
    default:          return <Bell className="w-4 h-4 text-gray-400" />;
  }
}

function statusLabel(s: string): string {
  switch (s) {
    case 'open':      return "Ochiq";
    case 'seen':      return "Ko'rildi";
    case 'resolved':  return "Yopilgan";
    case 'dismissed': return "Bekor";
    default:          return s;
  }
}

const ALERT_TYPE_LABELS: Record<string, string> = {
  adi_critical:        '📊 ADI Kritik',
  adi_warning:         '📊 ADI Ogohlantirish',
  adi_sharp_drop:      '📉 ADI Keskin Tushish',
  animal_missing:      '🐄 Jonivor Ko\'rinmaydi (24s)',
  animal_missing_long: '🐄 Jonivor Ko\'rinmaydi (48s+)',
  abnormal_movement:   '🏃 G\'ayritabiiy Harakat',
  isolation_detected:  '🔇 Ijtimoiy Ajralish',
  feeding_stopped:     '🌾 Ovqatlanish To\'xtadi',
  high_temperature:    '🌡️ Yuqori Harorat',
  low_heart_rate:      '❤️ Past Yurak Urishi',
  high_heart_rate:     '❤️ Yuqori Yurak Urishi',
  growth_stagnation:   '📏 O\'sish To\'xtadi',
  weight_loss:         '⚖️ Vazn Kamaydi',
  camera_offline:      '📷 Kamera O\'chdi',
  low_data_quality:    '📡 Ma\'lumot Sifati Past',
};

function alertTypeLabel(t: string): string {
  return ALERT_TYPE_LABELS[t] ?? t.replace(/_/g, ' ');
}

// ─── Filter tabs config ───────────────────────────────────────────────────────

type FilterKey = 'all' | 'open' | 'seen' | 'resolved';

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all',      label: 'Barchasi' },
  { key: 'open',     label: 'Ochiq' },
  { key: 'seen',     label: "Ko'rildi" },
  { key: 'resolved', label: 'Yopilgan' },
];

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AlertsPage() {
  const qClient = useQueryClient();
  const [filter,   setFilter]   = useState<FilterKey>('open');
  const [actionId, setActionId] = useState<number | null>(null);

  const alertsKey = ['alerts', filter];
  const statsKey  = ['alerts', 'stats'];

  const { data: alertsData, isFetching, isError, error } = useQuery({
    queryKey: alertsKey,
    queryFn: () => {
      const statusParam = filter === 'all' ? 'all' : filter;
      return apiFetch<AlertListResponse>(`/api/v1/alerts?status=${statusParam}&limit=100`);
    },
  });

  const { data: stats } = useQuery({
    queryKey: statsKey,
    queryFn:  () => apiFetch<AlertStats>('/api/v1/alerts/stats'),
  });

  const alerts = alertsData?.items ?? [];

  const invalidate = () => {
    qClient.invalidateQueries({ queryKey: ['alerts'] });
  };

  const seenMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/alerts/${id}/seen`, { method: 'PATCH' }),
    onMutate:  (id) => setActionId(id),
    onSettled: () => { setActionId(null); invalidate(); },
  });

  const resolveMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/alerts/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ resolved_by: 'Frontend foydalanuvchi', resolution_note: 'UI orqali yopildi' }),
    }),
    onMutate:  (id) => setActionId(id),
    onSettled: () => { setActionId(null); invalidate(); },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/alerts/${id}/dismiss`, {
      method: 'PATCH',
      body: JSON.stringify({ dismissed_by: 'Frontend foydalanuvchi', reason: "Noto'g'ri alarm" }),
    }),
    onMutate:  (id) => setActionId(id),
    onSettled: () => { setActionId(null); invalidate(); },
  });

  const handleMarkSeen  = (id: number) => seenMutation.mutate(id);
  const handleResolve   = (id: number) => resolveMutation.mutate(id);
  const handleDismiss   = (id: number) => dismissMutation.mutate(id);
  const loading = isFetching && alerts.length === 0;

  const openCount = stats ? (stats.total_open ?? 0) : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Bell className="w-8 h-8 text-yellow-500" />
            Alertlar
            {openCount > 0 && (
              <span className="ml-1 px-2.5 py-0.5 bg-red-100 text-red-700 text-sm rounded-full font-semibold">
                {openCount}
              </span>
            )}
          </h1>
          <p className="text-gray-500 mt-1">Ferma xabardorliklari va ogohlantirishlar</p>
        </div>
        <button
          onClick={() => qClient.invalidateQueries({ queryKey: ["alerts"] })}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Yangilash
        </button>
      </div>

      {/* ── Stats kartlari ── */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            {
              label: 'Jami ochiq',
              val:   stats.total_open,
              color: 'bg-red-50 border-red-200',
              text:  'text-red-700',
            },
            {
              label: 'Kritik',
              val:   stats.critical_open,
              color: 'bg-red-50 border-red-200',
              text:  'text-red-800',
            },
            {
              label: 'Yuqori',
              val:   stats.high_open,
              color: 'bg-orange-50 border-orange-200',
              text:  'text-orange-700',
            },
            {
              label: 'Bugun yopilgan',
              val:   stats.resolved_today,
              color: 'bg-green-50 border-green-200',
              text:  'text-green-700',
            },
          ].map(c => (
            <div key={c.label} className={`rounded-xl border p-5 ${c.color}`}>
              <div className={`text-3xl font-bold ${c.text} mb-1`}>{c.val}</div>
              <div className="text-sm text-gray-600">{c.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {isError ? (error instanceof Error ? error.message : "Xato") : ""}
        </div>
      )}

      {/* ── Filter tabs ── */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === f.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {f.label}
            {f.key === 'open' && stats && stats.total_open > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">
                {stats.total_open}
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
          <p className="text-gray-500 font-medium">
            {filter === 'open' ? 'Ochiq alertlar yo\'q ✅' : 'Bu bo\'limda alert yo\'q'}
          </p>
          <p className="text-sm text-gray-400 mt-1">Hamma narsa yaxshi!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <div
              key={alert.id}
              className={`bg-white rounded-xl border p-5 transition-all ${
                alert.status === 'open'
                  ? 'border-l-4 border-l-red-400 border-t-gray-200 border-r-gray-200 border-b-gray-200 shadow-sm'
                  : 'border-gray-200 opacity-80'
              }`}
            >
              <div className="flex items-start justify-between gap-4">

                {/* Left: content */}
                <div className="flex items-start gap-3 flex-1 min-w-0">

                  {/* Severity dot */}
                  <div className="mt-1.5 shrink-0">
                    <div className={`w-2.5 h-2.5 rounded-full ${severityDot(alert.severity)}`} />
                  </div>

                  {/* Text content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      {/* Status icon */}
                      {statusIcon(alert.status)}

                      {/* Alert type */}
                      <span className="text-sm font-semibold text-gray-900">
                        {alertTypeLabel(alert.alert_type)}
                      </span>

                      {/* Severity badge */}
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${severityColor(alert.severity)}`}>
                        {alert.severity}
                      </span>

                      {/* Status badge */}
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                        {statusLabel(alert.status)}
                      </span>

                      {/* Animal tag */}
                      {alert.animal_tag_id && (
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-mono font-semibold">
                          🐄 {alert.animal_tag_id}
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <p className="text-sm font-medium text-gray-800 mb-0.5">{alert.title}</p>

                    {/* Description — to'g'ri maydon */}
                    <p className="text-sm text-gray-500 leading-relaxed">{alert.description}</p>

                    {/* Meta */}
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {alert.triggered_at
                          ? formatDistanceToNow(new Date(alert.triggered_at), { addSuffix: true })
                          : '—'}
                      </span>
                      {alert.camera_id && (
                        <span>📷 {alert.camera_id}</span>
                      )}
                      {alert.resolved_at && alert.resolved_by && (
                        <span className="text-green-600">
                          ✓ {alert.resolved_by} — {format(new Date(alert.resolved_at), 'dd.MM HH:mm')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: actions — faqat ochiq va ko'rilgan alertlar uchun */}
                {(alert.status === 'open' || alert.status === 'seen') && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    {alert.status === 'open' && (
                      <button
                        onClick={() => handleMarkSeen(alert.id)}
                        disabled={actionId === alert.id}
                        className="flex items-center gap-1 px-3 py-1.5 bg-yellow-50 text-yellow-700 hover:bg-yellow-100 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                      >
                        <Eye className="w-3.5 h-3.5" /> Ko'rdim
                      </button>
                    )}
                    <button
                      onClick={() => handleResolve(alert.id)}
                      disabled={actionId === alert.id}
                      className="flex items-center gap-1 px-3 py-1.5 bg-green-50 text-green-700 hover:bg-green-100 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <CheckCircle className="w-3.5 h-3.5" /> Yopish
                    </button>
                    <button
                      onClick={() => handleDismiss(alert.id)}
                      disabled={actionId === alert.id}
                      title="Noto'g'ri alarm deb bekor qilish"
                      className="p-1.5 bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600 rounded-lg transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Jiddiylik taqsimoti ── */}
      {stats && (
        <div className="mt-8 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-blue-500" />
            Joriy ochiq alertlar jiddiylik bo'yicha
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Kritik',   val: stats.critical_open, color: 'text-red-700',    bg: 'bg-red-50    border-red-200'    },
              { label: 'Yuqori',   val: stats.high_open,     color: 'text-orange-700', bg: 'bg-orange-50 border-orange-200' },
              { label: "O'rtacha", val: stats.medium_open,   color: 'text-yellow-700', bg: 'bg-yellow-50 border-yellow-200' },
              { label: 'Past',     val: stats.low_open,      color: 'text-blue-700',   bg: 'bg-blue-50   border-blue-200'   },
            ].map(c => (
              <div key={c.label} className={`rounded-lg border p-3 ${c.bg}`}>
                <div className={`text-2xl font-bold ${c.color}`}>{c.val}</div>
                <div className="text-xs text-gray-500 mt-0.5">{c.label}</div>
              </div>
            ))}
          </div>
          {stats.avg_resolution_minutes != null && (
            <p className="mt-3 text-xs text-gray-400">
              O'rtacha hal etish vaqti: <span className="font-medium text-gray-600">
                {stats.avg_resolution_minutes.toFixed(0)} daqiqa
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}