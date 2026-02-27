/**
 * ADIMonitoringPage — Jonivorlar Rivojlanish Indeksi Monitoringi
 *
 * ADI (Animal Development Index) — 8 komponentdan iborat umumiy sog'liq indeksi:
 *   activity (20%), feeding (20%), growth (20%), movement (15%),
 *   social (10%), drinking (10%), sensor (5%), veterinary (5%)
 *
 * IMKONIYATLAR:
 *   - Ferma umumiy ADI holati (FarmSummary)
 *   - Kategoriya taqsimoti: healthy / average / warning / critical
 *   - Diqqat talab qiladiganlar ro'yxati (needs_attention)
 *   - Jonivor tanlash → 30 kunlik ADI trend grafigi + 8 komponent
 *   - Qo'lda ADI hisoblash trigger
 *
 * BACKEND: /api/v1/adi/farm-summary, /api/v1/adi/animal/{id}/trend, /api/v1/adi/calculate
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  CheckCircle, RefreshCw, Zap, ChevronRight,
  ArrowLeft, BarChart3, Activity,
} from 'lucide-react';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar,
  PolarGrid, PolarAngleAxis,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface ADIComponentScores {
  activity_score?:   number | null;
  feeding_score?:    number | null;
  drinking_score?:   number | null;
  movement_score?:   number | null;
  growth_score?:     number | null;
  social_score?:     number | null;
  sensor_score?:     number | null;
  veterinary_score?: number | null;
}

interface ADILogResponse {
  id:               number;
  animal_id:        number;
  calculation_date: string;
  adi_score:        number;
  category:         string;
  scores:           ADIComponentScores;
  data_quality:     number;
  notes:            string | null;
}

interface ADITrendPoint {
  date:     string;
  score:    number;
  category: string;
}

interface ADITrendResponse {
  animal_id:   number;
  animal_tag:  string;
  period_days: number;
  trend:       ADITrendPoint[];
  avg_score:   number;
  min_score:   number;
  max_score:   number;
  current:     ADILogResponse | null;
}

interface ADIFarmSummaryItem {
  animal_id:    number;
  tag_id:       string;
  species:      string;
  adi_score:    number;
  category:     string;
  trend:        string;
  last_updated: string | null;
}

interface ADIFarmSummary {
  date:           string;
  total_animals:  number;
  healthy_count:  number;
  average_count:  number;
  warning_count:  number;
  critical_count: number;
  healthy_pct:    number;
  average_pct:    number;
  warning_pct:    number;
  critical_pct:   number;
  farm_adi_score: number;
  needs_attention: ADIFarmSummaryItem[];
}

// =============================================================================
// CONSTANTS
// =============================================================================

const CATEGORY_CFG = {
  excellent: { color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0', label: 'Mukammal',  min: 90 },
  healthy:   { color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0', label: 'Sog\'lom',   min: 75 },
  good:      { color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe', label: 'Yaxshi',    min: 60 },
  average:   { color: '#f59e0b', bg: '#fffbeb', border: '#fde68a', label: "O'rtacha",  min: 45 },
  warning:   { color: '#f97316', bg: '#fff7ed', border: '#fed7aa', label: 'Ogohlantirish', min: 30 },
  critical:  { color: '#ef4444', bg: '#fef2f2', border: '#fecaca', label: 'Kritik',    min: 0  },
} as const;

const COMPONENTS = [
  { key: 'activity_score',   label: 'Faollik',        weight: 20, color: '#6366f1' },
  { key: 'feeding_score',    label: 'Ovqatlanish',     weight: 20, color: '#10b981' },
  { key: 'growth_score',     label: "O'sish",          weight: 20, color: '#3b82f6' },
  { key: 'movement_score',   label: 'Harakat sifati',  weight: 15, color: '#8b5cf6' },
  { key: 'social_score',     label: 'Ijtimoiy',        weight: 10, color: '#f59e0b' },
  { key: 'drinking_score',   label: 'Suv ichish',      weight: 10, color: '#06b6d4' },
  { key: 'sensor_score',     label: 'Sensor',          weight: 5,  color: '#ec4899' },
  { key: 'veterinary_score', label: 'Veterinar',       weight: 5,  color: '#14b8a6' },
] as const;

const TREND_DAYS_OPTIONS = [7, 14, 30, 90];

// =============================================================================
// HELPERS
// =============================================================================

function getCategoryConfig(category: string) {
  return CATEGORY_CFG[category as keyof typeof CATEGORY_CFG] ?? CATEGORY_CFG.average;
}

function getScoreColor(score: number) {
  if (score >= 75) return '#10b981';
  if (score >= 60) return '#3b82f6';
  if (score >= 45) return '#f59e0b';
  if (score >= 30) return '#f97316';
  return '#ef4444';
}

function CategoryBadge({ category }: { category: string }) {
  const cfg = getCategoryConfig(category);
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
      {cfg.label}
    </span>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'up')   return <TrendingUp size={14} className="text-emerald-500" />;
  if (trend === 'down') return <TrendingDown size={14} className="text-red-500" />;
  return <Minus size={14} className="text-gray-400" />;
}

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const color = getScoreColor(score);
  const r = size * 0.4;
  const circ = 2 * Math.PI * r;
  const dash = circ * score / 100;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f3f4f6" strokeWidth={size*0.1} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color}
        strokeWidth={size*0.1} strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
    </svg>
  );
}

// =============================================================================
// SUMMARY STAT CARD
// =============================================================================

function StatCard({ label, count, pct, color, bg }: {
  label: string; count: number; pct: number; color: string; bg: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-gray-500">{label}</p>
        <span className="text-xs font-bold px-2 py-0.5 rounded-full"
          style={{ background: bg, color }}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <p className="text-3xl font-bold" style={{ color }}>{count}</p>
      <div className="w-full h-1.5 bg-gray-100 rounded-full mt-3 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// =============================================================================
// COMPONENT BAR
// =============================================================================

function ComponentBar({ label, score, weight, color }: {
  label: string; score: number | null | undefined; weight: number; color: string;
}) {
  const val = score ?? 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: color }} />
          <span className="text-xs text-gray-600 font-medium">{label}</span>
          <span className="text-xs text-gray-400">({weight}%)</span>
        </div>
        <span className="text-xs font-bold tabular-nums" style={{ color: getScoreColor(val) }}>
          {score != null ? `${val.toFixed(0)}` : '—'}
        </span>
      </div>
      <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: score != null ? `${val}%` : '0%', background: color }} />
      </div>
    </div>
  );
}

// =============================================================================
// CUSTOM TOOLTIP
// =============================================================================

function AdiTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const score = payload[0]?.value;
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg px-3 py-2">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-sm font-bold" style={{ color: getScoreColor(score) }}>
        ADI: {score?.toFixed(1)}
      </p>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ADIMonitoringPage() {
  const navigate   = useNavigate();
  const qClient    = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [trendDays, setTrendDays]   = useState(30);

  // ── Farm summary ──────────────────────────────────────────────────────────
  const {
    data: farm,
    isFetching: farmLoading,
    refetch: refetchFarm,
  } = useQuery({
    queryKey: ['adi', 'farm-summary'],
    queryFn:  () => apiFetch<ADIFarmSummary>('/api/v1/adi/farm-summary'),
  });

  // ── Selected animal trend ─────────────────────────────────────────────────
  const { data: trendData, isFetching: trendLoading } = useQuery({
    queryKey: ['adi', 'trend', selectedId, trendDays],
    queryFn:  () => apiFetch<ADITrendResponse>(`/api/v1/adi/animal/${selectedId}/trend?days=${trendDays}`),
    enabled:  !!selectedId,
  });

  // ── Manual calculate mutation ─────────────────────────────────────────────
  const calcMutation = useMutation({
    mutationFn: (animalId: number | null) =>
      apiFetch('/api/v1/adi/calculate', {
        method: 'POST',
        body: JSON.stringify({ animal_id: animalId, recalculate: true }),
      }),
    onSuccess: () => {
      qClient.invalidateQueries({ queryKey: ['adi'] });
    },
  });

  // ── Derived ───────────────────────────────────────────────────────────────
  const chartData = (trendData?.trend ?? []).map(p => ({
    date:     format(parseISO(p.date), 'dd/MM'),
    score:    p.score,
    category: p.category,
  }));

  const radarData = trendData?.current ? COMPONENTS.map(c => ({
    subject: c.label,
    value:   trendData.current!.scores[c.key as keyof ADIComponentScores] ?? 0,
    fullMark: 100,
  })) : [];

  const current = trendData?.current ?? null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">ADI Monitoring</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Jonivorlar Rivojlanish Indeksi ·{' '}
            {farm ? `${farm.total_animals} ta jonivor · ${farm.date}` : 'Yuklanmoqda...'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => calcMutation.mutate(null)}
            disabled={calcMutation.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 shadow-sm">
            <Zap className="w-4 h-4" />
            {calcMutation.isPending ? 'Hisoblanmoqda...' : 'Barchasini hisoblash'}
          </button>
          <button onClick={() => refetchFarm()} disabled={farmLoading}
            className="p-2.5 border border-gray-200 rounded-xl text-gray-500 hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${farmLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Farm ADI Score (Hero) ────────────────────────────────────────── */}
      <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-6 mb-6 text-white shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-blue-200 text-sm font-medium mb-1">Ferma umumiy ADI bali</p>
            <p className="text-6xl font-bold mb-2">
              {farm ? farm.farm_adi_score.toFixed(1) : '—'}
            </p>
            <p className="text-blue-200 text-sm">
              {farm
                ? `${farm.total_animals} ta jonivordan ${farm.healthy_count + farm.average_count} tasi me'yorda`
                : 'Yuklanmoqda...'}
            </p>
          </div>
          {farm && (
            <div className="relative">
              <ScoreRing score={farm.farm_adi_score} size={120} />
              <div className="absolute inset-0 flex items-center justify-center">
                <BarChart3 className="w-8 h-8 text-white/50" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Kategoriya kartalar ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Sog'lom"         count={farm?.healthy_count  ?? 0} pct={farm?.healthy_pct  ?? 0} color="#10b981" bg="#ecfdf5" />
        <StatCard label="O'rtacha"         count={farm?.average_count  ?? 0} pct={farm?.average_pct  ?? 0} color="#f59e0b" bg="#fffbeb" />
        <StatCard label="Ogohlantirish"   count={farm?.warning_count  ?? 0} pct={farm?.warning_pct  ?? 0} color="#f97316" bg="#fff7ed" />
        <StatCard label="Kritik"           count={farm?.critical_count ?? 0} pct={farm?.critical_pct ?? 0} color="#ef4444" bg="#fef2f2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

        {/* ── Diqqat talab qiladiganlar ────────────────────────────────── */}
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
              <AlertTriangle size={15} className="text-amber-500" />
              Diqqat talab qiladiganlar
            </h2>
            <span className="text-xs bg-red-50 text-red-600 font-semibold px-2 py-0.5 rounded-full">
              {farm?.needs_attention.length ?? 0} ta
            </span>
          </div>
          <div className="divide-y divide-gray-50 max-h-[360px] overflow-y-auto">
            {!farm ? (
              <div className="py-10 text-center text-gray-300 text-sm">Yuklanmoqda...</div>
            ) : farm.needs_attention.length === 0 ? (
              <div className="py-10 text-center">
                <CheckCircle className="w-10 h-10 text-emerald-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">Barcha jonivorlar yaxshi holatda</p>
              </div>
            ) : (
              farm.needs_attention.map(item => (
                <button key={item.animal_id}
                  onClick={() => setSelectedId(item.animal_id)}
                  className={`w-full text-left flex items-center gap-3 px-5 py-3 transition-colors ${
                    selectedId === item.animal_id
                      ? 'bg-blue-50'
                      : 'hover:bg-gray-50'
                  }`}>
                  {/* Score ring mini */}
                  <div className="relative shrink-0">
                    <ScoreRing score={item.adi_score} size={40} />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold tabular-nums"
                        style={{ color: getScoreColor(item.adi_score) }}>
                        {item.adi_score.toFixed(0)}
                      </span>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-mono font-bold text-sm text-gray-900">{item.tag_id}</p>
                    <p className="text-xs text-gray-400 capitalize">{item.species}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <CategoryBadge category={item.category} />
                    <TrendIcon trend={item.trend} />
                    <ChevronRight size={14} className="text-gray-300" />
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* ── Tanlangan jonivor: Trend ─────────────────────────────────── */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

          {/* Tab header */}
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            {selectedId && trendData ? (
              <>
                <div className="flex items-center gap-3">
                  <button onClick={() => setSelectedId(null)}
                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
                    <ArrowLeft size={15} />
                  </button>
                  <div>
                    <h2 className="text-sm font-bold text-gray-900">{trendData.animal_tag}</h2>
                    <p className="text-xs text-gray-400">
                      Avg: {trendData.avg_score.toFixed(1)} ·
                      Min: {trendData.min_score.toFixed(1)} ·
                      Max: {trendData.max_score.toFixed(1)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {current && <CategoryBadge category={current.category} />}
                  {/* Trend days toggle */}
                  <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
                    {TREND_DAYS_OPTIONS.map(d => (
                      <button key={d} onClick={() => setTrendDays(d)}
                        className={`px-2.5 py-1 font-semibold transition-colors ${
                          trendDays === d ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-50'
                        }`}>
                        {d}k
                      </button>
                    ))}
                  </div>
                  <button onClick={() => navigate(`/animals/${selectedId}`)}
                    className="px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50">
                    Profil →
                  </button>
                  <button onClick={() => calcMutation.mutate(selectedId)}
                    disabled={calcMutation.isPending}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                    <Zap size={11} /> Hisoblash
                  </button>
                </div>
              </>
            ) : (
              <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <Activity size={15} className="text-blue-500" />
                ADI Trend grafigi
              </h2>
            )}
          </div>

          {!selectedId ? (
            <div className="flex flex-col items-center justify-center h-64 text-center px-8">
              <BarChart3 className="w-12 h-12 text-gray-200 mb-3" />
              <p className="text-gray-500 font-medium mb-1">Jonivor tanlanmagan</p>
              <p className="text-sm text-gray-400">
                Chap tomondagi ro'yxatdan jonivor tanlang
              </p>
            </div>
          ) : trendLoading ? (
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-7 h-7 text-gray-200 animate-spin" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center px-8">
              <AlertTriangle className="w-10 h-10 text-amber-300 mb-3" />
              <p className="text-gray-500 font-medium mb-1">ADI ma'lumoti yo'q</p>
              <p className="text-sm text-gray-400 mb-4">
                Bu jonivor uchun hali ADI hisoblanmagan
              </p>
              <button onClick={() => calcMutation.mutate(selectedId)}
                disabled={calcMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-50">
                <Zap size={14} />
                {calcMutation.isPending ? 'Hisoblanmoqda...' : 'Hozir hisoblash'}
              </button>
            </div>
          ) : (
            <div className="p-5">
              {/* Area chart */}
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="adiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip content={<AdiTooltip />} />
                  {/* Reference lines */}
                  <Area dataKey="score" stroke="#6366f1" strokeWidth={2}
                    fill="url(#adiGrad)" dot={false}
                    activeDot={{ r: 4, fill: '#6366f1' }} />
                </AreaChart>
              </ResponsiveContainer>

              {/* 8 komponent + radar */}
              {current && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-100">
                  {/* Component bars */}
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">8 Komponent</p>
                      <span className="text-xs text-gray-400">
                        Sifat: {(current.data_quality * 100).toFixed(0)}%
                      </span>
                    </div>
                    {COMPONENTS.map(c => (
                      <ComponentBar
                        key={c.key}
                        label={c.label}
                        score={current.scores[c.key as keyof ADIComponentScores]}
                        weight={c.weight}
                        color={c.color}
                      />
                    ))}
                  </div>

                  {/* Radar */}
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Profil</p>
                    <ResponsiveContainer width="100%" height={200}>
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="#e5e7eb" />
                        <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                        <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                      </RadarChart>
                    </ResponsiveContainer>

                    {/* Notes */}
                    {current.notes && (
                      <div className="mt-2 p-3 bg-blue-50 rounded-xl">
                        <p className="text-xs text-blue-700">{current.notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

    </div>
  );
}