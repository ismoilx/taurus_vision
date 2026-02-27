/**
 * Taurus Vision — Cameras Page (Sprint 10)
 *
 * Multi-camera pipeline boshqaruvi.
 * Har bir kamera kartasida:
 *   - Real-time holat (active/inactive/error)
 *   - Pipeline Start / Stop tugmasi
 *   - FPS va kadrlar statistikasi
 *   - Pipeline ishlayotganda live stats
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Camera, Plus, RefreshCw, AlertCircle, CheckCircle,
  XCircle, Video, Trash2, Play, Square, Film,
  Activity, Eye, Wifi, WifiOff,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CameraConfig {
  id:       string;
  name:     string;
  type:     'usb' | 'rtsp' | 'simulated';
  source?:  string;
  device_id?: number;
  fps?:     number;
  enabled:  boolean;
  status?:  'active' | 'inactive' | 'error';
}

interface CameraStatus {
  camera_id:       string;
  is_active:       boolean;
  fps:             number;
  frames_captured: number;
  last_frame_time: string | null;
  error:           string | null;
}

interface PipelineStatus {
  camera_id:  string;
  running:    boolean;
  started_at: string | null;
  stats: {
    fps:             number;
    processed_frames: number;
    yolo_detections: number;
    identified:      number;
    unidentified:    number;
    uptime_seconds:  number;
    errors:          number;
  } | null;
}

interface AllPipelinesStatus {
  total_running:   number;
  running_cameras: string[];
  pipelines:       Record<string, PipelineStatus>;
}

// ---------------------------------------------------------------------------
// Camera Card
// ---------------------------------------------------------------------------

function CameraCard({
  camera,
  camStatus,
  pipelineStatus,
  onDelete,
  onPipelineToggle,
  pipelineLoading,
}: {
  camera:          CameraConfig;
  camStatus?:      CameraStatus;
  pipelineStatus?: PipelineStatus;
  onDelete:        () => void;
  onPipelineToggle: () => void;
  pipelineLoading: boolean;
}) {
  const isActive    = camStatus?.is_active ?? false;
  const hasError    = !!camStatus?.error;
  const pRunning    = pipelineStatus?.running ?? false;
  const stats       = pipelineStatus?.stats;

  const statusColor = isActive ? '#10B981' : hasError ? '#DC2626' : '#9CA3AF';
  const statusBg    = isActive ? '#ECFDF5' : hasError ? '#FEF2F2' : '#F3F4F6';
  const statusLabel = isActive ? 'Faol' : hasError ? 'Xatolik' : 'Nofaol';

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${pRunning ? '#A7F3D0' : '#E4E7ED'}`,
      borderRadius: 14,
      overflow: 'hidden',
      boxShadow: pRunning
        ? '0 1px 3px rgba(16,185,129,0.15)'
        : '0 1px 3px rgba(0,0,0,0.05)',
      transition: 'box-shadow .2s, border-color .2s',
    }}>
      {/* Card Header */}
      <div style={{
        padding: '16px 18px',
        borderBottom: '1px solid #F3F4F6',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        background: pRunning ? 'rgba(16,185,129,0.03)' : '#fff',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 10,
            background: statusBg,
            display: 'grid', placeItems: 'center',
            flexShrink: 0,
          }}>
            <Camera size={19} color={statusColor} />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>
              {camera.name}
            </div>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 1 }}>
              {camera.id} · {camera.type.toUpperCase()}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Pipeline holat badge */}
          {pRunning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '3px 10px',
              background: '#ECFDF5',
              border: '1px solid #A7F3D0',
              borderRadius: 20,
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#10B981',
                animation: 'pulse-dot 1.5s infinite',
              }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: '#059669' }}>
                Pipeline
              </span>
            </div>
          )}

          <button onClick={onDelete} style={{
            padding: 7, background: 'none', border: 'none',
            cursor: 'pointer', borderRadius: 7, color: '#DC2626',
            opacity: 0.6, transition: 'opacity .15s',
          }}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Stats qatori */}
      <div style={{ padding: '12px 18px' }}>

        {/* Kamera holati */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 0',
          borderBottom: '1px solid #F9FAFB',
        }}>
          <span style={{ fontSize: 12, color: '#6B7280' }}>Holat</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {isActive
              ? <CheckCircle size={13} color="#10B981" />
              : hasError
              ? <XCircle size={13} color="#DC2626" />
              : <XCircle size={13} color="#9CA3AF" />}
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0D1117' }}>
              {statusLabel}
            </span>
          </div>
        </div>

        {/* Camera FPS */}
        {camStatus && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '8px 0',
            borderBottom: '1px solid #F9FAFB',
          }}>
            <span style={{ fontSize: 12, color: '#6B7280' }}>Kamera FPS</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0D1117', fontFamily: 'monospace' }}>
              {camStatus.fps.toFixed(1)}
            </span>
          </div>
        )}

        {/* Pipeline statistika — faqat ishlayotganda */}
        {pRunning && stats && (
          <>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 8,
              marginTop: 10,
              padding: '10px',
              background: '#F0FDF4',
              border: '1px solid #D1FAE5',
              borderRadius: 8,
            }}>
              {[
                { icon: Activity, label: 'FPS', value: stats.fps.toFixed(1), color: '#10B981' },
                { icon: Film,     label: 'Kadrlar', value: stats.processed_frames.toLocaleString(), color: '#3B82F6' },
                { icon: Eye,      label: 'Aniqlangan', value: stats.yolo_detections.toLocaleString(), color: '#8B5CF6' },
                { icon: CheckCircle, label: 'Tanildi', value: stats.identified.toLocaleString(), color: '#059669' },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <Icon size={12} color={color} />
                  <span style={{ fontSize: 11, color: '#6B7280' }}>{label}:</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#0D1117', fontFamily: 'monospace' }}>
                    {value}
                  </span>
                </div>
              ))}
            </div>

            {/* Uptime */}
            <div style={{
              fontSize: 11, color: '#6B7280', textAlign: 'center',
              marginTop: 6,
            }}>
              Vaqt: {stats.uptime_seconds < 60
                ? `${Math.floor(stats.uptime_seconds)}s`
                : `${Math.floor(stats.uptime_seconds / 60)}m ${Math.floor(stats.uptime_seconds % 60)}s`}
              {stats.errors > 0 && (
                <span style={{ color: '#F59E0B', marginLeft: 8 }}>
                  ⚠ {stats.errors} xato
                </span>
              )}
            </div>
          </>
        )}

        {/* RTSP URL */}
        {camera.type === 'rtsp' && camera.source && (
          <div style={{ marginTop: 10 }}>
            <code style={{
              fontSize: 10, color: '#6B7280',
              background: '#F9FAFB', padding: '4px 8px',
              borderRadius: 5, display: 'block', overflowX: 'auto',
            }}>
              {camera.source}
            </code>
          </div>
        )}

        {/* Error */}
        {hasError && camStatus?.error && (
          <div style={{
            display: 'flex', gap: 6,
            background: '#FEF2F2', border: '1px solid #FECACA',
            borderRadius: 7, padding: '7px 10px', marginTop: 10,
          }}>
            <AlertCircle size={13} color="#DC2626" style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 11, color: '#DC2626', margin: 0 }}>{camStatus.error}</p>
          </div>
        )}
      </div>

      {/* Pipeline Start / Stop tugmasi */}
      {camera.enabled && (
        <div style={{ padding: '0 18px 16px' }}>
          <button
            onClick={onPipelineToggle}
            disabled={pipelineLoading}
            style={{
              width: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              padding: '9px 0',
              background: pipelineLoading
                ? '#9CA3AF'
                : pRunning
                ? '#FEF2F2'
                : '#1E3EB4',
              color: pRunning ? '#DC2626' : '#fff',
              border: pRunning ? '1px solid #FECACA' : 'none',
              borderRadius: 8,
              fontSize: 13, fontWeight: 700,
              cursor: pipelineLoading ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif',
              transition: 'background .15s',
            }}
          >
            {pipelineLoading ? (
              <>
                <div style={{
                  width: 14, height: 14, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.4)',
                  borderTopColor: '#fff',
                  animation: 'spin .7s linear infinite',
                }} />
                Yuklanmoqda...
              </>
            ) : pRunning ? (
              <><Square size={14} /> To'xtatish</>
            ) : (
              <><Play size={14} /> Pipeline ishga tushir</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add Camera Modal
// ---------------------------------------------------------------------------

function AddCameraModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: '', type: 'simulated' as 'usb' | 'rtsp' | 'simulated',
    source: '', device_id: 0, fps: 10,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  async function handleSubmit() {
    if (!form.name.trim()) { setError('Kamera nomi kiritilishi shart'); return; }
    setLoading(true); setError('');
    try {
      const body: Record<string, unknown> = {
        name: form.name, type: form.type, fps: form.fps, enabled: true,
      };
      if (form.type === 'rtsp') body.source    = form.source;
      if (form.type === 'usb')  body.device_id = form.device_id;

      await apiFetch('/api/v1/cameras/', { method: 'POST', body: JSON.stringify(body) });
      onSaved(); onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally { setLoading(false); }
  }

  const inp = {
    width: '100%', padding: '10px 14px',
    border: '1px solid #D1D5DB', borderRadius: 8,
    fontSize: 14, color: '#0D1117', outline: 'none',
    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box' as const,
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 460,
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #F3F4F6' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            Yangi kamera qo'shish
          </h2>
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isError && (
            <div style={{
              display: 'flex', gap: 8,
              background: '#FEF2F2', border: '1px solid #FECACA',
              borderRadius: 8, padding: '10px 14px',
            }}>
              <AlertCircle size={14} color="#DC2626" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#DC2626' }}>{error instanceof Error ? error.message : "Yuklab bo'lmadi"}</span>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Kamera nomi *
            </label>
            <input type="text" value={form.name}
              onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
              placeholder="Shimoliy molxona kamerasi" style={inp} />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Kamera turi
            </label>
            <select value={form.type}
              onChange={e => setForm(p => ({ ...p, type: e.target.value as any }))}
              style={inp}>
              <option value="simulated">Simulated (Test)</option>
              <option value="usb">USB Camera</option>
              <option value="rtsp">RTSP Stream</option>
            </select>
          </div>

          {form.type === 'rtsp' && (
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                RTSP URL
              </label>
              <input type="text" value={form.source}
                onChange={e => setForm(p => ({ ...p, source: e.target.value }))}
                placeholder="rtsp://192.168.1.100:554/stream"
                style={{ ...inp, fontFamily: 'monospace', fontSize: 12 }} />
            </div>
          )}

          {form.type === 'usb' && (
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
                Device ID
              </label>
              <input type="number" value={form.device_id}
                onChange={e => setForm(p => ({ ...p, device_id: parseInt(e.target.value) || 0 }))}
                min="0" style={inp} />
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>Odatda 0</p>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              FPS
            </label>
            <input type="number" value={form.fps}
              onChange={e => setForm(p => ({ ...p, fps: parseInt(e.target.value) || 10 }))}
              min="1" max="30" style={inp} />
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>Tavsiya: 10–15 FPS</p>
          </div>
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 10 }}>
          <button onClick={onClose} disabled={loading} style={{
            flex: 1, padding: '10px 0',
            border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            Bekor qilish
          </button>
          <button onClick={handleSubmit} disabled={loading} style={{
            flex: 1, padding: '10px 0',
            background: loading ? '#9CA3AF' : '#1E3EB4',
            border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 14, fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            {loading ? "Qo'shilmoqda..." : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CamerasPage() {
  const qClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState<Record<string, boolean>>({});

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: cameras = [], isFetching: loading, isError, error } = useQuery({
    queryKey: ['cameras'],
    queryFn:  () => apiFetch<CameraConfig[]>('/api/v1/cameras/'),
  });

  const { data: statuses = {} } = useQuery({
    queryKey: ['cameras', 'stats'],
    queryFn:  () => apiFetch<Record<string, CameraStatus>>('/api/v1/cameras/stats/all').catch(() => ({})),
    refetchInterval: 2500,   // WS yo'q — polling orqali yangilanadi
  });

  const { data: pipelines } = useQuery({
    queryKey: ['pipeline', 'status'],
    queryFn:  () => apiFetch<AllPipelinesStatus>('/api/v1/pipeline/status').catch(() => null),
    refetchInterval: 2500,
  });

  const invalidate = () => {
    qClient.invalidateQueries({ queryKey: ['cameras'] });
    qClient.invalidateQueries({ queryKey: ['pipeline', 'status'] });
  };

  // ── Mutations ─────────────────────────────────────────────────────────────
  const deleteMutation = useMutation({
    mutationFn: async (camera: CameraConfig) => {
      if (pipelines?.running_cameras.includes(camera.id)) {
        await apiFetch(`/api/v1/pipeline/stop?camera_id=${camera.id}`, { method: 'POST' }).catch(() => {});
      }
      return apiFetch(`/api/v1/cameras/${camera.id}`, { method: 'DELETE' });
    },
    onSuccess: invalidate,
    onError: (e: Error) => alert("O'chirish xatolik: " + e.message),
  });

  async function handleDelete(camera: CameraConfig) {
    if (!window.confirm(`${camera.name} kamerasini o'chirishga ishonchingiz komilmi?`)) return;
    deleteMutation.mutate(camera);
  }

  async function handlePipelineToggle(camera: CameraConfig) {
    const isRunning = pipelines?.running_cameras.includes(camera.id) ?? false;
    setPipelineLoading(p => ({ ...p, [camera.id]: true }));
    try {
      if (isRunning) {
        await apiFetch(`/api/v1/pipeline/stop?camera_id=${camera.id}`, { method: 'POST' });
      } else {
        await apiFetch('/api/v1/pipeline/start', {
          method: 'POST',
          body: JSON.stringify({ camera_id: camera.id, skip_frames: 3 }),
        });
      }
      invalidate();
    } catch (err) {
      alert(`Pipeline xatosi: ${err instanceof Error ? err.message : 'Xato'}`);
    } finally {
      setPipelineLoading(p => ({ ...p, [camera.id]: false }));
    }
  }

  const totalRunning = pipelines?.total_running ?? 0;

  return (
    <div style={{
      maxWidth: 1280, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>Kameralar</h1>
          <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
            {cameras.length} ta kamera
            {totalRunning > 0 && (
              <span style={{
                marginLeft: 10, padding: '2px 10px',
                background: '#ECFDF5', border: '1px solid #A7F3D0',
                borderRadius: 20, fontSize: 12, fontWeight: 600, color: '#059669',
              }}>
                {totalRunning} ta pipeline aktiv
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => { qClient.invalidateQueries({ queryKey: ["cameras"] }); }} disabled={loading} style={{
            padding: '9px 12px',
            border: '1px solid #D1D5DB', borderRadius: 8, background: '#fff',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center',
          }}>
            <RefreshCw size={16} color="#6B7280"
              style={{ animation: loading ? 'spin .7s linear infinite' : 'none' }} />
          </button>
          <button onClick={() => setShowAddModal(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 18px',
            background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={16} />
            Kamera qo'shish
          </button>
        </div>
      </div>

      {/* Pipeline umumiy holat */}
      {totalRunning > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 20px',
          background: '#F0FDF4', border: '1px solid #A7F3D0',
          borderRadius: 12, marginBottom: 24,
        }}>
          <div style={{ position: 'relative' }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#10B981' }} />
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              background: '#10B981', animation: 'ping 1s cubic-bezier(0,0,.2,1) infinite',
            }} />
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#065F46' }}>
            {totalRunning} ta kamera pipeline ishlayapti:
          </span>
          <span style={{ fontSize: 13, color: '#059669' }}>
            {pipelines?.running_cameras.join(', ')}
          </span>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div style={{
          display: 'flex', gap: 10,
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: 10, padding: '12px 16px', marginBottom: 24,
        }}>
          <AlertCircle size={16} color="#DC2626" />
          <span style={{ fontSize: 13, color: '#DC2626' }}>{error instanceof Error ? error.message : "Yuklab bo'lmadi"}</span>
        </div>
      )}

      {/* Camera Grid */}
      {loading && cameras.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#9CA3AF', fontSize: 14 }}>
          Yuklanmoqda...
        </div>
      ) : cameras.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '64px 0' }}>
          <Video size={48} color="#D1D5DB" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: '#6B7280', fontSize: 16, marginBottom: 8 }}>Hali kamera qo'shilmagan</p>
          <button onClick={() => setShowAddModal(true)} style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '10px 20px',
            background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8,
            fontSize: 14, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={16} />
            Birinchi kamerani qo'shish
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
          {cameras.map(camera => (
            <CameraCard
              key={camera.id}
              camera={camera}
              camStatus={statuses[camera.id]}
              pipelineStatus={pipelines?.pipelines?.[camera.id]}
              onDelete={() => handleDelete(camera)}
              onPipelineToggle={() => handlePipelineToggle(camera)}
              pipelineLoading={pipelineLoading[camera.id] ?? false}
            />
          ))}
        </div>
      )}

      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => { setShowAddModal(false); qClient.invalidateQueries({ queryKey: ["cameras"] }); }}
        />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
      `}</style>
    </div>
  );
}