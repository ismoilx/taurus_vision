/**
 * Taurus Vision — Veterinariya Jurnali (Sprint 14)
 *
 * Barcha jonivorlarning sog'liq yozuvlari boshqaruvi.
 *
 * IMKONIYATLAR:
 *   - Ferma bo'yicha sog'liq statistikasi
 *   - Hal etilmagan muammolar ro'yxati
 *   - Yaqin tekshiruvlar jadvali
 *   - Yangi yozuv qo'shish (tekshiruv, davolash, emlash...)
 *   - Jonivor bo'yicha filtr
 *   - Yozuvni hal etilgan belgilash
 *   - Qidirish va filtrlash
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stethoscope, Plus, Search, AlertTriangle, CheckCircle,
  Calendar, RefreshCw, Filter, ChevronRight, Clock,
  Activity, Heart, Shield, Syringe, Scissors,
  AlertCircle, FileText, X, XCircle,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Animal {
  id:      number;
  tag_id:  string;
  species: string;
}

interface HealthRecord {
  id:                number;
  animal_id:         number;
  record_type:       string;
  severity:          string;
  diagnosis:         string;
  symptoms:          string | null;
  treatment:         string | null;
  medication:        string | null;
  dosage:            string | null;
  veterinarian:      string | null;
  clinic_name:       string | null;
  cost:              number | null;
  notes:             string | null;
  recorded_at:       string;
  next_checkup_date: string | null;
  is_resolved:       boolean;
  resolved_at:       string | null;
}

interface HealthStats {
  total_records:      number;
  by_type:            Record<string, number>;
  by_severity:        Record<string, number>;
  unresolved:         number;
  critical_unresolved: number;
  health_score:       number;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const TYPE_CFG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  checkup:     { label: 'Tekshiruv',  icon: Stethoscope, color: '#1D4ED8', bg: '#EFF6FF' },
  treatment:   { label: 'Davolash',   icon: Activity,    color: '#DC2626', bg: '#FEF2F2' },
  vaccination: { label: 'Emlash',     icon: Syringe,     color: '#059669', bg: '#F0FDF4' },
  injury:      { label: 'Jarohat',    icon: AlertTriangle, color: '#D97706', bg: '#FFF7ED' },
  surgery:     { label: 'Jarrohlik',  icon: Scissors,    color: '#7C3AED', bg: '#F5F3FF' },
  illness:     { label: "Kasallik",   icon: Heart,       color: '#E11D48', bg: '#FFF1F2' },
  other:       { label: 'Boshqa',     icon: FileText,    color: '#6B7280', bg: '#F9FAFB' },
};

const SEV_CFG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  normal:   { label: 'Normal',   color: '#059669', bg: '#F0FDF4', border: '#A7F3D0' },
  warning:  { label: 'Diqqat',   color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  critical: { label: 'Kritik',   color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('uz-UZ', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

function fmtFull(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / 86400000);
}

// ---------------------------------------------------------------------------
// Severity Badge
// ---------------------------------------------------------------------------
function SevBadge({ severity }: { severity: string }) {
  const cfg = SEV_CFG[severity] ?? SEV_CFG.normal;
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px',
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: 20, fontSize: 11, fontWeight: 700, color: cfg.color,
    }}>
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Type Badge
// ---------------------------------------------------------------------------
function TypeBadge({ type }: { type: string }) {
  const cfg = TYPE_CFG[type] ?? TYPE_CFG.other;
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 10px',
      background: cfg.bg, borderRadius: 20,
      fontSize: 11, fontWeight: 700, color: cfg.color,
    }}>
      <Icon size={11} />
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Add Record Modal
// ---------------------------------------------------------------------------
function AddRecordModal({
  animals, onClose, onSaved,
}: { animals: Animal[]; onClose: () => void; onSaved: () => void }) {
  const [animalId, setAnimalId]     = useState('');
  const [form, setForm] = useState({
    record_type:       'checkup' as string,
    severity:          'normal'  as string,
    diagnosis:         '',
    symptoms:          '',
    treatment:         '',
    medication:        '',
    dosage:            '',
    veterinarian:      '',
    clinic_name:       '',
    cost:              '',
    notes:             '',
    next_checkup_date: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const set = (key: string, val: string) => setForm(p => ({ ...p, [key]: val }));

  async function handleSubmit() {
    if (!animalId) { setError('Jonivor tanlang'); return; }
    if (!form.diagnosis.trim()) { setError("Tashxis majburiy"); return; }
    setLoading(true); setError('');
    try {
      const body: any = {
        record_type: form.record_type,
        severity:    form.severity,
        diagnosis:   form.diagnosis,
      };
      if (form.symptoms)          body.symptoms          = form.symptoms;
      if (form.treatment)         body.treatment         = form.treatment;
      if (form.medication)        body.medication        = form.medication;
      if (form.dosage)            body.dosage            = form.dosage;
      if (form.veterinarian)      body.veterinarian      = form.veterinarian;
      if (form.clinic_name)       body.clinic_name       = form.clinic_name;
      if (form.cost)              body.cost              = parseFloat(form.cost);
      if (form.notes)             body.notes             = form.notes;
      if (form.next_checkup_date) body.next_checkup_date = form.next_checkup_date;

      await apiFetch(`/api/v1/health/animals/${animalId}/records`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      onSaved(); onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Xato');
    } finally { setLoading(false); }
  }

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px',
    border: '1px solid #D1D5DB', borderRadius: 8,
    fontSize: 13, color: '#0D1117', outline: 'none',
    fontFamily: 'Outfit, sans-serif', boxSizing: 'border-box',
  };
  const lbl: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: '#374151', marginBottom: 4,
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
        width: '100%', maxWidth: 640,
        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px', borderBottom: '1px solid #F3F4F6',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#F0FDF4', display: 'grid', placeItems: 'center' }}>
              <Stethoscope size={16} color="#059669" />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0D1117', margin: 0 }}>
                Yangi Sog'liq Yozuvi
              </h2>
              <p style={{ fontSize: 11, color: '#9CA3AF', margin: 0 }}>Veterinariya jurnali</p>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: '#F9FAFB', border: '1px solid #E5E7EB',
            borderRadius: 7, width: 30, height: 30,
            display: 'grid', placeItems: 'center', cursor: 'pointer',
          }}>
            <X size={14} color="#6B7280" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div style={{
              display: 'flex', gap: 8, padding: '10px 14px', marginBottom: 14,
              background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8,
            }}>
              <AlertCircle size={14} color="#DC2626" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: '#DC2626' }}>{error}</span>
            </div>
          )}

          {/* Row 1: Jonivor */}
          <div style={{ marginBottom: 14 }}>
            <label style={lbl}>Jonivor *</label>
            <select value={animalId} onChange={e => setAnimalId(e.target.value)} style={inp}>
              <option value="">— Jonivor tanlang —</option>
              {animals.map(a => (
                <option key={a.id} value={a.id}>{a.tag_id} · {a.species}</option>
              ))}
            </select>
          </div>

          {/* Row 2: Tur + Jiddiylik */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <div>
              <label style={lbl}>Yozuv turi *</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 5 }}>
                {Object.entries(TYPE_CFG).map(([key, cfg]) => {
                  const Icon = cfg.icon;
                  const sel = form.record_type === key;
                  return (
                    <button key={key} onClick={() => set('record_type', key)} style={{
                      padding: '8px 4px',
                      border: `1.5px solid ${sel ? cfg.color : '#E5E7EB'}`,
                      borderRadius: 7, background: sel ? cfg.bg : '#fff',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                      cursor: 'pointer',
                    }}>
                      <Icon size={14} color={sel ? cfg.color : '#9CA3AF'} />
                      <span style={{ fontSize: 9, fontWeight: sel ? 700 : 500, color: sel ? cfg.color : '#9CA3AF' }}>
                        {cfg.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <label style={lbl}>Jiddiylik *</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {Object.entries(SEV_CFG).map(([key, cfg]) => (
                  <button key={key} onClick={() => set('severity', key)} style={{
                    padding: '7px 12px',
                    border: `1.5px solid ${form.severity === key ? cfg.color : '#E5E7EB'}`,
                    borderRadius: 7, background: form.severity === key ? cfg.bg : '#fff',
                    display: 'flex', alignItems: 'center', gap: 7,
                    cursor: 'pointer',
                  }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: form.severity === key ? cfg.color : '#D1D5DB',
                    }} />
                    <span style={{ fontSize: 12, fontWeight: form.severity === key ? 700 : 500, color: form.severity === key ? cfg.color : '#6B7280' }}>
                      {cfg.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Tashxis */}
          <div style={{ marginBottom: 12 }}>
            <label style={lbl}>Tashxis / Holat *</label>
            <input type="text" value={form.diagnosis}
              onChange={e => set('diagnosis', e.target.value)}
              placeholder="Masalan: Oddiy tekshiruv, OYT emlash..." style={inp} />
          </div>

          {/* Simptomlar + Davolash */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={lbl}>Simptomlar</label>
              <textarea value={form.symptoms} onChange={e => set('symptoms', e.target.value)}
                placeholder="Kuzatilgan simptomlar..." rows={3}
                style={{ ...inp, resize: 'vertical' }} />
            </div>
            <div>
              <label style={lbl}>Davolash</label>
              <textarea value={form.treatment} onChange={e => set('treatment', e.target.value)}
                placeholder="Qilingan davolash..." rows={3}
                style={{ ...inp, resize: 'vertical' }} />
            </div>
          </div>

          {/* Dori + Dozaj */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={lbl}>Dori-darmon</label>
              <input type="text" value={form.medication}
                onChange={e => set('medication', e.target.value)}
                placeholder="Dori nomi" style={inp} />
            </div>
            <div>
              <label style={lbl}>Dozaj</label>
              <input type="text" value={form.dosage}
                onChange={e => set('dosage', e.target.value)}
                placeholder="2ml, 1 dona..." style={inp} />
            </div>
          </div>

          {/* Veterinar + Klinika */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={lbl}>Veterinar</label>
              <input type="text" value={form.veterinarian}
                onChange={e => set('veterinarian', e.target.value)}
                placeholder="Dr. Karimov" style={inp} />
            </div>
            <div>
              <label style={lbl}>Klinika</label>
              <input type="text" value={form.clinic_name}
                onChange={e => set('clinic_name', e.target.value)}
                placeholder="Veterinariya klinikasi" style={inp} />
            </div>
          </div>

          {/* Narx + Keyingi tekshiruv */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div>
              <label style={lbl}>Narx (so'm)</label>
              <input type="number" value={form.cost}
                onChange={e => set('cost', e.target.value)}
                placeholder="0" style={inp} />
            </div>
            <div>
              <label style={lbl}>Keyingi tekshiruv</label>
              <input type="date" value={form.next_checkup_date}
                onChange={e => set('next_checkup_date', e.target.value)}
                min={new Date().toISOString().slice(0, 10)} style={inp} />
            </div>
          </div>

          {/* Izoh */}
          <div>
            <label style={lbl}>Qo'shimcha izoh</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              placeholder="Qo'shimcha ma'lumotlar..." rows={2}
              style={{ ...inp, resize: 'vertical' }} />
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 24px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '10px',
            border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>Bekor</button>
          <button onClick={handleSubmit} disabled={loading} style={{
            flex: 2, padding: '10px',
            background: loading ? '#9CA3AF' : '#059669',
            border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 14, fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'Outfit, sans-serif',
          }}>
            {loading ? 'Saqlanmoqda...' : 'Saqlash'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Record Detail Modal
// ---------------------------------------------------------------------------
function RecordDetailModal({
  record, animal, onClose, onResolved,
}: {
  record: HealthRecord; animal: Animal | undefined;
  onClose: () => void; onResolved: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const typCfg = TYPE_CFG[record.record_type] ?? TYPE_CFG.other;
  const TypeIcon = typCfg.icon;

  async function handleResolve() {
    setLoading(true);
    try {
      await apiFetch(`/api/v1/health/records/${record.id}/resolve`, { method: 'POST' });
      onResolved(); onClose();
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }

  const Row = ({ label, value }: { label: string; value: React.ReactNode }) => (
    value ? (
      <div style={{
        display: 'flex', gap: 12,
        padding: '8px 0', borderBottom: '1px solid #F9FAFB',
      }}>
        <span style={{ fontSize: 12, color: '#9CA3AF', width: 130, flexShrink: 0 }}>{label}</span>
        <span style={{ fontSize: 13, color: '#0D1117', flex: 1 }}>{value}</span>
      </div>
    ) : null
  );

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
        width: '100%', maxWidth: 560,
        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px', borderBottom: '1px solid #F3F4F6',
          display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, background: typCfg.bg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
            <TypeIcon size={20} color={typCfg.color} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0D1117', margin: 0 }}>
                {record.diagnosis}
              </h2>
              {record.is_resolved && (
                <span style={{ fontSize: 10, background: '#F0FDF4', color: '#059669', border: '1px solid #A7F3D0', padding: '2px 8px', borderRadius: 10, fontWeight: 700 }}>
                  ✓ Hal etilgan
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <TypeBadge type={record.record_type} />
              <SevBadge severity={record.severity} />
            </div>
          </div>
          <button onClick={onClose} style={{
            background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 7,
            width: 30, height: 30, display: 'grid', placeItems: 'center', cursor: 'pointer',
          }}>
            <X size={14} color="#6B7280" />
          </button>
        </div>

        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          <Row label="Jonivor" value={animal ? `${animal.tag_id} · ${animal.species}` : `#${record.animal_id}`} />
          <Row label="Sana" value={fmtFull(record.recorded_at)} />
          <Row label="Veterinar" value={record.veterinarian} />
          <Row label="Klinika" value={record.clinic_name} />
          <Row label="Simptomlar" value={record.symptoms} />
          <Row label="Davolash" value={record.treatment} />
          <Row label="Dori-darmon" value={record.medication} />
          <Row label="Dozaj" value={record.dosage} />
          <Row label="Narx" value={record.cost ? `${record.cost.toLocaleString()} so'm` : null} />
          <Row label="Keyingi tekshiruv" value={record.next_checkup_date ? (() => {
            const days = daysUntil(record.next_checkup_date);
            const d = fmt(record.next_checkup_date);
            if (days === null) return d;
            if (days < 0) return <span style={{ color: '#DC2626', fontWeight: 700 }}>{d} — muddati o'tdi!</span>;
            if (days === 0) return <span style={{ color: '#EA580C', fontWeight: 700 }}>{d} — bugun!</span>;
            return <span style={{ color: days <= 7 ? '#D97706' : '#374151' }}>{d} — {days} kun qoldi</span>;
          })() : null} />
          <Row label="Izoh" value={record.notes} />
          {record.is_resolved && record.resolved_at && (
            <Row label="Hal etilgan" value={<span style={{ color: '#059669' }}>{fmtFull(record.resolved_at)}</span>} />
          )}
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '10px', border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', color: '#374151', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>Yopish</button>
          {!record.is_resolved && (
            <button onClick={handleResolve} disabled={loading} style={{
              flex: 2, padding: '10px',
              background: loading ? '#9CA3AF' : '#059669',
              border: 'none', borderRadius: 8,
              color: '#fff', fontSize: 14, fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontFamily: 'Outfit, sans-serif',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
            }}>
              <CheckCircle size={14} />
              {loading ? 'Saqlanmoqda...' : 'Hal etilgan deb belgilash'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upcoming Checkup Card
// ---------------------------------------------------------------------------
function CheckupCard({ record, animals }: { record: HealthRecord; animals: Animal[] }) {
  const days    = daysUntil(record.next_checkup_date);
  const animal  = animals.find(a => a.id === record.animal_id);
  const isUrgent = days !== null && days <= 3;
  const isOverdue = days !== null && days < 0;

  return (
    <div style={{
      padding: '12px 16px',
      background: isOverdue ? '#FEF2F2' : isUrgent ? '#FFFBEB' : '#F9FAFB',
      border: `1px solid ${isOverdue ? '#FECACA' : isUrgent ? '#FDE68A' : '#E5E7EB'}`,
      borderLeft: `4px solid ${isOverdue ? '#DC2626' : isUrgent ? '#D97706' : '#D1D5DB'}`,
      borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#0D1117', marginBottom: 2 }}>
          {animal?.tag_id || `#${record.animal_id}`}
        </div>
        <div style={{ fontSize: 11, color: '#6B7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {record.diagnosis}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: isOverdue ? '#DC2626' : isUrgent ? '#D97706' : '#6B7280' }}>
          {isOverdue ? `${Math.abs(days!)} kun oldin` : days === 0 ? 'Bugun!' : `${days} kun`}
        </div>
        <div style={{ fontSize: 10, color: '#9CA3AF' }}>{fmt(record.next_checkup_date)}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Record Row
// ---------------------------------------------------------------------------
function RecordRow({
  record, animal, onClick,
}: { record: HealthRecord; animal: Animal | undefined; onClick: () => void }) {
  const typCfg = TYPE_CFG[record.record_type] ?? TYPE_CFG.other;
  const TypeIcon = typCfg.icon;

  return (
    <div onClick={onClick} style={{
      padding: '14px 20px',
      display: 'grid',
      gridTemplateColumns: '2.5fr 1.2fr 1.1fr 1fr 1.2fr 80px',
      gap: 12, alignItems: 'center',
      borderBottom: '1px solid #F3F4F6',
      cursor: 'pointer', transition: 'background .1s',
    }}
      onMouseEnter={e => e.currentTarget.style.background = '#FAFAFA'}
      onMouseLeave={e => e.currentTarget.style.background = '#fff'}
    >
      {/* Diagnosis */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 34, height: 34, borderRadius: 8, background: typCfg.bg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
          <TypeIcon size={15} color={typCfg.color} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#0D1117', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
            {record.diagnosis}
          </div>
          {record.veterinarian && (
            <div style={{ fontSize: 11, color: '#9CA3AF' }}>{record.veterinarian}</div>
          )}
        </div>
      </div>

      {/* Animal */}
      <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
        {animal?.tag_id || `#${record.animal_id}`}
      </div>

      {/* Type */}
      <div><TypeBadge type={record.record_type} /></div>

      {/* Severity */}
      <div><SevBadge severity={record.severity} /></div>

      {/* Date */}
      <div style={{ fontSize: 12, color: '#6B7280' }}>{fmt(record.recorded_at)}</div>

      {/* Status */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        {record.is_resolved ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#059669', fontWeight: 600 }}>
            <CheckCircle size={13} /> Hal
          </span>
        ) : (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#D97706', fontWeight: 600 }}>
            <Clock size={13} /> Ochiq
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function HealthPage() {
  const qClient = useQueryClient();
  const [search, setSearch]         = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [sevFilter, setSevFilter]   = useState('all');
  const [animalFilter, setAF]       = useState('');
  const [showResolved, setShowRes]  = useState(false);
  const [showAdd, setShowAdd]       = useState(false);
  const [detail, setDetail]         = useState<HealthRecord | null>(null);
  const [toast, setToast]           = useState('');

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  }

  const invalidateHealth = () => qClient.invalidateQueries({ queryKey: ['health'] });

  const load = () => {
    qClient.invalidateQueries({ queryKey: ['health'] });
    qClient.invalidateQueries({ queryKey: ['animals'] });
  };

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: animalsRes, isLoading: loading } = useQuery({
    queryKey: ['animals', 'list-200'],
    queryFn:  () => apiFetch<{ items: Animal[] }>('/api/v1/animals/?limit=200'),
  });
  const animals = animalsRes?.items ?? [];

  const { data: unresolvedRes } = useQuery({
    queryKey: ['health', 'unresolved'],
    queryFn:  () => apiFetch<{ records: HealthRecord[] }>('/api/v1/health/unresolved?limit=100'),
  });

  const { data: criticalRes } = useQuery({
    queryKey: ['health', 'critical'],
    queryFn:  () => apiFetch<{ records: HealthRecord[] }>('/api/v1/health/critical'),
    enabled:  showResolved,
  });

  const { data: stats } = useQuery({
    queryKey: ['health', 'stats'],
    queryFn:  () => apiFetch<HealthStats>('/api/v1/health/statistics'),
  });

  const { data: upcomingRes } = useQuery({
    queryKey: ['health', 'upcoming'],
    queryFn:  () => apiFetch<{ records: HealthRecord[] }>('/api/v1/health/upcoming-checkups?days_ahead=14'),
  });
  const upcoming = upcomingRes?.records ?? [];

  // Combine unresolved + critical (deduplicated)
  const records: HealthRecord[] = (() => {
    const base = unresolvedRes?.records ?? [];
    if (!showResolved || !criticalRes?.records) return base;
    const combined = [...base];
    (criticalRes.records).forEach(r => {
      if (!combined.find(x => x.id === r.id)) combined.push(r);
    });
    return combined;
  })();

  // Filtered records
  const filtered = records.filter(r => {
    const animal = animals.find(a => a.id === r.animal_id);
    const q = search.toLowerCase();
    const matchSearch = !q
      || r.diagnosis.toLowerCase().includes(q)
      || (r.veterinarian || '').toLowerCase().includes(q)
      || (animal?.tag_id || '').toLowerCase().includes(q);
    const matchType   = typeFilter === 'all' || r.record_type === typeFilter;
    const matchSev    = sevFilter  === 'all' || r.severity === sevFilter;
    const matchAnimal = !animalFilter || String(r.animal_id) === animalFilter;
    const matchRes    = showResolved ? true : !r.is_resolved;
    return matchSearch && matchType && matchSev && matchAnimal && matchRes;
  });

  const criticalCount = records.filter(r => !r.is_resolved && r.severity === 'critical').length;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '32px 24px', fontFamily: 'Outfit, sans-serif' }}>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 100,
          padding: '12px 20px', background: '#0D1117', color: '#fff',
          borderRadius: 10, fontSize: 14, fontWeight: 500,
          boxShadow: '0 8px 24px rgba(0,0,0,0.2)', animation: 'fadeIn .2s ease',
        }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0D1117', margin: 0 }}>
            Veterinariya Jurnali
          </h1>
          <p style={{ fontSize: 14, color: '#6B7280', margin: '4px 0 0' }}>
            Barcha jonivorlarning sog'liq tarixi va muolajalar yozuvi
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={load} style={{
            padding: '9px 12px', border: '1px solid #D1D5DB', borderRadius: 8,
            background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center',
          }}>
            <RefreshCw size={15} color="#6B7280"
              style={{ animation: loading ? 'spin .7s linear infinite' : 'none' }} />
          </button>
          <button onClick={() => setShowAdd(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '9px 18px',
            background: '#059669', color: '#fff', border: 'none', borderRadius: 8,
            fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
          }}>
            <Plus size={16} /> Yozuv qo'shish
          </button>
        </div>
      </div>

      {/* Critical alert banner */}
      {criticalCount > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20,
          padding: '14px 20px',
          background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12,
        }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#DC2626', display: 'grid', placeItems: 'center', flexShrink: 0 }}>
            <AlertTriangle size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#DC2626' }}>
              {criticalCount} ta kritik sog'liq muammosi hal etilmagan!
            </div>
            <div style={{ fontSize: 12, color: '#B91C1C' }}>
              Zudlik bilan veterinar ko'rigi talab etiladi
            </div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Jami yozuvlar',  value: stats?.total_records ?? 0,      icon: FileText,    color: '#1D4ED8', bg: '#EFF6FF' },
          { label: 'Hal etilmagan',  value: stats?.unresolved ?? 0,          icon: Clock,       color: '#D97706', bg: '#FFFBEB' },
          { label: 'Kritik',         value: stats?.critical_unresolved ?? 0, icon: AlertTriangle, color: '#DC2626', bg: '#FEF2F2' },
          { label: 'Yaqin tekshiruv', value: upcoming.length,              icon: Calendar,    color: '#7C3AED', bg: '#F5F3FF' },
          { label: "Sog'liq skori",  value: `${stats?.health_score ?? 0}%`, icon: Heart,       color: '#059669', bg: '#F0FDF4' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} style={{
            background: '#fff', border: '1px solid #E4E7ED',
            borderRadius: 12, padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{ width: 38, height: 38, borderRadius: 8, background: bg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
              <Icon size={16} color={color} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280' }}>{label}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#0D1117' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Main layout: table + sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>

        {/* LEFT — Records table */}
        <div>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
            {/* Search */}
            <div style={{ position: 'relative', flex: '1 1 200px' }}>
              <Search size={13} color="#9CA3AF" style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)' }} />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Tashxis, veterinar, teg..."
                style={{
                  width: '100%', padding: '9px 10px 9px 32px',
                  border: '1px solid #D1D5DB', borderRadius: 8,
                  fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  fontFamily: 'Outfit, sans-serif',
                }} />
            </div>

            {/* Animal filter */}
            <select value={animalFilter} onChange={e => setAF(e.target.value)}
              style={{ padding: '9px 12px', border: '1px solid #D1D5DB', borderRadius: 8, fontSize: 13, color: '#374151', outline: 'none', fontFamily: 'Outfit, sans-serif', background: '#fff' }}>
              <option value="">Barcha jonivorlar</option>
              {animals.map(a => <option key={a.id} value={a.id}>{a.tag_id}</option>)}
            </select>

            {/* Type filter */}
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
              style={{ padding: '9px 12px', border: '1px solid #D1D5DB', borderRadius: 8, fontSize: 13, color: '#374151', outline: 'none', fontFamily: 'Outfit, sans-serif', background: '#fff' }}>
              <option value="all">Barcha turlar</option>
              {Object.entries(TYPE_CFG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>

            {/* Severity filter */}
            <select value={sevFilter} onChange={e => setSevFilter(e.target.value)}
              style={{ padding: '9px 12px', border: '1px solid #D1D5DB', borderRadius: 8, fontSize: 13, color: '#374151', outline: 'none', fontFamily: 'Outfit, sans-serif', background: '#fff' }}>
              <option value="all">Barcha darajalar</option>
              {Object.entries(SEV_CFG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>

            {/* Show resolved toggle */}
            <button onClick={() => setShowRes(p => !p)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '9px 14px',
              border: `1px solid ${showResolved ? '#1E3EB4' : '#D1D5DB'}`,
              borderRadius: 8, background: showResolved ? '#EEF2FF' : '#fff',
              color: showResolved ? '#1E3EB4' : '#6B7280',
              fontSize: 13, fontWeight: showResolved ? 700 : 500,
              cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
            }}>
              <Filter size={13} />
              {showResolved ? 'Hammasi' : 'Ochiq'}
            </button>
          </div>

          {/* Table */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, overflow: 'hidden' }}>
            {/* Header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '2.5fr 1.2fr 1.1fr 1fr 1.2fr 80px',
              padding: '11px 20px', gap: 12,
              background: '#F9FAFB', borderBottom: '1px solid #E4E7ED',
            }}>
              {['Tashxis', 'Jonivor', 'Tur', 'Jiddiylik', 'Sana', 'Holat'].map((h, i) => (
                <div key={i} style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {h}
                </div>
              ))}
            </div>

            {loading ? (
              <div style={{ padding: '48px', textAlign: 'center', color: '#9CA3AF' }}>Yuklanmoqda...</div>
            ) : filtered.length === 0 ? (
              <div style={{ padding: '48px', textAlign: 'center' }}>
                <Stethoscope size={36} color="#D1D5DB" style={{ margin: '0 auto 12px', display: 'block' }} />
                <p style={{ color: '#9CA3AF', fontSize: 14, margin: 0 }}>
                  {search || typeFilter !== 'all' || sevFilter !== 'all' || animalFilter
                    ? 'Qidiruv bo\'yicha yozuv topilmadi'
                    : showResolved ? 'Yozuv yo\'q' : 'Hal etilmagan muammo yo\'q ✓'}
                </p>
              </div>
            ) : filtered.map(r => (
              <RecordRow
                key={r.id}
                record={r}
                animal={animals.find(a => a.id === r.animal_id)}
                onClick={() => setDetail(r)}
              />
            ))}
          </div>

          <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 10, textAlign: 'center' }}>
            {filtered.length} ta yozuv ko'rsatilmoqda
          </p>
        </div>

        {/* RIGHT Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Health Score */}
          {stats && (
            <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <Shield size={15} color="#059669" />
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: 0 }}>Umumiy Sog'liq</h3>
              </div>

              {/* Score ring */}
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <svg width={100} height={100} viewBox="0 0 100 100">
                    <circle cx={50} cy={50} r={40} fill="none" stroke="#F3F4F6" strokeWidth={10} />
                    <circle cx={50} cy={50} r={40} fill="none"
                      stroke={stats.health_score >= 80 ? '#10B981' : stats.health_score >= 60 ? '#D97706' : '#DC2626'}
                      strokeWidth={10}
                      strokeDasharray={`${2 * Math.PI * 40 * stats.health_score / 100} 999`}
                      strokeLinecap="round"
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
                    <div style={{ fontSize: 22, fontWeight: 900, color: '#0D1117' }}>{stats.health_score}</div>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
                  {stats.health_score >= 80 ? '🟢 Yaxshi' : stats.health_score >= 60 ? '🟡 Qoniqarli' : '🔴 Muammo bor'}
                </div>
              </div>

              {/* By type */}
              <div>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 8px' }}>
                  Tur bo'yicha
                </p>
                {Object.entries(stats.by_type || {}).filter(([, v]) => v > 0).map(([type, count]) => {
                  const cfg = TYPE_CFG[type] ?? TYPE_CFG.other;
                  const Icon = cfg.icon;
                  const total = stats.total_records || 1;
                  return (
                    <div key={type} style={{ marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Icon size={11} color={cfg.color} />
                          <span style={{ fontSize: 12, color: '#374151' }}>{cfg.label}</span>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#0D1117' }}>{count}</span>
                      </div>
                      <div style={{ height: 4, background: '#F3F4F6', borderRadius: 3 }}>
                        <div style={{ height: '100%', background: cfg.color, borderRadius: 3, width: `${count / total * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Upcoming Checkups */}
          <div style={{ background: '#fff', border: '1px solid #E4E7ED', borderRadius: 14, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Calendar size={15} color="#7C3AED" />
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: 0 }}>Yaqin Tekshiruvlar</h3>
              </div>
              {upcoming.length > 0 && (
                <span style={{ fontSize: 11, background: '#F5F3FF', color: '#7C3AED', border: '1px solid #DDD6FE', padding: '2px 8px', borderRadius: 10, fontWeight: 700 }}>
                  {upcoming.length}
                </span>
              )}
            </div>

            {upcoming.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <Calendar size={28} color="#E5E7EB" style={{ margin: '0 auto 8px', display: 'block' }} />
                <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>14 kun ichida tekshiruv yo'q</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {upcoming.slice(0, 6).map(r => (
                  <CheckupCard key={r.id} record={r} animals={animals} />
                ))}
                {upcoming.length > 6 && (
                  <p style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', margin: 0 }}>
                    + {upcoming.length - 6} ta ko'proq
                  </p>
                )}
              </div>
            )}
          </div>

        </div>
      </div>

      {/* Modals */}
      {showAdd && (
        <AddRecordModal
          animals={animals}
          onClose={() => setShowAdd(false)}
          onSaved={() => { invalidateHealth(); showToast("✅ Yozuv qo'shildi!"); }}
        />
      )}
      {detail && (
        <RecordDetailModal
          record={detail}
          animal={animals.find(a => a.id === detail.animal_id)}
          onClose={() => setDetail(null)}
          onResolved={() => { invalidateHealth(); showToast('✅ Hal etilgan deb belgilandi!'); }}
        />
      )}

      <style>{`
        @keyframes spin   { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}