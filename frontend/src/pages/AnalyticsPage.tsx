/**
 * AnalyticsPage — Sprint 21-24
 *
 * 5 tab, 12 endpoint, to'liq professional analytics sahifasi.
 *
 * TAB 1 — Umumiy:     Herd statistikasi KPIlar, ADI taqsimoti, Avtomatik insights
 * TAB 2 — Trendlar:   ADI trendi, O'sish regressiyasi, Xatti-harakat komponentlari
 * TAB 3 — Taqqoslash: Davr-davr taqqoslash, Ko'p jonivor taqqoslash
 * TAB 4 — Naqshlar:   Deteksiya soatlik/kunlik, Top jonivorlar, Kamera samaradorligi
 * TAB 5 — Sog'liq:    Xavf balli, Vazn taqsimoti, Alertlar ro'yxati
 *
 * ENDPOINTLAR:
 *   GET /api/v1/analytics/herd/statistics         → Tab 1
 *   GET /api/v1/analytics/insights                → Tab 1
 *   GET /api/v1/analytics/trends/adi              → Tab 2
 *   GET /api/v1/analytics/trends/growth           → Tab 2
 *   GET /api/v1/analytics/trends/behavior         → Tab 2
 *   GET /api/v1/analytics/trends/weight           → Tab 2 & 5
 *   GET /api/v1/analytics/compare/periods         → Tab 3
 *   GET /api/v1/analytics/compare/animals         → Tab 3
 *   GET /api/v1/analytics/patterns/detection      → Tab 4
 *   GET /api/v1/analytics/cameras/performance     → Tab 4
 *   GET /api/v1/analytics/health/metrics          → Tab 5
 *   GET /api/v1/analytics/overview                → Barcha tab header
 */

import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  LayoutDashboard, TrendingUp, GitCompare, Activity,
  Heart, RefreshCw, AlertTriangle, CheckCircle, Info,
  Camera, Award, Zap, ArrowUpRight, ArrowDownRight,
  Minus, ChevronRight, Lightbulb, BarChart3,
  Scale, Users, Eye,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES — Sprint 21-24 API javoblari
// =============================================================================

interface HerdKPIs {
  overall_health_score: number;
  detection_coverage_pct: number;
  avg_daily_detections: number;
  animals_needing_attention: number;
  animals_missing_7d: number;
  avg_weight_kg: number | null;
  total_weight_gain_kg: number | null;
  feed_efficiency_index: number | null;
}

interface HerdStatistics {
  timestamp: string;
  total_animals: number;
  active_animals: number;
  species_breakdown: { species: string; count: number; percentage: number; avg_weight_kg: number | null }[];
  adi_distribution: { healthy: number; average: number; warning: number; critical: number; no_data: number; healthy_pct: number; critical_pct: number };
  weight_distribution: { range_label: string; count: number; percentage: number }[];
  age_distribution: { range_label: string; count: number; percentage: number }[];
  kpis: HerdKPIs;
}

interface InsightItem {
  insight_id: string;
  category: string;
  severity: 'info' | 'warning' | 'critical' | 'positive';
  title: string;
  description: string;
  affected_animals: string[];
  metric_value: number | null;
  metric_label: string | null;
  action_required: boolean;
  generated_at: string;
}

interface InsightsResponse {
  generated_at: string;
  insights: InsightItem[];
  summary: { total: number; critical: number; warning: number; positive: number; info: number; actions_required: number };
  analysis_period_days: number;
  animals_analyzed: number;
}

interface ADITrendPoint {
  date: string;
  adi_score: number;
  category: string;
  activity_score: number | null;
  feeding_score: number | null;
  drinking_score: number | null;
  movement_score: number | null;
  growth_score: number | null;
  social_score: number | null;
  sensor_score: number | null;
  veterinary_score: number | null;
}

interface ADITrends {
  animal_id: number | null;
  animal_tag: string | null;
  period_days: number;
  data: ADITrendPoint[];
  stats: { period_days: number; average_adi: number; min_adi: number; max_adi: number; trend_direction: string; trend_delta: number; days_healthy: number; days_critical: number };
}

interface GrowthPoint {
  date: string;
  average_weight_kg: number;
  measurement_count: number;
  animal_count: number;
}

interface GrowthTrends {
  animal_id: number | null;
  period_days: number;
  data: GrowthPoint[];
  regression: { slope_kg_per_day: number; slope_kg_per_week: number; slope_kg_per_month: number; r_squared: number; projected_weight_30d: number; data_points_used: number } | null;
  summary: { first_weight_kg?: number; last_weight_kg?: number; total_gain_kg?: number };
}

interface BehaviorPoint {
  date: string;
  activity_score: number | null;
  feeding_score: number | null;
  drinking_score: number | null;
  movement_score: number | null;
  growth_score: number | null;
  social_score: number | null;
  composite_behavior: number | null;
}

interface BehaviorTrends {
  period_days: number;
  data: BehaviorPoint[];
  component_summaries: { component: string; average: number; trend: string; delta: number }[];
  weakest_component: string | null;
  strongest_component: string | null;
}

interface PeriodMetrics {
  period_label: string;
  date_from: string;
  date_to: string;
  total_detections: number;
  avg_detections_per_day: number;
  avg_confidence: number | null;
  avg_adi: number | null;
  animals_in_healthy: number;
  animals_in_critical: number;
  avg_weight_kg: number | null;
  total_alerts: number;
  critical_alerts: number;
}

interface PeriodDelta {
  metric: string;
  current_value: number | null;
  previous_value: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
  direction: 'up' | 'down' | 'unchanged';
  is_positive_change: boolean;
}

interface PeriodComparison {
  current_period: PeriodMetrics;
  previous_period: PeriodMetrics;
  deltas: PeriodDelta[];
  overall_assessment: 'improved' | 'declined' | 'stable';
  key_changes: string[];
}

interface AnimalMetric {
  animal_id: number;
  tag_id: string;
  species: string;
  status: string;
  average_adi: number | null;
  latest_adi: number | null;
  adi_trend: string | null;
  latest_weight_kg: number | null;
  weight_change_pct: number | null;
  detections_period: number;
  detection_rate_per_day: number;
  avg_activity_score: number | null;
  avg_feeding_score: number | null;
  risk_level: string;
  active_alerts_count: number;
}

interface AnimalComparison {
  period_days: number;
  animals: AnimalMetric[];
  best_adi_animal: string | null;
  worst_adi_animal: string | null;
  highest_weight_animal: string | null;
  most_active_animal: string | null;
}

interface DetectionPatterns {
  date_range: { from: string; to: string; days: number };
  detections_by_hour: number[];
  detections_by_day: { date: string; count: number }[];
  detections_by_camera: { camera_id: string; detections: number; average_confidence: number }[];
  top_detected_animals: { tag_id: string; species: string; detections: number }[];
  statistics: { total_detections: number; detection_rate_per_hour: number; peak_hour: number | null };
}

interface CameraPerf {
  cameras: { camera_id: string; status: string; total_detections: number; average_confidence: number; fps: number; uptime_percentage: number; errors: number }[];
  summary: { total_cameras: number; running_cameras: number; total_detections: number; average_fps: number };
}

interface HealthMetrics {
  animals_by_status: Record<string, number>;
  weight_distribution: Record<string, number>;
  alerts: { type: string; severity: string; animal_tag: string; message: string; loss_percentage?: number }[];
  alert_summary: { total: number; critical: number; warning: number };
  risk_score: number;
}

// =============================================================================
// DESIGN CONSTANTS
// =============================================================================

const TAB_LIST = [
  { id: 'overview',    label: 'Umumiy',      icon: LayoutDashboard },
  { id: 'trends',      label: 'Trendlar',    icon: TrendingUp      },
  { id: 'compare',     label: 'Taqqoslash',  icon: GitCompare      },
  { id: 'patterns',    label: 'Naqshlar',    icon: Activity        },
  { id: 'health',      label: "Sog'liq",     icon: Heart           },
] as const;
type TabId = typeof TAB_LIST[number]['id'];

const ADI_COLORS = { healthy: '#10b981', average: '#3b82f6', warning: '#f59e0b', critical: '#ef4444', no_data: '#d1d5db' };
const CHART_PALETTE = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#84cc16'];

const SEVERITY_CFG = {
  critical: { bg: 'bg-red-50',     border: 'border-red-200',    icon: 'text-red-500',    badge: 'bg-red-100 text-red-700'    },
  warning:  { bg: 'bg-amber-50',   border: 'border-amber-200',  icon: 'text-amber-500',  badge: 'bg-amber-100 text-amber-700' },
  positive: { bg: 'bg-emerald-50', border: 'border-emerald-200',icon: 'text-emerald-500',badge: 'bg-emerald-100 text-emerald-700' },
  info:     { bg: 'bg-blue-50',    border: 'border-blue-200',   icon: 'text-blue-500',   badge: 'bg-blue-100 text-blue-700'   },
};

// =============================================================================
// SHARED MICRO-COMPONENTS
// =============================================================================

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-2xl shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function CardHeader({ icon: Icon, title, color = 'text-blue-500', action }: {
  icon: React.ElementType; title: string; color?: string; action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      </div>
      {action}
    </div>
  );
}

function SegmentedControl({ options, value, onChange }: {
  options: { label: string; value: number | string }[];
  value: number | string;
  onChange: (v: any) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 bg-gray-100 rounded-xl p-1">
      {options.map(o => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
            value === o.value
              ? 'bg-white shadow-sm text-blue-600 font-semibold'
              : 'text-gray-500 hover:text-gray-700'
          }`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function KpiCard({ label, value, sub, color = 'text-gray-900', bg = 'bg-white', icon: Icon, iconColor = 'text-gray-400' }: {
  label: string; value: string | number; sub?: string;
  color?: string; bg?: string; icon?: React.ElementType; iconColor?: string;
}) {
  return (
    <div className={`${bg} border border-gray-200 rounded-2xl p-4 flex flex-col gap-1`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">{label}</span>
        {Icon && <Icon className={`w-4 h-4 ${iconColor}`} />}
      </div>
      <span className={`text-2xl font-bold tabular-nums ${color}`}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="h-48 flex flex-col items-center justify-center text-gray-400 gap-2">
      <BarChart3 className="w-8 h-8 opacity-30" />
      <span className="text-sm">{text}</span>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="h-48 flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function TrendBadge({ direction, delta }: { direction: string; delta?: number }) {
  if (direction === 'improving') return (
    <span className="flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-lg font-medium">
      <ArrowUpRight className="w-3 h-3" />
      {delta ? `+${Math.abs(delta).toFixed(1)}` : "O'smoqda"}
    </span>
  );
  if (direction === 'declining') return (
    <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-lg font-medium">
      <ArrowDownRight className="w-3 h-3" />
      {delta ? `-${Math.abs(delta).toFixed(1)}` : "Tushmoqda"}
    </span>
  );
  return (
    <span className="flex items-center gap-1 text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-lg font-medium">
      <Minus className="w-3 h-3" /> Barqaror
    </span>
  );
}

// Custom recharts tooltips
function SimpleTooltip({ active, payload, label, unit = '' }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-lg text-xs space-y-1">
      <p className="font-semibold text-gray-700">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <b>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}{unit}</b>
        </p>
      ))}
    </div>
  );
}

// =============================================================================
// TAB 1 — UMUMIY (Overview)
// =============================================================================

function OverviewTab() {
  const { data: herd, isLoading: herdLoading } = useQuery({
    queryKey: ['analytics', 'herd-statistics'],
    queryFn: () => apiFetch<HerdStatistics>('/api/v1/analytics/herd/statistics'),
  });

  const [insightDays, setInsightDays] = useState(14);
  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ['analytics', 'insights', insightDays],
    queryFn: () => apiFetch<InsightsResponse>(`/api/v1/analytics/insights?days=${insightDays}`),
  });

  const adiPieData = herd ? [
    { name: 'Healthy',  value: herd.adi_distribution.healthy,  color: ADI_COLORS.healthy  },
    { name: 'Average',  value: herd.adi_distribution.average,  color: ADI_COLORS.average  },
    { name: 'Warning',  value: herd.adi_distribution.warning,  color: ADI_COLORS.warning  },
    { name: 'Critical', value: herd.adi_distribution.critical, color: ADI_COLORS.critical },
    { name: "Ma'lumot yo'q", value: herd.adi_distribution.no_data, color: ADI_COLORS.no_data },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="space-y-6">
      {/* KPI cards row */}
      {herdLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-2xl h-24 animate-pulse" />
          ))}
        </div>
      ) : herd ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
          <KpiCard label="Aktiv jonivorlar" value={herd.active_animals}
            sub={`Jami: ${herd.total_animals}`} icon={Users} iconColor="text-blue-400" />
          <KpiCard label="Sog'liq balli"
            value={`${herd.kpis.overall_health_score.toFixed(1)}`}
            sub="ADI o'rtacha"
            color={herd.kpis.overall_health_score >= 75 ? 'text-emerald-600' : herd.kpis.overall_health_score >= 50 ? 'text-amber-600' : 'text-red-600'}
            icon={Heart} iconColor="text-rose-400" />
          <KpiCard label="Qamrov"
            value={`${herd.kpis.detection_coverage_pct.toFixed(0)}%`}
            sub="7 kunlik kamera"
            color={herd.kpis.detection_coverage_pct >= 90 ? 'text-emerald-600' : 'text-amber-600'}
            icon={Eye} iconColor="text-violet-400" />
          <KpiCard label="Kunlik deteksiya"
            value={herd.kpis.avg_daily_detections.toFixed(0)}
            sub="O'rtacha"
            icon={Activity} iconColor="text-indigo-400" />
          <KpiCard label="Diqqat kerak"
            value={herd.kpis.animals_needing_attention}
            sub="warning/critical"
            color={herd.kpis.animals_needing_attention > 0 ? 'text-amber-600' : 'text-gray-900'}
            icon={AlertTriangle} iconColor="text-amber-400" />
          <KpiCard label="Ko'rinmagan"
            value={herd.kpis.animals_missing_7d}
            sub="7+ kun"
            color={herd.kpis.animals_missing_7d > 0 ? 'text-red-600' : 'text-gray-900'}
            icon={Eye} iconColor="text-red-400" />
          <KpiCard label="O'rt. vazn"
            value={herd.kpis.avg_weight_kg ? `${herd.kpis.avg_weight_kg.toFixed(1)} kg` : '—'}
            sub="Aktiv jonivorlar"
            icon={Scale} iconColor="text-sky-400" />
        </div>
      ) : null}

      {/* ADI distribution + Species breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* ADI donut */}
        <Card className="p-5">
          <CardHeader icon={Activity} title="ADI Taqsimoti" color="text-emerald-500" />
          {herdLoading ? <LoadingState /> : (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={adiPieData} cx="50%" cy="50%" innerRadius={48} outerRadius={72}
                    paddingAngle={3} dataKey="value">
                    {adiPieData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [`${v} jonivor`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {adiPieData.map(item => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: item.color }} />
                    <span className="text-xs text-gray-600">{item.name}</span>
                    <span className="text-xs font-semibold text-gray-800 ml-auto">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        {/* Weight distribution */}
        <Card className="p-5">
          <CardHeader icon={Scale} title="Vazn Taqsimoti" color="text-sky-500" />
          {herdLoading ? <LoadingState /> : herd?.weight_distribution.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={herd.weight_distribution} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="range_label" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <Tooltip content={<SimpleTooltip unit=" jonivor" />} cursor={{ fill: '#f1f5f9' }} />
                <Bar dataKey="count" name="Soni" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState text="Vazn ma'lumoti yo'q" />}
        </Card>

        {/* Species breakdown */}
        <Card className="p-5">
          <CardHeader icon={Users} title="Tur bo'yicha" color="text-violet-500" />
          {herdLoading ? <LoadingState /> : herd?.species_breakdown.length ? (
            <div className="space-y-3 mt-1">
              {herd.species_breakdown.map((sp, i) => (
                <div key={sp.species} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-gray-700 capitalize">{sp.species}</span>
                    <span className="text-gray-500">{sp.count} ({sp.percentage}%)</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${sp.percentage}%`, background: CHART_PALETTE[i % CHART_PALETTE.length] }} />
                  </div>
                  {sp.avg_weight_kg && (
                    <p className="text-xs text-gray-400">O'rt. vazn: {sp.avg_weight_kg.toFixed(1)} kg</p>
                  )}
                </div>
              ))}
            </div>
          ) : <EmptyState text="Ma'lumot yo'q" />}
        </Card>
      </div>

      {/* Automated Insights */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-800">Avtomatik Tushunchalar</h3>
            {insights && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-lg font-medium">
                {insights.summary.total} ta
              </span>
            )}
          </div>
          <SegmentedControl
            options={[{ label: '7k', value: 7 }, { label: '14k', value: 14 }, { label: '30k', value: 30 }]}
            value={insightDays}
            onChange={setInsightDays}
          />
        </div>

        {insightsLoading ? <LoadingState /> : insights?.insights.length ? (
          <>
            {/* Summary row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Kritik',       val: insights.summary.critical, color: 'text-red-600',     bg: 'bg-red-50'     },
                { label: 'Ogohlantirish', val: insights.summary.warning,  color: 'text-amber-600',  bg: 'bg-amber-50'   },
                { label: 'Ijobiy',        val: insights.summary.positive, color: 'text-emerald-600', bg: 'bg-emerald-50' },
                { label: 'Harakatlar',    val: insights.summary.actions_required, color: 'text-violet-600', bg: 'bg-violet-50' },
              ].map(({ label, val, color, bg }) => (
                <div key={label} className={`${bg} rounded-xl p-3 text-center`}>
                  <div className={`text-xl font-bold ${color}`}>{val}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            {/* Insight cards */}
            <div className="space-y-3">
              {insights.insights.map(item => {
                const cfg = SEVERITY_CFG[item.severity] ?? SEVERITY_CFG.info;
                return (
                  <div key={item.insight_id}
                    className={`${cfg.bg} ${cfg.border} border rounded-xl p-4`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 flex-1">
                        {item.severity === 'critical' ? <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.icon}`} /> :
                         item.severity === 'warning'  ? <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.icon}`} /> :
                         item.severity === 'positive' ? <CheckCircle   className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.icon}`} /> :
                                                         <Info          className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.icon}`} />}
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-gray-800">{item.title}</span>
                            {item.action_required && (
                              <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                                Harakat kerak
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-600 mt-1 leading-relaxed">{item.description}</p>
                          {item.affected_animals.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {item.affected_animals.slice(0, 6).map(tag => (
                                <span key={tag} className="text-xs bg-white/70 border border-gray-200 rounded px-1.5 py-0.5 font-mono text-gray-600">
                                  {tag}
                                </span>
                              ))}
                              {item.affected_animals.length > 6 && (
                                <span className="text-xs text-gray-400">+{item.affected_animals.length - 6} ta</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      {item.metric_value !== null && (
                        <div className="text-right shrink-0">
                          <div className={`text-lg font-bold ${cfg.icon}`}>{item.metric_value.toFixed(1)}</div>
                          {item.metric_label && <div className="text-xs text-gray-400">{item.metric_label}</div>}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : <EmptyState text="Insight ma'lumoti yo'q" />}
      </Card>
    </div>
  );
}

// =============================================================================
// TAB 2 — TRENDLAR
// =============================================================================

function TrendsTab() {
  const [trendType, setTrendType] = useState<'adi' | 'growth' | 'behavior'>('adi');
  const [days, setDays] = useState(30);
  const [showComponents, setShowComponents] = useState(false);

  const { data: adiData, isLoading: adiLoading } = useQuery({
    queryKey: ['analytics', 'adi-trend', days],
    queryFn: () => apiFetch<ADITrends>(`/api/v1/analytics/trends/adi?days=${days}`),
    enabled: trendType === 'adi',
  });

  const { data: growthData, isLoading: growthLoading } = useQuery({
    queryKey: ['analytics', 'growth-trend', days],
    queryFn: () => apiFetch<GrowthTrends>(`/api/v1/analytics/trends/growth?days=${Math.max(days, 14)}`),
    enabled: trendType === 'growth',
  });

  const { data: behavData, isLoading: behavLoading } = useQuery({
    queryKey: ['analytics', 'behavior-trend', days],
    queryFn: () => apiFetch<BehaviorTrends>(`/api/v1/analytics/trends/behavior?days=${days}`),
    enabled: trendType === 'behavior',
  });

  const isLoading = adiLoading || growthLoading || behavLoading;

  const adiChartData = useMemo(() =>
    (adiData?.data ?? []).map(p => ({
      ...p,
      date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    })),
    [adiData]
  );

  const growthChartData = useMemo(() =>
    (growthData?.data ?? []).map(p => ({
      ...p,
      date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    })),
    [growthData]
  );

  const behavChartData = useMemo(() =>
    (behavData?.data ?? []).map(p => ({
      ...p,
      date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    })),
    [behavData]
  );

  const radarData = useMemo(() =>
    (behavData?.component_summaries ?? []).map(c => ({
      component: c.component.charAt(0).toUpperCase() + c.component.slice(1),
      value: c.average,
      fullMark: 100,
    })),
    [behavData]
  );

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {([
            { id: 'adi',      label: 'ADI Trend'    },
            { id: 'growth',   label: "O'sish"        },
            { id: 'behavior', label: 'Xatti-harakat' },
          ] as const).map(t => (
            <button key={t.id} onClick={() => setTrendType(t.id)}
              className={`px-4 py-2 text-xs font-medium rounded-lg transition-all ${
                trendType === t.id ? 'bg-white shadow-sm text-blue-600 font-semibold' : 'text-gray-500 hover:text-gray-700'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
        <SegmentedControl
          options={[
            { label: '14k', value: 14 },
            { label: '30k', value: 30 },
            { label: '90k', value: 90 },
            { label: '180k', value: 180 },
          ]}
          value={days}
          onChange={setDays}
        />
      </div>

      {/* ADI TREND */}
      {trendType === 'adi' && (
        <div className="space-y-5">
          {/* Stats row */}
          {adiData?.stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <KpiCard label="O'rtacha ADI" value={adiData.stats.average_adi.toFixed(1)}
                color="text-blue-600" icon={Activity} iconColor="text-blue-400" />
              <KpiCard label="Min / Maks"
                value={`${adiData.stats.min_adi.toFixed(0)} / ${adiData.stats.max_adi.toFixed(0)}`}
                icon={TrendingUp} iconColor="text-gray-400" />
              <KpiCard label="Healthy kunlar" value={`${adiData.stats.days_healthy} kun`}
                color="text-emerald-600" icon={CheckCircle} iconColor="text-emerald-400" />
              <KpiCard label="Trend"
                value={adiData.stats.trend_direction === 'improving' ? "O'smoqda" :
                       adiData.stats.trend_direction === 'declining' ? "Tushmoqda" : "Barqaror"}
                color={adiData.stats.trend_direction === 'improving' ? 'text-emerald-600' :
                       adiData.stats.trend_direction === 'declining' ? 'text-red-600' : 'text-gray-600'}
                sub={adiData.stats.trend_delta >= 0 ? `+${adiData.stats.trend_delta.toFixed(1)} ball` : `${adiData.stats.trend_delta.toFixed(1)} ball`}
                icon={adiData.stats.trend_direction === 'improving' ? ArrowUpRight : adiData.stats.trend_direction === 'declining' ? ArrowDownRight : Minus}
                iconColor={adiData.stats.trend_direction === 'improving' ? 'text-emerald-500' : 'text-red-500'} />
            </div>
          )}

          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <CardHeader icon={TrendingUp} title="ADI Ball Trendi (Poda o'rtacha)" color="text-blue-500" />
              <button onClick={() => setShowComponents(!showComponents)}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium">
                {showComponents ? 'Sodda' : 'Komponentlar'}
              </button>
            </div>

            {isLoading ? <LoadingState /> : adiChartData.length === 0 ? <EmptyState text="ADI ma'lumoti yo'q" /> : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={adiChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    {[
                      { id: 'adiGrad', color: '#3b82f6' },
                      { id: 'actGrad', color: '#10b981' },
                      { id: 'feedGrad',color: '#f59e0b' },
                      { id: 'movGrad', color: '#8b5cf6' },
                    ].map(({ id, color }) => (
                      <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={color} stopOpacity={0.18} />
                        <stop offset="95%" stopColor={color} stopOpacity={0}    />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <ReferenceLine y={75} stroke="#10b981" strokeDasharray="3 3" strokeWidth={1} label={{ value: 'Healthy', position: 'right', fontSize: 9, fill: '#10b981' }} />
                  <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
                  <Tooltip content={<SimpleTooltip unit=" ball" />} />
                  <Area type="monotone" dataKey="adi_score" name="ADI" stroke="#3b82f6" strokeWidth={2.5}
                    fill="url(#adiGrad)" dot={false} activeDot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} />
                  {showComponents && <>
                    <Area type="monotone" dataKey="activity_score" name="Faollik" stroke="#10b981" strokeWidth={1.5}
                      fill="url(#actGrad)" dot={false} strokeDasharray="4 2" />
                    <Area type="monotone" dataKey="feeding_score" name="Oziqlanish" stroke="#f59e0b" strokeWidth={1.5}
                      fill="url(#feedGrad)" dot={false} strokeDasharray="4 2" />
                    <Area type="monotone" dataKey="movement_score" name="Harakat" stroke="#8b5cf6" strokeWidth={1.5}
                      fill="url(#movGrad)" dot={false} strokeDasharray="4 2" />
                    <Legend iconType="line" iconSize={16} wrapperStyle={{ fontSize: 11 }} />
                  </>}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      )}

      {/* GROWTH TREND */}
      {trendType === 'growth' && (
        <div className="space-y-5">
          {growthData?.regression && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <KpiCard label="Kunlik o'sish"
                value={`${growthData.regression.slope_kg_per_day >= 0 ? '+' : ''}${growthData.regression.slope_kg_per_day.toFixed(3)} kg`}
                color={growthData.regression.slope_kg_per_day >= 0 ? 'text-emerald-600' : 'text-red-600'}
                icon={TrendingUp} iconColor="text-emerald-400" />
              <KpiCard label="Oylik o'sish"
                value={`${growthData.regression.slope_kg_per_month >= 0 ? '+' : ''}${growthData.regression.slope_kg_per_month.toFixed(1)} kg`}
                color={growthData.regression.slope_kg_per_month >= 0 ? 'text-emerald-600' : 'text-red-600'}
                icon={BarChart3} iconColor="text-blue-400" />
              <KpiCard label="Regressiya sifati"
                value={`R²=${growthData.regression.r_squared.toFixed(2)}`}
                sub={growthData.regression.r_squared > 0.7 ? "Yuqori sifat" : "Past sifat"}
                icon={Zap} iconColor="text-violet-400" />
              <KpiCard label="30k prognoz"
                value={`${growthData.regression.projected_weight_30d.toFixed(1)} kg`}
                sub="Taxminiy"
                icon={ChevronRight} iconColor="text-sky-400" />
            </div>
          )}

          <Card className="p-5">
            <CardHeader icon={TrendingUp} title="O'sish Egri Chizig'i (kg)" color="text-sky-500" />
            {isLoading ? <LoadingState /> : growthChartData.length === 0 ? <EmptyState text="Vazn ma'lumoti yo'q" /> : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={growthChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="growGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#0ea5e9" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} unit=" kg" />
                  <Tooltip content={<SimpleTooltip unit=" kg" />} />
                  <Area type="monotone" dataKey="average_weight_kg" name="O'rtacha vazn" stroke="#0ea5e9"
                    strokeWidth={2.5} fill="url(#growGrad)" dot={false} activeDot={{ r: 4, fill: '#0ea5e9', strokeWidth: 0 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      )}

      {/* BEHAVIOR TRENDS */}
      {trendType === 'behavior' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Line chart */}
          <Card className="lg:col-span-2 p-5">
            <div className="flex items-center justify-between mb-4">
              <CardHeader icon={Activity} title="Xatti-harakat Komponentlari" color="text-violet-500" />
              {behavData && (
                <div className="flex gap-3 text-xs">
                  {behavData.weakest_component && (
                    <span className="text-red-500">⬇ {behavData.weakest_component}</span>
                  )}
                  {behavData.strongest_component && (
                    <span className="text-emerald-500">⬆ {behavData.strongest_component}</span>
                  )}
                </div>
              )}
            </div>
            {isLoading ? <LoadingState /> : behavChartData.length === 0 ? <EmptyState text="Behavior ma'lumoti yo'q" /> : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={behavChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<SimpleTooltip unit=" ball" />} />
                  {[
                    { key: 'activity_score',   name: 'Faollik',     color: '#3b82f6' },
                    { key: 'feeding_score',    name: 'Oziqlanish',  color: '#10b981' },
                    { key: 'drinking_score',   name: 'Ichish',      color: '#06b6d4' },
                    { key: 'movement_score',   name: 'Harakat',     color: '#8b5cf6' },
                    { key: 'composite_behavior', name: 'Kompozit', color: '#f97316' },
                  ].map(({ key, name, color }) => (
                    <Line key={key} type="monotone" dataKey={key} name={name}
                      stroke={color} strokeWidth={key === 'composite_behavior' ? 2.5 : 1.5}
                      dot={false} activeDot={{ r: 3, strokeWidth: 0 }}
                      strokeDasharray={key === 'composite_behavior' ? undefined : '4 2'} />
                  ))}
                  <Legend iconType="line" iconSize={16} wrapperStyle={{ fontSize: 11 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Radar chart */}
          <Card className="p-5">
            <CardHeader icon={Activity} title="Radar Ko'rinish" color="text-violet-500" />
            {isLoading ? <LoadingState /> : radarData.length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={75}>
                    <PolarGrid stroke="#f3f4f6" />
                    <PolarAngleAxis dataKey="component" tick={{ fontSize: 10, fill: '#6b7280' }} />
                    <Radar name="Ball" dataKey="value" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.2} strokeWidth={2} />
                  </RadarChart>
                </ResponsiveContainer>
                {/* Component summary list */}
                <div className="space-y-2 mt-2">
                  {(behavData?.component_summaries ?? []).map(c => (
                    <div key={c.component} className="flex items-center gap-2">
                      <span className="text-xs text-gray-600 capitalize w-20 truncate">{c.component}</span>
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-violet-400 rounded-full" style={{ width: `${c.average}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-gray-700 w-8 text-right">{c.average.toFixed(0)}</span>
                      <TrendBadge direction={c.trend} />
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TAB 3 — TAQQOSLASH
// =============================================================================

function CompareTab() {
  const [compType, setCompType] = useState<'periods' | 'animals'>('periods');
  const [periodDays, setPeriodDays] = useState(30);
  const [animalIdsInput, setAnimalIdsInput] = useState('');
  const [submittedIds, setSubmittedIds] = useState<string>('');

  const { data: periodData, isLoading: periodLoading } = useQuery({
    queryKey: ['analytics', 'period-compare', periodDays],
    queryFn: () => apiFetch<PeriodComparison>(`/api/v1/analytics/compare/periods?days=${periodDays}`),
    enabled: compType === 'periods',
  });

  const { data: animalData, isLoading: animalLoading } = useQuery({
    queryKey: ['analytics', 'animal-compare', submittedIds, periodDays],
    queryFn: () => apiFetch<AnimalComparison>(`/api/v1/analytics/compare/animals?animal_ids=${submittedIds}&days=${periodDays}`),
    enabled: compType === 'animals' && submittedIds.length > 0,
  });

  const assessmentCfg = {
    improved: { color: 'text-emerald-600', bg: 'bg-emerald-50', label: "Yaxshilangan ✅" },
    declined: { color: 'text-red-600',     bg: 'bg-red-50',     label: "Yomonlashgan ⚠️" },
    stable:   { color: 'text-gray-600',    bg: 'bg-gray-100',   label: "Barqaror →"      },
  };

  const riskColors: Record<string, string> = {
    low: 'text-emerald-600 bg-emerald-50',
    moderate: 'text-amber-600 bg-amber-50',
    high: 'text-orange-600 bg-orange-50',
    critical: 'text-red-600 bg-red-50',
  };

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          <button onClick={() => setCompType('periods')}
            className={`px-4 py-2 text-xs font-medium rounded-lg transition-all ${compType === 'periods' ? 'bg-white shadow-sm text-blue-600 font-semibold' : 'text-gray-500'}`}>
            Davr-Davr
          </button>
          <button onClick={() => setCompType('animals')}
            className={`px-4 py-2 text-xs font-medium rounded-lg transition-all ${compType === 'animals' ? 'bg-white shadow-sm text-blue-600 font-semibold' : 'text-gray-500'}`}>
            Jonivorlar
          </button>
        </div>
        <SegmentedControl
          options={[{ label: '14k', value: 14 }, { label: '30k', value: 30 }, { label: '60k', value: 60 }]}
          value={periodDays}
          onChange={setPeriodDays}
        />
      </div>

      {/* PERIOD COMPARISON */}
      {compType === 'periods' && (
        <div className="space-y-5">
          {periodLoading ? <LoadingState /> : periodData ? (
            <>
              {/* Assessment banner */}
              {(() => {
                const cfg = assessmentCfg[periodData.overall_assessment];
                return (
                  <div className={`${cfg.bg} rounded-2xl p-4 flex items-center justify-between`}>
                    <div>
                      <span className={`text-base font-bold ${cfg.color}`}>{cfg.label}</span>
                      <p className="text-xs text-gray-600 mt-0.5">
                        {periodData.current_period.period_label} vs {periodData.previous_period.period_label}
                      </p>
                    </div>
                    {periodData.key_changes.length > 0 && (
                      <div className="space-y-1 text-right">
                        {periodData.key_changes.slice(0, 2).map((c, i) => (
                          <p key={i} className="text-xs text-gray-700">{c}</p>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Side-by-side metrics */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {[periodData.current_period, periodData.previous_period].map((p, pi) => (
                  <Card key={pi} className={`p-5 ${pi === 0 ? 'ring-2 ring-blue-200' : ''}`}>
                    <h4 className={`text-sm font-semibold mb-4 ${pi === 0 ? 'text-blue-700' : 'text-gray-700'}`}>
                      {pi === 0 ? '⬜ Joriy davr' : '⬛ Oldingi davr'}: {p.period_label}
                    </h4>
                    <div className="space-y-2">
                      {[
                        { label: 'Jami deteksiyalar',    val: p.total_detections.toLocaleString() },
                        { label: 'Kunlik o\'rt. deteksiya', val: p.avg_detections_per_day.toFixed(1) },
                        { label: 'O\'rtacha ADI',          val: p.avg_adi ? p.avg_adi.toFixed(1) + ' ball' : '—' },
                        { label: 'Healthy jonivorlar',    val: p.animals_in_healthy.toString() },
                        { label: 'Critical jonivorlar',   val: p.animals_in_critical.toString() },
                        { label: 'O\'rtacha vazn',         val: p.avg_weight_kg ? p.avg_weight_kg.toFixed(1) + ' kg' : '—' },
                        { label: 'Jami alertlar',         val: p.total_alerts.toString() },
                        { label: 'Kritik alertlar',       val: p.critical_alerts.toString() },
                      ].map(({ label, val }) => (
                        <div key={label} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
                          <span className="text-xs text-gray-500">{label}</span>
                          <span className="text-xs font-semibold text-gray-800">{val}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>

              {/* Delta table */}
              <Card className="p-5">
                <CardHeader icon={GitCompare} title="O'zgarishlar Jadvali" color="text-blue-500" />
                <div className="space-y-2">
                  {periodData.deltas.map(d => (
                    <div key={d.metric} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
                      <span className="text-xs text-gray-600 flex-1">{d.metric}</span>
                      <span className="text-xs text-gray-400 w-16 text-right tabular-nums">
                        {d.previous_value !== null ? d.previous_value.toFixed(1) : '—'}
                      </span>
                      <span className="text-xs font-semibold text-gray-800 w-16 text-right tabular-nums">
                        {d.current_value !== null ? d.current_value.toFixed(1) : '—'}
                      </span>
                      {d.percentage_change !== null ? (
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-lg w-20 text-center ${
                          d.is_positive_change ? 'text-emerald-700 bg-emerald-50' : 'text-red-700 bg-red-50'
                        }`}>
                          {d.direction === 'up' ? '+' : d.direction === 'down' ? '-' : ''}{Math.abs(d.percentage_change).toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 w-20 text-center">—</span>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </>
          ) : <EmptyState text="Taqqoslash ma'lumoti yo'q" />}
        </div>
      )}

      {/* ANIMAL COMPARISON */}
      {compType === 'animals' && (
        <div className="space-y-5">
          <Card className="p-5">
            <CardHeader icon={Users} title="Jonivor ID larini kiriting" color="text-violet-500" />
            <div className="flex gap-3">
              <input
                type="text"
                value={animalIdsInput}
                onChange={e => setAnimalIdsInput(e.target.value)}
                placeholder="Masalan: 1,2,3,5,8  (maks 10 ta)"
                className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent"
              />
              <button
                onClick={() => setSubmittedIds(animalIdsInput.trim())}
                disabled={!animalIdsInput.trim()}
                className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors">
                Taqqosla
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Jonivorlar ID sini vergul bilan ajrating. ID ni Animals sahifasidan topishingiz mumkin.
            </p>
          </Card>

          {animalLoading ? <LoadingState /> : animalData && animalData.animals.length > 0 ? (
            <div className="space-y-5">
              {/* Champions row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Eng yuqori ADI', val: animalData.best_adi_animal,    icon: Award,        color: 'text-emerald-600' },
                  { label: 'Eng past ADI',   val: animalData.worst_adi_animal,   icon: AlertTriangle, color: 'text-red-600'     },
                  { label: 'Eng og\'ir',      val: animalData.highest_weight_animal, icon: Scale,     color: 'text-sky-600'     },
                  { label: 'Eng faol',        val: animalData.most_active_animal, icon: Activity,     color: 'text-violet-600'  },
                ].map(({ label, val, icon: Icon, color }) => (
                  <div key={label} className="bg-gray-50 border border-gray-200 rounded-2xl p-4 text-center">
                    <Icon className={`w-5 h-5 mx-auto mb-2 ${color}`} />
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className={`text-sm font-bold mt-1 ${color}`}>{val ?? '—'}</p>
                  </div>
                ))}
              </div>

              {/* Comparison table */}
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 bg-gray-50">
                        {['Tag', 'Tur', 'ADI', 'ADI Trend', 'Vazn', 'Δ Vazn', 'Deteksiya', 'Xavf', 'Alertlar'].map(h => (
                          <th key={h} className="text-left px-4 py-3 text-gray-500 font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {animalData.animals.map((a, i) => (
                        <tr key={a.animal_id} className={`border-b border-gray-100 last:border-0 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                          <td className="px-4 py-3 font-mono font-semibold text-gray-800">{a.tag_id}</td>
                          <td className="px-4 py-3 text-gray-600 capitalize">{a.species}</td>
                          <td className="px-4 py-3">
                            {a.average_adi != null ? (
                              <span className={`font-bold ${a.average_adi >= 75 ? 'text-emerald-600' : a.average_adi >= 50 ? 'text-blue-600' : a.average_adi >= 25 ? 'text-amber-600' : 'text-red-600'}`}>
                                {a.average_adi.toFixed(1)}
                              </span>
                            ) : '—'}
                          </td>
                          <td className="px-4 py-3">
                            {a.adi_trend ? <TrendBadge direction={a.adi_trend} /> : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-700 font-medium">
                            {a.latest_weight_kg ? `${a.latest_weight_kg.toFixed(1)} kg` : '—'}
                          </td>
                          <td className="px-4 py-3">
                            {a.weight_change_pct != null ? (
                              <span className={a.weight_change_pct >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                                {a.weight_change_pct >= 0 ? '+' : ''}{a.weight_change_pct.toFixed(1)}%
                              </span>
                            ) : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-600 tabular-nums">{a.detections_period}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded-lg font-medium capitalize ${riskColors[a.risk_level] ?? 'text-gray-600 bg-gray-100'}`}>
                              {a.risk_level}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {a.active_alerts_count > 0 ? (
                              <span className="text-red-600 font-bold">{a.active_alerts_count}</span>
                            ) : (
                              <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mx-auto" />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* ADI bar comparison */}
              <Card className="p-5">
                <CardHeader icon={BarChart3} title="ADI Taqqoslash (Diagramma)" color="text-blue-500" />
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={animalData.animals.filter(a => a.average_adi != null).map(a => ({ tag: a.tag_id, adi: a.average_adi }))}
                    margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                    <XAxis dataKey="tag" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                    <ReferenceLine y={75} stroke="#10b981" strokeDasharray="3 3" strokeWidth={1} />
                    <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
                    <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)} ball`, 'ADI']} cursor={{ fill: '#f1f5f9' }} />
                    <Bar dataKey="adi" name="ADI" radius={[4, 4, 0, 0]}>
                      {animalData.animals.filter(a => a.average_adi != null).map((a, i) => (
                        <Cell key={i} fill={a.average_adi! >= 75 ? '#10b981' : a.average_adi! >= 50 ? '#3b82f6' : a.average_adi! >= 25 ? '#f59e0b' : '#ef4444'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>
          ) : submittedIds ? (
            <EmptyState text="Jonivorlar topilmadi yoki ma'lumot yo'q" />
          ) : null}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TAB 4 — NAQSHLAR (Patterns)
// =============================================================================

function PatternsTab() {
  const [patternDays, setPatternDays] = useState(7);
  const to   = new Date().toISOString().split('T')[0];
  const from = new Date(Date.now() - patternDays * 86400000).toISOString().split('T')[0];

  const { data: patterns, isLoading: pLoading } = useQuery({
    queryKey: ['analytics', 'patterns', from, to],
    queryFn: () => apiFetch<DetectionPatterns>(`/api/v1/analytics/patterns/detection?date_from=${from}&date_to=${to}`),
  });

  const { data: cameraPerf, isLoading: cLoading } = useQuery({
    queryKey: ['analytics', 'camera-perf', patternDays],
    queryFn: () => apiFetch<CameraPerf>(`/api/v1/analytics/cameras/performance?days=${patternDays}`),
  });

  const hourlyData = useMemo(() =>
    (patterns?.detections_by_hour ?? []).map((count, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      detections: count,
    })),
    [patterns]
  );

  const dailyData = useMemo(() =>
    (patterns?.detections_by_day ?? []).map(d => ({
      date: new Date(d.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
      detections: d.count,
    })),
    [patterns]
  );

  const peakHour = patterns?.statistics?.peak_hour;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <SegmentedControl
          options={[{ label: '7k', value: 7 }, { label: '14k', value: 14 }, { label: '30k', value: 30 }]}
          value={patternDays}
          onChange={setPatternDays}
        />
      </div>

      {/* Stats summary */}
      {patterns && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <KpiCard label="Jami aniqlash"       value={patterns.statistics.total_detections.toLocaleString()} icon={Activity}   iconColor="text-indigo-400" />
          <KpiCard label="Soatiga o'rtacha"     value={patterns.statistics.detection_rate_per_hour.toFixed(1)} icon={BarChart3} iconColor="text-violet-400" />
          <KpiCard label="Eng faol soat"        value={peakHour != null ? `${String(peakHour).padStart(2, '0')}:00` : '—'} icon={Zap} iconColor="text-amber-400" />
        </div>
      )}

      {/* Hourly heatmap + Daily trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <CardHeader icon={Activity} title="Soatlik Aniqlash Heatmap" color="text-indigo-500" />
            {peakHour != null && (
              <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-1 rounded-lg font-medium">
                Peak: {String(peakHour).padStart(2, '0')}:00
              </span>
            )}
          </div>
          {pLoading ? <LoadingState /> : hourlyData.every(d => d.detections === 0) ? <EmptyState text="Aniqlash ma'lumoti yo'q" /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={hourlyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="12%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="hour" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval={3} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [v, 'Aniqlashlar']} cursor={{ fill: '#f1f5f9' }} />
                {peakHour != null && (
                  <ReferenceLine x={`${String(peakHour).padStart(2, '0')}:00`} stroke="#6366f1" strokeDasharray="3 3" strokeWidth={1.5} />
                )}
                <Bar dataKey="detections" fill="#6366f1" radius={[3, 3, 0, 0]}>
                  {hourlyData.map((d, i) => (
                    <Cell key={i} fill={i === peakHour ? '#4f46e5' : '#6366f1'} opacity={d.detections === 0 ? 0.3 : 1} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="p-5">
          <CardHeader icon={BarChart3} title="Kunlik Aniqlash Trendi" color="text-violet-500" />
          {pLoading ? <LoadingState /> : dailyData.length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={dailyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="dailyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [v, 'Aniqlashlar']} />
                <Area type="monotone" dataKey="detections" name="Aniqlashlar" stroke="#8b5cf6" strokeWidth={2}
                  fill="url(#dailyGrad)" dot={false} activeDot={{ r: 4, fill: '#8b5cf6', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Top animals + Camera + Per-camera stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Top detected animals */}
        <Card className="p-5">
          <CardHeader icon={Award} title="Ko'p Aniqlangan Jonivorlar" color="text-amber-500" />
          {pLoading ? <LoadingState /> : (patterns?.top_detected_animals ?? []).length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
            <div className="space-y-2.5">
              {patterns!.top_detected_animals.slice(0, 8).map((a, i) => {
                const max = patterns!.top_detected_animals[0].detections;
                return (
                  <div key={a.tag_id} className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-400 w-4 shrink-0">{i + 1}</span>
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-xs font-semibold text-gray-800">{a.tag_id}</span>
                        <span className="text-xs text-gray-500">{a.detections.toLocaleString()}</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-amber-400 rounded-full transition-all"
                          style={{ width: `${(a.detections / max) * 100}%` }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Camera detection by camera */}
        <Card className="p-5">
          <CardHeader icon={Camera} title="Kamera bo'yicha" color="text-sky-500" />
          {pLoading ? <LoadingState /> : (patterns?.detections_by_camera ?? []).length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={patterns!.detections_by_camera}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="camera_id" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} width={80} />
                <Tooltip formatter={(v) => [v, 'Aniqlashlar']} cursor={{ fill: '#f1f5f9' }} />
                <Bar dataKey="detections" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Camera performance */}
        <Card className="p-5">
          <CardHeader icon={Camera} title="Kamera Ishlashi" color="text-emerald-500" />
          {cLoading ? <LoadingState /> : !cameraPerf || cameraPerf.cameras.length === 0 ? <EmptyState text="Kamera ma'lumoti yo'q" /> : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div className="bg-emerald-50 rounded-xl p-2.5 text-center">
                  <div className="text-lg font-bold text-emerald-700">
                    {cameraPerf.summary.running_cameras}/{cameraPerf.summary.total_cameras}
                  </div>
                  <div className="text-xs text-emerald-600">Ishlayotgan</div>
                </div>
                <div className="bg-blue-50 rounded-xl p-2.5 text-center">
                  <div className="text-lg font-bold text-blue-700">{cameraPerf.summary.average_fps.toFixed(1)}</div>
                  <div className="text-xs text-blue-600">O'rtacha FPS</div>
                </div>
              </div>
              {cameraPerf.cameras.map(cam => (
                <div key={cam.camera_id} className="flex items-center gap-2.5 py-2 border-b border-gray-100 last:border-0">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${cam.status === 'running' ? 'bg-emerald-500' : 'bg-red-400'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between">
                      <span className="text-xs font-semibold text-gray-800 truncate">{cam.camera_id}</span>
                      <span className="text-xs text-gray-500 ml-1 shrink-0">{cam.total_detections.toLocaleString()} det</span>
                    </div>
                    <div className="flex justify-between mt-0.5 text-xs text-gray-400">
                      <span>Ishonch: {(cam.average_confidence * 100).toFixed(0)}%</span>
                      <span>{cam.fps.toFixed(1)} FPS</span>
                      {cam.errors > 0 && <span className="text-red-400">{cam.errors} xato</span>}
                    </div>
                  </div>
                  {cam.status === 'running'
                    ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    : <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// =============================================================================
// TAB 5 — SOG'LIQ (Health)
// =============================================================================

function HealthTab() {
  const { data: health, isLoading } = useQuery({
    queryKey: ['analytics', 'health'],
    queryFn: () => apiFetch<HealthMetrics>('/api/v1/analytics/health/metrics'),
  });

  const { data: weightTrend, isLoading: wLoading } = useQuery({
    queryKey: ['analytics', 'weight-trend', 30],
    queryFn: () => apiFetch<{ data: any[] }>('/api/v1/analytics/trends/weight?days=30'),
  });

  const statusPieData = Object.entries(health?.animals_by_status ?? {}).map(([k, v], i) => ({
    name: { active: 'Faol', quarantine: 'Karantin', sick: 'Kasal', sold: 'Sotilgan', deceased: 'Vafot' }[k] ?? k,
    value: v as number,
    color: CHART_PALETTE[i % CHART_PALETTE.length],
  }));

  const weightDistData = Object.entries(health?.weight_distribution ?? {}).map(([k, v]) => ({
    range: k, count: v as number,
  }));

  const wTrendData = (weightTrend?.data ?? []).map((p: any) => ({
    ...p,
    date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
  }));

  const riskScore = health?.risk_score ?? 0;
  const riskCfg =
    riskScore <= 20 ? { label: "Xavf past — ferma normal holat", color: 'text-emerald-600', bg: 'bg-emerald-50', bar: 'bg-emerald-500' } :
    riskScore <= 50 ? { label: "O'rta xavf — kuzatuv tavsiya etiladi", color: 'text-amber-600',  bg: 'bg-amber-50',  bar: 'bg-amber-500'  } :
    riskScore <= 80 ? { label: "Yuqori xavf — harakat zarur",         color: 'text-orange-600', bg: 'bg-orange-50', bar: 'bg-orange-500' } :
                      { label: "Kritik xavf — darhol chora ko'ring",   color: 'text-red-600',    bg: 'bg-red-50',    bar: 'bg-red-500'    };

  return (
    <div className="space-y-5">
      {/* Risk score banner */}
      {health && (
        <div className={`${riskCfg.bg} border rounded-2xl p-5`}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className={`text-base font-bold ${riskCfg.color}`}>Xavf Balli: {riskScore}/100</h3>
              <p className="text-sm text-gray-600 mt-0.5">{riskCfg.label}</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: 'Jami', val: health.alert_summary.total, c: 'text-gray-700' },
                { label: 'Kritik', val: health.alert_summary.critical, c: 'text-red-600' },
                { label: 'Ogohlantirish', val: health.alert_summary.warning, c: 'text-amber-600' },
              ].map(({ label, val, c }) => (
                <div key={label} className="bg-white/70 rounded-xl px-3 py-2 text-center">
                  <div className={`text-xl font-bold ${c}`}>{val}</div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="h-3 bg-white/50 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${riskCfg.bar} transition-all duration-700`}
              style={{ width: `${riskScore}%` }} />
          </div>
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Status pie */}
        <Card className="p-5">
          <CardHeader icon={Users} title="Holat Taqsimoti" color="text-blue-500" />
          {isLoading ? <LoadingState /> : statusPieData.length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={statusPieData} cx="50%" cy="50%" innerRadius={40} outerRadius={62}
                    paddingAngle={3} dataKey="value">
                    {statusPieData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [`${v} ta`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-1">
                {statusPieData.map(item => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: item.color }} />
                    <span className="text-xs text-gray-600 flex-1">{item.name}</span>
                    <span className="text-xs font-semibold text-gray-800">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        {/* Weight distribution */}
        <Card className="p-5">
          <CardHeader icon={Scale} title="Vazn Taqsimoti" color="text-sky-500" />
          {isLoading ? <LoadingState /> : weightDistData.length === 0 ? <EmptyState text="Ma'lumot yo'q" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={weightDistData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="range" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [v, 'Jonivorlar']} cursor={{ fill: '#f1f5f9' }} />
                <Bar dataKey="count" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Weight trend */}
        <Card className="p-5">
          <CardHeader icon={TrendingUp} title="30 Kunlik Vazn Trendi" color="text-blue-500" />
          {wLoading ? <LoadingState /> : wTrendData.length === 0 ? <EmptyState text="Vazn ma'lumoti yo'q" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={wTrendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="hwGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} unit=" kg" />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)} kg`, "O'rtacha"]} />
                <Area type="monotone" dataKey="average_weight" name="Vazn" stroke="#3b82f6" strokeWidth={2}
                  fill="url(#hwGrad)" dot={false} activeDot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Alerts list */}
      {health && health.alerts.length > 0 && (
        <Card className="p-5">
          <CardHeader icon={AlertTriangle} title={`Aktiv Alertlar (${health.alerts.length} ta)`} color="text-amber-500" />
          <div className="space-y-2">
            {health.alerts.map((a, i) => {
              const cfg = a.severity === 'critical' ? SEVERITY_CFG.critical : SEVERITY_CFG.warning;
              return (
                <div key={i} className={`flex items-start gap-3 ${cfg.bg} ${cfg.border} border rounded-xl p-3`}>
                  <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.icon}`} />
                  <div className="flex-1">
                    <span className="text-xs font-semibold text-gray-800">{a.animal_tag}</span>
                    <span className="text-xs text-gray-600 ml-2">{a.message}</span>
                    {a.loss_percentage && (
                      <span className="text-xs text-red-600 ml-2 font-medium">(-{a.loss_percentage.toFixed(1)}%)</span>
                    )}
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${cfg.badge}`}>
                    {a.severity === 'critical' ? 'Kritik' : 'Ogohlantirish'}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const qClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await qClient.invalidateQueries({ queryKey: ['analytics'] });
    setTimeout(() => setRefreshing(false), 800);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analitika</h1>
          <p className="text-sm text-gray-500 mt-0.5">Ferma statistikasi, trendlar va avtomatik tushunchalar</p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors">
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Yangilash
        </button>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {TAB_LIST.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-all ${
              activeTab === id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}>
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'overview'  && <OverviewTab  />}
        {activeTab === 'trends'    && <TrendsTab    />}
        {activeTab === 'compare'   && <CompareTab   />}
        {activeTab === 'patterns'  && <PatternsTab  />}
        {activeTab === 'health'    && <HealthTab    />}
      </div>
    </div>
  );
}