import { useState, useEffect, useRef, useCallback } from 'react';
import { ConnectionStatus, type WebSocketMessage } from '../types';

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
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    try {
      setStatus(ConnectionStatus.CONNECTING);
      const socket = new WebSocket(url);

      socket.onopen = () => {
        setStatus(ConnectionStatus.CONNECTED);
        reconnectAttemptRef.current = 0;
        optionsRef.current.onConnect?.();
      };

      socket.onclose = () => {
        setStatus(ConnectionStatus.DISCONNECTED);
        optionsRef.current.onDisconnect?.();

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);

        const timeout = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 10000);
        reconnectAttemptRef.current += 1;
        setStatus(ConnectionStatus.RECONNECTING);
        reconnectTimeoutRef.current = setTimeout(() => connect(), timeout);
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
          console.error('WebSocket parse error:', e);
        }
      };

      socketRef.current = socket;
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setStatus(ConnectionStatus.ERROR);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      socketRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { status, lastMessage, connect };
}