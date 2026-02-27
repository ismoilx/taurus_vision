/**
 * Taurus Vision — Global WebSocket Context (Server Push Integration)
 *
 * ARXITEKTURA:
 *   WebSocket event kelganda → queryClient cache ni yangilaydi →
 *   barcha sahifalar darhol yangi ma'lumotni ko'radi.
 *   API call HECH QACHON qaytadan ketmaydi.
 *
 * EVENT TURLARI VA KESH YANGILANISHI:
 *
 *   "detection" eventi keldi:
 *     → liveDetections listiga qo'shiladi (LiveFeedPage uchun)
 *     → pipeline stats yangilanadi
 *     → analytics:overview detection count +1 bo'ladi (optimistic update)
 *
 *   "alert" eventi keldi:
 *     → ['alerts'] keshi invalidate qilinadi → AlertsPage yangi alert ko'radi
 *
 *   "pipeline_status" eventi keldi:
 *     → pipeline keshi to'g'ridan-to'g'ri setQueryData bilan yangilanadi
 *
 *   "heartbeat" eventi — faqat WS tirik ekanini bildiradi, hech narsa qilinmaydi
 *
 * SAHIFA ALMASHTIRGANDA:
 *   - WS ulanishi UZILMAYDI (App darajasida yashaydi)
 *   - Kesh SAQLANIB qoladi (staleTime: Infinity)
 *   - Sahifaga qaytganda: 0ms da ko'rsatiladi
 */

import {
  createContext, useContext, useState, useEffect,
  useRef, useCallback, type ReactNode,
} from 'react';
import { ConnectionStatus, type WebSocketMessage, type LiveWeightUpdate } from '../shared/types';
import { queryClient, queryKeys } from '../lib/queryClient';
import config from '../config';

// ─── Context type ─────────────────────────────────────────────────────────────

interface WebSocketContextValue {
  status: ConnectionStatus;
  /** So'nggi 50 ta real-time detection — LiveFeedPage uchun */
  liveDetections: LiveWeightUpdate[];
  /** Qo'lda reconnect (token yangilanganda ishlatiladi) */
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus]               = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  const [liveDetections, setLiveDetections] = useState<LiveWeightUpdate[]>([]);

  const wsRef               = useRef<WebSocket | null>(null);
  const reconnectTimerRef   = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttemptRef = useRef(0);
  const unmountedRef        = useRef(false);

  const getWsUrl = useCallback((): string => {
    const token = localStorage.getItem('tv_access_token') ?? '';
    return `${config.wsUrl}/api/v1/live/ws${token ? `?token=${token}` : ''}`;
  }, []);

  // ─── Xabar handler — ASOSIY MANTIQ ─────────────────────────────────────────
  const handleMessage = useCallback((event: MessageEvent) => {
    if (unmountedRef.current) return;

    let data: WebSocketMessage;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }

    const raw     = data as any;
    const payload = raw?.data ?? raw;
    const type    = payload?.type ?? data.type;

    // ── Detection event ────────────────────────────────────────────────────
    if (type === 'detection') {
      // 1. LiveFeedPage uchun list ga qo'shamiz
      const update: LiveWeightUpdate = {
        animal_id:           payload.animal_id ?? 0,
        animal_tag_id:       payload.animal_tag_id ?? payload.class_name ?? 'UNKNOWN',
        estimated_weight_kg: payload.estimated_weight_kg ?? 0,
        confidence_score:    payload.confidence_score ?? payload.confidence ?? 0,
        camera_id:           payload.camera_id ?? '',
        timestamp:           payload.timestamp ?? new Date().toISOString(),
      };
      setLiveDetections(prev => [update, ...prev].slice(0, 50));

      // 2. Dashboard overview — bugungi detection count ni +1 qilamiz
      //    Bu optimistic update: API call qilmasdan UI ni yangilaymiz
      queryClient.setQueryData(queryKeys.analytics.overview, (old: any) => {
        if (!old) return old;
        return {
          ...old,
          detections: {
            ...old.detections,
            today: (old.detections?.today ?? 0) + 1,
            week:  (old.detections?.week  ?? 0) + 1,
            month: (old.detections?.month ?? 0) + 1,
            total: (old.detections?.total ?? 0) + 1,
          },
        };
      });

      // 3. Pipeline status stats ni yangilaymiz
      if (payload.pipeline_stats) {
        queryClient.setQueryData(queryKeys.pipeline.status, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            stats: {
              ...old.stats,
              fps: payload.pipeline_stats.fps ?? old.stats?.fps ?? 0,
              total_frames: payload.pipeline_stats.frames ?? old.stats?.total_frames ?? 0,
            },
          };
        });
      }
    }

    // ── Alert event ───────────────────────────────────────────────────────────
    else if (type === 'alert' || type === 'new_alert') {
      // Alerts keshini invalidate qilamiz — AlertsPage qayta yuklanadi
      queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
      // Dashboard health metricsini ham yangilaymiz
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics.health });
    }

    // ── Pipeline status event ─────────────────────────────────────────────────
    else if (type === 'pipeline_status' || type === 'pipeline_update') {
      queryClient.setQueryData(queryKeys.pipeline.status, (old: any) => ({
        ...(old ?? {}),
        status:  payload.status  ?? old?.status,
        running: payload.running ?? old?.running,
      }));
    }

    // ── Animal update event ───────────────────────────────────────────────────
    else if (type === 'animal_update' && payload.animal_id) {
      // Faqat shu jonivorning detail keshini yangilaymiz
      queryClient.invalidateQueries({ queryKey: queryKeys.animals.detail(payload.animal_id) });
    }

  }, []);

  // ─── WebSocket ulanish ─────────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (unmountedRef.current) return;

    const url = getWsUrl();
    if (!url || url.endsWith('/ws')) return; // token yo'q

    try {
      setStatus(ConnectionStatus.CONNECTING);
      const ws = new WebSocket(url);

      ws.onopen = () => {
        if (unmountedRef.current) { ws.close(); return; }
        setStatus(ConnectionStatus.CONNECTED);
        reconnectAttemptRef.current = 0;
      };

      ws.onclose = (event) => {
        if (unmountedRef.current) return;
        wsRef.current = null;
        setStatus(ConnectionStatus.DISCONNECTED);
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);

        // Auth xatosi yoki juda ko'p urinish — to'xtatamiz
        if (event.code === 4001 || event.code === 4003 || reconnectAttemptRef.current >= 8) {
          setStatus(ConnectionStatus.ERROR);
          return;
        }

        // Exponential backoff: 2s → 4s → 8s → 16s → max 30s
        const delay = Math.min(2000 * Math.pow(2, reconnectAttemptRef.current), 30_000);
        reconnectAttemptRef.current += 1;
        setStatus(ConnectionStatus.RECONNECTING);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        setStatus(ConnectionStatus.ERROR);
      };

      ws.onmessage = handleMessage;
      wsRef.current = ws;

    } catch (err) {
      console.error('[WS] Ulanish xatosi:', err);
      setStatus(ConnectionStatus.ERROR);
    }
  }, [getWsUrl, handleMessage]);

  const reconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    reconnectAttemptRef.current = 0;
    connect();
  }, [connect]);

  // Mount bo'lganda — token bo'lsa ulanamiz
  useEffect(() => {
    unmountedRef.current = false;
    const token = localStorage.getItem('tv_access_token');
    if (token) connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{ status, liveDetections, reconnect }}>
      {children}
    </WebSocketContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useWebSocketContext(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error('useWebSocketContext must be inside <WebSocketProvider>');
  return ctx;
}