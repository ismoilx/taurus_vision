import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
} from 'react';

import {
  ConnectionStatus,
  type WebSocketMessage,
  type LiveWeightUpdate,
  type LiveTrackedUpdate,
  type TrackedAnimal,
} from '../shared/types';

import { queryClient, queryKeys } from '../lib/queryClient';
import config from '../config';

// ─── Context type ──────────────────────────────────────────────────────────────

interface WebSocketContextValue {
  status: ConnectionStatus;
  liveDetections: LiveWeightUpdate[];
  liveTrackedUpdates: LiveTrackedUpdate[];
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// ─── Provider ──────────────────────────────────────────────────────────────────

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>(
    ConnectionStatus.DISCONNECTED,
  );
  const [liveDetections, setLiveDetections] = useState<LiveWeightUpdate[]>([]);
  const [liveTrackedUpdates, setLiveTrackedUpdates] = useState<
    LiveTrackedUpdate[]
  >([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttemptRef = useRef(0);
  const unmountedRef = useRef(false);

  const getWsUrl = useCallback((): string => {
    const token = localStorage.getItem('tv_access_token') ?? '';
    return `${config.wsUrl}/api/v1/live/ws${token ? `?token=${token}` : ''}`;
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    if (unmountedRef.current) return;

    let data: WebSocketMessage;
    try {
      data = JSON.parse(event.data) as WebSocketMessage;
    } catch {
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const payload: any = (data as any)?.data ?? data;
    const type: string = payload?.type ?? '';

    if (type === 'tracked_detections') {
      const tracks = (payload.tracks ?? []) as TrackedAnimal[];
      const camera = (payload.camera ?? '') as string;
      const now = new Date().toISOString();

      const newUpdates: LiveTrackedUpdate[] = tracks
        .filter((t) => t.state === 'unidentified' || t.state === 'identified')
        .map(
          (t): LiveTrackedUpdate => ({
            camera_id: camera,
            track_id: t.track_id,
            animal_id: t.animal_id,
            tag_id: t.tag_id,
            state: t.state as 'unidentified' | 'identified',
            bbox_color: t.bbox_color,
            confidence: t.confidence,
            id_score: t.identification_score,
            timestamp: now,
          }),
        );

      if (newUpdates.length > 0) {
        setLiveTrackedUpdates((prev) => [...newUpdates, ...prev].slice(0, 60));
      }

      const identifiedCount = tracks.filter((t) => t.state === 'identified').length;
      if (identifiedCount > 0) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        queryClient.setQueryData(queryKeys.analytics.overview, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            detections: {
              ...old.detections,
              today: (old.detections?.today ?? 0) + identifiedCount,
              total: (old.detections?.total ?? 0) + identifiedCount,
            },
          };
        });
      }
    } else if (type === 'detection') {
      const update: LiveWeightUpdate = {
        animal_id: payload.animal_id ?? 0,
        animal_tag_id: payload.animal_tag_id ?? payload.class_name ?? 'UNKNOWN',
        estimated_weight_kg: payload.estimated_weight_kg ?? 0,
        confidence_score: payload.confidence_score ?? payload.confidence ?? 0,
        camera_id: payload.camera_id ?? '',
        timestamp: payload.timestamp ?? new Date().toISOString(),
      };
      setLiveDetections((prev) => [update, ...prev].slice(0, 50));
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      queryClient.setQueryData(queryKeys.analytics.overview, (old: any) => {
        if (!old) return old;
        return {
          ...old,
          detections: {
            ...old.detections,
            today: (old.detections?.today ?? 0) + 1,
            total: (old.detections?.total ?? 0) + 1,
          },
        };
      });
    } else if (type === 'alert' || type === 'new_alert') {
      queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics.health });
    } else if (type === 'pipeline_status' || type === 'pipeline_update') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      queryClient.setQueryData(queryKeys.pipeline.status, (old: any) => ({
        ...(old ?? {}),
        status: payload.status ?? old?.status,
        running: payload.running ?? old?.running,
      }));
    } else if (type === 'animal_update' && payload.animal_id) {
      queryClient.invalidateQueries({
        queryKey: queryKeys.animals.detail(payload.animal_id),
      });
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (unmountedRef.current) return;
    const url = getWsUrl();
    if (!url || url.endsWith('/ws')) return;

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
        if (event.code === 4001 || event.code === 4003 || reconnectAttemptRef.current >= 8) {
          setStatus(ConnectionStatus.ERROR);
          return;
        }
        const delay = Math.min(2000 * Math.pow(2, reconnectAttemptRef.current), 30_000);
        reconnectAttemptRef.current += 1;
        setStatus(ConnectionStatus.RECONNECTING);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => { setStatus(ConnectionStatus.ERROR); };
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
    <WebSocketContext.Provider value={{ status, liveDetections, liveTrackedUpdates, reconnect }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error('useWebSocketContext must be inside <WebSocketProvider>');
  return ctx;
}