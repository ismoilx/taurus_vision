/**
 * SensorPage — IoT Sensor Monitoring (Sprint 17-18)
 *
 * Ferma bo'yicha IoT sensor qurilmalarini real-time monitoring qilish.
 *
 * TAB 1 — Umumiy:    KPI kartalar, ferma statistikasi, bugungi anomaliyalar
 * TAB 2 — Qurilmalar: Aktiv qurilmalar ro'yxati, online/offline holati
 * TAB 3 — Anomaliyalar: Bugungi barcha anormal o'lchovlar
 *
 * ENDPOINTLAR:
 *   GET /api/v1/sensors/stats      → KPI, umumiy statistika
 *   GET /api/v1/sensors/devices    → Aktiv qurilmalar ro'yxati
 *   GET /api/v1/sensors/anomalies  → Bugungi anomaliyalar
 *
 * YANGILANISH:
 *   30 soniyada bir avtomatik refetch (React Query)
 *
 * NORMAL DIAPZONLAR (qoramol):
 *   Harorat:      38.0 – 39.5 °C (warning: 37.5–40.0, critical: <36 / >41.5)
 *   Yurak urishi: 40 – 80 bpm    (warning: 30–100,    critical: <20 / >120)
 *   Faollik:      0.2 – 0.8      (0.0=tinch, 1.0=juda faol)
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Thermometer, Heart, Activity, Wifi, WifiOff,
  AlertTriangle, CheckCircle, RefreshCw, Cpu,
  Zap, Radio, BarChart3, Clock, TrendingUp,
  TrendingDown, Minus, Server, Search,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { format } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES — Backend API javoblariga to'liq mos
// =============================================================================

interface SensorStats {
  total_devices:        number;
  active_devices_today: number;
  total_readings_today: number;
  animals_with_sensors: number;
  anomalies_today:      number;
  recent_anomalies:     AnomalyItem[];
}

interface AnomalyItem {
  animal_id:   number;
  device_id:   string;
  issues:      string[];
  recorded_at: string;
}

interface DeviceItem {
  device_id:     string;
  device_type:   'collar' | 'scale' | 'environment' | 'camera' | string;
  animal_id:     number | null;
  reading_count: number;
  last_seen:     string;
}

interface DevicesResponse {
  total:   number;
  devices: DeviceItem[];
}

interface AnomaliesResponse {
  total:      number;
  anomalies:  AnomalyItem[];
}

// =============================================================================
// CONSTANTS
// =============================================================================

/** Normal qiymatlar — sensor kartalarida rang berish uchun */
const NORMAL_RANGES = {
  temperature: { min: 38.0, max: 39.5, warnMin: 37.5, warnMax: 40.0 },
  heart_rate:  { min: 40,   max: 80,   warnMin: 30,   warnMax: 100  },
  activity:    { min: 0.2,  max: 0.8 },
} as const;

const DEVICE_TYPE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  collar:      { label: 'Yoqa',        color: '#8B5CF6', bg: '#EDE9FE' },
  scale:       { label: 'Tarozu',      color: '#0EA5E9', bg: '#E0F2FE' },
  environment: { label: 'Muhit',       color: '#10B981', bg: '#D1FAE5' },
  camera:      { label: 'Kamera',      color: '#F59E0B', bg: '#FEF3C7' },
};

const REFETCH_INTERVAL_MS = 30_000;

// =============================================================================
// HELPERS
// =============================================================================

function timeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const s    = Math.floor(diff / 1000);
  const m    = Math.floor(s / 60);
  const h    = Math.floor(m / 60);
  if (s  < 60)  return `${s}s oldin`;
  if (m  < 60)  return `${m}d oldin`;
  if (h  < 24)  return `${h}s oldin`;
  return `${Math.floor(h / 24)} kun oldin`;
}

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function isOnline(lastSeen: string, thresholdMins = 30): boolean {
  return (Date.now() - new Date(lastSeen).getTime()) < thresholdMins * 60_000;
}

function tempStatus(t: number): 'normal' | 'warning' | 'critical' {
  const r = NORMAL_RANGES.temperature;
  if (t < 36.0 || t > 41.5) return 'critical';
  if (t < r.warnMin || t > r.warnMax) return 'warning';
  return 'normal';
}

function hrStatus(hr: number): 'normal' | 'warning' | 'critical' {
  const r = NORMAL_RANGES.heart_rate;
  if (hr < 20 || hr > 120) return 'critical';
  if (hr < r.warnMin || hr > r.warnMax) return 'warning';
  return 'normal';
}

const STATUS_COLORS = {
  normal:   { text: '#10B981', bg: '#ECFDF5', border: '#A7F3D0' },
  warning:  { text: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  critical: { text: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
} as const;

// =============================================================================
// KPI CARD
// =============================================================================

function KPICard({
  icon, label, value, sub, color = '#1E3EB4', loading,
}: {
  icon:    React.ReactNode;
  label:   string;
  value:   number | string;
  sub?:    string;
  color?:  string;
  loading: boolean;
}) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      padding: '16px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: 14,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 12,
        background: `${color}14`,
        display: 'grid', placeItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{ color }}>{icon}</span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 11, fontWeight: 500,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          fontFamily: "'Outfit', sans-serif",
          marginBottom: 2,
        }}>
          {label}
        </div>

        {loading ? (
          <div style={{
            width: 48, height: 22, borderRadius: 6,
            background: 'var(--border)',
            animation: 'tv-pulse 1.5s ease-in-out infinite',
          }} />
        ) : (
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 24, fontWeight: 700,
            color: 'var(--text-primary)',
            lineHeight: 1,
          }}>
            {value}
          </div>
        )}

        {sub && !loading && (
          <div style={{
            fontSize: 10, color: 'var(--text-muted)',
            marginTop: 3,
            fontFamily: "'Outfit', sans-serif",
          }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// DEVICE ROW
// =============================================================================

function DeviceRow({ device }: { device: DeviceItem }) {
  const online  = isOnline(device.last_seen);
  const typeInfo = DEVICE_TYPE_LABELS[device.device_type] ?? {
    label: device.device_type, color: '#6B7280', bg: '#F3F4F6',
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      {/* Online dot */}
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: online ? '#10B981' : '#D1D5DB',
        flexShrink: 0,
        boxShadow: online ? '0 0 0 3px #D1FAE5' : 'none',
      }} />

      {/* Device ID + type badge */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 13, fontWeight: 600,
            color: 'var(--text-primary)',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {device.device_id}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 600,
            padding: '2px 8px', borderRadius: 20,
            background: typeInfo.bg, color: typeInfo.color,
            fontFamily: "'Outfit', sans-serif",
          }}>
            {typeInfo.label}
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
          {device.animal_id
            ? `Jonivor #${device.animal_id} · `
            : 'Bog\'liq emas · '
          }
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
          }}>
            {device.reading_count}
          </span>
          {' '}o'lchov
        </div>
      </div>

      {/* Last seen */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          justifyContent: 'flex-end',
          color: online ? '#10B981' : '#9CA3AF',
        }}>
          {online ? <Wifi size={12} /> : <WifiOff size={12} />}
          <span style={{ fontSize: 11, fontWeight: 600 }}>
            {online ? 'Online' : 'Offline'}
          </span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
          {timeAgo(device.last_seen)}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// ANOMALY ROW
// =============================================================================

function AnomalyRow({ item }: { item: AnomalyItem }) {
  // Severityni issues asosida aniqlash
  const hasCritical = item.issues.some(
    i => i.toLowerCase().includes('kritik')
  );
  const col = hasCritical ? STATUS_COLORS.critical : STATUS_COLORS.warning;

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '12px 14px',
      borderRadius: 10,
      background: col.bg,
      border: `1px solid ${col.border}`,
      marginBottom: 8,
    }}>
      <AlertTriangle
        size={15}
        color={col.text}
        style={{ flexShrink: 0, marginTop: 1 }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 12, fontWeight: 700,
            color: col.text,
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {item.device_id}
          </span>
          {item.animal_id && (
            <span style={{
              fontSize: 11, color: col.text, opacity: 0.8,
            }}>
              Jonivor #{item.animal_id}
            </span>
          )}
          <span style={{
            marginLeft: 'auto',
            fontSize: 10, color: col.text, opacity: 0.7,
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {formatTime(item.recorded_at)}
          </span>
        </div>
        <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {item.issues.map((issue, i) => (
            <div key={i} style={{
              fontSize: 11, color: col.text,
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              <span style={{
                width: 4, height: 4, borderRadius: '50%',
                background: col.text,
                flexShrink: 0,
                display: 'inline-block',
              }} />
              {issue}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// TAB COMPONENT
// =============================================================================

function Tab({
  label, active, onClick, badge,
}: {
  label:   string;
  active:  boolean;
  onClick: () => void;
  badge?:  number;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '8px 16px',
        borderTop: 'none',
        borderRight: 'none',
        borderLeft: 'none',
        borderBottom: `2px solid ${active ? '#1E3EB4' : 'transparent'}`,
        background: 'transparent',
        cursor: 'pointer',
        fontFamily: "'Outfit', sans-serif",
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        color: active ? '#1E3EB4' : 'var(--text-muted)',
        transition: 'all .15s',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <span style={{
          fontSize: 10, fontWeight: 700,
          padding: '1px 6px', borderRadius: 20,
          background: badge > 0 ? '#FEF3C7' : '#F3F4F6',
          color: badge > 0 ? '#D97706' : '#9CA3AF',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {badge}
        </span>
      )}
    </button>
  );
}

// =============================================================================
// EMPTY STATE
// =============================================================================

function EmptyState({ icon, title, desc }: {
  icon:  React.ReactNode;
  title: string;
  desc:  string;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center',
      padding: '60px 24px',
      textAlign: 'center',
      color: 'var(--text-muted)',
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 16,
        background: 'var(--border)',
        display: 'grid', placeItems: 'center',
        marginBottom: 16,
        opacity: 0.6,
      }}>
        {icon}
      </div>
      <div style={{
        fontSize: 14, fontWeight: 600,
        color: 'var(--text-secondary)',
        marginBottom: 6,
      }}>
        {title}
      </div>
      <div style={{ fontSize: 12, maxWidth: 300 }}>
        {desc}
      </div>
    </div>
  );
}

// =============================================================================
// SKELETON LOADER
// =============================================================================

function SkeletonRow() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--border)' }} />
      <div style={{ flex: 1 }}>
        <div style={{
          width: '40%', height: 14, borderRadius: 4,
          background: 'var(--border)',
          marginBottom: 6,
          animation: 'tv-pulse 1.5s ease-in-out infinite',
        }} />
        <div style={{
          width: '60%', height: 11, borderRadius: 4,
          background: 'var(--border)',
          animation: 'tv-pulse 1.5s ease-in-out infinite',
          animationDelay: '0.15s',
        }} />
      </div>
      <div style={{
        width: 56, height: 28, borderRadius: 6,
        background: 'var(--border)',
        animation: 'tv-pulse 1.5s ease-in-out infinite',
      }} />
    </div>
  );
}

// =============================================================================
// OVERVIEW TAB
// =============================================================================

function OverviewTab({
  stats,
  statsLoading,
}: {
  stats:        SensorStats | undefined;
  statsLoading: boolean;
}) {
  const noAnomalies = !statsLoading && (stats?.anomalies_today ?? 0) === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Normal ranges reference */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '16px 20px',
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700,
          color: 'var(--text-muted)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: 14,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          Normal Diapzonlar
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 12,
        }}>
          {[
            {
              icon: <Thermometer size={14} />,
              label: 'Harorat',
              normal: '38.0 – 39.5°C',
              warn: '37.5 – 40.0°C',
              color: '#EF4444',
            },
            {
              icon: <Heart size={14} />,
              label: 'Yurak urishi',
              normal: '40 – 80 bpm',
              warn: '30 – 100 bpm',
              color: '#EC4899',
            },
            {
              icon: <Activity size={14} />,
              label: 'Faollik darajasi',
              normal: '0.2 – 0.8',
              warn: '0.0 – 1.0',
              color: '#10B981',
            },
          ].map(item => (
            <div key={item.label} style={{
              padding: '10px 12px',
              borderRadius: 10,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                marginBottom: 8,
                color: item.color,
              }}>
                {item.icon}
                <span style={{
                  fontSize: 12, fontWeight: 600,
                  color: 'var(--text-secondary)',
                  fontFamily: "'Outfit', sans-serif",
                }}>
                  {item.label}
                </span>
              </div>
              <div style={{ fontSize: 11, marginBottom: 2 }}>
                <span style={{ color: '#10B981', fontWeight: 600 }}>✓ </span>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  color: 'var(--text-primary)',
                }}>
                  {item.normal}
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                <span style={{ color: '#D97706', fontWeight: 600 }}>⚠ </span>
                Ogohlantirish: <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{item.warn}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bugungi anomaliyalar */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '16px 20px',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 14,
        }}>
          <div style={{
            fontSize: 11, fontWeight: 700,
            color: 'var(--text-muted)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            Bugungi Anomaliyalar
          </div>
          {!statsLoading && (
            <span style={{
              fontSize: 11, fontWeight: 600,
              padding: '2px 10px', borderRadius: 20,
              background: noAnomalies ? '#ECFDF5' : '#FEF3C7',
              color: noAnomalies ? '#10B981' : '#D97706',
              border: `1px solid ${noAnomalies ? '#A7F3D0' : '#FDE68A'}`,
            }}>
              {stats?.anomalies_today ?? 0} ta
            </span>
          )}
        </div>

        {statsLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                height: 64, borderRadius: 10,
                background: 'var(--border)',
                animation: 'tv-pulse 1.5s ease-in-out infinite',
                animationDelay: `${i * 0.1}s`,
              }} />
            ))}
          </div>
        ) : noAnomalies ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '20px',
            background: '#ECFDF5',
            border: '1px solid #A7F3D0',
            borderRadius: 10,
          }}>
            <CheckCircle size={20} color="#10B981" />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#065F46' }}>
                Barcha ko'rsatkichlar normal
              </div>
              <div style={{ fontSize: 11, color: '#059669', marginTop: 2 }}>
                Bugun hali anomaliya qayd etilmagan
              </div>
            </div>
          </div>
        ) : (
          <div>
            {(stats?.recent_anomalies ?? []).map((item, i) => (
              <AnomalyRow key={i} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// DEVICES TAB
// =============================================================================

function DevicesTab({
  data,
  isLoading,
}: {
  data:      DevicesResponse | undefined;
  isLoading: boolean;
}) {
  const devices   = data?.devices ?? [];
  const onlineCount  = devices.filter(d => isOnline(d.last_seen)).length;
  const offlineCount = devices.length - onlineCount;

  const byType = devices.reduce<Record<string, number>>((acc, d) => {
    acc[d.device_type] = (acc[d.device_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Device type summary */}
      {!isLoading && devices.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 10,
        }}>
          {[
            { key: 'online',  label: 'Online',   count: onlineCount,  color: '#10B981', bg: '#ECFDF5' },
            { key: 'offline', label: 'Offline',  count: offlineCount, color: '#9CA3AF', bg: '#F9FAFB' },
            ...Object.entries(byType).map(([type, count]) => ({
              key: type,
              label: DEVICE_TYPE_LABELS[type]?.label ?? type,
              count,
              color: DEVICE_TYPE_LABELS[type]?.color ?? '#6B7280',
              bg:    DEVICE_TYPE_LABELS[type]?.bg    ?? '#F3F4F6',
            })),
          ].map(item => (
            <div key={item.key} style={{
              padding: '10px 14px',
              borderRadius: 10,
              background: item.bg,
              border: `1px solid ${item.color}30`,
              textAlign: 'center',
            }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 20, fontWeight: 700,
                color: item.color,
              }}>
                {item.count}
              </div>
              <div style={{ fontSize: 10, color: item.color, marginTop: 2, fontWeight: 600 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Devices list */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '16px 20px',
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700,
          color: 'var(--text-muted)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: 4,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          Barcha Qurilmalar
        </div>

        {isLoading ? (
          <>
            {[1, 2, 3, 4, 5].map(i => <SkeletonRow key={i} />)}
          </>
        ) : devices.length === 0 ? (
          <EmptyState
            icon={<Wifi size={22} />}
            title="Hali sensor ulanmagan"
            desc="POST /api/v1/sensors/reading orqali birinchi o'lchovni yuborish bilan qurilmalar bu yerda ko'rinadi."
          />
        ) : (
          devices.map((device, i) => (
            <DeviceRow key={`${device.device_id}-${i}`} device={device} />
          ))
        )}
      </div>
    </div>
  );
}

// =============================================================================
// ANOMALIES TAB
// =============================================================================

function AnomaliesTab({
  data,
  isLoading,
}: {
  data:      AnomaliesResponse | undefined;
  isLoading: boolean;
}) {
  const anomalies  = data?.anomalies ?? [];
  const critCount  = anomalies.filter(a =>
    a.issues.some(i => i.toLowerCase().includes('kritik'))
  ).length;
  const warnCount  = anomalies.length - critCount;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {!isLoading && anomalies.length > 0 && (
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{
            flex: 1, padding: '12px 16px',
            borderRadius: 12,
            background: '#FEF2F2',
            border: '1px solid #FECACA',
            textAlign: 'center',
          }}>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 22, fontWeight: 700, color: '#DC2626',
            }}>
              {critCount}
            </div>
            <div style={{ fontSize: 11, color: '#DC2626', fontWeight: 600 }}>
              Kritik
            </div>
          </div>
          <div style={{
            flex: 1, padding: '12px 16px',
            borderRadius: 12,
            background: '#FFFBEB',
            border: '1px solid #FDE68A',
            textAlign: 'center',
          }}>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 22, fontWeight: 700, color: '#D97706',
            }}>
              {warnCount}
            </div>
            <div style={{ fontSize: 11, color: '#D97706', fontWeight: 600 }}>
              Ogohlantirish
            </div>
          </div>
          <div style={{
            flex: 1, padding: '12px 16px',
            borderRadius: 12,
            background: '#F9FAFB',
            border: '1px solid var(--border)',
            textAlign: 'center',
          }}>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            }}>
              {anomalies.length}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
              Jami
            </div>
          </div>
        </div>
      )}

      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '16px 20px',
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700,
          color: 'var(--text-muted)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: 14,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          Bugungi Barcha Anomaliyalar
        </div>

        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[1, 2, 3, 4].map(i => (
              <div key={i} style={{
                height: 72, borderRadius: 10,
                background: 'var(--border)',
                animation: 'tv-pulse 1.5s ease-in-out infinite',
                animationDelay: `${i * 0.1}s`,
              }} />
            ))}
          </div>
        ) : anomalies.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '20px',
            background: '#ECFDF5',
            border: '1px solid #A7F3D0',
            borderRadius: 10,
          }}>
            <CheckCircle size={20} color="#10B981" />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#065F46' }}>
                Bugun anomaliya qayd etilmagan
              </div>
              <div style={{ fontSize: 11, color: '#059669', marginTop: 2 }}>
                Barcha sensor ko'rsatkichlari normal diapzonda
              </div>
            </div>
          </div>
        ) : (
          <div>
            {anomalies.map((item, i) => (
              <AnomalyRow key={i} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

type ActiveTab = 'overview' | 'devices' | 'anomalies' | 'history';

// =============================================================================
// HISTORY TAB — Sensor tarix grafiği
// =============================================================================

interface HistoryPoint {
  hour:           string | null;
  temperature:    number | null;
  heart_rate:     number | null;
  activity_level: number | null;
  weight_kg:      number | null;
  count:          number;
}

interface AnimalHistoryResponse {
  animal_id:    number;
  days:         number;
  total_points: number;
  points:       HistoryPoint[];
}

interface FarmHistoryPoint {
  date:            string | null;
  avg_temperature: number | null;
  avg_heart_rate:  number | null;
  avg_activity:    number | null;
  animal_count:    number;
  reading_count:   number;
}

interface FarmHistoryResponse {
  days:         number;
  total_points: number;
  points:       FarmHistoryPoint[];
}

// Normal diapzonlar (qoramol)
const NORMAL = {
  temperature: { min: 38.0, max: 39.5, warn_min: 37.5, warn_max: 40.0 },
  heart_rate:  { min: 40,   max: 80,   warn_min: 30,   warn_max: 100  },
};

function HistoryTab() {
  const [mode, setMode]           = useState<'farm' | 'animal'>('farm');
  const [days, setDays]           = useState(7);
  const [animalId, setAnimalId]   = useState('');
  const [inputId, setInputId]     = useState('');
  const [metric, setMetric]       = useState<'temperature' | 'heart_rate' | 'activity_level'>('temperature');

  const farmQ = useQuery<FarmHistoryResponse>({
    queryKey: ['sensor-farm-history', days],
    queryFn:  () => apiFetch(`/api/v1/sensors/farm-history?days=${days}`),
    enabled:  mode === 'farm',
    staleTime: 60_000,
    retry:    false,
  });

  const animalQ = useQuery<AnimalHistoryResponse>({
    queryKey: ['sensor-animal-history', animalId, days],
    queryFn:  () => apiFetch(`/api/v1/sensors/history/${animalId}?days=${days}`),
    enabled:  mode === 'animal' && !!animalId,
    staleTime: 60_000,
    retry:    false,
  });

  const isLoading = mode === 'farm' ? farmQ.isLoading : animalQ.isLoading;
  const isError   = mode === 'farm' ? farmQ.isError   : animalQ.isError;

  // Chart data
  const farmData = (farmQ.data?.points ?? []).map(p => ({
    label:       p.date ? format(new Date(p.date), 'dd.MM') : '',
    temperature: p.avg_temperature,
    heart_rate:  p.avg_heart_rate,
    activity:    p.avg_activity != null ? +(p.avg_activity * 100).toFixed(1) : null,
    animals:     p.animal_count,
  }));

  const animalData = (animalQ.data?.points ?? []).map(p => ({
    label:       p.hour ? format(new Date(p.hour), 'dd.MM HH:mm') : '',
    temperature: p.temperature,
    heart_rate:  p.heart_rate,
    activity:    p.activity_level != null ? +(p.activity_level * 100).toFixed(1) : null,
    weight:      p.weight_kg,
  }));

  const chartData = mode === 'farm' ? farmData : animalData;

  const METRIC_CFG = {
    temperature:    { label: 'Harorat (°C)',      color: '#EF4444', unit: '°C' },
    heart_rate:     { label: 'Yurak urishi (bpm)', color: '#3B82F6', unit: ' bpm' },
    activity_level: { label: 'Faollik (%)',        color: '#10B981', unit: '%' },
  };
  const cfg = METRIC_CFG[metric];

  const inp: React.CSSProperties = {
    padding: '7px 12px', border: '1px solid #E4E7ED',
    borderRadius: 8, fontSize: 13, color: '#374151',
    outline: 'none', fontFamily: 'Outfit, sans-serif',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Controls */}
      <div style={{
        background: '#F8FAFC', border: '1px solid #E4E7ED',
        borderRadius: 12, padding: '14px 16px',
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
      }}>
        {/* Mode toggle */}
        <div style={{ display: 'flex', background: '#fff', border: '1px solid #E4E7ED', borderRadius: 8, overflow: 'hidden' }}>
          {(['farm', 'animal'] as const).map(m => (
            <button key={m} onClick={() => setMode(m)} style={{
              padding: '7px 14px', border: 'none',
              background: mode === m ? '#1E3EB4' : 'transparent',
              color: mode === m ? '#fff' : '#6B7280',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
            }}>
              {m === 'farm' ? '🌾 Ferma' : '🐄 Jonivor'}
            </button>
          ))}
        </div>

        {/* Animal search (only for animal mode) */}
        {mode === 'animal' && (
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              value={inputId}
              onChange={e => setInputId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && setAnimalId(inputId)}
              placeholder="Jonivor ID (raqam)..."
              style={{ ...inp, width: 160 }}
              type="number"
            />
            <button onClick={() => setAnimalId(inputId)} style={{
              padding: '7px 12px', border: 'none',
              background: '#1E3EB4', borderRadius: 8,
              color: '#fff', cursor: 'pointer',
            }}>
              <Search size={14} />
            </button>
          </div>
        )}

        {/* Metric */}
        <select value={metric} onChange={e => setMetric(e.target.value as typeof metric)} style={inp}>
          <option value="temperature">🌡 Harorat</option>
          <option value="heart_rate">❤️ Yurak urishi</option>
          <option value="activity_level">⚡ Faollik</option>
        </select>

        {/* Days */}
        <select value={days} onChange={e => setDays(Number(e.target.value))} style={inp}>
          <option value={1}>1 kun</option>
          <option value={3}>3 kun</option>
          <option value={7}>7 kun</option>
          <option value={14}>14 kun</option>
          <option value={30}>30 kun</option>
        </select>
      </div>

      {/* Chart */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 12, padding: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            {cfg.label} — So'nggi {days} kun
          </h3>
          {mode === 'animal' && animalId && (
            <span style={{
              padding: '4px 10px', background: '#EEF2FF',
              borderRadius: 6, fontSize: 12, fontWeight: 600, color: '#1E3EB4',
            }}>
              Jonivor #{animalId}
            </span>
          )}
        </div>

        {isLoading ? (
          <div style={{ height: 300, display: 'grid', placeItems: 'center', color: '#6B7280' }}>
            <RefreshCw size={24} style={{ animation: 'tv-pulse 1s linear infinite' }} />
          </div>
        ) : isError ? (
          <div style={{ height: 300, display: 'grid', placeItems: 'center' }}>
            <div style={{ textAlign: 'center', color: '#DC2626' }}>
              <AlertTriangle size={28} style={{ margin: '0 auto 8px', display: 'block' }} />
              <p style={{ fontSize: 13 }}>
                {mode === 'animal' && !animalId
                  ? 'Jonivor ID kiriting'
                  : "Ma'lumot topilmadi"}
              </p>
            </div>
          </div>
        ) : chartData.length === 0 ? (
          <div style={{ height: 300, display: 'grid', placeItems: 'center', color: '#9CA3AF' }}>
            <div style={{ textAlign: 'center' }}>
              <BarChart3 size={32} style={{ margin: '0 auto 8px', display: 'block', opacity: .3 }} />
              <p style={{ fontSize: 13 }}>
                {mode === 'animal' && !animalId
                  ? '⬆️ Jonivor ID kiriting'
                  : "Bu davr uchun sensor ma'lumoti yo'q"}
              </p>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                stroke="#E2E8F0"
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 11 }} stroke="#E2E8F0" />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: '1px solid #E4E7ED', fontSize: 12 }}
                formatter={(v: number) => [`${v}${cfg.unit}`, cfg.label]}
              />
              {/* Normal range reference lines */}
              {metric === 'temperature' && (
                <>
                  <ReferenceLine y={NORMAL.temperature.min} stroke="#10B981" strokeDasharray="4 4" label={{ value: 'Min norm', position: 'right', fontSize: 10, fill: '#10B981' }} />
                  <ReferenceLine y={NORMAL.temperature.max} stroke="#10B981" strokeDasharray="4 4" label={{ value: 'Max norm', position: 'right', fontSize: 10, fill: '#10B981' }} />
                  <ReferenceLine y={NORMAL.temperature.warn_max} stroke="#F59E0B" strokeDasharray="3 3" label={{ value: 'Ogohlantirish', position: 'right', fontSize: 10, fill: '#F59E0B' }} />
                </>
              )}
              {metric === 'heart_rate' && (
                <>
                  <ReferenceLine y={NORMAL.heart_rate.min} stroke="#10B981" strokeDasharray="4 4" label={{ value: 'Min norm', position: 'right', fontSize: 10, fill: '#10B981' }} />
                  <ReferenceLine y={NORMAL.heart_rate.max} stroke="#10B981" strokeDasharray="4 4" label={{ value: 'Max norm', position: 'right', fontSize: 10, fill: '#10B981' }} />
                </>
              )}
              <Line
                type="monotone"
                dataKey={metric === 'activity_level' ? 'activity' : metric}
                stroke={cfg.color}
                strokeWidth={2}
                dot={chartData.length < 50 ? { r: 3, fill: cfg.color, strokeWidth: 0 } : false}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}

        {/* Stats summary */}
        {chartData.length > 0 && (
          <div style={{
            display: 'flex', gap: 16, marginTop: 16, flexWrap: 'wrap',
            borderTop: '1px solid #F3F4F6', paddingTop: 14,
          }}>
            {(() => {
              const key = metric === 'activity_level' ? 'activity' : metric;
              const vals = chartData.map((d: any) => d[key]).filter((v: any) => v != null) as number[];
              if (vals.length === 0) return null;
              const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
              const min = Math.min(...vals);
              const max = Math.max(...vals);
              return [
                { label: "O'rtacha", value: avg.toFixed(1) + cfg.unit, color: cfg.color },
                { label: 'Minimum', value: min.toFixed(1) + cfg.unit, color: '#6B7280' },
                { label: 'Maksimum', value: max.toFixed(1) + cfg.unit, color: '#6B7280' },
                { label: 'Nuqtalar', value: String(vals.length), color: '#6B7280' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 500 }}>{label}</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color }}>{value}</div>
                </div>
              ));
            })()}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
export default function SensorPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');

  // ── Queries ────────────────────────────────────────────────────────────────

  const {
    data: stats,
    isLoading: statsLoading,
    isError: statsError,
    refetch: refetchStats,
    dataUpdatedAt,
  } = useQuery<SensorStats>({
    queryKey:        ['sensor-stats'],
    queryFn:         () => apiFetch('/api/v1/sensors/stats'),
    refetchInterval: REFETCH_INTERVAL_MS,
    staleTime:       20_000,
  });

  const {
    data:      devicesData,
    isLoading: devicesLoading,
    refetch:   refetchDevices,
  } = useQuery<DevicesResponse>({
    queryKey:        ['sensor-devices'],
    queryFn:         () => apiFetch('/api/v1/sensors/devices'),
    refetchInterval: REFETCH_INTERVAL_MS,
    staleTime:       20_000,
  });

  const {
    data:      anomaliesData,
    isLoading: anomaliesLoading,
    refetch:   refetchAnomalies,
  } = useQuery<AnomaliesResponse>({
    queryKey:        ['sensor-anomalies'],
    queryFn:         () => apiFetch('/api/v1/sensors/anomalies'),
    refetchInterval: REFETCH_INTERVAL_MS,
    staleTime:       20_000,
    // Faqat anomaliyalar tabida faol bo'lganda refetch qilish samaradorligi uchun
    enabled: activeTab === 'anomalies' || activeTab === 'overview',
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  const lastUpdate = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('uz-UZ')
    : null;

  function handleRefreshAll() {
    refetchStats();
    refetchDevices();
    refetchAnomalies();
  }

  const anomalyCount  = anomaliesData?.total  ?? stats?.anomalies_today ?? 0;
  const deviceCount   = devicesData?.total     ?? stats?.total_devices   ?? 0;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={{
      maxWidth: 900,
      margin: '0 auto',
      padding: '24px 20px 40px',
      fontFamily: "'Outfit', sans-serif",
    }}>

      {/* Pulse animation keyframe */}
      <style>{`
        @keyframes tv-pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'flex-start',
        justifyContent: 'space-between',
        marginBottom: 24,
        flexWrap: 'wrap', gap: 12,
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: '#EDE9FE',
              display: 'grid', placeItems: 'center',
              flexShrink: 0,
            }}>
              <Radio size={18} color="#7C3AED" />
            </div>
            <div>
              <h1 style={{
                margin: 0,
                fontSize: 20, fontWeight: 700,
                color: 'var(--text-primary)',
                lineHeight: 1.2,
              }}>
                IoT Sensor Monitoring
              </h1>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                Sprint 17-18 · Real-time qurilma monitoringi
              </div>
            </div>
          </div>
        </div>

        {/* Right: last update + refresh */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {lastUpdate && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 11, color: 'var(--text-muted)',
            }}>
              <Clock size={12} />
              {lastUpdate}
            </div>
          )}
          <button
            onClick={handleRefreshAll}
            disabled={statsLoading && devicesLoading}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 14px',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              cursor: 'pointer',
              fontSize: 12, fontWeight: 600,
              color: 'var(--text-secondary)',
              fontFamily: "'Outfit', sans-serif",
              opacity: (statsLoading && devicesLoading) ? 0.6 : 1,
            }}
          >
            <RefreshCw
              size={13}
              style={{
                animation: (statsLoading || devicesLoading)
                  ? 'tv-spin .65s linear infinite'
                  : 'none',
              }}
            />
            Yangilash
          </button>
        </div>
      </div>

      {/* ── Error Banner ───────────────────────────────────────────────── */}
      {statsError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px',
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: 10,
          marginBottom: 20,
          fontSize: 13, color: '#DC2626',
        }}>
          <AlertTriangle size={15} />
          Sensor ma'lumotlari yuklanishida xatolik. Internet aloqasini tekshiring.
        </div>
      )}

      {/* ── KPI Cards ──────────────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        gap: 12,
        marginBottom: 24,
      }}>
        <KPICard
          icon={<Server size={18} />}
          label="Jami qurilmalar"
          value={stats?.total_devices ?? deviceCount}
          sub={`${devicesData?.devices.filter(d => isOnline(d.last_seen)).length ?? 0} ta online`}
          color="#1E3EB4"
          loading={statsLoading}
        />
        <KPICard
          icon={<Zap size={18} />}
          label="Bugungi o'lchovlar"
          value={stats?.total_readings_today ?? 0}
          sub="Jami qabul qilingan"
          color="#10B981"
          loading={statsLoading}
        />
        <KPICard
          icon={<Heart size={18} />}
          label="Sensorli jonivorlar"
          value={stats?.animals_with_sensors ?? 0}
          sub="Aktiv monitoring"
          color="#8B5CF6"
          loading={statsLoading}
        />
        <KPICard
          icon={<AlertTriangle size={18} />}
          label="Anomaliyalar"
          value={stats?.anomalies_today ?? 0}
          sub={
            (stats?.anomalies_today ?? 0) === 0
              ? 'Hammasi normal'
              : 'Bugun aniqlangan'
          }
          color={
            (stats?.anomalies_today ?? 0) === 0 ? '#10B981' : '#D97706'
          }
          loading={statsLoading}
        />
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────────── */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        overflow: 'hidden',
      }}>
        {/* Tab bar */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          overflowX: 'auto',
          padding: '0 4px',
        }}>
          <Tab
            label="Umumiy"
            active={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
          />
          <Tab
            label="Qurilmalar"
            active={activeTab === 'devices'}
            onClick={() => setActiveTab('devices')}
            badge={deviceCount}
          />
          <Tab
            label="Anomaliyalar"
            active={activeTab === 'anomalies'}
            onClick={() => setActiveTab('anomalies')}
            badge={anomalyCount}
          />
          <Tab
            label="Tarix"
            active={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
          />
        </div>

        {/* Tab content */}
        <div style={{ padding: '20px' }}>
          {activeTab === 'overview' && (
            <OverviewTab
              stats={stats}
              statsLoading={statsLoading}
            />
          )}
          {activeTab === 'devices' && (
            <DevicesTab
              data={devicesData}
              isLoading={devicesLoading}
            />
          )}
          {activeTab === 'anomalies' && (
            <AnomaliesTab
              data={anomaliesData}
              isLoading={anomaliesLoading}
            />
          )}
          {activeTab === 'history' && (
            <HistoryTab />
          )}
        </div>
      </div>

      {/* ── Footer: auto-refresh bildiruvi ─────────────────────────────── */}
      <div style={{
        marginTop: 16,
        display: 'flex', alignItems: 'center', gap: 6,
        justifyContent: 'center',
        fontSize: 11, color: 'var(--text-muted)',
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: '#10B981',
          animation: 'tv-pulse 2s ease-in-out infinite',
        }} />
        Ma'lumotlar har 30 soniyada avtomatik yangilanadi
      </div>

    </div>
  );
}