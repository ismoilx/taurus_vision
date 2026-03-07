/**
 * Taurus Vision — usePWA Hook
 *
 * PWA install prompt va Service Worker yangilanishini boshqaradi.
 *
 * IMKONIYATLAR:
 *   1. Install Prompt — "Ilovani o'rnatish" tugmasi
 *      - beforeinstallprompt ni ushlab turadi
 *      - promptInstall() → native dialog
 *      - dismissInstall() → 30 kun davomida ko'rsatmaydi
 *
 *   2. SW Update Detection — yangi versiya bildirishnomasi
 *      - Service Worker yangilanganda xabar beradi
 *      - updateApp() → yangi versiyaga o'tadi (hard reload)
 *
 *   3. isOnline — internet ulanish holati
 *   4. isInstalled — PWA yoki browser
 *   5. isIOS — iOS uchun maxsus yo'riqnoma
 *
 * FOYDALANISH:
 *   const pwa = usePWA();
 *   {pwa.canInstall && <InstallBanner onInstall={pwa.promptInstall} />}
 *   {pwa.hasUpdate  && <UpdateBanner  onUpdate={pwa.updateApp}     />}
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const DISMISS_KEY     = 'tv-pwa-install-dismissed';
const DISMISS_DAYS    = 30;

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export interface PWAState {
  /** Ilovani o'rnatish imkoni bor (Android Chrome, Edge, Desktop) */
  canInstall:  boolean;
  /** O'rnatish dialog chiqarish */
  promptInstall: () => Promise<'accepted' | 'dismissed' | 'unavailable'>;
  /** "Ko'rsatma" yashirish (30 kun) */
  dismissInstall: () => void;
  /** Yangi SW versiyasi mavjud */
  hasUpdate:   boolean;
  /** Ilovani yangi versiyaga yangilash */
  updateApp:   () => void;
  /** Internet bor/yo'q */
  isOnline:    boolean;
  /** PWA sifatida ishga tushganligi (standalone) */
  isInstalled: boolean;
  /** iOS qurilma (Safari uchun maxsus) */
  isIOS:       boolean;
  /** iOS da hali o'rnatilmagan — yo'riqnoma ko'rsatish kerak */
  showIOSGuide: boolean;
  /** iOS yo'riqnomasini yashirish */
  dismissIOSGuide: () => void;
}

export function usePWA(): PWAState {
  const deferredRef         = useRef<BeforeInstallPromptEvent | null>(null);
  const swRegistrationRef   = useRef<ServiceWorkerRegistration | null>(null);

  const [canInstall,    setCanInstall]    = useState(false);
  const [hasUpdate,     setHasUpdate]     = useState(false);
  const [isOnline,      setIsOnline]      = useState(
    () => typeof navigator !== 'undefined' ? navigator.onLine : true
  );
  const [showIOSGuide,  setShowIOSGuide]  = useState(false);

  // ── Computed ──────────────────────────────────────────────────────────────
  const isInstalled = typeof window !== 'undefined' &&
    (window.matchMedia('(display-mode: standalone)').matches ||
     (window.navigator as any).standalone === true);

  const isIOS = typeof navigator !== 'undefined' &&
    /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream;

  // ── Install prompt listener ───────────────────────────────────────────────
  useEffect(() => {
    // Allaqachon o'rnatilgan → ko'rsatma yo'q
    if (isInstalled) return;

    // 30 kun oldin dismiss qilinganmi?
    const dismissed = localStorage.getItem(DISMISS_KEY);
    if (dismissed && Date.now() - Number(dismissed) < DISMISS_DAYS * 86_400_000) return;

    const handler = (e: Event) => {
      e.preventDefault();
      deferredRef.current = e as BeforeInstallPromptEvent;
      setCanInstall(true);
    };

    window.addEventListener('beforeinstallprompt', handler);

    // iOS da native prompt yo'q — manual guide ko'rsatish
    if (isIOS && !isInstalled) {
      const iosDismissed = sessionStorage.getItem('tv-ios-guide-dismissed');
      if (!iosDismissed) {
        setTimeout(() => setShowIOSGuide(true), 3000);
      }
    }

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, [isInstalled, isIOS]);

  // ── SW yangilanish kuzatuvi ───────────────────────────────────────────────
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;

    navigator.serviceWorker.getRegistration().then((reg) => {
      if (!reg) return;
      swRegistrationRef.current = reg;

      // Hozir waiting worker bor → update mavjud
      if (reg.waiting) {
        setHasUpdate(true);
        return;
      }

      // Yangi worker o'rnatilayotganda
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            setHasUpdate(true);
          }
        });
      });
    });

    // SW dan SKIP_WAITING xabari
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });
  }, []);

  // ── Online/Offline ────────────────────────────────────────────────────────
  useEffect(() => {
    const onOnline  = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener('online',  onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      window.removeEventListener('online',  onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────────
  const promptInstall = useCallback(async (): Promise<'accepted' | 'dismissed' | 'unavailable'> => {
    if (!deferredRef.current) return 'unavailable';
    try {
      await deferredRef.current.prompt();
      const { outcome } = await deferredRef.current.userChoice;
      deferredRef.current = null;
      setCanInstall(false);
      if (outcome === 'accepted') {
        localStorage.setItem(DISMISS_KEY, String(Date.now()));
      }
      return outcome;
    } catch {
      return 'unavailable';
    }
  }, []);

  const dismissInstall = useCallback(() => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setCanInstall(false);
    deferredRef.current = null;
  }, []);

  const updateApp = useCallback(() => {
    const reg = swRegistrationRef.current;
    if (reg?.waiting) {
      reg.waiting.postMessage({ type: 'SKIP_WAITING' });
    } else {
      window.location.reload();
    }
  }, []);

  const dismissIOSGuide = useCallback(() => {
    sessionStorage.setItem('tv-ios-guide-dismissed', '1');
    setShowIOSGuide(false);
  }, []);

  return {
    canInstall,
    promptInstall,
    dismissInstall,
    hasUpdate,
    updateApp,
    isOnline,
    isInstalled,
    isIOS,
    showIOSGuide,
    dismissIOSGuide,
  };
}