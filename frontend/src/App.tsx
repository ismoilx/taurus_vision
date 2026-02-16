/**
 * Main Application Component - WITH ROUTING
 * 
 * Updated Sprint 4:
 * - React Router integration
 * - Multiple pages support
 * - Professional navigation
 */

import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Scale, Camera, Users } from 'lucide-react';

// Pages
import DashboardPage from './pages/DashboardPage';
import AnimalsPage from './pages/AnimalsPage';
import AnimalDetailPage from './pages/AnimalDetailPage';
import LiveFeedPage from './pages/LiveFeedPage';
import CamerasPage from './pages/CamerasPage';

import './App.css';

// ---------------------------------------------------------------------------
// Layout Component
// ---------------------------------------------------------------------------

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header / Navigation */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
                <Scale className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-900">Taurus Vision</h1>
                <p className="text-xs text-gray-500">AI-Powered Farm Management</p>
              </div>
            </div>

            {/* Navigation Links */}
            <div className="flex items-center gap-2">
              <NavItem to="/" icon={Activity} label="Dashboard" />
              <NavItem to="/animals" icon={Users} label="Jonivorlar" />
              <NavItem to="/live" icon={Camera} label="Live Feed" />
              <NavItem to="/cameras" icon={Camera} label="Kameralar" />
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>{children}</main>
    </div>
  );
}

function NavItem({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: any;
  label: string;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
          isActive
            ? 'bg-blue-50 text-blue-600'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`
      }
    >
      <Icon className="w-4 h-4" />
      {label}
    </NavLink>
  );
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/animals" element={<AnimalsPage />} />
          <Route path="/animals/:id" element={<AnimalDetailPage />} />
          <Route path="/live" element={<LiveFeedPage />} />
          <Route path="/cameras" element={<CamerasPage />} />
        </Routes>
      </Layout>
    </Router>
  );
}