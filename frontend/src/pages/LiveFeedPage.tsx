/**
 * Taurus Vision — Live Feed Page
 *
 * Arxitektura:
 *   VIDEO:     <img src="/api/v1/cameras/{id}/stream?token=...">
 *              Backend MJPEG formatida kadrlar + cv2 bbox overlay yuboradi.
 *
 *   WEBSOCKET: Detection eventlari kelib o'ng panelni yangilaydi —
 *              animal nomi, confidence, vazn, vaqt.
 *
 *   KAMERA:    Pipeline/status dan aktiv kameralar ro'yxati.
 *              Tabs orqali tanlash, avtomatik birinchisi tanlanadi.
 */

import { useState, useEffect, useRef } from 'react';
import {
  Camera, Wifi, WifiOff, RefreshCw, ZoomIn, ZoomOut,
  Activity, Eye, Tag, Scale, AlertTriangle, Play,
} from 'lucide-react';
import { useQuery }            from '@tanstack/react-query';
import { apiFetch }            from '../utils/apiFetch';
import { useWebSocketContext } from '../context/WebSocketContext';
import { ConnectionStatus as WsStatus } from '../shared/types';

// ─── Types ─────────────────────────────────────────────────────────────────

interface PipelineStats {
  fps:        number;
  frames:     number;
  detections: number;
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
  camera_id:            string;
  animal_id:            number | null;
  animal_tag_id:        string;
  confidence:           number;
  estimated_weight_kg:  number;
  identified:           boolean;
  timestamp:            string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 4000)  return 'Hozir';
  if (ms < 60000) return `${Math.floor(ms / 1000)}s`;
  return `${Math.floor(ms / 60000)}m`;
}

// ─── MJPEG Video Player ─────────────────────────────────────────────────────

interface MjpegPlayerProps {
  cameraId: string;
  token:    string;
}

function MjpegPlayer({ cameraId, token }: MjpegPlayerProps) {
  const [phase, setPhase]     = useState<'loading'|'live'|'error'>('loading');
  const [imgKey, setImgKey]   = useState(0);
  const [fullscreen, setFs]   = useState(false);
  const prevCam               = useRef('');

  useEffect(() => {
    if (prevCam.current !== cameraId) {
      prevCam.current = cameraId;
      setPhase('loading');
      setImgKey(k => k + 1);
    }
  }, [cameraId]);

  // ESC — fullscreen yopish
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFs(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const src = `/api/v1/cameras/${encodeURIComponent(cameraId)}/stream?token=${encodeURIComponent(token)}`;

  const wrap: React.CSSProperties = fullscreen
    ? { position: 'fixed', inset: 0, zIndex: 9999, background: '#000',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }
    : { position: 'relative', width: '100%', aspectRatio: '16/9',
        background: '#000', borderRadius: 10, overflow: 'hidden' };

  return (
    <div style={wrap}>

      {/* ── Loading state ─────────────────────────── */}
      {phase === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          background: '#050c18', gap: 14,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            border: '3px solid #0f172a', borderTopColor: '#0ea5e9',
            animation: 'tv-spin .75s linear infinite',
          }}/>
          <span style={{ fontSize: 12, color: '#334155', fontFamily: 'monospace' }}>
            {cameraId} — ulanmoqda...
          </span>
        </div>
      )}

      {/* ── Error state ───────────────────────────── */}
      {phase === 'error' && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 4,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          background: '#050c18', gap: 14,
        }}>
          <AlertTriangle size={30} color="#1e293b" />
          <p style={{ fontSize: 12, color: '#334155', margin: 0 }}>Stream yuklanmadi</p>
          <button
            onClick={() => { setPhase('loading'); setImgKey(k => k + 1); }}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', background: '#0f172a',
              border: '1px solid #1e293b', borderRadius: 6,
              color: '#475569', cursor: 'pointer', fontSize: 12,
            }}
          >
            <RefreshCw size={12}/> Qayta urinish
          </button>
        </div>
      )}

      {/* ── MJPEG image ───────────────────────────── */}
      <img
        key={imgKey}
        src={src}
        alt="camera stream"
        style={{
          width: fullscreen ? 'auto' : '100%',
          height: fullscreen ? '100%' : '100%',
          objectFit: 'contain',
          display: phase === 'error' ? 'none' : 'block',
        }}
        onLoad={()  => setPhase('live')}
        onError={() => setPhase('error')}
      />

      {/* ── Scan-line aesthetic ───────────────────── */}
      {phase === 'live' && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 2,
          backgroundImage: 'repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.018) 2px,rgba(0,0,0,0.018) 4px)',
        }}/>
      )}

      {/* ── LIVE badge (top-left) ─────────────────── */}
      {phase === 'live' && (
        <div style={{
          position: 'absolute', top: 12, left: 12, zIndex: 5,
          display: 'flex', alignItems: 'center', gap: 5,
          background: 'rgba(0,0,0,.72)', backdropFilter: 'blur(6px)',
          border: '1px solid rgba(239,68,68,.35)',
          borderRadius: 5, padding: '3px 10px',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#ef4444', animation: 'tv-pulse 1.4s infinite',
          }}/>
          <span style={{
            fontFamily: 'monospace', fontSize: 10,
            fontWeight: 700, color: '#ef4444', letterSpacing: '.1em',
          }}>LIVE</span>
        </div>
      )}

      {/* ── Camera ID badge ───────────────────────── */}
      <div style={{
        position: 'absolute', top: 12,
        left: phase === 'live' ? 80 : 12,
        zIndex: 5,
        background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(6px)',
        border: '1px solid rgba(255,255,255,.07)',
        borderRadius: 5, padding: '3px 10px',
      }}>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: '#64748b' }}>
          {cameraId}
        </span>
      </div>

      {/* ── Fullscreen button ────────────────────── */}
      <button
        onClick={() => setFs(f => !f)}
        title={fullscreen ? 'Kichraytirish (ESC)' : 'Kattalashtirish'}
        style={{
          position: 'absolute', top: 12, right: 12, zIndex: 5,
          background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(6px)',
          border: '1px solid rgba(255,255,255,.07)',
          borderRadius: 5, padding: 7,
          cursor: 'pointer', color: '#475569', display: 'flex',
        }}
      >
        {fullscreen ? <ZoomOut size={13}/> : <ZoomIn size={13}/>}
      </button>

      {/* ── Fullscreen hint ───────────────────────── */}
      {fullscreen && (
        <div style={{
          position: 'absolute', bottom: 20, left: '50%',
          transform: 'translateX(-50%)', zIndex: 6,
          background: 'rgba(0,0,0,.8)', border: '1px solid #1e293b',
          borderRadius: 6, padding: '7px 18px',
          color: '#475569', fontSize: 11, fontFamily: 'monospace',
        }}>
          ESC yoki ✕ tugmasini bosib yoping
        </div>
      )}
    </div>
  );
}

// ─── Stats bar (pipeline ma'lumotlari) ─────────────────────────────────────

function StatsBar({ info }: { info: PipelineInfo | undefined }) {
  const s = info?.stats;
  if (!s) return null;

  return (
    <div style={{
      display: 'flex', borderTop: '1px solid #0a1628',
      background: '#050c18', flexShrink: 0,
    }}>
      {([
        { label: 'FPS',         val: s.fps.toFixed(1),  color: '#22c55e',  Icon: Activity },
        { label: 'Kadrlar',     val: s.frames,          color: '#38bdf8',  Icon: Eye      },
        { label: 'Detection',   val: s.detections,      color: '#a78bfa',  Icon: Tag      },
      ] as const).map(({ label, val, color, Icon }) => (
        <div key={label} style={{
          flex: 1, padding: '7px 14px',
          display: 'flex', alignItems: 'center', gap: 7,
          borderRight: '1px solid #0a1628',
        }}>
          <Icon size={11} color={color}/>
          <span style={{
            fontSize: 9, color: '#334155',
            textTransform: 'uppercase', letterSpacing: '.1em',
          }}>{label}</span>
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: '#64748b',
          }}>{val}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Camera selector tab ───────────────────────────────────────────────────

function CamTab({
  id, active, fps, onClick,
}: {
  id: string; active: boolean; fps: number; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 12px',
        background: active ? '#0ea5e9' : 'transparent',
        border: `1px solid ${active ? '#0ea5e9' : '#0f172a'}`,
        borderRadius: 6, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 7,
        transition: 'all .15s', flexShrink: 0,
      }}
    >
      {/* Green dot — aktiv pipeline */}
      <div style={{
        width: 6, height: 6, borderRadius: '50%',
        background: active ? '#fff' : '#22c55e',
        animation: 'tv-pulse 2s infinite',
      }}/>
      <span style={{
        fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
        color: active ? '#fff' : '#64748b', whiteSpace: 'nowrap',
      }}>{id}</span>
      {fps > 0 && (
        <span style={{
          fontSize: 10,
          color: active ? 'rgba(255,255,255,.6)' : '#1e293b',
        }}>{fps.toFixed(1)} fps</span>
      )}
    </button>
  );
}

// ─── Detection event row ───────────────────────────────────────────────────

function EventRow({ ev, fresh }: { ev: DetectionEvent; fresh: boolean }) {
  const identified = ev.identified;
  const accent     = identified ? '#22c55e' : '#f59e0b';
  const conf       = ev.confidence;
  const confColor  = conf >= .85 ? '#22c55e' : conf >= .65 ? '#f59e0b' : '#ef4444';

  return (
    <div style={{
      padding: '10px 16px',
      borderLeft: `2px solid ${fresh ? accent : 'transparent'}`,
      borderBottom: '1px solid #070d1a',
      background: fresh ? `rgba(${identified ? '34,197,94' : '245,158,11'},.04)` : 'transparent',
      transition: 'all .5s',
    }}>
      {/* Tag + confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: accent, flexShrink: 0,
        }}/>
        <span style={{
          fontFamily: 'monospace', fontSize: 13, fontWeight: 700,
          color: '#e2e8f0', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {identified ? ev.animal_tag_id : '— Tanilmadi'}
        </span>
        <span style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 700, color: confColor }}>
          {(conf * 100).toFixed(0)}%
        </span>
      </div>

      {/* Meta row */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, paddingLeft: 13,
      }}>
        <Scale size={9} color="#1e293b"/>
        <span style={{ fontSize: 10, color: '#334155' }}>
          {ev.estimated_weight_kg.toFixed(1)} kg
        </span>
        <span style={{
          fontSize: 9, padding: '1px 6px', borderRadius: 999,
          background: identified ? 'rgba(34,197,94,.1)' : 'rgba(245,158,11,.1)',
          color: identified ? '#22c55e' : '#f59e0b',
        }}>
          {identified ? 'Tanildi' : 'Tanilmadi'}
        </span>
        <span style={{ fontSize: 9, color: '#1e293b', marginLeft: 'auto' }}>
          {timeAgo(ev.timestamp)}
        </span>
      </div>
    </div>
  );
}

// ─── Right-side detection panel ────────────────────────────────────────────

function DetectionPanel({
  events, camId,
}: {
  events: DetectionEvent[];
  camId:  string | null;
}) {
  const list = camId ? events.filter(e => e.camera_id === camId) : events;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '11px 16px', borderBottom: '1px solid #0a1628',
        display: 'flex', alignItems: 'center', gap: 8,
        background: '#050c18', flexShrink: 0,
      }}>
        <Activity size={12} color="#38bdf8"/>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
          color: '#334155', textTransform: 'uppercase',
        }}>Detection Log</span>
        {list.length > 0 && (
          <span style={{
            marginLeft: 'auto', fontFamily: 'monospace',
            fontSize: 10, background: '#0a1628',
            color: '#38bdf8', padding: '1px 7px', borderRadius: 999,
          }}>{list.length}</span>
        )}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {list.length === 0 ? (
          <div style={{
            padding: '50px 20px', textAlign: 'center',
          }}>
            <Eye size={24} color="#0f172a" style={{ margin: '0 auto 10px', display: 'block' }}/>
            <p style={{ fontSize: 11, color: '#1e293b', margin: 0 }}>
              {camId ? 'Bu kamerada detection yo\'q' : 'Kamera tanlanmagan'}
            </p>
          </div>
        ) : (
          list.map((ev, i) => (
            <EventRow
              key={`${ev.timestamp}-${ev.camera_id}-${i}`}
              ev={ev}
              fresh={i === 0}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────

export default function LiveFeedPage() {
  const token = localStorage.getItem('tv_access_token') ?? '';

  // WebSocket
  const { status: wsStatus, liveDetections } = useWebSocketContext();

  // Detection history (max 60)
  const [events, setEvents]           = useState<DetectionEvent[]>([]);
  const lastEventKey                  = useRef('');

  // Kamera tanlash
  const [selectedCam, setSelectedCam] = useState<string | null>(null);

  // Pipeline data (5s interval)
  const { data: plData, refetch } = useQuery({
    queryKey:        ['pipeline', 'all-status'],
    queryFn:         () => apiFetch<AllPipelinesStatus>('/api/v1/pipeline/status'),
    refetchInterval: 5_000,
  });

  const running = plData?.running_cameras ?? [];

  // Auto-select birinchi kamera
  useEffect(() => {
    if (!selectedCam && running.length > 0)
      setSelectedCam(running[0]);
    if (selectedCam && running.length > 0 && !running.includes(selectedCam))
      setSelectedCam(running[0]);
    if (running.length === 0)
      setSelectedCam(null);
  }, [running, selectedCam]);

  // WS detection → events
  useEffect(() => {
    if (!liveDetections.length) return;
    const raw = liveDetections[0] as any;
    if (!raw) return;

    // Dublikat oldini olish
    const key = `${raw.timestamp}-${raw.camera_id}`;
    if (key === lastEventKey.current) return;
    lastEventKey.current = key;

    const ev: DetectionEvent = {
      camera_id:           raw.camera_id           ?? '',
      animal_id:           raw.animal_id            ?? null,
      animal_tag_id:       raw.animal_tag_id        ?? 'UNKNOWN',
      confidence:          raw.confidence_score     ?? raw.confidence ?? 0,
      estimated_weight_kg: raw.estimated_weight_kg  ?? 0,
      identified:          raw.identified           ?? (raw.animal_id !== null),
      timestamp:           raw.timestamp,
    };

    setEvents(prev => [ev, ...prev].slice(0, 60));
  }, [liveDetections]);

  // WS indikator
  const wsOk    = wsStatus === WsStatus.CONNECTED;
  const wsColor = wsOk ? '#22c55e' :
                  wsStatus === WsStatus.RECONNECTING ? '#f59e0b' : '#475569';

  const noPipeline = running.length === 0;

  return (
    <div style={{
      height: '100vh', overflow: 'hidden',
      background: '#050c18',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Inter', system-ui, sans-serif",
    }}>
      {/* ── Global CSS ───────────────────────────────────────────── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
        @keyframes tv-spin  { to { transform: rotate(360deg); } }
        @keyframes tv-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: #050c18; }
        ::-webkit-scrollbar-thumb { background: #0f172a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #1e293b; }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────── */}
      <header style={{
        padding: '9px 20px',
        borderBottom: '1px solid #0a1628',
        display: 'flex', alignItems: 'center', gap: 14,
        background: '#050c18', flexShrink: 0,
        minHeight: 48,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <Camera size={15} color="#0ea5e9"/>
          <span style={{
            fontFamily: 'monospace', fontSize: 11,
            fontWeight: 700, color: '#475569', letterSpacing: '.12em',
          }}>
            LIVE MONITOR
          </span>
        </div>

        {/* Camera tabs */}
        <div style={{
          flex: 1, display: 'flex', gap: 6, overflowX: 'auto',
          scrollbarWidth: 'none',
        }}>
          {running.map(id => (
            <CamTab
              key={id}
              id={id}
              active={selectedCam === id}
              fps={plData?.pipelines?.[id]?.stats?.fps ?? 0}
              onClick={() => setSelectedCam(id)}
            />
          ))}
          {noPipeline && (
            <span style={{
              fontSize: 11, color: '#1e293b',
              alignSelf: 'center', fontStyle: 'italic',
            }}>
              Aktiv pipeline yo'q — Cameras da pipeline ishga tushiring
            </span>
          )}
        </div>

        {/* WS indicator + refresh */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {wsOk
              ? <Wifi size={12} color={wsColor}/>
              : <WifiOff size={12} color={wsColor}/>
            }
            <span style={{ fontSize: 10, color: wsColor, fontFamily: 'monospace' }}>
              {wsStatus === WsStatus.CONNECTED    ? 'WS OK' :
               wsStatus === WsStatus.RECONNECTING ? 'RECONNECT' : 'OFFLINE'}
            </span>
          </div>
          <button
            onClick={() => refetch()}
            title="Yangilash"
            style={{
              background: 'transparent',
              border: '1px solid #0f172a',
              borderRadius: 4, padding: '4px 7px',
              cursor: 'pointer', color: '#1e293b', display: 'flex',
              transition: 'border-color .15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#1e293b')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = '#0f172a')}
          >
            <RefreshCw size={11}/>
          </button>
        </div>
      </header>

      {/* ── No pipeline banner ──────────────────────────────────── */}
      {noPipeline && (
        <div style={{
          margin: '20px 20px 0',
          padding: '12px 18px',
          background: 'rgba(239,68,68,.06)',
          border: '1px solid rgba(239,68,68,.18)',
          borderRadius: 8,
          display: 'flex', alignItems: 'center', gap: 11,
          flexShrink: 0,
        }}>
          <AlertTriangle size={14} color="#f87171"/>
          <p style={{ fontSize: 12, color: '#f87171', margin: 0 }}>
            Kamera pipeline ishlamayapti. Cameras sahifasidan kamera qo'shib pipeline ni ishga tushiring.
          </p>
        </div>
      )}

      {/* ── Body ───────────────────────────────────────────────── */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '1fr 270px',
        overflow: 'hidden',
        gap: 0,
      }}>

        {/* ── Left: video + stats ──────────────────────────────── */}
        <div style={{
          display: 'flex', flexDirection: 'column',
          borderRight: '1px solid #0a1628',
          overflow: 'hidden',
        }}>
          {selectedCam ? (
            <>
              {/* Video */}
              <div style={{
                flex: 1, padding: 16,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                overflow: 'hidden',
              }}>
                <div style={{ width: '100%' }}>
                  <MjpegPlayer cameraId={selectedCam} token={token}/>
                </div>
              </div>
              {/* Stats */}
              <StatsBar info={plData?.pipelines?.[selectedCam]}/>
            </>
          ) : (
            /* Empty state */
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 16,
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: '50%',
                background: '#0a1628',
                border: '1px solid #0f172a',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Camera size={28} color="#1e293b"/>
              </div>
              <p style={{ fontSize: 13, color: '#1e293b', margin: 0, textAlign: 'center' }}>
                {noPipeline
                  ? 'Pipeline ishga tushirilmagan'
                  : 'Yuqoridan kamera tanlang'}
              </p>
              {!noPipeline && running.length > 0 && (
                <button
                  onClick={() => setSelectedCam(running[0])}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 7,
                    padding: '8px 16px',
                    background: '#0ea5e9',
                    border: 'none', borderRadius: 7,
                    color: '#fff', fontSize: 12, fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <Play size={12}/> Birinchi kamerani ochish
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Right: detection panel ───────────────────────────── */}
        <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <DetectionPanel events={events} camId={selectedCam}/>
        </div>
      </div>
    </div>
  );
}