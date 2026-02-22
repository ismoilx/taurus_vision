/**
 * Cameras Page — Sprint 6 Video Pipeline paneli bilan
 *
 * Yangilik: Sahifa tepasida "Video Pipeline" panel qo'shildi.
 * Bu panel orqali:
 *   - Video fayl nomi kiritiladi
 *   - Pipeline ishga tushiriladi / to'xtatiladi
 *   - Real vaqtda holat (FPS, kadrlar, aniqlangan jonivorlar) ko'rsatiladi
 */

import { useState, useEffect, useRef } from 'react';
import {
  Camera,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  Video,
  Trash2,
  Play,
  Square,
  Film,
  Activity,
  Eye,
} from 'lucide-react';
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

interface PipelineStats {
  total_frames: number;
  processed_frames: number;
  yolo_detections: number;
  identified: number;
  unidentified: number;
  errors: number;
  fps: number;
  uptime_seconds: number;
}

interface PipelineStatus {
  status: 'not_initialized' | 'running' | 'stopped';
  running: boolean;
  stats?: PipelineStats;
}

// ---------------------------------------------------------------------------
// Video Pipeline Panel
// ---------------------------------------------------------------------------

function VideoPipelinePanel() {
  const [videoFilename, setVideoFilename] = useState('sigir_test.mp4');
  const [fps, setFps]           = useState(10);
  const [skipFrames, setSkip]   = useState(3);

  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [successMsg, setSuccess] = useState('');

  // Auto-refresh holat (har 2 soniyada)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  async function fetchStatus() {
    try {
      const data = await apiFetch<PipelineStatus>('/api/v1/pipeline/status');
      setPipelineStatus(data);
    } catch {
      // Silent — status har doim mavjud emas
    }
  }

  async function handleStart() {
    if (!videoFilename.trim()) {
      setError('Video fayl nomi kiritilishi shart');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const params = new URLSearchParams({
        video_filename: videoFilename.trim(),
        camera_fps: String(fps),
        skip_frames: String(skipFrames),
      });
      await apiFetch(`/api/v1/pipeline/start-video?${params}`, { method: 'POST' });
      setSuccess(`Pipeline ishga tushdi: ${videoFilename}`);
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await apiFetch('/api/v1/pipeline/stop', { method: 'POST' });
      setSuccess('Pipeline to\'xtatildi');
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  const isRunning = pipelineStatus?.running === true;
  const stats     = pipelineStatus?.stats;

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #E4E7ED',
      borderRadius: 14,
      overflow: 'hidden',
      marginBottom: 32,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      {/* Panel header */}
      <div style={{
        padding: '18px 24px',
        borderBottom: '1px solid #F3F4F6',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: isRunning ? 'rgba(16,185,129,0.04)' : 'rgba(30,62,180,0.03)',
      }}>
        <div style={{
          width: 38, height: 38,
          borderRadius: 9,
          background: isRunning ? '#ECFDF5' : '#EEF2FF',
          display: 'grid', placeItems: 'center',
        }}>
          <Film size={18} color={isRunning ? '#10B981' : '#4F46E5'} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>
            Video Pipeline — Sprint 6 Test
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 1 }}>
            Video fayldan real sigir aniqlash va identifikatsiya
          </div>
        </div>

        {/* Holat badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px',
          borderRadius: 20,
          background: isRunning ? '#ECFDF5' : '#F9FAFB',
          border: `1px solid ${isRunning ? '#A7F3D0' : '#E5E7EB'}`,
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: isRunning ? '#10B981' : '#9CA3AF',
            ...(isRunning ? { animation: 'pulse 1.5s infinite' } : {}),
          }} />
          <span style={{
            fontSize: 12, fontWeight: 600,
            color: isRunning ? '#059669' : '#6B7280',
          }}>
            {isRunning ? 'Ishlayapti' : pipelineStatus?.status === 'stopped' ? 'To\'xtatilgan' : 'Tayyor'}
          </span>
        </div>
      </div>

      <div style={{ padding: 24 }}>

        {/* Error / Success xabarlari */}
        {error && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            background: '#FEF2F2', border: '1px solid #FECACA',
            borderRadius: 10, padding: '12px 16px', marginBottom: 20,
          }}>
            <AlertCircle size={16} color="#DC2626" style={{ marginTop: 1, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
          </div>
        )}
        {successMsg && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: '#F0FDF4', border: '1px solid #BBF7D0',
            borderRadius: 10, padding: '12px 16px', marginBottom: 20,
          }}>
            <CheckCircle size={16} color="#16A34A" />
            <span style={{ fontSize: 13, color: '#16A34A' }}>{successMsg}</span>
          </div>
        )}

        {/* Forma + Tugmalar */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 24 }}>

          {/* Video fayl nomi */}
          <div style={{ flex: '2 1 220px' }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Video fayl nomi
            </label>
            <div style={{ position: 'relative' }}>
              <Film size={14} color="#9CA3AF" style={{
                position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
              }} />
              <input
                type="text"
                value={videoFilename}
                onChange={e => setVideoFilename(e.target.value)}
                disabled={isRunning || loading}
                placeholder="sigir_test.mp4"
                style={{
                  width: '100%', padding: '9px 12px 9px 32px',
                  border: '1px solid #D1D5DB',
                  borderRadius: 8, fontSize: 13,
                  fontFamily: "'JetBrains Mono', monospace",
                  background: isRunning ? '#F9FAFB' : '#fff',
                  color: '#0D1117', outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            <p style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
              ~/taurus-vision/data/videos/ papkasidagi fayl
            </p>
          </div>

          {/* FPS */}
          <div style={{ flex: '1 1 100px' }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              FPS
            </label>
            <input
              type="number"
              value={fps}
              onChange={e => setFps(Math.max(1, Math.min(30, +e.target.value || 10)))}
              disabled={isRunning || loading}
              min={1} max={30}
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB',
                borderRadius: 8, fontSize: 13,
                background: isRunning ? '#F9FAFB' : '#fff',
                color: '#0D1117', outline: 'none',
              }}
            />
          </div>

          {/* Skip frames */}
          <div style={{ flex: '1 1 100px' }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Skip kadrlar
            </label>
            <input
              type="number"
              value={skipFrames}
              onChange={e => setSkip(Math.max(1, Math.min(10, +e.target.value || 3)))}
              disabled={isRunning || loading}
              min={1} max={10}
              style={{
                width: '100%', padding: '9px 12px',
                border: '1px solid #D1D5DB',
                borderRadius: 8, fontSize: 13,
                background: isRunning ? '#F9FAFB' : '#fff',
                color: '#0D1117', outline: 'none',
              }}
            />
            <p style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
              Har N-chi kadr (CPU tejaш)
            </p>
          </div>

          {/* Start / Stop tugmasi */}
          {!isRunning ? (
            <button
              onClick={handleStart}
              disabled={loading}
              style={{
                flex: '1 1 130px',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '9px 20px',
                background: loading ? '#9CA3AF' : '#1E3EB4',
                color: '#fff', border: 'none', borderRadius: 8,
                fontSize: 13, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'Outfit, sans-serif',
                transition: 'background .15s',
              }}
            >
              <Play size={15} />
              {loading ? 'Yuklanmoqda...' : 'Ishga tushir'}
            </button>
          ) : (
            <button
              onClick={handleStop}
              disabled={loading}
              style={{
                flex: '1 1 130px',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '9px 20px',
                background: loading ? '#9CA3AF' : '#DC2626',
                color: '#fff', border: 'none', borderRadius: 8,
                fontSize: 13, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'Outfit, sans-serif',
                transition: 'background .15s',
              }}
            >
              <Square size={15} />
              {loading ? 'Yuklanmoqda...' : 'To\'xtat'}
            </button>
          )}
        </div>

        {/* Stats qatori — faqat pipeline ishlayotganda */}
        {isRunning && stats && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: 12,
          }}>
            {[
              { icon: Activity, label: 'FPS', value: stats.fps.toFixed(1), color: '#10B981' },
              { icon: Film, label: 'Kadrlar', value: stats.processed_frames.toLocaleString(), color: '#3B82F6' },
              { icon: Eye, label: 'Aniqlangan', value: stats.yolo_detections.toLocaleString(), color: '#8B5CF6' },
              { icon: CheckCircle, label: 'Tanildi', value: stats.identified.toLocaleString(), color: '#059669' },
              { icon: XCircle, label: 'Tanilmadi', value: stats.unidentified.toLocaleString(), color: '#F59E0B' },
              {
                icon: Activity,
                label: 'Vaqt',
                value: stats.uptime_seconds < 60
                  ? `${Math.floor(stats.uptime_seconds)}s`
                  : `${Math.floor(stats.uptime_seconds / 60)}m ${Math.floor(stats.uptime_seconds % 60)}s`,
                color: '#6B7280',
              },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} style={{
                background: '#F9FAFB',
                border: '1px solid #F3F4F6',
                borderRadius: 10,
                padding: '12px 14px',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon size={13} color={color} />
                  <span style={{ fontSize: 11, color: '#6B7280', fontWeight: 500 }}>{label}</span>
                </div>
                <span style={{ fontSize: 18, fontWeight: 700, color: '#0D1117', fontFamily: "'JetBrains Mono', monospace" }}>
                  {value}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Instruksiya — pipeline to'xtatilgan holatda */}
        {!isRunning && (
          <div style={{
            background: '#F8FAFC',
            border: '1px solid #E2E8F0',
            borderRadius: 10,
            padding: '14px 18px',
          }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 8 }}>
              Boshlashdan oldin:
            </p>
            <ol style={{ margin: 0, padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[
                'Sigirni tizimga qo\'shing: Jonivorlar sahifasi → "Qo\'shish"',
                '4-5 ta rasm orqali muzzle ro\'yxatdan o\'tkzing: Jonivor detail → "Ro\'yxatdan o\'tkazish"',
                'Video faylni qo\'ying: ~/taurus-vision/data/videos/sigir_test.mp4',
                'Docker restart: cd ~/taurus-vision && docker compose restart backend',
              ].map((step, i) => (
                <li key={i} style={{ fontSize: 12, color: '#64748B' }}>{step}</li>
              ))}
            </ol>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

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
  const [error, setError]     = useState('');

  async function handleSubmit() {
    if (!form.name.trim()) {
      setError('Kamera nomi kiritilishi shart');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        type: form.type,
        fps: form.fps,
        enabled: true,
      };
      if (form.type === 'rtsp')  body.source     = form.source;
      if (form.type === 'usb')   body.device_id  = form.device_id;

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

  const inputStyle = {
    width: '100%', padding: '10px 14px',
    border: '1px solid #D1D5DB', borderRadius: 8,
    fontSize: 14, color: '#0D1117', outline: 'none',
    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box' as const,
  };

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        width: '100%', maxWidth: 460,
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #F3F4F6' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0D1117' }}>Yangi kamera qo'shish</h2>
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {error && (
            <div style={{
              display: 'flex', gap: 8,
              background: '#FEF2F2', border: '1px solid #FECACA',
              borderRadius: 8, padding: '10px 14px',
            }}>
              <AlertCircle size={15} color="#DC2626" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>Kamera nomi *</label>
            <input type="text" value={form.name}
              onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
              placeholder="Kirish eshigi kamerasi" style={inputStyle} />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>Kamera turi</label>
            <select value={form.type}
              onChange={e => setForm(p => ({ ...p, type: e.target.value as 'usb' | 'rtsp' | 'simulated' }))}
              style={inputStyle}>
              <option value="simulated">Simulated (Test)</option>
              <option value="usb">USB Camera</option>
              <option value="rtsp">RTSP Stream</option>
            </select>
          </div>

          {form.type === 'rtsp' && (
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>RTSP URL</label>
              <input type="text" value={form.source}
                onChange={e => setForm(p => ({ ...p, source: e.target.value }))}
                placeholder="rtsp://192.168.1.100:554/stream"
                style={{ ...inputStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }} />
            </div>
          )}

          {form.type === 'usb' && (
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>Device ID</label>
              <input type="number" value={form.device_id}
                onChange={e => setForm(p => ({ ...p, device_id: parseInt(e.target.value) || 0 }))}
                min="0" style={inputStyle} />
              <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>Odatda 0 (birinchi kamera)</p>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>FPS</label>
            <input type="number" value={form.fps}
              onChange={e => setForm(p => ({ ...p, fps: parseInt(e.target.value) || 10 }))}
              min="1" max="30" style={inputStyle} />
            <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>Tavsiya: 10–15 FPS</p>
          </div>
        </div>

        <div style={{ padding: '16px 24px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 12 }}>
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
// Camera Card
// ---------------------------------------------------------------------------

function CameraCard({
  camera, status, onDelete,
}: {
  camera: CameraConfig;
  status?: CameraStatus;
  onDelete: () => void;
}) {
  const isActive = status?.is_active ?? false;
  const hasError = !!status?.error;

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #E4E7ED',
      borderRadius: 12,
      padding: 20,
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      transition: 'box-shadow .2s',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10,
            background: isActive ? '#ECFDF5' : hasError ? '#FEF2F2' : '#F3F4F6',
            display: 'grid', placeItems: 'center',
          }}>
            <Camera size={20} color={isActive ? '#10B981' : hasError ? '#DC2626' : '#9CA3AF'} />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>{camera.name}</div>
            <div style={{ fontSize: 12, color: '#9CA3AF', textTransform: 'capitalize' }}>{camera.type}</div>
          </div>
        </div>
        <button onClick={onDelete} style={{
          padding: 8, background: 'none', border: 'none',
          cursor: 'pointer', borderRadius: 7, color: '#DC2626',
        }}>
          <Trash2 size={15} />
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {[
          {
            label: 'Holat',
            value: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {isActive
                  ? <CheckCircle size={14} color="#10B981" />
                  : hasError
                  ? <XCircle size={14} color="#DC2626" />
                  : <XCircle size={14} color="#9CA3AF" />}
                <span style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>
                  {isActive ? 'Faol' : hasError ? 'Xatolik' : 'Nofaol'}
                </span>
              </div>
            ),
          },
          ...(status ? [
            { label: 'FPS', value: <span style={{ fontSize: 13, fontWeight: 600 }}>{status.fps.toFixed(1)}</span> },
            { label: 'Kadrlar', value: <span style={{ fontSize: 13, fontWeight: 600 }}>{status.frames_captured}</span> },
          ] : []),
        ].map(({ label, value }, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 0', borderTop: '1px solid #F3F4F6',
          }}>
            <span style={{ fontSize: 13, color: '#6B7280' }}>{label}</span>
            {value}
          </div>
        ))}

        {camera.type === 'rtsp' && camera.source && (
          <div style={{ paddingTop: 10, borderTop: '1px solid #F3F4F6' }}>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>URL</div>
            <code style={{
              fontSize: 11, color: '#0D1117',
              background: '#F9FAFB', padding: '4px 8px',
              borderRadius: 5, display: 'block', overflowX: 'auto',
            }}>
              {camera.source}
            </code>
          </div>
        )}

        {hasError && status?.error && (
          <div style={{
            display: 'flex', gap: 8,
            background: '#FEF2F2', border: '1px solid #FECACA',
            borderRadius: 8, padding: '8px 12px', marginTop: 10,
          }}>
            <AlertCircle size={14} color="#DC2626" style={{ flexShrink: 0 }} />
            <p style={{ fontSize: 12, color: '#DC2626', margin: 0 }}>{status.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CamerasPage() {
  const [cameras, setCameras]   = useState<CameraConfig[]>([]);
  const [statuses, setStatuses] = useState<Record<string, CameraStatus>>({});
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

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
    } catch {
      // silent
    }
  }

  async function handleDelete(camera: CameraConfig) {
    if (!window.confirm(`${camera.name} kamerasini o'chirishga ishonchingiz komilmi?`)) return;
    try {
      await apiFetch(`/api/v1/cameras/${camera.id}`, { method: 'DELETE' });
      loadCameras();
    } catch (err) {
      alert("O'chirish xatolik: " + (err instanceof Error ? err.message : ''));
    }
  }

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
            {cameras.length} ta kamera manbai
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={loadCameras}
            disabled={loading}
            style={{
              padding: '9px 12px',
              border: '1px solid #D1D5DB',
              borderRadius: 8, background: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center',
            }}
          >
            <RefreshCw size={16} color="#6B7280" style={{ animation: loading ? 'spin .7s linear infinite' : 'none' }} />
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '9px 18px',
              background: '#1E3EB4', color: '#fff',
              border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}
          >
            <Plus size={16} />
            Kamera qo'shish
          </button>
        </div>
      </div>

      {/* === VIDEO PIPELINE PANEL === */}
      <VideoPipelinePanel />

      {/* Error */}
      {error && (
        <div style={{
          display: 'flex', gap: 10,
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: 10, padding: '12px 16px', marginBottom: 24,
        }}>
          <AlertCircle size={16} color="#DC2626" />
          <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
        </div>
      )}

      {/* Camera grid */}
      {loading && cameras.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#9CA3AF', fontSize: 14 }}>
          Yuklanmoqda...
        </div>
      ) : cameras.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Video size={48} color="#D1D5DB" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: '#6B7280', fontSize: 16, marginBottom: 8 }}>Hali kamera qo'shilmagan</p>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '10px 20px',
              background: '#1E3EB4', color: '#fff',
              border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}
          >
            <Plus size={16} />
            Birinchi kamerani qo'shish
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20 }}>
          {cameras.map(camera => (
            <CameraCard
              key={camera.id}
              camera={camera}
              status={statuses[camera.id]}
              onDelete={() => handleDelete(camera)}
            />
          ))}
        </div>
      )}

      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => { setShowAddModal(false); loadCameras(); }}
        />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}