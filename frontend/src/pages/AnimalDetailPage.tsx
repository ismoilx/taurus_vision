/**
 * AnimalDetailPage — Jonivor shaxsiy sahifasi
 *
 * Ko'rsatiladi:
 *   - Asosiy ma'lumotlar + holat
 *   - ADI joriy ball + kategoriya + trend
 *   - ADI 30 kunlik grafik
 *   - Vazn 30 kunlik grafik
 *   - ADI komponentlari (feeding, activity, growth)
 *   - Oxirgi o'lchovlar jadvali
 *   - Rasm ro'yxatdan o'tkazish
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Scale, Activity, TrendingUp, TrendingDown,
  Minus, AlertTriangle, CheckCircle, Camera, Upload,
  Trash2, Download, RefreshCw,
} from 'lucide-react';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadialBarChart, RadialBar,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';
import config from '../config';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Animal {
  id: number; tag_id: string; species: string; gender: string;
  status: string; breed?: string; notes?: string;
  acquisition_date?: string; birth_date?: string;
  total_detections: number; last_detected_at: string | null;
  created_at: string;
}

interface WeightMeasurement {
  id: number; animal_id: number; estimated_weight_kg: number;
  confidence_score: number; camera_id: string; timestamp: string;
}

interface ADILog {
  id: number; animal_id: number; calculation_date: string;
  adi_score: number; category: string;
  feeding_score?: number; activity_score?: number; growth_score?: number;
  detection_count?: number; weight_count?: number;
  data_completeness?: number;
}

interface ADITrend {
  trend: string;   // improving | declining | stable | insufficient_data
  points: { date: string; score: number; category: string }[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG = {
  healthy:  { label: 'Sog\'lom',    color: '#22C55E', bg: '#F0FDF4', border: '#BBF7D0' },
  average:  { label: 'O\'rtacha',   color: '#F59E0B', bg: '#FFFBEB', border: '#FDE68A' },
  warning:  { label: 'Diqqat',      color: '#F97316', bg: '#FFF7ED', border: '#FED7AA' },
  critical: { label: 'Kritik',      color: '#EF4444', bg: '#FEF2F2', border: '#FECACA' },
};

const TREND_CONFIG = {
  improving:         { label: 'Yaxshilanmoqda', icon: TrendingUp,   color: '#22C55E' },
  declining:         { label: 'Yomonlashmoqda', icon: TrendingDown,  color: '#EF4444' },
  stable:            { label: 'Barqaror',        icon: Minus,         color: '#6B7280' },
  insufficient_data: { label: 'Ma\'lumot yetarli emas', icon: Minus, color: '#9CA3AF' },
};

// ─── ADI Score Ring ───────────────────────────────────────────────────────────

function ADIRing({ score, category }: { score: number; category: string }) {
  const cfg = CATEGORY_CONFIG[category as keyof typeof CATEGORY_CONFIG]
           || CATEGORY_CONFIG.average;

  const data = [
    { value: score,       fill: cfg.color },
    { value: 100 - score, fill: '#F3F4F6' },
  ];

  return (
    <div style={{ position: 'relative', width: 140, height: 140 }}>
      <RadialBarChart
        width={140} height={140}
        cx={70} cy={70}
        innerRadius={50} outerRadius={65}
        startAngle={225} endAngle={-45}
        data={data} barSize={12}
      >
        <RadialBar dataKey="value" cornerRadius={6} background={{ fill: '#F3F4F6' }} />
      </RadialBarChart>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: cfg.color, lineHeight: 1 }}>
          {score.toFixed(0)}
        </span>
        <span style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>/ 100</span>
      </div>
    </div>
  );
}

// ─── Component Bar ────────────────────────────────────────────────────────────

function ComponentBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: '#6B7280' }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{value.toFixed(0)}</span>
      </div>
      <div style={{ height: 6, background: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${value}%`,
          background: color, borderRadius: 3,
          transition: 'width 0.5s ease',
        }} />
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AnimalDetailPage() {
  const { id }   = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [animal,   setAnimal]   = useState<Animal | null>(null);
  const [weights,  setWeights]  = useState<WeightMeasurement[]>([]);
  const [adiLogs,  setAdiLogs]  = useState<ADILog[]>([]);
  const [adiToday, setAdiToday] = useState<ADILog | null>(null);
  const [adiTrend, setAdiTrend] = useState<ADITrend | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [tab,      setTab]      = useState<'overview'|'adi'|'weight'|'register'>('overview');

  // Registration
  const [regFile,     setRegFile]     = useState<File | null>(null);
  const [regPreview,  setRegPreview]  = useState<string>('');
  const [regLoading,  setRegLoading]  = useState(false);
  const [regMsg,      setRegMsg]      = useState('');
  const [embedCount,  setEmbedCount]  = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Load ──────────────────────────────────────────────────────────────────

  useEffect(() => { if (id) loadAll(); }, [id]);

  async function loadAll() {
    setLoading(true); setError('');
    try {
      const [animalData, weightsData] = await Promise.all([
        apiFetch<Animal>(`/api/v1/animals/${id}`),
        apiFetch<any>(`/api/v1/weights/animal/${id}`),
      ]);
      setAnimal(animalData);

      // weights — array yoki { items: [] } bo'lishi mumkin
      const wArr = Array.isArray(weightsData) ? weightsData
                 : (weightsData?.items ?? []);
      setWeights(wArr);

      // ADI trend
      try {
        const trend = await apiFetch<ADITrend>(`/api/v1/adi/animal/${id}/trend?days=30`);
        setAdiTrend(trend);
        if (trend.points?.length) {
          const last = trend.points[trend.points.length - 1];
          setAdiToday({ id: 0, animal_id: Number(id),
            calculation_date: last.date, adi_score: last.score, category: last.category });
        }
        setAdiLogs(trend.points?.map((p, i) => ({
          id: i, animal_id: Number(id),
          calculation_date: p.date, adi_score: p.score, category: p.category,
        })) ?? []);
      } catch { /* ADI yo'q bo'lishi mumkin */ }

      // Embedding count
      try {
        const embs = await apiFetch<any[]>(`/api/v1/identification/${id}/embeddings`);
        setEmbedCount(embs?.length ?? 0);
      } catch { setEmbedCount(0); }

    } catch (e) {
      setError(e instanceof Error ? e.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  // ── Registration ──────────────────────────────────────────────────────────

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setRegFile(f);
    const reader = new FileReader();
    reader.onload = ev => setRegPreview(ev.target?.result as string);
    reader.readAsDataURL(f);
    setRegMsg('');
  }

  async function handleRegister() {
    if (!regFile || !id) return;
    setRegLoading(true); setRegMsg('');
    try {
      const form = new FormData();
      form.append('photo', regFile);
      const token = localStorage.getItem('tv_access_token');
      const res = await fetch(`${config.apiUrl}/api/v1/identification/register/${id}`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRegMsg(`✅ Muvaffaqiyatli! Similarity: ${(data.similarity_score * 100).toFixed(1)}%`);
      setRegFile(null); setRegPreview('');
      setEmbedCount(c => c + 1);
    } catch (e) {
      setRegMsg(`❌ ${e instanceof Error ? e.message : 'Xato'}`);
    } finally {
      setRegLoading(false);
    }
  }

  // ── Derived data ──────────────────────────────────────────────────────────

  const weightChart = [...weights]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(-30)
    .map(w => ({
      date:   format(new Date(w.timestamp), 'dd/MM'),
      weight: +w.estimated_weight_kg.toFixed(1),
      conf:   +(w.confidence_score * 100).toFixed(0),
    }));

  const adiChart = [...adiLogs]
    .sort((a, b) => a.calculation_date.localeCompare(b.calculation_date))
    .map(a => ({
      date:     format(parseISO(a.calculation_date), 'dd/MM'),
      score:    +a.adi_score.toFixed(1),
      category: a.category,
    }));

  const latestWeight = weightChart.length ? weightChart[weightChart.length - 1].weight : null;
  const prevWeight   = weightChart.length > 1 ? weightChart[weightChart.length - 7]?.weight : null;
  const weightChange = latestWeight && prevWeight ? latestWeight - prevWeight : null;

  const adiCfg   = adiToday
    ? (CATEGORY_CONFIG[adiToday.category as keyof typeof CATEGORY_CONFIG] || CATEGORY_CONFIG.average)
    : null;
  const trendCfg = adiTrend
    ? (TREND_CONFIG[adiTrend.trend as keyof typeof TREND_CONFIG] || TREND_CONFIG.stable)
    : null;

  // ── Render helpers ────────────────────────────────────────────────────────

  const tabStyle = (t: string) => ({
    padding: '8px 18px', borderRadius: 8,
    fontSize: 13, fontWeight: 500, cursor: 'pointer',
    border: 'none',
    background: tab === t ? '#1E3EB4' : 'transparent',
    color: tab === t ? '#fff' : '#6B7280',
    transition: 'all .15s',
  });

  if (loading) return (
    <div style={{ minHeight: '60vh', display: 'grid', placeItems: 'center' }}>
      <div style={{ textAlign: 'center', color: '#6B7280' }}>
        <div style={{
          width: 32, height: 32, border: '2px solid #E4E7ED',
          borderTopColor: '#1E3EB4', borderRadius: '50%',
          animation: 'spin .65s linear infinite', margin: '0 auto 12px',
        }} />
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        Yuklanmoqda...
      </div>
    </div>
  );

  if (error || !animal) return (
    <div style={{ minHeight: '60vh', display: 'grid', placeItems: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <AlertTriangle size={40} color="#EF4444" style={{ margin: '0 auto 12px' }} />
        <p style={{ color: '#EF4444', marginBottom: 16 }}>{error || 'Jonivor topilmadi'}</p>
        <button onClick={() => navigate('/animals')}
          style={{ color: '#1E3EB4', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>
          ← Orqaga
        </button>
      </div>
    </div>
  );

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 20px', fontFamily: 'Outfit, sans-serif' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');
      `}</style>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={() => navigate('/animals')} style={{
            width: 36, height: 36, borderRadius: 8, border: '1px solid #E4E7ED',
            background: '#fff', cursor: 'pointer', display: 'grid', placeItems: 'center',
          }}>
            <ArrowLeft size={16} color="#6B7280" />
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0D1117', margin: 0,
                fontFamily: "'JetBrains Mono', monospace" }}>
                {animal.tag_id}
              </h1>
              <span style={{
                padding: '2px 10px', borderRadius: 99,
                fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
                background: animal.status === 'active' ? '#F0FDF4' : '#F3F4F6',
                color: animal.status === 'active' ? '#16A34A' : '#6B7280',
                border: `1px solid ${animal.status === 'active' ? '#BBF7D0' : '#E5E7EB'}`,
              }}>
                {animal.status === 'active' ? 'Faol' : animal.status}
              </span>
              {embedCount > 0 && (
                <span style={{
                  padding: '2px 10px', borderRadius: 99,
                  fontSize: 11, fontWeight: 600,
                  background: '#EFF6FF', color: '#1E3EB4',
                  border: '1px solid #BFDBFE',
                }}>
                  📷 {embedCount} rasm
                </span>
              )}
            </div>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0', textTransform: 'capitalize' }}>
              {animal.species} · {animal.gender} · {animal.breed || 'Zot noma\'lum'}
            </p>
          </div>
        </div>

        <button onClick={loadAll} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '7px 14px', borderRadius: 8,
          border: '1px solid #E4E7ED', background: '#fff',
          fontSize: 13, color: '#6B7280', cursor: 'pointer',
        }}>
          <RefreshCw size={14} /> Yangilash
        </button>
      </div>

      {/* ── Top Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 24 }}>

        {/* ADI Card */}
        <div style={{
          background: adiCfg?.bg || '#F9FAFB',
          border: `1px solid ${adiCfg?.border || '#E5E7EB'}`,
          borderRadius: 12, padding: '16px 20px',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>ADI Ball</div>
          {adiToday ? (
            <>
              <div style={{ fontSize: 32, fontWeight: 700, color: adiCfg?.color, lineHeight: 1 }}>
                {adiToday.adi_score.toFixed(0)}
              </div>
              <div style={{ fontSize: 12, color: adiCfg?.color, marginTop: 4, fontWeight: 500 }}>
                {adiCfg?.label}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 14, color: '#9CA3AF' }}>—</div>
          )}
        </div>

        {/* Joriy vazn */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Joriy vazn</div>
          {latestWeight ? (
            <>
              <div style={{ fontSize: 32, fontWeight: 700, color: '#0D1117', lineHeight: 1 }}>
                {latestWeight}
              </div>
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>kg</div>
            </>
          ) : (
            <div style={{ fontSize: 14, color: '#9CA3AF' }}>—</div>
          )}
        </div>

        {/* 7 kunlik o'zgarish */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>7 kun o'zgarish</div>
          {weightChange !== null ? (
            <>
              <div style={{ fontSize: 32, fontWeight: 700, lineHeight: 1,
                color: weightChange > 0 ? '#22C55E' : weightChange < 0 ? '#EF4444' : '#6B7280' }}>
                {weightChange > 0 ? '+' : ''}{weightChange.toFixed(1)}
              </div>
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>kg</div>
            </>
          ) : (
            <div style={{ fontSize: 14, color: '#9CA3AF' }}>—</div>
          )}
        </div>

        {/* Trend */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>ADI Trendi</div>
          {trendCfg ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <trendCfg.icon size={24} color={trendCfg.color} />
              <span style={{ fontSize: 13, fontWeight: 600, color: trendCfg.color }}>
                {trendCfg.label}
              </span>
            </div>
          ) : (
            <div style={{ fontSize: 14, color: '#9CA3AF' }}>—</div>
          )}
        </div>

        {/* Aniqlashlar */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280',
            textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Aniqlashlar</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#0D1117', lineHeight: 1 }}>
            {animal.total_detections}
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>ta</div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20,
        background: '#F7F8FA', borderRadius: 10, padding: 4, width: 'fit-content' }}>
        {(['overview', 'adi', 'weight', 'register'] as const).map(t => (
          <button key={t} style={tabStyle(t)} onClick={() => setTab(t)}>
            {t === 'overview' ? '📋 Umumiy'
           : t === 'adi'      ? '🎯 ADI'
           : t === 'weight'   ? '⚖️ Vazn'
           :                    '📷 Identifikatsiya'}
          </button>
        ))}
      </div>

      {/* ══════════════════════ OVERVIEW TAB ══════════════════════ */}
      {tab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Asosiy ma'lumotlar */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 16 }}>
              Asosiy Ma'lumotlar
            </h3>
            {[
              ['Tag ID',        animal.tag_id],
              ['Tur',           animal.species],
              ['Jins',          animal.gender === 'male' ? 'Erkak' : 'Urg\'oqi'],
              ['Zot',           animal.breed || '—'],
              ['Holat',         animal.status === 'active' ? 'Faol' : animal.status],
              ['Olingan sana',  animal.acquisition_date
                ? format(new Date(animal.acquisition_date), 'dd.MM.yyyy') : '—'],
              ['Tug\'ilgan',    animal.birth_date
                ? format(new Date(animal.birth_date), 'dd.MM.yyyy') : '—'],
              ['Oxirgi ko\'rinish', animal.last_detected_at
                ? format(new Date(animal.last_detected_at), 'dd.MM.yyyy HH:mm') : '—'],
            ].map(([label, value]) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '8px 0', borderBottom: '1px solid #F3F4F6',
                fontSize: 13,
              }}>
                <span style={{ color: '#6B7280' }}>{label}</span>
                <span style={{ fontWeight: 500, color: '#0D1117', textTransform: 'capitalize' }}>
                  {value as string}
                </span>
              </div>
            ))}
            {animal.notes && (
              <div style={{ marginTop: 12, padding: 12, background: '#F9FAFB', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4 }}>IZOH</div>
                <p style={{ fontSize: 13, color: '#374151', margin: 0 }}>{animal.notes}</p>
              </div>
            )}
          </div>

          {/* ADI bugungi holat */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 20 }}>
              ADI Bugungi Holat
            </h3>
            {adiToday ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 24 }}>
                  <ADIRing score={adiToday.adi_score} category={adiToday.category} />
                  <div>
                    <div style={{
                      display: 'inline-block', padding: '4px 14px', borderRadius: 99,
                      background: adiCfg?.bg, border: `1px solid ${adiCfg?.border}`,
                      fontSize: 13, fontWeight: 600, color: adiCfg?.color, marginBottom: 8,
                    }}>
                      {adiCfg?.label}
                    </div>
                    {trendCfg && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: trendCfg.color }}>
                        <trendCfg.icon size={16} />
                        {trendCfg.label}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>
                      {format(parseISO(adiToday.calculation_date), 'dd.MM.yyyy')}
                    </div>
                  </div>
                </div>

                {/* Komponentlar */}
                {(adiToday as any).feeding_score !== undefined && (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280',
                      textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                      Komponentlar
                    </div>
                    <ComponentBar label="Oziqlanish" value={(adiToday as any).feeding_score ?? 0} color="#3B82F6" />
                    <ComponentBar label="Faollik"    value={(adiToday as any).activity_score ?? 0} color="#8B5CF6" />
                    <ComponentBar label="O'sish"     value={(adiToday as any).growth_score ?? 0}   color="#22C55E" />
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF' }}>
                <Activity size={40} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
                <p style={{ fontSize: 14 }}>ADI ma'lumoti yo'q</p>
                <p style={{ fontSize: 12, marginTop: 4 }}>Simulate qilish uchun backend scriptni ishga tushiring</p>
              </div>
            )}
          </div>

          {/* Oxirgi o'lchovlar */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 16 }}>
              Oxirgi Vazn O'lchovlari
            </h3>
            {weights.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: '#9CA3AF', fontSize: 14 }}>
                O'lchovlar mavjud emas
              </div>
            ) : (
              <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                {weights.slice(0, 8).map(w => (
                  <div key={w.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: '1px solid #F3F4F6',
                  }}>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: '#0D1117' }}>
                        {w.estimated_weight_kg.toFixed(1)} kg
                      </div>
                      <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
                        {format(new Date(w.timestamp), 'dd.MM.yyyy HH:mm')}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 11, color: '#6B7280' }}>{w.camera_id}</div>
                      <div style={{
                        fontSize: 11, fontWeight: 600, marginTop: 2,
                        color: w.confidence_score >= 0.85 ? '#22C55E' : '#F59E0B',
                      }}>
                        {(w.confidence_score * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ADI oxirgi yozuvlar */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 16 }}>
              ADI Tarixi (oxirgi 7 kun)
            </h3>
            {adiLogs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: '#9CA3AF', fontSize: 14 }}>
                ADI yozuvlari mavjud emas
              </div>
            ) : (
              <div>
                {[...adiLogs]
                  .sort((a, b) => b.calculation_date.localeCompare(a.calculation_date))
                  .slice(0, 7)
                  .map(a => {
                    const c = CATEGORY_CONFIG[a.category as keyof typeof CATEGORY_CONFIG] || CATEGORY_CONFIG.average;
                    return (
                      <div key={a.calculation_date} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '10px 0', borderBottom: '1px solid #F3F4F6',
                      }}>
                        <div style={{ fontSize: 13, color: '#6B7280' }}>
                          {format(parseISO(a.calculation_date), 'dd.MM.yyyy')}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{ width: 80, height: 6, background: '#F3F4F6', borderRadius: 3 }}>
                            <div style={{ width: `${a.adi_score}%`, height: '100%',
                              background: c.color, borderRadius: 3 }} />
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 600, color: c.color, minWidth: 30 }}>
                            {a.adi_score.toFixed(0)}
                          </span>
                          <span style={{
                            fontSize: 10, padding: '2px 8px', borderRadius: 99,
                            background: c.bg, color: c.color, border: `1px solid ${c.border}`,
                          }}>
                            {c.label}
                          </span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════ ADI TAB ══════════════════════ */}
      {tab === 'adi' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ADI grafik */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 20 }}>
              ADI 30 Kunlik Trend
            </h3>
            {adiChart.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: '#9CA3AF' }}>
                <Activity size={40} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                Ma'lumot yo'q — simulatsiya scriptini ishga tushiring
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={adiChart}>
                  <defs>
                    <linearGradient id="adiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#1E3EB4" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#1E3EB4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#E4E7ED" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#E4E7ED" />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: '1px solid #E4E7ED', fontSize: 12 }}
                    formatter={(v: any) => [`${Number(v).toFixed(1)}`, 'ADI Ball']}
                  />
                  <Area type="monotone" dataKey="score" stroke="#1E3EB4"
                    strokeWidth={2} fill="url(#adiGrad)" dot={{ r: 3, fill: '#1E3EB4' }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Komponentlar grafik */}
          {adiLogs.some(a => (a as any).feeding_score) && (
            <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 20 }}>
                ADI Komponentlari Trendi
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={[...adiLogs]
                  .sort((a, b) => a.calculation_date.localeCompare(b.calculation_date))
                  .map(a => ({
                    date:     format(parseISO(a.calculation_date), 'dd/MM'),
                    feeding:  (a as any).feeding_score?.toFixed(1),
                    activity: (a as any).activity_score?.toFixed(1),
                    growth:   (a as any).growth_score?.toFixed(1),
                  }))
                }>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#E4E7ED" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#E4E7ED" />
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E4E7ED', fontSize: 12 }} />
                  <Line type="monotone" dataKey="feeding"  stroke="#3B82F6" strokeWidth={2} dot={false} name="Oziqlanish" />
                  <Line type="monotone" dataKey="activity" stroke="#8B5CF6" strokeWidth={2} dot={false} name="Faollik" />
                  <Line type="monotone" dataKey="growth"   stroke="#22C55E" strokeWidth={2} dot={false} name="O'sish" />
                </LineChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', gap: 20, justifyContent: 'center', marginTop: 12 }}>
                {[['#3B82F6', 'Oziqlanish'], ['#8B5CF6', 'Faollik'], ['#22C55E', "O'sish"]].map(([c, l]) => (
                  <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#6B7280' }}>
                    <div style={{ width: 20, height: 2, background: c }} />
                    {l}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════ WEIGHT TAB ══════════════════════ */}
      {tab === 'weight' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 20 }}>
              Vazn O'zgarish Grafigi (oxirgi 30 o'lchov)
            </h3>
            {weightChart.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: '#9CA3AF' }}>
                <Scale size={40} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                Vazn ma'lumotlari yo'q
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={weightChart}>
                  <defs>
                    <linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#22C55E" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#E4E7ED" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#E4E7ED"
                    label={{ value: 'kg', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: '1px solid #E4E7ED', fontSize: 12 }}
                    formatter={(v: any) => [`${Number(v).toFixed(1)} kg`, 'Vazn']}
                  />
                  <Area type="monotone" dataKey="weight" stroke="#22C55E"
                    strokeWidth={2} fill="url(#wGrad)" dot={{ r: 2, fill: '#22C55E' }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Jadval */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', margin: 0 }}>
                Barcha O'lchovlar ({weights.length} ta)
              </h3>
              <button onClick={() => {
                const token = localStorage.getItem('tv_access_token');
                window.open(`${config.apiUrl}/api/v1/export/weights?animal_id=${id}&format=csv`, '_blank');
              }} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', borderRadius: 7,
                border: '1px solid #E4E7ED', background: '#F7F8FA',
                fontSize: 12, color: '#6B7280', cursor: 'pointer',
              }}>
                <Download size={13} /> CSV
              </button>
            </div>
            <div style={{ maxHeight: 360, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#F7F8FA' }}>
                    {['Sana', 'Vazn', 'Ishonch', 'Kamera'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left',
                        fontWeight: 600, color: '#6B7280', fontSize: 11,
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                        borderBottom: '1px solid #E4E7ED' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...weights]
                    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                    .map(w => (
                      <tr key={w.id} style={{ borderBottom: '1px solid #F3F4F6' }}>
                        <td style={{ padding: '10px 12px', color: '#374151' }}>
                          {format(new Date(w.timestamp), 'dd.MM.yyyy HH:mm')}
                        </td>
                        <td style={{ padding: '10px 12px', fontWeight: 600, color: '#0D1117' }}>
                          {w.estimated_weight_kg.toFixed(1)} kg
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{
                            color: w.confidence_score >= 0.85 ? '#22C55E' : '#F59E0B',
                            fontWeight: 500,
                          }}>
                            {(w.confidence_score * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', color: '#6B7280', fontSize: 12 }}>
                          {w.camera_id}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════ REGISTER TAB ══════════════════════ */}
      {tab === 'register' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Rasm yuklash */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 6 }}>
              Identifikatsiya Rasmi Yuklash
            </h3>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 20 }}>
              Sigirning yuz yoki tana rasmini yuklab, tizimga o'rgating.
              Bir necha burchakdan rasm yuklash aniqlikni oshiradi.
            </p>

            {/* Upload zone */}
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${regPreview ? '#1E3EB4' : '#E4E7ED'}`,
                borderRadius: 10, padding: 24,
                textAlign: 'center', cursor: 'pointer',
                background: regPreview ? '#EFF6FF' : '#F9FAFB',
                transition: 'all .2s', marginBottom: 16,
              }}
            >
              {regPreview ? (
                <img src={regPreview} alt="preview" style={{
                  maxHeight: 200, maxWidth: '100%', borderRadius: 8, margin: '0 auto',
                }} />
              ) : (
                <>
                  <Upload size={32} color="#9CA3AF" style={{ margin: '0 auto 10px' }} />
                  <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>
                    Rasm yuklash uchun bosing
                  </p>
                  <p style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
                    JPG, PNG — max 10MB
                  </p>
                </>
              )}
              <input ref={fileRef} type="file" accept="image/*"
                onChange={onFileChange} style={{ display: 'none' }} />
            </div>

            {regMsg && (
              <div style={{
                padding: '10px 14px', borderRadius: 8, marginBottom: 14,
                background: regMsg.startsWith('✅') ? '#F0FDF4' : '#FEF2F2',
                color: regMsg.startsWith('✅') ? '#16A34A' : '#DC2626',
                fontSize: 13, fontWeight: 500,
                border: `1px solid ${regMsg.startsWith('✅') ? '#BBF7D0' : '#FECACA'}`,
              }}>
                {regMsg}
              </div>
            )}

            <button
              onClick={handleRegister}
              disabled={!regFile || regLoading}
              style={{
                width: '100%', padding: '12px', borderRadius: 8,
                background: regFile ? '#1E3EB4' : '#E4E7ED',
                color: regFile ? '#fff' : '#9CA3AF',
                border: 'none', cursor: regFile ? 'pointer' : 'not-allowed',
                fontSize: 14, fontWeight: 600, display: 'flex',
                alignItems: 'center', justifyContent: 'center', gap: 8,
                transition: 'background .15s',
              }}
            >
              {regLoading ? (
                <>
                  <div style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .6s linear infinite' }} />
                  Yuklanmoqda...
                </>
              ) : (
                <><Camera size={16} /> Ro'yxatdan o'tkazish</>
              )}
            </button>
          </div>

          {/* Yo'riqnoma */}
          <div style={{ background: '#F7F8FA', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 16 }}>
              Qanday ishlaydi?
            </h3>
            {[
              ['1', '#1E3EB4', "Rasmni yuklang", "Sigirning yuz (burun) yoki tana rasmi. Aniq, yorqin rasm tavsiya etiladi."],
              ['2', '#8B5CF6', "MobileNetV2 tahlil qiladi", "1280-o'lchamli embedding vektori chiqariladi va bazaga saqlanadi."],
              ['3', '#22C55E', "Kamera aniqlaganida", "Cosine similarity ≥ 0.80 bo'lsa jonivor tanilgan hisoblanadi."],
              ['4', '#F59E0B', "ADI va vazn", "Tanilgan jonivor uchun avtomatik hisoblanib, bazaga saqlanadi."],
            ].map(([num, color, title, desc]) => (
              <div key={num} style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: color, color: '#fff',
                  display: 'grid', placeItems: 'center',
                  fontSize: 13, fontWeight: 700, flexShrink: 0,
                }}>
                  {num}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#0D1117', marginBottom: 3 }}>{title}</div>
                  <div style={{ fontSize: 12, color: '#6B7280', lineHeight: 1.5 }}>{desc}</div>
                </div>
              </div>
            ))}

            <div style={{
              marginTop: 20, padding: '12px 16px', borderRadius: 8,
              background: '#EFF6FF', border: '1px solid #BFDBFE',
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#1E3EB4', marginBottom: 4 }}>
                💡 Maslahat
              </div>
              <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.5 }}>
                Har bir jonivor uchun kamida <b>3-5 ta rasm</b> (turli burchak va yoritishda) yuklang.
                Bu aniqlikni 75% dan 95% ga yetkazadi.
              </div>
            </div>

            <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8,
              background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
              <div style={{ fontSize: 12, color: '#16A34A', fontWeight: 500 }}>
                ✅ Saqlangan rasmlar: <b>{embedCount} ta</b>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}