import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Activity, Scale, Camera, Play, Square,
  AlertCircle, TrendingUp, Users, RefreshCw,
  Plus, X, ChevronRight, Pencil, Trash2,
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
  breed?: string;
  notes?: string;
  acquisition_date?: string;
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

interface WeightMeasurement {
  id: number;
  animal_id: number;
  estimated_weight_kg: number;
  confidence_score: number;
  camera_id: string;
  timestamp: string;
}

type Tab = 'dashboard' | 'animals' | 'live';

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
// Weight SVG Chart
// ---------------------------------------------------------------------------

function WeightChart({ data }: { data: WeightMeasurement[] }) {
  if (data.length < 2) {
    return (
      <div className="h-20 flex items-center justify-center text-gray-400 text-sm">
        Grafik uchun kamida 2 ta o'lchov kerak
      </div>
    );
  }
  const pts = [...data].slice(0, 20).reverse();
  const weights = pts.map(d => d.estimated_weight_kg);
  const min = Math.min(...weights);
  const max = Math.max(...weights);
  const range = max - min || 1;
  const W = 400, H = 80, pad = 10;
  const points = pts.map((_, i) => {
    const x = pad + (i / (pts.length - 1)) * (W - pad * 2);
    const y = H - pad - ((weights[i] - min) / range) * (H - pad * 2);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-20">
        <polyline
          points={points}
          fill="none"
          stroke="#16a34a"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {pts.map((d, i) => {
          const x = pad + (i / (pts.length - 1)) * (W - pad * 2);
          const y = H - pad - ((weights[i] - min) / range) * (H - pad * 2);
          return (
            <circle key={d.id} cx={x} cy={y} r="3.5" fill="#16a34a" opacity="0.85">
              <title>{weights[i].toFixed(1)} kg</title>
            </circle>
          );
        })}
      </svg>
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{min.toFixed(0)} kg min</span>
        <span className="text-gray-500">Oxirgi {pts.length} o'lchov</span>
        <span>{max.toFixed(0)} kg max</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add / Edit Modal
// ---------------------------------------------------------------------------

interface AnimalFormData {
  tag_id: string;
  species: string;
  gender: string;
  acquisition_date: string;
  breed: string;
  notes: string;
}

interface AnimalModalProps {
  initial?: Animal;          // agar bor bo'lsa — edit mode
  onClose: () => void;
  onSaved: () => void;
}

function AnimalModal({ initial, onClose, onSaved }: AnimalModalProps) {
  const isEdit = Boolean(initial);

  const [form, setForm] = useState<AnimalFormData>({
    tag_id:           initial?.tag_id           ?? '',
    species:          initial?.species           ?? 'cattle',
    gender:           initial?.gender            ?? 'male',
    acquisition_date: initial?.acquisition_date
      ? initial.acquisition_date.split('T')[0]
      : new Date().toISOString().split('T')[0],
    breed:  initial?.breed  ?? '',
    notes:  initial?.notes  ?? '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const set = (key: keyof AnimalFormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm(p => ({ ...p, [key]: key === 'tag_id' ? e.target.value.toUpperCase() : e.target.value }));

  const handleSubmit = async () => {
    if (!form.tag_id.trim()) { setError('Tag ID kiritilishi shart'); return; }
    setLoading(true); setError('');
    try {
      const body = {
        ...form,
        acquisition_date: `${form.acquisition_date}T00:00:00`,
        breed: form.breed || undefined,
        notes: form.notes || undefined,
      };
      if (isEdit) {
        await apiFetch(`/api/v1/animals/${initial!.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      } else {
        await apiFetch('/api/v1/animals/', { method: 'POST', body: JSON.stringify(body) });
      }
      onSaved(); onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Xato');
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">
            {isEdit ? `Tahrirlash — ${initial!.tag_id}` : "Yangi jonivor qo'shish"}
          </h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
            </div>
          )}

          {/* Tag ID */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Tag ID *</label>
            <input
              type="text"
              placeholder="JNV-001"
              value={form.tag_id}
              onChange={set('tag_id')}
              disabled={isEdit}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 font-mono disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          {/* Tur + Jins */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Tur</label>
              <select value={form.species} onChange={set('species')}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                <option value="cattle">Qoramol</option>
                <option value="sheep">Qo'y</option>
                <option value="goat">Echki</option>
                <option value="horse">Ot</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Jins</label>
              <select value={form.gender} onChange={set('gender')}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                <option value="male">Erkak</option>
                <option value="female">Urg'ochi</option>
                <option value="unknown">Noma'lum</option>
              </select>
            </div>
          </div>

          {/* Status (faqat edit da) */}
          {isEdit && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Holat</label>
              <select value={form.species} onChange={set('species')}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                <option value="active">Faol</option>
                <option value="quarantine">Karantin</option>
                <option value="sick">Kasal</option>
                <option value="sold">Sotilgan</option>
                <option value="deceased">Vafot etgan</option>
              </select>
            </div>
          )}

          {/* Zot */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Zot (ixtiyoriy)</label>
            <input type="text" placeholder="Masalan: Simmental" value={form.breed} onChange={set('breed')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>

          {/* Sana */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Kelgan sana</label>
            <input type="date" value={form.acquisition_date} onChange={set('acquisition_date')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>

          {/* Izoh */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Izoh (ixtiyoriy)</label>
            <textarea rows={2} placeholder="..." value={form.notes} onChange={set('notes')}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 resize-none" />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <button onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            Bekor
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="flex-1 px-4 py-2 bg-green-600 rounded-lg text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors">
            {loading ? 'Saqlanmoqda...' : isEdit ? 'Saqlash' : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete Confirm
// ---------------------------------------------------------------------------

function DeleteConfirm({ animal, onClose, onDeleted }: {
  animal: Animal; onClose: () => void; onDeleted: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const handleDelete = async () => {
    setLoading(true);
    try {
      await apiFetch(`/api/v1/animals/${animal.id}`, { method: 'DELETE' });
      onDeleted(); onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Xato');
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="px-6 py-5 text-center">
          <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Trash2 className="w-5 h-5 text-red-500" />
          </div>
          <h2 className="text-base font-semibold text-gray-900 mb-1">O'chirishni tasdiqlang</h2>
          <p className="text-sm text-gray-500">
            <span className="font-mono font-medium text-gray-700">{animal.tag_id}</span> — bu jonivorni
            o'chirsangiz, barcha ma'lumotlari ham o'chib ketadi.
          </p>
          {error && (
            <div className="mt-3 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
            </div>
          )}
        </div>
        <div className="px-6 pb-5 flex gap-3">
          <button onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            Bekor
          </button>
          <button onClick={handleDelete} disabled={loading}
            className="flex-1 px-4 py-2 bg-red-600 rounded-lg text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors">
            {loading ? "O'chirilmoqda..." : "Ha, o'chirish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animal Detail Panel
// ---------------------------------------------------------------------------

function AnimalDetail({ animal, onClose, onEdit, onDelete }: {
  animal: Animal;
  onClose: () => void;
  onEdit: (a: Animal) => void;
  onDelete: (a: Animal) => void;
}) {
  const [history, setHistory]   = useState<WeightMeasurement[]>([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    apiFetch<{ items: WeightMeasurement[] }>(
      `/api/v1/weights/animal/${animal.id}?limit=20&min_confidence=0.5`
    )
      .then(d => setHistory(d.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [animal.id]);

  const lastWeight = history[0]?.estimated_weight_kg;
  const avgWeight  = history.length
    ? (history.reduce((s, m) => s + m.estimated_weight_kg, 0) / history.length).toFixed(1)
    : null;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-semibold text-gray-800 font-mono">{animal.tag_id}</h2>
            <p className="text-xs text-gray-400 capitalize">{animal.species} · {animal.gender}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { onClose(); onEdit(animal); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />Tahrirlash
            </button>
            <button
              onClick={() => { onClose(); onDelete(animal); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />O'chirish
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg ml-1">
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Oxirgi vazn', val: lastWeight ? `${lastWeight.toFixed(1)} kg` : '—' },
              { label: "O'rtacha",    val: avgWeight  ? `${avgWeight} kg`              : '—' },
              { label: 'Aniqlashlar', val: animal.total_detections },
            ].map(({ label, val }) => (
              <div key={label} className="bg-gray-50 rounded-xl p-3 text-center">
                <div className="text-lg font-bold text-gray-900">{val}</div>
                <div className="text-xs text-gray-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Vazn tarixi
            </h3>
            {loading
              ? <div className="h-20 flex items-center justify-center text-gray-400 text-sm">Yuklanmoqda...</div>
              : <WeightChart data={history} />
            }
          </div>

          {/* Last measurements */}
          {history.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Oxirgi o'lchovlar
              </h3>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {history.slice(0, 8).map(m => (
                  <div key={m.id} className="flex justify-between items-center py-1.5 border-b border-gray-50 last:border-0">
                    <div className="flex items-center gap-2">
                      <Scale className="w-3.5 h-3.5 text-green-500" />
                      <span className="text-sm font-medium text-gray-800">{m.estimated_weight_kg.toFixed(1)} kg</span>
                      <span className="text-xs text-gray-400">{(m.confidence_score * 100).toFixed(0)}%</span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(m.timestamp).toLocaleString('uz-UZ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          {animal.notes && (
            <div className="bg-yellow-50 border border-yellow-100 rounded-xl px-4 py-3">
              <p className="text-xs text-yellow-700 font-medium mb-1">Izoh</p>
              <p className="text-sm text-yellow-900">{animal.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub, icon: Icon, accent }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-start gap-4">
      <div className={`p-2 rounded-lg ${accent}`}><Icon className="w-5 h-5 text-white" /></div>
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
    active:      'bg-green-100 text-green-700',
    quarantine:  'bg-yellow-100 text-yellow-700',
    sick:        'bg-red-100 text-red-700',
    sold:        'bg-gray-100 text-gray-500',
    deceased:    'bg-gray-100 text-gray-400',
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
  const [tab, setTab] = useState<Tab>('dashboard');

  // Animals state
  const [animals, setAnimals]           = useState<Animal[]>([]);
  const [animalTotal, setAnimalTotal]   = useState(0);
  const [animalsLoading, setAnimalsLoading] = useState(false);
  const [animalsError, setAnimalsError] = useState('');

  // Modals
  const [showAddModal, setShowAddModal]       = useState(false);
  const [editAnimal, setEditAnimal]           = useState<Animal | null>(null);
  const [deleteAnimal, setDeleteAnimal]       = useState<Animal | null>(null);
  const [selectedAnimal, setSelectedAnimal]   = useState<Animal | null>(null);

  // Live feed
  const [measurements, setMeasurements] = useState<LiveWeightUpdate[]>([]);
  const [newId, setNewId]               = useState<number | null>(null);

  // Pipeline
  const [pipeline, setPipeline]             = useState<PipelineStatus>({ status: 'not_initialized', running: false });
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineError, setPipelineError]   = useState('');

  // WebSocket
  const wsOptions = useMemo(() => ({
    onMessage: (msg: { type: string; data?: LiveWeightUpdate }) => {
      if (msg.type === 'weight_update' && msg.data) {
        setMeasurements(prev => [msg.data!, ...prev].slice(0, config.ui.maxRecentMeasurements));
        setNewId(msg.data.animal_id);
        setTimeout(() => setNewId(null), 2000);
      }
    },
  }), []);

  const { status: wsStatus } = useWebSocket(`${config.wsUrl}/api/v1/live/ws`, wsOptions);

  // Fetch animals
  const loadAnimals = useCallback(async () => {
    setAnimalsLoading(true); setAnimalsError('');
    try {
      const data = await apiFetch<AnimalListResponse>('/api/v1/animals/?limit=100');
      setAnimals(data.items); setAnimalTotal(data.total);
    } catch (e: unknown) {
      setAnimalsError(e instanceof Error ? e.message : 'Xato');
    } finally { setAnimalsLoading(false); }
  }, []);

  // Fetch pipeline
  const loadPipeline = useCallback(async () => {
    try { setPipeline(await apiFetch<PipelineStatus>('/api/v1/pipeline/status')); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadAnimals(); loadPipeline();
    const t = setInterval(loadPipeline, 5000);
    return () => clearInterval(t);
  }, [loadAnimals, loadPipeline]);

  // Pipeline toggle
  const togglePipeline = async () => {
    setPipelineLoading(true); setPipelineError('');
    try {
      await apiFetch(pipeline.running ? '/api/v1/pipeline/stop' : '/api/v1/pipeline/start', { method: 'POST' });
      await loadPipeline();
    } catch (e: unknown) {
      setPipelineError(e instanceof Error ? e.message : 'Xato');
    } finally { setPipelineLoading(false); }
  };

  // Stats
  const activeAnimals  = animals.filter(a => a.status === 'active').length;
  const totalDetections = animals.reduce((s, a) => s + a.total_detections, 0);
  const avgWeight = measurements.length
    ? (measurements.reduce((s, m) => s + m.estimated_weight_kg, 0) / measurements.length).toFixed(1)
    : '—';

  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-gray-50">

      {/* ── Modals ── */}
      {showAddModal && (
        <AnimalModal onClose={() => setShowAddModal(false)} onSaved={loadAnimals} />
      )}
      {editAnimal && (
        <AnimalModal initial={editAnimal} onClose={() => setEditAnimal(null)} onSaved={loadAnimals} />
      )}
      {deleteAnimal && (
        <DeleteConfirm
          animal={deleteAnimal}
          onClose={() => setDeleteAnimal(null)}
          onDeleted={loadAnimals}
        />
      )}
      {selectedAnimal && (
        <AnimalDetail
          animal={selectedAnimal}
          onClose={() => setSelectedAnimal(null)}
          onEdit={a => { setSelectedAnimal(null); setEditAnimal(a); }}
          onDelete={a => { setSelectedAnimal(null); setDeleteAnimal(a); }}
        />
      )}

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
            <button
              onClick={togglePipeline}
              disabled={pipelineLoading}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                pipeline.running
                  ? 'bg-red-50 text-red-600 hover:bg-red-100'
                  : 'bg-green-50 text-green-700 hover:bg-green-100'
              }`}
            >
              {pipelineLoading
                ? <RefreshCw className="w-4 h-4 animate-spin" />
                : pipeline.running ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {pipeline.running ? 'Stop' : 'Start'}
            </button>
          </div>
        </div>
      </header>

      {pipelineError && (
        <div className="max-w-7xl mx-auto px-6 pt-3">
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />{pipelineError}
          </div>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="border-b border-gray-200 bg-white sticky top-[57px] z-10">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-1">
            {([
              { key: 'dashboard', label: 'Dashboard',    badge: null,                  badgeCls: '' },
              { key: 'animals',   label: 'Jonivorlar',   badge: animalTotal || null,   badgeCls: 'bg-gray-100 text-gray-600' },
              { key: 'live',      label: 'Live Feed',    badge: measurements.length || null, badgeCls: 'bg-green-100 text-green-700' },
            ] as const).map(({ key, label, badge, badgeCls }) => (
              <button key={key} onClick={() => setTab(key as Tab)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === key ? 'border-green-600 text-green-700' : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}>
                {label}
                {badge != null && (
                  <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${badgeCls}`}>{badge}</span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Main ── */}
      <main className="max-w-7xl mx-auto px-6 py-6">

        {/* DASHBOARD */}
        {tab === 'dashboard' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Jonivorlar"    value={animalTotal}  sub={`${activeAnimals} faol`} icon={Users}    accent="bg-green-500" />
              <StatCard label="Aniqlashlar"   value={totalDetections} sub="jami"               icon={Camera}   accent="bg-blue-500" />
              <StatCard label="O'rtacha vazn" value={avgWeight === '—' ? '—' : `${avgWeight} kg`} sub="sessiya" icon={Scale}    accent="bg-purple-500" />
              <StatCard
                label="Pipeline"
                value={pipeline.running ? 'Ishlaydi' : "To'xtatilgan"}
                sub={pipeline.stats ? `${(pipeline.stats.fps ?? 0).toFixed(1)} FPS` : '—'}
                icon={Activity}
                accent={pipeline.running ? 'bg-green-500' : 'bg-gray-400'}
              />
            </div>

            {pipeline.running && pipeline.stats && (
              <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline — real vaqt</h3>
                <div className="grid grid-cols-5 gap-3 text-center">
                  {[
                    { label: 'Kadrlar',    val: pipeline.stats.total_frames },
                    { label: 'Qayta isl.', val: pipeline.stats.processed_frames },
                    { label: 'Aniqlash',   val: pipeline.stats.detections },
                    { label: 'Saqlangan',  val: pipeline.stats.measurements_created },
                    { label: 'Xato',       val: pipeline.stats.errors },
                  ].map(({ label, val }) => (
                    <div key={label} className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xl font-bold text-gray-900">{val}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-700">Oxirgi o'lchovlar</h3>
                <TrendingUp className="w-4 h-4 text-gray-400" />
              </div>
              {measurements.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-sm">
                  Pipeline ishga tushirilganda o'lchovlar shu yerda ko'rinadi
                </div>
              ) : (
                <div className="space-y-1">
                  {measurements.slice(0, 8).map((m, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 bg-green-50 rounded-full flex items-center justify-center">
                          <Scale className="w-3.5 h-3.5 text-green-600" />
                        </div>
                        <span className="text-sm font-medium text-gray-800">{m.animal_tag_id}</span>
                        <span className="text-xs text-gray-400">{m.camera_id}</span>
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

        {/* ANIMALS */}
        {tab === 'animals' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                Jonivorlar — jami {animalTotal}
              </h2>
              <div className="flex items-center gap-2">
                <button onClick={loadAnimals}
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                  <RefreshCw className={`w-4 h-4 ${animalsLoading ? 'animate-spin' : ''}`} />
                </button>
                <button onClick={() => setShowAddModal(true)}
                  className="flex items-center gap-1.5 bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
                  <Plus className="w-4 h-4" />Qo'shish
                </button>
              </div>
            </div>

            {animalsError && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                <AlertCircle className="w-4 h-4" />{animalsError}
              </div>
            )}

            {animalsLoading && !animals.length ? (
              <div className="text-center py-16 text-gray-400 text-sm">Yuklanmoqda...</div>
            ) : animals.length === 0 ? (
              <div className="text-center py-16">
                <Users className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 text-sm">Hali jonivor qo'shilmagan</p>
                <button onClick={() => setShowAddModal(true)}
                  className="mt-3 inline-flex items-center gap-1.5 bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700">
                  <Plus className="w-4 h-4" />Birinchi jonivorniqo'shish
                </button>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      {["Tag ID", "Tur", "Jins", "Holat", "Aniqlash", "Oxirgi ko'rinish", ""].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {animals.map(a => (
                      <tr key={a.id}
                        className="border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer group"
                        onClick={() => setSelectedAnimal(a)}
                      >
                        <td className="px-4 py-3 font-mono font-medium text-gray-900">{a.tag_id}</td>
                        <td className="px-4 py-3 text-gray-600 capitalize">{a.species}</td>
                        <td className="px-4 py-3 text-gray-600 capitalize">{a.gender}</td>
                        <td className="px-4 py-3"><AnimalBadge status={a.status} /></td>
                        <td className="px-4 py-3 text-gray-700 font-medium">{a.total_detections}</td>
                        <td className="px-4 py-3 text-gray-400 text-xs">
                          {a.last_detected_at ? new Date(a.last_detected_at).toLocaleString('uz-UZ') : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={e => { e.stopPropagation(); setEditAnimal(a); }}
                              className="p-1.5 text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
                              title="Tahrirlash"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={e => { e.stopPropagation(); setDeleteAnimal(a); }}
                              className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                              title="O'chirish"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* LIVE FEED */}
        {tab === 'live' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">
                Live Feed
                {measurements.length > 0 && (
                  <span className="ml-2 text-xs text-gray-400 font-normal">{measurements.length} o'lchov</span>
                )}
              </h2>
              {wsStatus === WsStatus.CONNECTED && (
                <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse inline-block" />Jonli
                </span>
              )}
            </div>
            {measurements.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                {pipeline.running
                  ? "Pipeline ishlaydi — birinchi o'lchovni kutmoqda..."
                  : "Pipeline to'xtatilgan. Yuqoridagi Start tugmasini bosing."}
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