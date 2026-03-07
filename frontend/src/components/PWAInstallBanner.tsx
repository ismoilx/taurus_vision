/**
 * Taurus Vision — PWAInstallBanner
 *
 * Ilovani qurilmaga o'rnatish taklifi.
 * - Android/Desktop: native "Add to Home Screen" dialog
 * - iOS Safari: qo'lda yo'riqnoma (Share → Add to Home Screen)
 * - O'rnatilgan bo'lsa: ko'rsatilmaydi
 *
 * JOYLASHUV: sahifa pastida floating banner
 * ANIMATSIYA: pastdan chiqadi, dismiss bilan pastga ketadi
 */

import { useState } from 'react';
import { Download, X, Share, Plus, Smartphone, Zap, Wifi } from 'lucide-react';
import type { PWAState } from '../hooks/usePWA';

// =============================================================================
// iOS GUIDE MODAL
// =============================================================================

function IOSGuideModal({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.55)',
      display: 'flex', alignItems: 'flex-end',
      zIndex: 9000,
      animation: 'tv-fade-in .2s ease',
    }}
      onClick={onDismiss}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%',
          background: '#fff',
          borderRadius: '20px 20px 0 0',
          padding: '20px 24px calc(20px + env(safe-area-inset-bottom, 0px))',
          boxShadow: '0 -8px 40px rgba(0,0,0,0.15)',
          animation: 'tv-slide-up .3s cubic-bezier(.4,0,.2,1)',
        }}
      >
        {/* Handle */}
        <div style={{
          width: 40, height: 4, borderRadius: 4,
          background: '#D1D5DB',
          margin: '0 auto 20px',
        }} />

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 12,
            background: '#1E3EB4',
            display: 'grid', placeItems: 'center', flexShrink: 0,
          }}>
            <svg width="28" height="28" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
              <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
              <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 17, fontWeight: 800, color: '#0D1117', fontFamily: 'Outfit, sans-serif' }}>
              Taurus Vision
            </div>
            <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2, fontFamily: 'Outfit, sans-serif' }}>
              Ilovani telefoningizga o'rnating
            </div>
          </div>
        </div>

        {/* Afzalliklar */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
          gap: 10, marginBottom: 24,
        }}>
          {[
            { icon: Zap,       label: 'Tezkor',    desc: 'App tezligida' },
            { icon: Wifi,      label: 'Offline',   desc: 'Internetsiz ham' },
            { icon: Smartphone, label: 'Native',   desc: 'Telefon kabi' },
          ].map(({ icon: Icon, label, desc }) => (
            <div key={label} style={{
              background: '#F7F8FA', borderRadius: 12, padding: '12px 8px',
              textAlign: 'center', border: '1px solid #E4E7ED',
            }}>
              <Icon size={20} color="#1E3EB4" style={{ margin: '0 auto 6px' }} />
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0D1117', fontFamily: 'Outfit, sans-serif' }}>{label}</div>
              <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2, fontFamily: 'Outfit, sans-serif' }}>{desc}</div>
            </div>
          ))}
        </div>

        {/* Qadamlar */}
        <div style={{
          background: '#F7F8FA', borderRadius: 14, padding: 16, marginBottom: 20,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', marginBottom: 12,
            textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: "'JetBrains Mono', monospace" }}>
            O'rnatish qadamlari
          </div>

          {[
            {
              num: '1',
              text: 'Safari pastidagi',
              highlight: 'Share',
              icon: <Share size={14} color="#007AFF" />,
              after: 'tugmasini bosing',
            },
            {
              num: '2',
              text: 'Pastga suring va',
              highlight: 'Add to Home Screen',
              icon: <Plus size={14} color="#007AFF" />,
              after: 'ni tanlang',
            },
            {
              num: '3',
              text: 'Yuqori o\'ngda',
              highlight: 'Add',
              icon: null,
              after: 'tugmasini bosing',
            },
          ].map(({ num, text, highlight, icon, after }) => (
            <div key={num} style={{
              display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10,
            }}>
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                background: '#1E3EB4', color: '#fff',
                display: 'grid', placeItems: 'center',
                fontSize: 13, fontWeight: 700, flexShrink: 0,
                fontFamily: 'Outfit, sans-serif',
              }}>{num}</div>
              <div style={{ fontSize: 13, color: '#374151', fontFamily: 'Outfit, sans-serif' }}>
                {text}{' '}
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 3,
                  background: '#E8F0FE', color: '#1E3EB4',
                  padding: '1px 7px', borderRadius: 6,
                  fontWeight: 700, fontSize: 12,
                }}>
                  {icon} {highlight}
                </span>
                {' '}{after}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={onDismiss}
          style={{
            width: '100%', padding: '13px',
            background: '#F3F4F6', color: '#374151',
            border: 'none', borderRadius: 12,
            fontSize: 14, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}
        >
          Keyinroq
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// INSTALL BANNER (Android / Desktop)
// =============================================================================

function InstallBanner({ pwa }: { pwa: PWAState }) {
  const [installing, setInstalling] = useState(false);
  const [installed,  setInstalled]  = useState(false);
  const [dismissed,  setDismissed]  = useState(false);

  if (dismissed || installed) return null;

  async function handleInstall() {
    setInstalling(true);
    const result = await pwa.promptInstall();
    setInstalling(false);
    if (result === 'accepted') {
      setInstalled(true);
    }
  }

  function handleDismiss() {
    pwa.dismissInstall();
    setDismissed(true);
  }

  return (
    <div style={{
      position: 'fixed',
      bottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)',
      left: 16, right: 16,
      zIndex: 8000,
      animation: 'tv-slide-up .35s cubic-bezier(.4,0,.2,1)',
    }}>
      <div style={{
        background: '#fff',
        border: '1px solid #E4E7ED',
        borderRadius: 18,
        boxShadow: '0 8px 40px rgba(0,0,0,0.14)',
        padding: '16px 18px',
        display: 'flex', alignItems: 'center', gap: 14,
        maxWidth: 500, margin: '0 auto',
      }}>
        {/* App icon */}
        <div style={{
          width: 48, height: 48, borderRadius: 12,
          background: '#1E3EB4', flexShrink: 0,
          display: 'grid', placeItems: 'center',
          boxShadow: '0 2px 8px rgba(30,62,180,0.3)',
        }}>
          <svg width="26" height="26" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
            <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
            <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>

        {/* Text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 14, fontWeight: 700, color: '#0D1117',
            fontFamily: 'Outfit, sans-serif',
          }}>
            Taurus Vision
          </div>
          <div style={{
            fontSize: 12, color: '#6B7280', marginTop: 2,
            fontFamily: 'Outfit, sans-serif',
          }}>
            Qurilmangizga o'rnating — tezroq va oflayn ishlaydi
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            onClick={handleDismiss}
            style={{
              width: 32, height: 32, borderRadius: 9,
              background: '#F3F4F6', border: 'none',
              display: 'grid', placeItems: 'center', cursor: 'pointer',
            }}
          >
            <X size={14} color="#9CA3AF" />
          </button>
          <button
            onClick={handleInstall}
            disabled={installing}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px',
              background: installing ? '#9CA3AF' : '#1E3EB4',
              color: '#fff', border: 'none', borderRadius: 9,
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif',
              transition: 'background .15s',
            }}
          >
            {installing ? (
              <div style={{
                width: 13, height: 13, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.4)',
                borderTopColor: '#fff',
                animation: 'tv-spin .65s linear infinite',
              }} />
            ) : <Download size={13} />}
            {installing ? 'Yuklanmoqda...' : "O'rnatish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN EXPORT
// =============================================================================

export function PWAInstallBanner({ pwa }: { pwa: PWAState }) {
  // O'rnatilgan bo'lsa — hech narsa ko'rsatilmaydi
  if (pwa.isInstalled) return null;

  // iOS — maxsus yo'riqnoma
  if (pwa.showIOSGuide) {
    return <IOSGuideModal onDismiss={pwa.dismissIOSGuide} />;
  }

  // Android / Desktop — native prompt
  if (pwa.canInstall) {
    return <InstallBanner pwa={pwa} />;
  }

  return null;
}