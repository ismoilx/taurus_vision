/**
 * BehaviorPage — Jonivorlar Xatti-harakat Tahlili (Sprint 11-12)
 *
 * IMKONIYATLAR:
 *   - Poda umumiy holati (HerdBehaviorSummary) — 4 ta o'rtacha ko'rsatkich
 *   - Holat taqsimoti: excellent / good / fair / poor / critical
 *   - Diqqat talab qiladigan jonivorlar ro'yxati
 *   - Alohida jonivor tanlash → to'liq tahlil: 4 komponent + anomaliyalar
 *   - Tahlil davri: 24h / 48h / 72h
 *
 * BACKEND: /api/v1/behavior/herd/summary, /api/v1/behavior/{id}
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Activity, Utensils, Wind, Users,
  AlertTriangle, CheckCircle, XCircle, TrendingUp,
  TrendingDown, Minus, RefreshCw, ChevronRight,
  ArrowLeft, Zap,
} from 'lucide-react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface BehaviorScore {
  value:       number;
  max_value:   number;
  percentage:  number;
  status:      'excellent' | 'good' | 'fair' | 'poor' | 'critical';
  description: string;
}

interface BehaviorAnalysis {
  animal_id:       number;
  animal_tag:      string;
  period_start:    string;
  period_end:      string;
  detection_count: number;
  activity:        BehaviorScore;
  feeding:         BehaviorScore;
  movement:        BehaviorScore;
  social:          BehaviorScore;
  overall_score:   number;
  overall_status:  string;
  anomalies:       string[];
  recommendations: string[];
  adi_trend:       string | null;
  adi_7day:        number[];
  analyzed_at:     string;
}

interface AttentionItem {
  animal_id:     number;
  animal_tag:    string;
  overall_score: number;
  status:        string;
  anomalies:     string[];
  adi_trend:     string | null;
}

interface HerdSummary {
  total_animals:    number;
  analyzed_count:   number;
  period:           string;
  excellent_count:  number;
  good_count:       number;
  fair_count:       number;
  poor_count:       number;
  critical_count:   number;
  no_data_count:    number;
  avg_activity:     number;
  avg_feeding:      number;
  avg_movement:     number;
  avg_social:       number;
  avg_overall:      number;
  attention_needed: AttentionItem[];
  generated_at:     string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STATUS_CFG = {
  excellent: { color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0', label: 'A\'lo',      icon: <CheckCircle size={14} /> },
  good:      { color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe', label: 'Yaxshi',    icon: <CheckCircle size={14} /> },
  fair:      { color: '#f59e0b', bg: '#fffbeb', border: '#fde68a', label: "O'rtacha",  icon: <AlertTriangle size={14} /> },
  poor:      { color: '#f97316', bg: '#fff7ed', border: '#fed7aa', label: 'Yomon',     icon: <AlertTriangle size={14} /> },
  critical:  { color: '#ef4444', bg: '#fef2f2', border: '#fecaca', label: 'Kritik',    icon: <XCircle size={14} /> },
} as const;

const HOUR_OPTIONS = [
  { value: 24,  label: '24 soat' },
  { value: 48,  label: '48 soat' },
  { value: 72,  label: '72 soat' },
  { value: 168, label: '7 kun'   },
];

const COMPONENT_META = {
  activity: { icon: <Activity size={18} />,  label: 'Faollik',       color: '#6366f1' },
  feeding:  { icon: <Utensils size={18} />,  label: 'Oziqlanish',    color: '#10b981' },
  movement: { icon: <Wind size={18} />,      label: 'Harakat',       color: '#3b82f6' },
  social:   { icon: <Users size={18} />,     label: 'Ijtimoiy xulq', color: '#f59e0b' },
};

// =============================================================================
// HELPERS
// =============================================================================

function ScoreBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color }}
      />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CFG[status as keyof typeof STATUS_CFG] ?? STATUS_CFG.fair;
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function TrendBadge({ trend }: { trend: string | null }) {
  if (!trend) return null;
  const cfg = trend === 'improving'
    ? { icon: <TrendingUp size={12} />, color: '#10b981', label: 'O\'sish' }
    : trend === 'declining'
    ? { icon: <TrendingDown size={12} />, color: '#ef4444', label: 'Pasayish' }
    : { icon: <Minus size={12} />, color: '#6b7280', label: 'Barqaror' };
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-gray-50 border border-gray-200"
      style={{ color: cfg.color }}>
      {cfg.icon} ADI {cfg.label}
    </span>
  );
}

// =============================================================================
// COMPONENT CARD
// =============================================================================

function ComponentCard({ type, score }: { type: keyof typeof COMPONENT_META; score: BehaviorScore }) {
  const meta = COMPONENT_META[type];
  const sCfg = STATUS_CFG[score.status] ?? STATUS_CFG.fair;
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: meta.color + '1a', color: meta.color }}>
            {meta.icon}
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">{meta.label}</p>
            <p className="text-xs text-gray-400">{score.description.split('.')[0]}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold tabular-nums" style={{ color: meta.color }}>
            {score.percentage.toFixed(0)}%
          </p>
          <StatusBadge status={score.status} />
        </div>
      </div>
      <ScoreBar pct={score.percentage} color={meta.color} />
      <p className="text-xs text-gray-400 mt-2 line-clamp-2">{score.description}</p>
    </div>
  );
}

// =============================================================================
// HERD OVERVIEW CARD
// =============================================================================

function HerdCard({ label, value, max, color, icon }: {
  label: string; value: number; max: number; color: string; icon: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ background: color + '15', color }}>
          {icon}
        </div>
        <p className="text-sm font-medium text-gray-600">{label}</p>
      </div>
      <p className="text-3xl font-bold mb-2" style={{ color }}>{value.toFixed(0)}%</p>
      <ScoreBar pct={value} color={color} />
      <p className="text-xs text-gray-400 mt-1">Maksimal: {max}%</p>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function BehaviorPage() {
  const navigate  = useNavigate();
  const [hours, setHours]           = useState(24);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // ── Poda xulosasi ──────────────────────────────────────────────────────────
  const {
    data: herd,
    isFetching: herdLoading,
    refetch: refetchHerd,
  } = useQuery({
    queryKey: ['behavior', 'herd', hours],
    queryFn:  () => apiFetch<HerdSummary>(`/api/v1/behavior/herd/summary?hours=${hours}&limit=10`),
    staleTime: 5 * 60_000,
  });

  // ── Alohida jonivor tahlili (bosilganda) ──────────────────────────────────
  const {
    data: animalBehavior,
    isFetching: animalLoading,
  } = useQuery({
    queryKey: ['behavior', 'animal', selectedId, hours],
    queryFn:  () => apiFetch<BehaviorAnalysis>(`/api/v1/behavior/${selectedId}?hours=${hours}`),
    enabled:  !!selectedId,
    staleTime: 5 * 60_000,
  });

  // ── Qayta tahlil (POST trigger) ───────────────────────────────────────────
  const analyzeMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/behavior/${id}/analyze`, { method: 'POST' }),
    onSuccess:  (_d, id) => {
      // Cache ni yangilaymiz
      setSelectedId(null);
      setTimeout(() => setSelectedId(id), 100);
    },
  });

  // ── Derived ───────────────────────────────────────────────────────────────
  const distributionData = herd ? [
    { name: "A'lo",      value: herd.excellent_count, color: '#10b981' },
    { name: 'Yaxshi',    value: herd.good_count,      color: '#3b82f6' },
    { name: "O'rtacha",  value: herd.fair_count,      color: '#f59e0b' },
    { name: 'Yomon',     value: herd.poor_count,       color: '#f97316' },
    { name: 'Kritik',    value: herd.critical_count,   color: '#ef4444' },
  ] : [];

  const radarData = animalBehavior ? [
    { subject: 'Faollik',    value: animalBehavior.activity.percentage,  fullMark: 100 },
    { subject: 'Oziqlanish', value: animalBehavior.feeding.percentage,   fullMark: 100 },
    { subject: 'Harakat',    value: animalBehavior.movement.percentage,  fullMark: 100 },
    { subject: 'Ijtimoiy',   value: animalBehavior.social.percentage,    fullMark: 100 },
  ] : [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Xatti-harakat Tahlili</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {herd
              ? `${herd.analyzed_count} ta jonivor tahlil qilindi · ${herd.period}`
              : 'Yuklanmoqda...'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex rounded-xl border border-gray-200 overflow-hidden bg-white">
            {HOUR_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => setHours(opt.value)}
                className={`px-3 py-2 text-xs font-semibold transition-colors ${
                  hours === opt.value
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}>
                {opt.label}
              </button>
            ))}
          </div>
          <button onClick={() => refetchHerd()} disabled={herdLoading}
            className="p-2.5 border border-gray-200 rounded-xl text-gray-500 hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${herdLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Poda umumiy ko'rsatkichlari ──────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <HerdCard label="Faollik o'rtacha"    value={herd?.avg_activity ?? 0}  max={100} color="#6366f1" icon={<Activity size={20} />} />
        <HerdCard label="Oziqlanish o'rtacha" value={herd?.avg_feeding ?? 0}   max={100} color="#10b981" icon={<Utensils size={20} />} />
        <HerdCard label="Harakat o'rtacha"    value={herd?.avg_movement ?? 0}  max={100} color="#3b82f6" icon={<Wind size={20} />} />
        <HerdCard label="Ijtimoiy o'rtacha"   value={herd?.avg_social ?? 0}    max={100} color="#f59e0b" icon={<Users size={20} />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

        {/* ── Holat taqsimoti (Bar chart) ─────────────────────────────── */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Poda holati taqsimoti</h2>
          {herd ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={distributionData} barCategoryGap="30%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip formatter={(v: number) => [`${v} ta`, 'Soni']} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {distributionData.map((d, i) => (
                      <Cell key={i} fill={d.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                <span>Jami: {herd.total_animals} ta</span>
                <span>Tahlil: {herd.analyzed_count} ta</span>
                <span>Ma'lumot yo'q: {herd.no_data_count} ta</span>
              </div>
            </>
          ) : (
            <div className="h-[180px] flex items-center justify-center">
              <RefreshCw className="w-6 h-6 text-gray-300 animate-spin" />
            </div>
          )}
        </div>

        {/* ── Umumiy ball + status ──────────────────────────────────────── */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm flex flex-col items-center justify-center">
          {herd ? (
            <>
              <div className="relative w-36 h-36 mb-4">
                <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="#f3f4f6" strokeWidth="12" />
                  <circle cx="60" cy="60" r="50" fill="none"
                    stroke={herd.avg_overall >= 75 ? '#10b981' : herd.avg_overall >= 50 ? '#f59e0b' : '#ef4444'}
                    strokeWidth="12"
                    strokeDasharray={`${2 * Math.PI * 50 * herd.avg_overall / 100} ${2 * Math.PI * 50}`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <p className="text-3xl font-bold text-gray-900">{herd.avg_overall.toFixed(0)}</p>
                  <p className="text-xs text-gray-400">/ 100</p>
                </div>
              </div>
              <p className="text-sm font-semibold text-gray-700 mb-1">Poda umumiy ball</p>
              <StatusBadge status={
                herd.avg_overall >= 90 ? 'excellent' :
                herd.avg_overall >= 75 ? 'good' :
                herd.avg_overall >= 55 ? 'fair' :
                herd.avg_overall >= 35 ? 'poor' : 'critical'
              } />
            </>
          ) : (
            <div className="text-gray-300 text-sm">Yuklanmoqda...</div>
          )}
        </div>

        {/* ── Diqqat talab qiladiganlar ─────────────────────────────────── */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <AlertTriangle size={15} className="text-amber-500" />
            Diqqat talab qiladiganlar
          </h2>
          {!herd ? (
            <div className="text-gray-300 text-sm text-center py-8">Yuklanmoqda...</div>
          ) : herd.attention_needed.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle className="w-10 h-10 text-emerald-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">Barcha jonivorlar yaxshi holatda</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[200px] overflow-y-auto pr-1">
              {herd.attention_needed.map(item => (
                <button key={item.animal_id}
                  onClick={() => setSelectedId(item.animal_id)}
                  className={`w-full text-left flex items-center justify-between px-3 py-2.5 rounded-xl border transition-all ${
                    selectedId === item.animal_id
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                  }`}>
                  <div className="flex-1 min-w-0">
                    <p className="font-mono font-semibold text-sm text-gray-900">{item.animal_tag}</p>
                    <p className="text-xs text-gray-400 truncate">
                      {item.anomalies[0] || item.status}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <TrendBadge trend={item.adi_trend} />
                    <span className="text-xs font-bold tabular-nums"
                      style={{ color: STATUS_CFG[item.status as keyof typeof STATUS_CFG]?.color ?? '#6b7280' }}>
                      {item.overall_score.toFixed(0)}
                    </span>
                    <ChevronRight size={14} className="text-gray-400" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Tanlangan jonivor tahlili ─────────────────────────────────────── */}
      {selectedId && (
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
            <div className="flex items-center gap-3">
              <button onClick={() => setSelectedId(null)}
                className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500">
                <ArrowLeft size={16} />
              </button>
              <div>
                <h2 className="text-sm font-bold text-gray-900">
                  {animalLoading ? 'Yuklanmoqda...' : (animalBehavior?.animal_tag ?? `#${selectedId}`)} — Tahlil
                </h2>
                {animalBehavior && (
                  <p className="text-xs text-gray-400">
                    {animalBehavior.detection_count} ta aniqlash · {new Date(animalBehavior.analyzed_at).toLocaleString('uz-UZ')}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {animalBehavior && <TrendBadge trend={animalBehavior.adi_trend} />}
              {animalBehavior && <StatusBadge status={animalBehavior.overall_status} />}
              <button
                onClick={() => navigate(`/animals/${selectedId}`)}
                className="px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50">
                Profil →
              </button>
              <button
                onClick={() => analyzeMutation.mutate(selectedId)}
                disabled={analyzeMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <Zap size={12} />
                {analyzeMutation.isPending ? 'Tahlil...' : 'Qayta tahlil'}
              </button>
            </div>
          </div>

          {animalLoading ? (
            <div className="py-16 text-center">
              <RefreshCw className="w-8 h-8 text-gray-200 animate-spin mx-auto mb-3" />
              <p className="text-sm text-gray-400">Tahlil qilinmoqda...</p>
            </div>
          ) : animalBehavior ? (
            <div className="p-6">
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

                {/* 4 ta komponent karta */}
                <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <ComponentCard type="activity" score={animalBehavior.activity} />
                  <ComponentCard type="feeding"  score={animalBehavior.feeding}  />
                  <ComponentCard type="movement" score={animalBehavior.movement} />
                  <ComponentCard type="social"   score={animalBehavior.social}   />
                </div>

                {/* Radar chart + anomaliyalar */}
                <div className="lg:col-span-2 space-y-4">

                  {/* Radar */}
                  <div className="bg-gray-50 rounded-2xl p-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Profil grafigi</p>
                    <ResponsiveContainer width="100%" height={200}>
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="#e5e7eb" />
                        <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                        <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Anomaliyalar */}
                  {animalBehavior.anomalies.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
                      <p className="text-xs font-semibold text-amber-700 mb-2 flex items-center gap-1.5">
                        <AlertTriangle size={13} /> Aniqlangan muammolar
                      </p>
                      <ul className="space-y-1">
                        {animalBehavior.anomalies.map((a, i) => (
                          <li key={i} className="text-xs text-amber-800 flex items-start gap-1.5">
                            <span className="mt-0.5 shrink-0">•</span>{a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Tavsiyalar */}
                  {animalBehavior.recommendations.length > 0 && (
                    <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
                      <p className="text-xs font-semibold text-blue-700 mb-2 flex items-center gap-1.5">
                        <CheckCircle size={13} /> Tavsiyalar
                      </p>
                      <ul className="space-y-1">
                        {animalBehavior.recommendations.slice(0, 4).map((r, i) => (
                          <li key={i} className="text-xs text-blue-800 flex items-start gap-1.5">
                            <span className="mt-0.5 shrink-0">→</span>{r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* ── Jonivor tanlash (agar tanlangan bo'lmasa) ────────────────────── */}
      {!selectedId && herd && (
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-2xl p-8 text-center">
          <Activity className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium mb-1">Alohida jonivor tahlili</p>
          <p className="text-sm text-gray-400">
            Yuqoridagi "Diqqat talab qiladiganlar" ro'yxatidan yoki quyidan jonivor tanlang
          </p>
          {herd.attention_needed.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-center mt-4">
              {herd.attention_needed.slice(0, 8).map(a => (
                <button key={a.animal_id}
                  onClick={() => setSelectedId(a.animal_id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-sm font-mono font-semibold text-gray-700 hover:border-blue-300 hover:text-blue-600 transition-colors shadow-sm">
                  {a.animal_tag}
                  <StatusBadge status={a.status} />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

    </div>
  );
}