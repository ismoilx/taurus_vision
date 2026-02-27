/**
 * Live Feed Page — Optimized
 *
 * OPTIMIZATSIYA:
 *   - Global WebSocketContext ishlatadi — sahifaga kirganingizda WS allaqachon ulangan
 *   - Sahifadan chiqsangiz ham ma'lumotlar WebSocketContext da saqlanib qoladi
 *   - Pipeline status React Query keshidan — yangi API call ketmaydi
 */

import { useState, useEffect } from 'react';
import { Camera, AlertCircle } from 'lucide-react';
import { useWebSocketContext } from '../context/WebSocketContext';
import { ConnectionStatus } from '../shared/components/ConnectionStatus';
import { LiveFeedCard } from '../features/live-feed/components/LiveFeedCard';
import { ConnectionStatus as WsStatus } from '../shared/types';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { queryKeys } from '../lib/queryClient';

export default function LiveFeedPage() {
  const { status, liveDetections } = useWebSocketContext();

  const { data: pipelineData } = useQuery({
    queryKey: queryKeys.pipeline.status,
    queryFn:  () => apiFetch<{ running: boolean }>('/api/v1/pipeline/status'),

    refetchInterval: 10_000, // WS fallback
  });
  const pipelineRunning = pipelineData?.running ?? false;

  const [newId, setNewId] = useState<number | null>(null);
  useEffect(() => {
    if (liveDetections.length > 0) {
      setNewId(liveDetections[0].animal_id);
      const t = setTimeout(() => setNewId(null), 3000);
      return () => clearTimeout(t);
    }
  }, [liveDetections]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Live Feed</h1>
          <p className="text-gray-600 mt-1">
            Real-time vazn o'lchovlari
            {liveDetections.length > 0 && (
              <span className="ml-2 text-sm">({liveDetections.length} ta o'lchov)</span>
            )}
          </p>
        </div>
        <ConnectionStatus status={status} />
      </div>

      {!pipelineRunning && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-900 mb-1">Pipeline to'xtatilgan</p>
            <p className="text-sm text-yellow-700">
              Live feed uchun Dashboard sahifasidan Pipeline ni ishga tushiring.
            </p>
          </div>
        </div>
      )}

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
            <p className="text-sm font-medium text-red-900 mb-1">Ulanish xatolik</p>
            <p className="text-sm text-red-700">
              WebSocket serverga ulanib bo'lmadi. Backend ishlaganini tekshiring.
            </p>
          </div>
        </div>
      )}

      {liveDetections.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-16 text-center">
          <Camera className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 text-lg mb-2">
            {pipelineRunning ? "Birinchi o'lchovni kutmoqda..." : "Pipeline to'xtatilgan"}
          </p>
          <p className="text-gray-500 text-sm">
            {pipelineRunning
              ? 'Jonivor kamera oldiga kelganda avtomatik aniqlanadi'
              : "Pipeline ni ishga tushirish uchun Dashboard ga o'ting"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {liveDetections.map((m, i) => (
            <LiveFeedCard
              key={`${m.animal_id}-${m.timestamp}-${i}`}
              measurement={m}
              isNew={m.animal_id === newId && i === 0}
            />
          ))}
        </div>
      )}

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