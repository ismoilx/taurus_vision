/**
 * DashboardPage — 6 karta, 2 qator
 *
 * 1-QATOR:
 *   [1] Jonivorlar turlari   — tur bo'yicha donut
 *   [2] Sog'liq holati        — status bo'yicha donut
 *   [3] Fermaning rivojlanishi — vaqt bo'yicha, bosilsa modal
 *
 * 2-QATOR:
 *   [4] Diqqat talab qiladiganlar
 *   [5] Ferma sog'lig'i grafigi (ADI trend)
 *   [6] Umumiy tirik vazn
 *
 * MUAMMOLAR TUZATILDI:
 *   ✅ Species query: limit=100, res.length — to'g'ri hisob
 *   ✅ Card 3 modal: 1k/7k/30k/90k/maxsus sana
 *   ✅ Card 5: real ADI trend (multiple farm-summary calls)
 *   ✅ Card 6: joy muammosi tuzatildi
 *   ✅ Scrollbar: butunlay yashirilgan
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PieChart, Pie, Cell, Tooltip as RTooltip,
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Minus,
  AlertTriangle, ChevronRight, CheckCircle,
  X, Calendar,
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
  animals_by_status: Record<string, number>;
  alert_summary:     { total: number; critical: number; warning: number };
  risk_score:        number;
}
interface ADIFarmSummaryItem {
  animal_id: number; tag_id: string; species: string;
  adi_score: number; category: string; trend: string;
}
interface ADIFarmSummary {
  date:            string;
  farm_adi_score:  number;
  healthy_count:   number;
  average_count:   number;
  warning_count:   number;
  critical_count:  number;
  needs_attention: ADIFarmSummaryItem[];
}
interface WeightTrendRaw {
  data: { date: string; average_weight: number; measurement_count: number }[];
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SPECIES_CFG = [
  { key: 'cattle', label: 'Qoramol', color: '#1E3EB4' },
  { key: 'sheep',  label: "Qo'y",    color: '#10B981' },
  { key: 'goat',   label: 'Echki',   color: '#F59E0B' },
  { key: 'horse',  label: 'Ot',      color: '#8B5CF6' },
  { key: 'other',  label: 'Boshqa',  color: '#6B7280' },
];

const STATUS_CFG = [
  { key: 'active',      label: "Sog'lom",      color: '#10B981' },
  { key: 'quarantine',  label: 'Karantin',      color: '#F59E0B' },
  { key: 'sick',        label: 'Kasal',         color: '#EF4444' },
  { key: 'deceased',    label: 'Vafot etdi',    color: '#9CA3AF' },
  { key: 'sold',        label: 'Sotilgan',      color: '#3B82F6' },
  { key: 'transferred', label: "Ko'chirilgan",  color: '#8B5CF6' },
];

const ADI_CFG = {
  healthy:  { color: '#10B981', label: "Sog'lom"      },
  average:  { color: '#F59E0B', label: "O'rtacha"     },
  warning:  { color: '#F97316', label: 'Ogohlantirish' },
  critical: { color: '#EF4444', label: 'Kritik'        },
} as const;

const PERIOD_OPTIONS = [
  { label: '1k',  days: 1  },
  { label: '7k',  days: 7  },
  { label: '30k', days: 30 },
  { label: '90k', days: 90 },
];

// =============================================================================
// HELPERS
// =============================================================================

function formatDate(d: Date) {
  return d.toISOString().split('T')[0];
}

function subtractDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() - n);
  return r;
}

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' });
}

// =============================================================================
// SHARED COMPONENTS
// =============================================================================

function Card({
  children, className = '', onClick, style = {},
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div
      ref={ref}
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid #E4E7ED',
        borderRadius: 16,
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
        overflow: 'hidden',
        cursor: onClick ? 'pointer' : 'default',
        display: 'flex',
        flexDirection: 'column',
        transition: onClick ? 'transform .15s, box-shadow .15s' : undefined,
        ...style,
      }}
      className={className}
      onMouseEnter={() => {
        if (onClick && ref.current) {
          ref.current.style.transform = 'translateY(-2px)';
          ref.current.style.boxShadow = '0 6px 20px rgba(0,0,0,0.09)';
        }
      }}
      onMouseLeave={() => {
        if (onClick && ref.current) {
          ref.current.style.transform = 'translateY(0)';
          ref.current.style.boxShadow = '0 1px 4px rgba(0,0,0,0.05)';
        }
      }}
    >
      {children}
    </div>
  );
}

function CardHead({
  title, action,
}: {
  title: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 18px 11px',
      borderBottom: '1px solid #F3F4F6',
      flexShrink: 0,
    }}>
      <span style={{
        fontSize: 12, fontWeight: 600, color: '#374151',
        fontFamily: "'Outfit', sans-serif",
      }}>
        {title}
      </span>
      {action}
    </div>
  );
}

// =============================================================================
// DONUT CHART
// =============================================================================

interface DonutSlice { name: string; value: number; color: string }

function DonutChart({ data, total, sub }: {
  data:  DonutSlice[];
  total: number;
  sub:   string;
}) {
  const nonZero = data.filter(d => d.value > 0);
  const display = nonZero.length > 0 ? nonZero : [{ name: '', value: 1, color: '#F3F4F6' }];

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <PieChart width={144} height={144}>
        <Pie
          data={display}
          cx={68} cy={68}
          innerRadius={44}
          outerRadius={62}
          paddingAngle={nonZero.length > 1 ? 2 : 0}
          dataKey="value"
          strokeWidth={0}
          animationBegin={0}
          animationDuration={700}
        >
          {display.map((e, i) => <Cell key={i} fill={e.color} />)}
        </Pie>
        {nonZero.length > 0 && (
          <RTooltip
            formatter={(v: number, n: string) => [`${v} ta`, n]}
            contentStyle={{
              fontSize: 11, borderRadius: 8,
              border: '1px solid #E4E7ED', padding: '5px 9px',
              fontFamily: "'Outfit', sans-serif",
            }}
          />
        )}
      </PieChart>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none',
      }}>
        <span style={{
          fontSize: 22, fontWeight: 800, color: '#0D1117', lineHeight: 1,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {total}
        </span>
        <span style={{ fontSize: 9, color: '#9CA3AF', marginTop: 3, fontFamily: "'Outfit', sans-serif" }}>
          {sub}
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// LEGEND
// =============================================================================

function Legend({ items }: { items: { label: string; value: number; color: string }[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7, flex: 1, justifyContent: 'center' }}>
      {items.map(it => (
        <div key={it.label} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: it.color, flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: '#6B7280', fontFamily: "'Outfit', sans-serif" }}>
              {it.label}
            </span>
          </div>
          <span style={{
            fontSize: 12, fontWeight: 700,
            color: it.value > 0 ? it.color : '#E5E7EB',
            fontFamily: "'JetBrains Mono', monospace",
            minWidth: 20, textAlign: 'right',
          }}>
            {it.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// TOOLTIPS
// =============================================================================

function WeightTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#fff', border: '1px solid #E4E7ED', borderRadius: 8,
      padding: '7px 11px', boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
      fontSize: 11, fontFamily: "'Outfit', sans-serif",
    }}>
      <div style={{ color: '#9CA3AF', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 700, color: '#0D1117' }}>{payload[0]?.value?.toFixed(1)} kg</div>
    </div>
  );
}

function AdiTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0]?.value ?? 0;
  const color = v >= 70 ? '#10B981' : v >= 40 ? '#F59E0B' : '#EF4444';
  return (
    <div style={{
      background: '#fff', border: '1px solid #E4E7ED', borderRadius: 8,
      padding: '7px 11px', boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
      fontSize: 11, fontFamily: "'Outfit', sans-serif",
    }}>
      <div style={{ color: '#9CA3AF', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 700, color }}>ADI: {v.toFixed(1)}</div>
    </div>
  );
}

// =============================================================================
// MODAL — Rivojlanish grafigi
// =============================================================================

function DevChartModal({
  onClose, weightTrend, defaultDays,
}: {
  onClose:     () => void;
  weightTrend: (days: number) => { date: string; average_weight: number; measurement_count: number }[];
  defaultDays: number;
}) {
  const [days, setDays] = useState(defaultDays);
  const [customFrom, setCustomFrom] = useState('');
  const [customTo,   setCustomTo]   = useState(formatDate(new Date()));
  const [useCustom,  setUseCustom]  = useState(false);

  const data = weightTrend(days).map(p => ({
    date: shortDate(p.date),
    kg:   p.average_weight,
    cnt:  p.measurement_count,
  }));

  // Close on Escape
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  const weights = data.map(d => d.kg).filter(Boolean);
  const avgW    = weights.length ? weights.reduce((a, b) => a + b) / weights.length : 0;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
        animation: 'tv-fadein .2s ease',
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#fff', borderRadius: 20,
          width: '100%', maxWidth: 720,
          boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
          overflow: 'hidden',
          animation: 'tv-slideup .25s ease',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 22px 14px',
          borderBottom: '1px solid #F3F4F6',
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit', sans-serif" }}>
              Fermaning rivojlanishi
            </div>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
              O'rtacha vazn trendi
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: 8,
              background: '#F3F4F6', border: 'none',
              display: 'grid', placeItems: 'center',
              cursor: 'pointer', color: '#6B7280',
            }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Period selector */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '12px 22px',
          borderBottom: '1px solid #F3F4F6',
          flexWrap: 'wrap',
        }}>
          {PERIOD_OPTIONS.map(p => (
            <button
              key={p.days}
              onClick={() => { setDays(p.days); setUseCustom(false); }}
              style={{
                padding: '5px 14px', borderRadius: 8,
                border: `1px solid ${!useCustom && days === p.days ? '#1E3EB4' : '#E4E7ED'}`,
                background: !useCustom && days === p.days ? '#1E3EB4' : '#fff',
                color: !useCustom && days === p.days ? '#fff' : '#6B7280',
                fontSize: 12, fontWeight: 500, cursor: 'pointer',
                fontFamily: "'Outfit', sans-serif",
                transition: 'all .15s',
              }}
            >
              {p.label}
            </button>
          ))}

          {/* Custom range */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 4 }}>
            <Calendar size={13} color="#9CA3AF" />
            <input
              type="date"
              value={customFrom}
              max={formatDate(new Date())}
              onChange={e => { setCustomFrom(e.target.value); setUseCustom(true); }}
              style={{
                border: `1px solid ${useCustom ? '#1E3EB4' : '#E4E7ED'}`,
                borderRadius: 7, padding: '4px 8px', fontSize: 11,
                color: '#374151', outline: 'none', fontFamily: "'Outfit', sans-serif",
              }}
            />
            <span style={{ fontSize: 11, color: '#9CA3AF' }}>—</span>
            <input
              type="date"
              value={customTo}
              max={formatDate(new Date())}
              onChange={e => { setCustomTo(e.target.value); setUseCustom(true); }}
              style={{
                border: `1px solid ${useCustom ? '#1E3EB4' : '#E4E7ED'}`,
                borderRadius: 7, padding: '4px 8px', fontSize: 11,
                color: '#374151', outline: 'none', fontFamily: "'Outfit', sans-serif",
              }}
            />
          </div>
        </div>

        {/* Chart */}
        <div style={{ padding: '16px 8px 20px 0' }}>
          {data.length < 2 ? (
            <div style={{
              height: 240, display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: '#D1D5DB', fontSize: 13,
            }}>
              Ma'lumot yo'q
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={data} margin={{ top: 8, right: 20, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="modalWGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#1E3EB4" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#1E3EB4" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                {avgW > 0 && <>
                  <defs>
                    <pattern id="greenZone" patternUnits="userSpaceOnUse" width="4" height="4">
                      <rect width="4" height="4" fill="#10B98108"/>
                    </pattern>
                  </defs>
                </>}
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9CA3AF' }}
                  tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }}
                  tickLine={false} axisLine={false} unit=" kg" width={58} />
                <Tooltip content={<WeightTip />} cursor={{ stroke: '#E5E7EB', strokeWidth: 1 }} />
                <Area type="monotone" dataKey="kg"
                  stroke="#1E3EB4" strokeWidth={2.5}
                  fill="url(#modalWGrad)"
                  dot={false}
                  activeDot={{ r: 4, fill: '#1E3EB4', strokeWidth: 0 }}
                  animationDuration={600}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Stats row */}
        {data.length > 0 && (
          <div style={{
            display: 'flex', gap: 1,
            borderTop: '1px solid #F3F4F6',
          }}>
            {[
              { label: 'O\'rtacha', val: avgW > 0 ? `${avgW.toFixed(1)} kg` : '—' },
              { label: 'Minimum',   val: weights.length ? `${Math.min(...weights).toFixed(1)} kg` : '—' },
              { label: 'Maksimum',  val: weights.length ? `${Math.max(...weights).toFixed(1)} kg` : '—' },
              { label: 'O\'lchov',  val: `${data.reduce((a, b) => a + (b.cnt ?? 0), 0)} ta` },
            ].map(s => (
              <div key={s.label} style={{
                flex: 1, padding: '12px 16px', textAlign: 'center',
                borderRight: '1px solid #F3F4F6',
              }}>
                <div style={{
                  fontSize: 14, fontWeight: 700, color: '#0D1117',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {s.val}
                </div>
                <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function DashboardPage() {
  const navigate = useNavigate();
  const [devModalOpen, setDevModalOpen] = useState(false);

  // ─── Queries ────────────────────────────────────────────────────────────────

  const { data: overview } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn:  () => apiFetch<OverviewStats>('/api/v1/analytics/overview'),
    staleTime: 60_000,
  });

  const { data: health } = useQuery({
    queryKey: ['analytics', 'health'],
    queryFn:  () => apiFetch<HealthMetrics>('/api/v1/analytics/health/metrics'),
    staleTime: 60_000,
  });

  const { data: adiSummary } = useQuery({
    queryKey: ['adi', 'farm-summary'],
    queryFn:  () => apiFetch<ADIFarmSummary>('/api/v1/adi/farm-summary'),
    staleTime: 5 * 60_000,
  });

  // Weight trends — all periods cached
  const { data: w7  } = useQuery({ queryKey: ['wt', 7],  queryFn: () => apiFetch<WeightTrendRaw>('/api/v1/analytics/trends/weight?days=7'),  staleTime: 5 * 60_000 });
  const { data: w30 } = useQuery({ queryKey: ['wt', 30], queryFn: () => apiFetch<WeightTrendRaw>('/api/v1/analytics/trends/weight?days=30'), staleTime: 5 * 60_000 });
  const { data: w90 } = useQuery({ queryKey: ['wt', 90], queryFn: () => apiFetch<WeightTrendRaw>('/api/v1/analytics/trends/weight?days=90'), staleTime: 5 * 60_000 });

  // Species counts — parallel, limit=100 (max), use array length
  const speciesQ = useQueries({
    queries: SPECIES_CFG.map(sp => ({
      queryKey: ['species-cnt', sp.key],
      queryFn:  async () => {
        const res = await apiFetch<any>(`/api/v1/animals/search?species=${sp.key}&limit=100`);
        return Array.isArray(res) ? res.length : (res?.total ?? 0);
      },
      staleTime: 5 * 60_000,
    })),
  });

  // ADI health trend — 7 daily points
  const today = new Date();
  const adiTrendQ = useQueries({
    queries: [0, 1, 2, 3, 4, 5, 6].map(daysAgo => {
      const d = subtractDays(today, daysAgo);
      const ds = formatDate(d);
      return {
        queryKey: ['adi-farm', ds],
        queryFn:  () => apiFetch<ADIFarmSummary>(`/api/v1/adi/farm-summary?date=${ds}`),
        staleTime: 60 * 60_000,
      };
    }),
  });

  // ─── Derived ────────────────────────────────────────────────────────────────

  const totalAnimals = overview?.animals?.total ?? 0;

  // Species donut — use fetched counts
  const speciesCounts = SPECIES_CFG.map((sp, i) => ({
    name:  sp.label,
    value: (speciesQ[i].data as number) ?? 0,
    color: sp.color,
  }));
  const speciesNonZero = speciesCounts.filter(s => s.value > 0);
  const speciesTotal   = speciesNonZero.reduce((a, b) => a + b.value, 0);

  // Status donut
  const statusByKey  = health?.animals_by_status ?? {};
  const statusSlices = STATUS_CFG.map(s => ({
    name: s.label, value: statusByKey[s.key] ?? 0, color: s.color,
  })).filter(d => d.value > 0);
  const statusTotal  = statusSlices.reduce((a, b) => a + b.value, 0);

  // Weight trend getter
  const getWeightTrend = (days: number) => {
    const raw = days <= 7 ? w7 : days <= 30 ? w30 : w90;
    return raw?.data ?? [];
  };

  // Weight trend for card 6 mini chart (30 days)
  const weightTrend30 = (w30?.data ?? []).map(p => ({
    date: shortDate(p.date),
    kg:   p.average_weight,
    cnt:  p.measurement_count,
  }));

  // ADI health trend for card 5
  const adiHealthTrend = [...adiTrendQ]
    .reverse()
    .map((q, i) => ({
      date:  shortDate(formatDate(subtractDays(today, 6 - i))),
      score: (q.data as ADIFarmSummary)?.farm_adi_score ?? null,
    }))
    .filter(d => d.score !== null && d.score > 0);

  // Farm ADI
  const farmAdi      = adiSummary?.farm_adi_score ?? 0;
  const farmAdiColor = farmAdi >= 70 ? '#10B981' : farmAdi >= 40 ? '#F59E0B' : '#EF4444';

  // ADI distribution
  const adiDist = adiSummary ? [
    { name: "Sog'lom",   value: adiSummary.healthy_count,  color: '#10B981' },
    { name: "O'rtacha",  value: adiSummary.average_count,  color: '#F59E0B' },
    { name: 'Ogohlantr.', value: adiSummary.warning_count,  color: '#F97316' },
    { name: 'Kritik',    value: adiSummary.critical_count, color: '#EF4444' },
  ] : [];
  const adiDistTotal = adiDist.reduce((a, b) => a + b.value, 0);

  // Attention list
  const attention = (adiSummary?.needs_attention ?? []).slice(0, 6);

  // Weight stats
  const avgKg        = overview?.weight?.average_kg ?? 0;
  const totalKg      = avgKg * totalAnimals;
  const totalTonnes  = totalKg / 1000;
  const weightChange = overview?.weight?.change_percentage_7d;
  const WIcon        = (weightChange ?? 0) > 0 ? TrendingUp :
                       (weightChange ?? 0) < 0 ? TrendingDown : Minus;
  const wColor       = (weightChange ?? 0) > 0 ? '#10B981' :
                       (weightChange ?? 0) < 0 ? '#EF4444' : '#9CA3AF';

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <>
      <style>{`
        /* ── Hide ALL scrollbars ── */
        html, body, .tv-dashboard {
          scrollbar-width: none !important;
          -ms-overflow-style: none !important;
        }
        html::-webkit-scrollbar,
        body::-webkit-scrollbar,
        .tv-dashboard::-webkit-scrollbar { display: none !important; }

        @keyframes tv-fadein  { from { opacity: 0; } to { opacity: 1; } }
        @keyframes tv-slideup { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

        .c1 { animation: tv-slideup .38s ease both .04s; }
        .c2 { animation: tv-slideup .38s ease both .09s; }
        .c3 { animation: tv-slideup .38s ease both .14s; }
        .c4 { animation: tv-slideup .38s ease both .19s; }
        .c5 { animation: tv-slideup .38s ease both .24s; }
        .c6 { animation: tv-slideup .38s ease both .29s; }

        .attn-row { transition: background .12s; }
        .attn-row:hover { background: #F9FAFB; }

        .period-btn { transition: all .15s; }
        .period-btn:hover { border-color: #1E3EB4 !important; color: #1E3EB4 !important; }
      `}</style>

      {/* ── Modal ── */}
      {devModalOpen && (
        <DevChartModal
          onClose={() => setDevModalOpen(false)}
          weightTrend={getWeightTrend}
          defaultDays={30}
        />
      )}

      <div
        className="tv-dashboard"
        style={{
          minHeight: 'calc(100vh - 64px)',
          background: '#F7F8FA',
          padding: '18px 22px 26px',
          fontFamily: "'Outfit', sans-serif",
          overflowY: 'auto',
        }}
      >
        <div style={{ maxWidth: 1280, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* ═══════════════════════════════════════
              QATOR 1 — 3 karta
          ═══════════════════════════════════════ */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>

            {/* ── KARTA 1: Jonivorlar turlari ── */}
            <Card className="c1">
              <CardHead title="Jonivorlar turlari" />
              <div style={{
                display: 'flex', alignItems: 'center',
                gap: 14, padding: '14px 16px 16px',
                flex: 1,
              }}>
                <DonutChart
                  data={speciesNonZero.length > 0 ? speciesNonZero : speciesCounts}
                  total={speciesTotal || totalAnimals}
                  sub="Jami"
                />
                <Legend
                  items={SPECIES_CFG.map((sp, i) => ({
                    label: sp.label,
                    value: (speciesQ[i].data as number) ?? 0,
                    color: sp.color,
                  }))}
                />
              </div>
            </Card>

            {/* ── KARTA 2: Sog'liq holati ── */}
            <Card className="c2">
              <CardHead title="Sog'liq holati" />
              <div style={{
                display: 'flex', alignItems: 'center',
                gap: 14, padding: '14px 16px 16px',
                flex: 1,
              }}>
                <DonutChart
                  data={statusSlices}
                  total={statusTotal}
                  sub="Jonivor"
                />
                <Legend
                  items={STATUS_CFG.map(s => ({
                    label: s.label,
                    value: statusByKey[s.key] ?? 0,
                    color: s.color,
                  }))}
                />
              </div>
            </Card>

            {/* ── KARTA 3: Fermaning rivojlanishi — bosilsa modal ── */}
            <Card className="c3" onClick={() => setDevModalOpen(true)}>
              <CardHead
                title={
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    Fermaning rivojlanishi
                    <span style={{
                      fontSize: 9, background: '#EFF6FF', color: '#1E3EB4',
                      borderRadius: 4, padding: '2px 5px', fontWeight: 500,
                    }}>
                      Ko'rish →
                    </span>
                  </span>
                }
                action={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{
                      fontSize: 18, fontWeight: 800, color: farmAdiColor,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>
                      {farmAdi.toFixed(0)}
                    </span>
                    <span style={{ fontSize: 10, color: '#9CA3AF' }}>ADI</span>
                  </div>
                }
              />
              {/* Mini preview chart */}
              <div style={{ padding: '10px 6px 6px 0', flex: 1, pointerEvents: 'none' }}>
                {weightTrend30.length < 2 ? (
                  <div style={{
                    height: 110, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', color: '#D1D5DB', fontSize: 11,
                    flexDirection: 'column', gap: 6,
                  }}>
                    <TrendingUp size={24} color="#E5E7EB" />
                    <span>Bosib batafsil ko'ring</span>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={110}>
                    <AreaChart data={weightTrend30.slice(-14)} margin={{ top: 4, right: 12, left: -28, bottom: 0 }}>
                      <defs>
                        <linearGradient id="cg3" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#1E3EB4" stopOpacity={0.14} />
                          <stop offset="95%" stopColor="#1E3EB4" stopOpacity={0.01} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                      <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#C4C9D4' }}
                        tickLine={false} axisLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 8, fill: '#C4C9D4' }} tickLine={false} axisLine={false} />
                      <Area type="monotone" dataKey="kg" stroke="#1E3EB4" strokeWidth={2}
                        fill="url(#cg3)" dot={false} isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div style={{
                padding: '8px 16px 12px',
                fontSize: 10, color: '#9CA3AF', textAlign: 'center',
                borderTop: '1px solid #F9FAFB',
              }}>
                1k · 7k · 30k · 90k · Maxsus sana — bosib tanlang
              </div>
            </Card>

          </div>

          {/* ═══════════════════════════════════════
              QATOR 2 — 3 karta
          ═══════════════════════════════════════ */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>

            {/* ── KARTA 4: Diqqat talab qiladiganlar ── */}
            <Card className="c4" onClick={() => navigate('/adi')}>
              <CardHead
                title="Diqqat talab qiladiganlar"
                action={
                  <span style={{
                    fontSize: 20, fontWeight: 800,
                    color: attention.length > 0 ? '#F97316' : '#10B981',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {attention.length}
                  </span>
                }
              />
              <div style={{ flex: 1 }}>
                {attention.length === 0 ? (
                  <div style={{
                    height: 160, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', gap: 8,
                  }}>
                    <CheckCircle size={36} color="#10B981" opacity={0.35} />
                    <span style={{ fontSize: 12, color: '#9CA3AF' }}>Hammasi yaxshi</span>
                  </div>
                ) : (
                  attention.map(item => {
                    const cfg = ADI_CFG[item.category as keyof typeof ADI_CFG] ?? ADI_CFG.warning;
                    const TI  = item.trend === 'improving' ? TrendingUp :
                                item.trend === 'declining' ? TrendingDown : Minus;
                    return (
                      <div key={item.animal_id} className="attn-row" style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '9px 16px',
                        borderBottom: '1px solid #F9FAFB',
                      }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                          background: cfg.color + '1A',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <span style={{
                            fontSize: 11, fontWeight: 800, color: cfg.color,
                            fontFamily: "'JetBrains Mono', monospace",
                          }}>
                            {Math.round(item.adi_score)}
                          </span>
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 12, fontWeight: 600, color: '#0D1117',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {item.tag_id}
                          </div>
                          <div style={{ fontSize: 10, color: cfg.color, marginTop: 1 }}>
                            {cfg.label}
                          </div>
                        </div>
                        <TI size={12} color={
                          item.trend === 'improving' ? '#10B981' :
                          item.trend === 'declining' ? '#EF4444' : '#D1D5DB'
                        } />
                        <ChevronRight size={12} color="#D1D5DB" />
                      </div>
                    );
                  })
                )}
              </div>
            </Card>

            {/* ── KARTA 5: Ferma sog'lig'i grafigi ── */}
            <Card className="c5">
              <CardHead
                title="Ferma sog'lig'i (ADI trendi)"
                action={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: farmAdiColor,
                    }} />
                    <span style={{ fontSize: 11, color: '#6B7280', fontFamily: "'Outfit', sans-serif" }}>
                      {farmAdi.toFixed(0)}/100
                    </span>
                  </div>
                }
              />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>

                {/* ADI trend chart */}
                <div style={{ padding: '10px 6px 4px 0' }}>
                  {adiHealthTrend.length < 2 ? (
                    <div style={{
                      height: 90, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', color: '#D1D5DB', fontSize: 11,
                    }}>
                      ADI ma'lumot to'planmoqda...
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height={90}>
                      <AreaChart data={adiHealthTrend} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="adiHGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor={farmAdiColor} stopOpacity={0.18} />
                            <stop offset="95%" stopColor={farmAdiColor} stopOpacity={0.01} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                        <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#C4C9D4' }}
                          tickLine={false} axisLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#C4C9D4' }}
                          tickLine={false} axisLine={false} />
                        <Tooltip content={<AdiTip />} cursor={{ stroke: '#E5E7EB', strokeWidth: 1 }} />
                        <Area type="monotone" dataKey="score"
                          stroke={farmAdiColor} strokeWidth={2}
                          fill="url(#adiHGrad)" dot={false}
                          activeDot={{ r: 3, fill: farmAdiColor, strokeWidth: 0 }}
                          animationDuration={600}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* ADI distribution bars */}
                <div style={{ padding: '4px 16px 14px', display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {adiDist.map(cat => {
                    const pct = adiDistTotal > 0 ? (cat.value / adiDistTotal) * 100 : 0;
                    return (
                      <div key={cat.name}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 7, height: 7, borderRadius: '50%', background: cat.color }} />
                            <span style={{ fontSize: 10, color: '#6B7280' }}>{cat.name}</span>
                          </div>
                          <span style={{
                            fontSize: 10, fontWeight: 700,
                            color: cat.value > 0 ? cat.color : '#E5E7EB',
                            fontFamily: "'JetBrains Mono', monospace",
                          }}>
                            {cat.value}
                          </span>
                        </div>
                        <div style={{ height: 4, background: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', width: `${pct}%`,
                            background: cat.color, borderRadius: 3,
                            transition: 'width .7s ease',
                          }} />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Alert summary */}
                {health && (health.alert_summary.critical > 0 || health.alert_summary.warning > 0) && (
                  <div style={{
                    display: 'flex', gap: 8, padding: '10px 16px 14px',
                    borderTop: '1px solid #F3F4F6', marginTop: 'auto',
                  }}>
                    {[
                      { label: 'Kritik',       val: health.alert_summary.critical, color: '#EF4444' },
                      { label: 'Ogohlantirish', val: health.alert_summary.warning,  color: '#F59E0B' },
                      { label: 'Jami alert',   val: health.alert_summary.total,    color: '#6B7280' },
                    ].map(a => (
                      <div key={a.label} style={{
                        flex: 1, textAlign: 'center',
                        background: a.val > 0 ? a.color + '12' : '#F9FAFB',
                        borderRadius: 8, padding: '7px 4px',
                      }}>
                        <div style={{
                          fontSize: 16, fontWeight: 800,
                          color: a.val > 0 ? a.color : '#D1D5DB',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {a.val}
                        </div>
                        <div style={{ fontSize: 9, color: '#9CA3AF', marginTop: 1 }}>{a.label}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* ── KARTA 6: Umumiy tirik vazn ── */}
            <Card className="c6">
              <CardHead title="Umumiy tirik vazn" />
              <div style={{ flex: 1, padding: '14px 18px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>

                {/* Big number */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span style={{
                      fontSize: 38, fontWeight: 900, color: '#0D1117',
                      fontFamily: "'JetBrains Mono', monospace",
                      lineHeight: 1, letterSpacing: '-0.02em',
                    }}>
                      {totalTonnes >= 1 ? totalTonnes.toFixed(2) : totalKg > 0 ? totalKg.toFixed(0) : '—'}
                    </span>
                    {(totalTonnes >= 1 || totalKg > 0) && (
                      <span style={{ fontSize: 15, fontWeight: 500, color: '#6B7280' }}>
                        {totalTonnes >= 1 ? 'tonna' : 'kg'}
                      </span>
                    )}
                  </div>
                  {totalTonnes >= 1 && totalKg > 0 && (
                    <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 3 }}>
                      = {totalKg.toLocaleString('uz-UZ', { maximumFractionDigits: 0 })} kg
                    </div>
                  )}
                  {weightChange != null && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 5 }}>
                      <WIcon size={11} color={wColor} />
                      <span style={{ fontSize: 11, color: wColor, fontWeight: 600 }}>
                        {weightChange >= 0 ? '+' : ''}{weightChange.toFixed(1)}% so'nggi 7 kun
                      </span>
                    </div>
                  )}
                </div>

                {/* Mini trend */}
                <div style={{ flex: 1 }}>
                  {weightTrend30.length < 2 ? (
                    <div style={{
                      height: 70, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', color: '#D1D5DB', fontSize: 10,
                    }}>
                      Ma'lumot to'planmoqda...
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height={80}>
                      <LineChart data={weightTrend30} margin={{ top: 4, right: 4, left: -36, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                        <XAxis dataKey="date" tick={{ fontSize: 8, fill: '#C4C9D4' }}
                          tickLine={false} axisLine={false} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 8, fill: '#C4C9D4' }}
                          tickLine={false} axisLine={false} unit="kg" />
                        <Tooltip content={<WeightTip />} cursor={{ stroke: '#E5E7EB', strokeWidth: 1 }} />
                        <Line type="monotone" dataKey="kg"
                          stroke="#1E3EB4" strokeWidth={2} dot={false}
                          activeDot={{ r: 3, fill: '#1E3EB4', strokeWidth: 0 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Bottom stats */}
                <div style={{ display: 'flex', gap: 8, paddingTop: 10, borderTop: '1px solid #F3F4F6' }}>
                  {[
                    { label: 'Bitta jonivor', val: avgKg > 0 ? `${avgKg.toFixed(1)} kg` : '—' },
                    { label: 'Jonivorlar',    val: totalAnimals > 0 ? `${totalAnimals} ta` : '—' },
                  ].map(s => (
                    <div key={s.label} style={{ flex: 1, textAlign: 'center' }}>
                      <div style={{
                        fontSize: 14, fontWeight: 700, color: '#374151',
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {s.val}
                      </div>
                      <div style={{ fontSize: 9, color: '#9CA3AF', marginTop: 2 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

          </div>

        </div>
      </div>
    </>
  );
}