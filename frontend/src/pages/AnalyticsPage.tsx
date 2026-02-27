/**
 * AnalyticsPage — Sprint 7-8
 *
 * Endpointlar:
 *   GET /api/v1/analytics/trends/weight       — Vazn trendi
 *   GET /api/v1/analytics/patterns/detection  — Aniqlash patternlari
 *   GET /api/v1/analytics/health/metrics      — Sog'liq metrikalari
 *   GET /api/v1/analytics/cameras/performance — Kamera ishlashi
 */

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import {
  TrendingUp, Activity, Camera, Heart,
  RefreshCw, AlertTriangle, CheckCircle, Award,
  BarChart2, Clock,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface WeightTrendPoint {
  date: string; average_weight: number;
  min_weight: number; max_weight: number;
  measurement_count: number; animal_count: number;
}

interface DetectionPatterns {
  date_range: { from: string; to: string; days: number };
  detections_by_hour: number[];
  detections_by_day: { date: string; count: number }[];
  detections_by_camera: { camera_id: string; detections: number; average_confidence: number }[];
  top_detected_animals: { tag_id: string; species: string; detections: number }[];
  statistics: { total_detections: number; detection_rate_per_hour: number; peak_hour: number | null };
}

interface HealthMetrics {
  animals_by_status: Record<string, number>;
  weight_distribution: Record<string, number>;
  alerts: { type: string; severity: string; animal_tag: string; message: string }[];
  alert_summary: { total: number; critical: number; warning: number };
  risk_score: number;
}

interface CameraPerf {
  cameras: { camera_id: string; status: string; total_detections: number; average_confidence: number; fps: number; uptime_percentage: number }[];
  summary: { total_cameras: number; running_cameras: number; total_detections: number; average_fps: number };
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STATUS_COLORS: Record<string, string> = {
  active: '#10b981', quarantine: '#f59e0b', sick: '#ef4444',
  sold: '#3b82f6', deceased: '#9ca3af', transferred: '#8b5cf6',
};
const STATUS_LABELS: Record<string, string> = {
  active: 'Faol', quarantine: 'Karantin', sick: 'Kasal',
  sold: 'Sotilgan', deceased: 'Vafot', transferred: "Ko'chirilgan",
};

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#9ca3af'];

// =============================================================================
// SMALL COMPONENTS
// =============================================================================

function SectionHeader({ icon: Icon, title, color = 'text-blue-500' }: {
  icon: React.ElementType; title: string; color?: string;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon className={`w-4 h-4 ${color}`} />
      <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
    </div>
  );
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-2xl p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="h-48 flex items-center justify-center text-gray-400 text-sm">{text}</div>
  );
}

function RiskBar({ score }: { score: number }) {
  const cfg =
    score <= 20 ? { label: 'Xavf past', color: 'bg-emerald-500', text: 'text-emerald-700' } :
    score <= 50 ? { label: "O'rta", color: 'bg-amber-500', text: 'text-amber-700' } :
    score <= 80 ? { label: 'Yuqori', color: 'bg-orange-500', text: 'text-orange-700' } :
                  { label: 'Kritik', color: 'bg-red-500', text: 'text-red-700' };
  return (
    <div>
      <div className="flex justify-between mb-1.5">
        <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
        <span className={`text-sm font-bold ${cfg.text}`}>{score}/100</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${cfg.color} transition-all duration-700`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

// =============================================================================
// CUSTOM TOOLTIPS
// =============================================================================

function WeightTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-lg text-xs space-y-0.5">
      <p className="font-semibold text-gray-700">{label}</p>
      <p className="text-blue-600">O'rtacha: <b>{payload[0]?.value?.toFixed(1)} kg</b></p>
      {payload[1] && <p className="text-gray-400">Min: {payload[1]?.payload?.min_weight?.toFixed(1)} kg</p>}
      {payload[1] && <p className="text-gray-400">Max: {payload[1]?.payload?.max_weight?.toFixed(1)} kg</p>}
      <p className="text-gray-400">{payload[0]?.payload?.measurement_count} o'lchov</p>
    </div>
  );
}

function DetTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-lg text-xs">
      <p className="font-semibold text-gray-700">{label}</p>
      <p className="text-indigo-600"><b>{payload[0]?.value}</b> aniqlash</p>
    </div>
  );
}

function DayTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-lg text-xs">
      <p className="font-semibold text-gray-700">{label}</p>
      <p className="text-violet-600"><b>{payload[0]?.value}</b> aniqlash</p>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function AnalyticsPage() {
  const qClient = useQueryClient();
  const [trendDays, setTrendDays]     = useState(30);
  const [patternDays, setPatternDays] = useState(7);

  const to   = new Date().toISOString().split('T')[0];
  const from = new Date(Date.now() - patternDays * 86400000).toISOString().split('T')[0];

  const { data: wtRaw, isFetching: loading } = useQuery({
    queryKey: ['analytics', 'weight-trend', trendDays],
    queryFn:  () => apiFetch<{ data: WeightTrendPoint[] }>(`/api/v1/analytics/trends/weight?days=${trendDays}`),
  });

  const { data: patterns } = useQuery({
    queryKey: ['analytics', 'patterns', from, to],
    queryFn:  () => apiFetch<DetectionPatterns>(`/api/v1/analytics/patterns/detection?date_from=${from}&date_to=${to}`),
  });

  const { data: health } = useQuery({
    queryKey: ['analytics', 'health'],
    queryFn:  () => apiFetch<HealthMetrics>('/api/v1/analytics/health/metrics'),
  });

  const { data: cameraPerf } = useQuery({
    queryKey: ['analytics', 'camera-perf'],
    queryFn:  () => apiFetch<CameraPerf>('/api/v1/analytics/cameras/performance?days=7'),
  });

  // Formatted data
  const weightTrend = (wtRaw?.data ?? []).map((p: any) => ({
    ...p,
    date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
  }));

  const hourlyData = (patterns?.detections_by_hour ?? []).map((count, i) => ({
    hour: `${String(i).padStart(2, '0')}:00`,
    detections: count,
  }));

  const dailyData = (patterns?.detections_by_day ?? []).map((d: any) => ({
    date: new Date(d.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    detections: d.count,
  }));

  const statusPieData = Object.entries(health?.animals_by_status ?? {}).map(([k, v]) => ({
    name: STATUS_LABELS[k] ?? k, value: v as number, color: STATUS_COLORS[k] ?? '#9ca3af',
  }));

  const weightDistData = Object.entries(health?.weight_distribution ?? {}).map(([k, v]) => ({
    range: k, count: v as number,
  }));

  const peakHour = patterns?.statistics?.peak_hour;

  // =============================================================================
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analitika</h1>
          <p className="text-sm text-gray-500 mt-0.5">Ferma statistikasi va trendlar</p>
        </div>
        <button onClick={() => qClient.invalidateQueries({ queryKey: ['analytics'] })} disabled={loading}
          className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Yangilash
        </button>
      </div>

      {/* ── ROW 1: Weight trend (2/3) + Risk score (1/3) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Weight trend */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <SectionHeader icon={TrendingUp} title="Vazn trendi (o'rtacha kg)" />
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {[7, 30, 90].map(d => (
                <button key={d} onClick={() => setTrendDays(d)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${trendDays === d ? 'bg-white shadow-sm text-blue-600 font-semibold' : 'text-gray-500 hover:text-gray-700'}`}>
                  {d}k
                </button>
              ))}
            </div>
          </div>

          {weightTrend.length === 0
            ? <EmptyState text="Ma'lumot yo'q — pipeline ishga tushirilganda to'planadi" />
            : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={weightTrend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} unit=" kg" />
                  <Tooltip content={<WeightTip />} cursor={{ stroke: '#e5e7eb', strokeWidth: 1 }} />
                  <Area type="monotone" dataKey="average_weight" stroke="#3b82f6" strokeWidth={2}
                    fill="url(#wGrad)" dot={false} activeDot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} />
                </AreaChart>
              </ResponsiveContainer>
            )
          }
        </Card>

        {/* Health & Risk */}
        <Card className="flex flex-col gap-4">
          <SectionHeader icon={Heart} title="Sog'liq holati" color="text-rose-500" />

          {health ? (
            <>
              <RiskBar score={health.risk_score} />

              {/* Alert summary */}
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: 'Jami', val: health.alert_summary.total, color: 'text-gray-700' },
                  { label: 'Kritik', val: health.alert_summary.critical, color: 'text-red-600' },
                  { label: 'Ogohlantirish', val: health.alert_summary.warning, color: 'text-amber-600' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="bg-gray-50 rounded-xl p-3 text-center">
                    <div className={`text-xl font-bold ${color}`}>{val}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{label}</div>
                  </div>
                ))}
              </div>

              {/* Status pie */}
              {statusPieData.length > 0 && (
                <>
                  <p className="text-xs text-gray-500 font-medium">Holat bo'yicha</p>
                  <ResponsiveContainer width="100%" height={120}>
                    <PieChart>
                      <Pie data={statusPieData} cx="50%" cy="50%" innerRadius={32} outerRadius={52}
                        paddingAngle={3} dataKey="value">
                        {statusPieData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v, n) => [v, n]} />
                      <Legend iconType="circle" iconSize={8}
                        formatter={(v) => <span style={{ fontSize: 10, color: '#6b7280' }}>{v}</span>} />
                    </PieChart>
                  </ResponsiveContainer>
                </>
              )}

              {/* Recent alerts */}
              {health.alerts.slice(0, 3).map((a, i) => (
                <div key={i} className={`flex items-start gap-2 p-2.5 rounded-xl text-xs ${a.severity === 'critical' ? 'bg-red-50' : 'bg-amber-50'}`}>
                  <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${a.severity === 'critical' ? 'text-red-500' : 'text-amber-500'}`} />
                  <div>
                    <span className="font-semibold">{a.animal_tag}</span>
                    <span className="text-gray-600 ml-1">{a.message}</span>
                  </div>
                </div>
              ))}
            </>
          ) : <EmptyState text="Yuklanmoqda..." />}
        </Card>
      </div>

      {/* ── ROW 2: Hourly heatmap + Daily trend ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Hourly */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <SectionHeader icon={Clock} title="Soatlik aniqlash" color="text-indigo-500" />
            {peakHour !== null && peakHour !== undefined && (
              <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-1 rounded-lg font-medium">
                Peak: {String(peakHour).padStart(2, '0')}:00
              </span>
            )}
          </div>
          {hourlyData.every(d => d.detections === 0)
            ? <EmptyState text="Aniqlash ma'lumoti yo'q" />
            : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={hourlyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="15%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval={3} />
                  <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<DetTip />} cursor={{ fill: '#f1f5f9' }} />
                  {peakHour !== null && peakHour !== undefined && (
                    <ReferenceLine x={`${String(peakHour).padStart(2, '0')}:00`} stroke="#6366f1" strokeDasharray="3 3" strokeWidth={1.5} />
                  )}
                  <Bar dataKey="detections" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </Card>

        {/* Daily trend */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <SectionHeader icon={BarChart2} title="Kunlik aniqlash" color="text-violet-500" />
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {[7, 14, 30].map(d => (
                <button key={d} onClick={() => setPatternDays(d)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${patternDays === d ? 'bg-white shadow-sm text-violet-600 font-semibold' : 'text-gray-500 hover:text-gray-700'}`}>
                  {d}k
                </button>
              ))}
            </div>
          </div>
          {dailyData.length === 0
            ? <EmptyState text="Ma'lumot yo'q" />
            : (
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={dailyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="dGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<DayTip />} cursor={{ stroke: '#e5e7eb', strokeWidth: 1 }} />
                  <Area type="monotone" dataKey="detections" stroke="#8b5cf6" strokeWidth={2}
                    fill="url(#dGrad)" dot={false} activeDot={{ r: 4, fill: '#8b5cf6', strokeWidth: 0 }} />
                </AreaChart>
              </ResponsiveContainer>
            )
          }
        </Card>
      </div>

      {/* ── ROW 3: Top animals + Weight distribution + Camera perf ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Top detected animals */}
        <Card>
          <SectionHeader icon={Award} title="Ko'p aniqlangan jonivorlar" color="text-amber-500" />
          {(patterns?.top_detected_animals ?? []).length === 0
            ? <EmptyState text="Ma'lumot yo'q" />
            : (
              <div className="space-y-2">
                {patterns!.top_detected_animals.slice(0, 8).map((a, i) => {
                  const max = patterns!.top_detected_animals[0].detections;
                  return (
                    <div key={a.tag_id} className="flex items-center gap-3">
                      <span className="text-xs font-mono text-gray-400 w-4">{i + 1}</span>
                      <div className="flex-1">
                        <div className="flex justify-between mb-0.5">
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
            )
          }
        </Card>

        {/* Weight distribution */}
        <Card>
          <SectionHeader icon={TrendingUp} title="Vazn taqsimoti" color="text-blue-500" />
          {weightDistData.length === 0
            ? <EmptyState text="Vazn ma'lumoti yo'q" />
            : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={weightDistData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="range" tick={{ fontSize: 9, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v) => [v, 'Jonivorlar']} cursor={{ fill: '#f1f5f9' }} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </Card>

        {/* Camera performance */}
        <Card>
          <SectionHeader icon={Camera} title="Kamera ishlashi" color="text-emerald-500" />
          {!cameraPerf || cameraPerf.cameras.length === 0
            ? <EmptyState text="Kamera ma'lumoti yo'q" />
            : (
              <div className="space-y-3">
                {/* Summary row */}
                <div className="grid grid-cols-2 gap-2 mb-1">
                  <div className="bg-emerald-50 rounded-xl p-2.5 text-center">
                    <div className="text-lg font-bold text-emerald-700">
                      {cameraPerf.summary.running_cameras}/{cameraPerf.summary.total_cameras}
                    </div>
                    <div className="text-xs text-emerald-600">Ishlayotgan</div>
                  </div>
                  <div className="bg-blue-50 rounded-xl p-2.5 text-center">
                    <div className="text-lg font-bold text-blue-700">
                      {cameraPerf.summary.average_fps.toFixed(1)}
                    </div>
                    <div className="text-xs text-blue-600">O'rtacha FPS</div>
                  </div>
                </div>

                {/* Per-camera list */}
                {cameraPerf.cameras.map(cam => (
                  <div key={cam.camera_id} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
                    <div className={`w-2 h-2 rounded-full shrink-0 ${cam.status === 'running' ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between">
                        <span className="text-xs font-semibold text-gray-800 truncate">{cam.camera_id}</span>
                        <span className="text-xs text-gray-500 ml-2 shrink-0">{cam.total_detections.toLocaleString()} det</span>
                      </div>
                      <div className="flex justify-between mt-0.5">
                        <span className="text-xs text-gray-400">
                          Ishonch: {(cam.average_confidence * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs text-gray-400">{cam.fps.toFixed(1)} FPS</span>
                      </div>
                    </div>
                    {cam.status === 'running'
                      ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      : <AlertTriangle className="w-3.5 h-3.5 text-gray-400 shrink-0" />}
                  </div>
                ))}
              </div>
            )
          }
        </Card>
      </div>

      {/* ── Detection stats summary ── */}
      {patterns && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Jami aniqlash', val: patterns.statistics.total_detections.toLocaleString() },
            { label: 'Soatiga o\'rtacha', val: patterns.statistics.detection_rate_per_hour.toFixed(1) },
            { label: 'Eng faol soat', val: peakHour !== null && peakHour !== undefined ? `${String(peakHour).padStart(2, '0')}:00` : '—' },
          ].map(({ label, val }) => (
            <Card key={label} className="text-center py-4">
              <div className="text-2xl font-bold text-gray-900 tabular-nums">{val}</div>
              <div className="text-xs text-gray-500 mt-1">{label}</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}