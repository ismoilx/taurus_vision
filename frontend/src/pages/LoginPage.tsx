/**
 * LoginPage — Taurus Vision v2
 * Dizayn: Tech Farm AI — Yumshoq ko'k/yashil palitra, kuchliroq skaner, matritsa elementlari.
 */

import React, { useState, useRef, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// ─── YANGI: Advanced AI Background Animation ──────────────────────────────────

function AdvancedAiBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // ─── Ranglar Palitrasi (Yumshoq Texno) ───
    const colors = {
      bgTop: '#F8FAFC',     // Juda och kulrang-ko'k
      bgBot: '#EFF6FF',     // Yumshoq osmon rangi
      node: 'rgba(56, 189, 248, 0.5)',   // Ochiq ko'k (Cyan) nuqtalar
      nodeActive: 'rgba(14, 165, 233, 0.9)', // Faol nuqta (To'qroq ko'k)
      line: 'rgba(148, 163, 184, 0.15)', // Juda xira bog'lamlar
      scanner: 'rgba(45, 212, 191, 0.2)', // Feruza (Teal) skaner nuri
      bbox: '#10B981',      // Zumrad yashil (Emerald) - Aniqlash rangi
      bboxGlow: 'rgba(16, 185, 129, 0.3)',
      binaryText: 'rgba(100, 116, 139, 0.15)' // Xira matritsa raqamlari
    };

    let animId: number;
    let scanY = 0;
    let frame = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // 1. Matritsa elementlari (0 va 1 lar)
    const binCount = Math.floor((canvas.width * canvas.height) / 25000);
    const binaries = Array.from({ length: binCount }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      val: Math.random() > 0.5 ? '1' : '0',
      speed: (Math.random() + 0.2) * 0.4, // Sekin harakat
      opacity: Math.random() * 0.6 + 0.2,
    }));

    // 2. Neyron tarmoq tugunlari
    const nodeCount = Math.floor((canvas.width * canvas.height) / 20000);
    const nodes = Array.from({ length: Math.min(nodeCount, 50) }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1.5,
      isTarget: Math.random() > 0.8,
      targetLabel: Math.random() > 0.4 ? 'Target ID: #4A2' : 'Health Status: OK',
      conf: (Math.random() * 0.15 + 0.84).toFixed(2),
    }));

    const draw = () => {
      frame++;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // A. Orqa fon gradienti
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
      grad.addColorStop(0, colors.bgTop);
      grad.addColorStop(1, colors.bgBot);
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // B. Matritsa qatlami (Eng orqada)
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = colors.binaryText;
      binaries.forEach(bin => {
        bin.y -= bin.speed; // Yuqoriga suzish
        if (bin.y < -20) bin.y = canvas.height + 20;
        
        // Biroz "pirpirash" effekti
        const flicker = Math.sin(frame * 0.05 + bin.x) * 0.1 + bin.opacity;
        ctx.globalAlpha = Math.max(0.1, flicker);
        ctx.fillText(bin.val, bin.x, bin.y);
      });
      ctx.globalAlpha = 1; // Reset alpha

      // C. Skaner chizig'i harakati (Tezroq)
      scanY += 2.5;
      if (scanY > canvas.height + 150) scanY = -150;

      // D. Neyron tarmoqlari va Aniqlash
      for (let i = 0; i < nodes.length; i++) {
        const nodeA = nodes[i];
        nodeA.x += nodeA.vx; nodeA.y += nodeA.vy;
        if (nodeA.x < 0 || nodeA.x > canvas.width) nodeA.vx *= -1;
        if (nodeA.y < 0 || nodeA.y > canvas.height) nodeA.vy *= -1;

        const distToScan = Math.abs(nodeA.y - scanY);
        const isScanned = distToScan < 80;
        const isCenterScan = distToScan < 20;

        // Chiziqlar
        for (let j = i + 1; j < nodes.length; j++) {
          const nodeB = nodes[j];
          const dx = nodeA.x - nodeB.x; const dy = nodeA.y - nodeB.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            ctx.beginPath(); ctx.moveTo(nodeA.x, nodeA.y); ctx.lineTo(nodeB.x, nodeB.y);
            // Skaner o'tganda chiziqlar ham biroz yorishadi
            const lineAlpha = isScanned ? 0.3 : 0.15;
            ctx.strokeStyle = colors.line.replace('0.15', lineAlpha.toString());
            ctx.lineWidth = isScanned ? 1 : 0.8;
            ctx.stroke();
          }
        }

        // Tugunlar (Nodes)
        ctx.beginPath();
        ctx.arc(nodeA.x, nodeA.y, nodeA.radius * (isScanned ? 1.8 : 1), 0, Math.PI * 2);
        ctx.fillStyle = isCenterScan ? colors.nodeActive : colors.node;
        // Skaner markazida bo'lsa biroz porlash (glow) beramiz
        if (isCenterScan) {
            ctx.shadowColor = colors.nodeActive;
            ctx.shadowBlur = 10;
        }
        ctx.fill();
        ctx.shadowBlur = 0; // Reset shadow

        // E. Bounding Box (Yorqin Yashil Aniqlash)
        if (nodeA.isTarget && isScanned) {
          const boxSize = 44;
          const bx = nodeA.x - boxSize / 2;
          const by = nodeA.y - boxSize / 2;
          const intensity = 1 - distToScan / 80;

          // Glow effekti
          ctx.shadowColor = colors.bbox;
          ctx.shadowBlur = 15 * intensity;
          
          // Asosiy quti
          ctx.strokeStyle = colors.bbox;
          ctx.lineWidth = 2;
          ctx.strokeRect(bx, by, boxSize, boxSize);
          
          // Reset shadow text uchun
          ctx.shadowBlur = 0;

          // Label va Confidence
          ctx.fillStyle = colors.bbox;
          ctx.font = 'bold 11px "Inter", sans-serif';
          ctx.fillText(nodeA.targetLabel, bx, by - 14);
          
          ctx.fillStyle = colors.nodeActive;
          ctx.font = '10px "JetBrains Mono", monospace';
          ctx.fillText(`[CONF: ${nodeA.conf}]`, bx, by - 3);

          // Burchaklardagi qo'shimcha ramkalar (Crosshair style)
          const cs = 6;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(bx-2, by+cs); ctx.lineTo(bx-2, by-2); ctx.lineTo(bx+cs, by-2); // TL
          ctx.moveTo(bx+boxSize-cs, by-2); ctx.lineTo(bx+boxSize+2, by-2); ctx.lineTo(bx+boxSize+2, by+cs); // TR
          ctx.moveTo(bx-2, by+boxSize-cs); ctx.lineTo(bx-2, by+boxSize+2); ctx.lineTo(bx+cs, by+boxSize+2); // BL
          ctx.moveTo(bx+boxSize-cs, by+boxSize+2); ctx.lineTo(bx+boxSize+2, by+boxSize+2); ctx.lineTo(bx+boxSize+2, by+boxSize-cs); // BR
          ctx.stroke();
        }
      }

      // F. Skaner Nuri (Feruza rang)
      const scanGrad = ctx.createLinearGradient(0, scanY - 60, 0, scanY + 60);
      scanGrad.addColorStop(0, 'rgba(45, 212, 191, 0)');
      scanGrad.addColorStop(0.5, colors.scanner);
      scanGrad.addColorStop(1, 'rgba(45, 212, 191, 0)');
      ctx.fillStyle = scanGrad;
      ctx.fillRect(0, scanY - 60, canvas.width, 120);

      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }}
    />
  );
}

// ─── Login Page Component ─────────────────────────────────────────────────────

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap';
    document.head.appendChild(link);
    const timer = setTimeout(() => setReady(true), 150);
    return () => { clearTimeout(timer); document.head.removeChild(link); };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) return;
    setError(''); setLoading(true);
    try {
      await login(identifier.trim(), password);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Email yoki parol xato.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
          font-family: 'Inter', sans-serif; 
          background-color: #F8FAFC; /* Fon rangi canvas bilan bir xil */
          color: #1E293B;
        }
        .auth-wrapper {
          min-height: 100vh;
          display: grid;
          place-items: center;
          position: relative;
          padding: 20px;
          overflow: hidden; /* Skrollni oldini olish */
        }

        /* ── Glassmorphism Card ── */
        .auth-card {
          position: relative;
          z-index: 10;
          width: 100%;
          max-width: 440px;
          /* Ko'proq shaffoflik va zamonaviy blur */
          background: rgba(255, 255, 255, 0.75);
          backdrop-filter: blur(20px) saturate(180%);
          -webkit-backdrop-filter: blur(20px) saturate(180%);
          border: 1px solid rgba(255, 255, 255, 0.5);
          border-radius: 24px;
          padding: 48px 40px;
          /* Yumshoq rangli soya */
          box-shadow: 0 25px 50px -12px rgba(16, 185, 129, 0.15);
          
          opacity: 0;
          transform: translateY(30px) scale(0.98);
          transition: all 0.7s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .auth-card.ready { 
          opacity: 1; 
          transform: translateY(0) scale(1); 
        }

        /* ── Header ── */
        .brand-title {
          font-family: 'JetBrains Mono', monospace;
          font-size: 26px;
          font-weight: 700;
          color: #0F172A;
          text-align: center;
          letter-spacing: -0.5px;
          margin-bottom: 8px;
        }
        .brand-title span {
          /* Brend rangi: Feruza/Ko'k gradient */
          background: linear-gradient(135deg, #0EA5E9 0%, #10B981 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .page-subtitle {
          font-size: 15px;
          color: #64748B;
          text-align: center;
          margin-bottom: 40px;
          font-weight: 400;
        }

        /* ── Form ── */
        .input-label {
          display: block;
          font-size: 13px; font-weight: 600; color: #475569;
          margin-bottom: 8px;
        }
        .form-input {
          width: 100%; height: 50px;
          background: rgba(255, 255, 255, 0.8);
          border: 1px solid #E2E8F0;
          border-radius: 14px;
          padding: 0 16px;
          font-family: inherit; font-size: 15px; color: #1E293B;
          transition: all 0.2s ease; outline: none;
        }
        .form-input:focus {
          border-color: #0EA5E9; /* Fokusda ko'k */
          background: #FFFFFF;
          box-shadow: 0 0 0 4px rgba(14, 165, 233, 0.1);
        }
        .eye-btn {
          position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
          background: none; border: none; color: #94A3B8; cursor: pointer;
          padding: 4px; transition: color 0.2s;
        }
        .eye-btn:hover { color: #0EA5E9; }

        /* ── Submit Button (Gradient) ── */
        .submit-btn {
          width: 100%; height: 50px;
          /* Tugma gradienti */
          background: linear-gradient(135deg, #0EA5E9 0%, #059669 100%);
          color: #FFFFFF; border: none; border-radius: 14px;
          font-size: 16px; font-weight: 600; cursor: pointer;
          transition: all 0.3s ease; margin-top: 16px;
          display: flex; align-items: center; justify-content: center; gap: 8px;
          box-shadow: 0 4px 6px -1px rgba(14, 165, 233, 0.2);
        }
        .submit-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 10px 15px -3px rgba(14, 165, 233, 0.3);
        }
        .submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

        /* ── Error & Spinner ── */
        .error-message {
          background: #FEF2F2; border-left: 4px solid #EF4444; color: #B91C1C;
          padding: 12px 16px; border-radius: 8px; font-size: 13px; margin-bottom: 24px;
          display: flex; align-items: center; gap: 10px;
        }
        .spinner {
          width: 20px; height: 20px;
          border: 2px solid rgba(255,255,255,0.3); border-top-color: #FFF;
          border-radius: 50%; animation: spin 0.8s linear infinite;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>

      <div className="auth-wrapper">
        <AdvancedAiBackground />

        <div className={`auth-card ${ready ? 'ready' : ''}`}>
          <div className="brand-title">TAURUS <span>VISION</span></div>
          <div className="page-subtitle">Tizimga kirish</div>

          {error && (
            <div className="error-message">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div style={{ marginBottom: 20 }}>
              <label className="input-label" htmlFor="login-email">Email yoki Foydalanuvchi nomi</label>
              <input id="login-email" type="text" value={identifier} onChange={(e) => { setIdentifier(e.target.value); setError(''); }} placeholder="admin" disabled={loading} className="form-input"/>
            </div>

            <div style={{ marginBottom: 20 }}>
              <label className="input-label" htmlFor="login-password">Parol</label>
              <div style={{ position: 'relative' }}>
                <input id="login-password" type={showPass ? 'text' : 'password'} value={password} onChange={(e) => { setPassword(e.target.value); setError(''); }} placeholder="••••••••" disabled={loading} className="form-input" style={{ paddingRight: '44px' }}/>
                <button type="button" className="eye-btn" onClick={() => setShowPass(!showPass)} tabIndex={-1}>
                  {showPass ? <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9 9 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg> : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>}
                </button>
              </div>
            </div>

            <button type="submit" className="submit-btn" disabled={loading || !identifier.trim() || !password}>
              {loading ? <><div className="spinner"></div>Tizimga kirilmoqda...</> : 'Kirish'}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}