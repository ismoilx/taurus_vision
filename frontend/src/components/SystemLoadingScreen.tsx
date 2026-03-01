import { useSystemReady } from '../hooks/useSystemReady';

export function SystemLoadingScreen({ children }: { children: React.ReactNode }) {
  const { state, dots } = useSystemReady();

  if (state === 'ready') return <>{children}</>;

  const isError = state === 'error';

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#0D1117',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      zIndex: 9999, fontFamily: "'Outfit', system-ui, sans-serif",
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 14, background: '#1E3EB4',
        display: 'grid', placeItems: 'center', marginBottom: 24,
        boxShadow: '0 0 32px rgba(30,62,180,0.4)',
      }}>
        <svg width="28" height="28" viewBox="0 0 20 20" fill="none">
          <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
          <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
          <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4"
                strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 600,
        letterSpacing: '0.12em', textTransform: 'uppercase' as const,
        color: '#fff', marginBottom: 8,
      }}>
        Taurus <span style={{ color: '#3B82F6' }}>Vision</span>
      </div>

      {!isError ? (
        <>
          <div style={{ margin: '20px 0' }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              border: '3px solid rgba(59,130,246,0.2)', borderTopColor: '#3B82F6',
              animation: 'sl-spin .8s linear infinite',
            }}/>
          </div>
          <p style={{ fontSize: 14, color: '#4B5563', margin: 0 }}>
            AI model yuklanmoqda{dots}
          </p>
          <p style={{ fontSize: 12, color: '#374151', margin: '6px 0 0' }}>
            YOLOv11 tayyorlanayapti
          </p>
        </>
      ) : (
        <>
          <p style={{ fontSize: 14, color: '#EF4444', margin: '20px 0 6px', fontWeight: 600 }}>
            Backend bilan aloqa yo'q
          </p>
          <p style={{ fontSize: 12, color: '#4B5563', margin: '0 0 16px', textAlign: 'center' as const }}>
            <code>docker-compose up</code> ni tekshiring
          </p>
          <button onClick={() => window.location.reload()} style={{
            padding: '8px 20px', background: '#1E3EB4', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>
            Qayta urinish
          </button>
        </>
      )}

      <style>{`@keyframes sl-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}