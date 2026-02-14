import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Activity, Scale, Camera, Play, Square,
  AlertCircle, TrendingUp, Users, RefreshCw,
} from 'lucide-react';
import { useWebSocket } from './shared/hooks/useWebSocket';
import { ConnectionStatus } from './shared/components/ConnectionStatus';
import { LiveFeedCard } from './features/live-feed/components/LiveFeedCard';
import { ConnectionStatus as WsStatus, type LiveWeightUpdate } from './shared/types';
import config from './config';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Animal {
  id: number;
  tag_id: string;
  species: string;
  gender: string;
  status: string;
  total_detections: number;
  last_detected_at: string | null;
}

interface AnimalListResponse {
  items: Animal[];
  total: number;
  skip: number;
  limit: number;
}

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

type Tab = 'dashboard' | 'animals' | 'live';

// ---------------------------------------------------------------------------
// API helpers
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
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label, value, sub, icon: Icon, accent,
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-start gap-4">
      <div className={`p-2 rounded-lg ${accent}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 leading-tight">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function AnimalBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: 'bg-green-100 text-green-700',
    quarantine: 'bg-yellow-100 text-yellow-700',
    sick: 'bg-red-100 text-red-700',
    sold: 'bg-gray-100 text-gray-500',
    deceased: 'bg-gray-100 text-gray-400',
    transferred: 'bg-blue-100 text-blue-700',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  // ---- state ----
  const [tab, setTab] = useState<Tab>('dashboard');
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [animalTotal, setAnimalTotal] = useState(0);
  const [animalsLoading, setAnimalsLoading] = useState(false);
  const [animalsError, setAnimalsError] = useState('');

  const [measurements, setMeasurements] = useState<LiveWeightUpdate[]>([]);
  const [newId, setNewId] = useState<number | null>(null);

  const [pipeline, setPipeline] = useState<PipelineStatus>({ status: 'not_initialized', running: false });
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineError, setPipelineError] = useState('');

  // ---- WebSocket ----
  const wsOptions = useMemo(() => ({
    onMessage: (msg: { type: string; data?: LiveWeightUpdate }) => {
      if (msg.type === 'weight_update' && msg.data) {
        setMeasurements(prev => {
          const next = [msg.data!, ...prev];
          return next.slice(0, config.ui.maxRecentMeasurements);
        });
        setNewId(msg.data.animal_id);
        setTimeout(() => setNewId(null), 2000);
      }
    },
  }), []);

  const { status: wsStatus } = useWebSocket(
    `${config.wsUrl}/api/v1/live/ws`,
    wsOptions,
  );

  // ---- fetch animals ----
  const loadAnimals = useCallback(async () => {
    setAnimalsLoading(true);
    setAnimalsError('');
    try {
      const data = await apiFetch<AnimalListResponse>('/api/v1/animals/?limit=100');
      setAnimals(data.items);
      setAnimalTotal(data.total);
    } catch (e: unknown) {
      setAnimalsError(e instanceof Error ? e.message : 'Xato');
    } finally {
      setAnimalsLoading(false);
    }
  }, []);

  // ---- fetch pipeline status ----
  const loadPipeline = useCallback(async () => {
    try {
      const data = await apiFetch<PipelineStatus>('/api/v1/pipeline/status');
      setPipeline(data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadAnimals();
    loadPipeline();
    const t = setInterval(loadPipeline, 5000);
    return () => clearInterval(t);
  }, [loadAnimals, loadPipeline]);

  // ---- pipeline start / stop ----
  const togglePipeline = async () => {
    setPipelineLoading(true);
    setPipelineError('');
    try {
      if (pipeline.running) {
        await apiFetch('/api/v1/pipeline/stop', { method: 'POST' });
      } else {
        await apiFetch('/api/v1/pipeline/start', { method: 'POST' });
      }
      await loadPipeline();
    } catch (e: unknown) {
      setPipelineError(e instanceof Error ? e.message : 'Xato');
    } finally {
      setPipelineLoading(false);
    }
  };

  // ---- derived stats ----
  const activeAnimals = animals.filter(a => a.status === 'active').length;
  const totalDetections = animals.reduce((s, a) => s + a.total_detections, 0);
  const avgWeight = measurements.length
    ? (measurements.reduce((s, m) => s + m.estimated_weight_kg, 0) / measurements.length).toFixed(1)
    : '—';

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-gray-50">

      {/* ── Header ── */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-green-600 p-2 rounded-lg">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900">Taurus Vision</span>
            <span className="text-xs text-gray-400 font-mono hidden sm:block">v0.1.0</span>
          </div>
          <div className="flex items-center gap-3">
            <ConnectionStatus status={wsStatus} />
            {/* Pipeline toggle */}
            <button
              onClick={togglePipeline}
              disabled={pipelineLoading}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${pipeline.running
                ? 'bg-red-50 text-red-600 hover:bg-red-100'
                : 'bg-green-50 text-green-700 hover:bg-green-100'
                } disabled:opacity-50`}
            >
              {pipelineLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : pipeline.running ? (
                <Square className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {pipeline.running ? 'Stop' : 'Start'} Pipeline
            </button>
          </div>
        </div>
      </header>

      {/* ── Pipeline error ── */}
      {pipelineError && (
        <div className="max-w-7xl mx-auto px-6 pt-4">
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {pipelineError}
          </div>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="border-b border-gray-200 bg-white sticky top-[57px] z-10">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-1">
            {(['dashboard', 'animals', 'live'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${tab === t
                  ? 'border-green-600 text-green-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
              >
                {t === 'live' ? 'Live Feed' : t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Main ── */}
      <main className="max-w-7xl mx-auto px-6 py-6">

        {/* ══ DASHBOARD TAB ══ */}
        {tab === 'dashboard' && (
          <div className="space-y-6">

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Jonivorlar" value={animalTotal} sub={`${activeAnimals} faol`} icon={Users} accent="bg-green-500" />
              <StatCard label="Jami aniqlash" value={totalDetections} sub="barcha vaqt" icon={Camera} accent="bg-blue-500" />
              <StatCard label="O'rtacha vazn" value={avgWeight === '—' ? '—' : `${avgWeight} kg`} sub="live sessiya" icon={Scale} accent="bg-purple-500" />
              <StatCard
                label="Pipeline"
                value={pipeline.running ? 'Ishlaydi' : 'To\'xtatilgan'}
                sub={pipeline.stats ? `${pipeline.stats.fps?.toFixed(1) ?? 0} FPS` : 'hozir faol emas'}
                icon={Activity}
                accent={pipeline.running ? 'bg-green-500' : 'bg-gray-400'}
              />
            </div>

            {/* Pipeline stats */}
            {pipeline.running && pipeline.stats && (
              <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline — real vaqt statistika</h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                  {[
                    { label: 'Kadrlar', val: pipeline.stats.total_frames },
                    { label: 'Qayta ishlangan', val: pipeline.stats.processed_frames },
                    { label: 'Aniqlashlar', val: pipeline.stats.detections },
                    { label: 'Saqlangan', val: pipeline.stats.measurements_created },
                    { label: 'Xatoliklar', val: pipeline.stats.errors },
                  ].map(({ label, val }) => (
                    <div key={label} className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xl font-bold text-gray-900">{val}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Last 5 measurements */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-700">Oxirgi o'lchovlar</h3>
                <TrendingUp className="w-4 h-4 text-gray-400" />
              </div>
              {measurements.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-sm">
                  Pipeline ishga tushirilganda o'lchovlar bu yerda ko'rinadi
                </div>
              ) : (
                <div className="space-y-2">
                  {measurements.slice(0, 5).map((m, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-50 rounded-full flex items-center justify-center">
                          <Scale className="w-4 h-4 text-green-600" />
                        </div>
                        <div>
                          <span className="text-sm font-medium text-gray-800">{m.animal_tag_id}</span>
                          <span className="text-xs text-gray-400 ml-2">{m.camera_id}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-gray-900">{m.estimated_weight_kg.toFixed(1)} kg</span>
                        <div className="text-xs text-gray-400">{(m.confidence_score * 100).toFixed(0)}% ishonch</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* ══ ANIMALS TAB ══ */}
        {tab === 'animals' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                Jonivorlar — jami {animalTotal}
              </h2>
              <button
                onClick={loadAnimals}
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
              >
                <RefreshCw className={`w-4 h-4 ${animalsLoading ? 'animate-spin' : ''}`} />
                Yangilash
              </button>
            </div>

            {animalsError && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                <AlertCircle className="w-4 h-4" />
                {animalsError}
              </div>
            )}

            {animalsLoading && !animals.length ? (
              <div className="text-center py-16 text-gray-400 text-sm">Yuklanmoqda...</div>
            ) : animals.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                Hali birorta jonivor qo'shilmagan.
                <br />
                <span className="text-xs mt-1 block">
                  POST /api/v1/animals/ orqali qo'shing yoki{' '}
                  <a href={`${config.apiUrl}/docs`} target="_blank" rel="noreferrer" className="text-green-600 underline">
                    Swagger UI
                  </a>
                </span>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      {['Tag ID', 'Tur', 'Jins', 'Holat', 'Aniqlashlar', 'Oxirgi ko\'rinish'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {animals.map(a => (
                      <tr key={a.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-mono font-medium text-gray-900">{a.tag_id}</td>
                        <td className="px-4 py-3 text-gray-600 capitalize">{a.species}</td>
                        <td className="px-4 py-3 text-gray-600 capitalize">{a.gender}</td>
                        <td className="px-4 py-3"><AnimalBadge status={a.status} /></td>
                        <td className="px-4 py-3 text-gray-700 font-medium">{a.total_detections}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs">
                          {a.last_detected_at
                            ? new Date(a.last_detected_at).toLocaleString('uz-UZ')
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ══ LIVE FEED TAB ══ */}
        {tab === 'live' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                Live Feed
                {measurements.length > 0 && (
                  <span className="ml-2 text-xs text-gray-400 font-normal">
                    {measurements.length} o'lchov
                  </span>
                )}
              </h2>
              {wsStatus === WsStatus.CONNECTED ? (
                <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse inline-block" />
                  Jonli
                </span>
              ) : null}
            </div>

            {measurements.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                {pipeline.running
                  ? 'Pipeline ishlaydi — birinchi o\'lchovni kutmoqda...'
                  : 'Pipeline to\'xtatilgan. Yuqoridagi "Start Pipeline" tugmasini bosing.'}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {measurements.map((m, i) => (
                  <LiveFeedCard
                    key={`${m.animal_id}-${m.timestamp}-${i}`}
                    measurement={m}
                    isNew={m.animal_id === newId && i === 0}
                  />
                ))}
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}