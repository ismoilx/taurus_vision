/**
 * Dashboard Page
 * 
 * Main overview with statistics and recent activity
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Scale,
  Camera,
  Users,
  TrendingUp,
  Play,
  Square,
  AlertCircle,
} from 'lucide-react';
import config from '../config';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PipelineStatus {
  status: 'not_initialized' | 'running' | 'stopped';
  running: boolean;
  stats?: {
    total_frames: number;
    processed_frames: number;
    detections: number;
    measurements_created: number;
    errors: number;
    fps?: number;
  };
}

interface LiveWeightUpdate {
  animal_id: number;
  animal_tag_id: string;
  estimated_weight_kg: number;
  confidence_score: number;
  camera_id: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// API
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
  sub,
  icon: Icon,
  accent,
  onClick,
}: {
  label: string;
  value: string | number;
  sub: string;
  icon: any;
  accent: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all ${
        onClick ? 'cursor-pointer' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className={`p-3 ${accent} rounded-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
      <div className="text-3xl font-bold text-gray-900 mb-1">{value}</div>
      <div className="text-sm text-gray-600 font-medium mb-0.5">{label}</div>
      <div className="text-xs text-gray-400">{sub}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const navigate = useNavigate();

  const [pipeline, setPipeline] = useState<PipelineStatus>({
    status: 'not_initialized',
    running: false,
  });
  const [measurements, setMeasurements] = useState<LiveWeightUpdate[]>([]);
  const [stats, setStats] = useState({
    totalAnimals: 0,
    totalDetections: 0,
    avgWeight: '—',
  });

  // ---------------------------------------------------------------------------
  // Load Data
  // ---------------------------------------------------------------------------

  useEffect(() => {
    loadPipelineStatus();
    loadStats();
    loadRecentMeasurements();

    const interval = setInterval(() => {
      loadPipelineStatus();
      if (pipeline.running) {
        loadRecentMeasurements();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  async function loadPipelineStatus() {
    try {
      const status = await apiFetch<PipelineStatus>('/api/v1/pipeline/status');
      setPipeline(status);
    } catch (err) {
      console.error('Pipeline status error:', err);
    }
  }

  async function loadStats() {
    try {
      const [animalsRes, analyticsRes] = await Promise.all([
        apiFetch<{ total: number }>('/api/v1/animals/?limit=1'),
        apiFetch<any>('/api/v1/analytics/overview'),
      ]);

      setStats({
        totalAnimals: animalsRes.total || 0,
        totalDetections: analyticsRes?.detections?.total ?? analyticsRes?.total_detections ?? 0,
        avgWeight:
          analyticsRes?.weight?.average_kg > 0
            ? analyticsRes.weight.average_kg.toFixed(1)
            : analyticsRes?.average_weight > 0
            ? analyticsRes.average_weight.toFixed(1)
            : '—',
      });
    } catch (err) {
      console.error('Stats error:', err);
    }
  }

  async function loadRecentMeasurements() {
    try {
      const data = await apiFetch<any>('/api/v1/weights/recent?limit=8&min_confidence=0.0');
      // WeightMeasurementListResponse: { items: [...], total, skip, limit }
      const items = Array.isArray(data) ? data : (data?.items ?? []);
      setMeasurements(
        items.map((m: any) => ({
          animal_id: m.animal_id,
          animal_tag_id: m.animal_tag_id ?? `#${m.animal_id}`,
          estimated_weight_kg: m.estimated_weight_kg,
          confidence_score: m.confidence_score,
          camera_id: m.camera_id,
          timestamp: m.timestamp,
        }))
      );
    } catch (err) {
      console.error('Measurements error:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // Pipeline Controls
  // ---------------------------------------------------------------------------

  async function handleStartPipeline() {
    try {
      await apiFetch('/api/v1/pipeline/start', { method: 'POST' });
      await loadPipelineStatus();
    } catch (err) {
      alert('Pipeline xatolik: ' + (err instanceof Error ? err.message : ''));
    }
  }

  async function handleStopPipeline() {
    try {
      await apiFetch('/api/v1/pipeline/stop', { method: 'POST' });
      await loadPipelineStatus();
    } catch (err) {
      alert('Pipeline xatolik: ' + (err instanceof Error ? err.message : ''));
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">Umumiy ko'rinish va statistika</p>
        </div>

        {/* Pipeline Control */}
        <button
          onClick={pipeline.running ? handleStopPipeline : handleStartPipeline}
          className={`flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white shadow-lg transition-all hover:scale-105 ${
            pipeline.running
              ? 'bg-gradient-to-r from-red-500 to-red-600'
              : 'bg-gradient-to-r from-green-500 to-green-600'
          }`}
        >
          {pipeline.running ? (
            <>
              <Square className="w-5 h-5 fill-current" />
              Stop Pipeline
            </>
          ) : (
            <>
              <Play className="w-5 h-5 fill-current" />
              Start Pipeline
            </>
          )}
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          label="Jonivorlar"
          value={stats.totalAnimals}
          sub="jami ro'yxatda"
          icon={Users}
          accent="bg-green-500"
          onClick={() => navigate('/animals')}
        />
        <StatCard
          label="Aniqlashlar"
          value={stats.totalDetections}
          sub="jami"
          icon={Camera}
          accent="bg-blue-500"
        />
        <StatCard
          label="O'rtacha vazn"
          value={stats.avgWeight === '—' ? '—' : `${stats.avgWeight} kg`}
          sub="sessiya"
          icon={Scale}
          accent="bg-purple-500"
        />
        <StatCard
          label="Pipeline"
          value={pipeline.running ? 'Ishlaydi' : "To'xtatilgan"}
          sub={pipeline.stats ? `${(pipeline.stats.fps ?? 0).toFixed(1)} FPS` : '—'}
          icon={Activity}
          accent={pipeline.running ? 'bg-green-500' : 'bg-gray-400'}
        />
      </div>

      {/* Pipeline Stats (if running) */}
      {pipeline.running && pipeline.stats && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Pipeline — real vaqt
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: 'Kadrlar', val: pipeline.stats.total_frames },
              { label: 'Qayta isl.', val: pipeline.stats.processed_frames },
              { label: 'Aniqlash', val: pipeline.stats.detections },
              { label: 'Saqlangan', val: pipeline.stats.measurements_created },
              { label: 'Xato', val: pipeline.stats.errors },
            ].map(({ label, val }) => (
              <div key={label} className="bg-gray-50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-gray-900">{val}</div>
                <div className="text-xs text-gray-500 mt-1">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Measurements */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Oxirgi O'lchovlar</h3>
          <TrendingUp className="w-5 h-5 text-gray-400" />
        </div>

        {measurements.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            Pipeline ishga tushirilganda o'lchovlar shu yerda ko'rinadi
          </div>
        ) : (
          <div className="space-y-2">
            {measurements.map((m, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 rounded-lg px-3 cursor-pointer transition-colors"
                onClick={() => navigate(`/animals/${m.animal_id}`)}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-50 rounded-full flex items-center justify-center">
                    <Scale className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-gray-900">
                      {m.animal_tag_id}
                    </div>
                    <div className="text-xs text-gray-500">{m.camera_id}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold text-gray-900">
                    {m.estimated_weight_kg.toFixed(1)} kg
                  </div>
                  <div className="text-xs text-gray-400">
                    {(m.confidence_score * 100).toFixed(0)}% ishonch
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}