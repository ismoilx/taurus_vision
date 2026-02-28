/**
 * DashboardPage — Sprint 7-8
 *
 * Yangiliklar:
 *   - Vazn trend grafigi (LineChart) — /analytics/trends/weight
 *   - Soatlik aniqlash grafigi (BarChart) — /analytics/patterns/detection
 *   - Sog'liq metrikalari — /analytics/health/metrics
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Activity, Scale, Camera, Users,
  TrendingUp, Play, Square,
  Heart, Zap, Brain, ShieldAlert, ShieldCheck,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { queryKeys } from '../lib/queryClient';

// =============================================================================
// TYPES
// =============================================================================

interface PipelineStatus {
  status: 'not_initialized' | 'running' | 'stopped';
  running: boolean;
  stats?: { total_frames: number; processed_frames: number; detections: number; measurements_created: number; errors: number; fps?: number };
}

interface OverviewStats {
  animals: { total: number; active: number };
  detections: { today: number; week: number; month: number; total: number };
  weight: { average_kg: number | null; change_percentage_7d: number | null };
}

interface WeightTrendPoint { date: string; average_weight: number; measurement_count: number }
interface HourlyDetection  { hour: string; detections: number }
interface HealthMetrics    { risk_score: number; alert_summary: { total: number; critical: number; warning: number } }

interface FarmPredictionSummary {
  date:            string;
  total_predicted: number;
  avg_risk_score:  number;
  low_count:       number;
  medium_count:    number;
  high_count:      number;
  critical_count:  number;
  at_risk_animals: { animal_id: number; tag_id: string; risk_level: string; risk_score: number }[];
}

// =============================================================================
// STAT CARD
// =============================================================================

function StatCard({ label, value, sub, icon: Icon, color, onClick }: {
  label: string; value: string | number; sub: string;
  icon: React.ElementType; color: string; onClick?: () => void;
}) {
  return (
    <div onClick={onClick}
      className={`bg-white rounded-2xl border border-gray-200 p-5 shadow-sm transition-all hover:shadow-md ${onClick ? 'cursor-pointer hover:-translate-y-0.5' : ''}`}>
      <div className="flex items-center justify-between mb-4">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
      <div className="text-3xl font-bold text-gray-900 tracking-tight mb-1">{value}</div>
      <div className="text-sm font-medium text-gray-700 mb-0.5">{label}</div>
      <div className="text-xs text-gray-400">{sub}</div>
    </div>
  );
}

// =============================================================================
// CUSTOM TOOLTIP
// =============================================================================

function WeightTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2.5 shadow-lg text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      <p className="text-blue-600 font-medium">{payload[0]?.value?.toFixed(1)} kg</p>
      <p className="text-gray-400">{payload[0]?.payload?.measurement_count ?? 0} ta o'lchov</p>
    </div>
  );
}

function DetectionTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2.5 shadow-lg text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      <p className="text-indigo-600 font-medium">{payload[0]?.value} ta aniqlash</p>
    </div>
  );
}

// =============================================================================
// RISK BADGE
// =============================================================================

function RiskBadge({ score }: { score: number }) {
  const cfg =
    score <= 20 ? { label: 'Xavf past', bg: 'bg-emerald-50', text: 'text-emerald-700', bar: 'bg-emerald-500' } :
    score <= 50 ? { label: "O'rta xavf", bg: 'bg-amber-50', text: 'text-amber-700', bar: 'bg-amber-500' } :
    score <= 80 ? { label: 'Yuqori xavf', bg: 'bg-orange-50', text: 'text-orange-700', bar: 'bg-orange-500' } :
                  { label: 'Kritik', bg: 'bg-red-50', text: 'text-red-700', bar: 'bg-red-500' };
  return (
    <div className={`rounded-xl p-3 ${cfg.bg}`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
        <span className={`text-sm font-bold ${cfg.text}`}>{score}/100</span>
      </div>
      <div className="h-1.5 bg-white/60 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${cfg.bar} transition-all`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function DashboardPage() {
  const navigate = useNavigate();
  const qClient  = useQueryClient();
  const [trendDays, setTrendDays] = useState(30);

  // ─── Queries (kesh bilan) ──────────────────────────────────────────────────
  // Pipeline: har 5 soniyada yangilanadi, kesh yo'q (real-time)
  const { data: pipeline = { status: 'not_initialized' as const, running: false } } =
    useQuery({
      queryKey: queryKeys.pipeline.status,
      queryFn:  () => apiFetch<PipelineStatus>('/api/v1/pipeline/status'),
      refetchInterval: 10_000, // WS fallback
    });

  // Overview: 1 daqiqa kesh — sahifaga qaytganda darhol ko'rsatiladi
  const { data: overview = null } =
    useQuery({
      queryKey: queryKeys.analytics.overview,
      queryFn:  () => apiFetch<OverviewStats>('/api/v1/analytics/overview'),
    });

  // Weight trend: trendDays o'zgarganda qayta so'rov, aks holda kesh
  const { data: weightTrendRaw, isFetching: loadingCharts } =
    useQuery({
      queryKey: queryKeys.analytics.weightTrend(trendDays),
      queryFn:  () => apiFetch<{ data: any[] }>(`/api/v1/analytics/trends/weight?days=${trendDays}`),
    });

  const weightTrend: WeightTrendPoint[] = (weightTrendRaw?.data ?? []).map((p: any) => ({
    date: new Date(p.date).toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' }),
    average_weight: p.average_weight,
    measurement_count: p.measurement_count,
  }));

  // Hourly detection
  const today   = new Date().toISOString().split('T')[0];
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0];
  const { data: hourlyRaw } =
    useQuery({
      queryKey: queryKeys.analytics.hourlyDetection(weekAgo, today),
      queryFn:  () => apiFetch<{ detections_by_hour: number[] }>(
        `/api/v1/analytics/patterns/detection?date_from=${weekAgo}&date_to=${today}`
      ),
    });

  const hourlyData: HourlyDetection[] = (hourlyRaw?.detections_by_hour ?? []).map(
    (count, hour) => ({ hour: `${String(hour).padStart(2, '0')}:00`, detections: count })
  );

  // Health metrics
  const { data: health = null } =
    useQuery({
      queryKey: queryKeys.analytics.health,
      queryFn:  () => apiFetch<HealthMetrics>('/api/v1/analytics/health/metrics'),
    });

  // Prediction farm summary — 5 daqiqa kesh
  const { data: prediction = null } =
    useQuery({
      queryKey: queryKeys.predictions.farmSummary(),
      queryFn:  () => apiFetch<FarmPredictionSummary>('/api/v1/predictions/farm-summary'),
      staleTime: 5 * 60 * 1000,
    });

  // ─── Mutations ─────────────────────────────────────────────────────────────
  const startPipeline = useMutation({
    mutationFn: () => apiFetch('/api/v1/pipeline/start', { method: 'POST' }),
    onSuccess:  () => qClient.invalidateQueries({ queryKey: queryKeys.pipeline.status }),
    onError:    (e: Error) => alert('Pipeline xatolik: ' + e.message),
  });

  const stopPipeline = useMutation({
    mutationFn: () => apiFetch('/api/v1/pipeline/stop', { method: 'POST' }),
    onSuccess:  () => qClient.invalidateQueries({ queryKey: queryKeys.pipeline.status }),
    onError:    (e: Error) => alert('Pipeline xatolik: ' + e.message),
  });

  function handleStartPipeline() { startPipeline.mutate(); }
  function handleStopPipeline()  { stopPipeline.mutate(); }

  // ─── Derived ───────────────────────────────────────────────────────────────
  const weightChange = overview?.weight?.change_percentage_7d;
  const avgWeight    = overview?.weight?.average_kg;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Umumiy ko'rinish va statistika</p>
        </div>
        <button
          onClick={pipeline.running ? handleStopPipeline : handleStartPipeline}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white shadow-sm transition-all hover:shadow-md active:scale-95 ${
            pipeline.running ? 'bg-red-500 hover:bg-red-600' : 'bg-emerald-500 hover:bg-emerald-600'
          }`}>
          {pipeline.running
            ? <><Square className="w-4 h-4 fill-current" /> Stop</>
            : <><Play className="w-4 h-4 fill-current" /> Start Pipeline</>}
        </button>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Jonivorlar" icon={Users} color="bg-blue-500"
          value={overview?.animals?.total ?? '—'}
          sub={`${overview?.animals?.active ?? 0} ta faol`}
          onClick={() => navigate('/animals')}
        />
        <StatCard
          label="Bugungi aniqlash" icon={Camera} color="bg-indigo-500"
          value={overview?.detections?.today ?? '—'}
          sub={`Hafta: ${overview?.detections?.week ?? 0}`}
        />
        <StatCard
          label="O'rtacha vazn" icon={Scale} color="bg-violet-500"
          value={avgWeight != null ? `${avgWeight.toFixed(1)} kg` : '—'}
          sub={weightChange != null
            ? `${weightChange >= 0 ? '+' : ''}${weightChange.toFixed(1)}% (7 kun)`
            : '7 kunlik ma\'lumot yo\'q'}
        />
        <StatCard
          label="Pipeline" icon={Activity} color={pipeline.running ? 'bg-emerald-500' : 'bg-gray-400'}
          value={pipeline.running ? 'Ishlaydi' : "To'xtatilgan"}
          sub={pipeline.stats ? `${(pipeline.stats.fps ?? 0).toFixed(1)} FPS` : '—'}
        />
      </div>

      {/* ── Pipeline stats bar ── */}
      {pipeline.running && pipeline.stats && (
        <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-emerald-500" />
            <span className="text-sm font-semibold text-gray-700">Pipeline — real vaqt</span>
            <span className="ml-auto flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-xs text-emerald-600 font-medium">Jonli</span>
            </span>
          </div>
          <div className="grid grid-cols-5 gap-3">
            {[
              { l: 'Kadrlar',    v: pipeline.stats.total_frames },
              { l: 'Qayta isl.', v: pipeline.stats.processed_frames },
              { l: 'Aniqlash',   v: pipeline.stats.detections },
              { l: 'Saqlangan',  v: pipeline.stats.measurements_created },
              { l: 'Xato',       v: pipeline.stats.errors },
            ].map(({ l, v }) => (
              <div key={l} className="bg-gray-50 rounded-xl p-3 text-center">
                <div className="text-xl font-bold text-gray-900 tabular-nums">{v}</div>
                <div className="text-xs text-gray-500 mt-0.5">{l}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Weight trend — 2/3 width */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">Vazn trendi</span>
            </div>
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {[7, 30, 90].map(d => (
                <button key={d} onClick={() => setTrendDays(d)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${trendDays === d ? 'bg-white shadow-sm text-blue-600 font-semibold' : 'text-gray-500 hover:text-gray-800'}`}>
                  {d}k
                </button>
              ))}
            </div>
          </div>

          {loadingCharts ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Yuklanmoqda...</div>
          ) : weightTrend.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-gray-400">
              <Scale className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-sm">Pipeline ishlayotganda ma'lumot to'planadi</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={weightTrend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} unit=" kg" />
                <Tooltip content={<WeightTooltip />} cursor={{ stroke: '#e5e7eb', strokeWidth: 1 }} />
                <Line type="monotone" dataKey="average_weight" stroke="#3b82f6"
                  strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Health card — 1/3 width */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Heart className="w-4 h-4 text-rose-500" />
            <span className="text-sm font-semibold text-gray-800">Sog'liq holati</span>
          </div>

          {health ? (
            <>
              <RiskBadge score={health.risk_score} />
              <div className="space-y-2">
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <span className="text-xs text-gray-500">Jami alertlar</span>
                  <span className="text-sm font-bold text-gray-900">{health.alert_summary.total}</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <span className="text-xs text-gray-500 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500" /> Kritik
                  </span>
                  <span className={`text-sm font-bold ${health.alert_summary.critical > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                    {health.alert_summary.critical}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-xs text-gray-500 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Ogohlantirish
                  </span>
                  <span className={`text-sm font-bold ${health.alert_summary.warning > 0 ? 'text-amber-600' : 'text-gray-400'}`}>
                    {health.alert_summary.warning}
                  </span>
                </div>
              </div>
              {health.alert_summary.total > 0 && (
                <button onClick={() => navigate('/alerts')}
                  className="mt-auto w-full py-2 text-xs font-medium text-blue-600 border border-blue-200 rounded-xl hover:bg-blue-50 transition-colors">
                  Alertlarni ko'rish →
                </button>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Yuklanmoqda...</div>
          )}
        </div>
      </div>

      {/* ── Prediction Risk Summary ── */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-indigo-500" />
            <span className="text-sm font-semibold text-gray-800">AI Sog'liq Bashorati</span>
            {prediction && (
              <span className="text-xs text-gray-400">{prediction.total_predicted} jonivor</span>
            )}
          </div>
          <button
            onClick={() => navigate('/predictions')}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
          >
            Batafsil →
          </button>
        </div>

        {prediction ? (
          <div className="flex flex-col gap-3">
            {/* Distribution bar */}
            {prediction.total_predicted > 0 && (
              <div>
                <div className="flex h-3 rounded-full overflow-hidden gap-0.5 mb-2">
                  {([
                    ['low',      prediction.low_count,      '#10b981'],
                    ['medium',   prediction.medium_count,   '#f59e0b'],
                    ['high',     prediction.high_count,     '#f97316'],
                    ['critical', prediction.critical_count, '#ef4444'],
                  ] as const).map(([key, count, color]) => {
                    const pct = prediction.total_predicted > 0
                      ? (count / prediction.total_predicted) * 100 : 0;
                    return pct > 0 ? (
                      <div
                        key={key}
                        className="h-full rounded-sm"
                        style={{ width: `${pct}%`, background: color }}
                        title={`${count} ta`}
                      />
                    ) : null;
                  })}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { label: 'Xavfsiz',   count: prediction.low_count,      color: '#10b981', bg: '#ecfdf5' },
                    { label: "O'rtacha",  count: prediction.medium_count,   color: '#f59e0b', bg: '#fffbeb' },
                    { label: 'Yuqori',    count: prediction.high_count,     color: '#f97316', bg: '#fff7ed' },
                    { label: 'Kritik',    count: prediction.critical_count, color: '#ef4444', bg: '#fef2f2' },
                  ].map(({ label, count, color, bg }) => (
                    <div key={label} className="rounded-xl p-2.5 text-center" style={{ background: bg }}>
                      <div className="text-lg font-black tabular-nums" style={{ color }}>{count}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Critical/High animals quick list */}
            {prediction.at_risk_animals.filter(a =>
              a.risk_level === 'critical' || a.risk_level === 'high'
            ).length > 0 ? (
              <div className="border-t border-gray-100 pt-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <ShieldAlert className="w-3.5 h-3.5 text-red-500" />
                  <span className="text-xs font-semibold text-gray-600">Darhol e'tibor talab qiladi</span>
                </div>
                <div className="space-y-1.5">
                  {prediction.at_risk_animals
                    .filter(a => a.risk_level === 'critical' || a.risk_level === 'high')
                    .slice(0, 3)
                    .map(a => (
                      <div
                        key={a.animal_id}
                        onClick={() => navigate(`/animals/${a.animal_id}`)}
                        className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 cursor-pointer transition-colors"
                      >
                        <span className="text-xs font-medium text-gray-700">{a.tag_id}</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold tabular-nums"
                            style={{ color: a.risk_level === 'critical' ? '#ef4444' : '#f97316' }}>
                            {Math.round(a.risk_score)}
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded-full font-medium"
                            style={{
                              background: a.risk_level === 'critical' ? '#fef2f2' : '#fff7ed',
                              color: a.risk_level === 'critical' ? '#7f1d1d' : '#7c2d12',
                            }}>
                            {a.risk_level === 'critical' ? 'Kritik' : 'Yuqori'}
                          </span>
                        </div>
                      </div>
                    ))}
                  {prediction.at_risk_animals.filter(a =>
                    a.risk_level === 'critical' || a.risk_level === 'high'
                  ).length > 3 && (
                    <button
                      onClick={() => navigate('/predictions')}
                      className="w-full text-xs text-indigo-600 py-1 hover:text-indigo-800 font-medium"
                    >
                      + {prediction.at_risk_animals.filter(a =>
                        a.risk_level === 'critical' || a.risk_level === 'high'
                      ).length - 3} ta ko'proq →
                    </button>
                  )}
                </div>
              </div>
            ) : prediction.total_predicted > 0 ? (
              <div className="flex items-center gap-2 text-emerald-600 border-t border-gray-100 pt-3">
                <ShieldCheck className="w-4 h-4" />
                <span className="text-xs font-medium">Barcha jonivorlar xavfsiz holda</span>
              </div>
            ) : null}

            {prediction.total_predicted === 0 && (
              <div className="text-xs text-gray-400 text-center py-3">
                Hali bashorat hisoblanmagan — /predictions sahifasida ishga tushiring
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-20 text-gray-400 text-sm">
            Yuklanmoqda...
          </div>
        )}
      </div>

      {/* ── Hourly detection heatmap ── */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-semibold text-gray-800">Soatlik aniqlash (oxirgi 7 kun)</span>
        </div>

        {loadingCharts ? (
          <div className="h-40 flex items-center justify-center text-gray-400 text-sm">Yuklanmoqda...</div>
        ) : hourlyData.every(d => d.detections === 0) ? (
          <div className="h-40 flex flex-col items-center justify-center text-gray-400">
            <Camera className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-sm">So'nggi 7 kunda aniqlash ma'lumoti yo'q</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={hourlyData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
              <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false}
                interval={3} />
              <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
              <Tooltip content={<DetectionTooltip />} cursor={{ fill: '#f1f5f9' }} />
              <Bar dataKey="detections" fill="#6366f1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Detections summary row ── */}
      {overview && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Bugun', value: overview.detections.today },
            { label: 'Bu hafta', value: overview.detections.week },
            { label: 'Bu oy', value: overview.detections.month },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm text-center">
              <div className="text-2xl font-bold text-gray-900 tabular-nums">{value.toLocaleString()}</div>
              <div className="text-xs text-gray-500 mt-1">{label} aniqlash</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}