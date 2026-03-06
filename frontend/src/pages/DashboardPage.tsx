/**
 * Taurus Vision — Dashboard Page (UI Redesign)
 * Top navbar saqlanadi, hamma ma'lumot real API ga ulangan
 * Bu faylni: frontend/src/pages/DashboardPage.tsx ga ko'chiring
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Minus,
  AlertTriangle, ChevronRight, CheckCircle,
  Activity, Scale, Thermometer, Wheat,
  Eye, ArrowUpRight,
} from 'lucide-react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  blue:      '#1E3EB4',
  blueMid:   '#3B5FD9',
  blueLt:    '#EEF2FF',
  blueXlt:   '#F5F8FF',
  green:     '#059669',
  greenLt:   '#ECFDF5',
  amber:     '#D97706',
  amberLt:   '#FFFBEB',
  orange:    '#EA580C',
  orangeLt:  '#FFF7ED',
  red:       '#DC2626',
  redLt:     '#FEF2F2',
  purple:    '#7C3AED',
  purpleLt:  '#F5F3FF',
  bg:        '#F4F6FA',
  surface:   '#FFFFFF',
  border:    '#E8EBF2',
  borderDark:'#D1D5DB',
  text1:     '#0D1117',
  text2:     '#1F2937',
  text3:     '#6B7280',
  text4:     '#9CA3AF',
  mono:      "'JetBrains Mono', monospace",
  sans:      "'Plus Jakarta Sans', sans-serif",
};

// ─── Types ────────────────────────────────────────────────────────────────────
interface OverviewStats {
  animals: { total: number; active: number };
  weight:  { average_kg: number | null; change_percentage_7d: number | null };
}
interface HealthMetrics {
  animals_by_status: Record<string, number>;
  alert_summary:     { total: number; critical: number; warning: number };
  risk_score:        number;
}
interface ADIFarmSummary {
  date:           string;
  farm_adi_score: number;
  healthy_count:  number;
  average_count:  number;
  warning_count:  number;
  critical_count: number;
  needs_attention: { animal_id: number; tag_id: string; species: string; adi_score: number; category: string; trend: string }[];
}
interface WeightTrendRaw {
  data: { date: string; average_weight: number; measurement_count: number }[];
}

// ─── Config ───────────────────────────────────────────────────────────────────
const SPECIES_CFG = [
  { key: 'cattle', label: 'Qoramol', color: C.blue   },
  { key: 'sheep',  label: "Qo'y",    color: C.green  },
  { key: 'goat',   label: 'Echki',   color: C.amber  },
  { key: 'horse',  label: 'Ot',      color: C.purple },
  { key: 'other',  label: 'Boshqa',  color: C.text4  },
];

const STATUS_CFG = [
  { key: 'active',      label: "Sog'lom",     color: C.green  },
  { key: 'sick',        label: 'Kasal',       color: C.red    },
  { key: 'quarantine',  label: 'Karantin',    color: C.amber  },
  { key: 'deceased',    label: 'Vafot etdi',  color: C.text4  },
  { key: 'sold',        label: 'Sotilgan',    color: C.blue   },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (d: Date) => d.toISOString().split('T')[0];
const sub = (d: Date, n: number) => { const r = new Date(d); r.setDate(r.getDate() - n); return r; };
const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' });

// ─── Custom Tooltip ───────────────────────────────────────────────────────────
function CustomTip({ active, payload, label, unit = '' }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
      padding: '8px 13px', boxShadow: '0 8px 24px rgba(0,0,0,0.10)',
      fontFamily: C.sans,
    }}>
      <div style={{ fontSize: 10, color: C.text4, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: C.text1, fontFamily: C.mono }}>
        {payload[0]?.value?.toFixed(1)}{unit}
      </div>
    </div>
  );
}

// ─── Tiny Sparkline ───────────────────────────────────────────────────────────
function Spark({ data, color, h = 40 }: { data: number[]; color: string; h?: number }) {
  if (data.length < 2) return null;
  const min = Math.min(...data) * 0.97;
  const max = Math.max(...data) * 1.03;
  const W = 80;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return `${x},${y}`;
  }).join(' ');
  const area = `0,${h} ${pts} ${W},${h}`;
  return (
    <svg viewBox={`0 0 ${W} ${h}`} style={{ width: W, height: h }} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sg-${color.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.2"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#sg-${color.slice(1)})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────
function SectionHead({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 18px 12px', borderBottom: `1px solid ${C.border}`,
    }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: C.text2, fontFamily: C.sans, letterSpacing: '0.01em' }}>
        {title}
      </span>
      {action}
    </div>
  );
}

// ─── Card shell ───────────────────────────────────────────────────────────────
function Card({
  children, onClick, style = {}, className = '',
}: {
  children: React.ReactNode; onClick?: () => void;
  style?: React.CSSProperties; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div ref={ref} onClick={onClick} className={className} style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 16, overflow: 'hidden',
      boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      cursor: onClick ? 'pointer' : 'default',
      transition: 'transform .18s, box-shadow .18s',
      display: 'flex', flexDirection: 'column',
      ...style,
    }}
    onMouseEnter={() => { if (onClick && ref.current) { ref.current.style.transform = 'translateY(-2px)'; ref.current.style.boxShadow = '0 8px 28px rgba(0,0,0,0.09)'; } }}
    onMouseLeave={() => { if (onClick && ref.current) { ref.current.style.transform = 'none'; ref.current.style.boxShadow = '0 1px 4px rgba(0,0,0,0.05)'; } }}
    >
      {children}
    </div>
  );
}

// ─── KPI Stat Card ────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, trend, sparkData, accentColor, icon: Icon, onClick, delay = 0,
}: {
  label: string; value: string; sub?: string; trend?: number;
  sparkData?: number[]; accentColor: string; icon: React.ElementType;
  onClick?: () => void; delay?: number;
}) {
  const up    = (trend ?? 0) > 0;
  const down  = (trend ?? 0) < 0;
  const TIcon = up ? TrendingUp : down ? TrendingDown : Minus;
  const tCol  = up ? C.green : down ? C.red : C.text4;

  return (
    <Card onClick={onClick} style={{ animationDelay: `${delay}ms` }} className="tv2-rise">
      <div style={{ padding: '16px 18px 14px' }}>
        {/* Top row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: accentColor + '18',
            display: 'grid', placeItems: 'center', flexShrink: 0,
          }}>
            <Icon size={16} color={accentColor}/>
          </div>
          {trend !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 3, color: tCol }}>
              <TIcon size={12}/>
              <span style={{ fontSize: 11, fontWeight: 700, fontFamily: C.mono }}>
                {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Value */}
        <div style={{ fontFamily: C.mono, fontSize: 26, fontWeight: 800, color: C.text1, lineHeight: 1, marginBottom: 4 }}>
          {value}
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.text2, marginBottom: sub ? 3 : 0 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: C.text4 }}>{sub}</div>}
      </div>

      {/* Sparkline footer */}
      {sparkData && sparkData.length >= 2 && (
        <div style={{
          padding: '0 0 0 0', borderTop: `1px solid ${C.border}`,
          background: accentColor + '06',
        }}>
          <ResponsiveContainer width="100%" height={44}>
            <AreaChart data={sparkData.map((v, i) => ({ i, v }))} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`sg-${accentColor.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={accentColor} stopOpacity={0.18}/>
                  <stop offset="95%" stopColor={accentColor} stopOpacity={0.01}/>
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke={accentColor} strokeWidth={2}
                fill={`url(#sg-${accentColor.slice(1)})`} dot={false} isAnimationActive={false}/>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

// ─── ADI Score Ring ───────────────────────────────────────────────────────────
function AdiRing({ score }: { score: number }) {
  const color = score >= 70 ? C.green : score >= 40 ? C.amber : C.red;
  const label = score >= 70 ? "Yaxshi" : score >= 40 ? "O'rtacha" : "Xavfli";
  const r = 36, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div style={{ position: 'relative', width: 90, height: 90, flexShrink: 0 }}>
      <svg width="90" height="90" viewBox="0 0 90 90">
        <circle cx="45" cy="45" r={r} fill="none" stroke={C.border} strokeWidth="8"/>
        <circle cx="45" cy="45" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ * 0.25}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray .8s ease' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 20, fontWeight: 900, color, fontFamily: C.mono, lineHeight: 1 }}>{score.toFixed(0)}</span>
        <span style={{ fontSize: 8, color: C.text4, marginTop: 2 }}>{label}</span>
      </div>
    </div>
  );
}

// ─── Progress bar ─────────────────────────────────────────────────────────────
function ProgBar({ label, val, total, color }: { label: string; val: number; total: number; color: string }) {
  const pct = total > 0 ? (val / total) * 100 : 0;
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: color }}/>
          <span style={{ fontSize: 11, color: C.text3 }}>{label}</span>
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: val > 0 ? color : C.border, fontFamily: C.mono }}>{val}</span>
      </div>
      <div style={{ height: 4, background: '#F1F3F9', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width .8s ease' }}/>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function DashboardPage() {
  const navigate = useNavigate();

  // ── Queries ────────────────────────────────────────────────────────────────
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

  const { data: w30 } = useQuery({
    queryKey: ['wt', 30],
    queryFn:  () => apiFetch<WeightTrendRaw>('/api/v1/analytics/trends/weight?days=30'),
    staleTime: 5 * 60_000,
  });

  // ADI trend (7 kun)
  const today = new Date();
  const adiTrendQ = useQueries({
    queries: [0,1,2,3,4,5,6].map(ago => {
      const ds = fmt(sub(today, ago));
      return {
        queryKey:  ['adi-farm', ds],
        queryFn:   () => apiFetch<ADIFarmSummary>(`/api/v1/adi/farm-summary?date=${ds}`),
        staleTime: 60 * 60_000,
      };
    }),
  });

  // Species counts
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

  // ── Derived ────────────────────────────────────────────────────────────────
  const totalAnimals  = overview?.animals?.total ?? 0;
  const activeAnimals = overview?.animals?.active ?? 0;
  const avgKg         = overview?.weight?.average_kg ?? 0;
  const totalKg       = avgKg * totalAnimals;
  const totalTonnes   = totalKg / 1000;
  const weightChange  = overview?.weight?.change_percentage_7d ?? 0;

  const farmAdi  = adiSummary?.farm_adi_score ?? 0;
  const adiColor = farmAdi >= 70 ? C.green : farmAdi >= 40 ? C.amber : C.red;

  const attention  = (adiSummary?.needs_attention ?? []).slice(0, 5);
  const totalAlerts  = health?.alert_summary?.total    ?? 0;
  const critAlerts   = health?.alert_summary?.critical ?? 0;

  const statusByKey = health?.animals_by_status ?? {};

  // Weight trend for chart
  const weightChartData = (w30?.data ?? []).map(p => ({
    date: shortDate(p.date),
    kg:   p.average_weight,
  }));
  const weightSpark = (w30?.data ?? []).map(p => p.average_weight).filter(Boolean);

  // ADI trend chart
  const adiChartData = [...adiTrendQ]
    .reverse()
    .map((q, i) => ({
      date:  shortDate(fmt(sub(today, 6 - i))),
      score: (q.data as ADIFarmSummary)?.farm_adi_score ?? null,
    }))
    .filter(d => d.score !== null && d.score > 0);

  const adiSpark = adiChartData.map(d => d.score as number);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

        .tv2-page { font-family: ${C.sans}; }

        @keyframes tv2-rise {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .tv2-rise { animation: tv2-rise .38s ease both; }

        .tv2-row:hover { background: #F9FAFB !important; }
        .tv2-link:hover { color: ${C.blueMid} !important; text-decoration: underline; }
      `}</style>

      <div className="tv2-page" style={{ background: C.bg, minHeight: 'calc(100vh - 56px)', padding: '20px 24px 32px' }}>
        <div style={{ maxWidth: 1360, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Page title ── */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text1, margin: 0, lineHeight: 1 }}>
                Ferma holati
              </h1>
              <p style={{ fontSize: 12, color: C.text4, marginTop: 4 }}>
                {new Date().toLocaleDateString('uz-UZ', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
            </div>
            <button
              onClick={() => navigate('/live')}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '8px 16px', borderRadius: 10,
                background: C.blue, border: 'none', color: '#fff',
                fontSize: 12, fontWeight: 700, cursor: 'pointer',
                fontFamily: C.sans, boxShadow: `0 2px 12px ${C.blue}40`,
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#6EE7B7', boxShadow: '0 0 0 2px rgba(110,231,183,0.4)', animation: 'tv2-ping 2s infinite' }}/>
              Live kamera
            </button>
          </div>

          {/* ══ ROW 1: 4 KPI karta ══ */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
            <StatCard
              label="Jonivorlar"
              value={totalAnimals > 0 ? String(totalAnimals) : '—'}
              sub={`${activeAnimals} ta faol`}
              accentColor={C.blue}
              icon={Activity}
              sparkData={weightSpark}
              onClick={() => navigate('/animals')}
              delay={0}
            />
            <StatCard
              label="ADI Ball (ferma)"
              value={farmAdi > 0 ? farmAdi.toFixed(0) : '—'}
              sub={farmAdi >= 70 ? "Poda sog'lom" : farmAdi >= 40 ? "E'tibor kerak" : "Xavfli holat"}
              trend={undefined}
              accentColor={adiColor}
              icon={Activity}
              sparkData={adiSpark}
              onClick={() => navigate('/adi')}
              delay={70}
            />
            <StatCard
              label="Aktiv alertlar"
              value={totalAlerts > 0 ? String(totalAlerts) : '0'}
              sub={critAlerts > 0 ? `${critAlerts} ta kritik` : "Hammasi tartibda"}
              accentColor={critAlerts > 0 ? C.red : C.green}
              icon={AlertTriangle}
              onClick={() => navigate('/alerts')}
              delay={140}
            />
            <StatCard
              label="Umumiy tirik vazn"
              value={totalTonnes >= 1 ? `${totalTonnes.toFixed(1)}t` : avgKg > 0 ? `${(avgKg).toFixed(0)}kg` : '—'}
              sub={avgKg > 0 ? `O'rtacha ${avgKg.toFixed(0)} kg/bosh` : undefined}
              trend={weightChange ?? undefined}
              accentColor={C.amber}
              icon={Scale}
              sparkData={weightSpark}
              onClick={() => navigate('/animals')}
              delay={210}
            />
          </div>

          {/* ══ ROW 2: Tur donut + ADI ring + Holat ══ */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px 300px', gap: 14 }}>

            {/* Jonivor turlari — gorizontal bar */}
            <Card className="tv2-rise" style={{ animationDelay: '280ms' }}>
              <SectionHead title="Jonivor turlari taqsimoti"/>
              <div style={{ padding: '16px 20px 18px', flex: 1 }}>
                {SPECIES_CFG.map((sp, i) => {
                  const cnt = (speciesQ[i].data as number) ?? 0;
                  const pct = totalAnimals > 0 ? Math.round((cnt / totalAnimals) * 100) : 0;
                  return (
                    <div key={sp.key} style={{ marginBottom: 13 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 9, height: 9, borderRadius: '50%', background: sp.color }}/>
                          <span style={{ fontSize: 13, fontWeight: 500, color: C.text2 }}>{sp.label}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 11, color: C.text4 }}>{pct}%</span>
                          <span style={{ fontSize: 13, fontWeight: 700, color: sp.color, fontFamily: C.mono, minWidth: 28, textAlign: 'right' }}>{cnt}</span>
                        </div>
                      </div>
                      <div style={{ height: 6, background: '#F1F3F9', borderRadius: 6, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: sp.color, borderRadius: 6, transition: 'width .9s ease' }}/>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Ferma ADI holati */}
            <Card className="tv2-rise" style={{ animationDelay: '340ms' }}>
              <SectionHead title="Ferma ADI holati"/>
              <div style={{ padding: '16px 18px', flex: 1 }}>
                {/* Ring + score */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18, paddingBottom: 16, borderBottom: `1px solid ${C.border}` }}>
                  <AdiRing score={farmAdi}/>
                  <div>
                    <div style={{ fontSize: 11, color: C.text4, marginBottom: 4 }}>Bugungi poda bahosi</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: adiColor, marginBottom: 8 }}>
                      {farmAdi >= 70 ? '✓ Yaxshi' : farmAdi >= 40 ? '⚠ E\'tibor kerak' : '✗ Xavfli'}
                    </div>
                    <div style={{ fontSize: 11, color: C.text4 }}>
                      {adiSummary?.healthy_count ?? '—'} ta sog'lom jonivor
                    </div>
                  </div>
                </div>
                {/* Distribution */}
                <ProgBar label="Sog'lom (70+)"      val={adiSummary?.healthy_count  ?? 0} total={totalAnimals} color={C.green}/>
                <ProgBar label="O'rtacha (40–70)"   val={adiSummary?.average_count  ?? 0} total={totalAnimals} color={C.amber}/>
                <ProgBar label="Ogohlantirish (<40)" val={adiSummary?.warning_count  ?? 0} total={totalAnimals} color={C.orange}/>
                <ProgBar label="Kritik (<20)"        val={adiSummary?.critical_count ?? 0} total={totalAnimals} color={C.red}/>
              </div>
            </Card>

            {/* Sog'liq holati */}
            <Card className="tv2-rise" style={{ animationDelay: '400ms' }}>
              <SectionHead title="Sog'liq va alertlar"/>
              <div style={{ padding: '14px 18px', flex: 1 }}>
                {/* Alert summary */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr',
                  gap: 8, marginBottom: 16,
                }}>
                  {[
                    { label: 'Kritik',   val: critAlerts,                                      color: C.red,    bg: C.redLt    },
                    { label: 'Ogohlan.', val: (health?.alert_summary?.warning ?? 0),           color: C.amber,  bg: C.amberLt  },
                    { label: 'Xavf bali', val: health?.risk_score != null ? `${health.risk_score.toFixed(0)}` : '—', color: C.purple, bg: C.purpleLt },
                    { label: 'Jami alert', val: totalAlerts,                                   color: C.blue,   bg: C.blueLt   },
                  ].map(s => (
                    <div key={s.label} style={{ background: s.bg, borderRadius: 10, padding: '10px 12px', textAlign: 'center' }}>
                      <div style={{ fontSize: 20, fontWeight: 900, color: s.color, fontFamily: C.mono }}>{s.val}</div>
                      <div style={{ fontSize: 10, color: C.text4, marginTop: 2 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
                {/* Status bars */}
                {STATUS_CFG.map(s => (
                  <ProgBar key={s.key} label={s.label} val={statusByKey[s.key] ?? 0} total={totalAnimals} color={s.color}/>
                ))}
              </div>
            </Card>
          </div>

          {/* ══ ROW 3: Grafik + Diqqat talab qiladiganlar ══ */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

            {/* Vazn + ADI trend grafigi */}
            <Card className="tv2-rise" style={{ animationDelay: '460ms' }}>
              <SectionHead
                title="Vazn trendi (30 kun)"
                action={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {weightChange !== 0 && (
                      <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: weightChange > 0 ? C.green : C.red,
                        fontFamily: C.mono,
                        display: 'flex', alignItems: 'center', gap: 3,
                      }}>
                        {weightChange > 0 ? <TrendingUp size={11}/> : <TrendingDown size={11}/>}
                        {weightChange > 0 ? '+' : ''}{weightChange.toFixed(1)}%
                      </span>
                    )}
                  </div>
                }
              />
              <div style={{ padding: '16px 12px 8px 4px', flex: 1 }}>
                {weightChartData.length < 2 ? (
                  <div style={{ height: 180, display: 'grid', placeItems: 'center', color: C.text4, fontSize: 12 }}>
                    Ma'lumot to'planmoqda...
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={weightChartData} margin={{ top: 4, right: 12, left: -10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={C.blue} stopOpacity={0.14}/>
                          <stop offset="95%" stopColor={C.blue} stopOpacity={0.01}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F3F9"/>
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: C.text4, fontFamily: C.sans }}
                        tickLine={false} axisLine={false} interval="preserveStartEnd"/>
                      <YAxis tick={{ fontSize: 10, fill: C.text4 }} tickLine={false} axisLine={false} unit=" kg" width={52}/>
                      <Tooltip content={<CustomTip unit=" kg"/>} cursor={{ stroke: C.border }}/>
                      <Area type="monotone" dataKey="kg" stroke={C.blue} strokeWidth={2.5}
                        fill="url(#wGrad)" dot={false}
                        activeDot={{ r: 4, fill: C.blue, strokeWidth: 0 }}
                        animationDuration={700}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>

            {/* ADI trend */}
            <Card className="tv2-rise" style={{ animationDelay: '520ms' }}>
              <SectionHead
                title="Ferma ADI trendi (7 kun)"
                action={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: adiColor }}/>
                    <span style={{ fontSize: 11, fontWeight: 600, color: adiColor, fontFamily: C.mono }}>
                      {farmAdi.toFixed(0)}/100
                    </span>
                  </div>
                }
              />
              <div style={{ padding: '16px 12px 8px 4px', flex: 1 }}>
                {adiChartData.length < 2 ? (
                  <div style={{ height: 180, display: 'grid', placeItems: 'center', color: C.text4, fontSize: 12 }}>
                    ADI ma'lumot to'planmoqda...
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={adiChartData} margin={{ top: 4, right: 12, left: -10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="adiGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={adiColor} stopOpacity={0.16}/>
                          <stop offset="95%" stopColor={adiColor} stopOpacity={0.01}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F3F9"/>
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: C.text4, fontFamily: C.sans }}
                        tickLine={false} axisLine={false}/>
                      <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: C.text4 }}
                        tickLine={false} axisLine={false} width={30}/>
                      <Tooltip content={<CustomTip/>} cursor={{ stroke: C.border }}/>
                      <Area type="monotone" dataKey="score" stroke={adiColor} strokeWidth={2.5}
                        fill="url(#adiGrad)" dot={false}
                        activeDot={{ r: 4, fill: adiColor, strokeWidth: 0 }}
                        animationDuration={700}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
          </div>

          {/* ══ ROW 4: Diqqat talab qiladiganlar ══ */}
          <Card className="tv2-rise" style={{ animationDelay: '580ms' }}>
            <SectionHead
              title="Diqqat talab qiladiganlar"
              action={
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    fontSize: 18, fontWeight: 900, fontFamily: C.mono,
                    color: attention.length > 0 ? C.orange : C.green,
                  }}>
                    {attention.length}
                  </span>
                  <button
                    onClick={() => navigate('/adi')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      fontSize: 11, fontWeight: 600, color: C.blue,
                      background: C.blueLt, border: 'none', borderRadius: 7,
                      padding: '4px 10px', cursor: 'pointer', fontFamily: C.sans,
                    }}
                  >
                    Barchasi <ArrowUpRight size={11}/>
                  </button>
                </div>
              }
            />

            {attention.length === 0 ? (
              <div style={{ padding: '32px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <CheckCircle size={40} color={C.green} opacity={0.3}/>
                <span style={{ fontSize: 13, color: C.text4 }}>Hammasi yaxshi — diqqat talab qiladigan jonivor yo'q</span>
              </div>
            ) : (
              <>
                {/* Table header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 120px 80px 60px',
                  padding: '8px 20px', borderBottom: `1px solid ${C.border}`,
                  background: '#FAFBFD',
                }}>
                  {['Jonivor', 'Tag ID', 'ADI ball', 'Holat', 'Trend', ''].map(h => (
                    <span key={h} style={{ fontSize: 10, fontWeight: 700, color: C.text4, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{h}</span>
                  ))}
                </div>

                {attention.map((item, i) => {
                  const aCfg = item.category === 'critical'
                    ? { bg: C.redLt,    color: C.red,    label: 'Kritik'        }
                    : item.category === 'warning'
                    ? { bg: C.amberLt,  color: C.amber,  label: 'Ogohlantiruv' }
                    : { bg: C.orangeLt, color: C.orange, label: "O'rtacha"     };
                  const TI = item.trend === 'improving' ? TrendingUp
                           : item.trend === 'declining'  ? TrendingDown : Minus;
                  const tC = item.trend === 'improving' ? C.green
                           : item.trend === 'declining'  ? C.red : C.text4;
                  return (
                    <div
                      key={item.animal_id}
                      className="tv2-row"
                      onClick={() => navigate(`/animals/${item.animal_id}`)}
                      style={{
                        display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 120px 80px 60px',
                        padding: '13px 20px', cursor: 'pointer',
                        borderBottom: i < attention.length - 1 ? `1px solid ${C.border}` : 'none',
                        transition: 'background .12s',
                      }}
                    >
                      {/* Jonivor */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 34, height: 34, borderRadius: 9,
                          background: aCfg.color + '18',
                          display: 'grid', placeItems: 'center', flexShrink: 0,
                        }}>
                          <span style={{ fontSize: 11, fontWeight: 800, color: aCfg.color, fontFamily: C.mono }}>
                            {Math.round(item.adi_score)}
                          </span>
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: C.text1 }}>{item.tag_id}</div>
                          <div style={{ fontSize: 10, color: C.text4, textTransform: 'capitalize' }}>{item.species}</div>
                        </div>
                      </div>
                      {/* Tag */}
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <span style={{ fontSize: 11, fontFamily: C.mono, color: C.text3 }}>{item.tag_id}</span>
                      </div>
                      {/* Ball */}
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{ padding: '3px 11px', borderRadius: 20, background: aCfg.bg }}>
                          <span style={{ fontSize: 12, fontWeight: 800, color: aCfg.color, fontFamily: C.mono }}>
                            {item.adi_score.toFixed(1)}
                          </span>
                        </div>
                      </div>
                      {/* Holat */}
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '3px 9px',
                          borderRadius: 20, background: aCfg.bg, color: aCfg.color,
                          letterSpacing: '0.04em', textTransform: 'uppercase',
                        }}>
                          {aCfg.label}
                        </span>
                      </div>
                      {/* Trend */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: tC }}>
                        <TI size={13}/>
                        <span style={{ fontSize: 11, fontWeight: 600, fontFamily: C.sans }}>
                          {item.trend === 'improving' ? 'Yaxshilanmoqda'
                           : item.trend === 'declining' ? 'Tushmoqda' : 'Barqaror'}
                        </span>
                      </div>
                      {/* Arrow */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                        <ChevronRight size={14} color={C.text4}/>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </Card>

        </div>
      </div>
    </>
  );
}