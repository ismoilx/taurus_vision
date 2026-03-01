/**
 * Taurus Vision — Live Monitor
 *
 * Barcha kameralar grid ko'rinishida, har birida MJPEG stream + AI overlay.
 *
 * API FIELD MAPPING (backend CameraResponse):
 *   id       → camera_id string (stream URL uchun)
 *   name     → display nomi
 *   enabled  → is_enabled emas, enabled
 *   status   → 'active' | 'inactive' | 'error'
 *
 * STREAM:
 *   <img src="/api/v1/cameras/{id}/stream?token=...">
 *   Backend MJPEG + cv2 bbox overlay yuboradi.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Camera, Wifi, WifiOff, RefreshCw, Maximize2, Minimize2,
  Activity, Tag, Scale, AlertTriangle, Play,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch }            from '../utils/apiFetch';
import { useWebSocketContext } from '../context/WebSocketContext';
import { ConnectionStatus as WsStatus } from '../shared/types';

// ─── Types ──────────────────────────────────────────────────────────────────
// CameraResponse (backend) field names — id = camera_id string

interface CameraItem {
  id:        string;   // camera_id string (e.g. "CAM-BARN-01")
  name:      string;
  type:      string;
  source:    string | null;
  device_id: number | null;
  fps:       number;
  enabled:   boolean;
  status:    string;
}

interface CameraStatus {
  camera_id:       string;
  is_active:       boolean;
  fps:             number;
  frames_captured: number;
  last_frame_time: string | null;
  error:           string | null;
}

interface PipelineStats {
  fps:              number;
  processed_frames: number;
  yolo_detections:  number;
  identified:       number;
  uptime_seconds:   number;
  errors:           number;
}

interface PipelineInfo {
  camera_id:  string;
  running:    boolean;
  started_at: string | null;
  stats:      PipelineStats | null;
}

interface AllPipelinesStatus {
  total_running:   number;
  running_cameras: string[];
  pipelines:       Record<string, PipelineInfo>;
}

interface DetectionEvent {
  camera_id:           string;
  animal_id:           number | null;
  animal_tag_id:       string;
  confidence:          number;
  estimated_weight_kg: number;
  identified:          boolean;
  timestamp:           string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 4000)  return 'Hozir';
  if (ms < 60000) return `${Math.floor(ms / 1000)}s`;
  return `${Math.floor(ms / 60000)}m`;
}

function gridCols(n: number): number {
  if (n <= 1) return 1;
  if (n <= 2) return 2;
  if (n <= 4) return 2;
  if (n <= 6) return 3;
  return 4;
}

// ─── MJPEG Player ────────────────────────────────────────────────────────────

function MjpegPlayer({
  camId, camName, token, isActive, pipeInfo, expanded, onExpand,
}: {
  camId:    string;
  camName:  string;
  token:    string;
  isActive: boolean;
  pipeInfo?: PipelineInfo;
  expanded: boolean;
  onExpand: () => void;
}) {
  const [phase, setPhase] = useState<'loading' | 'live' | 'error'>('loading');
  const [imgKey, setImgKey] = useState(0);
  const retry = useCallback(() => { setPhase('loading'); setImgKey(k => k + 1); }, []);

  useEffect(() => { setPhase('loading'); setImgKey(k => k + 1); }, [camId]);

  const fps  = pipeInfo?.stats?.fps ?? 0;
  const dets = pipeInfo?.stats?.yolo_detections ?? 0;
  const src  = `/api/v1/cameras/${encodeURIComponent(camId)}/stream?token=${encodeURIComponent(token)}`;

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      background: '#0D1117', overflow: 'hidden',
    }}>
      {/* Loading */}
      {phase === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 12,
          background: '#0D1117',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            border: '2px solid #1E293B', borderTopColor: '#1E3EB4',
            animation: 'lv-spin .7s linear infinite',
          }}/>
          <span style={{ fontSize: 11, color: '#374151', fontFamily: 'monospace' }}>
            {camId}
          </span>
        </div>
      )}

      {/* Error / No Signal */}
      {phase === 'error' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 14,
          background: '#0D1117',
        }}>
          <Camera size={28} color="#1E293B"/>
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 12, color: '#374151', margin: '0 0 4px', fontFamily: 'monospace', fontWeight: 700 }}>
              NO SIGNAL
            </p>
            <p style={{ fontSize: 11, color: '#1E293B', margin: 0 }}>
              {!isActive ? "Pipeline to'xtatilgan" : 'Stream yuklanmadi'}
            </p>
          </div>
          <button onClick={retry} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 14px',
            background: 'transparent', border: '1px solid #1E293B',
            borderRadius: 6, color: '#374151', cursor: 'pointer', fontSize: 11,
          }}>
            <RefreshCw size={11}/> Qayta
          </button>
        </div>
      )}

      {/* MJPEG img */}
      <img
        key={imgKey}
        src={src}
        alt={`${camId} stream`}
        style={{
          width: '100%', height: '100%', objectFit: 'contain',
          display: phase === 'error' ? 'none' : 'block',
        }}
        onLoad={() => setPhase('live')}
        onError={() => setPhase('error')}
      />

      {/* Scanline */}
      {phase === 'live' && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 2,
          backgroundImage: 'repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.012) 2px,rgba(0,0,0,.012) 4px)',
        }}/>
      )}

      {/* LIVE badge */}
      {phase === 'live' && isActive && (
        <div style={{
          position: 'absolute', top: 10, left: 10, zIndex: 5,
          display: 'flex', alignItems: 'center', gap: 5,
          background: 'rgba(0,0,0,.72)', backdropFilter: 'blur(6px)',
          border: '1px solid rgba(239,68,68,.3)',
          borderRadius: 5, padding: '3px 9px',
        }}>
          <div style={{
            width: 5, height: 5, borderRadius: '50%', background: '#EF4444',
            animation: 'lv-pulse 1.4s ease-in-out infinite',
          }}/>
          <span style={{
            fontFamily: 'monospace', fontSize: 9, fontWeight: 700,
            color: '#EF4444', letterSpacing: '.12em',
          }}>LIVE</span>
        </div>
      )}

      {/* Cam name */}
      <div style={{
        position: 'absolute', top: 10, left: phase === 'live' && isActive ? 76 : 10,
        zIndex: 5,
        background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(5px)',
        border: '1px solid rgba(255,255,255,.07)',
        borderRadius: 5, padding: '3px 9px',
        maxWidth: '55%',
      }}>
        <span style={{
          fontFamily: 'monospace', fontSize: 9, color: '#6B7280',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block',
        }}>
          {camName}
        </span>
      </div>

      {/* Fullscreen btn */}
      <button
        onClick={onExpand}
        title={expanded ? 'Kichraytirish' : 'Kattalashtirish'}
        style={{
          position: 'absolute', top: 10, right: 10, zIndex: 5,
          background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(5px)',
          border: '1px solid rgba(255,255,255,.07)',
          borderRadius: 5, padding: 6,
          cursor: 'pointer', color: '#6B7280', display: 'flex',
        }}
      >
        {expanded ? <Minimize2 size={12}/> : <Maximize2 size={12}/>}
      </button>

      {/* Stats */}
      {phase === 'live' && (fps > 0 || dets > 0) && (
        <div style={{
          position: 'absolute', bottom: 10, left: 10, zIndex: 5,
          display: 'flex', gap: 5,
        }}>
          {fps > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'rgba(0,0,0,.7)', border: '1px solid rgba(16,185,129,.25)',
              borderRadius: 4, padding: '2px 7px',
            }}>
              <Activity size={9} color="#10B981"/>
              <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#10B981', fontWeight: 700 }}>
                {fps.toFixed(1)} fps
              </span>
            </div>
          )}
          {dets > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'rgba(0,0,0,.7)', border: '1px solid rgba(139,92,246,.25)',
              borderRadius: 4, padding: '2px 7px',
            }}>
              <Tag size={9} color="#8B5CF6"/>
              <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#8B5CF6', fontWeight: 700 }}>
                {dets}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Status dot */}
      <div style={{
        position: 'absolute', bottom: 10, right: 10, zIndex: 5,
        width: 7, height: 7, borderRadius: '50%',
        background: isActive ? '#10B981' : '#6B7280',
        boxShadow: isActive ? '0 0 5px rgba(16,185,129,.6)' : 'none',
      }}/>
    </div>
  );
}

// ─── Camera Card ─────────────────────────────────────────────────────────────

function CameraCard({
  cam, status, pipeInfo, token, expanded, onExpand,
}: {
  cam:      CameraItem;
  status?:  CameraStatus;
  pipeInfo?: PipelineInfo;
  token:    string;
  expanded: boolean;
  onExpand: () => void;
}) {
  const isActive = status?.is_active ?? false;
  const hasError = !!status?.error;
  const running  = pipeInfo?.running ?? false;

  const borderColor = running
    ? '#A7F3D0'
    : hasError
    ? '#FECACA'
    : '#E4E7ED';

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${borderColor}`,
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: running
        ? '0 1px 4px rgba(16,185,129,.12)'
        : '0 1px 3px rgba(0,0,0,.05)',
      transition: 'border-color .2s, box-shadow .2s',
    }}>
      {/* Video — 16:9 */}
      <div style={{ position: 'relative', aspectRatio: '16/9', width: '100%' }}>
        <MjpegPlayer
          camId={cam.id}
          camName={cam.name}
          token={token}
          isActive={isActive}
          pipeInfo={pipeInfo}
          expanded={expanded}
          onExpand={onExpand}
        />
      </div>

      {/* Footer */}
      <div style={{
        padding: '8px 14px',
        display: 'flex', alignItems: 'center', gap: 8,
        borderTop: '1px solid #F3F4F6',
        background: running ? 'rgba(16,185,129,.03)' : '#FAFAFA',
      }}>
        {/* Status dot */}
        <div style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: isActive ? '#10B981' : hasError ? '#EF4444' : '#D1D5DB',
          boxShadow: isActive ? '0 0 4px rgba(16,185,129,.5)' : 'none',
        }}/>

        <span style={{
          fontSize: 12, fontWeight: 700, color: '#0D1117',
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {cam.name}
        </span>

        {/* Type */}
        <span style={{
          fontSize: 9, padding: '1px 7px', borderRadius: 20,
          background: '#F3F4F6', color: '#9CA3AF',
          fontFamily: 'monospace', textTransform: 'uppercase',
          letterSpacing: '.06em', flexShrink: 0,
        }}>
          {cam.type}
        </span>

        {/* Status */}
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 20,
          background: isActive ? '#ECFDF5' : hasError ? '#FEF2F2' : '#F3F4F6',
          color: isActive ? '#059669' : hasError ? '#DC2626' : '#9CA3AF',
          fontWeight: 600, flexShrink: 0,
        }}>
          {isActive ? 'Faol' : hasError ? 'Xato' : 'Nofaol'}
        </span>
      </div>
    </div>
  );
}

// ─── Detection Log Row ───────────────────────────────────────────────────────

function EventRow({ ev, fresh }: { ev: DetectionEvent; fresh: boolean }) {
  const accent    = ev.identified ? '#10B981' : '#F59E0B';
  const confColor = ev.confidence >= .85 ? '#10B981'
                  : ev.confidence >= .65 ? '#F59E0B' : '#EF4444';

  return (
    <div style={{
      padding: '9px 14px',
      borderLeft: `2px solid ${fresh ? accent : 'transparent'}`,
      borderBottom: '1px solid #F9FAFB',
      background: fresh
        ? `rgba(${ev.identified ? '16,185,129' : '245,158,11'},.04)`
        : 'transparent',
      transition: 'all .4s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: accent, flexShrink: 0,
        }}/>
        <span style={{
          fontFamily: 'monospace', fontSize: 12, fontWeight: 700,
          color: '#0D1117', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {ev.identified ? ev.animal_tag_id : '— Tanilmadi'}
        </span>
        <span style={{
          fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: confColor, flexShrink: 0,
        }}>
          {(ev.confidence * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 12 }}>
        <Scale size={9} color="#D1D5DB"/>
        <span style={{ fontSize: 10, color: '#6B7280' }}>
          {ev.estimated_weight_kg.toFixed(1)} kg
        </span>
        <span style={{
          fontSize: 9, color: '#9CA3AF', fontFamily: 'monospace',
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {ev.camera_id}
        </span>
        <span style={{ fontSize: 9, color: '#D1D5DB', flexShrink: 0 }}>
          {timeAgo(ev.timestamp)}
        </span>
      </div>
    </div>
  );
}

// ─── Detection Panel ─────────────────────────────────────────────────────────

function DetectionPanel({
  events, filter,
}: {
  events: DetectionEvent[];
  filter: string | null;
}) {
  const list       = filter ? events.filter(e => e.camera_id === filter) : events;
  const identified = list.filter(e => e.identified).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid #F3F4F6',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
        background: '#FAFAFA',
      }}>
        <Activity size={13} color="#1E3EB4"/>
        <span style={{
          fontSize: 11, fontWeight: 700, color: '#374151',
          letterSpacing: '.04em', textTransform: 'uppercase',
        }}>
          Detection Log
        </span>
        {list.length > 0 && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
            <span style={{
              fontSize: 10, padding: '1px 7px',
              background: '#ECFDF5', color: '#059669', borderRadius: 20,
              fontWeight: 600,
            }}>{identified} ID</span>
            <span style={{
              fontSize: 10, padding: '1px 7px',
              background: '#F3F4F6', color: '#6B7280', borderRadius: 20,
              fontWeight: 600,
            }}>{list.length}</span>
          </div>
        )}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {list.length === 0 ? (
          <div style={{
            padding: '40px 16px', textAlign: 'center',
          }}>
            <Activity size={22} color="#E5E7EB" style={{ margin: '0 auto 10px', display: 'block' }}/>
            <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
              {filter ? 'Bu kamerada detection yo\'q' : 'Hali detection yo\'q'}
            </p>
          </div>
        ) : (
          list.map((ev, i) => (
            <EventRow key={`${ev.timestamp}-${ev.camera_id}-${i}`} ev={ev} fresh={i === 0}/>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function LiveFeedPage() {
  const token = localStorage.getItem('tv_access_token') ?? '';

  const { status: wsStatus, liveDetections } = useWebSocketContext();

  const [events, setEvents]           = useState<DetectionEvent[]>([]);
  const [expandedCam, setExpandedCam] = useState<string | null>(null);
  const [filterCam, setFilterCam]     = useState<string | null>(null);
  const lastKey                        = useRef('');

  // Cameras list (DB) — field `id` = camera_id string, `enabled` = boolean
  const { data: cameras = [], isError: camsError } = useQuery<CameraItem[]>({
    queryKey:        ['cameras', 'list'],
    queryFn:         () => apiFetch<CameraItem[]>('/api/v1/cameras/'),
    refetchInterval: 15_000,
  });

  // Runtime status polling (2.5s)
  const { data: statuses = {} as Record<string, CameraStatus> } = useQuery({
    queryKey:        ['cameras', 'stats'],
    queryFn:         () => apiFetch<Record<string, CameraStatus>>('/api/v1/cameras/stats/all')
      .catch(() => ({} as Record<string, CameraStatus>)),
    refetchInterval: 2500,
  });

  // Pipeline status (2.5s)
  const { data: plData, refetch: refetchPl } = useQuery<AllPipelinesStatus>({
    queryKey:        ['pipeline', 'status'],
    queryFn:         () => apiFetch<AllPipelinesStatus>('/api/v1/pipeline/status')
      .catch(() => ({ total_running: 0, running_cameras: [], pipelines: {} }) as AllPipelinesStatus),
    refetchInterval: 2500,
  });

  // Enabled cameras — field is `enabled` not `is_enabled`
  const enabledCams = cameras.filter(c => c.enabled);
  const activeCnt   = enabledCams.filter(c => statuses[c.id]?.is_active).length;

  // WS detection events
  useEffect(() => {
    if (!liveDetections.length) return;
    const raw = liveDetections[0] as any;
    if (!raw) return;
    const key = `${raw.timestamp}-${raw.camera_id}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    setEvents(prev => [{
      camera_id:           raw.camera_id          ?? '',
      animal_id:           raw.animal_id           ?? null,
      animal_tag_id:       raw.animal_tag_id       ?? 'UNKNOWN',
      confidence:          raw.confidence_score    ?? raw.confidence ?? 0,
      estimated_weight_kg: raw.estimated_weight_kg ?? 0,
      identified:          raw.identified          ?? (raw.animal_id !== null),
      timestamp:           raw.timestamp,
    }, ...prev].slice(0, 80));
  }, [liveDetections]);

  // Expand handler
  const handleExpand = useCallback((id: string) => {
    setExpandedCam(prev => {
      const next = prev === id ? null : id;
      setFilterCam(next);
      return next;
    });
  }, []);

  // ESC
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setExpandedCam(null); setFilterCam(null); }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  const wsOk    = wsStatus === WsStatus.CONNECTED;
  const wsColor = wsOk ? '#10B981'
                : wsStatus === WsStatus.RECONNECTING ? '#F59E0B' : '#9CA3AF';
  const cols    = expandedCam ? 1 : gridCols(enabledCams.length);

  return (
    <div style={{
      height: 'calc(100vh - 64px)',
      overflow: 'hidden',
      background: 'var(--bg, #F7F8FA)',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Outfit', system-ui, sans-serif",
    }}>
      <style>{`
        @keyframes lv-spin  { to { transform: rotate(360deg); } }
        @keyframes lv-pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
        .lv-pill-btn {
          padding: 4px 12px; border-radius: 20px; cursor: pointer;
          font-size: 12px; font-weight: 600; transition: all .15s;
          border: 1px solid transparent; background: #F3F4F6; color: #6B7280;
          font-family: 'Outfit', sans-serif;
        }
        .lv-pill-btn:hover { background: #E5E7EB; color: #374151; }
        .lv-pill-btn.active { background: #EEF2FF; border-color: rgba(30,62,180,.3); color: #1E3EB4; }
        .lv-scroll::-webkit-scrollbar { width: 4px; }
        .lv-scroll::-webkit-scrollbar-track { background: transparent; }
        .lv-scroll::-webkit-scrollbar-thumb { background: #E4E7ED; border-radius: 4px; }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={{
        padding: '12px 24px',
        background: 'var(--surface, #fff)',
        borderBottom: '1px solid var(--border, #E4E7ED)',
        display: 'flex', alignItems: 'center', gap: 14,
        flexShrink: 0,
      }}>
        {/* Title */}
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: '#0D1117', margin: 0, lineHeight: 1 }}>
            Live Monitor
          </h1>
          <p style={{ fontSize: 12, color: '#9CA3AF', margin: '2px 0 0' }}>
            {activeCnt}/{enabledCams.length} kamera faol
          </p>
        </div>

        <div style={{ width: 1, height: 28, background: '#E4E7ED', flexShrink: 0 }}/>

        {/* Camera filter pills */}
        <div style={{
          flex: 1, display: 'flex', gap: 6, overflowX: 'auto',
          scrollbarWidth: 'none', alignItems: 'center',
        }}>
          <button
            className={`lv-pill-btn${filterCam === null ? ' active' : ''}`}
            onClick={() => { setFilterCam(null); setExpandedCam(null); }}
          >
            Hammasi
          </button>
          {enabledCams.map(cam => {
            const active = statuses[cam.id]?.is_active ?? false;
            const sel    = filterCam === cam.id;
            return (
              <button
                key={cam.id}
                className={`lv-pill-btn${sel ? ' active' : ''}`}
                onClick={() => { setFilterCam(sel ? null : cam.id); setExpandedCam(null); }}
                style={{
                  borderColor: active ? 'rgba(16,185,129,.3)' : 'transparent',
                }}
              >
                <span style={{
                  display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                  background: active ? '#10B981' : '#D1D5DB',
                  marginRight: 5, verticalAlign: 'middle',
                }}/>
                {cam.name}
              </button>
            );
          })}
        </div>

        {/* Right side */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          {/* WS status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {wsOk
              ? <Wifi size={14} color={wsColor}/>
              : <WifiOff size={14} color={wsColor}/>
            }
            <span style={{ fontSize: 11, color: wsColor, fontWeight: 600 }}>
              {wsStatus === WsStatus.CONNECTED    ? 'WS'
               : wsStatus === WsStatus.RECONNECTING ? 'Sync'
               : 'Offline'}
            </span>
          </div>

          <button
            onClick={() => refetchPl()}
            style={{
              padding: '6px 8px',
              border: '1px solid #E4E7ED', borderRadius: 8,
              background: '#fff', cursor: 'pointer', display: 'flex', color: '#6B7280',
            }}
          >
            <RefreshCw size={14}/>
          </button>
        </div>
      </div>

      {/* ── Body ───────────────────────────────────────────────── */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1fr 280px',
        overflow: 'hidden',
      }}>

        {/* ── Left: grid ─────────────────────────────────────── */}
        <div className="lv-scroll" style={{
          overflowY: 'auto', padding: 16,
        }}>
          {/* Backend offline warning */}
          {camsError && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '12px 16px', marginBottom: 16,
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 10,
            }}>
              <AlertTriangle size={15} color="#DC2626"/>
              <p style={{ fontSize: 13, color: '#DC2626', margin: 0 }}>
                Backend bilan aloqa yo'q. Server ishlayotganini tekshiring.
              </p>
            </div>
          )}

          {/* No pipeline warning */}
          {!camsError && enabledCams.length > 0 && activeCnt === 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px', marginBottom: 16,
              background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 10,
            }}>
              <AlertTriangle size={14} color="#D97706"/>
              <p style={{ fontSize: 12, color: '#92400E', margin: 0 }}>
                Kameralar nofaol — Kameralar sahifasidan pipeline ishga tushiring.
              </p>
              <a href="/cameras" style={{
                marginLeft: 'auto', fontSize: 12, fontWeight: 600,
                color: '#1E3EB4', textDecoration: 'none', flexShrink: 0,
              }}>
                Kameralar →
              </a>
            </div>
          )}

          {/* Empty state */}
          {!camsError && enabledCams.length === 0 && (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              minHeight: 360, gap: 16,
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: 16,
                background: '#EEF2FF', border: '1px solid #C7D2FE',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Camera size={28} color="#818CF8"/>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', margin: '0 0 4px' }}>
                  Kamera yo'q
                </p>
                <p style={{ fontSize: 13, color: '#9CA3AF', margin: 0 }}>
                  Kameralar sahifasidan kamera qo'shing
                </p>
              </div>
              <a href="/cameras" style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '9px 20px',
                background: '#1E3EB4', color: '#fff',
                borderRadius: 8, fontSize: 13, fontWeight: 700, textDecoration: 'none',
              }}>
                <Play size={13}/> Kameralar
              </a>
            </div>
          )}

          {/* Camera grid */}
          {enabledCams.length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, 1fr)`,
              gap: 14,
            }}>
              {(expandedCam
                ? enabledCams.filter(c => c.id === expandedCam)
                : enabledCams
              ).map(cam => (
                <CameraCard
                  key={cam.id}
                  cam={cam}
                  status={statuses[cam.id]}
                  pipeInfo={plData?.pipelines?.[cam.id]}
                  token={token}
                  expanded={expandedCam === cam.id}
                  onExpand={() => handleExpand(cam.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Right: detection panel ─────────────────────────── */}
        <div style={{
          borderLeft: '1px solid #E4E7ED',
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          background: '#fff',
        }}>
          <DetectionPanel events={events} filter={filterCam}/>
        </div>
      </div>
    </div>
  );
}