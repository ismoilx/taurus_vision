/**
 * Taurus Vision — Main Application
 * Oq/kulrang minimal tema, auth routing bilan
 */

import { BrowserRouter as Router, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { LayoutDashboard, Cpu, Video, Camera, Bell, Mail, Users, FileText, Stethoscope, LogOut, ChevronDown, BarChart2 } from 'lucide-react';
import { useState } from 'react';

import { AuthProvider, useAuth } from './context/AuthContext';

import LoginPage       from './pages/LoginPage';
import DashboardPage   from './pages/DashboardPage';
import AnimalsPage     from './pages/AnimalsPage';
import AnimalDetailPage from './pages/AnimalDetailPage';
import LiveFeedPage    from './pages/LiveFeedPage';
import CamerasPage     from './pages/CamerasPage';
import AlertsPage          from './pages/AlertsPage';
import NotificationsPage   from './pages/NotificationsPage';
import UsersPage           from './pages/UsersPage';
import ReportsPage         from './pages/ReportsPage';
import HealthPage          from './pages/HealthPage';
import AnalyticsPage   from './pages/AnalyticsPage';

import './App.css';

// ─── Protected / Public routes ────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return (
    <div style={{
      minHeight:'100vh', display:'grid', placeItems:'center', background:'#F7F8FA',
    }}>
      <div style={{
        width:28,height:28,
        border:'2px solid #E4E7ED',
        borderTopColor:'#1E3EB4',
        borderRadius:'50%',
        animation:'spin .65s linear infinite',
      }}/>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  return isAuthenticated ? <Navigate to="/" replace /> : <>{children}</>;
}

// ─── User Menu ────────────────────────────────────────────────────────────────

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen]  = useState(false);
  if (!user) return null;

  const roleLabel: Record<string,string> = {
    admin:'Admin', manager:'Menejer', viewer:'Kuzatuvchi',
  };

  return (
    <div style={{ position:'relative' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display:'flex', alignItems:'center', gap:8,
          padding:'5px 10px 5px 6px',
          borderRadius:8,
          background: open ? 'rgba(30,62,180,0.06)' : 'transparent',
          border:`1px solid ${open ? 'rgba(30,62,180,0.18)' : '#E4E7ED'}`,
          cursor:'pointer', transition:'all .15s',
        }}
      >
        {/* Avatar */}
        <div style={{
          width:28, height:28, borderRadius:6,
          background:'#1E3EB4',
          display:'grid', placeItems:'center',
          fontSize:12, fontWeight:700, color:'#fff',
          fontFamily:'Outfit,sans-serif',
          flexShrink:0,
        }}>
          {(user.full_name || user.username).charAt(0).toUpperCase()}
        </div>
        <div style={{ textAlign:'left' }}>
          <div style={{ fontSize:13, fontWeight:600, color:'#0D1117', lineHeight:1.2 }}>
            {user.full_name || user.username}
          </div>
          <div style={{
            fontSize:10, fontWeight:500,
            color:'#1E3EB4', letterSpacing:'0.06em', textTransform:'uppercase',
            fontFamily:"'JetBrains Mono',monospace",
          }}>
            {roleLabel[user.role] || user.role}
          </div>
        </div>
        <ChevronDown size={13} color="#9CA3AF"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition:'transform .2s' }}
        />
      </button>

      {open && (
        <>
          <div style={{ position:'fixed', inset:0, zIndex:40 }} onClick={() => setOpen(false)} />
          <div style={{
            position:'absolute', top:'calc(100% + 6px)', right:0,
            minWidth:200,
            background:'#fff',
            border:'1px solid #E4E7ED',
            borderRadius:10,
            boxShadow:'0 8px 32px rgba(0,0,0,0.1)',
            zIndex:50, overflow:'hidden',
            animation:'dropIn .15s ease',
          }}>
            <style>{`@keyframes dropIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}`}</style>
            <div style={{ padding:'12px 14px', borderBottom:'1px solid #F3F4F6' }}>
              <div style={{ fontSize:12, color:'#6B7280' }}>{user.email}</div>
            </div>
            <button
              onClick={async () => { setOpen(false); await logout(); }}
              style={{
                width:'100%', padding:'10px 14px',
                display:'flex', alignItems:'center', gap:8,
                background:'none', border:'none', cursor:'pointer',
                fontSize:13, color:'#6B7280',
                fontFamily:'Outfit,sans-serif',
                transition:'background .1s, color .1s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = '#FEF2F2';
                e.currentTarget.style.color = '#DC2626';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'none';
                e.currentTarget.style.color = '#6B7280';
              }}
            >
              <LogOut size={14} />
              Chiqish
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Layout ───────────────────────────────────────────────────────────────────

const navItems = [
  { to:'/',        icon:LayoutDashboard, label:'Dashboard',  end:true },
  { to:'/animals',   icon:Cpu,            label:'Jonivorlar'           },
  { to:'/analytics', icon:BarChart2,      label:'Analitika'            },
  { to:'/live',      icon:Video,          label:'Live Feed'            },
  { to:'/cameras',   icon:Camera,         label:'Kameralar'            },
  { to:'/alerts',        icon:Bell,   label:'Alertlar'             },
  { to:'/notifications', icon:Mail,   label:'Bildirishnomalar'      },
  { to:'/users',         icon:Users,       label:'Foydalanuvchilar'   },
  { to:'/reports',       icon:FileText,    label:'Hisobotlar'         },
  { to:'/health',        icon:Stethoscope, label:'Veterinariya'       },
];

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight:'100vh', background:'#F7F8FA' }}>

      {/* Nav */}
      <nav style={{
        background:'#fff',
        borderBottom:'1px solid #E4E7ED',
        position:'sticky', top:0, zIndex:50,
        boxShadow:'0 1px 3px rgba(0,0,0,0.04)',
      }}>
        <div style={{
          maxWidth:1280, margin:'0 auto',
          padding:'0 24px',
          display:'flex', alignItems:'center', justifyContent:'space-between',
          height:56,
        }}>
          {/* Logo */}
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{
              width:32, height:32,
              background:'#1E3EB4',
              borderRadius:7,
              display:'grid', placeItems:'center',
            }}>
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
                <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
                <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <div style={{
                fontFamily:"'JetBrains Mono',monospace",
                fontSize:12, fontWeight:500,
                letterSpacing:'0.1em',
                color:'#0D1117',
                textTransform:'uppercase',
              }}>
                Taurus <span style={{ color:'#1E3EB4' }}>Vision</span>
              </div>
              <div style={{ fontSize:10, color:'#9CA3AF', letterSpacing:'0.04em' }}>
                AI Farm Monitoring
              </div>
            </div>
          </div>

          {/* Nav items */}
          <div style={{ display:'flex', alignItems:'center', gap:2 }}>
            {navItems.map(({ to, icon: Icon, label, end }) => (
              <NavLink
                key={to} to={to} end={end}
                style={({ isActive }) => ({
                  display:'flex', alignItems:'center', gap:6,
                  padding:'6px 12px',
                  borderRadius:7,
                  fontSize:13, fontWeight:500,
                  fontFamily:'Outfit,sans-serif',
                  color: isActive ? '#1E3EB4' : '#6B7280',
                  background: isActive ? 'rgba(30,62,180,0.07)' : 'transparent',
                  textDecoration:'none',
                  transition:'all .15s',
                })}
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </div>

          {/* User */}
          <UserMenu />
        </div>
      </nav>

      <main style={{ fontFamily:'Outfit,sans-serif' }}>{children}</main>

      {/* Mono font load */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');
        a { text-decoration: none; }
        nav a:hover:not([aria-current="page"]) { color: #374151 !important; background: rgba(0,0,0,0.04) !important; }
      `}</style>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/"            element={<DashboardPage />} />
                  <Route path="/animals"     element={<AnimalsPage />} />
                  <Route path="/animals/:id" element={<AnimalDetailPage />} />
                  <Route path="/analytics"  element={<AnalyticsPage />} />
                  <Route path="/live"        element={<LiveFeedPage />} />
                  <Route path="/cameras"     element={<CamerasPage />} />
                  <Route path="/alerts"          element={<AlertsPage />} />
                  <Route path="/notifications"    element={<NotificationsPage />} />
                  <Route path="/users"            element={<UsersPage />} />
                  <Route path="/reports"          element={<ReportsPage />} />
                  <Route path="/health"           element={<HealthPage />} />
                  <Route path="*"            element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }/>
        </Routes>
      </Router>
    </AuthProvider>
  );
}