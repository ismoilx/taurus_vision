/**
 * Taurus Vision — Reports & Export Page
 *
 * PDF HISOBOTLAR:
 *   - Bitta jonivor hisoboti (og'irlik, deteksiya tarixi, ADI)
 *   - Ferma umumiy hisobot (xulosa / batafsil / sog'liq)
 *   - Sog'liq hisoboti (alertlar, risk baholash)
 *
 * CSV EKSPORT:
 *   - Jonivorlar CSV (filtrlangan)
 *   - Deteksiyalar CSV (sana oralig'i)
 *
 * EXCEL EKSPORT:
 *   - Jonivorlar Excel — professional, 2 varaqli  ← B7 yangi
 *   - Og'irlik o'lchovlari Excel (har jonivor alohida varaq)
 *   - To'liq arxiv Excel (4 varaqli)
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle, BarChart2, Calendar, CheckCircle,
  Clock, Download, FileSpreadsheet, FileText,
  Heart, Layers, Table, Users,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

interface Animal {
  id:      number;
  tag_id:  string;
  species: string;
  status:  string;
}

interface AnimalListResponse {
  items: Animal[];
  total: number;
}

type DlStatus = 'idle' | 'loading' | 'success' | 'error';

interface DlState {
  status:  DlStatus;
  message: string;
}

// =============================================================================
// HELPERS
// =============================================================================

function today()         { return new Date().toISOString().slice(0, 10); }
function daysAgo(n: number) {
  const d = new Date(); d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

/**
 * Blob yuklab olish — token bilan.
 * Content-Type ni body bor/yo'qligiga qarab belgilaydi.
 */
async function downloadBlob(
  url: string,
  filename: string,
  options?: RequestInit,
): Promise<void> {
  const token = localStorage.getItem('access_token')
    || sessionStorage.getItem('access_token')
    || '';

  const isJson = options?.body !== undefined;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      ...(isJson ? { 'Content-Type': 'application/json' } : {}),
      ...(options?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  const blob = await res.blob();
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// =============================================================================
// DOWNLOAD HOOK
// =============================================================================

function useDownload() {
  const [state, setState] = useState<Record<string, DlState>>({});

  async function run(key: string, fn: () => Promise<void>): Promise<void> {
    setState(p => ({ ...p, [key]: { status: 'loading', message: '' } }));
    try {
      await fn();
      setState(p => ({ ...p, [key]: { status: 'success', message: 'Yuklandi!' } }));
      setTimeout(
        () => setState(p => ({ ...p, [key]: { status: 'idle', message: '' } })),
        3000,
      );
    } catch (err) {
      setState(p => ({
        ...p,
        [key]: {
          status:  'error',
          message: err instanceof Error ? err.message : 'Xato',
        },
      }));
    }
  }

  return { state, run };
}

// =============================================================================
// UI COMPONENTS
// =============================================================================

function SectionHeader({
  icon: Icon, title, subtitle, color = '#1E3EB4',
}: {
  icon: React.ElementType; title: string; subtitle: string; color?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
      <div style={{
        width: 44, height: 44, borderRadius: 11,
        background: `${color}18`,
        display: 'grid', placeItems: 'center', flexShrink: 0,
      }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <h2 style={{ fontSize: 17, fontWeight: 800, color: '#0D1117', margin: 0 }}>{title}</h2>
        <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>{subtitle}</p>
      </div>
    </div>
  );
}

function ReportCard({
  children, highlight = false,
}: {
  children: React.ReactNode; highlight?: boolean;
}) {
  return (
    <div style={{
      background:   '#fff',
      border:       `1px solid ${highlight ? '#C7D2FE' : '#E4E7ED'}`,
      borderRadius: 14,
      padding:      24,
      boxShadow:    highlight
        ? '0 2px 12px rgba(30,62,180,0.08)'
        : '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      {children}
    </div>
  );
}

function DownloadBtn({
  dlKey, state, onClick, label,
  icon: Icon = Download, color = '#1E3EB4',
}: {
  dlKey: string;
  state: DlState | undefined;
  onClick: () => void;
  label: string;
  icon?: React.ElementType;
  color?: string;
}) {
  const s = state?.status ?? 'idle';
  return (
    <button
      onClick={onClick}
      disabled={s === 'loading'}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        width: '100%', padding: '10px 20px',
        background: s === 'loading' ? '#9CA3AF'
                  : s === 'success'  ? '#10B981'
                  : s === 'error'    ? '#FEF2F2'
                  : color,
        color:  s === 'error' ? '#DC2626' : '#fff',
        border: s === 'error' ? '1px solid #FECACA' : 'none',
        borderRadius: 8, fontSize: 13, fontWeight: 700,
        cursor: s === 'loading' ? 'not-allowed' : 'pointer',
        fontFamily: 'Outfit, sans-serif',
        transition: 'background .15s, transform .1s',
        whiteSpace: 'nowrap',
      }}
    >
      {s === 'loading' ? (
        <div style={{
          width: 14, height: 14, borderRadius: '50%',
          border: '2px solid rgba(255,255,255,0.4)',
          borderTopColor: '#fff',
          animation: 'spin .7s linear infinite',
        }} />
      ) : s === 'success' ? (
        <CheckCircle size={14} />
      ) : s === 'error' ? (
        <AlertCircle size={14} />
      ) : (
        <Icon size={14} />
      )}
      {s === 'loading' ? 'Yuklanmoqda...'
     : s === 'success'  ? 'Yuklandi!'
     : s === 'error'    ? (state?.message?.slice(0, 35) || 'Xato')
     : label}
    </button>
  );
}

// Kichik info blok
function InfoBox({
  children, color, bg, border,
}: {
  children: React.ReactNode;
  color: string; bg: string; border: string;
}) {
  return (
    <div style={{
      padding: '10px 12px', background: bg,
      border: `1px solid ${border}`, borderRadius: 8, marginBottom: 14,
    }}>
      <p style={{ fontSize: 11, color, margin: 0, lineHeight: 1.6 }}>{children}</p>
    </div>
  );
}

// =============================================================================
// INPUT STYLES
// =============================================================================

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  border: '1px solid #D1D5DB', borderRadius: 8,
  fontSize: 13, color: '#0D1117', outline: 'none',
  fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 600,
  color: '#374151', marginBottom: 5,
};

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ReportsPage() {
  const { state: dl, run } = useDownload();

  // Jonivorlar ro'yxati (PDF va Excel selectorlar uchun)
  const { data: animalsRes, isLoading: loadingAnimals } = useQuery({
    queryKey:  ['animals', 'list-200'],
    queryFn:   () => apiFetch<AnimalListResponse>('/api/v1/animals/?limit=200'),
    staleTime: 60_000,
  });
  const animals = animalsRes?.items ?? [];

  // ─── PDF holatlari ───────────────────────────────────────────────────────
  const [animalId,  setAnimalId]  = useState('');
  const [farmFrom,  setFarmFrom]  = useState(daysAgo(30));
  const [farmTo,    setFarmTo]    = useState(today());
  const [farmType,  setFarmType]  = useState<'summary' | 'detailed' | 'health'>('summary');
  const [healthIds, setHealthIds] = useState('');

  // ─── CSV holatlari ───────────────────────────────────────────────────────
  const [csvStatus,  setCsvStatus]  = useState('');
  const [csvSpecies, setCsvSpecies] = useState('');
  const [detFrom,    setDetFrom]    = useState(daysAgo(7));
  const [detTo,      setDetTo]      = useState(today());
  const [detAnimal,  setDetAnimal]  = useState('');

  // ─── Excel holatlari ─────────────────────────────────────────────────────
  const [xlsStatus,  setXlsStatus]  = useState('');   // B7: Animals Excel filtr
  const [xlsSpecies, setXlsSpecies] = useState('');   // B7
  const [wExcelIds,  setWExcelIds]  = useState('');   // Weights Excel

  // ==========================================================================
  // DOWNLOAD HANDLERS
  // ==========================================================================

  // PDF — bitta jonivor
  async function dlAnimalPdf() {
    if (!animalId) return;
    const id     = parseInt(animalId);
    const animal = animals.find(a => a.id === id);
    await downloadBlob(
      `/api/v1/reports/generate/animal/${id}`,
      `animal_${animal?.tag_id || id}_${today()}.pdf`,
      { method: 'POST' },
    );
  }

  // PDF — ferma
  async function dlFarmPdf() {
    await downloadBlob(
      '/api/v1/reports/generate/farm',
      `farm_${farmType}_${farmFrom}_${farmTo}.pdf`,
      {
        method: 'POST',
        body:   JSON.stringify({ date_from: farmFrom, date_to: farmTo, report_type: farmType }),
      },
    );
  }

  // PDF — sog'liq
  async function dlHealthPdf() {
    const ids = healthIds
      ? healthIds.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
      : null;
    await downloadBlob(
      '/api/v1/reports/generate/health',
      `health_report_${today()}.pdf`,
      { method: 'POST', body: JSON.stringify({ animal_ids: ids }) },
    );
  }

  // CSV — jonivorlar
  async function dlAnimalsCsv() {
    const body: Record<string, string> = {};
    if (csvStatus)  body.status  = csvStatus;
    if (csvSpecies) body.species = csvSpecies;
    await downloadBlob(
      '/api/v1/export/animals/csv',
      `animals_${today()}.csv`,
      { method: 'POST', body: JSON.stringify(body) },
    );
  }

  // CSV — deteksiyalar
  async function dlDetectionsCsv() {
    const body: Record<string, unknown> = { date_from: detFrom, date_to: detTo };
    if (detAnimal) body.animal_id = parseInt(detAnimal);
    await downloadBlob(
      '/api/v1/export/detections/csv',
      `detections_${detFrom}_${detTo}.csv`,
      { method: 'POST', body: JSON.stringify(body) },
    );
  }

  // Excel — jonivorlar (B7)
  async function dlAnimalsExcel() {
    const params = new URLSearchParams();
    if (xlsStatus)  params.set('status',  xlsStatus);
    if (xlsSpecies) params.set('species', xlsSpecies);
    const qs = params.toString() ? `?${params.toString()}` : '';
    await downloadBlob(
      `/api/v1/export/animals/excel${qs}`,
      `animals_${today()}.xlsx`,
    );
  }

  // Excel — og'irliklar
  async function dlWeightsExcel() {
    const ids = wExcelIds
      ? wExcelIds.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
      : null;
    await downloadBlob(
      '/api/v1/export/weights/excel',
      `weights_${today()}.xlsx`,
      { method: 'POST', body: JSON.stringify({ animal_ids: ids }) },
    );
  }

  // Excel — to'liq arxiv
  async function dlAllExcel() {
    await downloadBlob(
      '/api/v1/export/all/excel',
      `farm_data_complete_${today()}.xlsx`,
    );
  }

  // ==========================================================================
  // RENDER
  // ==========================================================================

  return (
    <div style={{
      maxWidth: 1200, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>

      {/* ─── Page header ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
          Hisobotlar & Eksport
        </h1>
        <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
          PDF hisobotlar yaratish va ma'lumotlarni CSV / Excel formatda yuklab olish
        </p>
      </div>

      {/* ─── Quick stats ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 14, marginBottom: 36,
      }}>
        {[
          { icon: FileText,        label: 'PDF Hisobotlar',  value: '3 tur',   color: '#DC2626', bg: '#FEF2F2' },
          { icon: Table,           label: 'CSV Eksport',     value: '2 tur',   color: '#059669', bg: '#F0FDF4' },
          { icon: FileSpreadsheet, label: 'Excel Eksport',   value: '3 tur',   color: '#1D4ED8', bg: '#EFF6FF' },
          { icon: Layers,          label: "To'liq Arxiv",    value: 'Excel',   color: '#7C3AED', bg: '#F5F3FF' },
        ].map(({ icon: Icon, label, value, color, bg }) => (
          <div key={label} style={{
            background: '#fff', border: '1px solid #E4E7ED',
            borderRadius: 12, padding: '14px 18px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 9,
              background: bg, display: 'grid', placeItems: 'center', flexShrink: 0,
            }}>
              <Icon size={17} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280' }}>{label}</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#0D1117' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ================================================================== */}
      {/* PDF HISOBOTLAR                                                       */}
      {/* ================================================================== */}

      <div style={{ marginBottom: 40 }}>
        <SectionHeader
          icon={FileText}
          title="PDF Hisobotlar"
          subtitle="Professional PDF fayllar — bosib chiqarish yoki yuborish uchun"
          color="#DC2626"
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>

          {/* Jonivor PDF */}
          <ReportCard highlight>
            <CardIcon icon={BarChart2} color="#DC2626" bg="#FEF2F2" />
            <CardTitle title="Jonivor Hisoboti" sub="Og'irlik · Deteksiya · ADI" />

            <div style={{ marginBottom: 14 }}>
              <label style={labelStyle}>Jonivor tanlash</label>
              <select
                value={animalId}
                onChange={e => setAnimalId(e.target.value)}
                style={inputStyle}
              >
                <option value="">— Jonivor tanlang —</option>
                {animals.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.tag_id} · {a.species}
                  </option>
                ))}
              </select>
              {loadingAnimals && (
                <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>Yuklanmoqda...</p>
              )}
            </div>

            <DownloadBtn
              dlKey="animal-pdf" state={dl['animal-pdf']}
              onClick={() => run('animal-pdf', dlAnimalPdf)}
              label="PDF Yuklab Olish"
              icon={FileText}
              color={animalId ? '#DC2626' : '#9CA3AF'}
            />
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '10px 0 0', lineHeight: 1.5 }}>
              Og'irlik tarixi, deteksiya vaqtlari, ADI ko'rsatkichi va batafsil statistika
            </p>
          </ReportCard>

          {/* Ferma PDF */}
          <ReportCard highlight>
            <CardIcon icon={Layers} color="#EA580C" bg="#FFF7ED" />
            <CardTitle title="Ferma Hisoboti" sub="Umumiy statistika · Trendlar" />

            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Hisobot turi</label>
              <div style={{ display: 'flex', gap: 6 }}>
                {([ ['summary', 'Xulosa'], ['detailed', "Batafsil"], ['health', "Sog'liq"] ] as const).map(
                  ([key, lbl]) => (
                    <button key={key} onClick={() => setFarmType(key)} style={{
                      flex: 1, padding: '7px 4px',
                      border: `1px solid ${farmType === key ? '#EA580C' : '#D1D5DB'}`,
                      borderRadius: 7,
                      background: farmType === key ? '#FFF7ED' : '#fff',
                      color:      farmType === key ? '#EA580C' : '#6B7280',
                      fontSize: 11, fontWeight: farmType === key ? 700 : 500,
                      cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                    }}>{lbl}</button>
                  )
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              <div>
                <label style={labelStyle}>Boshlanish</label>
                <input type="date" value={farmFrom} onChange={e => setFarmFrom(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Tugash</label>
                <input type="date" value={farmTo} onChange={e => setFarmTo(e.target.value)} style={inputStyle} />
              </div>
            </div>

            <QuickDates current={farmFrom} onSelect={from => { setFarmFrom(from); setFarmTo(today()); }} color="#EA580C" />

            <DownloadBtn
              dlKey="farm-pdf" state={dl['farm-pdf']}
              onClick={() => run('farm-pdf', dlFarmPdf)}
              label="PDF Yuklab Olish"
              icon={FileText}
              color="#EA580C"
            />
          </ReportCard>

          {/* Sog'liq PDF */}
          <ReportCard highlight>
            <CardIcon icon={Heart} color="#059669" bg="#F0FDF4" />
            <CardTitle title="Sog'liq Hisoboti" sub="Alertlar · Risk baholash" />

            <div style={{ marginBottom: 10 }}>
              <label style={labelStyle}>
                Jonivor IDlar{' '}
                <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <input
                type="text" value={healthIds}
                onChange={e => setHealthIds(e.target.value)}
                placeholder="1, 2, 3 — bo'sh = hammasi"
                style={inputStyle}
              />
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>
                Bo'sh → barcha aktiv jonivorlar uchun
              </p>
            </div>

            <InfoBox color="#065F46" bg="#F0FDF4" border="#A7F3D0">
              Hisobot o'z ichiga oladi: og'irlik yo'qotish alertlari (≥5%),
              7+ kun ko'rinmagan jonivorlar, umumiy sog'liq skori va tavsiyalar
            </InfoBox>

            <DownloadBtn
              dlKey="health-pdf" state={dl['health-pdf']}
              onClick={() => run('health-pdf', dlHealthPdf)}
              label="PDF Yuklab Olish"
              icon={FileText}
              color="#059669"
            />
          </ReportCard>

        </div>
      </div>

      {/* ================================================================== */}
      {/* CSV EKSPORT                                                          */}
      {/* ================================================================== */}

      <div style={{ marginBottom: 40 }}>
        <SectionHeader
          icon={Table}
          title="CSV Eksport"
          subtitle="Elektron jadval, Python / R tahlili uchun CSV fayllar"
          color="#059669"
        />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

          {/* Jonivorlar CSV */}
          <ReportCard>
            <CardIcon icon={Users} color="#059669" bg="#F0FDF4" />
            <CardTitle title="Jonivorlar CSV" sub="Tag ID, tur, holat, zot, deteksiya soni" />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>Holat</label>
                <select value={csvStatus} onChange={e => setCsvStatus(e.target.value)} style={inputStyle}>
                  <option value="">Barchasi</option>
                  <option value="active">Faol</option>
                  <option value="sick">Kasal</option>
                  <option value="quarantine">Karantin</option>
                  <option value="sold">Sotilgan</option>
                  <option value="deceased">Vafot etgan</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Tur</label>
                <select value={csvSpecies} onChange={e => setCsvSpecies(e.target.value)} style={inputStyle}>
                  <option value="">Barchasi</option>
                  <option value="cattle">Qoramol</option>
                  <option value="sheep">Qo'y</option>
                  <option value="goat">Echki</option>
                  <option value="horse">Ot</option>
                  <option value="other">Boshqa</option>
                </select>
              </div>
            </div>

            <DownloadBtn
              dlKey="animals-csv" state={dl['animals-csv']}
              onClick={() => run('animals-csv', dlAnimalsCsv)}
              label="CSV Yuklab Olish"
              icon={Download}
              color="#059669"
            />
          </ReportCard>

          {/* Deteksiyalar CSV */}
          <ReportCard>
            <CardIcon icon={Clock} color="#059669" bg="#F0FDF4" />
            <CardTitle title="Deteksiyalar CSV" sub="Vaqt, kamera, ishonch, bbox koordinatalari" />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              <div>
                <label style={labelStyle}>Boshlanish *</label>
                <input type="date" value={detFrom} onChange={e => setDetFrom(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Tugash *</label>
                <input type="date" value={detTo} onChange={e => setDetTo(e.target.value)} style={inputStyle} />
              </div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={labelStyle}>
                Jonivor{' '}
                <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <select value={detAnimal} onChange={e => setDetAnimal(e.target.value)} style={inputStyle}>
                <option value="">Barcha jonivorlar</option>
                {animals.map(a => (
                  <option key={a.id} value={a.id}>{a.tag_id}</option>
                ))}
              </select>
            </div>

            <QuickDates
              current={detFrom}
              onSelect={from => { setDetFrom(from); setDetTo(today()); }}
              color="#059669"
              options={[
                { label: 'Bugun', from: today() },
                { label: '7 kun', from: daysAgo(7) },
                { label: '30 kun', from: daysAgo(30) },
              ]}
            />

            <DownloadBtn
              dlKey="detections-csv" state={dl['detections-csv']}
              onClick={() => run('detections-csv', dlDetectionsCsv)}
              label="CSV Yuklab Olish"
              icon={Download}
              color="#059669"
            />
          </ReportCard>

        </div>
      </div>

      {/* ================================================================== */}
      {/* EXCEL EKSPORT                                                        */}
      {/* ================================================================== */}

      <div>
        <SectionHeader
          icon={FileSpreadsheet}
          title="Excel Eksport"
          subtitle="Professional .xlsx fayllar — ko'p varaqli, formatlangan"
          color="#1D4ED8"
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>

          {/* ─── B7: JONIVORLAR EXCEL (yangi) ──────────────────────────── */}
          <ReportCard highlight>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              background: '#EFF6FF', border: '1px solid #BFDBFE',
              borderRadius: 20, padding: '3px 10px',
              marginBottom: 12,
            }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#1D4ED8', letterSpacing: 0.5 }}>
                B7 · YANGI
              </span>
            </div>

            <CardIcon icon={Users} color="#1D4ED8" bg="#EFF6FF" />
            <CardTitle
              title="Jonivorlar Excel"
              sub="Professional formatlash · 2 varaqli"
            />

            {/* Filtrlar */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              <div>
                <label style={labelStyle}>Holat</label>
                <select value={xlsStatus} onChange={e => setXlsStatus(e.target.value)} style={inputStyle}>
                  <option value="">Barchasi</option>
                  <option value="active">Faol</option>
                  <option value="sick">Kasal</option>
                  <option value="quarantine">Karantin</option>
                  <option value="sold">Sotilgan</option>
                  <option value="deceased">Vafot etgan</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Tur</label>
                <select value={xlsSpecies} onChange={e => setXlsSpecies(e.target.value)} style={inputStyle}>
                  <option value="">Barchasi</option>
                  <option value="cattle">Qoramol</option>
                  <option value="sheep">Qo'y</option>
                  <option value="goat">Echki</option>
                  <option value="horse">Ot</option>
                  <option value="other">Boshqa</option>
                </select>
              </div>
            </div>

            {/* Tarkib haqida ma'lumot */}
            <InfoBox color="#1E40AF" bg="#EFF6FF" border="#BFDBFE">
              <strong>Fayl tarkibi:</strong><br />
              📋 Varaq 1 — Ro'yxat: holat ranglari, muzlatilgan sarlavha<br />
              📊 Varaq 2 — Statistika: tur / holat taqsimot
            </InfoBox>

            <DownloadBtn
              dlKey="animals-excel" state={dl['animals-excel']}
              onClick={() => run('animals-excel', dlAnimalsExcel)}
              label="Excel Yuklab Olish"
              icon={FileSpreadsheet}
              color="#1D4ED8"
            />
          </ReportCard>

          {/* ─── OG'IRLIK EXCEL ──────────────────────────────────────── */}
          <ReportCard>
            <CardIcon icon={BarChart2} color="#1D4ED8" bg="#EFF6FF" />
            <CardTitle title="Og'irlik Excel" sub="Har jonivor uchun alohida varaq" />

            <div style={{ marginBottom: 10 }}>
              <label style={labelStyle}>
                Jonivor IDlar{' '}
                <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <input
                type="text" value={wExcelIds}
                onChange={e => setWExcelIds(e.target.value)}
                placeholder="1, 2, 3 — bo'sh = hammasi"
                style={inputStyle}
              />
            </div>

            <InfoBox color="#1E40AF" bg="#EFF6FF" border="#BFDBFE">
              <strong>Fayl tarkibi:</strong><br />
              📊 Varaq 1 — Xulosa (barcha jonivorlar)<br />
              📋 Varaq 2+ — Har bir jonivor uchun alohida
            </InfoBox>

            <DownloadBtn
              dlKey="weights-excel" state={dl['weights-excel']}
              onClick={() => run('weights-excel', dlWeightsExcel)}
              label="Excel Yuklab Olish"
              icon={FileSpreadsheet}
              color="#1D4ED8"
            />
          </ReportCard>

          {/* ─── TO'LIQ ARXIV ───────────────────────────────────────── */}
          <ReportCard>
            <CardIcon icon={Layers} color="#7C3AED" bg="#F5F3FF" />
            <CardTitle title="To'liq Arxiv Excel" sub="Barcha ma'lumotlar bitta faylda" />

            {/* 4 varaq */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
              {[
                { n: '1', text: 'Jonivorlar',           color: '#7C3AED', bg: '#F5F3FF' },
                { n: '2', text: 'Deteksiyalar (30 kun)', color: '#1D4ED8', bg: '#EFF6FF' },
                { n: '3', text: "Og'irlik o'lchovlari", color: '#059669', bg: '#F0FDF4' },
                { n: '4', text: 'Statistika',           color: '#DC2626', bg: '#FEF2F2' },
              ].map(({ n, text, color, bg }) => (
                <div key={n} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 10px',
                  background: bg, border: `1px solid ${color}22`,
                  borderRadius: 7,
                }}>
                  <FileSpreadsheet size={11} color={color} />
                  <span style={{ fontSize: 11, fontWeight: 700, color }}>Varaq {n}:</span>
                  <span style={{ fontSize: 11, color: '#374151' }}>{text}</span>
                </div>
              ))}
            </div>

            <InfoBox color="#92400E" bg="#FFFBEB" border="#FDE68A">
              ⚠ Katta fermalarda fayl 100MB+ bo'lishi mumkin.
              Kichik eksportlar uchun yuqoridagi variantlardan foydalaning.
            </InfoBox>

            <DownloadBtn
              dlKey="all-excel" state={dl['all-excel']}
              onClick={() => run('all-excel', dlAllExcel)}
              label="To'liq Excel Yuklab Olish"
              icon={FileSpreadsheet}
              color="#7C3AED"
            />
          </ReportCard>

        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

// =============================================================================
// LOCAL HELPERS (faqat shu fayl uchun)
// =============================================================================

function CardIcon({
  icon: Icon, color, bg,
}: { icon: React.ElementType; color: string; bg: string }) {
  return (
    <div style={{
      width: 36, height: 36, borderRadius: 8,
      background: bg, display: 'grid', placeItems: 'center',
      marginBottom: 10, flexShrink: 0,
    }}>
      <Icon size={16} color={color} />
    </div>
  );
}

function CardTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>{title}</div>
      <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function QuickDates({
  current, onSelect, color,
  options = [
    { label: '7 kun',  from: '' },
    { label: '30 kun', from: '' },
    { label: '90 kun', from: '' },
  ],
}: {
  current: string;
  onSelect: (from: string) => void;
  color: string;
  options?: { label: string; from: string }[];
}) {
  // Agar from bo'sh bo'lsa, daysAgo bilan hisoblash
  const today0 = new Date().toISOString().slice(0, 10);
  const resolved = options.map(o => ({
    label: o.label,
    from:  o.from || (() => {
      const days = parseInt(o.label);
      if (isNaN(days)) return today0;
      const d = new Date(); d.setDate(d.getDate() - days);
      return d.toISOString().slice(0, 10);
    })(),
  }));

  return (
    <div style={{ display: 'flex', gap: 5, marginBottom: 12 }}>
      {resolved.map(({ label, from }) => (
        <button key={label} onClick={() => onSelect(from)} style={{
          flex: 1, padding: '5px 0',
          border: '1px solid #E5E7EB', borderRadius: 6,
          background: current === from ? `${color}14` : '#fff',
          color:      current === from ? color          : '#9CA3AF',
          fontSize: 11, fontWeight: current === from ? 700 : 500,
          cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          transition: 'all .15s',
        }}>
          {label}
        </button>
      ))}
    </div>
  );
}