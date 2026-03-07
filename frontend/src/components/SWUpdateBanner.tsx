/**
 * Taurus Vision — SWUpdateBanner
 *
 * Service Worker yangi versiyasi mavjud bo'lganda ko'rinadigan banner.
 * Sahifa yuqorida (sticky) joylashadi.
 * "Yangilash" → window.location.reload() + SKIP_WAITING
 * "Keyinroq"  → yashiriladi (session davomida)
 */

import { useState } from 'react';
import { RefreshCw, X, Zap } from 'lucide-react';
import type { PWAState } from '../hooks/usePWA';

export function SWUpdateBanner({ pwa }: { pwa: PWAState }) {
  const [dismissed, setDismissed] = useState(false);
  const [updating,  setUpdating]  = useState(false);

  if (!pwa.hasUpdate || dismissed) return null;

  async function handleUpdate() {
    setUpdating(true);
    // Qisqa animatsiya uchun kechikish
    await new Promise(r => setTimeout(r, 300));
    pwa.updateApp();
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0,
      zIndex: 9100,
      animation: 'tv-slide-down .35s cubic-bezier(.4,0,.2,1)',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #1E3EB4 0%, #3B5FD9 100%)',
        color: '#fff',
        padding: '10px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        boxShadow: '0 4px 24px rgba(30,62,180,0.4)',
        paddingTop: 'calc(10px + env(safe-area-inset-top, 0px))',
      }}>
        {/* Icon */}
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: 'rgba(255,255,255,0.15)',
          display: 'grid', placeItems: 'center', flexShrink: 0,
        }}>
          <Zap size={16} color="#fff" />
        </div>

        {/* Text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'Outfit, sans-serif' }}>
            Yangi versiya mavjud
          </div>
          <div style={{ fontSize: 11, opacity: 0.8, marginTop: 1, fontFamily: 'Outfit, sans-serif' }}>
            Eng so'nggi yangilanishlardan foydalanish uchun ilovani yangilang
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            onClick={() => setDismissed(true)}
            style={{
              width: 28, height: 28, borderRadius: 7,
              background: 'rgba(255,255,255,0.15)',
              border: 'none', display: 'grid', placeItems: 'center', cursor: 'pointer',
            }}
          >
            <X size={13} color="#fff" />
          </button>

          <button
            onClick={handleUpdate}
            disabled={updating}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px',
              background: '#fff', color: '#1E3EB4',
              border: 'none', borderRadius: 8,
              fontSize: 12, fontWeight: 800,
              cursor: updating ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif',
              opacity: updating ? 0.8 : 1,
              transition: 'opacity .15s',
            }}
          >
            <RefreshCw
              size={12}
              style={{ animation: updating ? 'tv-spin .65s linear infinite' : 'none' }}
            />
            {updating ? 'Yangilanmoqda...' : 'Yangilash'}
          </button>
        </div>
      </div>
    </div>
  );
}