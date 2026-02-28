/**
 * DashboardPage — "Morning Briefing" konsepti
 *
 * Ferma egasi bir qaraganda ko'radigan narsalar:
 *   1. Jonivorlar soni — tur bo'yicha donut diagramma
 *   2. Ferma ADI skori — kategoriya taqsimoti
 *   3. Diqqat talab qiladiganlar ro'yxati
 *   4. Ferma rivojlanishi — vazn trendi, rangli zonalar
 *
 * Dark mode: document.documentElement.classList.toggle('dark')
 * Animatsiyalar: CSS keyframes + counter animation
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Minus,
  AlertTriangle, ChevronRight,
  Moon, Sun, RefreshCw, CheckCircle,
} from 'lucide-react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface OverviewStats {
  animals: { total: number; active: number };
  weight:  { average_kg: number | null; change_percentage_7d: number | null };
}

interface HealthMetrics {
  risk_score:        number;
  animals_by_status: Record<string, number>;
  alert_summary:     { total: number; critical: number; warning: number };
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
  farm_adi_score: number;
  needs_attention: ADIFarmSummaryItem[];
}

interface AnimalSearchResponse {
  total: number;
}

interface WeightTrendRaw {
  data: { date: string; average_weight: number; measurement_count: number }[];
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SPECIES = [
  { key: 'cattle', label: 'Qoramol',  color: '#1E3EB4' },
  { key: 'sheep',  label: "Qo'y",     color: '#10B981' },
  { key: 'goat',   label: 'Echki',    color: '#F59E0B' },
  { key: 'horse',  label: 'Ot',       color: '#8B5CF6' },
  { key: 'other',  label: 'Boshqa',   color: '#6B7280' },
];

const ADI_CFG = {
  healthy:  { color: '#10B981', label: "Sog'lom",       bg: 'rgba(16,185,129,0.1)'  },
  average:  { color: '#F59E0B', label: "O'rtacha",      bg: 'rgba(245,158,11,0.1)'  },
  warning:  { color: '#F97316', label: 'Ogohlantirish', bg: 'rgba(249,115,22,0.1)'  },
  critical: { color: '#EF4444', label: 'Kritik',        bg: 'rgba(239,68,68,0.1)'   },
} as const;

const R    = 52;
const CIRC = 2 * Math.PI * R;
const GAP  = 2;

// =============================================================================
// HOOKS
// =============================================================================

function useCountUp(target: number, duration = 900, trigger = true) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!trigger || target === 0) { setValue(target); return; }
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const ease     = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(ease * target));
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration, trigger]);

  return value;
}

function useDarkMode() {
  const [dark, setDark] = useState(() =>
    typeof window !== 'undefined' &&
    (localStorage.getItem('tv-theme') === 'dark' ||
      (!localStorage.getItem('tv-theme') &&
        window.matchMedia('(prefers-color-scheme: dark)').matches))
  );

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add('dark');
      localStorage.setItem('tv-theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('tv-theme', 'light');
    }
  }, [dark]);

  return [dark, () => setDark(d => !d)] as const;
}

// =============================================================================
// DONUT CHART
// =============================================================================

interface DonutSegment { key: string; label: string; value: number; color: string }

function DonutChart({
  segments, total, selected, onSelect,
}: {
  segments: DonutSegment[];
  total:    number;
  selected: string | null;
  onSelect: (k: string | null) => void;
}) {
  const nonZero = segments.filter(s => s.value > 0);
  if (nonZero.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
        Ma'lumot yo'q
      </div>
    );
  }

  let cumOffset = 0;
  const slices = nonZero.map(seg => {
    const len    = (seg.value / total) * CIRC - GAP;
    const offset = CIRC - cumOffset;
    cumOffset   += (seg.value / total) * CIRC;
    return { ...seg, len: Math.max(0, len), offset };
  });

  const active = selected ? segments.find(s => s.key === selected) : null;

  return (
    <div className="relative flex items-center justify-center" style={{ height: 168 }}>
      <svg
        viewBox="0 0 128 128"
        style={{ width: 168, height: 168, transform: 'rotate(-90deg)' }}
      >
        {/* track */}
        <circle
          cx={64} cy={64} r={R} fill="none"
          stroke="#E5E7EB" strokeWidth={12}
          className="dark:[stroke:#374151]"
        />
        {slices.map(s => (
          <circle
            key={s.key}
            cx={64} cy={64} r={R} fill="none"
            stroke={s.color}
            strokeWidth={selected && selected !== s.key ? 10 : 13}
            strokeLinecap="butt"
            strokeDasharray={`${s.len} ${CIRC}`}
            strokeDashoffset={s.offset}
            opacity={selected && selected !== s.key ? 0.25 : 1}
            style={{ cursor: 'pointer', transition: 'stroke-width .2s, opacity .2s' }}
            onClick={() => onSelect(selected === s.key ? null : s.key)}
          />
        ))}
      </svg>

      {/* center */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div
          className="text-2xl font-black tabular-nums"
          style={{
            color: active ? active.color : undefined,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          <span className={active ? '' : 'text-gray-900 dark:text-gray-100'}>
            {active ? active.value : total}
          </span>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {active ? active.label : 'Jami'}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

function Card({ children, className = '', onClick }: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`
        bg-white dark:bg-gray-900
        border border-gray-200 dark:border-gray-800
        rounded-2xl shadow-sm
        ${onClick ? 'cursor-pointer hover:-translate-y-0.5 transition-transform' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

function CardHeader({ title, action }: {
  title: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-5 pt-5 pb-3">
      <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</div>
      {action}
    </div>
  );
}

function AttentionRow({ item, onClick }: { item: ADIFarmSummaryItem; onClick: () => void }) {
  const cfg = ADI_CFG[item.category as keyof typeof ADI_CFG] ?? ADI_CFG.warning;
  const TrendIcon = item.trend === 'improving' ? TrendingUp :
                    item.trend === 'declining' ? TrendingDown : Minus;

  return (
    <button
      onClick={onClick}
      className="
        w-full flex items-center gap-3 px-5 py-3 text-left group
        hover:bg-gray-50 dark:hover:bg-gray-800/60
        border-t border-gray-100 dark:border-gray-800
        transition-colors
      "
    >
      <div
        className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
        style={{ background: cfg.bg }}
      >
        <span
          className="text-sm font-black tabular-nums"
          style={{ color: cfg.color, fontFamily: "'JetBrains Mono', monospace" }}
        >
          {Math.round(item.adi_score)}
        </span>
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
          {item.tag_id}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className="text-xs font-medium" style={{ color: cfg.color }}>{cfg.label}</span>
          <span className="text-gray-300 dark:text-gray-600">·</span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {item.species === 'cattle' ? 'Qoramol' :
             item.species === 'sheep'  ? "Qo'y"    :
             item.species === 'goat'   ? 'Echki'   :
             item.species === 'horse'  ? 'Ot'      : 'Boshqa'}
          </span>
        </div>
      </div>

      <TrendIcon
        size={13}
        style={{
          color: item.trend === 'improving' ? '#10B981' :
                 item.trend === 'declining' ? '#EF4444' : '#9CA3AF',
          flexShrink: 0,
        }}
      />
      <ChevronRight
        size={13}
        className="text-gray-300 dark:text-gray-600 group-hover:text-gray-500 transition-colors flex-shrink-0"
      />
    </button>
  );
}

function WeightTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2.5 shadow-lg text-xs">
      <p className="font-semibold text-gray-600 dark:text-gray-400 mb-1">{label}</p>
      <p className="font-bold text-gray-900 dark:text-gray-100">
        {payload[0]?.value?.toFixed(1)} kg
      </p>
      <p className="text-gray-400 dark:text-gray-500 mt-0.5">
        {payload[0]?.payload?.measurement_count ?? 0} ta o'lchov
      </p>
    </div>
  );
}

// =============================================================================
// MAIN
// =============================================================================

export default function DashboardPage() {
  const navigate = useNavigate();
  const [isDark, toggleDark]        = useDarkMode();
  const [trendDays, setTrendDays]   = useState(30);
  const [selSpecies, setSelSpecies] = useState<string | null>(null);
  const hasAnimated = useRef(false);
  const [animated, setAnimated]     = useState(false);

  // ─── Queries ────────────────────────────────────────────────────────────────

  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn:  () => apiFetch<OverviewStats>('/api/v1/analytics/overview'),
    staleTime: 60_000,
  });

  const { data: health } = useQuery({
    queryKey: ['analytics', 'health'],
    queryFn:  () => apiFetch<HealthMetrics>('/api/v1/analytics/health/metrics'),
    staleTime: 60_000,
  });

  const { data: adiSummary, refetch: refetchAdi, isFetching: loadingAdi } = useQuery({
    queryKey: ['adi', 'farm-summary'],
    queryFn:  () => apiFetch<ADIFarmSummary>('/api/v1/adi/farm-summary'),
    staleTime: 5 * 60_000,
  });

  const { data: weightRaw, isFetching: loadingChart } = useQuery({
    queryKey: ['analytics', 'weight-trend', trendDays],
    queryFn:  () => apiFetch<WeightTrendRaw>(`/api/v1/analytics/trends/weight?days=${trendDays}`),
    staleTime: 5 * 60_000,
  });

  // Species counts — parallel
  const speciesQ = useQueries({
    queries: SPECIES.map(sp => ({
      queryKey:  ['animals', 'species-count', sp.key],
      queryFn:   () => apiFetch<AnimalSearchResponse>(
        `/api/v1/animals/search?species=${sp.key}&limit=1`
      ),
      staleTime: 5 * 60_000,
    })),
  });

  // ─── Derived ────────────────────────────────────────────────────────────────

  const totalAnimals  = overview?.animals?.total ?? 0;
  const animatedTotal = useCountUp(totalAnimals, 900, !loadingOverview);
  const farmAdi       = adiSummary?.farm_adi_score ?? 0;
  const animatedAdi   = useCountUp(Math.round(farmAdi), 1100, !!adiSummary);

  const speciesData: DonutSegment[] = SPECIES.map((sp, i) => ({
    ...sp, value: speciesQ[i].data?.total ?? 0,
  })).filter(s => s.value > 0);

  const weightTrend = (weightRaw?.data ?? []).map(p => ({
    date:              new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    average_weight:    p.average_weight,
    measurement_count: p.measurement_count,
  }));

  const weights = weightTrend.map(d => d.average_weight).filter(Boolean);
  const avgW    = weights.length ? weights.reduce((a, b) => a + b, 0) / weights.length : 0;

  const adiCats: [string, number][] = adiSummary ? [
    ['healthy',  adiSummary.healthy_count],
    ['average',  adiSummary.average_count],
    ['warning',  adiSummary.warning_count],
    ['critical', adiSummary.critical_count],
  ] : [];

  const adiTotal       = adiCats.reduce((s, [, n]) => s + n, 0);
  const attentionList  = (adiSummary?.needs_attention ?? []).slice(0, 5);

  const farmColor = farmAdi >= 70 ? '#10B981' : farmAdi >= 40 ? '#F59E0B' : '#EF4444';
  const farmLabel = farmAdi >= 70 ? "Yaxshi holat" :
                    farmAdi >= 40 ? "O'rtacha holat" : "Diqqat talab qiladi";

  const weightChange  = overview?.weight?.change_percentage_7d;
  const WeightIcon    = (weightChange ?? 0) > 0 ? TrendingUp :
                        (weightChange ?? 0) < 0 ? TrendingDown : Minus;
  const weightColor   = (weightChange ?? 0) > 0 ? '#10B981' :
                        (weightChange ?? 0) < 0 ? '#EF4444' : '#9CA3AF';

  const today = new Date().toLocaleDateString('uz-UZ', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  // Trigger stagger animation once
  useEffect(() => {
    if (!hasAnimated.current && (overview || adiSummary)) {
      hasAnimated.current = true;
      setTimeout(() => setAnimated(true), 80);
    }
  }, [overview, adiSummary]);

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity:0; transform:translateY(14px); }
          to   { opacity:1; transform:translateY(0);    }
        }
        .du-1 { animation: fadeUp .45s ease both .04s; }
        .du-2 { animation: fadeUp .45s ease both .10s; }
        .du-3 { animation: fadeUp .45s ease both .18s; }
        .du-4 { animation: fadeUp .45s ease both .26s; }
        .du-5 { animation: fadeUp .45s ease both .34s; }
      `}</style>

      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">

          {/* ── HEADER ── */}
          <div className="du-1 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50">
                Ferma holati
              </h1>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 capitalize">
                {today}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetchAdi()}
                disabled={loadingAdi}
                className="
                  flex items-center gap-1.5 px-3 py-2 rounded-xl
                  text-xs font-medium text-gray-500 dark:text-gray-400
                  border border-gray-200 dark:border-gray-800
                  hover:bg-gray-100 dark:hover:bg-gray-800
                  disabled:opacity-50 transition-colors
                "
              >
                <RefreshCw size={13} className={loadingAdi ? 'animate-spin' : ''} />
                Yangilash
              </button>
              <button
                onClick={toggleDark}
                aria-label="Rejimni o'zgartirish"
                className="
                  p-2 rounded-xl text-gray-500 dark:text-gray-400
                  border border-gray-200 dark:border-gray-800
                  hover:bg-gray-100 dark:hover:bg-gray-800
                  transition-colors
                "
              >
                {isDark ? <Sun size={15} /> : <Moon size={15} />}
              </button>
            </div>
          </div>

          {/* ── TOP METRICS ── */}
          <div className="du-2 grid grid-cols-2 lg:grid-cols-4 gap-4">

            {/* Farm ADI */}
            <Card className="p-5">
              <div className="text-xs text-gray-400 dark:text-gray-500 mb-2 font-medium">
                Ferma ADI skori
              </div>
              <div className="flex items-end gap-2">
                <div
                  className="text-5xl font-black tabular-nums leading-none"
                  style={{ color: farmColor, fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {animatedAdi}
                </div>
                <span className="text-base text-gray-400 dark:text-gray-600 mb-1">/100</span>
              </div>
              <div className="mt-3 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{ width: `${farmAdi}%`, background: farmColor }}
                />
              </div>
              <div className="mt-1.5 text-xs font-medium" style={{ color: farmColor }}>
                {farmLabel}
              </div>
            </Card>

            {/* Total animals */}
            <Card className="p-5" onClick={() => navigate('/animals')}>
              <div className="text-xs text-gray-400 dark:text-gray-500 mb-2 font-medium">
                Jami jonivorlar
              </div>
              <div
                className="text-4xl font-black tabular-nums text-gray-900 dark:text-gray-100"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {animatedTotal}
              </div>
              <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                {overview?.animals?.active ?? 0} ta faol
              </div>
            </Card>

            {/* Avg weight */}
            <Card className="p-5">
              <div className="text-xs text-gray-400 dark:text-gray-500 mb-2 font-medium">
                O'rtacha vazn
              </div>
              <div
                className="text-4xl font-black tabular-nums text-gray-900 dark:text-gray-100"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {overview?.weight?.average_kg != null
                  ? overview.weight.average_kg.toFixed(0)
                  : '—'}
                <span className="text-lg font-normal text-gray-400 ml-1">kg</span>
              </div>
              {weightChange != null && (
                <div className="flex items-center gap-1 mt-1">
                  <WeightIcon size={11} style={{ color: weightColor }} />
                  <span className="text-xs font-medium" style={{ color: weightColor }}>
                    {weightChange >= 0 ? '+' : ''}{weightChange.toFixed(1)}% (7 kun)
                  </span>
                </div>
              )}
            </Card>

            {/* Attention count */}
            <Card className="p-5" onClick={() => navigate('/adi')}>
              <div className="text-xs text-gray-400 dark:text-gray-500 mb-2 font-medium">
                Diqqat talab qiladi
              </div>
              <div
                className="text-4xl font-black tabular-nums"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  color: attentionList.length > 0 ? '#F97316' : '#10B981',
                }}
              >
                {attentionList.length}
              </div>
              <div className="flex items-center gap-1 mt-1">
                {attentionList.length === 0 ? (
                  <>
                    <CheckCircle size={11} className="text-emerald-500" />
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      Hammasi yaxshi
                    </span>
                  </>
                ) : (
                  <>
                    <AlertTriangle size={11} className="text-orange-500" />
                    <span className="text-xs text-orange-600 dark:text-orange-400 font-medium">
                      {health?.alert_summary?.critical ?? 0} ta kritik
                    </span>
                  </>
                )}
              </div>
            </Card>
          </div>

          {/* ── 3 COLUMNS ── */}
          <div className="du-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">

            {/* Donut — species */}
            <Card>
              <CardHeader title="Jonivorlar turlari" />
              <div className="px-5 pb-2">
                <DonutChart
                  segments={speciesData}
                  total={totalAnimals}
                  selected={selSpecies}
                  onSelect={setSelSpecies}
                />
              </div>
              <div className="px-5 pb-5 grid grid-cols-2 gap-y-2.5 gap-x-3">
                {speciesData.map(sp => (
                  <button
                    key={sp.key}
                    onClick={() => setSelSpecies(p => p === sp.key ? null : sp.key)}
                    className="flex items-center gap-2 text-left hover:opacity-80 transition-opacity"
                  >
                    <div
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: sp.color }}
                    />
                    <div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{sp.label}</div>
                      <div
                        className="text-xs font-bold tabular-nums"
                        style={{
                          color: selSpecies === sp.key ? sp.color : undefined,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        <span className={selSpecies === sp.key ? '' : 'text-gray-800 dark:text-gray-200'}>
                          {sp.value}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </Card>

            {/* ADI distribution */}
            <Card>
              <CardHeader
                title="ADI holati taqsimoti"
                action={
                  <button
                    onClick={() => navigate('/adi')}
                    className="text-xs text-blue-500 hover:text-blue-600 font-medium"
                  >
                    Batafsil →
                  </button>
                }
              />
              <div className="px-5 pb-5">
                {adiTotal === 0 ? (
                  <div className="h-36 flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
                    ADI ma'lumot yo'q
                  </div>
                ) : (
                  <div className="space-y-1">
                    {/* Stacked bar */}
                    <div className="flex h-2 rounded-full overflow-hidden gap-px mb-5">
                      {adiCats.map(([cat, count]) => {
                        const cfg = ADI_CFG[cat as keyof typeof ADI_CFG];
                        const pct = adiTotal > 0 ? (count / adiTotal) * 100 : 0;
                        return pct > 0 ? (
                          <div
                            key={cat}
                            className="h-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: cfg.color }}
                            title={`${cfg.label}: ${count}`}
                          />
                        ) : null;
                      })}
                    </div>

                    {adiCats.map(([cat, count]) => {
                      const cfg = ADI_CFG[cat as keyof typeof ADI_CFG];
                      const pct = adiTotal > 0 ? (count / adiTotal) * 100 : 0;
                      return (
                        <div key={cat} className="py-1.5">
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full" style={{ background: cfg.color }} />
                              <span className="text-xs text-gray-600 dark:text-gray-400">{cfg.label}</span>
                            </div>
                            <span
                              className="text-xs font-bold tabular-nums"
                              style={{
                                fontFamily: "'JetBrains Mono', monospace",
                                color: count > 0 ? cfg.color : '#9CA3AF',
                              }}
                            >
                              {count}
                            </span>
                          </div>
                          <div className="h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{ width: `${pct}%`, background: cfg.color }}
                            />
                          </div>
                        </div>
                      );
                    })}

                    <div className="pt-3 mt-2 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
                      <span className="text-xs text-gray-400 dark:text-gray-500">Bugungi o'rtacha</span>
                      <span
                        className="text-sm font-black tabular-nums"
                        style={{ color: farmColor, fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {farmAdi.toFixed(1)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Attention list */}
            <Card className="overflow-hidden">
              <CardHeader
                title="Diqqat talab qiladiganlar"
                action={attentionList.length > 0 && (
                  <button
                    onClick={() => navigate('/adi')}
                    className="text-xs text-orange-500 hover:text-orange-600 font-medium"
                  >
                    Hammasi →
                  </button>
                )}
              />
              {attentionList.length === 0 ? (
                <div className="px-5 pb-5 h-48 flex flex-col items-center justify-center gap-2">
                  <CheckCircle size={36} className="text-emerald-400 opacity-40" />
                  <p className="text-sm text-gray-400 dark:text-gray-500 text-center leading-relaxed">
                    Barcha jonivorlar<br />yaxshi holatda
                  </p>
                </div>
              ) : (
                attentionList.map(item => (
                  <AttentionRow
                    key={item.animal_id}
                    item={item}
                    onClick={() => navigate(`/animals/${item.animal_id}`)}
                  />
                ))
              )}
            </Card>
          </div>

          {/* ── FARM DEVELOPMENT CHART ── */}
          <Card className="du-4">
            <CardHeader
              title={
                <div className="flex items-center gap-2">
                  <TrendingUp size={14} className="text-blue-500" />
                  <span>Ferma rivojlanishi — o'rtacha vazn trendi</span>
                </div>
              }
              action={
                <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
                  {([7, 30, 90] as const).map(d => (
                    <button
                      key={d}
                      onClick={() => setTrendDays(d)}
                      className={`
                        px-3 py-1 text-xs font-medium rounded-md transition-all
                        ${trendDays === d
                          ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400 font-semibold'
                          : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}
                      `}
                    >
                      {d}k
                    </button>
                  ))}
                </div>
              }
            />
            <div className="px-5 pb-5">
              {/* Zone legend */}
              <div className="flex items-center gap-4 mb-4">
                {[
                  { color: '#10B981', label: 'O\'rtachadan yuqori' },
                  { color: '#F59E0B', label: 'O\'rtacha' },
                  { color: '#EF4444', label: 'O\'rtachadan past' },
                ].map(z => (
                  <div key={z.label} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-sm opacity-60" style={{ background: z.color }} />
                    <span className="text-xs text-gray-400 dark:text-gray-500">{z.label}</span>
                  </div>
                ))}
              </div>

              {loadingChart ? (
                <div className="h-52 flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
                  Yuklanmoqda...
                </div>
              ) : weightTrend.length < 2 ? (
                <div className="h-52 flex flex-col items-center justify-center gap-2 text-gray-400 dark:text-gray-500">
                  <TrendingUp size={32} className="opacity-25" />
                  <p className="text-sm">Trendni ko'rish uchun ko'proq o'lchov kerak</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={weightTrend} margin={{ top: 8, right: 4, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#1E3EB4" stopOpacity={0.14} />
                        <stop offset="95%" stopColor="#1E3EB4" stopOpacity={0.01} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3" vertical={false}
                      stroke="currentColor"
                      className="text-gray-100 dark:text-gray-800"
                    />
                    {avgW > 0 && <>
                      <ReferenceArea y1={avgW * 1.05} fill="#10B981" fillOpacity={0.07} stroke="none" />
                      <ReferenceArea y1={avgW * 0.92} y2={avgW * 1.05} fill="#F59E0B" fillOpacity={0.07} stroke="none" />
                      <ReferenceArea y1={0} y2={avgW * 0.92} fill="#EF4444" fillOpacity={0.07} stroke="none" />
                    </>}
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: '#9CA3AF' }}
                      tickLine={false} axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: '#9CA3AF' }}
                      tickLine={false} axisLine={false}
                      unit=" kg" width={58}
                    />
                    <Tooltip content={<WeightTooltip />} cursor={{ stroke: '#E5E7EB', strokeWidth: 1 }} />
                    <Area
                      type="monotone"
                      dataKey="average_weight"
                      stroke="#1E3EB4"
                      strokeWidth={2}
                      fill="url(#wGrad)"
                      dot={false}
                      activeDot={{ r: 4, fill: '#1E3EB4', strokeWidth: 0 }}
                      animationDuration={800}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </Card>

          {/* ── ALERTS BANNER ── */}
          {health && health.alert_summary.total > 0 && (
            <Card className="du-5">
              <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle size={16} className="text-red-500" />
                  </div>
                  <div>
                    <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                      {health.alert_summary.total} ta ochiq alert
                    </span>
                    <div className="flex items-center gap-3 mt-0.5">
                      {health.alert_summary.critical > 0 && (
                        <span className="text-xs text-red-500 font-medium">
                          {health.alert_summary.critical} ta kritik
                        </span>
                      )}
                      {health.alert_summary.warning > 0 && (
                        <span className="text-xs text-amber-500 font-medium">
                          {health.alert_summary.warning} ta ogohlantirish
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/alerts')}
                  className="
                    flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-xl
                    text-xs font-semibold text-white bg-red-500 hover:bg-red-600
                    transition-colors
                  "
                >
                  Ko'rish <ChevronRight size={12} />
                </button>
              </div>
            </Card>
          )}

        </div>
      </div>
    </>
  );
}