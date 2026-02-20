/**
 * Animal Detail Page
 * 
 * Jonivor haqida to'liq ma'lumot:
 * - Asosiy ma'lumotlar
 * - Vazn grafigi (Recharts)
 * - Detection tarixi
 * - Sog'lik holati
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Scale,
  Activity,
  Calendar,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Download,
  Edit2,
  Trash2,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { format } from 'date-fns';
import config from '../config';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Animal {
  id: number;
  tag_id: string;
  species: string;
  gender: string;
  status: string;
  breed?: string;
  notes?: string;
  acquisition_date?: string;
  total_detections: number;
  last_detected_at: string | null;
}

interface WeightMeasurement {
  id: number;
  animal_id: number;
  estimated_weight_kg: number;
  confidence_score: number;
  camera_id: string;
  timestamp: string;
}

interface HealthRecord {
  id: number;
  animal_id: number;
  record_type: string;
  description: string;
  recorded_at: string;
  recorded_by?: string;
}

interface WeightStats {
  current: number;
  average: number;
  min: number;
  max: number;
  change_7d: number;
  change_30d: number;
}

// ---------------------------------------------------------------------------
// API Helper
// ---------------------------------------------------------------------------

const API = config.apiUrl;

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  change,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  change?: string;
  icon: any;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const trendColor =
    trend === 'up'
      ? 'text-green-600'
      : trend === 'down'
      ? 'text-red-600'
      : 'text-gray-500';

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="p-2 bg-blue-50 rounded-lg">
          <Icon className="w-5 h-5 text-blue-600" />
        </div>
        {change && TrendIcon && (
          <div className={`flex items-center gap-1 text-sm font-medium ${trendColor}`}>
            <TrendIcon className="w-4 h-4" />
            {change}
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-gray-900 mb-1">{value}</div>
      <div className="text-sm text-gray-500">{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AnimalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [animal, setAnimal] = useState<Animal | null>(null);
  const [weights, setWeights] = useState<WeightMeasurement[]>([]);
  const [health, setHealth] = useState<HealthRecord[]>([]);
  const [stats, setStats] = useState<WeightStats | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // ---------------------------------------------------------------------------
  // Data Loading
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  async function loadData() {
    setLoading(true);
    setError('');

    try {
      // Load animal info
      const animalData = await apiFetch<Animal>(`/api/v1/animals/${id}`);
      setAnimal(animalData);

      // Load weight history
      const weightsData = await apiFetch<WeightMeasurement[]>(
        `/api/v1/weights/animal/${id}`
      );
      setWeights(weightsData);

      // Calculate stats
      if (weightsData.length > 0) {
        const sorted = [...weightsData].sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        
        const current = sorted[0].estimated_weight_kg;
        const allWeights = weightsData.map((w) => w.estimated_weight_kg);
        const average = allWeights.reduce((a, b) => a + b, 0) / allWeights.length;
        const min = Math.min(...allWeights);
        const max = Math.max(...allWeights);

        // 7-day and 30-day change
        const now = new Date();
        const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

        const weights7d = weightsData.filter(
          (w) => new Date(w.timestamp) >= sevenDaysAgo
        );
        const weights30d = weightsData.filter(
          (w) => new Date(w.timestamp) >= thirtyDaysAgo
        );

        const change7d =
          weights7d.length > 1
            ? current - weights7d[weights7d.length - 1].estimated_weight_kg
            : 0;
        const change30d =
          weights30d.length > 1
            ? current - weights30d[weights30d.length - 1].estimated_weight_kg
            : 0;

        setStats({
          current,
          average,
          min,
          max,
          change_7d: change7d,
          change_30d: change30d,
        });
      }

      // Load health records
      try {
        const healthData = await apiFetch<HealthRecord[]>(
          `/api/v1/health/animal/${id}`
        );
        setHealth(healthData);
      } catch (err) {
        // Health endpoint might not exist yet, skip
        console.log('Health records not available');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato yuz berdi');
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Chart Data Preparation
  // ---------------------------------------------------------------------------

  const chartData = weights
    .slice()
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(-30) // Last 30 measurements
    .map((w) => ({
      date: format(new Date(w.timestamp), 'MMM dd'),
      weight: w.estimated_weight_kg,
      confidence: w.confidence_score * 100,
      fullDate: format(new Date(w.timestamp), 'PPpp'),
    }));

  // ---------------------------------------------------------------------------
  // Export Handler
  // ---------------------------------------------------------------------------

  async function handleExport(format: 'csv' | 'excel') {
    try {
      const response = await fetch(
        `${API}/api/v1/export/weights?animal_id=${id}&format=${format}`
      );
      
      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${animal?.tag_id}_weights_${format === 'excel' ? 'xlsx' : 'csv'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export xatolik: ' + (err instanceof Error ? err.message : ''));
    }
  }

  // ---------------------------------------------------------------------------
  // Delete Handler
  // ---------------------------------------------------------------------------

  async function handleDelete() {
    if (!animal) return;
    
    const confirmed = window.confirm(
      `${animal.tag_id} ni o'chirishga ishonchingiz komilmi?`
    );
    
    if (!confirmed) return;

    try {
      await apiFetch(`/api/v1/animals/${id}`, { method: 'DELETE' });
      navigate('/animals');
    } catch (err) {
      alert('O\'chirish xatolik: ' + (err instanceof Error ? err.message : ''));
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Yuklanmoqda...</p>
        </div>
      </div>
    );
  }

  if (error || !animal) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 mb-4">{error || 'Jonivor topilmadi'}</p>
          <button
            onClick={() => navigate('/animals')}
            className="text-blue-600 hover:underline"
          >
            Orqaga
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-white rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{animal.tag_id}</h1>
              <p className="text-sm text-gray-500 capitalize">
                {animal.species} • {animal.gender} • {animal.breed || 'Unknown breed'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport('csv')}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4" />
              CSV
            </button>
            <button
              onClick={() => handleExport('excel')}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4" />
              Excel
            </button>
            <button
              onClick={() => navigate(`/animals/${id}/edit`)}
              className="p-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <Edit2 className="w-5 h-5" />
            </button>
            <button
              onClick={handleDelete}
              className="p-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Hozirgi vazn"
              value={`${stats.current.toFixed(1)} kg`}
              icon={Scale}
            />
            <StatCard
              label="O'rtacha vazn"
              value={`${stats.average.toFixed(1)} kg`}
              icon={Activity}
            />
            <StatCard
              label="7 kunlik o'zgarish"
              value={`${Math.abs(stats.change_7d).toFixed(1)} kg`}
              change={stats.change_7d > 0 ? `+${stats.change_7d.toFixed(1)}` : stats.change_7d.toFixed(1)}
              trend={stats.change_7d > 0 ? 'up' : stats.change_7d < 0 ? 'down' : 'neutral'}
              icon={TrendingUp}
            />
            <StatCard
              label="30 kunlik o'zgarish"
              value={`${Math.abs(stats.change_30d).toFixed(1)} kg`}
              change={stats.change_30d > 0 ? `+${stats.change_30d.toFixed(1)}` : stats.change_30d.toFixed(1)}
              trend={stats.change_30d > 0 ? 'up' : stats.change_30d < 0 ? 'down' : 'neutral'}
              icon={TrendingUp}
            />
          </div>
        )}

        {/* Weight Chart */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Vazn Tarixi
            <span className="ml-2 text-sm font-normal text-gray-500">
              (oxirgi 30 ta o'lchov)
            </span>
          </h2>

          {chartData.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              Vazn ma'lumotlari mavjud emas
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorWeight" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12 }}
                  stroke="#9ca3af"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  stroke="#9ca3af"
                  label={{ value: 'Vazn (kg)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                  }}
                  formatter={(value: any, name: any): any => {
                    const val = Number(value);
                    if (name === 'weight') return [`${val.toFixed(1)} kg`, 'Vazn'];
                    if (name === 'confidence') return [`${val.toFixed(0)}%`, 'Ishonch'];
                    return [`${val}`, String(name)];
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="weight"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#colorWeight)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Animal Info */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Asosiy Ma'lumotlar
            </h2>
            <div className="space-y-3">
              <InfoRow label="Tag ID" value={animal.tag_id} />
              <InfoRow label="Tur" value={animal.species} />
              <InfoRow label="Jins" value={animal.gender} />
              <InfoRow label="Zot" value={animal.breed || '—'} />
              <InfoRow label="Holat" value={animal.status} />
              <InfoRow
                label="Kiritilgan sana"
                value={
                  animal.acquisition_date
                    ? format(new Date(animal.acquisition_date), 'PPP')
                    : '—'
                }
              />
              <InfoRow
                label="Jami aniqlashlar"
                value={animal.total_detections.toString()}
              />
              <InfoRow
                label="Oxirgi ko'rinish"
                value={
                  animal.last_detected_at
                    ? format(new Date(animal.last_detected_at), 'PPpp')
                    : '—'
                }
              />
            </div>
            {animal.notes && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-sm font-medium text-gray-700 mb-1">Izohlar:</p>
                <p className="text-sm text-gray-600">{animal.notes}</p>
              </div>
            )}
          </div>

          {/* Recent Measurements */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Oxirgi O'lchovlar
            </h2>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {weights.length === 0 ? (
                <p className="text-center text-gray-400 py-8">
                  O'lchovlar mavjud emas
                </p>
              ) : (
                weights.slice(0, 10).map((w) => (
                  <div
                    key={w.id}
                    className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0"
                  >
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {w.estimated_weight_kg.toFixed(1)} kg
                      </div>
                      <div className="text-xs text-gray-500">
                        {format(new Date(w.timestamp), 'PPpp')}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">{w.camera_id}</div>
                      <div className="text-xs text-green-600">
                        {(w.confidence_score * 100).toFixed(0)}% ishonch
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Health Records (if available) */}
        {health.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mt-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Sog'lik Yozuvlari
            </h2>
            <div className="space-y-3">
              {health.map((h) => (
                <div
                  key={h.id}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                >
                  <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900">
                        {h.record_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        {format(new Date(h.recorded_at), 'PPp')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{h.description}</p>
                    {h.recorded_by && (
                      <p className="text-xs text-gray-500 mt-1">
                        Yozuvchi: {h.recorded_by}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Component
// ---------------------------------------------------------------------------

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900 capitalize">{value}</span>
    </div>
  );
}