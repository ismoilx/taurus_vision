/**
 * Taurus Vision — Live Monitor
 *
 * Sodda va ishlaydigan live feed sahifasi:
 *   - Kameralar grid ko'rinishida, har birida MJPEG stream
 *   - Pipeline holati (aktiv/nofaol) ko'rinadi
 *   - Detection log o'ng panelda
 *   - Ortiqcha UI yo'q — faqat kerakli narsa
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Camera, Wifi, WifiOff, RefreshCw,
  Maximize2, Minimize2, Activity, AlertTriangle, Play,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch }            from '../utils/apiFetch';
import { useWebSocketContext } from '../context/WebSocketContext';
import { ConnectionStatus as WsStatus } from '../shared/types';
import { useResponsive } from '../hooks/useResponsive';

// ─── Types ───────────────────────────────────────────────────────────────────

interface CameraItem {
  id:       string;
  name:     string;
  type:     string;
  source:   string | null;
  device_id: number | null;
  fps:      number;
  enabled:  boolean;
  status:   string;   // 'active' | 'inactive'
}

interface PipelineInfo {
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
  pipelines:       Record<string, PipelineInfo>;
}

interface DetectionEvent {
  camera_id:           string;
  track_id:            number | null;
  animal_tag_id:       string;
  state:               'unidentified' | 'identified';
  bbox_color:          'red' | 'green' | 'orange';
  confidence:          number;
  id_score:            number;
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

// ─── MJPEG Player ─────────────────────────────────────────────────────────────

function MjpegPlayer({
  cam, token, pipeInfo, expanded, onExpand,
}: {
  cam:      CameraItem;
  token:    string;
  pipeInfo?: PipelineInfo;
  expanded: boolean;
  onExpand: () => void;
}) {
  // LAZY LOAD: stream faqat foydalanuvchi "Ko'rish" bosganda ochiladi
  const [streamActive, setStreamActive] = useState(false);
  const [phase, setPhase] = useState<'loading' | 'live' | 'error'>('idle' as any);
  const [imgKey, setImgKey] = useState(0);
  const retry = useCallback(() => { setPhase('loading'); setImgKey(k => k + 1); }, []);

  // Kamera o'zgarganda streamni to'xtatib, qayta bosishni talab qilish
  useEffect(() => {
    setStreamActive(false);
    setPhase('idle' as any);
  }, [cam.id]);

  // Expand bo'lganda avtomatik stream boshlash
  useEffect(() => {
    if (expanded) { setStreamActive(true); setPhase('loading'); }
  }, [expanded]);

  const running = pipeInfo?.running ?? false;
  const fps     = pipeInfo?.stats?.fps ?? 0;
  const src     = `/api/v1/cameras/${encodeURIComponent(cam.id)}/stream?token=${encodeURIComponent(token)}`;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#0D1117', overflow: 'hidden' }}>

      {/* Loading spinner */}
      {phase === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 10,
          background: '#0D1117',
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            border: '2px solid #1E293B', borderTopColor: '#3B82F6',
            animation: 'lv-spin .7s linear infinite',
          }}/>
          <span style={{ fontSize: 10, color: '#374151', fontFamily: 'monospace' }}>
            {cam.id}
          </span>
        </div>
      )}

      {/* No signal / Error */}
      {phase === 'error' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 12,
          background: '#0D1117',
        }}>
          <Camera size={32} color="#1E293B"/>
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 12, color: '#4B5563', margin: '0 0 4px', fontWeight: 700 }}>
              NO SIGNAL
            </p>
            <p style={{ fontSize: 11, color: '#374151', margin: 0 }}>
              {!running ? "Pipeline to'xtatilgan" : 'Stream yuklanmadi'}
            </p>
          </div>
          {running && (
            <button onClick={retry} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 14px',
              background: 'transparent', border: '1px solid #1E293B',
              borderRadius: 6, color: '#4B5563', cursor: 'pointer', fontSize: 11,
            }}>
              <RefreshCw size={11}/> Qayta urinish
            </button>
          )}
        </div>
      )}

      {/* IDLE — Stream bosilmagan holat */}
      {!streamActive && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 12,
          background: '#0D1117',
        }}>
          <Camera size={28} color="#1E293B"/>
          <p style={{ fontSize: 11, color: '#4B5563', margin: 0 }}>
            {running ? 'Pipeline aktiv' : "Pipeline to'xtatilgan"}
          </p>
          {running && (
            <button
              onClick={() => { setStreamActive(true); setPhase('loading'); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '6px 16px',
                background: '#1E3EB4', border: 'none',
                borderRadius: 6, color: '#fff', cursor: 'pointer', fontSize: 11, fontWeight: 600,
              }}
            >
              <Play size={11}/> Ko'rish
            </button>
          )}
        </div>
      )}

      {/* MJPEG kadr — faqat streamActive bo'lganda */}
      {streamActive && (
        <img
          key={imgKey}
          src={src}
          alt={`${cam.name} stream`}
          style={{ width: '100%', height: '100%', objectFit: 'contain', display: phase === 'error' ? 'none' : 'block' }}
          onLoad={() => setPhase('live')}
          onError={() => { setPhase('error'); }}
        />
      )}

      {/* LIVE badge */}
      {phase === 'live' && running && (
        <div style={{
          position: 'absolute', top: 8, left: 8, zIndex: 5,
          display: 'flex', alignItems: 'center', gap: 4,
          background: 'rgba(0,0,0,.75)', backdropFilter: 'blur(4px)',
          border: '1px solid rgba(239,68,68,.4)',
          borderRadius: 4, padding: '2px 8px',
        }}>
          <div style={{
            width: 5, height: 5, borderRadius: '50%', background: '#EF4444',
            animation: 'lv-pulse 1.4s ease-in-out infinite',
          }}/>
          <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: '#EF4444', letterSpacing: '.1em' }}>
            LIVE
          </span>
        </div>
      )}

      {/* Kamera nomi */}
      <div style={{
        position: 'absolute', top: 8, left: phase === 'live' && running ? 68 : 8,
        zIndex: 5,
        background: 'rgba(0,0,0,.6)', backdropFilter: 'blur(4px)',
        border: '1px solid rgba(255,255,255,.06)',
        borderRadius: 4, padding: '2px 8px', maxWidth: '60%',
      }}>
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#6B7280',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>
          {cam.name}
        </span>
      </div>

      {/* Fullscreen button */}
      <button onClick={onExpand} style={{
        position: 'absolute', top: 8, right: 8, zIndex: 5,
        background: 'rgba(0,0,0,.6)', backdropFilter: 'blur(4px)',
        border: '1px solid rgba(255,255,255,.06)',
        borderRadius: 4, padding: 5, cursor: 'pointer',
        color: '#6B7280', display: 'flex',
      }}>
        {expanded ? <Minimize2 size={11}/> : <Maximize2 size={11}/>}
      </button>

      {/* FPS badge (pipeline ishlayotganda) */}
      {phase === 'live' && fps > 0 && (
        <div style={{
          position: 'absolute', bottom: 8, left: 8, zIndex: 5,
          display: 'flex', alignItems: 'center', gap: 4,
          background: 'rgba(0,0,0,.7)', border: '1px solid rgba(16,185,129,.3)',
          borderRadius: 4, padding: '2px 7px',
        }}>
          <Activity size={8} color="#10B981"/>
          <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#10B981', fontWeight: 700 }}>
            {fps.toFixed(1)} fps
          </span>
        </div>
      )}

      {/* Holat nuqtasi */}
      <div style={{
        position: 'absolute', bottom: 8, right: 8, zIndex: 5,
        width: 7, height: 7, borderRadius: '50%',
        background: running ? '#10B981' : '#4B5563',
        boxShadow: running ? '0 0 6px rgba(16,185,129,.6)' : 'none',
      }}/>
    </div>
  );
}

// ─── Camera Card ──────────────────────────────────────────────────────────────

function CameraCard({ cam, pipeInfo, token, expanded, onExpand }: {
  cam:      CameraItem;
  pipeInfo?: PipelineInfo;
  token:    string;
  expanded: boolean;
  onExpand: () => void;
}) {
  const running = pipeInfo?.running ?? false;

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${running ? '#A7F3D0' : '#E4E7ED'}`,
      borderRadius: 10, overflow: 'hidden',
      boxShadow: running ? '0 1px 4px rgba(16,185,129,.1)' : '0 1px 3px rgba(0,0,0,.05)',
      transition: 'border-color .2s',
    }}>
      {/* Video — 16:9 */}
      <div style={{ position: 'relative', aspectRatio: '16/9', width: '100%' }}>
        <MjpegPlayer
          cam={cam} token={token}
          pipeInfo={pipeInfo}
          expanded={expanded} onExpand={onExpand}
        />
      </div>

      {/* Footer */}
      <div style={{
        padding: '7px 12px',
        display: 'flex', alignItems: 'center', gap: 7,
        borderTop: '1px solid #F3F4F6',
        background: running ? 'rgba(16,185,129,.03)' : '#FAFAFA',
      }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: running ? '#10B981' : '#D1D5DB',
          boxShadow: running ? '0 0 4px rgba(16,185,129,.5)' : 'none',
        }}/>

        <span style={{ fontSize: 12, fontWeight: 700, color: '#0D1117', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {cam.name}
        </span>

        <span style={{
          fontSize: 9, padding: '1px 6px', borderRadius: 20,
          background: '#F3F4F6', color: '#9CA3AF',
          fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '.05em',
        }}>
          {cam.type}
        </span>

        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 600,
          background: running ? '#ECFDF5' : '#F3F4F6',
          color: running ? '#059669' : '#9CA3AF',
        }}>
          {running ? 'Aktiv' : 'Nofaol'}
        </span>
      </div>
    </div>
  );
}

// ─── Detection Log ────────────────────────────────────────────────────────────

function DetectionPanel({ events }: { events: DetectionEvent[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid #F3F4F6',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
        background: '#FAFAFA',
      }}>
        <Activity size={13} color="#1E3EB4"/>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#374151',
          letterSpacing: '.04em', textTransform: 'uppercase' }}>
          Tracker Log
        </span>
        {events.length > 0 && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
            <span style={{ fontSize: 10, padding: '1px 7px',
              background: '#ECFDF5', color: '#059669', borderRadius: 20, fontWeight: 600 }}>
              {events.filter(e => e.state === 'identified').length} ID
            </span>
            <span style={{ fontSize: 10, padding: '1px 7px',
              background: '#FEF2F2', color: '#DC2626', borderRadius: 20, fontWeight: 600 }}>
              {events.filter(e => e.state === 'unidentified').length} ?
            </span>
            <span style={{ fontSize: 10, padding: '1px 7px',
              background: '#F3F4F6', color: '#6B7280', borderRadius: 20, fontWeight: 600 }}>
              {events.length}
            </span>
          </div>
        )}
      </div>

      {/* Ro'yxat */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {events.length === 0 ? (
          <div style={{ padding: '40px 16px', textAlign: 'center' }}>
            <Activity size={22} color="#E5E7EB" style={{ margin: '0 auto 10px', display: 'block' }}/>
            <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
              Hali detection yo'q
            </p>
          </div>
        ) : events.map((ev, i) => {
          const isId    = ev.state === 'identified';
          const accent  = isId ? '#10B981' : '#EF4444';
          const bgAccent = isId ? '16,185,129' : '239,68,68';
          const fresh   = i === 0;

          return (
            <div key={`${ev.timestamp}-${i}`} style={{
              padding: '8px 14px',
              borderLeft: `2px solid ${fresh ? accent : 'transparent'}`,
              borderBottom: '1px solid #F9FAFB',
              background: fresh ? `rgba(${bgAccent},.04)` : 'transparent',
              transition: 'all .4s',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                {/* Rang nuqtasi — qizil yoki yashil */}
                <div style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: accent, flexShrink: 0,
                  boxShadow: `0 0 5px ${accent}88`,
                }}/>
                <span style={{ fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: '#0D1117', flex: 1 }}>
                  {isId ? ev.animal_tag_id : `T#${ev.track_id ?? '?'} — Tanilmadi`}
                </span>
                <span style={{
                  fontSize: 9, padding: '1px 6px', borderRadius: 10, fontWeight: 700,
                  background: isId ? '#ECFDF5' : '#FEF2F2',
                  color: isId ? '#059669' : '#DC2626',
                }}>
                  {isId ? 'ID' : '?'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 13 }}>
                <span style={{ fontSize: 10, color: '#6B7280' }}>
                  conf: {(ev.confidence * 100).toFixed(0)}%
                </span>
                {ev.id_score > 0 && (
                  <span style={{ fontSize: 10, color: '#6B7280' }}>
                    sim: {(ev.id_score * 100).toFixed(0)}%
                  </span>
                )}
                <span style={{ fontSize: 9, color: '#9CA3AF', flex: 1, overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
                  {ev.camera_id}
                </span>
                <span style={{ fontSize: 9, color: '#D1D5DB' }}>
                  {timeAgo(ev.timestamp)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LiveFeedPage() {
  const token = localStorage.getItem('tv_access_token') ?? '';
  const { status: wsStatus, liveDetections, liveTrackedUpdates } = useWebSocketContext();
  const { isMobile, isTablet } = useResponsive();

  const [events, setEvents]           = useState<DetectionEvent[]>([]);
  const [expandedCam, setExpandedCam] = useState<string | null>(null);
  const lastKey                        = useRef('');

  // Kameralar ro'yxati
  const { data: cameras = [], isError: camsError } = useQuery<CameraItem[]>({
    queryKey:        ['cameras', 'list'],
    queryFn:         () => apiFetch<CameraItem[]>('/api/v1/cameras/'),
    refetchInterval: 15_000,
  });

  // Pipeline holati
  const { data: plData, refetch: refetchPl } = useQuery<AllPipelinesStatus>({
    queryKey:        ['pipeline', 'status'],
    queryFn:         () => apiFetch<AllPipelinesStatus>('/api/v1/pipeline/status')
      .catch(() => ({ total_running: 0, running_cameras: [], pipelines: {} }) as AllPipelinesStatus),
    refetchInterval: 3000,
  });

  const enabledCams  = cameras.filter(c => c.enabled);
  const activeCnt    = plData?.running_cameras.length ?? 0;

  // WS tracked detection events (YANGI — CattleTracker)
  useEffect(() => {
    if (!liveTrackedUpdates.length) return;
    const latest = liveTrackedUpdates[0];
    if (!latest) return;
    const key = `${latest.timestamp}-${latest.camera_id}-${latest.track_id}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    const newEvent: DetectionEvent = {
      camera_id:     latest.camera_id,
      track_id:      latest.track_id,
      animal_tag_id: latest.tag_id ?? `T#${latest.track_id}`,
      state:         latest.state === 'identified' ? 'identified' : 'unidentified',
      bbox_color:    latest.bbox_color,
      confidence:    latest.confidence,
      id_score:      latest.id_score,
      timestamp:     latest.timestamp,
    };
    setEvents(prev => [newEvent, ...prev].slice(0, 60));
  }, [liveTrackedUpdates]);

  // Legacy detection events (eski pipeline uchun orqaga moslik)
  useEffect(() => {
    if (!liveDetections.length) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const raw = liveDetections[0] as any;
    if (!raw) return;
    const key = `legacy-${raw.timestamp}-${raw.camera_id}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    const newEvent: DetectionEvent = {
      camera_id:     raw.camera_id     ?? '',
      track_id:      null,
      animal_tag_id: raw.animal_tag_id ?? 'UNKNOWN',
      state:         raw.animal_id != null ? 'identified' : 'unidentified',
      bbox_color:    raw.animal_id != null ? 'green'      : 'red',
      confidence:    raw.confidence_score ?? raw.confidence ?? 0,
      id_score:      0,
      timestamp:     raw.timestamp ?? new Date().toISOString(),
    };
    setEvents(prev => [newEvent, ...prev].slice(0, 60));
  }, [liveDetections]);

  const handleExpand = useCallback((id: string) => {
    setExpandedCam(prev => prev === id ? null : id);
  }, []);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') setExpandedCam(null); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  const wsOk    = wsStatus === WsStatus.CONNECTED;
  const wsColor = wsOk ? '#10B981' : wsStatus === WsStatus.RECONNECTING ? '#F59E0B' : '#9CA3AF';
  const cols    = expandedCam ? 1 : gridCols(enabledCams.length);

  return (
    <div style={{
      height: isMobile ? 'auto' : 'calc(100vh - 64px)',
      minHeight: isMobile ? 'calc(100vh - 64px)' : undefined,
      overflow: isMobile ? 'auto' : 'hidden',
      background: '#F7F8FA', display: 'flex', flexDirection: 'column',
      fontFamily: "'Outfit', system-ui, sans-serif",
    }}>
      <style>{`
        @keyframes lv-spin  { to { transform: rotate(360deg); } }
        @keyframes lv-pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
        .lv-scroll::-webkit-scrollbar { width: 4px; }
        .lv-scroll::-webkit-scrollbar-thumb { background: #E4E7ED; border-radius: 4px; }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────── */}
      <div style={{
        padding: '10px 20px',
        background: '#fff', borderBottom: '1px solid #E4E7ED',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800, color: '#0D1117', margin: 0, lineHeight: 1 }}>
            Live Monitor
          </h1>
          <p style={{ fontSize: 11, color: '#9CA3AF', margin: '2px 0 0' }}>
            {activeCnt}/{enabledCams.length} kamera aktiv
          </p>
        </div>

        <div style={{ width: 1, height: 24, background: '#E4E7ED' }}/>

        {/* WS holati */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {wsOk ? <Wifi size={13} color={wsColor}/> : <WifiOff size={13} color={wsColor}/>}
          <span style={{ fontSize: 11, color: wsColor, fontWeight: 600 }}>
            {wsOk ? 'WS' : wsStatus === WsStatus.RECONNECTING ? 'Sync...' : 'Offline'}
          </span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {expandedCam && (
            <button onClick={() => setExpandedCam(null)} style={{
              fontSize: 12, color: '#6B7280', background: 'none', border: 'none',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
            }}>
              <Minimize2 size={13}/> Orqaga
            </button>
          )}
          <button onClick={() => refetchPl()} style={{
            padding: '5px 8px', border: '1px solid #E4E7ED', borderRadius: 7,
            background: '#fff', cursor: 'pointer', display: 'flex', color: '#6B7280',
          }}>
            <RefreshCw size={13}/>
          </button>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: isMobile ? '1fr' : (isTablet ? '1fr' : '1fr 260px'), overflow: isMobile ? 'auto' : 'hidden' }}>

        {/* ── Kamera grid ─────────────────────────────────────── */}
        <div className="lv-scroll" style={{ overflowY: 'auto', padding: 14 }}>

          {/* Backend offline */}
          {camsError && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 14px', marginBottom: 14,
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8,
            }}>
              <AlertTriangle size={14} color="#DC2626"/>
              <p style={{ fontSize: 12, color: '#DC2626', margin: 0 }}>
                Backend bilan aloqa yo'q. Docker ishlayotganini tekshiring.
              </p>
            </div>
          )}

          {/* Pipeline yo'q warning */}
          {!camsError && enabledCams.length > 0 && activeCnt === 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 14px', marginBottom: 14,
              background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 8,
            }}>
              <AlertTriangle size={13} color="#D97706"/>
              <p style={{ fontSize: 12, color: '#92400E', margin: 0 }}>
                Kameralar nofaol — Kameralar sahifasidan pipeline ishga tushiring.
              </p>
              <a href="/cameras" style={{
                marginLeft: 'auto', fontSize: 12, fontWeight: 700,
                color: '#1E3EB4', textDecoration: 'none', flexShrink: 0,
              }}>
                Kameralar →
              </a>
            </div>
          )}

          {/* Bo'sh holat */}
          {!camsError && enabledCams.length === 0 && (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              minHeight: 320, gap: 14,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 14,
                background: '#EEF2FF', border: '1px solid #C7D2FE',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Camera size={24} color="#818CF8"/>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 4px' }}>
                  Kamera yo'q
                </p>
                <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
                  Kameralar sahifasidan kamera qo'shing va pipeline ishga tushiring
                </p>
              </div>
              <a href="/cameras" style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '8px 18px', background: '#1E3EB4', color: '#fff',
                borderRadius: 8, fontSize: 13, fontWeight: 700, textDecoration: 'none',
              }}>
                <Play size={12}/> Kameralar
              </a>
            </div>
          )}

          {/* Kameralar grid */}
          {enabledCams.length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, 1fr)`,
              gap: 12,
            }}>
              {(expandedCam
                ? enabledCams.filter(c => c.id === expandedCam)
                : enabledCams
              ).map(cam => (
                <CameraCard
                  key={cam.id}
                  cam={cam}
                  pipeInfo={plData?.pipelines?.[cam.id]}
                  token={token}
                  expanded={expandedCam === cam.id}
                  onExpand={() => handleExpand(cam.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Detection panel ─────────────────────────────────── */}
        {!isMobile && !isTablet && (
          <div style={{
            borderLeft: '1px solid #E4E7ED',
            overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
            background: '#fff',
          }}>
            <DetectionPanel events={events}/>
          </div>
        )}
      </div>

      {/* ── Mobile Detection Panel (below cameras) ──────────── */}
      {(isMobile || isTablet) && events.length > 0 && (
        <div style={{
          borderTop: '1px solid #E4E7ED',
          background: '#fff',
          maxHeight: 220,
          overflowY: 'auto',
        }}>
          <DetectionPanel events={events}/>
        </div>
      )}
    </div>
  );
}