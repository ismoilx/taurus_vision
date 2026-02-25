/**
 * Live Feed Page
 * 
 * Real-time weight measurements via WebSocket
 */

import { useState, useEffect } from 'react';
import { Camera, Activity, AlertCircle } from 'lucide-react';
import { useWebSocket } from '../shared/hooks/useWebSocket';
import { ConnectionStatus } from '../shared/components/ConnectionStatus';
import { LiveFeedCard } from '../features/live-feed/components/LiveFeedCard';
import {
  ConnectionStatus as WsStatus,
  type LiveWeightUpdate,
} from '../shared/types';
import config from '../config';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

// Yangi to'g'irlangan qism:
export default function LiveFeedPage() {
  // Endi "lastMessage" ni chaqirib olamiz
  // Factory funksiya — har reconnect da tokenni localStorage dan yangi o'qiydi
  // Bu token refresh bo'lgandan keyin ham to'g'ri ulanishni ta'minlaydi
  const { status, lastMessage, connect, disconnect } = useWebSocket(
    () => {
      const t = localStorage.getItem('tv_access_token');
      return config.wsUrl + '/api/v1/live/ws' + (t ? `?token=${t}` : '');
    }
  );

  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [newId, setNewId] = useState<number | null>(null);
  
  // O'lchovlarni o'zimiz alohida saqlaymiz va turlarini aniq ko'rsatamiz:
  const [measurements, setMeasurements] = useState<LiveWeightUpdate[]>([]);

  // Yangi xabar kelganda, uni measurements ro'yxatiga qo'shamiz
  useEffect(() => {
    if (!lastMessage) return;

    // Backend format: { type: "weight_update", data: { type: "detection", animal_id, ... } }
    const raw = lastMessage as any;
    const payload = raw?.data ?? raw;

    // Faqat detection eventlarini qabul qilamiz
    if (payload?.type !== 'detection') return;

    // LiveWeightUpdate formatiga o'giramiz
    const update: LiveWeightUpdate = {
      animal_id:            payload.animal_id ?? 0,
      animal_tag_id:        payload.animal_tag_id ?? payload.class_name ?? 'UNKNOWN',
      estimated_weight_kg:  payload.estimated_weight_kg ?? 0,
      confidence_score:     payload.confidence_score ?? payload.confidence ?? 0,
      camera_id:            payload.camera_id ?? '',
      timestamp:            payload.timestamp ?? new Date().toISOString(),
    };

    setMeasurements(prev =>
      [update, ...prev].slice(0, 20)
    );

  }, [lastMessage]);

  // ---------------------------------------------------------------------------
  // Pipeline Status Check
  // ---------------------------------------------------------------------------

  useEffect(() => {
    checkPipeline();
    const interval = setInterval(checkPipeline, 5000);
    return () => clearInterval(interval);
  }, []);

  async function checkPipeline() {
    try {
      const data = await apiFetch<{ running: boolean }>('/api/v1/pipeline/status');
      setPipelineRunning(data.running);
    } catch (err) {
      console.error('Pipeline check error:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // WebSocket Management
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (pipelineRunning && status === WsStatus.DISCONNECTED) {
      connect();
    }
  }, [pipelineRunning, status]);

  useEffect(() => {
    return () => disconnect();
  }, []);

  // Track new measurements
  useEffect(() => {
    if (measurements.length > 0) {
      const latest = measurements[0];
      setNewId(latest.animal_id);
      setTimeout(() => setNewId(null), 3000);
    }
  }, [measurements]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Live Feed</h1>
          <p className="text-gray-600 mt-1">
            Real-time vazn o'lchovlari
            {measurements.length > 0 && (
              <span className="ml-2 text-sm">
                ({measurements.length} ta o'lchov)
              </span>
            )}
          </p>
        </div>

        <ConnectionStatus status={status} />
      </div>

      {/* Pipeline Warning */}
      {!pipelineRunning && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-900 mb-1">
              Pipeline to'xtatilgan
            </p>
            <p className="text-sm text-yellow-700">
              Live feed uchun Dashboard sahifasidan Pipeline ni ishga tushiring.
            </p>
          </div>
        </div>
      )}

      {/* Connection Info */}
      {pipelineRunning && status === WsStatus.CONNECTING && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
          <p className="text-sm text-blue-900">WebSocket ga ulanmoqda...</p>
        </div>
      )}

      {pipelineRunning && status === WsStatus.ERROR && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-900 mb-1">
              Ulanish xatolik
            </p>
            <p className="text-sm text-red-700">
              WebSocket serverga ulanib bo'lmadi. Backend ishlaganini tekshiring.
            </p>
          </div>
        </div>
      )}

      {/* Feed Grid */}
      {measurements.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-16 text-center">
          <Camera className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 text-lg mb-2">
            {pipelineRunning
              ? "Birinchi o'lchovni kutmoqda..."
              : "Pipeline to'xtatilgan"}
          </p>
          <p className="text-gray-500 text-sm">
            {pipelineRunning
              ? 'Jonivor kamera oldiga kelganda avtomatik aniqlanadi'
              : 'Pipeline ni ishga tushirish uchun Dashboard ga o\'ting'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {measurements.map((m, i) => (
            <LiveFeedCard
              key={`${m.animal_id}-${m.timestamp}-${i}`}
              measurement={m}
              isNew={m.animal_id === newId && i === 0}
            />
          ))}
        </div>
      )}

      {/* Live Indicator */}
      {pipelineRunning && status === WsStatus.CONNECTED && (
        <div className="fixed bottom-8 right-8 bg-white rounded-full shadow-lg px-4 py-3 flex items-center gap-2 border border-gray-200">
          <div className="relative">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            <div className="absolute inset-0 w-3 h-3 bg-green-500 rounded-full animate-ping" />
          </div>
          <span className="text-sm font-medium text-gray-900">Live</span>
        </div>
      )}
    </div>
  );
}