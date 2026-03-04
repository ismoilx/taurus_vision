/**
 * SensorWidget — IoT Sensor Real-time Monitor (Sprint 17-18)
 *
 * Dashboard da ko'rsatiladigan sensor kartasi.
 * Ferma bo'yicha sensor statistikasini va oxirgi anomaliyalarni ko'rsatadi.
 *
 * ENDPOINT:
 *   GET /api/v1/sensors/stats     — Umumiy statistika
 *   GET /api/v1/sensors/anomalies — Bugungi anomaliyalar
 *   GET /api/v1/sensors/devices   — Aktiv qurilmalar
 *
 * YANGILANISH:
 *   30 soniyada bir avtomatik refetch (React Query)
 */

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import {
  Thermometer, Heart, Activity, Wifi, WifiOff,
  AlertTriangle, CheckCircle, RefreshCw,
} from 'lucide-react';

// =============================================================================
// TYPES
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
  device_type:   string;
  animal_id:     number | null;
  reading_count: number;
  last_seen:     string;
}

// =============================================================================
// HELPERS
// =============================================================================

function timeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'hozir';
  if (mins < 60) return `${mins}d oldin`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}s oldin`;
  return `${Math.floor(hrs / 24)} kun oldin`;
}

function deviceIcon(type: string) {
  if (type === 'collar')      return <Heart size={12} />;
  if (type === 'scale')       return <Activity size={12} />;
  if (type === 'environment') return <Thermometer size={12} />;
  return <Wifi size={12} />;
}

// =============================================================================
// MINI STAT CARD
// =============================================================================

function StatBadge({
  icon, value, label, color = '#374151',
}: {
  icon: React.ReactNode;
  value: number | string;
  label: string;
  color?: string;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 2, flex: 1,
    }}>
      <div style={{ color, display: 'flex', alignItems: 'center', gap: 4 }}>
        {icon}
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700 }}>
          {value}
        </span>
      </div>
      <span style={{ fontSize: 10, color: '#9CA3AF', textAlign: 'center', lineHeight: 1.2 }}>
        {label}
      </span>
    </div>
  );
}

// =============================================================================
// ANOMALY ROW
// =============================================================================

function AnomalyRow({ item }: { item: AnomalyItem }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 8,
      padding: '6px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <AlertTriangle size={13} color="#F59E0B" style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {item.device_id}
          {item.animal_id && (
            <span style={{ fontWeight: 400, color: '#6B7280', marginLeft: 6 }}>
              #{item.animal_id}
            </span>
          )}
        </div>
        {item.issues.map((issue, i) => (
          <div key={i} style={{ fontSize: 11, color: '#DC2626', marginTop: 1 }}>
            {issue}
          </div>
        ))}
      </div>
      <span style={{ fontSize: 10, color: '#9CA3AF', flexShrink: 0 }}>
        {timeAgo(item.recorded_at)}
      </span>
    </div>
  );
}

// =============================================================================
// DEVICE ROW
// =============================================================================

function DeviceRow({ device }: { device: DeviceItem }) {
  const lastSeenDate = new Date(device.last_seen);
  const minsAgo      = Math.floor((Date.now() - lastSeenDate.getTime()) / 60000);
  const isOnline     = minsAgo < 30;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '5px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <div style={{
        color: isOnline ? '#10B981' : '#9CA3AF',
        display: 'flex', alignItems: 'center',
      }}>
        {isOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 11, fontWeight: 600,
          color: 'var(--text-primary)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {device.device_id}
        </div>
        <div style={{ fontSize: 10, color: '#9CA3AF' }}>
          {device.device_type} · {device.reading_count} o'lchov
        </div>
      </div>
      <span style={{
        fontSize: 10,
        color: isOnline ? '#10B981' : '#9CA3AF',
        flexShrink: 0,
      }}>
        {timeAgo(device.last_seen)}
      </span>
    </div>
  );
}

// =============================================================================
// MAIN WIDGET
// =============================================================================

export function SensorWidget() {
  const { data: stats, isLoading: statsLoading, refetch } = useQuery<SensorStats>({
    queryKey: ['sensor-stats'],
    queryFn:  () => apiFetch('/api/v1/sensors/stats'),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const { data: devicesData, isLoading: devicesLoading } = useQuery<{ total: number; devices: DeviceItem[] }>({
    queryKey: ['sensor-devices'],
    queryFn:  () => apiFetch('/api/v1/sensors/devices'),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const isLoading = statsLoading || devicesLoading;

  const hasAnomalies = (stats?.anomalies_today ?? 0) > 0;
  const allOnline    = (devicesData?.devices ?? []).every(d => {
    const minsAgo = Math.floor((Date.now() - new Date(d.last_seen).getTime()) / 60000);
    return minsAgo < 30;
  });

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      padding: '16px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      height: '100%',
    }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: hasAnomalies ? '#FEF3C7' : '#ECFDF5',
            display: 'grid', placeItems: 'center',
          }}>
            <Activity size={14} color={hasAnomalies ? '#D97706' : '#10B981'} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              IoT Sensorlar
            </div>
            <div style={{ fontSize: 10, color: '#9CA3AF' }}>
              Real-time monitoring
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Status pill */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            padding: '3px 8px', borderRadius: 20,
            background: hasAnomalies ? '#FEF3C7' : '#ECFDF5',
            border: `1px solid ${hasAnomalies ? '#FDE68A' : '#A7F3D0'}`,
          }}>
            {hasAnomalies
              ? <AlertTriangle size={10} color="#D97706" />
              : <CheckCircle  size={10} color="#10B981" />
            }
            <span style={{
              fontSize: 10, fontWeight: 600,
              color: hasAnomalies ? '#D97706' : '#10B981',
            }}>
              {hasAnomalies ? `${stats?.anomalies_today} anomaliya` : 'Normal'}
            </span>
          </div>

          {/* Refresh */}
          <button
            onClick={() => refetch()}
            style={{
              width: 26, height: 26, borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'transparent',
              display: 'grid', placeItems: 'center',
              cursor: 'pointer', color: '#9CA3AF',
            }}
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {/* ── Stats Row ── */}
      {isLoading ? (
        <div style={{
          display: 'flex', justifyContent: 'center', padding: '16px 0',
        }}>
          <div style={{
            width: 20, height: 20,
            border: '2px solid var(--border)',
            borderTopColor: '#1E3EB4',
            borderRadius: '50%',
            animation: 'tv-spin .65s linear infinite',
          }} />
        </div>
      ) : (
        <div style={{
          display: 'flex', alignItems: 'center',
          padding: '10px 0',
          borderTop: '1px solid var(--border)',
          borderBottom: '1px solid var(--border)',
          gap: 8,
        }}>
          <StatBadge
            icon={<Wifi size={14} />}
            value={stats?.total_devices ?? 0}
            label="Qurilmalar"
            color="#1E3EB4"
          />
          <div style={{ width: 1, height: 32, background: 'var(--border)' }} />
          <StatBadge
            icon={<Activity size={14} />}
            value={stats?.total_readings_today ?? 0}
            label="Bugun o'lchovlar"
            color="#10B981"
          />
          <div style={{ width: 1, height: 32, background: 'var(--border)' }} />
          <StatBadge
            icon={<AlertTriangle size={14} />}
            value={stats?.anomalies_today ?? 0}
            label="Anomaliyalar"
            color={hasAnomalies ? '#D97706' : '#9CA3AF'}
          />
          <div style={{ width: 1, height: 32, background: 'var(--border)' }} />
          <StatBadge
            icon={<Heart size={14} />}
            value={stats?.animals_with_sensors ?? 0}
            label="Jonivorlar"
            color="#8B5CF6"
          />
        </div>
      )}

      {/* ── Content: Anomalies OR Devices ── */}
      {!isLoading && (
        <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>

          {/* Anomaliyalar bo'lsa — ko'rsatish */}
          {hasAnomalies && (stats?.recent_anomalies?.length ?? 0) > 0 ? (
            <div>
              <div style={{
                fontSize: 10, fontWeight: 700, color: '#9CA3AF',
                letterSpacing: '0.06em', textTransform: 'uppercase',
                marginBottom: 6,
              }}>
                So'nggi anomaliyalar
              </div>
              <div style={{ maxHeight: 160, overflowY: 'auto' }}>
                {stats!.recent_anomalies.slice(0, 5).map((item, i) => (
                  <AnomalyRow key={i} item={item} />
                ))}
              </div>
            </div>
          ) : (
            /* Anomaliya yo'q — qurilmalar ro'yxati */
            <div>
              <div style={{
                fontSize: 10, fontWeight: 700, color: '#9CA3AF',
                letterSpacing: '0.06em', textTransform: 'uppercase',
                marginBottom: 6,
              }}>
                Aktiv qurilmalar
              </div>
              {(devicesData?.devices?.length ?? 0) === 0 ? (
                <div style={{
                  padding: '20px 0', textAlign: 'center',
                  color: '#9CA3AF', fontSize: 12,
                }}>
                  <Wifi size={24} style={{ margin: '0 auto 8px', opacity: 0.3, display: 'block' }} />
                  Hali sensor ulangani yo'q
                </div>
              ) : (
                <div style={{ maxHeight: 160, overflowY: 'auto' }}>
                  {devicesData!.devices.slice(0, 6).map((d, i) => (
                    <DeviceRow key={i} device={d} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SensorWidget;