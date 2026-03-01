/**
 * Taurus Vision — App Shell
 *
 * NAV ARXITEKTURASI:
 *   Desktop (≥768px): Top nav — icon ustida, label ostida, 4 guruh, separator
 *   Mobil  (<768px):  Bottom nav — 5 ta asosiy + "Ko'proq" drawer
 *
 * GURUHLAR:
 *   1. Dashboard
 *   2. Jonivorlar · Xatti-harakat · ADI Monitor · Bashorat
 *   3. Analitika · Live · Hisobotlar · Veterinariya
 *   4. Bildirishnomalar · Kameralar · Foydalanuvchilar
 */

import {
  BrowserRouter as Router,
  Routes, Route, NavLink, Navigate, useLocation,
} from 'react-router-dom';
import {
  LayoutDashboard, Activity, TrendingUp, Brain,
  BarChart2, Video, FileText, Stethoscope,
  Bell, Camera, Users,
  LogOut, ChevronDown, MoreHorizontal, X,
} from 'lucide-react';
import { useState, lazy, Suspense, useEffect } from 'react';

import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { SystemLoadingScreen } from './components/SystemLoadingScreen';
import './App.css';

// ─── Cow Icon ────────────────────────────────────────────────────────────────
function CowIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3c-.5 0-1 .4-1.4.8L4 6h-.5C2.7 6 2 6.7 2 7.5S2.7 9 3.5 9H4v4c0 2.8 2.2 5 5 5h6c2.8 0 5-2.2 5-5V9h.5c.8 0 1.5-.7 1.5-1.5S21.3 6 20.5 6H20l-1.6-2.2C18 3.4 17.5 3 17 3c-.8 0-1.3.7-1.5 1.3L15 6H9L8.5 4.3C8.3 3.7 7.8 3 7 3z"/>
      <path d="M9 14h.01M15 14h.01"/>
      <path d="M9 18v3M15 18v3"/>
    </svg>
  );
}


// ─── Live Clock ───────────────────────────────────────────────────────────────
function LiveClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');
  const ss = String(time.getSeconds()).padStart(2, '0');

  const days = ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'];
  const months = ['Yan','Fev','Mar','Apr','May','Iyn','Iyl','Avg','Sen','Okt','Noy','Dek'];
  const dayName = days[time.getDay()];
  const date = `${dayName}, ${time.getDate()} ${months[time.getMonth()]}`;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
      paddingRight: 12, borderRight: '1px solid var(--border)',
      marginRight: 12, flexShrink: 0,
    }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 15, fontWeight: 600, letterSpacing: '0.04em',
        color: 'var(--text-primary)', lineHeight: 1,
      }}>
        {hh}<span style={{ opacity: 0.4, animation: 'tv-blink 1s step-end infinite' }}>:</span>{mm}<span style={{ opacity: 0.4, animation: 'tv-blink 1s step-end infinite' }}>:</span>{ss}
      </div>
      <div style={{
        fontSize: 9, color: 'var(--text-muted)', marginTop: 3,
        fontFamily: "'Outfit', sans-serif", letterSpacing: '0.04em',
      }}>
        {date}
      </div>
    </div>
  );
}

// ─── Lazy pages ───────────────────────────────────────────────────────────────

const LoginPage         = lazy(() => import('./pages/LoginPage'));
const DashboardPage     = lazy(() => import('./pages/DashboardPage'));
const AnimalsPage       = lazy(() => import('./pages/AnimalsPage'));
const AnimalDetailPage  = lazy(() => import('./pages/AnimalDetailPage'));
const LiveFeedPage      = lazy(() => import('./pages/LiveFeedPage'));
const CamerasPage       = lazy(() => import('./pages/CamerasPage'));
const AlertsPage        = lazy(() => import('./pages/AlertsPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const UsersPage         = lazy(() => import('./pages/UsersPage'));
const ReportsPage       = lazy(() => import('./pages/ReportsPage'));
const HealthPage        = lazy(() => import('./pages/HealthPage'));
const AnalyticsPage     = lazy(() => import('./pages/AnalyticsPage'));
const BehaviorPage      = lazy(() => import('./pages/BehaviorPage'));
const ADIMonitoringPage = lazy(() => import('./pages/ADIMonitoringPage'));
const PredictionsPage   = lazy(() => import('./pages/PredictionsPage'));

// ─── Spinner ──────────────────────────────────────────────────────────────────

function Spinner({ full = false }: { full?: boolean }) {
  return (
    <div style={{
      minHeight: full ? '100vh' : 'calc(100vh - 64px)',
      display: 'grid', placeItems: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        width: 26, height: 26,
        border: '2px solid var(--border)',
        borderTopColor: '#1E3EB4',
        borderRadius: '50%',
        animation: 'tv-spin .65s linear infinite',
      }} />
    </div>
  );
}

// ─── Auth guards ──────────────────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <Spinner full />;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  return isAuthenticated ? <Navigate to="/" replace /> : <>{children}</>;
}

// =============================================================================
// NAV CONFIG
// =============================================================================

type NavItem = {
  to:      string;
  icon:    React.ElementType;
  label:   string;
  end?:    boolean;
  /** Extra paths that count as "active" for this item */
  also?:   string[];
};

// Guruh 1
const GROUP1: NavItem[] = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard',     end: true },
];

// Guruh 2 — Jonivorlar ekotizimi
const GROUP2: NavItem[] = [
  { to: '/animals',   icon: CowIcon,            label: 'Jonivorlar',    also: ['/animals/'] },
  { to: '/behavior',  icon: Activity,        label: 'Xatti-harakat' },
  { to: '/adi',       icon: TrendingUp,      label: 'ADI Monitor'   },
  { to: '/predictions',icon: Brain,          label: 'Bashorat'      },
];

// Guruh 3 — Monitoring
const GROUP3: NavItem[] = [
  { to: '/analytics', icon: BarChart2,       label: 'Analitika'     },
  { to: '/live',      icon: Video,           label: 'Live'          },
  { to: '/reports',   icon: FileText,        label: 'Hisobotlar'    },
  { to: '/health',    icon: Stethoscope,     label: 'Veterinariya'  },
];

// Guruh 4 — Boshqaruv
const GROUP4: NavItem[] = [
  {
    to: '/alerts',    icon: Bell,            label: 'Bildirishnomalar',
    also: ['/notifications'],
  },
  { to: '/cameras',   icon: Camera,          label: 'Kameralar'     },
  { to: '/users',     icon: Users,           label: 'Foydalanuvchilar' },
];

const ALL_GROUPS = [GROUP1, GROUP2, GROUP3, GROUP4];

// Bottom nav — 5 ta muhim item
const BOTTOM_MAIN: NavItem[] = [
  GROUP1[0],    // Dashboard
  GROUP2[0],    // Jonivorlar
  GROUP3[1],    // Live
  GROUP4[0],    // Bildirishnomalar
];

// Qolganlar "Ko'proq" drawer uchun
const BOTTOM_MORE: NavItem[] = [
  ...GROUP2.slice(1),
  ...GROUP3.filter(i => i.to !== '/live'),
  GROUP4[1],
  GROUP4[2],
];

// =============================================================================
// USER MENU
// =============================================================================

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen]  = useState(false);
  if (!user) return null;

  const roleLabel: Record<string, string> = {
    admin: 'Admin', manager: 'Menejer', viewer: 'Kuzatuvchi',
  };
  const initials = (user.full_name || user.username).charAt(0).toUpperCase();
  const name     = user.full_name || user.username;

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>

      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '5px 8px 5px 5px',
          borderRadius: 9,
          background: open ? 'var(--nav-active-bg)' : 'transparent',
          border: `1px solid ${open ? 'var(--nav-active-border)' : 'var(--border)'}`,
          cursor: 'pointer',
          transition: 'all .15s',
          outline: 'none',
        }}
      >
        {/* Avatar */}
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: '#1E3EB4',
          display: 'grid', placeItems: 'center',
          fontSize: 12, fontWeight: 700, color: '#fff',
          fontFamily: "'JetBrains Mono', monospace",
          flexShrink: 0,
        }}>
          {initials}
        </div>

        {/* Name + role */}
        <div style={{ textAlign: 'left', lineHeight: 1 }}>
          <div style={{
            fontSize: 12, fontWeight: 600,
            color: 'var(--text-primary)',
            maxWidth: 96, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {name}
          </div>
          <div style={{
            fontSize: 9, fontWeight: 600, marginTop: 2,
            color: '#1E3EB4', letterSpacing: '0.07em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {roleLabel[user.role] ?? user.role}
          </div>
        </div>

        <ChevronDown
          size={12}
          color="var(--text-muted)"
          style={{
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform .2s',
            flexShrink: 0,
          }}
        />
      </button>

      {/* Dropdown */}
      {open && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 40 }}
            onClick={() => setOpen(false)}
          />
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0,
            minWidth: 200,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 11,
            boxShadow: '0 8px 32px var(--shadow)',
            zIndex: 50, overflow: 'hidden',
            animation: 'tv-drop .15s ease',
          }}>
            <div style={{
              padding: '11px 14px',
              borderBottom: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{user.email}</div>
            </div>

            <button
              onClick={async () => { setOpen(false); await logout(); }}
              className="tv-menu-btn"
            >
              <LogOut size={14} />
              <span>Chiqish</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// =============================================================================
// DESKTOP NAV ITEM
// =============================================================================

function DesktopNavItem({ item }: { item: NavItem }) {
  const location = useLocation();
  const isAlsoActive = item.also?.some(path =>
    location.pathname === path || location.pathname.startsWith(path)
  ) ?? false;

  return (
    <NavLink
      to={item.to}
      end={item.end}
      style={({ isActive }) => {
        const active = isActive || isAlsoActive;
        return {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 3,
          padding: '0 10px',
          height: 64,
          position: 'relative',
          textDecoration: 'none',
          color: active ? '#1E3EB4' : 'var(--text-muted)',
          transition: 'color .15s',
          borderRadius: 0,
          minWidth: 0,
          flexShrink: 0,
        };
      }}
      className="tv-nav-item"
    >
      {({ isActive }) => {
        const active = isActive || isAlsoActive;
        const Icon = item.icon;
        return (
          <>
            {/* Bottom indicator */}
            <span
              style={{
                position: 'absolute',
                bottom: 0, left: '50%',
                transform: 'translateX(-50%)',
                width: active ? 24 : 0,
                height: 2,
                background: '#1E3EB4',
                borderRadius: '2px 2px 0 0',
                transition: 'width .2s ease',
              }}
            />
            {/* Hover bg pill */}
            <span
              className="tv-nav-hover-bg"
              style={{
                position: 'absolute',
                inset: '8px 4px',
                borderRadius: 8,
                background: active ? 'rgba(30,62,180,0.07)' : 'transparent',
                transition: 'background .15s',
              }}
            />
            <Icon
              size={16}
              style={{ position: 'relative', zIndex: 1, flexShrink: 0 }}
            />
            <span style={{
              position: 'relative', zIndex: 1,
              fontSize: 10, fontWeight: active ? 600 : 500,
              letterSpacing: '0.02em',
              fontFamily: "'Outfit', sans-serif",
              whiteSpace: 'nowrap',
              lineHeight: 1,
            }}>
              {item.label}
            </span>
          </>
        );
      }}
    </NavLink>
  );
}

// =============================================================================
// MOBILE BOTTOM NAV
// =============================================================================

function BottomNav() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  // Close drawer on route change
  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

  return (
    <>
      {/* Bottom bar */}
      <nav style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        height: 60,
        background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'stretch',
        zIndex: 100,
        boxShadow: '0 -2px 16px var(--shadow)',
      }}>
        {BOTTOM_MAIN.map(item => {
          const isAlso = item.also?.some(p =>
            location.pathname === p || location.pathname.startsWith(p)
          ) ?? false;
          const Icon = item.icon;

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={({ isActive }) => {
                const active = isActive || isAlso;
                return {
                  flex: 1,
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  gap: 3,
                  textDecoration: 'none',
                  color: active ? '#1E3EB4' : 'var(--text-muted)',
                  transition: 'color .15s',
                  position: 'relative',
                };
              }}
            >
              {({ isActive }) => {
                const active = isActive || isAlso;
                return (
                  <>
                    {active && (
                      <span style={{
                        position: 'absolute', top: 0, left: '50%',
                        transform: 'translateX(-50%)',
                        width: 28, height: 2,
                        background: '#1E3EB4',
                        borderRadius: '0 0 2px 2px',
                      }} />
                    )}
                    <Icon size={18} />
                    <span style={{
                      fontSize: 10, fontWeight: active ? 600 : 400,
                      fontFamily: "'Outfit', sans-serif",
                    }}>
                      {item.label}
                    </span>
                  </>
                );
              }}
            </NavLink>
          );
        })}

        {/* Ko'proq */}
        <button
          onClick={() => setDrawerOpen(v => !v)}
          style={{
            flex: 1,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 3, border: 'none', background: 'none',
            color: drawerOpen ? '#1E3EB4' : 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'color .15s',
            fontFamily: "'Outfit', sans-serif",
          }}
        >
          <MoreHorizontal size={18} />
          <span style={{ fontSize: 10, fontWeight: 500 }}>Ko'proq</span>
        </button>
      </nav>

      {/* Drawer backdrop */}
      {drawerOpen && (
        <div
          onClick={() => setDrawerOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 98,
            background: 'rgba(0,0,0,0.3)',
            animation: 'tv-fade-in .2s ease',
          }}
        />
      )}

      {/* Drawer */}
      <div style={{
        position: 'fixed', left: 0, right: 0,
        bottom: drawerOpen ? 60 : -400,
        zIndex: 99,
        background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        borderRadius: '20px 20px 0 0',
        padding: '16px 16px 8px',
        transition: 'bottom .3s cubic-bezier(.4,0,.2,1)',
        boxShadow: '0 -4px 32px var(--shadow)',
      }}>
        {/* Handle + close */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ width: 32, height: 3, background: 'var(--border)', borderRadius: 4 }} />
          <button
            onClick={() => setDrawerOpen(false)}
            style={{
              width: 28, height: 28, borderRadius: 8,
              background: 'var(--border)', border: 'none',
              display: 'grid', placeItems: 'center',
              cursor: 'pointer', color: 'var(--text-muted)',
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
          paddingBottom: 8,
        }}>
          {BOTTOM_MORE.map(item => {
            const isAlso = item.also?.some(p =>
              location.pathname === p || location.pathname.startsWith(p)
            ) ?? false;
            const Icon = item.icon;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setDrawerOpen(false)}
                style={({ isActive }) => {
                  const active = isActive || isAlso;
                  return {
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    gap: 6,
                    padding: '12px 8px',
                    borderRadius: 12,
                    textDecoration: 'none',
                    background: active ? 'rgba(30,62,180,0.07)' : 'var(--bg)',
                    color: active ? '#1E3EB4' : 'var(--text-secondary)',
                    border: `1px solid ${active ? 'rgba(30,62,180,0.15)' : 'var(--border)'}`,
                    transition: 'all .15s',
                  };
                }}
              >
                <Icon size={18} />
                <span style={{
                  fontSize: 10, fontWeight: 500, textAlign: 'center',
                  fontFamily: "'Outfit', sans-serif",
                  lineHeight: 1.2,
                }}>
                  {item.label}
                </span>
              </NavLink>
            );
          })}
        </div>
      </div>
    </>
  );
}

// =============================================================================
// LAYOUT
// =============================================================================

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* ── DESKTOP NAV ── */}
      <nav
        className="tv-desktop-nav"
        style={{
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          position: 'sticky', top: 0, zIndex: 50,
          boxShadow: '0 1px 0 var(--border)',
          height: 64,
        }}
      >
        <div style={{
          maxWidth: 1440, margin: '0 auto',
          padding: '0 20px',
          display: 'flex', alignItems: 'stretch',
          justifyContent: 'space-between',
          height: '100%',
        }}>

          {/* Logo */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            flexShrink: 0, paddingRight: 16,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: '#1E3EB4',
              display: 'grid', placeItems: 'center',
              flexShrink: 0,
            }}>
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
                <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
                <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div style={{ lineHeight: 1 }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11, fontWeight: 600,
                letterSpacing: '0.1em', textTransform: 'uppercase',
                color: 'var(--text-primary)',
              }}>
                Taurus <span style={{ color: '#1E3EB4' }}>Vision</span>
              </div>
              <div style={{
                fontSize: 9, color: 'var(--text-muted)',
                letterSpacing: '0.05em', marginTop: 2,
                fontFamily: "'Outfit', sans-serif",
              }}>
                AI Farm Monitoring
              </div>
            </div>
          </div>

          {/* Nav groups — CENTER */}
          <div style={{
            display: 'flex', alignItems: 'stretch',
            flex: 1, justifyContent: 'center',
            overflow: 'hidden',
          }}>
            {ALL_GROUPS.map((group, gi) => (
              <div key={gi} style={{ display: 'flex', alignItems: 'stretch' }}>
                {/* Separator before each group except first */}
                {gi > 0 && (
                  <div style={{
                    width: 1, background: 'var(--border)',
                    margin: '18px 6px',
                    flexShrink: 0,
                  }} />
                )}
                {group.map(item => (
                  <DesktopNavItem key={item.to} item={item} />
                ))}
              </div>
            ))}
          </div>

          {/* Clock + User menu — RIGHT */}
          <div style={{
            display: 'flex', alignItems: 'center',
            flexShrink: 0, paddingLeft: 12,
          }}>
            <LiveClock />
            <UserMenu />
          </div>
        </div>
      </nav>

      {/* ── CONTENT ── */}
      <main style={{
        fontFamily: "'Outfit', sans-serif",
        paddingBottom: 'var(--bottom-nav-safe)',
      }}>
        <WebSocketProvider>
          <Suspense fallback={<Spinner />}>
            {children}
          </Suspense>
        </WebSocketProvider>
      </main>

      {/* ── MOBILE BOTTOM NAV ── */}
      <div className="tv-mobile-nav">
        <BottomNav />
      </div>

    </div>
  );
}

// =============================================================================
// APP
// =============================================================================

export default function App() {
  return (
    <SystemLoadingScreen>
    <AuthProvider>
      <Router>
        <>
          {/* CSS variables + global resets */}
          <style>{`
            /* ── Variables ── */
            :root {
              --bg:                #F7F8FA;
              --surface:           #FFFFFF;
              --border:            #E4E7ED;
              --text-primary:      #0D1117;
              --text-secondary:    #374151;
              --text-muted:        #6B7280;
              --nav-active-bg:     rgba(30,62,180,0.07);
              --nav-active-border: rgba(30,62,180,0.18);
              --shadow:            rgba(0,0,0,0.06);
              --bottom-nav-safe:   0px;
            }

            /* Dark mode — will be toggled by DashboardPage for now,
               full dark support comes in next iteration */

            /* ── Resets ── */
            *, *::before, *::after { box-sizing: border-box; }
            body { margin: 0; }
            a    { text-decoration: none; }

            /* ── Animations ── */
            @keyframes tv-spin    { to { transform: rotate(360deg); } }
            @keyframes tv-drop    {
              from { opacity: 0; transform: translateY(-6px); }
              to   { opacity: 1; transform: translateY(0);    }
            }
            @keyframes tv-fade-in { from { opacity: 0; } to { opacity: 1; } }
            @keyframes tv-blink { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }

            /* ── Desktop hover effect ── */
            .tv-nav-item:hover .tv-nav-hover-bg {
              background: rgba(0,0,0,0.04) !important;
            }
            .tv-nav-item:hover {
              color: var(--text-secondary) !important;
            }

            /* ── User menu button ── */
            .tv-menu-btn {
              width: 100%; padding: 10px 14px;
              display: flex; align-items: center; gap: 8px;
              background: none; border: none; cursor: pointer;
              font-size: 13px; color: var(--text-muted);
              font-family: 'Outfit', sans-serif;
              transition: background .12s, color .12s;
              text-align: left;
            }
            .tv-menu-btn:hover {
              background: #FEF2F2;
              color: #DC2626;
            }

            /* ── Responsive visibility ── */
            .tv-desktop-nav { display: flex !important; }
            .tv-mobile-nav  { display: none  !important; }

            @media (max-width: 767px) {
              .tv-desktop-nav { display: none  !important; }
              .tv-mobile-nav  { display: block !important; }
              :root { --bottom-nav-safe: 60px; }
            }
          `}</style>

          <Routes>
            <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
            <Route path="/*" element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/"             element={<DashboardPage />} />
                    <Route path="/animals"      element={<AnimalsPage />} />
                    <Route path="/animals/:id"  element={<AnimalDetailPage />} />
                    <Route path="/behavior"     element={<BehaviorPage />} />
                    <Route path="/adi"          element={<ADIMonitoringPage />} />
                    <Route path="/predictions"  element={<PredictionsPage />} />
                    <Route path="/analytics"    element={<AnalyticsPage />} />
                    <Route path="/live"         element={<LiveFeedPage />} />
                    <Route path="/reports"      element={<ReportsPage />} />
                    <Route path="/health"       element={<HealthPage />} />
                    <Route path="/alerts"       element={<AlertsPage />} />
                    <Route path="/notifications" element={<NotificationsPage />} />
                    <Route path="/cameras"      element={<CamerasPage />} />
                    <Route path="/users"        element={<UsersPage />} />
                    <Route path="*"             element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            } />
          </Routes>
        </>
      </Router>
    </AuthProvider>
    </SystemLoadingScreen>
  );
}