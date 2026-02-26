/**
 * LoginPage — Taurus Vision
 * App dizayn tizimiga mos: Outfit font, #1E3EB4 ko'k, oq card.
 */

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login }  = useAuth();
  const navigate   = useNavigate();

  const [identifier, setIdentifier] = useState('');
  const [password,   setPassword]   = useState('');
  const [showPass,   setShowPass]   = useState(false);
  const [error,      setError]      = useState('');
  const [loading,    setLoading]    = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) return;
    setError('');
    setLoading(true);
    try {
      await login(identifier.trim(), password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login yoki parol xato.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');

        .lp-root {
          min-height: 100vh;
          background: #F7F8FA;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          font-family: 'Outfit', sans-serif;
          padding: 24px;
        }

        .lp-nav {
          position: fixed;
          top: 0; left: 0; right: 0;
          height: 56px;
          background: #fff;
          border-bottom: 1px solid #E4E7ED;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
          display: flex;
          align-items: center;
          padding: 0 24px;
          z-index: 50;
        }
        .lp-nav-icon {
          width: 32px; height: 32px;
          background: #1E3EB4;
          border-radius: 7px;
          display: grid;
          place-items: center;
          flex-shrink: 0;
          margin-right: 10px;
        }
        .lp-nav-name {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          font-weight: 500;
          letter-spacing: 0.1em;
          color: #0D1117;
          text-transform: uppercase;
        }
        .lp-nav-name span { color: #1E3EB4; }
        .lp-nav-sub {
          font-size: 10px;
          color: #9CA3AF;
          letter-spacing: 0.04em;
        }

        .lp-card {
          width: 100%;
          max-width: 420px;
          background: #fff;
          border: 1px solid #E4E7ED;
          border-radius: 16px;
          padding: 40px 36px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
          margin-top: 56px;
        }

        .lp-heading {
          font-size: 22px;
          font-weight: 600;
          color: #0D1117;
          margin-bottom: 4px;
        }
        .lp-sub {
          font-size: 14px;
          color: #6B7280;
          margin-bottom: 32px;
        }

        .lp-field { margin-bottom: 18px; }

        .lp-label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: #374151;
          margin-bottom: 7px;
        }

        .lp-input {
          width: 100%;
          height: 42px;
          padding: 0 12px;
          font-family: 'Outfit', sans-serif;
          font-size: 14px;
          color: #0D1117;
          background: #F9FAFB;
          border: 1px solid #E4E7ED;
          border-radius: 8px;
          outline: none;
          transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
        }
        .lp-input:focus {
          border-color: #1E3EB4;
          background: #fff;
          box-shadow: 0 0 0 3px rgba(30,62,180,0.08);
        }
        .lp-input::placeholder { color: #D1D5DB; }
        .lp-input:disabled { opacity: 0.6; cursor: not-allowed; }

        .lp-pass-wrap { position: relative; }
        .lp-pass-wrap .lp-input { padding-right: 42px; }
        .lp-eye {
          position: absolute;
          right: 12px; top: 50%;
          transform: translateY(-50%);
          background: none; border: none;
          color: #9CA3AF; cursor: pointer;
          padding: 2px; display: flex;
          align-items: center;
          transition: color 0.15s;
        }
        .lp-eye:hover { color: #1E3EB4; }

        .lp-error {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          color: #DC2626;
          background: #FEF2F2;
          border: 1px solid #FECACA;
          border-radius: 8px;
          padding: 10px 14px;
          margin-bottom: 20px;
        }

        .lp-btn {
          width: 100%;
          height: 42px;
          background: #1E3EB4;
          color: #fff;
          border: none;
          border-radius: 8px;
          font-family: 'Outfit', sans-serif;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
          margin-top: 8px;
        }
        .lp-btn:hover:not(:disabled) {
          background: #1a35a0;
          box-shadow: 0 4px 12px rgba(30,62,180,0.25);
          transform: translateY(-1px);
        }
        .lp-btn:active:not(:disabled) { transform: translateY(0); }
        .lp-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .lp-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: lp-spin 0.7s linear infinite;
          flex-shrink: 0;
        }
        @keyframes lp-spin { to { transform: rotate(360deg); } }

        .lp-footer {
          margin-top: 20px;
          font-size: 12px;
          color: #9CA3AF;
          text-align: center;
        }
      `}</style>

      {/* Navbar */}
      <nav className="lp-nav">
        <div className="lp-nav-icon">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="5" width="16" height="11" rx="2" stroke="white" strokeWidth="1.4"/>
            <circle cx="10" cy="10.5" r="3" stroke="white" strokeWidth="1.4"/>
            <path d="M7 5L8.5 2.5H11.5L13 5" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <div className="lp-nav-name">Taurus <span>Vision</span></div>
          <div className="lp-nav-sub">AI Farm Monitoring</div>
        </div>
      </nav>

      {/* Content */}
      <div className="lp-root">
        <div className="lp-card">

          <div className="lp-heading">Tizimga kirish</div>
          <div className="lp-sub">Davom etish uchun hisobingizga kiring</div>

          {error && (
            <div className="lp-error">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="lp-field">
              <label className="lp-label" htmlFor="lp-id">
                Foydalanuvchi nomi yoki Email
              </label>
              <input
                id="lp-id"
                className="lp-input"
                type="text"
                placeholder="admin"
                value={identifier}
                onChange={e => { setIdentifier(e.target.value); setError(''); }}
                disabled={loading}
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="lp-field">
              <label className="lp-label" htmlFor="lp-pass">Parol</label>
              <div className="lp-pass-wrap">
                <input
                  id="lp-pass"
                  className="lp-input"
                  type={showPass ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setError(''); }}
                  disabled={loading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="lp-eye"
                  onClick={() => setShowPass(v => !v)}
                  tabIndex={-1}
                >
                  {showPass ? (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9 9 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  ) : (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="lp-btn"
              disabled={loading || !identifier.trim() || !password}
            >
              {loading
                ? <><div className="lp-spinner" />Kirilmoqda...</>
                : 'Kirish'}
            </button>
          </form>
        </div>

        <div className="lp-footer">
          Taurus Vision © {new Date().getFullYear()}
        </div>
      </div>
    </>
  );
}