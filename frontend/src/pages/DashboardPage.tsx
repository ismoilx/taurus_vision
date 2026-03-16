/**
 * Taurus Vision — DashboardPage
 *
 * ENDPOINTLAR:
 *   GET /api/v1/analytics/herd/statistics  → jonivorlar turi taqsimoti
 *   GET /api/v1/analytics/overview         → jami aktiv jonivorlar soni + vazn
 *
 * O'ZGARISHLAR:
 *   - Chap karta ichiga 2 ta ichki ramka qo'shildi (tizim ko'k rangi #1E3EB4)
 *   - Ramkalar karta pastki qatlamida turadi (z-index ko'tarilmagan)
 *   - Tooltip barcha qatlamlar ustida erkin suzadi (position: fixed, z-index: 9999)
 *   - O'ng karta 1, chap 30%: Jami tirik vazn ko'rsatkichlari qo'shildi
 */

import { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Sector,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { useIsMobile } from '../hooks/useResponsive';

// =============================================================================
// TYPES
// =============================================================================

interface OverviewStats {
  animals: { total: number; active: number; by_status: Record<string, number> };
  weight:  { average_kg: number | null; change_percentage_7d: number | null };
}


interface SpeciesBreakdown {
  species: string;
  count: number;
  percentage: number;
  avg_weight_kg: number | null;
}

interface HealthStatistics {
  health_score:     number;
  sick_count:       number;
  quarantine_count: number;
  total_animals:    number;
}

interface PredictionSummary {
  high_count:     number;
  critical_count: number;
}

interface AlertStats {
  total_open:    number;
  critical_open: number;
  high_open:     number;
  medium_open:   number;
  low_open:      number;
}

interface HerdStatistics {
  total_animals: number;
  active_animals: number;
  species_breakdown: SpeciesBreakdown[];
}

interface DonutEntry {
  species: string;
  label: string;
  value: number;
  percentage: number;
  color: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const SPECIES_COLORS: Record<string, string> = {
  cattle: '#3b82f6',
  sheep:  '#10b981',
  goat:   '#f59e0b',
  horse:  '#8b5cf6',
  other:  '#9ca3af',
};

const SPECIES_LABELS: Record<string, string> = {
  cattle: 'Qoramollar',
  sheep:  "Qo'ylar",
  goat:   'Echkilar',
  horse:  'Otlar',
  other:  'Boshqalar',
};

const MAX_OFFSET = 10;

// =============================================================================
// ADI TREND TYPES
// =============================================================================

interface ADITrendPoint {
  date: string;
  adi_score: number;
  animal_count?: number;
}

interface ADITrendsResponse {
  data: ADITrendPoint[];
  stats: { trend_direction: 'improving' | 'declining' | 'stable'; start_score: number; end_score: number };
  period_days: number;
}

type PeriodKey = 'all' | '7' | '15' | '30' | 'custom';

// =============================================================================
// TRADING CHART COMPONENT
// =============================================================================

function TradingChart() {
  const [period, setPeriod]         = useState<PeriodKey>('7');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo,   setCustomTo]   = useState('');
  const [showCustom, setShowCustom] = useState(false);

  const days = period === '30' ? 30 : period === '7' ? 7 : 3650;

  const { data, isLoading } = useQuery<ADITrendsResponse>({
    queryKey: ['adi-trends-dashboard', period, customFrom, customTo],
    queryFn:  () => {
      if (period === 'custom' && customFrom && customTo) {
        const from = new Date(customFrom);
        const to   = new Date(customTo);
        const d    = Math.max(1, Math.round((to.getTime() - from.getTime()) / 86400000));
        return apiFetch<ADITrendsResponse>(`/api/v1/analytics/trends/adi?days=${d}`);
      }
      return apiFetch<ADITrendsResponse>(`/api/v1/analytics/trends/adi?days=${days}`);
    },
    staleTime: 300_000,
    retry: false,
  });

  const chartData = useMemo(() => {
    const raw = data?.data ?? [];
    if (!raw.length) return [];
    let filtered = raw;
    if (period === 'custom' && customFrom && customTo) {
      filtered = raw.filter(p => p.date >= customFrom && p.date <= customTo);
    }
    return filtered.map(p => ({
      date:  p.date,
      value: Math.round(p.adi_score * 10) / 10,
      label: p.date.slice(5),
    }));
  }, [data, period, customFrom, customTo]);

  const trendDir  = data?.stats?.trend_direction ?? 'stable';
  const delta     = (data?.stats?.end_score ?? 0) - (data?.stats?.start_score ?? 0);
  const isUp      = delta >= 0;
  const lineColor = trendDir === 'improving' ? '#10b981' : trendDir === 'declining' ? '#ef4444' : '#3b82f6';

  const PERIODS: { key: PeriodKey; label: string }[] = [
    { key: '7',      label: '7k'     },
    { key: '30',     label: '30k'    },
    { key: 'custom', label: 'Maxsus' },
  ];

  const btnStyle = (active: boolean): React.CSSProperties => ({
    appearance:       'none',
    WebkitAppearance: 'none',
    boxSizing:        'border-box',
    margin:            0,
    padding:          '3px 10px',
    borderRadius:      4,
    border:           `1px solid ${active ? lineColor : 'rgba(30,62,180,0.18)'}`,
    background:        active ? `${lineColor}14` : 'transparent',
    color:             active ? lineColor : 'var(--text-muted)',
    fontSize:          8,
    fontWeight:        active ? 700 : 500,
    cursor:            'pointer',
    fontFamily:        "'JetBrains Mono', monospace",
    transition:        'all .15s',
    whiteSpace:       'nowrap',
    display:          'inline-flex',
    alignItems:       'center',
    justifyContent:   'center',
    flexShrink:        0,
    lineHeight:        1,
    minHeight:         0,
    minWidth:          0,
    outline:          'none',
  });

  return (
    <InnerFrame style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ─ Sarlavha qatori ─────────────────────────────────────────────── */}
      <div style={{
        padding:      '10px 12px 6px',
        display:      'flex',
        alignItems:   'center',
        gap:           8,
        flexShrink:    0,
        flexWrap:     'nowrap',
        minWidth:      0,
      }}>
        {/* Sarlavha + delta — chap */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1 }}>
          <span style={{
            fontSize:      13,
            fontWeight:    700,
            color:        'var(--text-primary)',
            fontFamily:   "'Outfit', sans-serif",
            letterSpacing: '0.01em',
            whiteSpace:   'nowrap',
            overflow:     'hidden',
            textOverflow: 'ellipsis',
          }}>
            Umumiy rivojlanish grafigi
          </span>
          {!isLoading && data && (
            <span style={{
              fontSize:   12,
              fontWeight: 700,
              color:      isUp ? '#10b981' : '#ef4444',
              fontFamily: "'JetBrains Mono', monospace",
              flexShrink:  0,
            }}>
              {isUp ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}
            </span>
          )}
        </div>

        {/* Tugmalar — o'ng, siqilmaydi */}
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          {PERIODS.map(p => (
            <button
              key={p.key}
              style={btnStyle(period === p.key)}
              onClick={() => { setPeriod(p.key); setShowCustom(p.key === 'custom'); }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─ Maxsus sana inputlari ────────────────────────────────────────── */}
      {showCustom && (
        <div style={{
          display:    'flex',
          gap:         6,
          alignItems: 'center',
          padding:    '0 12px 6px',
          flexShrink:  0,
        }}>
          <input
            type="date"
            value={customFrom}
            onChange={e => setCustomFrom(e.target.value)}
            style={{
              fontSize:   11,
              padding:    '4px 8px',
              borderRadius: 6,
              border:     '1px solid var(--border)',
              background: 'var(--bg)',
              color:      'var(--text-primary)',
              fontFamily: "'JetBrains Mono', monospace",
              outline:    'none',
              width:      '100%',
            }}
          />
          <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>—</span>
          <input
            type="date"
            value={customTo}
            onChange={e => setCustomTo(e.target.value)}
            style={{
              fontSize:   11,
              padding:    '4px 8px',
              borderRadius: 6,
              border:     '1px solid var(--border)',
              background: 'var(--bg)',
              color:      'var(--text-primary)',
              fontFamily: "'JetBrains Mono', monospace",
              outline:    'none',
              width:      '100%',
            }}
          />
        </div>
      )}

      {/* ─ Grafik ──────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, minHeight: 0, paddingBottom: 6 }}>
        {isLoading ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{
              width:       20,
              height:      20,
              border:      '2px solid var(--border)',
              borderTopColor: lineColor,
              borderRadius: '50%',
              animation:   'tv-spin .65s linear infinite',
            }} />
          </div>
        ) : chartData.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)', fontFamily: "'Outfit', sans-serif" }}>
              Ma'lumot yo'q
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 12, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="tvAdiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={lineColor} stopOpacity={0.20} />
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}
                tickLine={false}
                axisLine={false}
                domain={['auto', 'auto']}
              />
              <RechartsTooltip
                contentStyle={{
                  background:  'var(--surface)',
                  border:      `1px solid ${lineColor}44`,
                  borderRadius: 9,
                  fontSize:    12,
                  fontFamily:  "'JetBrains Mono', monospace",
                  boxShadow:   '0 4px 16px rgba(0,0,0,0.10)',
                  padding:     '8px 12px',
                }}
                labelStyle={{ color: 'var(--text-muted)', marginBottom: 2 }}
                itemStyle={{ color: lineColor, fontWeight: 700 }}
                formatter={(v: number) => [`${v} ball`, 'ADI']}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={lineColor}
                strokeWidth={2}
                fill="url(#tvAdiGrad)"
                dot={false}
                activeDot={{ r: 4, fill: lineColor, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </InnerFrame>
  );
}

// =============================================================================
// SPRING HOOK
// =============================================================================

interface SpringState { value: number; velocity: number; }

function useSpringOffset(active: boolean) {
  const springRef = useRef<SpringState>({ value: 0, velocity: 0 });
  const rafRef    = useRef<number | null>(null);
  const [, setTick] = useState(0);

  const startAnim = useCallback(() => {
    if (rafRef.current !== null) return;
    const step = () => {
      const target    = active ? MAX_OFFSET : 0;
      const s         = springRef.current;
      s.velocity      = s.velocity * 0.78 + (target - s.value) * 0.10;
      s.value        += s.velocity;
      setTick(t => t + 1);
      if (Math.abs(s.velocity) > 0.005 || Math.abs(target - s.value) > 0.005) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        s.value = target; s.velocity = 0;
        rafRef.current = null;
        setTick(t => t + 1);
      }
    };
    rafRef.current = requestAnimationFrame(step);
  }, [active]);

  return { offset: springRef.current.value, startAnim };
}

// =============================================================================
// ANIMATED SECTOR
// =============================================================================

interface SectorProps {
  cx: number; cy: number;
  innerRadius: number; outerRadius: number;
  startAngle: number; endAngle: number;
  fill: string; midAngle: number;
}

function AnimatedSector(props: SectorProps) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, midAngle } = props;
  const { offset, startAnim } = useSpringOffset(true);
  const started = useRef(false);
  if (!started.current) { started.current = true; startAnim(); }

  const R  = Math.PI / 180;
  const dx = Math.cos(-midAngle * R) * offset;
  const dy = Math.sin(-midAngle * R) * offset;

  return (
    <Sector
      cx={cx + dx} cy={cy + dy}
      innerRadius={innerRadius}
      outerRadius={outerRadius + offset * 0.4}
      startAngle={startAngle} endAngle={endAngle}
      fill={fill}
      style={{ outline: 'none', filter: `drop-shadow(0 0 ${(offset / MAX_OFFSET) * 7}px ${fill}99)` }}
    />
  );
}

function InactiveSector(props: SectorProps & { globalActive: boolean }) {
  const { globalActive, cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, midAngle } = props;
  const { offset, startAnim } = useSpringOffset(globalActive);
  const started = useRef(false);
  if (!started.current) { started.current = true; startAnim(); }
  void midAngle;

  return (
    <Sector
      cx={cx} cy={cy}
      innerRadius={innerRadius} outerRadius={outerRadius}
      startAngle={startAngle} endAngle={endAngle}
      fill={fill}
      fillOpacity={globalActive ? 1 - (offset / MAX_OFFSET) * 0.45 : 1}
      style={{ outline: 'none' }}
    />
  );
}

// =============================================================================
// INNER FRAME COMPONENT
// Karta ichidagi ko'k chegarali ramka.
// z-index ko'tarilmagan — tooltip har doim ustida suzadi.
// =============================================================================

interface InnerFrameProps {
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

function InnerFrame({ children, style }: InnerFrameProps) {
  return (
    <div
      style={{
        border:        '1px solid rgba(30, 62, 180, 0.22)',
        borderRadius:   16,
        background:    'transparent',
        position:      'relative',
        zIndex:         0,
        overflow:      'hidden',
        ...style,
      }}
    >
      {children}
    </div>
  );
}


// =============================================================================
// FARM HEALTH PANEL
// =============================================================================

interface FarmHealthPanelProps {
  healthScore:      number | null;
  sickCount:        number;
  quarantineCount:  number;
  attentionCount:   number;
  isLoading:        boolean;
}

function FarmHealthPanel({ healthScore, sickCount, quarantineCount, attentionCount, isLoading }: FarmHealthPanelProps) {
  const scoreColor =
    healthScore == null ? '#9ca3af' :
    healthScore >= 80   ? '#10b981' :
    healthScore >= 60   ? '#f59e0b' :
                          '#ef4444';

  const HEALTH_STATUSES = [
    { key: 'sick',       label: 'Kasal',    color: '#ef4444', count: sickCount        },
    { key: 'quarantine', label: 'Karantin', color: '#f59e0b', count: quarantineCount  },
    { key: 'attention',  label: "E'tibor talab qiladigan", color: '#8b5cf6', count: attentionCount },
  ];

  const Skeleton = () => (
    <div style={{
      width: '60%', height: 12, borderRadius: 4,
      background: 'rgba(30,62,180,0.06)',
      animation: 'tv-pulse 1.4s ease-in-out infinite',
    }} />
  );

  const rowBase: React.CSSProperties = {
    width:          '100%',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '5px 6px',
    borderRadius:    8,
    border:         '1px solid transparent',
    background:     'transparent',
    cursor:         'pointer',
    outline:        'none',
    transition:     'background .15s, border-color .15s',
  };

  return (
    <div className="tv-health-panel" style={{
      height:        '100%',
      display:       'flex',
      flexDirection: 'column',
      padding:       '12px 10px',
      gap:            0,
      overflow:      'auto',
    }}>

      {/* ── Ferma sog'lig'i sarlavha ── */}
      <div style={{
        fontSize: 13, fontWeight: 700, color: 'var(--text-primary)',
        fontFamily: "'Outfit', sans-serif",
        marginBottom: 6,
      }}>
        Ferma sog'lig'i
      </div>

      {/* Ball */}
      {isLoading ? (
        <div style={{
          width: 80, height: 34, borderRadius: 8,
          background: 'rgba(30,62,180,0.06)',
          animation: 'tv-pulse 1.4s ease-in-out infinite',
          marginBottom: 6,
        }} />
      ) : (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 3, marginBottom: 6 }}>
          <span style={{
            fontSize: 76, fontWeight: 800, color: scoreColor,
            fontFamily: "'JetBrains Mono', monospace",
            lineHeight: 1, letterSpacing: '-0.03em',
          }}>
            {healthScore ?? '—'}
          </span>
          <span style={{
            fontSize: 35, fontWeight: 700, color: '#9ca3af',
            fontFamily: "'JetBrains Mono', monospace", lineHeight: 1,
          }}>/</span>
          <span style={{
            fontSize: 35, fontWeight: 700, color: '#10b981',
            fontFamily: "'JetBrains Mono', monospace", lineHeight: 1,
          }}>100</span>
        </div>
      )}

      {/* Kasal / Karantin — button */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, marginBottom: 8 }}>
        {HEALTH_STATUSES.map(({ key, label, color, count }) => (
          <button
            key={key}
            style={rowBase}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = `${color}0d`;
              (e.currentTarget as HTMLButtonElement).style.borderColor = `${color}33`;
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: color, flexShrink: 0,
              }} />
              <span style={{
                fontSize: 12, color: 'var(--text-secondary)',
                fontFamily: "'Outfit', sans-serif", fontWeight: 500,
              }}>{label}</span>
            </div>
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: isLoading ? 'var(--text-muted)' : count > 0 ? color : 'var(--text-muted)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {isLoading ? '—' : `${count} ta`}
            </span>
          </button>
        ))}
      </div>


    </div>
  );
}


// =============================================================================
// NOTICES PANEL — Chap karta, InnerFrame 2 (donut tagida)
// =============================================================================

interface NoticesPanelProps {
  alertStats: AlertStats | null;
  isLoading:  boolean;
}

function NoticesPanel({ alertStats, isLoading }: NoticesPanelProps) {
  const NOTICE_LEVELS = [
    { label: 'Jiddiy',  count: alertStats?.critical_open ?? 0, color: '#DC2626' },
    { label: 'Yuqori',  count: alertStats?.high_open     ?? 0, color: '#F59E0B' },
    { label: "O'rta",   count: alertStats?.medium_open   ?? 0, color: '#3B82F6' },
    { label: 'Oddiy',   count: alertStats?.low_open      ?? 0, color: '#10B981' },
  ];

  const rowBase: React.CSSProperties = {
    width:          '100%',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '4px 6px',
    borderRadius:    8,
    border:         '1px solid transparent',
    background:     'transparent',
    cursor:         'pointer',
    outline:        'none',
    transition:     'background .15s, border-color .15s',
  };

  return (
    <div style={{
      height:        '100%',
      display:       'flex',
      flexDirection: 'column',
      padding:       '10px 10px',
      overflow:      'hidden',
    }}>

      {/* Sarlavha */}
      <div style={{
        fontSize: 13, fontWeight: 700, color: 'var(--text-primary)',
        fontFamily: "'Outfit', sans-serif",
        marginBottom: 6,
      }}>
        Bildirishnomalar
      </div>

      {/* Qatorlar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {NOTICE_LEVELS.map(({ label, count, color }) => (
          <button
            key={label}
            style={rowBase}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background    = `${color}0d`;
              (e.currentTarget as HTMLButtonElement).style.borderColor   = `${color}33`;
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background    = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.borderColor   = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: color, flexShrink: 0,
              }} />
              <span style={{
                fontSize: 12, color: 'var(--text-secondary)',
                fontFamily: "'Outfit', sans-serif", fontWeight: 500,
              }}>{label}</span>
            </div>
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: isLoading ? 'var(--text-muted)' : count > 0 ? color : 'var(--text-muted)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {isLoading ? '—' : `${count} ta`}
            </span>
          </button>
        ))}
      </div>

    </div>
  );
}

// =============================================================================
// PAGE
// =============================================================================

export default function DashboardPage() {
  const isMobile = useIsMobile();

  const [activeIndex, setActiveIndex]   = useState<number | undefined>(undefined);
  const [activeData,  setActiveData]    = useState<DonutEntry | null>(null);
  const leaveTimer                       = useRef<ReturnType<typeof setTimeout> | null>(null);

  const tooltipRef                       = useRef<HTMLDivElement>(null);
  const [tipVisible, setTipVisible]      = useState(false);

  const chartRef   = useRef<HTMLDivElement>(null);
  const chartRect  = useRef<DOMRect | null>(null);

  const { data: overview, isLoading: overviewLoading } = useQuery<OverviewStats>({
    queryKey: ['analytics', 'overview'],
    queryFn:  () => apiFetch<OverviewStats>('/api/v1/analytics/overview'),
    staleTime: 60_000,
  });

  const { data: herd, isLoading: herdLoading } = useQuery<HerdStatistics>({
    queryKey: ['analytics', 'herd', 'statistics'],
    queryFn:  () => apiFetch<HerdStatistics>('/api/v1/analytics/herd/statistics'),
    staleTime: 60_000,
  });

  const { data: healthStats, isLoading: healthLoading } = useQuery<HealthStatistics>({
    queryKey: ['health', 'statistics'],
    queryFn:  () => apiFetch<HealthStatistics>('/api/v1/health/statistics'),
    staleTime: 60_000,
    retry:     false,
  });

  const { data: alertStats, isLoading: alertLoading } = useQuery<AlertStats>({
    queryKey:        ['alert-stats-nav'],
    queryFn:         () => apiFetch<AlertStats>('/api/v1/alerts/stats'),
    refetchInterval:  60_000,
    staleTime:        45_000,
    retry:            false,
  });

  const { data: predSummary, isLoading: predLoading } = useQuery<PredictionSummary>({
    queryKey: ['predictions', 'farm-summary'],
    queryFn:  () => apiFetch<PredictionSummary>('/api/v1/predictions/farm-summary'),
    staleTime: 120_000,
    retry:     false,
  });

  const activeAnimals = overview?.animals?.active ?? herd?.active_animals ?? 0;

  const donutData = useMemo<DonutEntry[]>(
    () =>
      (herd?.species_breakdown ?? [])
        .filter((s) => s.count > 0)
        .map((s) => ({
          species:    s.species,
          label:      SPECIES_LABELS[s.species] ?? s.species,
          value:      s.count,
          percentage: s.percentage,
          color:      SPECIES_COLORS[s.species] ?? '#9ca3af',
        })),
    [herd],
  );

  const isLoading = overviewLoading || herdLoading;

  useEffect(() => {
    const update = () => {
      if (chartRef.current) chartRect.current = chartRef.current.getBoundingClientRect();
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [isLoading]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const tip = tooltipRef.current;
    const r   = chartRect.current;
    if (!tip || !r) return;

    const cx     = r.left + r.width  / 2;
    const cy     = r.top  + r.height / 2;
    const dist   = Math.hypot(e.clientX - cx, e.clientY - cy);
    const innerR = Math.min(r.width, r.height) / 2 * 0.48;

    if (dist < innerR) {
      if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
      leaveTimer.current = setTimeout(() => {
        setActiveIndex(undefined);
        setTipVisible(false);
      }, 250);
      return;
    }

    const angle  = Math.atan2(e.clientY - cy, e.clientX - cx);
    const outerR = Math.min(r.width, r.height) / 2 * 0.80;
    tip.style.left = `${cx + Math.cos(angle) * (outerR + MAX_OFFSET + 70)}px`;
    tip.style.top  = `${cy + Math.sin(angle) * (outerR + MAX_OFFSET + 70)}px`;
  }, []);

  const handleEnter = useCallback((_: unknown, index: number) => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
    setActiveIndex(index);
    setActiveData(donutData[index] ?? null);
    setTipVisible(true);
  }, [donutData]);

  const handleContainerLeave = useCallback(() => {
    leaveTimer.current = setTimeout(() => {
      setActiveIndex(undefined);
      setTipVisible(false);
    }, 250);
  }, []);

  const handleContainerEnter = useCallback(() => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
  }, []);

  const renderActiveShape = useCallback((props: any) => <AnimatedSector {...props} />, []);

  const renderShape = useCallback((props: any) => (
    <InactiveSector {...props} globalActive={activeIndex !== undefined} />
  ), [activeIndex]);

  // ==========================================================================
  // RENDER
  // ==========================================================================

  return (
    <div style={{
      background: 'var(--bg)',
      minHeight:  'calc(100vh - 56px)',
      padding:    isMobile ? '24px 12px 34px' : '30px 24px 42px',
      overflow:   'hidden',
    }}>

      <style>{`
        .tv-donut path:focus,
        .tv-donut svg:focus,
        .tv-donut path { outline: none !important; }
        @keyframes tv-pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
        .tv-health-panel::-webkit-scrollbar { width: 3px; }
        .tv-health-panel::-webkit-scrollbar-track { background: transparent; }
        .tv-health-panel::-webkit-scrollbar-thumb { background: transparent; border-radius: 99px; }
        .tv-health-panel:hover::-webkit-scrollbar-thumb { background: rgba(30,62,180,0.15); }
      `}</style>

      <div style={{ display: 'flex', gap: 24, alignItems: 'stretch' }}>

        {/* ── Chap karta ───────────────────────────────────────────────── */}
        <div style={{
          flex:          '0 0 420px',
          maxWidth:       480,
          marginLeft:     32,
          height:         isMobile ? 'auto' : 'calc(100vh - 56px - 48px)',
          minHeight:      480,
          background:    '#fff',
          border:        '1px solid #e5e7eb',
          borderRadius:   24,
          boxShadow:     '0 1px 3px rgba(0,0,0,0.06)',
          display:       'flex',
          flexDirection: 'column',
          padding:        12,
          gap:            10,
          position:      'relative',
          zIndex:         0,
        }}>
          {isLoading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* ═══════════════════════════════════════════════════════
                  ICHKI RAMKA 1 — Donut diagramma
              ═══════════════════════════════════════════════════════ */}
              <InnerFrame style={{ flexShrink: 0 }}>
                <div
                  className="tv-donut"
                  ref={chartRef}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleContainerLeave}
                  onMouseEnter={handleContainerEnter}
                  style={{ position: 'relative', height: isMobile ? 285 : 365, marginTop: -15 }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={donutData}
                        dataKey="value"
                        nameKey="label"
                        cx="50%"
                        cy="50%"
                        innerRadius="48%"
                        outerRadius="80%"
                        paddingAngle={2}
                        stroke="none"
                        strokeWidth={0}
                        activeIndex={activeIndex}
                        activeShape={renderActiveShape}
                        shape={renderShape as any}
                        onMouseEnter={handleEnter}
                        isAnimationActive={true}
                        animationBegin={0}
                        animationDuration={900}
                        animationEasing="ease-out"
                        style={{ outline: 'none', cursor: 'default' }}
                      >
                        {donutData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} style={{ outline: 'none' }} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>

                  {/* Markaz */}
                  <div style={{
                    position:       'absolute',
                    inset:           0,
                    display:        'flex',
                    flexDirection:  'column',
                    alignItems:     'center',
                    justifyContent: 'center',
                    pointerEvents:  'none',
                  }}>
                    <span style={{
                      fontSize:      40,
                      fontWeight:    800,
                      color:         '#111827',
                      lineHeight:    1,
                      fontFamily:    "'JetBrains Mono', monospace",
                      letterSpacing: '-0.02em',
                    }}>
                      {activeAnimals > 0 ? activeAnimals : '—'}
                    </span>
                    <span style={{ marginTop: 8, fontSize: 13, fontWeight: 500, color: '#6b7280' }}>
                      Jami jonivorlar soni
                    </span>
                  </div>
                </div>
              </InnerFrame>

              {/* ═══════════════════════════════════════════════════════
                  ICHKI RAMKA 2 — Bildirishnomalar
              ═══════════════════════════════════════════════════════ */}
              <InnerFrame style={{ flex: 1, minHeight: 80 }}>
                <NoticesPanel
                  alertStats={alertStats ?? null}
                  isLoading={alertLoading}
                />
              </InnerFrame>
            </>
          )}
        </div>

        {/* ── O'ng tomon: 2 ta karta tagma-tag ────────────────────────── */}
        <div style={{
          flex:          1,
          display:       'flex',
          flexDirection: 'column',
          gap:            10,
          marginRight:    32,
          height:        isMobile ? 'auto' : 'calc(100vh - 56px - 48px)',
          minHeight:      480,
        }}>

          {/* ── O'ng karta 1 ──────────────────────────────────────────── */}
          <div style={{
            flex:          1,
            background:   '#fff',
            border:       '1px solid rgba(30, 62, 180, 0.22)',
            borderRadius:  24,
            boxShadow:    '0 1px 3px rgba(0,0,0,0.06)',
            position:     'relative',
            zIndex:        0,
            overflow:     'hidden',
            display:      'flex',
            flexDirection:'column',
            padding:       12,
            gap:           10,
          }}>
            {/* ═══════════════════════════════════════════════════════
                ICHKI RAMKALAR — yonma-yon
            ═══════════════════════════════════════════════════════ */}
            <div style={{ flex: 1, display: 'flex', gap: 10, minHeight: 0 }}>
              {/* Chap 30% — Ferma sog'lig'i */}
              <InnerFrame style={{ flex: '0 0 30%' }}>
                <FarmHealthPanel
                  healthScore={healthStats?.health_score ?? null}
                  sickCount={healthStats?.sick_count ?? 0}
                  quarantineCount={healthStats?.quarantine_count ?? 0}
                  attentionCount={(predSummary?.high_count ?? 0) + (predSummary?.critical_count ?? 0)}
                  isLoading={healthLoading || overviewLoading || predLoading}
                />
              </InnerFrame>

              {/* O'ng 70% — Umumiy rivojlanish grafigi */}
              <TradingChart />
            </div>
          </div>

          {/* ── O'ng karta 2 ──────────────────────────────────────────── */}
          <div style={{
            flex:          1,
            background:   '#fff',
            border:       '1px solid rgba(30, 62, 180, 0.22)',
            borderRadius:  24,
            boxShadow:    '0 1px 3px rgba(0,0,0,0.06)',
            position:     'relative',
            zIndex:        0,
            overflow:     'hidden',
            display:      'flex',
            flexDirection:'column',
            padding:       12,
            gap:           10,
          }}>
            {/* ═══════════════════════════════════════════════════════
                ICHKI RAMKA 1 — Keyingi buyruqda to'ldiriladi
            ═══════════════════════════════════════════════════════ */}
            <InnerFrame style={{ flex: 1 }} />
          </div>

        </div>
      </div>

      {/* ── Floating tooltip ─────────────────────────────────────────────
          position: fixed + z-index: 9999
          Barcha qatlamlar ustida erkin suzadi — ramkalar, karta hech narsa
          to'sqinlik qilmaydi.
      ──────────────────────────────────────────────────────────────────── */}
      <div
        ref={tooltipRef}
        style={{
          position:      'fixed',
          left:           0,
          top:            0,
          transform:     'translate(-50%, -50%)',
          pointerEvents: 'none',
          zIndex:         9999,
          opacity:        tipVisible ? 1 : 0,
          transition:    'opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {activeData && (
          <div style={{
            background:   '#fff',
            border:       `1.5px solid ${activeData.color}44`,
            borderRadius:  12,
            padding:      '10px 14px',
            boxShadow:    `0 4px 20px rgba(0,0,0,0.13), 0 0 0 1px ${activeData.color}22`,
            minWidth:      130,
            whiteSpace:   'nowrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: activeData.color, flexShrink: 0,
                boxShadow: `0 0 6px ${activeData.color}88`,
              }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>
                {activeData.label}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 14 }}>
              <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500 }}>Soni</span>
              <span style={{ fontSize: 15, fontWeight: 800, color: '#111827', fontFamily: "'JetBrains Mono', monospace" }}>
                {activeData.value} ta
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 14, marginTop: 3 }}>
              <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500 }}>Ulushi</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: activeData.color, fontFamily: "'JetBrains Mono', monospace" }}>
                {activeData.percentage}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}