/**
 * AnimalDetailPage — Jonivor shaxsiy sahifasi
 *
 * Tuzatilgan buglar:
 *   ✅ ADI komponentlar: adi.scores.feeding_score (oldin: adi.feeding_score)
 *   ✅ data_quality (oldin: data_completeness)
 *   ✅ adiDetailed state — trend.current dan olinadi
 *   ✅ (adiToday as any) hack olib tashlandi
 *   ✅ Barcha 8 komponent ko'rsatiladi (mavjud bo'lganda)
 */

import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Scale, Activity, TrendingUp, TrendingDown,
  Minus, AlertTriangle, CheckCircle, Camera, Upload,
  Download, RefreshCw, Heart, Plus,
  Images, ImagePlus, Trash2, Star, Clock, Stethoscope,
  Syringe, Bandage, Pill, ClipboardList, Layers,
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

interface AnimalPhoto {
  id: number; file_name: string; file_size?: number;
  url: string; is_profile: boolean; created_at: string;
}
interface AnimalPhotosResp {
  animal_id: number;
  profile_image: string | null;
  photos: AnimalPhoto[];
}
interface Animal {
  id: number; tag_id: string; species: string; gender: string;
  status: string; breed?: string; notes?: string;
  acquisition_date?: string; birth_date?: string;
  profile_image?: string | null;
  total_detections: number; last_detected_at: string | null;
  created_at: string;
}

interface WeightMeasurement {
  id: number; animal_id: number; estimated_weight_kg: number;
  confidence_score: number; camera_id: string; timestamp: string;
}

// Backend ADILogResponse.scores ichidagi komponentlar
interface ADIComponentScores {
  activity_score?:   number;
  feeding_score?:    number;
  drinking_score?:   number;
  movement_score?:   number;
  growth_score?:     number;
  social_score?:     number;
  sensor_score?:     number;
  veterinary_score?: number;
}

// Backend ADILogResponse — to'liq (komponentlar bilan)
interface ADILogDetailed {
  id:               number;
  animal_id:        number;
  calculation_date: string;
  calculated_at:    string;
  adi_score:        number;
  category:         string;
  scores:           ADIComponentScores;
  data_quality:     number;
  notes?:           string;
}

// Grafik uchun soddalashtirilgan yozuv
interface ADILog {
  id: number; animal_id: number; calculation_date: string;
  adi_score: number; category: string;
}

// Backend ADITrendResponse
interface ADITrend {
  trend:      { date: string; score: number; category: string }[];
  avg_score?: number;
  min_score?: number;
  max_score?: number;
  current?:   ADILogDetailed;   // ← eng so'nggi kunning to'liq ADI (komponentlar bilan)
}

interface HealthRecord {
  id: number;
  animal_id: number;
  record_type: string;
  severity: string;
  diagnosis: string;
  symptoms?: string;
  treatment?: string;
  medication?: string;
  veterinarian?: string;
  cost?: number;
  recorded_at: string;
  next_checkup_date?: string;
  is_resolved: boolean;
  resolved_at?: string;
}

interface HealthRecordListResponse {
  records: HealthRecord[];
  total: number;
  skip: number;
  limit: number;
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
  const qClient  = useQueryClient();
  const numId    = Number(id);

  // UI state (o'zgarmas — bular keshlanmaydi)
  const [tab,           setTab]           = useState<'overview'|'adi'|'weight'|'health'|'register'>('overview');
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [regFile,       setRegFile]       = useState<File | null>(null);
  const [regPreview,    setRegPreview]    = useState<string>('');
  const [regMsg,        setRegMsg]        = useState('');
  const [showHealthForm, setShowHealthForm] = useState(false);
  const [healthForm,    setHealthForm]    = useState({
    record_type: 'checkup', severity: 'normal',
    diagnosis: '', symptoms: '', treatment: '',
    medication: '', veterinarian: '', cost: '',
  });
  const [healthFormMsg, setHealthFormMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleGalleryUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setUploadingPhoto(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await fetch(`/api/v1/animals/${id}/photos`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('tv_access_token') ?? ''}` },
        body: fd,
      });
      await refetchPhotos();
      qClient.invalidateQueries({ queryKey: ['animals', numId] });
    } finally {
      setUploadingPhoto(false);
      if (galleryRef.current) galleryRef.current.value = '';
    }
  };

  const handleSetProfile = async (photoId: number) => {
    await apiFetch(`/api/v1/animals/${id}/photos/${photoId}/set-profile`, { method: 'PATCH' });
    await refetchPhotos();
    qClient.invalidateQueries({ queryKey: ['animals', numId] });
  };

  const handleDeletePhoto = async (photoId: number) => {
    await apiFetch(`/api/v1/animals/${id}/photos/${photoId}`, { method: 'DELETE' });
    await refetchPhotos();
    qClient.invalidateQueries({ queryKey: ['animals', numId] });
  };

  // ── Queries ───────────────────────────────────────────────────────────────

  const { data: animal, isLoading: loading, isError, error } = useQuery({
    queryKey: ['animals', numId],
    queryFn:  () => apiFetch<Animal>(`/api/v1/animals/${id}`),
    enabled:  !!id,
  });

  const { data: weightsRaw } = useQuery({
    queryKey: ['weights', numId],
    queryFn:  () => apiFetch<any>(`/api/v1/weights/animal/${id}`),
    enabled:  !!id,
  });
  const weights: WeightMeasurement[] = Array.isArray(weightsRaw)
    ? weightsRaw : (weightsRaw?.items ?? []);

  const { data: adiTrend } = useQuery({
    queryKey: ['adi', 'trend', numId],
    queryFn:  () => apiFetch<ADITrend>(`/api/v1/adi/animal/${id}/trend?days=30`),
    enabled:  !!id,
  });

  const { data: embsRaw } = useQuery({
    queryKey: ['embeddings', numId],
    queryFn:  () => apiFetch<any[]>(`/api/v1/identification/${id}/embeddings`),
    enabled:  !!id,
  });
  const embedCount = embsRaw?.length ?? 0;

  const { data: healthResp, isFetching: healthLoading } = useQuery({
    queryKey: ['health', 'records', numId],
    queryFn:  () => apiFetch<HealthRecordListResponse>(`/api/v1/health/animals/${id}/records?skip=0&limit=50`),
    enabled:  !!id && tab === 'health',
  });
  const healthRecords = healthResp?.records ?? [];
  const healthTotal   = healthResp?.total ?? 0;

  const { data: photosData, refetch: refetchPhotos } = useQuery<AnimalPhotosResp>({
    queryKey: ['animal-photos', numId],
    queryFn:  () => apiFetch<AnimalPhotosResp>(`/api/v1/animals/${id}/photos`),
    enabled:  !!id,
  });

  // Derived ADI values
  const adiDetailed = adiTrend?.current ?? null;
  const adiToday = adiDetailed
    ? { id: adiDetailed.id, animal_id: adiDetailed.animal_id,
        calculation_date: adiDetailed.calculation_date,
        adi_score: adiDetailed.adi_score, category: adiDetailed.category }
    : adiTrend?.trend?.length
    ? (() => { const last = adiTrend.trend[adiTrend.trend.length-1];
        return { id: 0, animal_id: numId,
          calculation_date: last.date, adi_score: last.score, category: last.category }; })()
    : null;
  const adiLogs: ADILog[] = (adiTrend?.trend ?? []).map((p, i) => ({
    id: i, animal_id: numId,
    calculation_date: p.date, adi_score: p.score, category: p.category,
  }));

  // ── Mutations ─────────────────────────────────────────────────────────────

  const createHealthMutation = useMutation({
    mutationFn: () => apiFetch(`/api/v1/health/animals/${id}/records`, {
      method: 'POST',
      body: JSON.stringify({
        record_type:  healthForm.record_type,
        severity:     healthForm.severity,
        diagnosis:    healthForm.diagnosis,
        symptoms:     healthForm.symptoms    || undefined,
        treatment:    healthForm.treatment   || undefined,
        medication:   healthForm.medication  || undefined,
        veterinarian: healthForm.veterinarian || undefined,
        cost:         healthForm.cost ? parseFloat(healthForm.cost) : undefined,
      }),
    }),
    onSuccess: () => {
      setHealthFormMsg("✅ Yozuv muvaffaqiyatli qo'shildi!");
      setHealthForm({ record_type: 'checkup', severity: 'normal',
        diagnosis: '', symptoms: '', treatment: '', medication: '', veterinarian: '', cost: '' });
      setShowHealthForm(false);
      qClient.invalidateQueries({ queryKey: ['health', 'records', numId] });
    },
    onError: (e: Error) => setHealthFormMsg(`❌ ${e.message}`),
  });

  const resolveHealthMutation = useMutation({
    mutationFn: (recordId: number) => apiFetch(`/api/v1/health/records/${recordId}/resolve`, { method: 'POST' }),
    onSuccess: () => qClient.invalidateQueries({ queryKey: ['health', 'records', numId] }),
  });

  async function handleHealthCreate() {
    if (!id || !healthForm.diagnosis.trim()) return;
    setHealthFormMsg('');
    createHealthMutation.mutate();
  }
  const handleHealthResolve = (recordId: number) => resolveHealthMutation.mutate(recordId);


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

  const registerMutation = useMutation({
    mutationFn: async () => {
      if (!regFile || !id) throw new Error('Fayl tanlanmagan');
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
      return res.json();
    },
    onSuccess: (data) => {
      setRegMsg(`✅ Muvaffaqiyatli! Similarity: ${(data.similarity_score * 100).toFixed(1)}%`);
      setRegFile(null); setRegPreview('');
      qClient.invalidateQueries({ queryKey: ['embeddings', numId] });
    },
    onError: (e: Error) => setRegMsg(`❌ ${e.message}`),
  });

  const regLoading = registerMutation.isPending;
  function handleRegister() { registerMutation.mutate(); }

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
  const prevWeight   = weightChart.length > 7 ? weightChart[weightChart.length - 7]?.weight : null;
  const weightChange = latestWeight && prevWeight ? latestWeight - prevWeight : null;

  const adiCfg = adiToday
    ? (CATEGORY_CONFIG[adiToday.category as keyof typeof CATEGORY_CONFIG] || CATEGORY_CONFIG.average)
    : null;

  const trendDirection = (() => {
    if (!adiTrend?.trend?.length || adiTrend.trend.length < 3) return 'insufficient_data';
    const arr   = adiTrend.trend;
    const first = arr[0].score;
    const last  = arr[arr.length - 1].score;
    if (last - first > 5)  return 'improving';
    if (last - first < -5) return 'declining';
    return 'stable';
  })();
  const trendCfg = TREND_CONFIG[trendDirection as keyof typeof TREND_CONFIG] || TREND_CONFIG.stable;

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
        <p style={{ color: '#EF4444', marginBottom: 16 }}>{error?.message || 'Jonivor topilmadi'}</p>
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
        @keyframes spin { to { transform: rotate(360deg); } }
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

          {/* Profil avatar */}
          <div
            onClick={() => setTab('register')}
            title="Identifikatsiya va rasmlar"
            style={{ cursor: 'pointer', position: 'relative', flexShrink: 0 }}>
            {photosData?.profile_image ? (
              <img
                src={photosData.profile_image}
                alt={animal.tag_id}
                style={{ width: 56, height: 56, borderRadius: 14, objectFit: 'cover',
                  border: '2px solid #E4E7ED', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}
              />
            ) : (
              <div style={{ width: 56, height: 56, borderRadius: 14,
                background: 'linear-gradient(135deg, #EFF6FF, #DBEAFE)',
                border: '2px solid #BFDBFE', display: 'grid', placeItems: 'center' }}>
                <Camera size={22} color="#93C5FD" />
              </div>
            )}
            <div style={{ position: 'absolute', bottom: -3, right: -3,
              width: 18, height: 18, borderRadius: '50%', background: '#1E3EB4',
              display: 'grid', placeItems: 'center', border: '2px solid #fff' }}>
              <Camera size={8} color="#fff" />
            </div>
          </div>

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
                  {embedCount} rasm
                </span>
              )}
            </div>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0', textTransform: 'capitalize' }}>
              {animal.species} · {animal.gender} · {animal.breed || 'Zot noma\'lum'}
            </p>
          </div>
        </div>

        <button onClick={() => qClient.invalidateQueries({ queryKey: ["animals", numId] })} style={{
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <trendCfg.icon size={24} color={trendCfg.color} />
            <span style={{ fontSize: 13, fontWeight: 600, color: trendCfg.color }}>
              {trendCfg.label}
            </span>
          </div>
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
        {(['overview', 'adi', 'weight', 'health', 'register'] as const).map(t => (
          <button key={t} style={tabStyle(t)} onClick={() => setTab(t)}>
            {t === 'overview'  ? 'Umumiy'
           : t === 'adi'       ? 'ADI'
           : t === 'weight'    ? 'Vazn'
           : t === 'health'    ? "Sog'liq"
           :                     'Identifikatsiya'}
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: trendCfg.color }}>
                      <trendCfg.icon size={16} />
                      {trendCfg.label}
                    </div>
                    <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>
                      {format(parseISO(adiToday.calculation_date), 'dd.MM.yyyy')}
                    </div>
                  </div>
                </div>

                {/* Komponentlar — adiDetailed.scores dan olinadi (to'g'ri manba) */}
                {adiDetailed?.scores && (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280',
                      textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
                      Komponentlar
                    </div>
                    {adiDetailed.scores.feeding_score != null && (
                      <ComponentBar label="Oziqlanish" value={adiDetailed.scores.feeding_score}  color="#3B82F6" />
                    )}
                    {adiDetailed.scores.activity_score != null && (
                      <ComponentBar label="Faollik"    value={adiDetailed.scores.activity_score} color="#8B5CF6" />
                    )}
                    {adiDetailed.scores.growth_score != null && (
                      <ComponentBar label="O'sish"     value={adiDetailed.scores.growth_score}   color="#22C55E" />
                    )}
                    {adiDetailed.scores.drinking_score != null && (
                      <ComponentBar label="Suv ichish" value={adiDetailed.scores.drinking_score} color="#06B6D4" />
                    )}
                    {adiDetailed.scores.movement_score != null && (
                      <ComponentBar label="Harakat"    value={adiDetailed.scores.movement_score} color="#F59E0B" />
                    )}
                    {adiDetailed.scores.social_score != null && (
                      <ComponentBar label="Ijtimoiy"   value={adiDetailed.scores.social_score}   color="#EC4899" />
                    )}
                    <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 8 }}>
                      Ma'lumot sifati: {((adiDetailed.data_quality ?? 0) * 100).toFixed(0)}%
                    </div>
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
                Ma'lumot yo'q
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

          {/* Komponentlar to'liq paneli — faqat adiDetailed mavjud bo'lganda */}
          {adiDetailed?.scores && (
            <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', margin: 0 }}>
                  ADI Komponentlari — {format(parseISO(adiDetailed.calculation_date), 'dd.MM.yyyy')}
                </h3>
                <span style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 99,
                  background: '#F3F4F6', color: '#6B7280',
                }}>
                  Sifat: {((adiDetailed.data_quality ?? 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
                {[
                  { key: 'feeding_score',    label: 'Oziqlanish',  color: '#3B82F6', weight: '20%' },
                  { key: 'activity_score',   label: 'Faollik',     color: '#8B5CF6', weight: '20%' },
                  { key: 'growth_score',     label: "O'sish",      color: '#22C55E', weight: '20%' },
                  { key: 'movement_score',   label: 'Harakat',     color: '#F59E0B', weight: '15%' },
                  { key: 'drinking_score',   label: 'Suv ichish',  color: '#06B6D4', weight: '10%' },
                  { key: 'social_score',     label: 'Ijtimoiy',    color: '#EC4899', weight: '10%' },
                  { key: 'sensor_score',     label: 'Sensor',      color: '#64748B', weight: '5%'  },
                  { key: 'veterinary_score', label: 'Veterinar',   color: '#DC2626', weight: '5%'  },
                ].map(({ key, label, color, weight }) => {
                  const val = adiDetailed.scores[key as keyof ADIComponentScores];
                  if (val == null) return null;
                  return (
                    <div key={key} style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: '#6B7280' }}>
                          {label} <span style={{ fontSize: 10, color: '#D1D5DB' }}>({weight})</span>
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 700, color }}>
                          {val.toFixed(0)}
                        </span>
                      </div>
                      <div style={{ height: 8, background: '#F3F4F6', borderRadius: 4, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${val}%`,
                          background: color, borderRadius: 4,
                          transition: 'width 0.6s ease',
                        }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              {adiDetailed.notes && (
                <div style={{
                  marginTop: 16, padding: '10px 14px', borderRadius: 8,
                  background: '#F9FAFB', border: '1px solid #E4E7ED',
                  fontSize: 12, color: '#6B7280',
                }}>
                  {adiDetailed.notes}
                </div>
              )}
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

      {/* ══════════════════════ HEALTH TAB ══════════════════════ */}
      {tab === 'health' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 14, color: '#6B7280' }}>
              Jami <span style={{ fontWeight: 700, color: '#0D1117' }}>{healthTotal}</span> ta sog'liq yozuvi
            </div>
            <button
              onClick={() => { setShowHealthForm(v => !v); setHealthFormMsg(''); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 16px', borderRadius: 8,
                background: showHealthForm ? '#F3F4F6' : '#1E3EB4',
                color: showHealthForm ? '#374151' : '#fff',
                border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              }}
            >
              <Plus size={14} />
              {showHealthForm ? 'Bekor qilish' : 'Yangi yozuv'}
            </button>
          </div>

          {/* ── Yangi yozuv formasi ── */}
          {showHealthForm && (
            <div style={{
              background: '#fff', border: '1px solid #E4E7ED',
              borderRadius: 12, padding: 24,
            }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 20 }}>
                Yangi Sog'liq Yozuvi
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                    Tur *
                  </label>
                  <select
                    value={healthForm.record_type}
                    onChange={e => setHealthForm(f => ({ ...f, record_type: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: 8,
                      border: '1px solid #E4E7ED', fontSize: 13, color: '#374151',
                      background: '#F9FAFB',
                    }}
                  >
                    <option value="checkup">Tekshiruv</option>
                    <option value="treatment">Davolash</option>
                    <option value="vaccination">Emlash</option>
                    <option value="injury">Shikast</option>
                    <option value="surgery">Operatsiya</option>
                    <option value="illness">Kasallik</option>
                    <option value="other">Boshqa</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                    Jiddiylik *
                  </label>
                  <select
                    value={healthForm.severity}
                    onChange={e => setHealthForm(f => ({ ...f, severity: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: 8,
                      border: '1px solid #E4E7ED', fontSize: 13, color: '#374151',
                      background: '#F9FAFB',
                    }}
                  >
                    <option value="normal">Normal</option>
                    <option value="warning">Ogohlantirish</option>
                    <option value="critical">Kritik</option>
                  </select>
                </div>

                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                    Diagnoz *
                  </label>
                  <input
                    type="text"
                    value={healthForm.diagnosis}
                    onChange={e => setHealthForm(f => ({ ...f, diagnosis: e.target.value }))}
                    placeholder="Masalan: Oddiy tekshiruv, Sog'lik holati normal"
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: 8,
                      border: `1px solid ${healthForm.diagnosis ? '#E4E7ED' : '#FCA5A5'}`,
                      fontSize: 13, boxSizing: 'border-box',
                    }}
                  />
                </div>

                {[
                  ['symptoms',    'Belgilar',    'Kuzatilgan alomatlar...'],
                  ['treatment',   'Davolash',    'Qilingan davolash...'],
                  ['medication',  'Dori-darmon', 'Berilgan dorilar...'],
                  ['veterinarian','Veterinar',   'Veterinar ismi...'],
                ].map(([field, label, placeholder]) => (
                  <div key={field}>
                    <label style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                      {label}
                    </label>
                    <input
                      type="text"
                      value={healthForm[field as keyof typeof healthForm]}
                      onChange={e => setHealthForm(f => ({ ...f, [field]: e.target.value }))}
                      placeholder={placeholder}
                      style={{
                        width: '100%', padding: '8px 12px', borderRadius: 8,
                        border: '1px solid #E4E7ED', fontSize: 13, boxSizing: 'border-box',
                      }}
                    />
                  </div>
                ))}

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', display: 'block', marginBottom: 6 }}>
                    Narx (UZS)
                  </label>
                  <input
                    type="number"
                    value={healthForm.cost}
                    onChange={e => setHealthForm(f => ({ ...f, cost: e.target.value }))}
                    placeholder="0"
                    min="0"
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: 8,
                      border: '1px solid #E4E7ED', fontSize: 13, boxSizing: 'border-box',
                    }}
                  />
                </div>
              </div>

              {healthFormMsg && (
                <div style={{
                  marginTop: 14, padding: '10px 14px', borderRadius: 8,
                  background: healthFormMsg.startsWith('✅') ? '#F0FDF4' : '#FEF2F2',
                  color: healthFormMsg.startsWith('✅') ? '#16A34A' : '#DC2626',
                  fontSize: 13, border: `1px solid ${healthFormMsg.startsWith('✅') ? '#BBF7D0' : '#FECACA'}`,
                }}>
                  {healthFormMsg}
                </div>
              )}

              <button
                onClick={handleHealthCreate}
                disabled={!healthForm.diagnosis.trim() || createHealthMutation.isPending}
                style={{
                  marginTop: 16, width: '100%', padding: '12px', borderRadius: 8,
                  background: healthForm.diagnosis ? '#1E3EB4' : '#E4E7ED',
                  color: healthForm.diagnosis ? '#fff' : '#9CA3AF',
                  border: 'none', cursor: healthForm.diagnosis ? 'pointer' : 'not-allowed',
                  fontSize: 14, fontWeight: 600, display: 'flex',
                  alignItems: 'center', justifyContent: 'center', gap: 8,
                }}
              >
                {createHealthMutation.isPending ? (
                  <>
                    <div style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)',
                      borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .6s linear infinite' }} />
                    Saqlanmoqda...
                  </>
                ) : (
                  <><Heart size={16} /> Saqlash</>
                )}
              </button>
            </div>
          )}

          {/* ── Yozuvlar ro'yxati ── */}
          {healthLoading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF' }}>
              <div style={{ width: 28, height: 28, border: '2px solid #E4E7ED',
                borderTopColor: '#1E3EB4', borderRadius: '50%',
                animation: 'spin .65s linear infinite', margin: '0 auto 10px' }} />
              Yuklanmoqda...
            </div>
          ) : healthRecords.length === 0 ? (
            <div style={{
              background: '#fff', border: '1px solid #E4E7ED',
              borderRadius: 12, padding: '48px 24px', textAlign: 'center',
            }}>
              <Heart size={40} color="#D1D5DB" style={{ margin: '0 auto 12px' }} />
              <p style={{ color: '#9CA3AF', fontSize: 14 }}>Sog'liq yozuvlari yo'q</p>
              <p style={{ color: '#D1D5DB', fontSize: 12, marginTop: 4 }}>
                Yuqoridagi "Yangi yozuv" tugmasini bosing
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {healthRecords.map(rec => {
                const sevColor = rec.severity === 'critical' ? '#EF4444'
                               : rec.severity === 'warning'  ? '#F59E0B'
                               :                               '#22C55E';
                const sevBg = rec.severity === 'critical' ? '#FEF2F2'
                            : rec.severity === 'warning'  ? '#FFFBEB'
                            :                               '#F0FDF4';
                const typeLabel: Record<string, string> = {
                  checkup: 'Tekshiruv', treatment: 'Davolash',
                  vaccination: 'Emlash', injury: 'Shikast',
                  surgery: 'Operatsiya', illness: 'Kasallik', other: 'Boshqa',
                };
                return (
                  <div key={rec.id} style={{
                    background: '#fff', border: '1px solid #E4E7ED',
                    borderRadius: 12, padding: '16px 20px',
                    borderLeft: `4px solid ${sevColor}`,
                    opacity: rec.is_resolved ? 0.7 : 1,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>
                            {typeLabel[rec.record_type] ?? rec.record_type}
                          </span>
                          <span style={{
                            fontSize: 11, fontWeight: 600, padding: '2px 8px',
                            borderRadius: 99, background: sevBg, color: sevColor,
                            border: `1px solid ${sevColor}22`,
                          }}>
                            {rec.severity}
                          </span>
                          {rec.is_resolved && (
                            <span style={{
                              fontSize: 11, padding: '2px 8px', borderRadius: 99,
                              background: '#F0FDF4', color: '#16A34A', border: '1px solid #BBF7D0',
                            }}>
                              Hal etilgan
                            </span>
                          )}
                        </div>

                        <p style={{ fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
                          {rec.diagnosis}
                        </p>

                        {rec.symptoms && (
                          <p style={{ fontSize: 12, color: '#6B7280', marginBottom: 2 }}>
                            <span style={{ fontWeight: 600 }}>Belgilar:</span> {rec.symptoms}
                          </p>
                        )}
                        {rec.treatment && (
                          <p style={{ fontSize: 12, color: '#6B7280', marginBottom: 2 }}>
                            <span style={{ fontWeight: 600 }}>Davolash:</span> {rec.treatment}
                          </p>
                        )}
                        {rec.medication && (
                          <p style={{ fontSize: 12, color: '#6B7280', marginBottom: 2 }}>
                            <span style={{ fontWeight: 600 }}>Dori:</span> {rec.medication}
                          </p>
                        )}

                        <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                            {format(new Date(rec.recorded_at), 'dd.MM.yyyy HH:mm')}
                          </span>
                          {rec.veterinarian && (
                            <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                              {rec.veterinarian}
                            </span>
                          )}
                          {rec.cost != null && (
                            <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                              {rec.cost?.toLocaleString()} UZS
                            </span>
                          )}
                          {rec.next_checkup_date && (
                            <span style={{ fontSize: 11, color: '#3B82F6' }}>
                              Keyingi: {format(new Date(rec.next_checkup_date), 'dd.MM.yyyy')}
                            </span>
                          )}
                        </div>
                      </div>

                      {!rec.is_resolved && (
                        <button
                          onClick={() => handleHealthResolve(rec.id)}
                          title="Hal etilgan deb belgilash"
                          style={{
                            marginLeft: 12, flexShrink: 0,
                            display: 'flex', alignItems: 'center', gap: 5,
                            padding: '6px 12px', borderRadius: 7,
                            background: '#F0FDF4', color: '#16A34A',
                            border: '1px solid #BBF7D0', cursor: 'pointer',
                            fontSize: 12, fontWeight: 500,
                          }}
                        >
                          <CheckCircle size={13} /> Hal etildi
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === 'register' && (
        <>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', marginBottom: 6 }}>
              Identifikatsiya Rasmi Yuklash
            </h3>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 20 }}>
              Sigirning yuz yoki tana rasmini yuklab, tizimga o'rgating.
              Bir necha burchakdan rasm yuklash aniqlikni oshiradi.
            </p>

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

            <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8,
              background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
              <div style={{ fontSize: 12, color: '#16A34A', fontWeight: 500 }}>
                Saqlangan rasmlar: <b>{embedCount} ta</b>
              </div>
            </div>
          </div>
        </div>

        {/* ── Rasm Galereyasi ── */}
        <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: 24, marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#0D1117', margin: 0 }}>
               {photosData?.photos.length ? <span style={{ fontSize: 13, color: '#6B7280', fontWeight: 400 }}>({photosData.photos.length} ta)</span> : null}
            </h3>
            <button
              onClick={() => galleryRef.current?.click()}
              disabled={uploadingPhoto}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
                borderRadius: 8, border: 'none', background: '#1E3EB4', color: '#fff',
                fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: uploadingPhoto ? 0.6 : 1 }}>
              {uploadingPhoto ? '⏳ Yuklanmoqda...' : "+ Rasm qo'shish"}
            </button>
            <input ref={galleryRef} type="file" accept="image/*"
              style={{ display: 'none' }} onChange={handleGalleryUpload} />
          </div>

          {!photosData?.photos.length ? (
            <div style={{ textAlign: 'center', padding: '32px 20px', color: '#9CA3AF',
              border: '1px dashed #E4E7ED', borderRadius: 10 }}>
              <div style={{ marginBottom: 12 }}><Images size={36} color="#D1D5DB" /></div>
              <p style={{ fontSize: 13, marginBottom: 12 }}>Hali rasm yuklanmagan</p>
              <button onClick={() => galleryRef.current?.click()}
                style={{ padding: '6px 16px', borderRadius: 8, border: '1px solid #D1D5DB',
                  background: 'transparent', color: '#6B7280', cursor: 'pointer', fontSize: 12 }}>
                Birinchi rasmni yuklash
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
              {photosData.photos.map(photo => (
                <div key={photo.id} style={{ borderRadius: 10, overflow: 'hidden',
                  border: photo.is_profile ? '2px solid #1E3EB4' : '1px solid #E4E7ED',
                  background: '#F8FAFC', position: 'relative' }}>
                  <img
                    src={`/api/v1/animals/photos/file/${photo.id}`}
                    alt={photo.file_name}
                    style={{ width: '100%', height: 130, objectFit: 'cover', display: 'block' }}
                  />
                  {photo.is_profile && (
                    <div style={{ position: 'absolute', top: 5, left: 5,
                      background: '#1E3EB4', color: '#fff', fontSize: 10, fontWeight: 700,
                      padding: '2px 7px', borderRadius: 99 }}>
                      Profil
                    </div>
                  )}
                  <div style={{ padding: '7px 8px', display: 'flex', gap: 5 }}>
                    {!photo.is_profile && (
                      <button
                        onClick={() => handleSetProfile(photo.id)}
                        style={{ flex: 1, fontSize: 10, padding: '3px 0', borderRadius: 6,
                          border: '1px solid #BFDBFE', background: '#EFF6FF',
                          color: '#1E3EB4', cursor: 'pointer', fontWeight: 600 }}>
                        Profil qil
                      </button>
                    )}
                    <button
                      onClick={() => handleDeletePhoto(photo.id)}
                      style={{ padding: '3px 7px', borderRadius: 6,
                        border: '1px solid #FCA5A5', background: '#FEF2F2',
                        color: '#EF4444', cursor: 'pointer', fontSize: 12 }}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        </>
      )}
    </div>
  );
}