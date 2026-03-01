/**
 * Taurus Vision — Cameras Page
 *
 * Kameralarni qo'shish, o'chirish, pipeline start/stop.
 * Barcha holat /api/v1/pipeline/status dan olinadi (poll 3s).
 * Kamera qo'shganda pipeline avtomatik ishga tushadi (enabled=true).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Camera, Plus, RefreshCw, AlertCircle, CheckCircle,
  XCircle, Video, Trash2, Play, Square, Film,
  Activity, Eye,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ────────────────────────────────────────────────────────────────────

interface CameraConfig {
  id:       string;
  name:     string;
  type:     'usb' | 'rtsp' | 'simulated';
  source?:  string;
  device_id?: number;
  fps?:     number;
  enabled:  boolean;
  status:   'active' | 'inactive' | 'error';
}

interface PipelineStatus {
  camera_id:  string;
  running:    boolean;
  started_at: string | null;
  stats: {
    fps:              number;
    processed_frames: number;
    yolo_detections:  number;
    identified:       number;
    uptime_seconds:   number;
    errors:           number;
  } | null;
}

interface AllPipelinesStatus {
  total_running:   number;
  running_cameras: string[];
  pipelines:       Record<string, PipelineStatus>;
}

// ─── Camera Card ──────────────────────────────────────────────────────────────

function CameraCard({
  camera, pipelineStatus, onDelete, onPipelineToggle, pipelineLoading,
}: {
  camera:          CameraConfig;
  pipelineStatus?: PipelineStatus;
  onDelete:        () => void;
  onPipelineToggle: () => void;
  pipelineLoading: boolean;
}) {
  const pRunning = pipelineStatus?.running ?? false;
  const stats    = pipelineStatus?.stats;

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${pRunning ? '#A7F3D0' : '#E4E7ED'}`,
      borderRadius: 12, overflow: 'hidden',
      boxShadow: pRunning
        ? '0 1px 4px rgba(16,185,129,.12)'
        : '0 1px 3px rgba(0,0,0,.05)',
      transition: 'box-shadow .2s, border-color .2s',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid #F3F4F6',
        display: 'flex', alignItems: 'flex-start',
        justifyContent: 'space-between',
        background: pRunning ? 'rgba(16,185,129,.03)' : '#fff',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 9,
            background: pRunning ? '#ECFDF5' : '#F3F4F6',
            display: 'grid', placeItems: 'center', flexShrink: 0,
          }}>
            <Camera size={17} color={pRunning ? '#10B981' : '#9CA3AF'}/>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>
              {camera.name}
            </div>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 1 }}>
              {camera.id} · {camera.type.toUpperCase()}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {pRunning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '2px 9px',
              background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: 20,
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%', background: '#10B981',
                animation: 'pulse-dot 1.5s infinite',
              }}/>
              <span style={{ fontSize: 10, fontWeight: 600, color: '#059669' }}>LIVE</span>
            </div>
          )}
          <button onClick={onDelete} style={{
            padding: 6, background: 'none', border: 'none',
            cursor: 'pointer', borderRadius: 6, color: '#DC2626', opacity: 0.6,
          }}>
            <Trash2 size={13}/>
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '12px 16px' }}>
        {/* Holat qatori */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '6px 0', borderBottom: '1px solid #F9FAFB',
        }}>
          <span style={{ fontSize: 12, color: '#6B7280' }}>Pipeline</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {pRunning
              ? <CheckCircle size={12} color="#10B981"/>
              : <XCircle size={12} color="#9CA3AF"/>}
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0D1117' }}>
              {pRunning ? 'Ishlayapti' : 'To\'xtatilgan'}
            </span>
          </div>
        </div>

        {/* RTSP URL */}
        {camera.type === 'rtsp' && camera.source && (
          <div style={{ marginTop: 8 }}>
            <code style={{
              fontSize: 10, color: '#6B7280',
              background: '#F9FAFB', padding: '3px 7px',
              borderRadius: 4, display: 'block', overflowX: 'auto',
            }}>
              {camera.source}
            </code>
          </div>
        )}

        {/* USB device */}
        {camera.type === 'usb' && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 0', borderBottom: '1px solid #F9FAFB',
          }}>
            <span style={{ fontSize: 12, color: '#6B7280' }}>Device</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0D1117', fontFamily: 'monospace' }}>
              /dev/video{camera.device_id ?? 0}
            </span>
          </div>
        )}

        {/* Pipeline statistika */}
        {pRunning && stats && (
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: 6, marginTop: 10,
            padding: '9px', background: '#F0FDF4',
            border: '1px solid #D1FAE5', borderRadius: 8,
          }}>
            {[
              { icon: Activity, label: 'FPS',       value: stats.fps.toFixed(1),                   color: '#10B981' },
              { icon: Film,     label: 'Kadrlar',   value: stats.processed_frames.toLocaleString(), color: '#3B82F6' },
              { icon: Eye,      label: 'Aniqlandi', value: stats.yolo_detections.toLocaleString(),  color: '#8B5CF6' },
              { icon: CheckCircle, label: 'Tanildi', value: stats.identified.toLocaleString(),      color: '#059669' },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Icon size={11} color={color}/>
                <span style={{ fontSize: 10, color: '#6B7280' }}>{label}:</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#0D1117', fontFamily: 'monospace' }}>
                  {value}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pipeline toggle button */}
      {camera.enabled && (
        <div style={{ padding: '0 16px 14px' }}>
          <button
            onClick={onPipelineToggle}
            disabled={pipelineLoading}
            style={{
              width: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              padding: '8px 0',
              background: pipelineLoading ? '#9CA3AF' : pRunning ? '#FEF2F2' : '#1E3EB4',
              color: pRunning ? '#DC2626' : '#fff',
              border: pRunning ? '1px solid #FECACA' : 'none',
              borderRadius: 8, fontSize: 13, fontWeight: 700,
              cursor: pipelineLoading ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif', transition: 'background .15s',
            }}
          >
            {pipelineLoading ? (
              <>
                <div style={{
                  width: 13, height: 13, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff',
                  animation: 'spin .7s linear infinite',
                }}/>
                Yuklanmoqda...
              </>
            ) : pRunning ? (
              <><Square size={13}/> To'xtatish</>
            ) : (
              <><Play size={13}/> Pipeline ishga tushir</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Add Camera Modal ─────────────────────────────────────────────────────────

function AddCameraModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: '', type: 'simulated' as 'usb' | 'rtsp' | 'simulated',
    source: '', device_id: 0, fps: 10,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [webcams, setWebcams] = useState<{device_index:number;label:string}[]>([]);
  const [scanning, setScanning] = useState(false);

  async function detectWebcams() {
    setScanning(true);
    try {
      const found = await apiFetch<{device_index:number;label:string;suggested_name:string}[]>(
        '/api/v1/cameras/detect-webcams'
      );
      setWebcams(found);
      if (found.length === 0) {
        setError('Webcam topilmadi. Docker da /dev/video0 mount bo\'lishi kerak.');
      } else {
        const first = found[0];
        setForm(p => ({ ...p, device_id: first.device_index, name: p.name || first.suggested_name || 'Webcam' }));
        setError('');
      }
    } catch {
      setError('Webcam aniqlashda xato');
    } finally {
      setScanning(false);
    }
  }

  async function handleSubmit() {
    if (!form.name.trim()) { setError('Kamera nomi kiritilishi shart'); return; }
    if (form.type === 'rtsp' && !form.source.trim()) { setError('RTSP URL kiritilishi shart'); return; }
    setLoading(true); setError('');
    try {
      const body: Record<string, unknown> = {
        name: form.name.trim(), type: form.type, fps: form.fps, enabled: true,
      };
      if (form.type === 'rtsp') body.source    = form.source.trim();
      if (form.type === 'usb')  body.device_id = form.device_id;

      await apiFetch('/api/v1/cameras/', { method: 'POST', body: JSON.stringify(body) });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Server xatosi');
    } finally { setLoading(false); }
  }

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px',
    border: '1px solid #D1D5DB', borderRadius: 8,
    fontSize: 14, color: '#0D1117', outline: 'none',
    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
  };
  const lbl: React.CSSProperties = {
    display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5,
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14,
        boxShadow: '0 20px 60px rgba(0,0,0,.18)',
        width: '100%', maxWidth: 440,
      }}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid #F3F4F6' }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            Yangi kamera qo'shish
          </h2>
          <p style={{ fontSize: 12, color: '#9CA3AF', margin: '3px 0 0' }}>
            Kamera qo'shilgandan so'ng pipeline avtomatik ishga tushadi
          </p>
        </div>

        <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {!!error && (
            <div style={{
              display: 'flex', gap: 8,
              background: '#FEF2F2', border: '1px solid #FECACA',
              borderRadius: 8, padding: '9px 12px',
            }}>
              <AlertCircle size={13} color="#DC2626" style={{ flexShrink: 0, marginTop: 1 }}/>
              <span style={{ fontSize: 12, color: '#DC2626' }}>{error}</span>
            </div>
          )}

          <div>
            <label style={lbl}>Kamera nomi *</label>
            <input type="text" value={form.name}
              onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
              placeholder="Shimoliy molxona" style={inp}/>
          </div>

          <div>
            <label style={lbl}>Kamera turi</label>
            <select value={form.type}
              onChange={e => setForm(p => ({ ...p, type: e.target.value as any }))}
              style={inp}>
              <option value="simulated">Simulated (Test)</option>
              <option value="usb">USB / Webcam</option>
              <option value="rtsp">RTSP Stream (IP kamera)</option>
            </select>
          </div>

          {form.type === 'rtsp' && (
            <div>
              <label style={lbl}>RTSP URL *</label>
              <input type="text" value={form.source}
                onChange={e => setForm(p => ({ ...p, source: e.target.value }))}
                placeholder="rtsp://admin:pass@192.168.1.100:554/stream"
                style={{ ...inp, fontFamily: 'monospace', fontSize: 12 }}/>
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: '3px 0 0' }}>
                Misol: rtsp://admin:password@192.168.1.64:554/ch01
              </p>
            </div>
          )}

          {form.type === 'usb' && (
            <div>
              <label style={lbl}>Webcam Device</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <select
                  value={form.device_id}
                  onChange={e => setForm(p => ({ ...p, device_id: parseInt(e.target.value) }))}
                  style={{ ...inp, flex: 1 }}
                >
                  {webcams.length > 0
                    ? webcams.map(w => (
                        <option key={w.device_index} value={w.device_index}>{w.label}</option>
                      ))
                    : [0,1,2,3].map(i => (
                        <option key={i} value={i}>Webcam {i} (/dev/video{i})</option>
                      ))
                  }
                </select>
                <button
                  type="button"
                  onClick={detectWebcams}
                  disabled={scanning}
                  style={{
                    padding: '9px 12px', background: '#EEF2FF',
                    border: '1px solid #C7D2FE', borderRadius: 8,
                    color: '#1E3EB4', fontSize: 12, fontWeight: 600,
                    cursor: scanning ? 'not-allowed' : 'pointer',
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}
                >
                  {scanning ? '...' : '🔍 Aniqlash'}
                </button>
              </div>
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: '3px 0 0' }}>
                Docker da: <code>devices: [/dev/video0:/dev/video0]</code>
              </p>
            </div>
          )}

          <div>
            <label style={lbl}>FPS (kadr/s)</label>
            <input type="number" value={form.fps}
              onChange={e => setForm(p => ({ ...p, fps: parseInt(e.target.value) || 10 }))}
              min="1" max="30" style={inp}/>
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '3px 0 0' }}>
              Tavsiya: Simulated/USB uchun 10–15, RTSP uchun 5–10
            </p>
          </div>
        </div>

        <div style={{ padding: '12px 22px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 10 }}>
          <button onClick={onClose} disabled={loading} style={{
            flex: 1, padding: '9px 0',
            border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', color: '#374151', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            Bekor qilish
          </button>
          <button onClick={handleSubmit} disabled={loading} style={{
            flex: 2, padding: '9px 0',
            background: loading ? '#9CA3AF' : '#1E3EB4',
            border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 13, fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            {loading ? "Qo'shilmoqda..." : "Qo'shish va ishga tushirish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CamerasPage() {
  const qClient = useQueryClient();
  const [showAddModal, setShowAddModal]   = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState<Record<string, boolean>>({});

  const invalidate = () => {
    qClient.invalidateQueries({ queryKey: ['cameras'] });
    qClient.invalidateQueries({ queryKey: ['pipeline', 'status'] });
  };

  // Kameralar ro'yxati (DB)
  const { data: cameras = [], isFetching, isError } = useQuery({
    queryKey: ['cameras'],
    queryFn:  () => apiFetch<CameraConfig[]>('/api/v1/cameras/'),
  });

  // Pipeline holati (poll 3s)
  const { data: pipelines } = useQuery({
    queryKey:        ['pipeline', 'status'],
    queryFn:         () => apiFetch<AllPipelinesStatus>('/api/v1/pipeline/status').catch(() => null),
    refetchInterval: 3000,
  });

  // O'chirish
  const deleteMutation = useMutation({
    mutationFn: async (camera: CameraConfig) => {
      // Backend endi o'zi pipeline to'xtatadi (DELETE endpointda)
      return apiFetch(`/api/v1/cameras/${camera.id}`, { method: 'DELETE' });
    },
    onSuccess:  invalidate,
    onError:    (e: Error) => alert("O'chirish xatoligi: " + e.message),
  });

  async function handleDelete(camera: CameraConfig) {
    if (!window.confirm(`"${camera.name}" kamerasini o'chirmoqchimisiz?\nPipeline ham to'xtatiladi.`)) return;
    deleteMutation.mutate(camera);
  }

  async function handlePipelineToggle(camera: CameraConfig) {
    const isRunning = pipelines?.running_cameras.includes(camera.id) ?? false;
    setPipelineLoading(p => ({ ...p, [camera.id]: true }));
    try {
      if (isRunning) {
        await apiFetch(`/api/v1/cameras/${camera.id}/stop`, { method: 'POST' });
      } else {
        await apiFetch(`/api/v1/cameras/${camera.id}/start`, { method: 'POST' });
      }
      invalidate();
    } catch (err) {
      alert(`Pipeline xatosi: ${err instanceof Error ? err.message : 'Noma\'lum xato'}`);
    } finally {
      setPipelineLoading(p => ({ ...p, [camera.id]: false }));
    }
  }

  const totalRunning = pipelines?.total_running ?? 0;

  return (
    <div style={{
      maxWidth: 1280, margin: '0 auto',
      padding: '28px 22px',
      fontFamily: 'Outfit, sans-serif',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#0D1117', margin: 0 }}>Kameralar</h1>
          <p style={{ fontSize: 13, color: '#6B7280', margin: '3px 0 0' }}>
            {cameras.length} ta kamera
            {totalRunning > 0 && (
              <span style={{
                marginLeft: 10, padding: '2px 9px',
                background: '#ECFDF5', border: '1px solid #A7F3D0',
                borderRadius: 20, fontSize: 11, fontWeight: 600, color: '#059669',
              }}>
                {totalRunning} ta aktiv
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => qClient.invalidateQueries({ queryKey: ['cameras'] })}
            disabled={isFetching} style={{
              padding: '8px 11px', border: '1px solid #D1D5DB', borderRadius: 8,
              background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center',
            }}>
            <RefreshCw size={15} color="#6B7280"
              style={{ animation: isFetching ? 'spin .7s linear infinite' : 'none' }}/>
          </button>
          <button onClick={() => setShowAddModal(true)} style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '8px 16px', background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={15}/> Kamera qo'shish
          </button>
        </div>
      </div>

      {/* Aktiv pipeline banner */}
      {totalRunning > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 18px', background: '#F0FDF4',
          border: '1px solid #A7F3D0', borderRadius: 10, marginBottom: 20,
        }}>
          <div style={{ position: 'relative' }}>
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#10B981' }}/>
            <div style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              background: '#10B981', animation: 'ping 1s cubic-bezier(0,0,.2,1) infinite',
            }}/>
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#065F46' }}>
            {totalRunning} ta pipeline ishlayapti:
          </span>
          <span style={{ fontSize: 12, color: '#059669' }}>
            {pipelines?.running_cameras.join(', ')}
          </span>
          <a href="/live" style={{
            marginLeft: 'auto', fontSize: 12, fontWeight: 700,
            color: '#1E3EB4', textDecoration: 'none',
          }}>
            Live ko'rish →
          </a>
        </div>
      )}

      {/* Backend xato */}
      {isError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: 10, padding: '11px 14px', marginBottom: 20,
        }}>
          <AlertCircle size={15} color="#DC2626" style={{ flexShrink: 0 }}/>
          <span style={{ fontSize: 13, color: '#DC2626' }}>
            Backend bilan aloqa yo'q. <code>docker-compose up</code> ni tekshiring.
          </span>
        </div>
      )}

      {/* Bo'sh holat */}
      {!isError && cameras.length === 0 && !isFetching && (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Video size={44} color="#D1D5DB" style={{ margin: '0 auto 14px' }}/>
          <p style={{ color: '#6B7280', fontSize: 15, marginBottom: 8 }}>
            Hali kamera qo'shilmagan
          </p>
          <button onClick={() => setShowAddModal(true)} style={{
            display: 'inline-flex', alignItems: 'center', gap: 7,
            padding: '9px 18px', background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={14}/> Birinchi kamerani qo'shish
          </button>
        </div>
      )}

      {/* Kameralar grid */}
      {cameras.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 18 }}>
          {cameras.map(camera => (
            <CameraCard
              key={camera.id}
              camera={camera}
              pipelineStatus={pipelines?.pipelines?.[camera.id]}
              onDelete={() => handleDelete(camera)}
              onPipelineToggle={() => handlePipelineToggle(camera)}
              pipelineLoading={pipelineLoading[camera.id] ?? false}
            />
          ))}
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => { setShowAddModal(false); invalidate(); }}
        />
      )}

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes ping    { 75%, 100% { transform: scale(2); opacity: 0; } }
        @keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:.4} }
      `}</style>
    </div>
  );
}