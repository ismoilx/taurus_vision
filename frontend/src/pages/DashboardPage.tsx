/**
 * Taurus Vision — DashboardPage
 *
 * ENDPOINTLAR:
 *   GET /api/v1/analytics/herd/statistics  → jonivorlar turi taqsimoti
 *   GET /api/v1/analytics/overview         → jami aktiv jonivorlar soni
 */

import { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Sector } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { useIsMobile } from '../hooks/useResponsive';

// =============================================================================
// TYPES
// =============================================================================

interface OverviewStats {
  animals: { total: number; active: number };
}

interface SpeciesBreakdown {
  species: string;
  count: number;
  percentage: number;
  avg_weight_kg: number | null;
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
// PAGE
// =============================================================================

export default function DashboardPage() {
  const isMobile = useIsMobile();

  // ── Hover state ──────────────────────────────────────────────────────────
  const [activeIndex, setActiveIndex]   = useState<number | undefined>(undefined);
  const [activeData,  setActiveData]    = useState<DonutEntry | null>(null);
  const leaveTimer                       = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Tooltip DOM ref — pozitsiya to'g'ridan DOM'ga yoziladi ──────────────
  const tooltipRef                       = useRef<HTMLDivElement>(null);
  const [tipVisible, setTipVisible]      = useState(false);

  // ── Chart o'lchami ────────────────────────────────────────────────────────
  const chartRef   = useRef<HTMLDivElement>(null);
  const chartRect  = useRef<DOMRect | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────
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

  // Chart rect ni kuzatish
  useEffect(() => {
    const update = () => {
      if (chartRef.current) chartRect.current = chartRef.current.getBoundingClientRect();
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [isLoading]);

  // ── Mouse move — DOM'ga to'g'ridan yoziladi, inner radius tekshiriladi ──
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const tip = tooltipRef.current;
    const r   = chartRect.current;
    if (!tip || !r) return;

    const cx     = r.left + r.width  / 2;
    const cy     = r.top  + r.height / 2;
    const dist   = Math.hypot(e.clientX - cx, e.clientY - cy);
    const innerR = Math.min(r.width, r.height) / 2 * 0.46;

    // Halqa ichiga kirganda — 500ms sekin yo'qolish
    if (dist < innerR) {
      if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
      leaveTimer.current = setTimeout(() => {
        setActiveIndex(undefined);
        setTipVisible(false);
      }, 250);
      return;
    }

    // Tooltip pozitsiyasini yangilash
    const angle  = Math.atan2(e.clientY - cy, e.clientX - cx);
    const outerR = Math.min(r.width, r.height) / 2 * 0.74;
    tip.style.left = `${cx + Math.cos(angle) * (outerR + MAX_OFFSET + 70)}px`;
    tip.style.top  = `${cy + Math.sin(angle) * (outerR + MAX_OFFSET + 70)}px`;
  }, []);

  // ── Segment enter ────────────────────────────────────────────────────────
  const handleEnter = useCallback((_: unknown, index: number) => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
    setActiveIndex(index);
    setActiveData(donutData[index] ?? null);
    setTipVisible(true);
  }, [donutData]);

  // ── Container leave — 500ms, silliq yo'qolish ────────────────────────────
  const handleContainerLeave = useCallback(() => {
    leaveTimer.current = setTimeout(() => {
      setActiveIndex(undefined);
      setTipVisible(false);
    }, 250);
  }, []);

  const handleContainerEnter = useCallback(() => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
  }, []);

  // ── Shape renderers ──────────────────────────────────────────────────────
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
      padding:    isMobile ? '14px 12px 24px' : '20px 24px 32px',
      overflow:   'hidden',
    }}>

      <style>{`
        .tv-donut path:focus,
        .tv-donut svg:focus,
        .tv-donut path { outline: none !important; }
      `}</style>

      <div style={{ display: 'flex', gap: 24 }}>

        {/* ── Chap karta ───────────────────────────────────────────────── */}
        <div style={{
          flex:          '0 0 420px',
          maxWidth:       480,
          marginLeft:     12,
          height:         isMobile ? 'auto' : 'calc(100vh - 56px - 48px)',
          minHeight:      480,
          background:    '#fff',
          border:        '1px solid #e5e7eb',
          borderRadius:   24,
          boxShadow:     '0 1px 3px rgba(0,0,0,0.06)',
          display:       'flex',
          flexDirection: 'column',
        }}>
          {isLoading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* ── Yuqori qism: donut ── */}
              <div
                className="tv-donut"
                ref={chartRef}
                onMouseMove={handleMouseMove}
                onMouseLeave={handleContainerLeave}
                onMouseEnter={handleContainerEnter}
                style={{ position: 'relative', height: isMobile ? 280 : 340, flexShrink: 0 }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      innerRadius="46%"
                      outerRadius="74%"
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

              {/* ── Pastki qism: keyingi buyruqda ── */}
              <div style={{ flex: 1 }} />
            </>
          )}
        </div>

        {/* ── O'ng tomon: keyingi buyruqda ─────────────────────────────── */}
        <div style={{ flex: 1 }} />
      </div>

      {/* ── Floating tooltip — position:fixed, DOM ref orqali boshqariladi ── */}
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