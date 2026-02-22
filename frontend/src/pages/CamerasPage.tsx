/**
 * Cameras Page
 * 
 * Manage and monitor camera sources
 */

import { useState, useEffect } from 'react';
import {
  Camera,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  Video,
  Settings,
  Trash2,
} from 'lucide-react';
import config from '../config';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CameraConfig {
  id: string;
  name: string;
  type: 'usb' | 'rtsp' | 'simulated';
  source?: string;
  device_id?: number;
  fps?: number;
  enabled: boolean;
  status?: 'active' | 'inactive' | 'error';
}

interface CameraStatus {
  camera_id: string;
  is_active: boolean;
  fps: number;
  frames_captured: number;
  last_frame_time: string | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const API = config.apiUrl;

// ---------------------------------------------------------------------------
// Add Camera Modal
// ---------------------------------------------------------------------------

function AddCameraModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: '',
    type: 'simulated' as 'usb' | 'rtsp' | 'simulated',
    source: '',
    device_id: 0,
    fps: 10,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit() {
    if (!form.name.trim()) {
      setError('Kamera nomi kiritilishi shart');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const body: any = {
        name: form.name,
        type: form.type,
        fps: form.fps,
        enabled: true,
      };

      if (form.type === 'rtsp') {
        body.source = form.source;
      } else if (form.type === 'usb') {
        body.device_id = form.device_id;
      }

      await apiFetch('/api/v1/cameras/', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Yangi kamera qo'shish</h2>
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kamera nomi *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="Kirish eshigi kamerasi"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kamera turi
            </label>
            <select
              value={form.type}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  type: e.target.value as 'usb' | 'rtsp' | 'simulated',
                }))
              }
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="simulated">Simulated (Test)</option>
              <option value="usb">USB Camera</option>
              <option value="rtsp">RTSP Stream</option>
            </select>
          </div>

          {form.type === 'rtsp' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                RTSP URL
              </label>
              <input
                type="text"
                value={form.source}
                onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}
                placeholder="rtsp://192.168.1.100:554/stream"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              />
            </div>
          )}

          {form.type === 'usb' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Device ID
              </label>
              <input
                type="number"
                value={form.device_id}
                onChange={(e) =>
                  setForm((p) => ({ ...p, device_id: parseInt(e.target.value) || 0 }))
                }
                min="0"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Odatda 0 (birinchi kamera)
              </p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              FPS (Frames per second)
            </label>
            <input
              type="number"
              value={form.fps}
              onChange={(e) =>
                setForm((p) => ({ ...p, fps: parseInt(e.target.value) || 10 }))
              }
              min="1"
              max="30"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Tavsiya: 10-15 FPS (yuqori FPS ko'proq resurs talab qiladi)
            </p>
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Bekor qilish
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Qo'shilmoqda..." : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Camera Card
// ---------------------------------------------------------------------------

function CameraCard({
  camera,
  status,
  onDelete,
}: {
  camera: CameraConfig;
  status?: CameraStatus;
  onDelete: () => void;
}) {
  const isActive = status?.is_active ?? false;
  const hasError = status?.error != null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-lg ${
              isActive
                ? 'bg-green-100'
                : hasError
                ? 'bg-red-100'
                : 'bg-gray-100'
            }`}
          >
            <Camera
              className={`w-6 h-6 ${
                isActive
                  ? 'text-green-600'
                  : hasError
                  ? 'text-red-600'
                  : 'text-gray-400'
              }`}
            />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{camera.name}</h3>
            <p className="text-sm text-gray-500 capitalize">{camera.type}</p>
          </div>
        </div>

        <button
          onClick={onDelete}
          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="O'chirish"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Status */}
      <div className="space-y-2">
        <div className="flex items-center justify-between py-2 border-t border-gray-100">
          <span className="text-sm text-gray-600">Holat</span>
          <div className="flex items-center gap-2">
            {isActive ? (
              <CheckCircle className="w-4 h-4 text-green-600" />
            ) : hasError ? (
              <XCircle className="w-4 h-4 text-red-600" />
            ) : (
              <XCircle className="w-4 h-4 text-gray-400" />
            )}
            <span className="text-sm font-medium text-gray-900">
              {isActive ? 'Faol' : hasError ? 'Xatolik' : 'Nofaol'}
            </span>
          </div>
        </div>

        {status && (
          <>
            <div className="flex items-center justify-between py-2 border-t border-gray-100">
              <span className="text-sm text-gray-600">FPS</span>
              <span className="text-sm font-medium text-gray-900">
                {status.fps.toFixed(1)}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-t border-gray-100">
              <span className="text-sm text-gray-600">Kadrlar</span>
              <span className="text-sm font-medium text-gray-900">
                {status.frames_captured}
              </span>
            </div>
          </>
        )}

        {camera.type === 'rtsp' && camera.source && (
          <div className="py-2 border-t border-gray-100">
            <span className="text-sm text-gray-600 block mb-1">URL</span>
            <code className="text-xs text-gray-900 bg-gray-50 px-2 py-1 rounded block overflow-x-auto">
              {camera.source}
            </code>
          </div>
        )}

        {hasError && status?.error && (
          <div className="py-2 border-t border-gray-100">
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-2">
              <AlertCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-700">{status.error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function CamerasPage() {
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [statuses, setStatuses] = useState<Record<string, CameraStatus>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  // ---------------------------------------------------------------------------
  // Load Data
  // ---------------------------------------------------------------------------

  useEffect(() => {
    loadCameras();
    const interval = setInterval(loadCameraStatuses, 3000);
    return () => clearInterval(interval);
  }, []);

  async function loadCameras() {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch<CameraConfig[]>('/api/v1/cameras/');
      setCameras(data);
      await loadCameraStatuses();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  async function loadCameraStatuses() {
    try {
      const data = await apiFetch<Record<string, CameraStatus>>('/api/v1/cameras/stats/all');
      setStatuses(data ?? {});
    } catch (err) {
      console.error('Status load error:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // Delete Handler
  // ---------------------------------------------------------------------------

  async function handleDelete(camera: CameraConfig) {
    const confirmed = window.confirm(
      `${camera.name} kamerasini o'chirishga ishonchingiz komilmi?`
    );
    if (!confirmed) return;

    try {
      await apiFetch(`/api/v1/cameras/${camera.id}`, { method: 'DELETE' });
      loadCameras();
    } catch (err) {
      alert('O\'chirish xatolik: ' + (err instanceof Error ? err.message : ''));
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
          <h1 className="text-3xl font-bold text-gray-900">Kameralar</h1>
          <p className="text-gray-600 mt-1">
            {cameras.length} ta kamera manbai
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadCameras}
            disabled={loading}
            className="p-2.5 text-gray-600 hover:text-gray-900 hover:bg-white border border-gray-300 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Plus className="w-5 h-5" />
            Kamera qo'shish
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && cameras.length === 0 ? (
        <div className="text-center py-16 text-gray-400">Yuklanmoqda...</div>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16">
          <Video className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 text-lg mb-2">Hali kamera qo'shilmagan</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-4 inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700"
          >
            <Plus className="w-5 h-5" />
            Birinchi kamerani qo'shish
          </button>
        </div>
      ) : (
        /* Camera Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cameras.map((camera) => (
            <CameraCard
              key={camera.id}
              camera={camera}
              status={statuses[camera.id]}
              onDelete={() => handleDelete(camera)}
            />
          ))}
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false);
            loadCameras();
          }}
        />
      )}
    </div>
  );
}