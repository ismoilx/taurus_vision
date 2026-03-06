/**
 * Taurus Vision — App Shell
 *
 * NAV: Logo | Dashboard | [Jonivorlar▾] [Monitoring▾] [Boshqaruv▾] | Soat | User
 *
 * Muammo (oldin): 14 item bir qatorda → overflow hidden → yarmi yo'qoldi
 * Yechim: 3 ta dropdown guruh → nav hech qachon to'lmaydi
 */

import {
  BrowserRouter as Router, Routes, Route,
  NavLink, Navigate, useLocation, useNavigate,
} from 'react-router-dom';
import {
  LayoutDashboard, Activity, TrendingUp, Brain,
  BarChart2, Video, FileText, Stethoscope,
  Bell, Camera, Users, Cpu, ClipboardList, Wheat,
  LogOut, ChevronDown, MoreHorizontal, X, Radio, Coins, Shield, Building2, Scale,
} from 'lucide-react';
import { useState, lazy, Suspense, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { SystemLoadingScreen } from './components/SystemLoadingScreen';
import { apiFetch } from './utils/apiFetch';
import './App.css';

// ─── Cow Icon ────────────────────────────────────────────────────────────────
function CowIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3c-.5 0-1 .4-1.4.8L4 6h-.5C2.7 6 2 6.7 2 7.5S2.7 9 3.5 9H4v4c0 2.8 2.2 5 5 5h6c2.8 0 5-2.2 5-5V9h.5c.8 0 1.5-.7 1.5-1.5S21.3 6 20.5 6H20l-1.6-2.2C18 3.4 17.5 3 17 3c-.8 0-1.3.7-1.5 1.3L15 6H9L8.5 4.3C8.3 3.7 7.8 3 7 3z"/>
      <path d="M9 14h.01M15 14h.01"/><path d="M9 18v3M15 18v3"/>
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
  const pad = (n: number) => String(n).padStart(2, '0');
  const days   = ['Yak','Dush','Sesh','Chor','Pay','Jum','Shan'];
  const months = ['Yan','Fev','Mar','Apr','May','Iyn','Iyl','Avg','Sen','Okt','Noy','Dek'];
  return (
    <div style={{
      display:'flex', flexDirection:'column', alignItems:'flex-end',
      paddingRight:10, borderRight:'1px solid var(--border)', marginRight:10, flexShrink:0,
    }}>
      <div style={{
        fontFamily:"'JetBrains Mono',monospace", fontSize:13, fontWeight:600,
        letterSpacing:'0.04em', color:'var(--text-primary)', lineHeight:1,
      }}>
        {pad(time.getHours())}
        <span style={{opacity:0.4,animation:'tv-blink 1s step-end infinite'}}>:</span>
        {pad(time.getMinutes())}
        <span style={{opacity:0.4,animation:'tv-blink 1s step-end infinite'}}>:</span>
        {pad(time.getSeconds())}
      </div>
      <div style={{fontSize:9,color:'var(--text-muted)',marginTop:2,fontFamily:"'Outfit',sans-serif"}}>
        {days[time.getDay()]}, {time.getDate()} {months[time.getMonth()]}
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
const TrainingPage      = lazy(() => import('./pages/TrainingPage'));
const TasksPage         = lazy(() => import('./pages/TasksPage'));
const FeedPage          = lazy(() => import('./pages/FeedPage'));
const SensorPage        = lazy(() => import('./pages/SensorPage'));
const FinancePage       = lazy(() => import('./pages/FinancePage'));
const IntegrationsPage  = lazy(() => import('./pages/IntegrationsPage'));
const AuditLogPage      = lazy(() => import('./pages/AuditLogPage'));
const FarmsPage         = lazy(() => import('./pages/FarmsPage'));
const ScalePage         = lazy(() => import('./pages/ScalePage'));

// ─── Spinner ──────────────────────────────────────────────────────────────────
function Spinner({ full = false }: { full?: boolean }) {
  return (
    <div style={{minHeight:full?'100vh':'calc(100vh - 56px)',display:'grid',placeItems:'center',background:'var(--bg)'}}>
      <div style={{width:24,height:24,border:'2px solid var(--border)',borderTopColor:'#1E3EB4',borderRadius:'50%',animation:'tv-spin .65s linear infinite'}}/>
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
type NavItem = { to:string; icon:React.ElementType; label:string; end?:boolean; also?:string[] };
type NavGroup = { label:string; icon:React.ElementType; items:NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label:'Jonivorlar', icon:CowIcon,
    items:[
      { to:'/animals',     icon:CowIcon,      label:'Jonivorlar',    also:['/animals/'] },
      { to:'/behavior',    icon:Activity,      label:'Xatti-harakat' },
      { to:'/adi',         icon:TrendingUp,    label:'ADI Monitor'   },
      { to:'/predictions', icon:Brain,         label:'Bashorat'      },
    ],
  },
  {
    label:'Monitoring', icon:BarChart2,
    items:[
      { to:'/analytics', icon:BarChart2,   label:'Analitika'    },
      { to:'/live',      icon:Video,       label:'Live Feed'    },
      { to:'/reports',   icon:FileText,    label:'Hisobotlar'   },
      { to:'/health',    icon:Stethoscope, label:'Veterinariya' },
      { to:'/sensors',   icon:Radio,       label:'IoT Sensorlar'},
      { to:'/scales',    icon:Scale,       label:'Tarozlar' },
    ],
  },
  {
    label:'Boshqaruv', icon:Bell,
    items:[
      { to:'/alerts',       icon:Bell,          label:'Alertlar',           also:['/notifications'] },
      { to:'/feed',         icon:Wheat,         label:'Ozuqa'               },
      { to:'/finance',      icon:Coins,         label:'Moliya'              },
      { to:'/integrations', icon:Radio,         label:'Integratsiyalar'     },
      { to:'/tasks',        icon:ClipboardList, label:'Vazifalar'           },
      { to:'/cameras',      icon:Camera,        label:'Kameralar'           },
      { to:'/farms',        icon:Building2,     label:'Fermalar'            },
      { to:'/users',        icon:Users,         label:'Foydalanuvchilar'    },
      { to:'/audit-log',    icon:Shield,         label:'Audit Log'          },
      { to:'/training',     icon:Cpu,           label:'AI Training'         },
    ],
  },
];

const ALL_ITEMS: NavItem[] = NAV_GROUPS.flatMap(g => g.items);
const BOTTOM_MAIN: NavItem[] = [
  { to:'/', icon:LayoutDashboard, label:'Dashboard', end:true },
  NAV_GROUPS[0].items[0],
  NAV_GROUPS[1].items[1],
  NAV_GROUPS[2].items[0],
];

// =============================================================================
// ALERT BELL — real-time kritik alertlar badge
// =============================================================================
interface AlertStats {
  total_open:    number;
  critical_open: number;
  high_open:     number;
}

function AlertBell() {
  const navigate  = useNavigate();
  const { user }  = useAuth();                         // faqat login bo'lganda so'rov

  const { data } = useQuery<AlertStats>({
    queryKey:        ['alert-stats-nav'],
    queryFn:         () => apiFetch<AlertStats>('/api/v1/alerts/stats'),
    enabled:         !!user,                           // login bo'lmasa so'rov yo'q
    refetchInterval: 60_000,                           // 30s → 60s (yuk kamayadi)
    staleTime:       45_000,
    retry:           false,                            // xato bo'lsa qotib qolmasin
    gcTime:          60_000,
  });

  const critical = data?.critical_open ?? 0;
  const total    = data?.total_open    ?? 0;
  const hasCrit  = critical > 0;
  const hasAny   = total > 0;

  const badgeCount = hasCrit ? critical : total > 0 ? total : 0;
  const badgeColor = hasCrit ? '#DC2626' : '#D97706';

  return (
    <button
      onClick={() => navigate('/alerts')}
      title={hasCrit ? `${critical} ta kritik alert!` : total > 0 ? `${total} ta ochiq alert` : "Alertlar yo'q"}
      style={{
        position: 'relative',
        display:  'flex', alignItems: 'center', justifyContent: 'center',
        width: 34, height: 34, borderRadius: 8,
        background: hasAny ? (hasCrit ? 'rgba(220,38,38,0.08)' : 'rgba(217,119,6,0.08)') : 'transparent',
        border: hasAny
          ? `1px solid ${hasCrit ? 'rgba(220,38,38,0.2)' : 'rgba(217,119,6,0.2)'}`
          : '1px solid var(--border)',
        cursor:  'pointer',
        outline: 'none',
        flexShrink: 0,
        transition: 'all .2s',
        animation: hasCrit ? 'tv-bell-shake 2.5s ease infinite' : 'none',
      }}
    >
      <Bell size={15} color={hasAny ? (hasCrit ? '#DC2626' : '#D97706') : 'var(--text-muted)'} />
      {badgeCount > 0 && (
        <span style={{
          position:   'absolute',
          top: -5, right: -5,
          minWidth:   16, height: 16,
          borderRadius: 8,
          background: badgeColor,
          color:      '#fff',
          fontSize:   9, fontWeight: 800,
          display:    'flex', alignItems: 'center', justifyContent: 'center',
          padding:    '0 3px',
          border:     '1.5px solid var(--surface)',
          fontFamily: "'JetBrains Mono', monospace",
          lineHeight: 1,
        }}>
          {badgeCount > 99 ? '99+' : badgeCount}
        </span>
      )}
    </button>
  );
}

// =============================================================================
// FARM SWITCHER
// =============================================================================

const FARM_STORAGE_KEY = 'tv_current_farm';

function FarmSwitcher() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [currentFarmId, setCurrentFarmId] = useState<number | null>(() => {
    try { const r = localStorage.getItem(FARM_STORAGE_KEY); return r ? parseInt(r) : null; } catch { return null; }
  });
  const [currentFarmName, setCurrentFarmName] = useState<string>(() => {
    try { return localStorage.getItem('tv_current_farm_name') ?? 'Ferma'; } catch { return 'Ferma'; }
  });

  const { data } = useQuery({
    queryKey: ['farms-nav'],
    queryFn:  () => apiFetch<{ items: Array<{ id: number; name: string; is_active: boolean; animal_count: number }> }>('/api/v1/farms?limit=50&active_only=true'),
    staleTime: 30_000,
  });

  const switchMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ farm_id: number; farm_name: string }>(`/api/v1/farms/${id}/switch`, { method: 'POST' }),
    onSuccess: (res) => {
      try {
        localStorage.setItem(FARM_STORAGE_KEY, String(res.farm_id));
        localStorage.setItem('tv_current_farm_name', res.farm_name);
      } catch { /* ignore */ }
      setCurrentFarmId(res.farm_id);
      setCurrentFarmName(res.farm_name);
      setOpen(false);
    },
  });

  const farms = data?.items ?? [];
  if (!user || farms.length <= 1) return null;

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '4px 10px 4px 8px', borderRadius: 8,
          background: open ? 'rgba(30,62,180,0.07)' : 'transparent',
          border: `1px solid ${open ? 'rgba(30,62,180,0.18)' : 'var(--border)'}`,
          cursor: 'pointer', outline: 'none', transition: 'all .15s',
        }}
      >
        <Building2 size={13} color="#1E3EB4"/>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: "'Outfit',sans-serif" }}>
          {currentFarmName}
        </span>
        <ChevronDown size={11} color="var(--text-muted)" style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}/>
      </button>

      {open && (<>
        <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setOpen(false)}/>
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0,
          minWidth: 200, background: 'var(--surface)',
          border: '1px solid var(--border)', borderRadius: 11,
          boxShadow: '0 8px 32px var(--shadow)', zIndex: 200,
          overflow: 'hidden', animation: 'tv-drop .15s ease',
        }}>
          <div style={{ padding: '7px 12px', borderBottom: '1px solid var(--border)', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontFamily: "'Outfit',sans-serif" }}>
            Ferma tanlash
          </div>
          {farms.map(farm => (
            <button
              key={farm.id}
              onClick={() => switchMut.mutate(farm.id)}
              disabled={switchMut.isPending}
              style={{
                width: '100%', padding: '9px 14px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: farm.id === currentFarmId ? 'rgba(30,62,180,0.07)' : 'none',
                border: 'none', cursor: 'pointer', fontSize: 13,
                color: farm.id === currentFarmId ? '#1E3EB4' : 'var(--text-secondary)',
                fontFamily: "'Outfit',sans-serif", fontWeight: farm.id === currentFarmId ? 600 : 400,
                textAlign: 'left',
              }}
            >
              <span>{farm.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{farm.animal_count}</span>
            </button>
          ))}
          <div style={{ borderTop: '1px solid var(--border)' }}>
            <button
              onClick={() => { setOpen(false); navigate('/farms'); }}
              style={{
                width: '100%', padding: '9px 14px', display: 'flex', alignItems: 'center', gap: 6,
                background: 'none', border: 'none', cursor: 'pointer', fontSize: 12,
                color: 'var(--text-muted)', fontFamily: "'Outfit',sans-serif", textAlign: 'left',
              }}
            >
              <Building2 size={12}/> Barcha fermalarga o'tish
            </button>
          </div>
        </div>
      </>)}
    </div>
  );
}

// =============================================================================
// USER MENU
// =============================================================================
function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const roleLabel: Record<string,string> = { admin:'Admin', manager:'Menejer', viewer:'Kuzatuvchi' };
  const initials = (user.full_name || user.username).charAt(0).toUpperCase();
  return (
    <div style={{position:'relative',flexShrink:0}}>
      <button onClick={() => setOpen(v => !v)} style={{
        display:'flex', alignItems:'center', gap:6,
        padding:'4px 8px 4px 4px', borderRadius:8,
        background: open ? 'var(--nav-active-bg)' : 'transparent',
        border:`1px solid ${open ? 'var(--nav-active-border)' : 'var(--border)'}`,
        cursor:'pointer', outline:'none', transition:'all .15s',
      }}>
        <div style={{
          width:26, height:26, borderRadius:6, background:'#1E3EB4',
          display:'grid', placeItems:'center',
          fontSize:11, fontWeight:700, color:'#fff',
          fontFamily:"'JetBrains Mono',monospace", flexShrink:0,
        }}>{initials}</div>
        <div style={{textAlign:'left',lineHeight:1}}>
          <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)',maxWidth:80,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
            {user.full_name || user.username}
          </div>
          <div style={{fontSize:9,fontWeight:600,marginTop:2,color:'#1E3EB4',letterSpacing:'0.07em',textTransform:'uppercase',fontFamily:"'JetBrains Mono',monospace"}}>
            {roleLabel[user.role] ?? user.role}
          </div>
        </div>
        <ChevronDown size={11} color="var(--text-muted)"
          style={{transform:open?'rotate(180deg)':'none',transition:'transform .2s',flexShrink:0}}/>
      </button>
      {open && (<>
        <div style={{position:'fixed',inset:0,zIndex:40}} onClick={() => setOpen(false)}/>
        <div style={{
          position:'absolute', top:'calc(100% + 6px)', right:0,
          minWidth:176, background:'var(--surface)',
          border:'1px solid var(--border)', borderRadius:11,
          boxShadow:'0 8px 32px var(--shadow)', zIndex:200,
          overflow:'hidden', animation:'tv-drop .15s ease',
        }}>
          <div style={{padding:'9px 14px',borderBottom:'1px solid var(--border)'}}>
            <div style={{fontSize:10,color:'var(--text-muted)'}}>{user.email}</div>
          </div>
          <button onClick={async () => { setOpen(false); await logout(); }} className="tv-menu-btn">
            <LogOut size={13}/><span>Chiqish</span>
          </button>
        </div>
      </>)}
    </div>
  );
}

// =============================================================================
// NAV DROPDOWN — Desktop
// =============================================================================
function isItemActive(item: NavItem, pathname: string): boolean {
  if (item.end) return pathname === item.to;
  if (item.to !== '/' && pathname.startsWith(item.to)) return true;
  return item.also?.some(p => pathname === p || pathname.startsWith(p)) ?? false;
}

function NavDropdown({ group }: { group: NavGroup }) {
  const [open, setOpen] = useState(false);
  const location        = useLocation();
  const navigate        = useNavigate();
  const ref             = useRef<HTMLDivElement>(null);

  const groupActive = group.items.some(i => isItemActive(i, location.pathname));

  useEffect(() => {
    if (!open) return;
    const fn = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', fn);
    return () => document.removeEventListener('mousedown', fn);
  }, [open]);

  useEffect(() => { setOpen(false); }, [location.pathname]);

  const G = group.icon;

  return (
    <div ref={ref} style={{position:'relative',display:'flex',alignItems:'stretch'}}>
      <button
        onClick={() => setOpen(v => !v)}
        className="tv-group-btn"
        style={{
          display:'flex', alignItems:'center', gap:5,
          padding:'0 11px', height:56,
          background:'none', border:'none', cursor:'pointer',
          color: groupActive ? '#1E3EB4' : 'var(--text-muted)',
          fontFamily:"'Outfit',sans-serif",
          fontSize:13, fontWeight: groupActive ? 600 : 500,
          transition:'color .15s', position:'relative', outline:'none',
        }}
      >
        {groupActive && (
          <span style={{
            position:'absolute', bottom:0, left:'50%', transform:'translateX(-50%)',
            width:26, height:2, background:'#1E3EB4', borderRadius:'2px 2px 0 0',
          }}/>
        )}
        <G size={13}/>
        <span>{group.label}</span>
        <ChevronDown size={11} style={{transform:open?'rotate(180deg)':'none',transition:'transform .2s',opacity:0.55}}/>
      </button>

      {open && (
        <div style={{
          position:'absolute', top:'calc(100% + 2px)', left:'50%', transform:'translateX(-50%)',
          minWidth:196, background:'var(--surface)',
          border:'1px solid var(--border)', borderRadius:12,
          boxShadow:'0 8px 28px rgba(0,0,0,0.10)',
          zIndex:200, overflow:'hidden', animation:'tv-drop .14s ease',
        }}>
          <div style={{
            padding:'7px 14px 5px', fontSize:9, fontWeight:700,
            color:'var(--text-muted)', letterSpacing:'0.1em', textTransform:'uppercase',
            borderBottom:'1px solid var(--border)', fontFamily:"'JetBrains Mono',monospace",
          }}>{group.label}</div>

          {group.items.map(item => {
            const active = isItemActive(item, location.pathname);
            const Icon   = item.icon;
            return (
              <button key={item.to}
                onClick={() => { navigate(item.to); setOpen(false); }}
                className="tv-dropdown-item"
                style={{
                  width:'100%', display:'flex', alignItems:'center', gap:9,
                  padding:'9px 14px',
                  background: active ? 'rgba(30,62,180,0.06)' : 'transparent',
                  border:'none', borderLeft: active ? '2px solid #1E3EB4' : '2px solid transparent',
                  cursor:'pointer',
                  color: active ? '#1E3EB4' : 'var(--text-secondary)',
                  fontFamily:"'Outfit',sans-serif",
                  fontSize:13, fontWeight: active ? 600 : 400,
                  textAlign:'left', transition:'background .1s,color .1s',
                }}
              >
                <Icon size={14} style={{flexShrink:0, opacity: active ? 1 : 0.65}}/>
                <span>{item.label}</span>
                {active && <span style={{marginLeft:'auto',width:6,height:6,borderRadius:'50%',background:'#1E3EB4',flexShrink:0}}/>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MOBILE BOTTOM NAV
// =============================================================================
function BottomNav() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

  return (<>
    <nav style={{
      position:'fixed', bottom:0, left:0, right:0,
      height:'calc(58px + env(safe-area-inset-bottom, 0px))',
      background:'var(--surface)', borderTop:'1px solid var(--border)',
      display:'flex', alignItems:'flex-start', paddingTop: 0,
      zIndex:100, boxShadow:'0 -2px 16px var(--shadow)',
      paddingBottom:'env(safe-area-inset-bottom, 0px)',
    }}>
      {BOTTOM_MAIN.map(item => {
        const isAlso = item.also?.some(p => location.pathname === p || location.pathname.startsWith(p)) ?? false;
        const Icon = item.icon;
        return (
          <NavLink key={item.to} to={item.to} end={item.end}
            style={({ isActive }) => ({
              flex:1, display:'flex', flexDirection:'column',
              alignItems:'center', justifyContent:'center', gap:3,
              textDecoration:'none',
              color:(isActive||isAlso) ? '#1E3EB4' : 'var(--text-muted)',
              transition:'color .15s', position:'relative',
            })}>
            {({ isActive }) => {
              const active = isActive || isAlso;
              return (<>
                {active && <span style={{position:'absolute',top:0,left:'50%',transform:'translateX(-50%)',width:24,height:2,background:'#1E3EB4',borderRadius:'0 0 2px 2px'}}/>}
                <Icon size={17}/>
                <span style={{fontSize:9,fontWeight:active?600:400,fontFamily:"'Outfit',sans-serif"}}>{item.label}</span>
              </>);
            }}
          </NavLink>
        );
      })}
      <button onClick={() => setDrawerOpen(v => !v)} style={{
        flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:3,
        border:'none', background:'none',
        color:drawerOpen ? '#1E3EB4' : 'var(--text-muted)',
        cursor:'pointer', fontFamily:"'Outfit',sans-serif",
      }}>
        <MoreHorizontal size={17}/>
        <span style={{fontSize:9,fontWeight:500}}>Ko'proq</span>
      </button>
    </nav>

    {drawerOpen && <div onClick={() => setDrawerOpen(false)} style={{position:'fixed',inset:0,zIndex:98,background:'rgba(0,0,0,0.3)',animation:'tv-fade-in .2s ease'}}/>}

    <div style={{
      position:'fixed', left:0, right:0, bottom: drawerOpen ? 58 : -600,
      zIndex:99, background:'var(--surface)',
      borderTop:'1px solid var(--border)', borderRadius:'18px 18px 0 0',
      padding:'12px 14px 8px',
      transition:'bottom .28s cubic-bezier(.4,0,.2,1)',
      boxShadow:'0 -4px 32px var(--shadow)', maxHeight:'72vh', overflowY:'auto',
    }}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
        <div style={{width:30,height:3,background:'var(--border)',borderRadius:4}}/>
        <button onClick={() => setDrawerOpen(false)} style={{width:26,height:26,borderRadius:7,background:'var(--border)',border:'none',display:'grid',placeItems:'center',cursor:'pointer',color:'var(--text-muted)'}}>
          <X size={13}/>
        </button>
      </div>

      {NAV_GROUPS.map(group => (
        <div key={group.label} style={{marginBottom:14}}>
          <div style={{fontSize:9,fontWeight:700,color:'var(--text-muted)',letterSpacing:'0.1em',textTransform:'uppercase',marginBottom:7,paddingLeft:2,fontFamily:"'JetBrains Mono',monospace"}}>
            {group.label}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:6}}>
            {group.items.map(item => {
              const active = isItemActive(item, location.pathname);
              const Icon   = item.icon;
              return (
                <NavLink key={item.to} to={item.to} end={item.end}
                  onClick={() => setDrawerOpen(false)}
                  style={{
                    display:'flex', flexDirection:'column', alignItems:'center',
                    justifyContent:'center', gap:5, padding:'9px 4px', borderRadius:10,
                    textDecoration:'none',
                    background: active ? 'rgba(30,62,180,0.08)' : 'var(--bg)',
                    color: active ? '#1E3EB4' : 'var(--text-secondary)',
                    border:`1px solid ${active ? 'rgba(30,62,180,0.18)' : 'var(--border)'}`,
                    transition:'all .15s',
                  }}>
                  <Icon size={15}/>
                  <span style={{fontSize:9,fontWeight:active?600:400,textAlign:'center',fontFamily:"'Outfit',sans-serif",lineHeight:1.2}}>
                    {item.label}
                  </span>
                </NavLink>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  </>);
}

// =============================================================================
// LAYOUT
// =============================================================================
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{minHeight:'100vh',background:'var(--bg)'}}>

      {/* DESKTOP NAV */}
      <nav className="tv-desktop-nav" style={{
        background:'var(--surface)',
        borderBottom:'1px solid var(--border)',
        position:'sticky', top:0, zIndex:150,
        height:56,
        boxShadow:'0 1px 0 var(--border)',
      }}>
        <div style={{
          maxWidth:1400, margin:'0 auto', padding:'0 20px',
          display:'flex', alignItems:'center', height:'100%',
          gap:4,
        }}>

          {/* Logo — LEFT */}
          <div style={{display:'flex',alignItems:'center',gap:8,flexShrink:0,marginRight:8}}>
            <div style={{width:30,height:30,borderRadius:7,background:'#1E3EB4',display:'grid',placeItems:'center',flexShrink:0}}>
              <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
                <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
                <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div style={{lineHeight:1}}>
              <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:11,fontWeight:600,letterSpacing:'0.08em',textTransform:'uppercase',color:'var(--text-primary)'}}>
                Taurus <span style={{color:'#1E3EB4'}}>Vision</span>
              </div>
              <div style={{fontSize:8,color:'var(--text-muted)',letterSpacing:'0.05em',marginTop:2,fontFamily:"'Outfit',sans-serif"}}>
                AI Farm Monitoring
              </div>
            </div>
          </div>

          {/* Separator */}
          <div style={{width:1,height:20,background:'var(--border)',flexShrink:0,marginRight:4}}/>

          {/* Dashboard */}
          <NavLink to="/" end className="tv-group-btn"
            style={({ isActive }) => ({
              display:'flex', alignItems:'center', gap:5,
              padding:'0 11px', height:56, textDecoration:'none',
              color: isActive ? '#1E3EB4' : 'var(--text-muted)',
              fontFamily:"'Outfit',sans-serif",
              fontSize:13, fontWeight: isActive ? 600 : 500,
              transition:'color .15s', position:'relative',
            })}>
            {({ isActive }) => (<>
              {isActive && <span style={{position:'absolute',bottom:0,left:'50%',transform:'translateX(-50%)',width:26,height:2,background:'#1E3EB4',borderRadius:'2px 2px 0 0'}}/>}
              <LayoutDashboard size={13}/>
              <span>Dashboard</span>
            </>)}
          </NavLink>

          {/* Separator */}
          <div style={{width:1,height:20,background:'var(--border)',flexShrink:0}}/>

          {/* 3 Dropdown */}
          {NAV_GROUPS.map((group, i) => (
            <div key={group.label} style={{display:'flex',alignItems:'center'}}>
              <NavDropdown group={group}/>
              {i < NAV_GROUPS.length - 1 && (
                <div style={{width:1,height:20,background:'var(--border)',flexShrink:0}}/>
              )}
            </div>
          ))}

          {/* Spacer */}
          <div style={{flex:1}}/>

          {/* RIGHT: Soat + AlertBell + User */}
          <LiveClock/>
          <FarmSwitcher/>
          <div style={{width:6}}/>
          <AlertBell/>
          <div style={{width:6}}/>
          <UserMenu/>
        </div>
      </nav>

      {/* CONTENT */}
      <main style={{fontFamily:"'Outfit',sans-serif",paddingBottom:'var(--bottom-nav-safe)'}}>
        <WebSocketProvider>
          <Suspense fallback={<Spinner/>}>
            {children}
          </Suspense>
        </WebSocketProvider>
      </main>

      {/* MOBILE */}
      <div className="tv-mobile-nav"><BottomNav/></div>
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
          <style>{`
            :root {
              --bg: #F7F8FA; --surface: #FFFFFF; --border: #E4E7ED;
              --text-primary: #0D1117; --text-secondary: #374151; --text-muted: #6B7280;
              --nav-active-bg: rgba(30,62,180,0.07); --nav-active-border: rgba(30,62,180,0.18);
              --shadow: rgba(0,0,0,0.06); --bottom-nav-safe: 0px;
            }
            *, *::before, *::after { box-sizing: border-box; }
            body { margin: 0; }
            a { text-decoration: none; }

            @keyframes tv-spin    { to { transform: rotate(360deg); } }
            @keyframes tv-bell-shake { 0%,90%,100%{transform:rotate(0)} 92%{transform:rotate(-8deg)} 94%{transform:rotate(8deg)} 96%{transform:rotate(-6deg)} 98%{transform:rotate(6deg)} }
            @keyframes tv-drop    { from { opacity:0; transform:translateY(-5px); } to { opacity:1; transform:translateY(0); } }
            @keyframes tv-fade-in { from { opacity:0; } to { opacity:1; } }
            @keyframes tv-blink   { 0%,100% { opacity:0.4; } 50% { opacity:1; } }

            .tv-group-btn:hover { color: var(--text-secondary) !important; background: rgba(0,0,0,0.02) !important; }
            .tv-dropdown-item:hover { background: rgba(30,62,180,0.05) !important; color: var(--text-primary) !important; }

            .tv-menu-btn {
              width:100%; padding:10px 14px; display:flex; align-items:center; gap:8px;
              background:none; border:none; cursor:pointer; font-size:13px;
              color:var(--text-muted); font-family:'Outfit',sans-serif;
              transition:background .12s,color .12s; text-align:left;
            }
            .tv-menu-btn:hover { background:#FEF2F2; color:#DC2626; }

            .tv-desktop-nav { display: flex !important; }
            .tv-mobile-nav  { display: none  !important; }

            @media (max-width: 767px) {
              .tv-desktop-nav { display: none  !important; }
              .tv-mobile-nav  { display: block !important; }
              :root { --bottom-nav-safe: calc(58px + env(safe-area-inset-bottom, 0px)); }
            }
          `}</style>

          <Routes>
            <Route path="/login" element={<PublicRoute><LoginPage/></PublicRoute>}/>
            <Route path="/*" element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/"              element={<DashboardPage/>}/>
                    <Route path="/animals"       element={<AnimalsPage/>}/>
                    <Route path="/animals/:id"   element={<AnimalDetailPage/>}/>
                    <Route path="/behavior"      element={<BehaviorPage/>}/>
                    <Route path="/adi"           element={<ADIMonitoringPage/>}/>
                    <Route path="/predictions"   element={<PredictionsPage/>}/>
                    <Route path="/analytics"     element={<AnalyticsPage/>}/>
                    <Route path="/live"          element={<LiveFeedPage/>}/>
                    <Route path="/reports"       element={<ReportsPage/>}/>
                    <Route path="/health"        element={<HealthPage/>}/>
                    <Route path="/alerts"        element={<AlertsPage/>}/>
                    <Route path="/notifications" element={<NotificationsPage/>}/>
                    <Route path="/cameras"       element={<CamerasPage/>}/>
                    <Route path="/users"         element={<UsersPage/>}/>
                    <Route path="/audit-log"     element={<AuditLogPage/>}/>
                    <Route path="/farms"         element={<FarmsPage/>}/>
                    <Route path="/scales"        element={<ScalePage/>}/>
                    <Route path="/training"      element={<TrainingPage/>}/>
                    <Route path="/tasks"         element={<TasksPage/>}/>
                    <Route path="/feed"          element={<FeedPage/>}/>
                    <Route path="/finance"       element={<FinancePage/>}/>
                    <Route path="/integrations" element={<IntegrationsPage/>}/>
                    <Route path="/sensors"       element={<SensorPage/>}/>
                    <Route path="*"              element={<Navigate to="/" replace/>}/>
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }/>
          </Routes>
        </>
      </Router>
    </AuthProvider>
    </SystemLoadingScreen>
  );
}
