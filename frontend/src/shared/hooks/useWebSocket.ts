import { useState, useEffect, useRef, useCallback } from 'react';

// --- SHARED TYPES ---
export enum ConnectionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error',
}

export interface WebSocketMessage {
  type: 'connection' | 'weight_update' | 'heartbeat';
  data?: any;
  status?: string;
  message?: string;
  timestamp?: number;
}
// --------------------

interface UseWebSocketOptions {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onMessage?: (message: WebSocketMessage) => void;
  reconnectInterval?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  // 2-MUHIM O'ZGARISH: Optionsni ref ga saqlaymiz.
  // Bu infinite loop oldini oladigan eng kuchli himoya.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const connect = useCallback(() => {
    // Agar allaqachon ulangan bo'lsa, qayta ulanma
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    try {
      setStatus(ConnectionStatus.CONNECTING);
      
      const socket = new WebSocket(url);

      socket.onopen = () => {
        setStatus(ConnectionStatus.CONNECTED);
        reconnectAttemptRef.current = 0;
        // Ref orqali chaqiramiz
        optionsRef.current.onConnect?.();
      };

      socket.onclose = () => {
        setStatus(ConnectionStatus.DISCONNECTED);
        optionsRef.current.onDisconnect?.();
        
        // Cleanup old timeout
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);

        // Reconnect logic
        const timeout = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 10000);
        reconnectAttemptRef.current += 1;
        
        setStatus(ConnectionStatus.RECONNECTING);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, timeout);
      };

      socket.onerror = () => {
        setStatus(ConnectionStatus.ERROR);
      };

      socket.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(data);
          optionsRef.current.onMessage?.(data);
        } catch (e) {
          console.error('WebSocket message parse error:', e);
        }
      };

      socketRef.current = socket;
    } catch (error) {
      console.error("Connection creation error:", error);
      setStatus(ConnectionStatus.ERROR);
    }
  }, [url]); // DIQQAT: [options] bu yerda yo'q! Bu loopni to'xtatadi.

  useEffect(() => {
    connect();
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return { status, lastMessage, connect };
}