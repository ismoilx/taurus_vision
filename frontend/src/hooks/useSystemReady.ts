/**
 * Backend YOLO model yuklanishini kuzatadi.
 * /health/ready endpoint 200 qaytarguncha polling qiladi.
 */
import { useState, useEffect, useRef } from 'react';

export type ReadyState = 'checking' | 'ready' | 'error';

export function useSystemReady() {
  const [state, setState] = useState<ReadyState>('checking');
  const [dots, setDots]   = useState('');
  const timerRef           = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dotRef             = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let attempts = 0;
    let cancelled = false;

    async function check() {
      if (cancelled) return;
      try {
        const res = await fetch('/health/ready', { signal: AbortSignal.timeout(4000) });
        if (res.ok) {
          if (!cancelled) setState('ready');
          return;
        }
      } catch {
        // hali yuklanmoqda
      }
      attempts++;
      if (attempts >= 30) {
        if (!cancelled) setState('error');
        return;
      }
      timerRef.current = setTimeout(check, 2000);
    }

    dotRef.current = setInterval(() =>
      setDots(d => d.length >= 3 ? '' : d + '.'), 500);

    check();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (dotRef.current)   clearInterval(dotRef.current);
    };
  }, []);

  return { state, dots };
}