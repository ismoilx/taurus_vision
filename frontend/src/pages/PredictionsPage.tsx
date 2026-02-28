/**
 * PredictionsPage — Sog'liq Bashorat Tizimi (Sprint 13-14)
 *
 * IMKONIYATLAR:
 *   - Ferma xavf xulosasi: low/medium/high/critical taqsimoti
 *   - Xavf ostidagi jonivorlar ro'yxati (risk score bo'yicha)
 *   - Alohida jonivor bashoratini ko'rish: ensemble breakdown, omillar, tavsiyalar
 *   - 30-kunlik xavf trend grafigi
 *   - Model holati: RF o'rgatilganmi, ensemble og'irliklari
 *   - Qo'lda bashorat va ferma-wide bashorat (manager/admin)
 *   - Model qayta o'rgatish (admin)
 *
 * BACKEND:
 *   GET  /predictions/farm-summary
 *   GET  /predictions/at-risk
 *   GET  /predictions/animal/{id}
 *   GET  /predictions/animal/{id}/history
 *   POST /predictions/animal/{id}/predict
 *   POST /predictions/run-farm
 *   POST /predictions/train
 *   GET  /predictions/model-status
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle, ShieldCheck, ShieldAlert, Zap,
  TrendingUp, TrendingDown, Minus,
  Brain, RefreshCw, ChevronRight, ArrowLeft,
  Activity, Utensils, Eye, BarChart2,
  CheckCircle2, Info, PlayCircle, FlaskConical,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, BarChart, Bar, PieChart, Pie,
} from 'recharts';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface EnsembleBreakdown {
  rule_based:    number;
  random_forest: number;
  isolation:     number;
  final:         number;
}

interface HealthPrediction {
  id:               number;
  animal_id:        number;
  prediction_date:  string;
  created_at:       string;
  risk_level:       'low' | 'medium' | 'high' | 'critical';
  risk_score:       number;
  confidence:       number;
  ensemble:         EnsembleBreakdown;
  adi_days_available: number;
  features_used:    number;
  predicted_adi_7day: number | null;
  trend_direction:  'improving' | 'stable' | 'declining' | null;
  risk_factors:     RiskFactor[];
  recommendations:  string[];
  model_version:    string;
  needs_attention:  boolean;
}

interface RiskFactor {
  factor:      string;
  weight:      number;
  value:       number;
  description: string;
  severity:    'critical' | 'warning' | 'ok';
}

interface AnimalRiskSummary {
  animal_id:       number;
  tag_id:          string;
  name:            string | null;
  species:         string;
  risk_level:      string;
  risk_score:      number;
  confidence:      number;
  trend_direction: string | null;
  top_risk_factor: string | null;
}

interface FarmSummary {
  date:            string;
  total_predicted: number;
  avg_risk_score:  number;
  max_risk_score:  number;
  low_count:       number;
  medium_count:    number;
  high_count:      number;
  critical_count:  number;
  at_risk_animals: AnimalRiskSummary[];
}

interface PredictionHistoryPoint {
  date:           string;
  risk_score:     number;
  risk_level:     string;
  adi_projection: number | null;
}

interface PredictionHistory {
  animal_id: number;
  days:      number;
  history:   PredictionHistoryPoint[];
}

interface ModelStatus {
  rf_trained:         boolean;
  iso_trained:        boolean;
  trained_at:         string | null;
  n_training_samples: number;
  model_version:      string;
  ensemble_weights:   { rule_based: number; random_forest: number; isolation: number };
  top_features:       { feature: string; importance: number }[];
  status_message:     string;
}

interface TrainResponse {
  rf_trained:   boolean;
  iso_trained:  boolean;
  n_samples:    number;
  n_positive:   number;
  rf_accuracy:  number;
  top_features: { feature: string; importance: number }[];
  duration_sec: number;
  trained_at:   string | null;
  message:      string | null;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const RISK_CFG = {
  low:      { color: '#10b981', bg: '#ecfdf5', border: '#6ee7b7', text: '#065f46', label: 'Xavfsiz',      icon: ShieldCheck    },
  medium:   { color: '#f59e0b', bg: '#fffbeb', border: '#fcd34d', text: '#78350f', label: "O'rtacha",     icon: AlertTriangle  },
  high:     { color: '#f97316', bg: '#fff7ed', border: '#fdba74', text: '#7c2d12', label: 'Yuqori xavf',  icon: ShieldAlert    },
  critical: { color: '#ef4444', bg: '#fef2f2', border: '#fca5a5', text: '#7f1d1d', label: 'Kritik xavf', icon: Zap            },
} as const;

const TREND_CFG = {
  improving: { icon: TrendingUp,   color: '#10b981', label: 'Yaxshilanmoqda' },
  stable:    { icon: Minus,        color: '#6b7280', label: 'Barqaror'       },
  declining: { icon: TrendingDown, color: '#ef4444', label: 'Yomonlashmoqda' },
} as const;

// =============================================================================
// SMALL COMPONENTS
// =============================================================================

function RiskBadge({ level, size = 'sm' }: { level: string; size?: 'xs' | 'sm' | 'md' }) {
  const cfg = RISK_CFG[level as keyof typeof RISK_CFG] ?? RISK_CFG.low;
  const Icon = cfg.icon;
  const pad = size === 'xs' ? 'px-1.5 py-0.5 text-xs' : size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-semibold ${pad}`}
      style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}` }}
    >
      <Icon size={size === 'xs' ? 10 : 12} />
      {cfg.label}
    </span>
  );
}

function TrendBadge({ trend }: { trend: string | null }) {
  if (!trend || !(trend in TREND_CFG)) return null;
  const cfg = TREND_CFG[trend as keyof typeof TREND_CFG];
  const Icon = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium" style={{ color: cfg.color }}>
      <Icon size={12} />
      {cfg.label}
    </span>
  );
}

function RiskGauge({ score }: { score: number }) {
  const pct   = Math.min(100, Math.max(0, score));
  const color = score >= 76 ? '#ef4444' : score >= 56 ? '#f97316' : score >= 31 ? '#f59e0b' : '#10b981';
  const r = 44;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="120" height="120" className="-rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#e5e7eb" strokeWidth="10" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-2xl font-black" style={{ color }}>{Math.round(score)}</div>
        <div className="text-xs text-gray-400 font-medium">/ 100</div>
      </div>
    </div>
  );
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color = pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#9ca3af';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-medium tabular-nums" style={{ color }}>{pct}%</span>
    </div>
  );
}

function EnsembleBar({
  label, value, color, weight,
}: { label: string; value: number; color: string; weight: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-gray-600">{label}</span>
          <span className="text-xs text-gray-400">({Math.round(weight * 100)}%)</span>
        </div>
        <span className="text-sm font-bold tabular-nums" style={{ color }}>{Math.round(value)}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  );
}

function StatCard({
  label, count, total, color, bg,
}: { label: string; count: number; total: number; color: string; bg: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="rounded-xl p-4 border" style={{ background: bg, borderColor: `${color}30` }}>
      <div className="text-2xl font-black tabular-nums" style={{ color }}>{count}</div>
      <div className="text-xs font-medium text-gray-500 mt-0.5">{label}</div>
      <div className="mt-2 h-1 bg-white/60 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="text-xs text-gray-400 mt-1 tabular-nums">{pct}% fermada</div>
    </div>
  );
}

// Custom tooltip for risk chart
function RiskTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const score = payload[0]?.value ?? 0;
  const color = score >= 76 ? '#ef4444' : score >= 56 ? '#f97316' : score >= 31 ? '#f59e0b' : '#10b981';
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-bold" style={{ color }}>Xavf bali: {Math.round(score)}</p>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function PredictionsPage() {
  const navigate      = useNavigate();
  const queryClient   = useQueryClient();
  const [selectedId, setSelectedId]       = useState<number | null>(null);
  const [historyDays, setHistoryDays]     = useState(30);
  const [showModelInfo, setShowModelInfo] = useState(false);
  const [trainResult, setTrainResult]     = useState<TrainResponse | null>(null);

  // ── Queries ─────────────────────────────────────────────────────────────── //

  const farmQuery = useQuery<FarmSummary>({
    queryKey: ['predictions', 'farm-summary'],
    queryFn:  () => apiFetch('/api/v1/predictions/farm-summary'),
    staleTime: 5 * 60 * 1000,
  });

  const atRiskQuery = useQuery<AnimalRiskSummary[]>({
    queryKey: ['predictions', 'at-risk'],
    queryFn:  () => apiFetch('/api/v1/predictions/at-risk?min_risk=medium'),
    staleTime: 5 * 60 * 1000,
  });

  const predictionQuery = useQuery<HealthPrediction>({
    queryKey: ['predictions', 'animal', selectedId],
    queryFn:  () => apiFetch(`/api/v1/predictions/animal/${selectedId}`),
    enabled:  selectedId !== null,
    staleTime: 5 * 60 * 1000,
  });

  const historyQuery = useQuery<PredictionHistory>({
    queryKey: ['predictions', 'history', selectedId, historyDays],
    queryFn:  () => apiFetch(`/api/v1/predictions/animal/${selectedId}/history?days=${historyDays}`),
    enabled:  selectedId !== null,
    staleTime: 5 * 60 * 1000,
  });

  const modelQuery = useQuery<ModelStatus>({
    queryKey: ['predictions', 'model-status'],
    queryFn:  () => apiFetch('/api/v1/predictions/model-status'),
    staleTime: 60 * 1000,
  });

  // ── Mutations ────────────────────────────────────────────────────────────── //

  const predictMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/predictions/animal/${id}/predict`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['predictions', 'animal', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['predictions', 'farm-summary'] });
    },
  });

  const farmRunMut = useMutation({
    mutationFn: () =>
      apiFetch('/api/v1/predictions/run-farm', { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] });
    },
  });

  const trainMut = useMutation<TrainResponse>({
    mutationFn: () =>
      apiFetch('/api/v1/predictions/train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days_back: 90 }),
      }),
    onSuccess: (data) => {
      setTrainResult(data);
      queryClient.invalidateQueries({ queryKey: ['predictions', 'model-status'] });
    },
  });

  // ── Derived ──────────────────────────────────────────────────────────────── //

  const farm        = farmQuery.data;
  const atRisk      = atRiskQuery.data ?? [];
  const pred        = predictionQuery.data;
  const history     = historyQuery.data?.history ?? [];
  const model       = modelQuery.data;

  const historyChartData = [...history].reverse().map(h => ({
    date:  h.date.slice(5),   // MM-DD
    score: h.risk_score,
    level: h.risk_level,
    adi:   h.adi_projection,
  }));

  // =============================================================================
  // RENDER — Detail Panel (right side when animal selected)
  // =============================================================================

  const renderDetail = () => {
    if (!selectedId) return null;

    return (
      <div className="flex flex-col gap-4">

        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelectedId(null)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-gray-900 truncate">
              {atRisk.find(a => a.animal_id === selectedId)?.tag_id ?? `Jonivor #${selectedId}`}
            </h3>
            <p className="text-xs text-gray-500">Batafsil bashorat</p>
          </div>
          <button
            onClick={() => navigate(`/animals/${selectedId}`)}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1 transition-colors"
          >
            Profil <ChevronRight size={14} />
          </button>
        </div>

        {predictionQuery.isLoading && (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            <RefreshCw size={16} className="animate-spin mr-2" /> Yuklanmoqda...
          </div>
        )}

        {pred && (
          <>
            {/* Risk Gauge + Meta */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-5">
                <RiskGauge score={pred.risk_score} />
                <div className="flex-1 space-y-2">
                  <RiskBadge level={pred.risk_level} size="md" />
                  {pred.trend_direction && <div><TrendBadge trend={pred.trend_direction} /></div>}
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Ishonchlilik</div>
                    <ConfidenceBar confidence={pred.confidence} />
                  </div>
                  {pred.predicted_adi_7day !== null && (
                    <div className="text-xs text-gray-500">
                      7 kunlik ADI bashorati:{' '}
                      <span className="font-bold text-gray-800">{pred.predicted_adi_7day}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Ensemble Breakdown */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <Brain size={16} className="text-indigo-500" />
                <h4 className="font-semibold text-gray-800 text-sm">Ensemble tafsiloti</h4>
              </div>
              <div className="space-y-3">
                <EnsembleBar
                  label="Qoidalar tizimi"
                  value={pred.ensemble.rule_based}
                  color="#6366f1"
                  weight={0.40}
                />
                <EnsembleBar
                  label="RandomForest"
                  value={pred.ensemble.random_forest}
                  color="#3b82f6"
                  weight={0.40}
                />
                <EnsembleBar
                  label="IsolationForest"
                  value={pred.ensemble.isolation}
                  color="#8b5cf6"
                  weight={0.20}
                />
                <div className="pt-2 border-t border-gray-100">
                  <EnsembleBar
                    label="Yakuniy ball"
                    value={pred.ensemble.final}
                    color={pred.risk_score >= 56 ? '#ef4444' : pred.risk_score >= 31 ? '#f59e0b' : '#10b981'}
                    weight={1.0}
                  />
                </div>
              </div>
            </div>

            {/* Risk Trend Chart */}
            {historyQuery.isLoading ? (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 h-44 flex items-center justify-center text-gray-400 text-xs">
                <RefreshCw size={14} className="animate-spin mr-2" /> Trend yuklanmoqda...
              </div>
            ) : history.length > 0 ? (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <BarChart2 size={16} className="text-indigo-500" />
                    <h4 className="font-semibold text-gray-800 text-sm">Xavf trendi</h4>
                  </div>
                  <div className="flex gap-1">
                    {[14, 30, 60].map(d => (
                      <button
                        key={d}
                        onClick={() => setHistoryDays(d)}
                        className={`text-xs px-2 py-0.5 rounded-lg font-medium transition-colors ${
                          historyDays === d
                            ? 'bg-indigo-600 text-white'
                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                        }`}
                      >{d}k</button>
                    ))}
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={130}>
                  <AreaChart data={historyChartData} margin={{ left: -20, right: 4, top: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                    <Tooltip content={<RiskTooltip />} />
                    <Area
                      type="monotone" dataKey="score"
                      stroke="#6366f1" strokeWidth={2}
                      fill="url(#riskGrad)" dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : null}

            {/* Risk Factors */}
            {pred.risk_factors.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle size={16} className="text-amber-500" />
                  <h4 className="font-semibold text-gray-800 text-sm">Xavf omillari</h4>
                </div>
                <div className="space-y-2">
                  {pred.risk_factors.slice(0, 5).map((f, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-gray-50">
                      <div
                        className="w-1 rounded-full mt-1 flex-shrink-0"
                        style={{
                          height: 28,
                          background:
                            f.severity === 'critical' ? '#ef4444' :
                            f.severity === 'warning'  ? '#f59e0b' : '#10b981',
                        }}
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-700 leading-snug">{f.description}</p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          Og'irlik: {Math.round(f.weight * 100)}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {pred.recommendations.length > 0 && (
              <div className="bg-indigo-50 rounded-2xl border border-indigo-100 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle2 size={16} className="text-indigo-600" />
                  <h4 className="font-semibold text-indigo-800 text-sm">Tavsiyalar</h4>
                </div>
                <ul className="space-y-2">
                  {pred.recommendations.map((rec, i) => (
                    <li key={i} className="text-xs text-indigo-700 flex items-start gap-1.5">
                      <span className="text-indigo-400 mt-0.5">›</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Meta */}
            <div className="text-xs text-gray-400 flex items-center gap-3 px-1">
              <span>Ma'lumot: {pred.adi_days_available} kun</span>
              <span>·</span>
              <span>Feature: {pred.features_used}</span>
              <span>·</span>
              <span>v{pred.model_version}</span>
            </div>

            {/* Predict button */}
            <button
              onClick={() => predictMut.mutate(selectedId)}
              disabled={predictMut.isPending}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl
                         bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold
                         disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {predictMut.isPending
                ? <><RefreshCw size={14} className="animate-spin" /> Hisoblanmoqda...</>
                : <><RefreshCw size={14} /> Qayta hisoblash</>
              }
            </button>
          </>
        )}
      </div>
    );
  };

  // =============================================================================
  // RENDER — Model Status Modal
  // =============================================================================

  const renderModelModal = () => {
    if (!showModelInfo || !model) return null;
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.5)' }}
        onClick={() => setShowModelInfo(false)}
      >
        <div
          className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Brain size={20} className="text-indigo-600" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900">Model holati</h3>
              <p className="text-xs text-gray-500">{model.status_message}</p>
            </div>
          </div>

          {/* Status chips */}
          <div className="flex gap-2 mb-4">
            <span className={`text-xs px-2 py-1 rounded-lg font-medium ${
              model.rf_trained ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}>
              {model.rf_trained ? '✅' : '⚠️'} RandomForest
            </span>
            <span className={`text-xs px-2 py-1 rounded-lg font-medium ${
              model.iso_trained ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}>
              {model.iso_trained ? '✅' : '⚠️'} IsolationForest
            </span>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-gray-50 rounded-xl p-3">
              <p className="text-xs text-gray-400">Training namunalari</p>
              <p className="text-xl font-black text-gray-800 tabular-nums">{model.n_training_samples}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-3">
              <p className="text-xs text-gray-400">Versiya</p>
              <p className="text-sm font-bold text-gray-800">{model.model_version}</p>
            </div>
          </div>

          {/* Ensemble weights */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-600 mb-2">Ensemble og'irliklari</p>
            <div className="space-y-2">
              {Object.entries(model.ensemble_weights).map(([key, w]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28">{
                    key === 'rule_based' ? 'Qoidalar' :
                    key === 'random_forest' ? 'RandomForest' : 'IsolationForest'
                  }</span>
                  <div className="flex-1 h-1.5 bg-gray-100 rounded-full">
                    <div className="h-full bg-indigo-400 rounded-full" style={{ width: `${w * 100}%` }} />
                  </div>
                  <span className="text-xs font-bold text-indigo-600 w-8 text-right">{Math.round(w * 100)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top features */}
          {model.top_features.length > 0 && (
            <div className="mb-5">
              <p className="text-xs font-semibold text-gray-600 mb-2">Eng muhim feature lar</p>
              <div className="space-y-1.5">
                {model.top_features.slice(0, 5).map(f => (
                  <div key={f.feature} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 truncate flex-1">{f.feature.replace(/_/g, ' ')}</span>
                    <div className="w-20 h-1.5 bg-gray-100 rounded-full">
                      <div
                        className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${f.importance * 100 * 5}%`, maxWidth: '100%' }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 w-10 text-right tabular-nums">
                      {(f.importance * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Train button */}
          <button
            onClick={() => { trainMut.mutate(); }}
            disabled={trainMut.isPending}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                       bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold
                       disabled:opacity-50 transition-colors"
          >
            {trainMut.isPending
              ? <><RefreshCw size={14} className="animate-spin" /> O'rgatilmoqda...</>
              : <><FlaskConical size={14} /> Modelni qayta o'rgatish</>
            }
          </button>

          {/* Train result */}
          {trainResult && (
            <div className={`mt-3 p-3 rounded-xl text-xs ${
              trainResult.rf_trained ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
            }`}>
              {trainResult.rf_trained
                ? `✅ Muvaffaqiyatli: ${trainResult.n_samples} namuna, ${trainResult.duration_sec.toFixed(1)}s`
                : `⚠️ ${trainResult.message ?? "Yetarli ma'lumot yo'q"}`
              }
            </div>
          )}
        </div>
      </div>
    );
  };

  // =============================================================================
  // MAIN RENDER
  // =============================================================================

  const isLoading = farmQuery.isLoading || atRiskQuery.isLoading;

  return (
    <div className="min-h-screen bg-gray-50">
      {renderModelModal()}

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm">
              <Brain size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-black text-gray-900">Sog'liq Bashorati</h1>
              <p className="text-xs text-gray-400">
                {farm ? `${farm.date} · ${farm.total_predicted} jonivor bashorat qilindi` : 'Sprint 13-14'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowModelInfo(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors font-medium"
            >
              <Info size={14} />
              Model holati
              {model && (
                <span className={`w-2 h-2 rounded-full ${model.rf_trained ? 'bg-green-500' : 'bg-amber-400'}`} />
              )}
            </button>
            <button
              onClick={() => farmRunMut.mutate()}
              disabled={farmRunMut.isPending}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50 transition-colors"
            >
              {farmRunMut.isPending
                ? <><RefreshCw size={13} className="animate-spin" /> Hisoblanmoqda...</>
                : <><PlayCircle size={13} /> Ferma bashorat</>
              }
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">

        {isLoading && (
          <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
            <RefreshCw size={16} className="animate-spin mr-2" /> Yuklanmoqda...
          </div>
        )}

        {!isLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* ── LEFT COLUMN: Farm Stats + At-Risk List ─────────────────── */}
            <div className={`${selectedId ? 'lg:col-span-2' : 'lg:col-span-2'} flex flex-col gap-6`}>

              {/* Farm stat cards */}
              {farm && (
                <div className="grid grid-cols-4 gap-3">
                  <StatCard
                    label="Xavfsiz"
                    count={farm.low_count}
                    total={farm.total_predicted}
                    color="#10b981"
                    bg="#ecfdf5"
                  />
                  <StatCard
                    label="O'rtacha"
                    count={farm.medium_count}
                    total={farm.total_predicted}
                    color="#f59e0b"
                    bg="#fffbeb"
                  />
                  <StatCard
                    label="Yuqori xavf"
                    count={farm.high_count}
                    total={farm.total_predicted}
                    color="#f97316"
                    bg="#fff7ed"
                  />
                  <StatCard
                    label="Kritik"
                    count={farm.critical_count}
                    total={farm.total_predicted}
                    color="#ef4444"
                    bg="#fef2f2"
                  />
                </div>
              )}

              {/* Farm average risk */}
              {farm && farm.total_predicted > 0 && (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Activity size={16} className="text-indigo-500" />
                      <h2 className="font-semibold text-gray-800 text-sm">Ferma umumiy xavf ko'rsatkichi</h2>
                    </div>
                    <div className="text-right">
                      <span className="text-2xl font-black tabular-nums" style={{
                        color: farm.avg_risk_score >= 56 ? '#ef4444' :
                               farm.avg_risk_score >= 31 ? '#f59e0b' : '#10b981'
                      }}>
                        {farm.avg_risk_score.toFixed(1)}
                      </span>
                      <span className="text-xs text-gray-400 ml-1">o'rtacha</span>
                    </div>
                  </div>

                  {/* Distribution bar */}
                  <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
                    {([
                      ['low',      farm.low_count,      '#10b981'],
                      ['medium',   farm.medium_count,   '#f59e0b'],
                      ['high',     farm.high_count,     '#f97316'],
                      ['critical', farm.critical_count, '#ef4444'],
                    ] as const).map(([key, count, color]) => {
                      const pct = farm.total_predicted > 0 ? (count / farm.total_predicted) * 100 : 0;
                      return pct > 0 ? (
                        <div
                          key={key}
                          className="h-full rounded-sm transition-all duration-700"
                          style={{ width: `${pct}%`, background: color }}
                          title={`${RISK_CFG[key].label}: ${count}`}
                        />
                      ) : null;
                    })}
                  </div>
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>0</span>
                    <span>Max xavf: {farm.max_risk_score.toFixed(0)}</span>
                  </div>
                </div>
              )}

              {/* At-Risk Animals table */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={16} className="text-amber-500" />
                    <h2 className="font-semibold text-gray-800 text-sm">
                      Xavf ostidagi jonivorlar
                      {atRisk.length > 0 && (
                        <span className="ml-2 text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-bold">
                          {atRisk.length}
                        </span>
                      )}
                    </h2>
                  </div>
                  <Eye size={15} className="text-gray-300" />
                </div>

                {atRisk.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                    <ShieldCheck size={32} className="text-green-400 mb-3" />
                    <p className="text-sm font-medium text-gray-500">Barcha jonivorlar xavfsiz</p>
                    <p className="text-xs mt-1">Hozircha medium+ xavf yo'q</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {atRisk.map(animal => (
                      <div
                        key={animal.animal_id}
                        onClick={() => setSelectedId(
                          selectedId === animal.animal_id ? null : animal.animal_id
                        )}
                        className={`px-5 py-3 flex items-center gap-4 cursor-pointer transition-colors ${
                          selectedId === animal.animal_id
                            ? 'bg-indigo-50'
                            : 'hover:bg-gray-50'
                        }`}
                      >
                        {/* Risk score */}
                        <div
                          className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 font-black text-sm tabular-nums"
                          style={{
                            background: RISK_CFG[animal.risk_level as keyof typeof RISK_CFG]?.bg ?? '#f9fafb',
                            color: RISK_CFG[animal.risk_level as keyof typeof RISK_CFG]?.color ?? '#374151',
                          }}
                        >
                          {Math.round(animal.risk_score)}
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-gray-900">{animal.tag_id}</span>
                            {animal.name && (
                              <span className="text-xs text-gray-400">{animal.name}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <RiskBadge level={animal.risk_level} size="xs" />
                            {animal.trend_direction && <TrendBadge trend={animal.trend_direction} />}
                          </div>
                          {animal.top_risk_factor && (
                            <p className="text-xs text-gray-400 mt-0.5 truncate">
                              {animal.top_risk_factor.replace(/_/g, ' ')}
                            </p>
                          )}
                        </div>

                        {/* Confidence */}
                        <div className="text-right flex-shrink-0">
                          <div className="text-xs text-gray-400 mb-1">Ishonch</div>
                          <div className="text-xs font-semibold text-gray-600">
                            {Math.round(animal.confidence * 100)}%
                          </div>
                        </div>

                        <ChevronRight
                          size={16}
                          className={`flex-shrink-0 transition-colors ${
                            selectedId === animal.animal_id ? 'text-indigo-400' : 'text-gray-200'
                          }`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* ── RIGHT COLUMN: Detail or placeholder ─────────────────────── */}
            <div className="lg:col-span-1">
              {selectedId ? (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sticky top-6">
                  {renderDetail()}
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-8 flex flex-col items-center justify-center text-center min-h-64">
                  <Brain size={32} className="text-gray-200 mb-3" />
                  <p className="text-sm font-medium text-gray-400">Jonivor tanlang</p>
                  <p className="text-xs text-gray-300 mt-1 max-w-40 leading-relaxed">
                    Ro'yxatdan jonivorni bosing — batafsil bashorat ko'rinadi
                  </p>
                </div>
              )}
            </div>

          </div>
        )}
      </div>
    </div>
  );
}