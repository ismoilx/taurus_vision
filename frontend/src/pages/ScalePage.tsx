/**
 * ScalePage — Tarozi integratsiyasi va vazn boshqaruvi
 *
 * Xususiyatlar:
 *   - Tarozlar ro'yxati (karta ko'rinishida)
 *   - Yangi tarozi qo'shish / tahrirlash (ADMIN)
 *   - Qo'lda vazn kiritish (MANAGER)
 *   - AI vs haqiqiy vazn taqqoslash hisoboti
 *   - Kalibratsiya paneli
 *   - Serial/API tarozi webhook yo'riqnomasi
 */

import { useState } from 'react';
import {
  Scale, Plus, Edit2, Wifi, Usb, Hand,
  CheckCircle, AlertTriangle, TrendingDown, TrendingUp,
  RefreshCw, ChevronDown, ChevronUp, Info, Trash2,
  BarChart2, Settings,
} from 'lucide-react';
import {
  useQuery, useMutation, useQueryClient,
} from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { apiFetch } from '../utils/apiFetch';
import { useAuth } from '../context/AuthContext';

// =============================================================================
// TYPES
// =============================================================================

interface ScaleData {
  id:                       number;
  name:                     string;
  scale_type:               'manual' | 'serial' | 'api';
  location:                 string | null;
  status:                   'active' | 'inactive' | 'error';
  is_active:                boolean;
  calibration_factor:       number;
  calibration_sample_count: number;
  last_calibrated_at:       string | null;
  last_reading_at:          string | null;
  last_weight_kg:           number | null;
  is_calibrated:            boolean;
  notes:                    string | null;
  serial_port:              string | null;
  baud_rate:                number | null;
  api_token:                string | null;
  created_at:               string;
}

interface ScaleListResponse { items: ScaleData[]; total: number; }

interface ComparisonItem {
  measurement_id:   number;
  animal_id:        number;
  animal_tag_id:    string;
  timestamp:        string;
  ai_weight_kg:     number;
  actual_weight_kg: number | null;
  difference_kg:    number | null;
  difference_pct:   number | null;
  source:           string;
}

interface ComparisonResponse {
  items:              ComparisonItem[];
  total:              number;
  mean_error_kg:      number | null;
  mean_error_pct:     number | null;
  current_factor:     number;
  recommended_factor: number | null;
}

interface Animal { id: number; tag_id: string; species: string; }

const EMPTY_FORM = {
  name:        '',
  scale_type:  'manual' as const,
  location:    '',
  serial_port: '',
  baud_rate:   9600,
  notes:       '',
};

const TYPE_META: Record<string, { label: string; icon: React.ReactNode; color: string; bg: string }> = {
  manual: { label: 'Qo\'lda',   icon: <Hand  size={14}/>, color: '#374151', bg: '#F9FAFB'  },
  serial: { label: 'Serial',    icon: <Usb   size={14}/>, color: '#1E3EB4', bg: '#EEF2FF'  },
  api:    { label: 'API/Wi-Fi', icon: <Wifi  size={14}/>, color: '#059669', bg: '#ECFDF5'  },
};

// =============================================================================
// PAGE
// =============================================================================

export default function ScalePage() {
  const { user } = useAuth();
  const qc       = useQueryClient();
  const isAdmin   = user?.role === 'admin';
  const isManager = user?.role === 'admin' || user?.role === 'manager';

  const [activeTab,    setActiveTab]   = useState<'scales' | 'manual' | 'comparison' | 'calibration'>('scales');
  const [showForm,     setShowForm]    = useState(false);
  const [editScale,    setEditScale]   = useState<ScaleData | null>(null);
  const [form,         setForm]        = useState(EMPTY_FORM);
  const [formErr,      setFormErr]     = useState<Record<string, string>>({});
  const [expandedId,   setExpandedId]  = useState<number | null>(null);

  // Manual weight form
  const [mAnimalId,  setMAnimalId]  = useState('');
  const [mWeight,    setMWeight]    = useState('');
  const [mScaleId,   setMScaleId]   = useState('');
  const [mNotes,     setMNotes]     = useState('');
  const [mSuccess,   setMSuccess]   = useState<string | null>(null);
  const [mError,     setMError]     = useState<string | null>(null);

  // Calibration form
  const [calScaleId,   setCalScaleId]   = useState('');
  const [calPoints,    setCalPoints]    = useState<{measurement_id:string; actual_weight_kg:string}[]>([
    { measurement_id: '', actual_weight_kg: '' },
    { measurement_id: '', actual_weight_kg: '' },
    { measurement_id: '', actual_weight_kg: '' },
  ]);
  const [calResult,    setCalResult]    = useState<null | { old: number; new: number; error_kg: number; error_pct: number; message: string }>(null);

  // ─── Queries ──────────────────────────────────────────────────────────────

  const { data: scalesData, isLoading: scalesLoading } = useQuery({
    queryKey: ['scales'],
    queryFn:  () => apiFetch<ScaleListResponse>('/api/v1/scales'),
  });

  const { data: animals } = useQuery({
    queryKey: ['animals-mini'],
    queryFn:  () => apiFetch<{ items: Animal[] }>('/api/v1/animals/?limit=500&status=active'),
  });

  const { data: comparison, isLoading: cmpLoading } = useQuery({
    queryKey: ['weight-comparison'],
    queryFn:  () => apiFetch<ComparisonResponse>('/api/v1/scales/comparison?limit=50'),
    enabled:  activeTab === 'comparison',
  });

  const scales     = scalesData?.items ?? [];
  const animalList = animals?.items    ?? [];

  // ─── Mutations ────────────────────────────────────────────────────────────

  const createMut = useMutation({
    mutationFn: (body: typeof EMPTY_FORM) =>
      apiFetch<ScaleData>('/api/v1/scales', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scales'] }); closeForm(); },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<typeof EMPTY_FORM> }) =>
      apiFetch<ScaleData>(`/api/v1/scales/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scales'] }); closeForm(); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/scales/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scales'] }),
  });

  const manualMut = useMutation({
    mutationFn: (body: object) =>
      apiFetch('/api/v1/scales/weights/manual', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scales'] });
      qc.invalidateQueries({ queryKey: ['weight-comparison'] });
      setMSuccess(`Vazn muvaffaqiyatli saqlandi: ${mWeight} kg`);
      setMWeight(''); setMNotes('');
      setTimeout(() => setMSuccess(null), 4000);
    },
    onError: () => setMError("Xato yuz berdi. Qayta urinib ko'ring."),
  });

  const calMut = useMutation({
    mutationFn: ({ scaleId, points }: { scaleId: number; points: object[] }) =>
      apiFetch<{ old_factor: number; new_factor: number; mean_absolute_error: number; mean_relative_error: number; message: string }>(
        `/api/v1/scales/${scaleId}/calibrate`,
        { method: 'POST', body: JSON.stringify(points) }
      ),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['scales'] });
      setCalResult({ old: res.old_factor, new: res.new_factor, error_kg: res.mean_absolute_error, error_pct: res.mean_relative_error, message: res.message });
    },
  });

  // ─── Handlers ─────────────────────────────────────────────────────────────

  function openCreate() {
    setEditScale(null); setForm(EMPTY_FORM); setFormErr({}); setShowForm(true);
  }
  function openEdit(s: ScaleData) {
    setEditScale(s);
    setForm({ name: s.name, scale_type: s.scale_type, location: s.location ?? '', serial_port: s.serial_port ?? '', baud_rate: s.baud_rate ?? 9600, notes: s.notes ?? '' });
    setFormErr({}); setShowForm(true);
  }
  function closeForm() { setShowForm(false); setEditScale(null); }

  function validate() {
    const e: Record<string, string> = {};
    if (!form.name.trim() || form.name.length < 2) e.name = 'Tarozi nomi kamida 2 ta harf';
    if (form.scale_type === 'serial' && !form.serial_port.trim()) e.serial_port = 'Serial port majburiy';
    setFormErr(e); return Object.keys(e).length === 0;
  }

  function handleFormSubmit() {
    if (!validate()) return;
    const body = { ...form, location: form.location || null, serial_port: form.serial_port || null, notes: form.notes || null };
    if (editScale) updateMut.mutate({ id: editScale.id, body });
    else           createMut.mutate(body as typeof EMPTY_FORM);
  }

  function handleManualSubmit() {
    setMError(null);
    if (!mAnimalId || !mWeight || parseFloat(mWeight) <= 0) {
      setMError('Jonivor va vazn majburiy'); return;
    }
    manualMut.mutate({
      animal_id: parseInt(mAnimalId),
      weight_kg: parseFloat(mWeight),
      scale_id:  mScaleId ? parseInt(mScaleId) : null,
      notes:     mNotes   || null,
    });
  }

  function handleCalibrate() {
    if (!calScaleId) return;
    const valid = calPoints.filter(p => p.measurement_id && p.actual_weight_kg);
    if (valid.length < 3) { alert("Kamida 3 ta to'g'ri nuqta kiriting"); return; }
    calMut.mutate({
      scaleId: parseInt(calScaleId),
      points: valid.map(p => ({
        measurement_id:   parseInt(p.measurement_id),
        actual_weight_kg: parseFloat(p.actual_weight_kg),
      })),
    });
  }

  // ─── Styles ───────────────────────────────────────────────────────────────

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8,
    border: '1px solid #E4E7ED', fontSize: 13,
    fontFamily: "'Outfit',sans-serif", outline: 'none',
    background: '#fff', color: '#0D1117', boxSizing: 'border-box',
  };
  const lbl: React.CSSProperties = {
    fontSize: 12, fontWeight: 600, color: '#374151',
    marginBottom: 5, display: 'block',
  };
  const tab = (active: boolean): React.CSSProperties => ({
    padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontSize: 13, fontWeight: active ? 700 : 500,
    background: active ? '#1E3EB4' : '#F7F8FA',
    color: active ? '#fff' : '#6B7280',
    fontFamily: "'Outfit',sans-serif",
    transition: 'all .15s',
  });

  // ─── Comparison chart data ─────────────────────────────────────────────────
  const chartData = (comparison?.items ?? [])
    .filter(i => i.difference_kg !== null)
    .slice(0, 20)
    .map(i => ({
      tag:  i.animal_tag_id,
      diff: i.difference_kg ? +i.difference_kg.toFixed(1) : 0,
    }));

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div style={{ padding: '24px 20px', maxWidth: 1100, margin: '0 auto' }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
            Tarozi integratsiyasi
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280', fontFamily: "'Outfit',sans-serif" }}>
            Aniq vazn o'lchov, kalibratsiya va AI vs haqiqiy taqqoslash
          </p>
        </div>
        {isAdmin && activeTab === 'scales' && (
          <button onClick={openCreate} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '9px 18px', borderRadius: 9,
            background: '#1E3EB4', color: '#fff', border: 'none',
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
            fontFamily: "'Outfit',sans-serif",
          }}>
            <Plus size={14}/> Yangi tarozi
          </button>
        )}
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button style={tab(activeTab === 'scales')}      onClick={() => setActiveTab('scales')}>
          <Settings size={13} style={{ marginRight: 5, verticalAlign: 'middle' }}/>Tarozlar
        </button>
        {isManager && (
          <button style={tab(activeTab === 'manual')}    onClick={() => setActiveTab('manual')}>
            <Hand size={13} style={{ marginRight: 5, verticalAlign: 'middle' }}/>Qo'lda kiritish
          </button>
        )}
        <button style={tab(activeTab === 'comparison')}  onClick={() => setActiveTab('comparison')}>
          <BarChart2 size={13} style={{ marginRight: 5, verticalAlign: 'middle' }}/>AI vs Haqiqiy
        </button>
        {isManager && (
          <button style={tab(activeTab === 'calibration')} onClick={() => setActiveTab('calibration')}>
            <RefreshCw size={13} style={{ marginRight: 5, verticalAlign: 'middle' }}/>Kalibratsiya
          </button>
        )}
      </div>

      {/* ================================================================= */}
      {/* TAB 1: TAROZLAR RO'YXATI                                          */}
      {/* ================================================================= */}
      {activeTab === 'scales' && (
        <>
          {scalesLoading && (
            <div style={{ display: 'grid', placeItems: 'center', height: 200 }}>
              <div style={{ width: 24, height: 24, border: '2px solid #E4E7ED', borderTopColor: '#1E3EB4', borderRadius: '50%', animation: 'tv-spin .65s linear infinite' }}/>
            </div>
          )}

          {!scalesLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {scales.map(s => {
                const meta    = TYPE_META[s.scale_type];
                const isOpen  = expandedId === s.id;

                return (
                  <div key={s.id} style={{
                    background: '#fff', border: '1px solid #E4E7ED',
                    borderRadius: 14, overflow: 'hidden',
                  }}>
                    {/* Karta header */}
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '16px 20px', cursor: 'pointer',
                    }} onClick={() => setExpandedId(isOpen ? null : s.id)}>

                      {/* Icon */}
                      <div style={{
                        width: 40, height: 40, borderRadius: 10,
                        background: meta.bg, display: 'grid', placeItems: 'center',
                        flexShrink: 0, color: meta.color,
                      }}>
                        {meta.icon}
                      </div>

                      {/* Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 15, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
                            {s.name}
                          </span>
                          <span style={{
                            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
                            background: meta.bg, color: meta.color, fontFamily: "'JetBrains Mono',monospace",
                          }}>
                            {meta.label}
                          </span>
                          {!s.is_active && (
                            <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: '#F3F4F6', color: '#9CA3AF' }}>
                              Nofaol
                            </span>
                          )}
                          {s.is_calibrated && (
                            <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: '#ECFDF5', color: '#059669' }}>
                              Kalibratlangan
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 12, color: '#6B7280', marginTop: 3, fontFamily: "'Outfit',sans-serif" }}>
                          {s.location ?? 'Manzil ko\'rsatilmagan'}
                          {s.last_reading_at && (
                            <span style={{ marginLeft: 12 }}>
                              Oxirgi: {new Date(s.last_reading_at).toLocaleString('uz-UZ')}
                              {s.last_weight_kg && <strong style={{ color: '#0D1117' }}> — {s.last_weight_kg.toFixed(1)} kg</strong>}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Calibration factor */}
                      <div style={{ textAlign: 'center', flexShrink: 0 }}>
                        <div style={{ fontSize: 18, fontWeight: 800, color: Math.abs(s.calibration_factor - 1) < 0.02 ? '#059669' : '#D97706', fontFamily: "'JetBrains Mono',monospace" }}>
                          {s.calibration_factor.toFixed(3)}
                        </div>
                        <div style={{ fontSize: 10, color: '#9CA3AF' }}>faktor</div>
                      </div>

                      {/* Actions */}
                      {isAdmin && (
                        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
                          <button onClick={() => openEdit(s)} style={{
                            width: 32, height: 32, borderRadius: 7, display: 'grid', placeItems: 'center',
                            background: '#F7F8FA', border: '1px solid #E4E7ED', cursor: 'pointer',
                          }}><Edit2 size={13} color="#6B7280"/></button>
                          <button onClick={() => { if (confirm(`"${s.name}" ni o'chirasizmi?`)) deleteMut.mutate(s.id); }} style={{
                            width: 32, height: 32, borderRadius: 7, display: 'grid', placeItems: 'center',
                            background: '#FEF2F2', border: '1px solid #FECACA', cursor: 'pointer',
                          }}><Trash2 size={13} color="#DC2626"/></button>
                        </div>
                      )}

                      <div style={{ color: '#9CA3AF', flexShrink: 0 }}>
                        {isOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
                      </div>
                    </div>

                    {/* Kengaytirilgan tafsilot */}
                    {isOpen && (
                      <div style={{ padding: '0 20px 20px', borderTop: '1px solid #F3F4F6' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 16 }}>
                          <InfoCell label="Tarozi turi"      value={meta.label}/>
                          <InfoCell label="Kalibratsiya namunalari" value={`${s.calibration_sample_count} ta`}/>
                          {s.last_calibrated_at && <InfoCell label="Oxirgi kalibratsiya" value={new Date(s.last_calibrated_at).toLocaleDateString('uz-UZ')}/>}
                          {s.serial_port && <InfoCell label="Serial port" value={s.serial_port}/>}
                          {s.baud_rate   && <InfoCell label="Baud rate"   value={String(s.baud_rate)}/>}
                          {s.notes       && <InfoCell label="Izoh"         value={s.notes}/>}
                        </div>

                        {/* API tarozi uchun webhook yo'riqnomasi */}
                        {(s.scale_type === 'api' || s.scale_type === 'serial') && s.api_token && (
                          <div style={{ marginTop: 16, padding: '14px 16px', borderRadius: 10, background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                              <Info size={13} color="#1E3EB4"/>
                              <span style={{ fontSize: 12, fontWeight: 700, color: '#1E3EB4' }}>Webhook yo'riqnomasi</span>
                            </div>
                            <p style={{ fontSize: 12, color: '#374151', margin: '0 0 8px' }}>
                              Tarozi quyidagi URL ga POST so'rov yuborishi kerak:
                            </p>
                            <code style={{ fontSize: 11, background: '#1E293B', color: '#7DD3FC', padding: '8px 12px', borderRadius: 7, display: 'block', fontFamily: "'JetBrains Mono',monospace" }}>
                              POST /api/v1/scales/{s.id}/webhook
                            </code>
                            <p style={{ fontSize: 12, color: '#374151', margin: '10px 0 4px' }}>Payload:</p>
                            <code style={{ fontSize: 11, background: '#1E293B', color: '#86EFAC', padding: '8px 12px', borderRadius: 7, display: 'block', fontFamily: "'JetBrains Mono',monospace", whiteSpace: 'pre' }}>
{`{
  "api_token": "${s.api_token.slice(0, 8)}...",
  "weight_kg": 245.3,
  "animal_id": 5
}`}
                            </code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {scales.length === 0 && !scalesLoading && (
                <div style={{ textAlign: 'center', padding: '60px 20px', background: '#fff', borderRadius: 14, border: '1px solid #E4E7ED' }}>
                  <Scale size={32} color="#D1D5DB" style={{ margin: '0 auto 12px' }}/>
                  <p style={{ margin: 0, fontSize: 14, color: '#9CA3AF', fontFamily: "'Outfit',sans-serif" }}>
                    Hech qanday tarozi yo'q. Yangi tarozi qo'shing.
                  </p>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ================================================================= */}
      {/* TAB 2: QO'LDA KIRITISH                                            */}
      {/* ================================================================= */}
      {activeTab === 'manual' && isManager && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>

          {/* Form */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, padding: 24 }}>
            <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              Tarozidan vazn kiritish
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={lbl}>Jonivor *</label>
                <select value={mAnimalId} onChange={e => setMAnimalId(e.target.value)} style={{ ...inp, cursor: 'pointer' }}>
                  <option value="">— Jonivorni tanlang —</option>
                  {animalList.map(a => (
                    <option key={a.id} value={a.id}>{a.tag_id} ({a.species})</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={lbl}>Vazn (kg) *</label>
                <input
                  type="number" step="0.1" min="1" max="2000"
                  value={mWeight}
                  onChange={e => setMWeight(e.target.value)}
                  placeholder="Masalan: 245.5"
                  style={inp}
                />
              </div>

              <div>
                <label style={lbl}>Tarozi qurilma</label>
                <select value={mScaleId} onChange={e => setMScaleId(e.target.value)} style={{ ...inp, cursor: 'pointer' }}>
                  <option value="">— Tanlang (ixtiyoriy) —</option>
                  {scales.filter(s => s.is_active).map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={lbl}>Izoh</label>
                <input value={mNotes} onChange={e => setMNotes(e.target.value)} placeholder="Ixtiyoriy izoh..." style={inp}/>
              </div>
            </div>

            {mError && (
              <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8, background: '#FEF2F2', color: '#DC2626', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertTriangle size={13}/> {mError}
              </div>
            )}

            {mSuccess && (
              <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8, background: '#ECFDF5', color: '#059669', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle size={13}/> {mSuccess}
              </div>
            )}

            <button
              onClick={handleManualSubmit}
              disabled={manualMut.isPending}
              style={{
                width: '100%', marginTop: 20, padding: '11px 0', borderRadius: 9,
                background: '#1E3EB4', color: '#fff', border: 'none',
                fontSize: 13, fontWeight: 600, cursor: 'pointer',
                fontFamily: "'Outfit',sans-serif",
                opacity: manualMut.isPending ? 0.7 : 1,
              }}
            >
              {manualMut.isPending ? 'Saqlanmoqda...' : 'Vaznni saqlash'}
            </button>
          </div>

          {/* Yordam */}
          <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 14, padding: 24 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              Qanday ishlaydi?
            </h3>
            <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                'Jonivornni taroziga torting va ko\'rsatgichni kuting',
                'Tarozidagi raqamni yuqoridagi maydonga kiriting',
                'Agar tarozi qurilmangiz ro\'yxatda bo\'lsa — tanlang',
                '"Vaznni saqlash" tugmasini bosing',
                'Saqlangan vazn kalibratsiya va hisobotlarda ko\'rinadi',
              ].map((s, i) => (
                <li key={i} style={{ fontSize: 13, color: '#374151', fontFamily: "'Outfit',sans-serif" }}>{s}</li>
              ))}
            </ol>

            <div style={{ marginTop: 20, padding: '12px 16px', borderRadius: 10, background: '#EEF2FF', border: '1px solid #C7D2FE' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <Info size={13} color="#1E3EB4"/>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#1E3EB4' }}>Muhim</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: '#374151', fontFamily: "'Outfit',sans-serif" }}>
                Qo'lda kiritiladigan vazn confidence_score = 1.0 bilan saqlanadi va kalibratsiya uchun ishlatiladi.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* TAB 3: AI VS HAQIQIY TAQQOSLASH                                   */}
      {/* ================================================================= */}
      {activeTab === 'comparison' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Umumiy statistika */}
          {comparison && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
              <StatCard label="O'lchovlar soni"  value={String(comparison.total)}       sub="taqqoslangan"/>
              <StatCard label="O'rtacha xato"    value={comparison.mean_error_kg ? `${comparison.mean_error_kg.toFixed(1)} kg` : '—'} sub="MAE"/>
              <StatCard label="Nisbiy xato"      value={comparison.mean_error_pct ? `${comparison.mean_error_pct.toFixed(1)}%` : '—'} sub="o'rtacha"
                color={comparison.mean_error_pct && comparison.mean_error_pct > 10 ? '#DC2626' : '#059669'}/>
              <StatCard
                label="Kalibratsiya faktori"
                value={comparison.current_factor.toFixed(3)}
                sub={comparison.recommended_factor ? `Tavsiya: ${comparison.recommended_factor.toFixed(3)}` : 'Faol faktor'}
                color={Math.abs(comparison.current_factor - 1) < 0.02 ? '#059669' : '#D97706'}
              />
            </div>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, padding: 20 }}>
              <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
                AI — Haqiqiy (kg farq)
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} barSize={18}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6"/>
                  <XAxis dataKey="tag" tick={{ fontSize: 10 }}/>
                  <YAxis tick={{ fontSize: 11 }}/>
                  <Tooltip formatter={(v: number) => [`${v > 0 ? '+' : ''}${v} kg`, 'Farq']}/>
                  <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4"/>
                  <Bar dataKey="diff" fill="#1E3EB4" radius={[4,4,0,0]}
                    label={{ position: 'top', fontSize: 10, formatter: (v: number) => v !== 0 ? `${v>0?'+':''}${v}` : '' }}/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Jadval */}
          {cmpLoading ? (
            <div style={{ display: 'grid', placeItems: 'center', height: 100 }}>
              <div style={{ width: 24, height: 24, border: '2px solid #E4E7ED', borderTopColor: '#1E3EB4', borderRadius: '50%', animation: 'tv-spin .65s linear infinite' }}/>
            </div>
          ) : (
            <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#F8FAFC' }}>
                    {['Jonivor', 'Sana', 'AI taxmin', 'Haqiqiy', 'Farq', 'Manba'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#64748B', textTransform: 'uppercase', letterSpacing: '.06em', borderBottom: '1px solid #E2E8F0' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(comparison?.items ?? []).map(row => (
                    <tr key={row.measurement_id} style={{ borderBottom: '1px solid #F8FAFC' }}>
                      <td style={{ padding: '9px 14px', fontWeight: 600, color: '#0D1117' }}>{row.animal_tag_id}</td>
                      <td style={{ padding: '9px 14px', color: '#374151' }}>{new Date(row.timestamp).toLocaleDateString('uz-UZ')}</td>
                      <td style={{ padding: '9px 14px', fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{row.ai_weight_kg.toFixed(1)} kg</td>
                      <td style={{ padding: '9px 14px', fontFamily: "'JetBrains Mono',monospace', fontWeight: 600" }}>
                        {row.actual_weight_kg ? `${row.actual_weight_kg.toFixed(1)} kg` : <span style={{ color: '#D1D5DB' }}>—</span>}
                      </td>
                      <td style={{ padding: '9px 14px' }}>
                        {row.difference_kg != null ? (
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: Math.abs(row.difference_kg) > 10 ? '#DC2626' : '#059669', fontWeight: 600, fontFamily: "'JetBrains Mono',monospace" }}>
                            {row.difference_kg > 0 ? <TrendingUp size={12}/> : <TrendingDown size={12}/>}
                            {row.difference_kg > 0 ? '+' : ''}{row.difference_kg.toFixed(1)} kg
                          </span>
                        ) : <span style={{ color: '#D1D5DB' }}>—</span>}
                      </td>
                      <td style={{ padding: '9px 14px', fontSize: 11, color: '#6B7280' }}>
                        {row.source === 'camera_ai' ? 'Kamera AI' : row.source === 'manual' ? 'Qo\'lda' : row.source}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(comparison?.items ?? []).length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#9CA3AF', fontSize: 13 }}>
                  Hali haqiqiy vazn biriktirilmagan. "Qo'lda kiritish" orqali ma'lumot to'plang.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ================================================================= */}
      {/* TAB 4: KALIBRATSIYA                                               */}
      {/* ================================================================= */}
      {activeTab === 'calibration' && isManager && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>

          {/* Kalibratsiya form */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, padding: 24 }}>
            <h3 style={{ margin: '0 0 4px', fontSize: 16, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              AI kalibratsiyasi
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: 12, color: '#6B7280', fontFamily: "'Outfit',sans-serif" }}>
              AI o'lchov ID va unga mos haqiqiy tarozidan o'qilgan vaznni kiriting.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Tarozi qurilma *</label>
              <select value={calScaleId} onChange={e => setCalScaleId(e.target.value)} style={{ ...inp, cursor: 'pointer' }}>
                <option value="">— Tanlang —</option>
                {scales.filter(s => s.is_active).map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {calPoints.map((p, i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, alignItems: 'center' }}>
                  <div>
                    {i === 0 && <label style={{ ...lbl, marginBottom: 4 }}>O'lchov ID</label>}
                    <input
                      type="number" value={p.measurement_id}
                      onChange={e => setCalPoints(pts => pts.map((x, j) => j === i ? { ...x, measurement_id: e.target.value } : x))}
                      placeholder={`ID #${i+1}`} style={inp}
                    />
                  </div>
                  <div>
                    {i === 0 && <label style={{ ...lbl, marginBottom: 4 }}>Haqiqiy vazn (kg)</label>}
                    <input
                      type="number" step="0.1" value={p.actual_weight_kg}
                      onChange={e => setCalPoints(pts => pts.map((x, j) => j === i ? { ...x, actual_weight_kg: e.target.value } : x))}
                      placeholder={`kg #${i+1}`} style={inp}
                    />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => setCalPoints(p => [...p, { measurement_id: '', actual_weight_kg: '' }])}
              style={{ marginTop: 10, width: '100%', padding: '8px', borderRadius: 8, background: '#F7F8FA', border: '1px dashed #D1D5DB', fontSize: 12, color: '#6B7280', cursor: 'pointer', fontFamily: "'Outfit',sans-serif" }}
            >
              + Yana nuqta qo'shish
            </button>

            <button
              onClick={handleCalibrate}
              disabled={calMut.isPending || !calScaleId}
              style={{
                width: '100%', marginTop: 16, padding: '11px 0', borderRadius: 9,
                background: '#1E3EB4', color: '#fff', border: 'none',
                fontSize: 13, fontWeight: 600, cursor: 'pointer',
                fontFamily: "'Outfit',sans-serif",
                opacity: (calMut.isPending || !calScaleId) ? 0.6 : 1,
              }}
            >
              {calMut.isPending ? 'Hisoblanmoqda...' : 'Kalibratsiyani hisoblash'}
            </button>

            {calResult && (
              <div style={{ marginTop: 16, padding: '16px', borderRadius: 10, background: '#ECFDF5', border: '1px solid #A7F3D0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                  <CheckCircle size={14} color="#059669"/>
                  <span style={{ fontWeight: 700, color: '#059669', fontSize: 13 }}>Kalibratsiya muvaffaqiyatli</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '10px 8px' }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: '#374151', fontFamily: "'JetBrains Mono',monospace" }}>{calResult.old.toFixed(4)}</div>
                    <div style={{ fontSize: 11, color: '#9CA3AF' }}>Eski faktor</div>
                  </div>
                  <div style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '10px 8px' }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: '#059669', fontFamily: "'JetBrains Mono',monospace" }}>{calResult.new.toFixed(4)}</div>
                    <div style={{ fontSize: 11, color: '#9CA3AF' }}>Yangi faktor</div>
                  </div>
                </div>
                <p style={{ margin: '10px 0 0', fontSize: 12, color: '#374151', fontFamily: "'Outfit',sans-serif" }}>
                  O'rtacha xato: <strong>{calResult.error_kg} kg</strong> ({calResult.error_pct}%)
                </p>
              </div>
            )}
          </div>

          {/* Tushuntirish */}
          <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 14, padding: 24 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              Kalibratsiya nima?
            </h3>
            <p style={{ fontSize: 13, color: '#374151', fontFamily: "'Outfit',sans-serif", lineHeight: 1.6 }}>
              AI kamera bbox maydoniga asoslanib taxminiy vazn hisoblaydi. Bu taxmin haqiqiy vazndan farq qilishi mumkin.
              Kalibratsiya bu xatoni tuzatuvchi koeffitsiyentni hisoblaydi.
            </p>
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { step: '1', text: 'Jonivorni kameraga ko\'rsating — AI vazn taxmin qiladi' },
                { step: '2', text: 'Shu jonivorni taroziga torting — haqiqiy vaznni oling' },
                { step: '3', text: 'AI o\'lchov ID va haqiqiy vaznni yuqoridagi formaga kiriting' },
                { step: '4', text: 'Kamida 3 ta juft kerak (5-10 ta yaxshiroq)' },
                { step: '5', text: '"Kalibratsiyani hisoblash" — faktor yangilanadi' },
              ].map(s => (
                <div key={s.step} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#1E3EB4', color: '#fff', display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{s.step}</div>
                  <p style={{ margin: 0, fontSize: 12, color: '#374151', fontFamily: "'Outfit',sans-serif", lineHeight: 1.5 }}>{s.text}</p>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, padding: '12px 14px', borderRadius: 10, background: '#EEF2FF', border: '1px solid #C7D2FE', fontSize: 12, color: '#374151', fontFamily: "'Outfit',sans-serif" }}>
              <strong style={{ color: '#1E3EB4' }}>Algoritm:</strong> Median(haqiqiy / AI_taxmin) — Outlier ga chidamli median koeffitsiyent.
            </div>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* FORM MODAL                                                         */}
      {/* ================================================================= */}
      {showForm && isAdmin && (
        <>
          <div onClick={closeForm} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 100, backdropFilter: 'blur(2px)' }}/>
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: '#fff', borderRadius: 16, padding: 28,
            width: '100%', maxWidth: 460, zIndex: 101,
            boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 17, fontWeight: 800, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              {editScale ? 'Tarozi tahrirlash' : 'Yangi tarozi qo\'shish'}
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={lbl}>Tarozi nomi *</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Masalan: Asosiy tarozi" style={{ ...inp, borderColor: formErr.name ? '#EF4444' : '#E4E7ED' }}/>
                {formErr.name && <p style={{ margin: '4px 0 0', fontSize: 11, color: '#EF4444' }}>{formErr.name}</p>}
              </div>

              <div>
                <label style={lbl}>Turi</label>
                <select value={form.scale_type} onChange={e => setForm(f => ({ ...f, scale_type: e.target.value as 'manual'|'serial'|'api' }))} style={{ ...inp, cursor: 'pointer' }}>
                  <option value="manual">Qo'lda kiritish</option>
                  <option value="serial">Serial / USB</option>
                  <option value="api">API / Wi-Fi</option>
                </select>
              </div>

              <div>
                <label style={lbl}>Joylashuv</label>
                <input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="Masalan: Asosiy molxona kirishi" style={inp}/>
              </div>

              {form.scale_type === 'serial' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={lbl}>Serial port *</label>
                    <input value={form.serial_port} onChange={e => setForm(f => ({ ...f, serial_port: e.target.value }))}
                      placeholder="/dev/ttyUSB0" style={{ ...inp, borderColor: formErr.serial_port ? '#EF4444' : '#E4E7ED' }}/>
                    {formErr.serial_port && <p style={{ margin: '4px 0 0', fontSize: 11, color: '#EF4444' }}>{formErr.serial_port}</p>}
                  </div>
                  <div>
                    <label style={lbl}>Baud rate</label>
                    <select value={form.baud_rate} onChange={e => setForm(f => ({ ...f, baud_rate: parseInt(e.target.value) }))} style={{ ...inp, cursor: 'pointer' }}>
                      {[9600, 19200, 38400, 57600, 115200].map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                </div>
              )}

              <div>
                <label style={lbl}>Izoh</label>
                <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Qo'shimcha ma'lumot..." rows={2} style={{ ...inp, resize: 'vertical' }}/>
              </div>
            </div>

            {(createMut.isError || updateMut.isError) && (
              <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8, background: '#FEF2F2', color: '#DC2626', fontSize: 13 }}>
                Xato yuz berdi. Qayta urinib ko'ring.
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
              <button onClick={closeForm} style={{ flex: 1, padding: '10px 0', borderRadius: 9, background: '#F7F8FA', border: '1px solid #E4E7ED', fontSize: 13, fontWeight: 600, cursor: 'pointer', color: '#374151', fontFamily: "'Outfit',sans-serif" }}>
                Bekor
              </button>
              <button onClick={handleFormSubmit} disabled={createMut.isPending || updateMut.isPending} style={{ flex: 2, padding: '10px 0', borderRadius: 9, background: '#1E3EB4', color: '#fff', border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'Outfit',sans-serif", opacity: (createMut.isPending || updateMut.isPending) ? 0.7 : 1 }}>
                {(createMut.isPending || updateMut.isPending) ? 'Saqlanmoqda...' : (editScale ? 'Saqlash' : 'Qo\'shish')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#F8FAFC', borderRadius: 8, padding: '10px 12px' }}>
      <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', fontFamily: "'Outfit',sans-serif" }}>{value}</div>
    </div>
  );
}

function StatCard({ label, value, sub, color = '#0D1117' }: { label: string; value: string; sub: string; color?: string }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 12, padding: '16px 18px' }}>
      <div style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color, fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>{sub}</div>
    </div>
  );
}