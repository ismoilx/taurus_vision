/**
 * Taurus Vision — Reports & Export Page (Sprint 13)
 *
 * PDF hisobotlar va ma'lumotlar eksporti.
 *
 * PDF HISOBOTLAR:
 *   - Bitta jonivor hisoboti (og'irlik, deteksiya tarixi)
 *   - Ferma umumiy hisobot (haftalik / oylik / choraklik)
 *   - Sog'liq hisoboti (alertlar, risk baholash)
 *
 * EKSPORT:
 *   - Jonivorlar CSV
 *   - Deteksiyalar CSV (sana oralig'i)
 *   - Og'irlik o'lchovlari Excel (multi-sheet)
 *   - Barcha ma'lumotlar Excel (to'liq arxiv)
 */

import { useState, useEffect } from 'react';
import {
  FileText, Download, AlertCircle, CheckCircle,
  Calendar, BarChart2, Heart, Layers, Table,
  ChevronRight, RefreshCw, Clock, FileSpreadsheet,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Animal {
  id:      number;
  tag_id:  string;
  species: string;
  status:  string;
}

type ReportStatus = 'idle' | 'loading' | 'success' | 'error';

interface DownloadState {
  status:  ReportStatus;
  message: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function today() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

async function downloadBlob(url: string, filename: string, options?: RequestInit): Promise<void> {
  const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
  const res = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Server xatosi' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function useDownload() {
  const [state, setState] = useState<Record<string, DownloadState>>({});

  async function run(key: string, fn: () => Promise<void>) {
    setState(p => ({ ...p, [key]: { status: 'loading', message: '' } }));
    try {
      await fn();
      setState(p => ({ ...p, [key]: { status: 'success', message: 'Yuklandi!' } }));
      setTimeout(() => setState(p => ({ ...p, [key]: { status: 'idle', message: '' } })), 3000);
    } catch (err) {
      setState(p => ({
        ...p,
        [key]: { status: 'error', message: err instanceof Error ? err.message : 'Xato' },
      }));
    }
  }

  return { state, run };
}

// ---------------------------------------------------------------------------
// Section Header
// ---------------------------------------------------------------------------

function SectionHeader({ icon: Icon, title, subtitle, color = '#1E3EB4' }: {
  icon: any; title: string; subtitle: string; color?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
      <div style={{
        width: 44, height: 44, borderRadius: 11,
        background: `${color}14`,
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

// ---------------------------------------------------------------------------
// Download Button
// ---------------------------------------------------------------------------

function DownloadBtn({
  dlKey, state, onClick, label, icon: Icon = Download, color = '#1E3EB4',
}: {
  dlKey: string; state: DownloadState | undefined;
  onClick: () => void; label: string;
  icon?: any; color?: string;
}) {
  const s = state?.status ?? 'idle';
  return (
    <button onClick={onClick} disabled={s === 'loading'} style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      padding: '10px 20px',
      background: s === 'loading' ? '#9CA3AF'
               : s === 'success'  ? '#10B981'
               : s === 'error'    ? '#FEF2F2'
               : color,
      color: s === 'error' ? '#DC2626' : '#fff',
      border: s === 'error' ? '1px solid #FECACA' : 'none',
      borderRadius: 8, fontSize: 13, fontWeight: 700,
      cursor: s === 'loading' ? 'not-allowed' : 'pointer',
      fontFamily: 'Outfit, sans-serif', transition: 'background .15s',
      whiteSpace: 'nowrap',
    }}>
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
     : s === 'error'    ? (state?.message?.slice(0, 30) || 'Xato')
     : label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Report Card
// ---------------------------------------------------------------------------

function ReportCard({ children, highlight = false }: { children: React.ReactNode; highlight?: boolean }) {
  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${highlight ? '#C7D2FE' : '#E4E7ED'}`,
      borderRadius: 14,
      padding: 24,
      boxShadow: highlight ? '0 2px 8px rgba(30,62,180,0.07)' : '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Input helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const { state: dl, run } = useDownload();

  // Animals list (for animal report selector)
  const [animals, setAnimals]     = useState<Animal[]>([]);
  const [loadingAnimals, setLA]   = useState(true);

  // PDF: Animal report
  const [animalId, setAnimalId]   = useState('');

  // PDF: Farm report
  const [farmFrom, setFarmFrom]   = useState(daysAgo(30));
  const [farmTo, setFarmTo]       = useState(today());
  const [farmType, setFarmType]   = useState<'summary' | 'detailed' | 'health'>('summary');

  // PDF: Health report
  const [healthIds, setHealthIds] = useState('');   // comma-separated

  // CSV: Animals
  const [csvStatus, setCsvStatus] = useState('');
  const [csvSpecies, setCsvSpecies] = useState('');

  // CSV: Detections
  const [detFrom, setDetFrom]     = useState(daysAgo(7));
  const [detTo, setDetTo]         = useState(today());
  const [detAnimal, setDetAnimal] = useState('');

  // Excel: Weights
  const [wExcelIds, setWExcelIds] = useState('');

  useEffect(() => {
    apiFetch<{ items: Animal[] }>('/api/v1/animals/?limit=200')
      .then(d => setAnimals(d.items || []))
      .catch(() => {})
      .finally(() => setLA(false));
  }, []);

  // ─── DOWNLOAD HANDLERS ──────────────────────────────────────────────────

  // PDF: single animal
  async function dlAnimalPdf() {
    if (!animalId) return;
    const id = parseInt(animalId);
    const animal = animals.find(a => a.id === id);
    const fname = `animal_${animal?.tag_id || id}_${today()}.pdf`;
    await downloadBlob(
      `/api/v1/reports/generate/animal/${id}`,
      fname,
      { method: 'POST' },
    );
  }

  // PDF: farm
  async function dlFarmPdf() {
    const fname = `farm_${farmType}_${farmFrom}_${farmTo}.pdf`;
    await downloadBlob(
      '/api/v1/reports/generate/farm',
      fname,
      {
        method: 'POST',
        body: JSON.stringify({ date_from: farmFrom, date_to: farmTo, report_type: farmType }),
      },
    );
  }

  // PDF: health
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

  // CSV: animals
  async function dlAnimalsCsv() {
    const body: any = {};
    if (csvStatus)  body.status  = csvStatus;
    if (csvSpecies) body.species = csvSpecies;
    await downloadBlob(
      '/api/v1/export/animals/csv',
      `animals_${today()}.csv`,
      { method: 'POST', body: JSON.stringify(body) },
    );
  }

  // CSV: detections
  async function dlDetectionsCsv() {
    const body: any = { date_from: detFrom, date_to: detTo };
    if (detAnimal) body.animal_id = parseInt(detAnimal);
    await downloadBlob(
      '/api/v1/export/detections/csv',
      `detections_${detFrom}_${detTo}.csv`,
      { method: 'POST', body: JSON.stringify(body) },
    );
  }

  // Excel: weights
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

  // Excel: all data
  async function dlAllExcel() {
    await downloadBlob(
      '/api/v1/export/all/excel',
      `farm_data_complete_${today()}.xlsx`,
    );
  }

  // ─── RENDER ─────────────────────────────────────────────────────────────

  return (
    <div style={{
      maxWidth: 1200, margin: '0 auto',
      padding: '32px 24px',
      fontFamily: 'Outfit, sans-serif',
    }}>

      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
          Hisobotlar & Eksport
        </h1>
        <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
          PDF hisobotlar yaratish va ma'lumotlarni CSV / Excel formatda yuklab olish
        </p>
      </div>

      {/* Quick stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 32 }}>
        {[
          { icon: FileText,        label: 'PDF Hisobotlar',  value: '3 tur',   color: '#DC2626', bg: '#FEF2F2' },
          { icon: Table,           label: 'CSV Eksport',     value: '2 tur',   color: '#059669', bg: '#F0FDF4' },
          { icon: FileSpreadsheet, label: 'Excel Eksport',   value: '2 tur',   color: '#1D4ED8', bg: '#EFF6FF' },
          { icon: Layers,          label: "To'liq Arxiv",    value: 'Excel',   color: '#7C3AED', bg: '#F5F3FF' },
        ].map(({ icon: Icon, label, value, color, bg }) => (
          <div key={label} style={{
            background: '#fff', border: '1px solid #E4E7ED',
            borderRadius: 12, padding: '14px 18px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{ width: 38, height: 38, borderRadius: 9, background: bg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
              <Icon size={17} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280' }}>{label}</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#0D1117' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* PDF HISOBOTLAR                                              */}
      {/* ═══════════════════════════════════════════════════════════ */}

      <div style={{ marginBottom: 32 }}>
        <SectionHeader
          icon={FileText}
          title="PDF Hisobotlar"
          subtitle="Professional PDF fayllar — bosib chiqarish yoki yuborish uchun"
          color="#DC2626"
        />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>

          {/* Animal PDF */}
          <ReportCard highlight>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: '#FEF2F2', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <BarChart2 size={16} color="#DC2626" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Jonivor Hisoboti</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Og'irlik · Deteksiya · Sog'liq</div>
              </div>
            </div>

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

            <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>
              Og'irlik tarixi, deteksiya vaqtlari, ADI ko'rsatkichi va batafsil statistika
            </div>
          </ReportCard>

          {/* Farm PDF */}
          <ReportCard highlight>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: '#FFF7ED', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Layers size={16} color="#EA580C" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Ferma Hisoboti</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Umumiy statistika · Trendlar</div>
              </div>
            </div>

            {/* Report type */}
            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Hisobot turi</label>
              <div style={{ display: 'flex', gap: 6 }}>
                {([
                  { key: 'summary',  label: 'Xulosa' },
                  { key: 'detailed', label: "Batafsil" },
                  { key: 'health',   label: "Sog'liq" },
                ] as const).map(({ key, label }) => (
                  <button key={key} onClick={() => setFarmType(key)} style={{
                    flex: 1, padding: '7px 4px',
                    border: `1px solid ${farmType === key ? '#EA580C' : '#D1D5DB'}`,
                    borderRadius: 7, background: farmType === key ? '#FFF7ED' : '#fff',
                    color: farmType === key ? '#EA580C' : '#6B7280',
                    fontSize: 11, fontWeight: farmType === key ? 700 : 500,
                    cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                  }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
              <div>
                <label style={labelStyle}>Boshlanish</label>
                <input type="date" value={farmFrom} onChange={e => setFarmFrom(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Tugash</label>
                <input type="date" value={farmTo} onChange={e => setFarmTo(e.target.value)} style={inputStyle} />
              </div>
            </div>

            {/* Quick presets */}
            <div style={{ display: 'flex', gap: 5, marginBottom: 14 }}>
              {[
                { label: '7 kun',  from: daysAgo(7) },
                { label: '30 kun', from: daysAgo(30) },
                { label: '90 kun', from: daysAgo(90) },
              ].map(({ label, from }) => (
                <button key={label} onClick={() => { setFarmFrom(from); setFarmTo(today()); }}
                  style={{
                    flex: 1, padding: '5px 0',
                    border: '1px solid #E5E7EB', borderRadius: 6,
                    background: farmFrom === from ? '#FFF7ED' : '#fff',
                    color: farmFrom === from ? '#EA580C' : '#9CA3AF',
                    fontSize: 11, fontWeight: 500,
                    cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                  }}>
                  {label}
                </button>
              ))}
            </div>

            <DownloadBtn
              dlKey="farm-pdf" state={dl['farm-pdf']}
              onClick={() => run('farm-pdf', dlFarmPdf)}
              label="PDF Yuklab Olish"
              icon={FileText}
              color="#EA580C"
            />
          </ReportCard>

          {/* Health PDF */}
          <ReportCard highlight>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: '#F0FDF4', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Heart size={16} color="#059669" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Sog'liq Hisoboti</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Alertlar · Risk baholash</div>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={labelStyle}>
                Jonivor IDlar <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <input
                type="text" value={healthIds}
                onChange={e => setHealthIds(e.target.value)}
                placeholder="1, 2, 3 — bo'sh qoldiring = hammasi"
                style={inputStyle}
              />
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: '4px 0 0' }}>
                Bo'sh → barcha aktiv jonivorlar uchun
              </p>
            </div>

            {/* Info box */}
            <div style={{
              padding: '10px 12px', background: '#F0FDF4',
              border: '1px solid #A7F3D0', borderRadius: 8, marginBottom: 14,
            }}>
              <p style={{ fontSize: 11, color: '#065F46', margin: 0, lineHeight: 1.5 }}>
                Hisobot o'z ichiga oladi: og'irlik yo'qotish alertlari (5%), 7+ kun ko'rinmagan jonivorlar, umumiy sog'liq skori va tavsiyalar
              </p>
            </div>

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

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* CSV EKSPORT                                                  */}
      {/* ═══════════════════════════════════════════════════════════ */}

      <div style={{ marginBottom: 32 }}>
        <SectionHeader
          icon={Table}
          title="CSV Eksport"
          subtitle="Excel, Google Sheets yoki tahlil uchun"
          color="#059669"
        />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

          {/* Animals CSV */}
          <ReportCard>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: '#F0FDF4', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                  <Table size={15} color="#059669" />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Jonivorlar CSV</div>
                  <div style={{ fontSize: 11, color: '#9CA3AF' }}>ID, teg, tur, holat, oxirgi deteksiya</div>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              <div>
                <label style={labelStyle}>Holat filtri</label>
                <select value={csvStatus} onChange={e => setCsvStatus(e.target.value)} style={inputStyle}>
                  <option value="">Hammasi</option>
                  <option value="active">Faol</option>
                  <option value="sold">Sotilgan</option>
                  <option value="deceased">Halok bo'lgan</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Tur filtri</label>
                <select value={csvSpecies} onChange={e => setCsvSpecies(e.target.value)} style={inputStyle}>
                  <option value="">Hammasi</option>
                  <option value="cattle">Qoramol</option>
                  <option value="sheep">Qo'y</option>
                  <option value="goat">Echki</option>
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

          {/* Detections CSV */}
          <ReportCard>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, background: '#F0FDF4', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Clock size={15} color="#059669" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Deteksiyalar CSV</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Vaqt, kamera, ishonch, bbox</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
              <div>
                <label style={labelStyle}>Boshlanish *</label>
                <input type="date" value={detFrom} onChange={e => setDetFrom(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>Tugash *</label>
                <input type="date" value={detTo} onChange={e => setDetTo(e.target.value)} style={inputStyle} />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>
                Jonivor <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <select value={detAnimal} onChange={e => setDetAnimal(e.target.value)} style={inputStyle}>
                <option value="">Barcha jonivorlar</option>
                {animals.map(a => (
                  <option key={a.id} value={a.id}>{a.tag_id}</option>
                ))}
              </select>
            </div>

            {/* Quick presets */}
            <div style={{ display: 'flex', gap: 5, marginBottom: 14 }}>
              {[
                { label: 'Bugun',   from: today() },
                { label: '7 kun',  from: daysAgo(7) },
                { label: '30 kun', from: daysAgo(30) },
              ].map(({ label, from }) => (
                <button key={label} onClick={() => { setDetFrom(from); setDetTo(today()); }}
                  style={{
                    flex: 1, padding: '5px 0',
                    border: '1px solid #E5E7EB', borderRadius: 6,
                    background: detFrom === from ? '#F0FDF4' : '#fff',
                    color: detFrom === from ? '#059669' : '#9CA3AF',
                    fontSize: 11, fontWeight: 500,
                    cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                  }}>
                  {label}
                </button>
              ))}
            </div>

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

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* EXCEL EKSPORT                                               */}
      {/* ═══════════════════════════════════════════════════════════ */}

      <div>
        <SectionHeader
          icon={FileSpreadsheet}
          title="Excel Eksport"
          subtitle="Ko'p varaqli .xlsx fayllar — professional tahlil uchun"
          color="#1D4ED8"
        />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

          {/* Weights Excel */}
          <ReportCard>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, background: '#EFF6FF', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <BarChart2 size={15} color="#1D4ED8" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Og'irlik Excel</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Har jonivor uchun alohida varaq</div>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>
                Jonivor IDlar <span style={{ color: '#9CA3AF', fontWeight: 400 }}>(ixtiyoriy)</span>
              </label>
              <input
                type="text" value={wExcelIds}
                onChange={e => setWExcelIds(e.target.value)}
                placeholder="1, 2, 3 — bo'sh = hammasi"
                style={inputStyle}
              />
            </div>

            {/* Excel structure info */}
            <div style={{
              padding: '10px 12px', background: '#EFF6FF',
              border: '1px solid #BFDBFE', borderRadius: 8, marginBottom: 16,
            }}>
              <p style={{ fontSize: 11, color: '#1D4ED8', margin: 0, lineHeight: 1.6 }}>
                <strong>Fayl tarkibi:</strong><br />
                📊 Varaq 1: Xulosa (barcha jonivorlar)<br />
                📋 Varaq 2+: Har bir jonivor uchun alohida
              </p>
            </div>

            <DownloadBtn
              dlKey="weights-excel" state={dl['weights-excel']}
              onClick={() => run('weights-excel', dlWeightsExcel)}
              label="Excel Yuklab Olish"
              icon={FileSpreadsheet}
              color="#1D4ED8"
            />
          </ReportCard>

          {/* All Data Excel */}
          <ReportCard>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, background: '#F5F3FF', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Layers size={15} color="#7C3AED" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>To'liq Arxiv Excel</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>Barcha ma'lumotlar bitta faylda</div>
              </div>
            </div>

            {/* Sheets info */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
              {[
                { sheet: 'Varaq 1', content: 'Barcha jonivorlar', color: '#7C3AED', bg: '#F5F3FF' },
                { sheet: 'Varaq 2', content: 'Deteksiyalar (30 kun)', color: '#1D4ED8', bg: '#EFF6FF' },
                { sheet: 'Varaq 3', content: "Og'irlik o'lchovlari", color: '#059669', bg: '#F0FDF4' },
                { sheet: 'Varaq 4', content: 'Umumiy statistika', color: '#DC2626', bg: '#FEF2F2' },
              ].map(({ sheet, content, color, bg }) => (
                <div key={sheet} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '7px 10px',
                  background: bg, border: `1px solid ${color}22`,
                  borderRadius: 7,
                }}>
                  <FileSpreadsheet size={12} color={color} />
                  <span style={{ fontSize: 12, fontWeight: 700, color }}>{sheet}:</span>
                  <span style={{ fontSize: 12, color: '#374151' }}>{content}</span>
                </div>
              ))}
            </div>

            <div style={{
              padding: '8px 12px', background: '#FFFBEB',
              border: '1px solid #FDE68A', borderRadius: 8, marginBottom: 16,
            }}>
              <p style={{ fontSize: 11, color: '#92400E', margin: 0 }}>
                ⚠ Katta fermalarda fayl hajmi 100MB+ bo'lishi mumkin. Kichik eksportlar uchun filtrli variantlardan foydalaning.
              </p>
            </div>

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