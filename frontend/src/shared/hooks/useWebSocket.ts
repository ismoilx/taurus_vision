/**
 * Taurus Vision — useWebSocket Hook
 *
 * Xususiyatlar:
 *   - url string yoki () => string factory qabul qiladi
 *     Factory bo'lsa har reconnect da yangi URL hisoblanadi
 *     (masalan, yangicha JWT token bilan)
 *   - Exponential backoff bilan auto-reconnect (max 10 soniya)
 *   - Barcha connection holatlari boshqariladi
 *
 * FOYDALANISH (token bilan):
 *   const { status, lastMessage } = useWebSocket(
 *     () => `ws://host/api/v1/live/ws?token=${localStorage.getItem('tv_access_token') ?? ''}`
 *   );
 *
 * FOYDALANISH (oddiy URL bilan):
 *   const { status, lastMessage } = useWebSocket('ws://host/api/v1/live/ws');
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { ConnectionStatus, type WebSocketMessage } from '../types';

// Reconnect paytida token olib qaytadigan factory yoki oddiy URL string
type WsUrl = string | (() => string);

interface UseWebSocketOptions {
  onConnect?:    () => void;
  onDisconnect?: () => void;
  onMessage?:    (message: WebSocketMessage) => void;
  /** Minimum reconnect kutish vaqti (ms). Default: 1000 */
  minReconnectMs?: number;
  /** Maksimum reconnect kutish vaqti (ms). Default: 10000 */
  maxReconnectMs?: number;
}

export function useWebSocket(url: WsUrl, options: UseWebSocketOptions = {}) {
  const [status, setStatus]           = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const socketRef           = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef   = useRef<ReturnType<typeof setTimeout>>();
  const optionsRef          = useRef(options);

  // options ref ni har render da yangilash — closure muammosini hal qiladi
  useEffect(() => {
    optionsRef.current = options;
  });

  // URL ni olish — string yoki factory
  const resolveUrl = useCallback((): string => {
    return typeof url === 'function' ? url() : url;
  }, [url]);

  const connect = useCallback(() => {
    // Allaqachon ulangan bo'lsa — qayta ulanmaydi
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = resolveUrl();

    // Token bo'lmasa — ulanishga urinmaymiz (4001 kelib qayta urinadi)
    // Bu yerda biz URL ni yasayapmiz — token yo'qligini URL dan aniqlaymiz
    if (wsUrl.includes('token=') && wsUrl.endsWith('token=')) {
      // token= bor lekin qiymati yo'q
      setStatus(ConnectionStatus.ERROR);
      return;
    }

    try {
      setStatus(ConnectionStatus.CONNECTING);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setStatus(ConnectionStatus.CONNECTED);
        reconnectAttemptRef.current = 0;
        optionsRef.current.onConnect?.();
      };

      ws.onclose = (event) => {
        setStatus(ConnectionStatus.DISCONNECTED);
        optionsRef.current.onDisconnect?.();
        socketRef.current = null;

        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);

        // Nginx orqali WebSocket ishlamasa (1006) yoki token xato bo'lsa (4001, 4003)
        // Haddan tashqari ko'p urinishlarning oldini olamiz
        if (event.code === 4001 || event.code === 4003 || reconnectAttemptRef.current > 10) {
          setStatus(ConnectionStatus.ERROR);
          console.warn(`[WebSocket] Ulanish to'xtatildi. Kod: ${event.code}. Sabab: ${event.reason || 'Noma\'lum xato yoki urinishlar tugadi'}`);
          return; // Qayta ulanishga urinmaymiz
        }

        // Exponential backoff: 1s → 2s → 4s → 8s → 10s (max)
        const min = optionsRef.current.minReconnectMs ?? 2000; // Minimal kutish vaqtini 1 emas, 2 soniyaga oshirdim
        const max = optionsRef.current.maxReconnectMs ?? 10_000;
        const delay = Math.min(min * Math.pow(2, reconnectAttemptRef.current), max);
        reconnectAttemptRef.current += 1;

        setStatus(ConnectionStatus.RECONNECTING);
        // Bu console.log ni qo'shdik, shunda brauzer necha soniyadan keyin qayta ulanishini ko'rsatadi
        console.log(`[WebSocket] Ulanish uzildi. ${delay}ms dan keyin qayta urinish... (Urinish: ${reconnectAttemptRef.current})`);
        
        reconnectTimerRef.current = setTimeout(() => connect(), delay);
      };

      ws.onerror = () => {
        // onclose ham chaqiriladi — bu yerda faqat log
        setStatus(ConnectionStatus.ERROR);
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(data);
          optionsRef.current.onMessage?.(data);
        } catch (e) {
          console.error('[WebSocket] Xabar parse xatosi:', e);
        }
      };

      socketRef.current = ws;

    } catch (err) {
      console.error('[WebSocket] Ulanish xatosi:', err);
      setStatus(ConnectionStatus.ERROR);
    }
  }, [resolveUrl]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setStatus(ConnectionStatus.DISCONNECTED);
  }, []);

  useEffect(() => {
    connect();
    return () => { disconnect(); };
  }, [connect, disconnect]);

  return { status, lastMessage, connect, disconnect };
}