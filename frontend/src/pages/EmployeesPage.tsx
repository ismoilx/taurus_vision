/**
 * Taurus Vision — Employees Page (Hodimlar)
 *
 * 2 tab:
 *   1. Xodimlar — ro'yxat, qo'shish, tahrirlash, badge
 *   2. Vazifalar — barcha vazifalar, filtr, holat o'zgartirish, tasdiqlash
 *
 * Faylni: frontend/src/pages/EmployeesPage.tsx ga joylashtiring
 */

import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users, Plus, Search, ChevronRight, CheckCircle,
  Clock, AlertTriangle, XCircle, RefreshCw,
  Phone, Briefcase, Calendar, Star, MoreVertical,
  ClipboardList, Filter, Eye, ShieldCheck, X,
  TrendingUp, TrendingDown, Minus, Camera,
  UserCheck, UserX, Edit2,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Employee {
  id:              number;
  full_name:       string;
  phone:           string | null;
  position:        string;
  status:          string;
  hire_date:       string | null;
  salary:          number | null;
  notes:           string | null;
  farm_id:         number | null;
  open_tasks:      number;
  completed_tasks: number;
  overdue_tasks:   number;
  created_at:      string;
  updated_at:      string;
}

interface EmployeeListResponse {
  items: Employee[];
  total: number;
  page:  number;
  size:  number;
  pages: number;
}

interface EmployeeStats {
  total:         number;
  active:        number;
  on_leave:      number;
  inactive:      number;
  by_position:   Record<string, number>;
  tasks_today:   number;
  overdue_tasks: number;
}

interface WorkerTask {
  id:                    number;
  title:                 string;
  description:           string | null;
  task_type:             string;
  priority:              string;
  status:                string;
  due_date:              string | null;
  started_at:            string | null;
  completed_at:          string | null;
  employee_id:           number | null;
  employee_name:         string | null;
  employee_position:     string | null;
  animal_id:             number | null;
  requires_verification: boolean;
  verification_status:   string;
  verified_at:           string | null;
  completion_notes:      string | null;
  is_overdue:            boolean;
  created_at:            string;
}

interface WorkerTaskListResponse {
  items: WorkerTask[];
  total: number;
  page:  number;
  size:  number;
  pages: number;
}

interface WorkerTaskStats {
  total:              number;
  pending:            number;
  in_progress:        number;
  completed:          number;
  overdue:            number;
  cancelled:          number;
  needs_verification: number;
  completion_rate:    number;
}

// ─── Config ───────────────────────────────────────────────────────────────────
const POSITION_CFG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  feeder:       { label: 'Boqituvchi',   color: '#059669', bg: '#ECFDF5', icon: '🌾' },
  veterinarian: { label: 'Veterinar',    color: '#2563EB', bg: '#EEF2FF', icon: '🩺' },
  mechanic:     { label: 'Mexanik',      color: '#D97706', bg: '#FFFBEB', icon: '🔧' },
  guard:        { label: 'Qorovul',      color: '#7C3AED', bg: '#F5F3FF', icon: '🛡️' },
  manager:      { label: 'Boshqaruvchi', color: '#1E3EB4', bg: '#EEF2FF', icon: '👔' },
  cleaner:      { label: 'Tozalovchi',   color: '#0891B2', bg: '#ECFEFF', icon: '🧹' },
  other:        { label: 'Boshqa',       color: '#6B7280', bg: '#F9FAFB', icon: '👷' },
};

const STATUS_CFG: Record<string, { label: string; color: string; bg: string }> = {
  active:   { label: 'Faol',    color: '#059669', bg: '#ECFDF5' },
  on_leave: { label: "Ta'tilda", color: '#D97706', bg: '#FFFBEB' },
  inactive: { label: 'Ishdan ketgan', color: '#9CA3AF', bg: '#F9FAFB' },
};

const TASK_TYPE_CFG: Record<string, { label: string; icon: string }> = {
  feeding:      { label: 'Oziqlantiruv',  icon: '🌿' },
  watering:     { label: 'Suv berish',    icon: '💧' },
  cleaning:     { label: 'Tozalash',      icon: '🧹' },
  vaccination:  { label: 'Emlash',        icon: '💉' },
  health_check: { label: "Sog'liq tekshiruv", icon: '🩺' },
  medication:   { label: 'Dori berish',   icon: '💊' },
  weighing:     { label: 'Vazn o\'lchash', icon: '⚖️' },
  grooming:     { label: 'Parvarish',     icon: '✂️' },
  transfer:     { label: "Ko'chirish",    icon: '🚚' },
  repair:       { label: "Ta'mirlash",    icon: '🔧' },
  security:     { label: "Qo'riqlash",    icon: '🛡️' },
  other:        { label: 'Boshqa',        icon: '📋' },
};

const PRIORITY_CFG: Record<string, { label: string; color: string; bg: string }> = {
  low:      { label: 'Past',    color: '#6B7280', bg: '#F9FAFB' },
  medium:   { label: "O'rta",   color: '#2563EB', bg: '#EEF2FF' },
  high:     { label: 'Yuqori',  color: '#D97706', bg: '#FFFBEB' },
  critical: { label: 'Kritik',  color: '#DC2626', bg: '#FEF2F2' },
};

const TASK_STATUS_CFG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  pending:     { label: 'Kutmoqda',    color: '#6B7280', bg: '#F9FAFB',  icon: Clock },
  in_progress: { label: 'Bajarilmoqda', color: '#2563EB', bg: '#EEF2FF', icon: RefreshCw },
  completed:   { label: 'Bajarildi',   color: '#059669', bg: '#ECFDF5',  icon: CheckCircle },
  overdue:     { label: 'Muddati o\'tdi', color: '#DC2626', bg: '#FEF2F2', icon: AlertTriangle },
  cancelled:   { label: 'Bekor qilindi', color: '#9CA3AF', bg: '#F9FAFB', icon: XCircle },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('uz-UZ', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit' })
    + ' ' + d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

// ─── Inline styles ────────────────────────────────────────────────────────────
const S = {
  page:    { background: '#F4F6FA', minHeight: 'calc(100vh - 56px)', padding: '20px 24px 32px', fontFamily: "'Plus Jakarta Sans', 'Outfit', sans-serif" } as React.CSSProperties,
  wrap:    { maxWidth: 1360, margin: '0 auto' } as React.CSSProperties,
  card:    { background: '#fff', border: '1px solid #E8EBF2', borderRadius: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.05)', overflow: 'hidden' } as React.CSSProperties,
  inp:     { border: '1px solid #E8EBF2', borderRadius: 8, padding: '8px 12px', fontSize: 13, outline: 'none', fontFamily: 'inherit', width: '100%', background: '#fff', color: '#1F2937' } as React.CSSProperties,
  sel:     { border: '1px solid #E8EBF2', borderRadius: 8, padding: '8px 12px', fontSize: 12, outline: 'none', fontFamily: 'inherit', background: '#fff', color: '#374151', cursor: 'pointer' } as React.CSSProperties,
  btnPri:  { background: '#1E3EB4', color: '#fff', border: 'none', borderRadius: 9, padding: '9px 18px', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit' } as React.CSSProperties,
  btnSec:  { background: '#F4F6FA', color: '#374151', border: '1px solid #E8EBF2', borderRadius: 9, padding: '8px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit' } as React.CSSProperties,
  btnSm:   { border: 'none', borderRadius: 7, padding: '5px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
  overlay: { position: 'fixed', inset: 0, zIndex: 200, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 } as React.CSSProperties,
  modal:   { background: '#fff', borderRadius: 20, width: '100%', maxWidth: 520, boxShadow: '0 24px 64px rgba(0,0,0,0.18)', overflow: 'hidden' } as React.CSSProperties,
  label:   { fontSize: 11, fontWeight: 700, color: '#6B7280', marginBottom: 5, display: 'block', letterSpacing: '0.04em' } as React.CSSProperties,
  row:     { display: 'flex', alignItems: 'center', gap: 12 } as React.CSSProperties,
};

// ─── Badge ────────────────────────────────────────────────────────────────────
function Badge({ label, color, bg }: { label: string; color: string; bg: string }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 9px', borderRadius: 20, background: bg, color, letterSpacing: '0.04em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
      {label}
    </span>
  );
}

// ─── Stat box ─────────────────────────────────────────────────────────────────
function StatBox({ val, label, color = '#1E3EB4' }: { val: number | string; label: string; color?: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '10px 16px', background: '#F9FAFB', borderRadius: 10 }}>
      <div style={{ fontSize: 22, fontWeight: 900, color, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>{val}</div>
      <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 3 }}>{label}</div>
    </div>
  );
}

// ─── Employee card ────────────────────────────────────────────────────────────
function EmployeeCard({ emp, onClick }: { emp: Employee; onClick: () => void }) {
  const posCfg = POSITION_CFG[emp.position] || POSITION_CFG.other;
  const stsCfg = STATUS_CFG[emp.status]     || STATUS_CFG.active;

  return (
    <div
      onClick={onClick}
      style={{
        ...S.card, cursor: 'pointer', transition: 'transform .15s, box-shadow .15s',
        display: 'flex', flexDirection: 'column',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 28px rgba(0,0,0,0.09)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'none'; (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 4px rgba(0,0,0,0.05)'; }}
    >
      {/* Top stripe */}
      <div style={{ height: 4, background: posCfg.color }}/>

      <div style={{ padding: '16px 18px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Avatar */}
            <div style={{
              width: 46, height: 46, borderRadius: 12,
              background: posCfg.bg, border: `2px solid ${posCfg.color}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <span style={{ fontSize: 15, fontWeight: 800, color: posCfg.color }}>{getInitials(emp.full_name)}</span>
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', lineHeight: 1.3 }}>{emp.full_name}</div>
              <div style={{ fontSize: 11, color: posCfg.color, marginTop: 3, fontWeight: 600 }}>
                {posCfg.icon} {posCfg.label}
              </div>
            </div>
          </div>
          <Badge label={stsCfg.label} color={stsCfg.color} bg={stsCfg.bg}/>
        </div>

        {/* Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
          {emp.phone && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
              <Phone size={11}/> {emp.phone}
            </div>
          )}
          {emp.hire_date && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
              <Calendar size={11}/> {formatDate(emp.hire_date)} dan beri
            </div>
          )}
        </div>

        {/* Task stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
          <div style={{ textAlign: 'center', background: '#EEF2FF', borderRadius: 8, padding: '7px 4px' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#1E3EB4', fontFamily: "'JetBrains Mono', monospace" }}>{emp.open_tasks}</div>
            <div style={{ fontSize: 9, color: '#6B7280', marginTop: 1 }}>Ochiq</div>
          </div>
          <div style={{ textAlign: 'center', background: '#ECFDF5', borderRadius: 8, padding: '7px 4px' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#059669', fontFamily: "'JetBrains Mono', monospace" }}>{emp.completed_tasks}</div>
            <div style={{ fontSize: 9, color: '#6B7280', marginTop: 1 }}>Bajarildi</div>
          </div>
          <div style={{ textAlign: 'center', background: emp.overdue_tasks > 0 ? '#FEF2F2' : '#F9FAFB', borderRadius: 8, padding: '7px 4px' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: emp.overdue_tasks > 0 ? '#DC2626' : '#9CA3AF', fontFamily: "'JetBrains Mono', monospace" }}>{emp.overdue_tasks}</div>
            <div style={{ fontSize: 9, color: '#6B7280', marginTop: 1 }}>Muddati o'tdi</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Employee Modal ───────────────────────────────────────────────────────────
function EmployeeModal({
  emp, onClose, onSave,
}: {
  emp: Employee | null;
  onClose: () => void;
  onSave: (data: any) => void;
}) {
  const isEdit = !!emp;
  const [form, setForm] = useState({
    full_name: emp?.full_name || '',
    phone:     emp?.phone     || '',
    position:  emp?.position  || 'other',
    status:    emp?.status    || 'active',
    hire_date: emp?.hire_date?.slice(0, 10) || '',
    salary:    emp?.salary    ? String(emp.salary) : '',
    notes:     emp?.notes     || '',
  });

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 22px 14px', borderBottom: '1px solid #F3F4F6' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>
            {isEdit ? 'Xodimni tahrirlash' : "Yangi xodim qo'shish"}
          </div>
          <button onClick={onClose} style={{ background: '#F3F4F6', border: 'none', borderRadius: 8, width: 30, height: 30, cursor: 'pointer', display: 'grid', placeItems: 'center', color: '#6B7280' }}>
            <X size={14}/>
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={S.label}>TO'LIQ ISM *</label>
            <input style={S.inp} value={form.full_name} onChange={e => set('full_name', e.target.value)} placeholder="Karimov Sardor"/>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={S.label}>LAVOZIM</label>
              <select style={{ ...S.sel, width: '100%' }} value={form.position} onChange={e => set('position', e.target.value)}>
                {Object.entries(POSITION_CFG).map(([k, v]) => (
                  <option key={k} value={k}>{v.icon} {v.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={S.label}>HOLAT</label>
              <select style={{ ...S.sel, width: '100%' }} value={form.status} onChange={e => set('status', e.target.value)}>
                <option value="active">✅ Faol</option>
                <option value="on_leave">⏸️ Ta'tilda</option>
                <option value="inactive">❌ Ishdan ketgan</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={S.label}>TELEFON</label>
              <input style={S.inp} value={form.phone} onChange={e => set('phone', e.target.value)} placeholder="+998 90 123 45 67"/>
            </div>
            <div>
              <label style={S.label}>ISHGA KIRGAN SANA</label>
              <input type="date" style={S.inp} value={form.hire_date} onChange={e => set('hire_date', e.target.value)}/>
            </div>
          </div>

          <div>
            <label style={S.label}>OYLIK MAOSH (so'm)</label>
            <input type="number" style={S.inp} value={form.salary} onChange={e => set('salary', e.target.value)} placeholder="3000000"/>
          </div>

          <div>
            <label style={S.label}>IZOH</label>
            <textarea style={{ ...S.inp, resize: 'vertical', minHeight: 60 } as any} value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Qo'shimcha ma'lumot..."/>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 22px 18px', borderTop: '1px solid #F3F4F6', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button style={S.btnSec} onClick={onClose}>Bekor qilish</button>
          <button
            style={S.btnPri}
            onClick={() => onSave({
              full_name: form.full_name,
              phone:     form.phone || null,
              position:  form.position,
              status:    form.status,
              hire_date: form.hire_date || null,
              salary:    form.salary ? parseFloat(form.salary) : null,
              notes:     form.notes || null,
            })}
          >
            {isEdit ? 'Saqlash' : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Task Modal ───────────────────────────────────────────────────────────────
function TaskModal({
  employees, task, onClose, onSave,
}: {
  employees: Employee[];
  task: WorkerTask | null;
  onClose: () => void;
  onSave: (data: any) => void;
}) {
  const isEdit = !!task;
  const [form, setForm] = useState({
    title:                 task?.title       || '',
    description:           task?.description || '',
    task_type:             task?.task_type   || 'other',
    priority:              task?.priority    || 'medium',
    due_date:              task?.due_date?.slice(0, 16) || '',
    employee_id:           task?.employee_id ? String(task.employee_id) : '',
    animal_id:             task?.animal_id   ? String(task.animal_id) : '',
    requires_verification: task?.requires_verification || false,
  });

  const set = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={{ ...S.modal, maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 22px 14px', borderBottom: '1px solid #F3F4F6' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1117' }}>
            {isEdit ? 'Vazifani tahrirlash' : 'Yangi vazifa'}
          </div>
          <button onClick={onClose} style={{ background: '#F3F4F6', border: 'none', borderRadius: 8, width: 30, height: 30, cursor: 'pointer', display: 'grid', placeItems: 'center', color: '#6B7280' }}>
            <X size={14}/>
          </button>
        </div>

        <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={S.label}>VAZIFA NOMI *</label>
            <input style={S.inp} value={form.title} onChange={e => set('title', e.target.value)} placeholder="Masalan: Ertalabki oziqlantiruv"/>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={S.label}>TURI</label>
              <select style={{ ...S.sel, width: '100%' }} value={form.task_type} onChange={e => set('task_type', e.target.value)}>
                {Object.entries(TASK_TYPE_CFG).map(([k, v]) => (
                  <option key={k} value={k}>{v.icon} {v.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={S.label}>MUHIMLIK</label>
              <select style={{ ...S.sel, width: '100%' }} value={form.priority} onChange={e => set('priority', e.target.value)}>
                {Object.entries(PRIORITY_CFG).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={S.label}>XODIM</label>
              <select style={{ ...S.sel, width: '100%' }} value={form.employee_id} onChange={e => set('employee_id', e.target.value)}>
                <option value="">— Tayinlanmagan —</option>
                {employees.filter(e => e.status === 'active').map(e => (
                  <option key={e.id} value={e.id}>{POSITION_CFG[e.position]?.icon} {e.full_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={S.label}>MUDDAT</label>
              <input type="datetime-local" style={S.inp} value={form.due_date} onChange={e => set('due_date', e.target.value)}/>
            </div>
          </div>

          <div>
            <label style={S.label}>TAVSIF</label>
            <textarea style={{ ...S.inp, resize: 'vertical', minHeight: 60 } as any} value={form.description} onChange={e => set('description', e.target.value)} placeholder="Batafsil ko'rsatmalar..."/>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 13, color: '#374151' }}>
            <input type="checkbox" checked={form.requires_verification} onChange={e => set('requires_verification', e.target.checked)} style={{ width: 15, height: 15, accentColor: '#1E3EB4' }}/>
            <Camera size={14} color="#1E3EB4"/>
            Kamera orqali tasdiqlash talab qilinsin
          </label>
        </div>

        <div style={{ padding: '12px 22px 18px', borderTop: '1px solid #F3F4F6', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button style={S.btnSec} onClick={onClose}>Bekor qilish</button>
          <button
            style={S.btnPri}
            onClick={() => onSave({
              title:                 form.title,
              description:           form.description || null,
              task_type:             form.task_type,
              priority:              form.priority,
              due_date:              form.due_date ? new Date(form.due_date).toISOString() : null,
              employee_id:           form.employee_id ? parseInt(form.employee_id) : null,
              animal_id:             form.animal_id ? parseInt(form.animal_id) : null,
              requires_verification: form.requires_verification,
            })}
          >
            {isEdit ? 'Saqlash' : 'Yaratish'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Task Row ─────────────────────────────────────────────────────────────────
function TaskRow({ task, onAction }: { task: WorkerTask; onAction: (action: string, task: WorkerTask) => void }) {
  const stsCfg  = TASK_STATUS_CFG[task.status]  || TASK_STATUS_CFG.pending;
  const priCfg  = PRIORITY_CFG[task.priority]   || PRIORITY_CFG.medium;
  const typeCfg = TASK_TYPE_CFG[task.task_type] || TASK_TYPE_CFG.other;
  const SIcon   = stsCfg.icon;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '2.5fr 1.2fr 100px 110px 120px 140px',
      padding: '13px 20px',
      borderBottom: '1px solid #F3F4F6',
      transition: 'background .12s',
      alignItems: 'center',
      gap: 8,
    }}
    onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#FAFBFD'}
    onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = ''}
    >
      {/* Vazifa */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ fontSize: 14 }}>{typeCfg.icon}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>{task.title}</span>
          {task.requires_verification && (
            <Camera size={11} color="#1E3EB4" title="Kamera tasdiqlash kerak"/>
          )}
        </div>
        <div style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 22 }}>{typeCfg.label}</div>
      </div>

      {/* Xodim */}
      <div>
        {task.employee_name ? (
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{task.employee_name}</div>
            <div style={{ fontSize: 10, color: '#9CA3AF' }}>{task.employee_position || ''}</div>
          </div>
        ) : (
          <span style={{ fontSize: 11, color: '#D1D5DB' }}>— Tayinlanmagan</span>
        )}
      </div>

      {/* Muhimlik */}
      <div>
        <Badge label={priCfg.label} color={priCfg.color} bg={priCfg.bg}/>
      </div>

      {/* Muddat */}
      <div style={{ fontSize: 11, color: task.is_overdue ? '#DC2626' : '#6B7280', fontWeight: task.is_overdue ? 700 : 400 }}>
        {task.due_date ? formatDateTime(task.due_date) : '—'}
      </div>

      {/* Holat */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <SIcon size={11} color={stsCfg.color}/>
          <Badge label={stsCfg.label} color={stsCfg.color} bg={stsCfg.bg}/>
        </div>
        {task.requires_verification && task.status === 'completed' && (
          <div style={{ fontSize: 9, color: task.verification_status === 'verified' ? '#059669' : task.verification_status === 'failed' ? '#DC2626' : '#D97706', marginTop: 3 }}>
            {task.verification_status === 'verified' ? '✓ Tasdiqlandi'
             : task.verification_status === 'failed'  ? '✗ Rad etildi'
             : '⏳ Tasdiqlanmagan'}
          </div>
        )}
      </div>

      {/* Amallar */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {task.status === 'pending' && (
          <button style={{ ...S.btnSm, background: '#EEF2FF', color: '#1E3EB4' }} onClick={() => onAction('start', task)}>
            Boshlash
          </button>
        )}
        {task.status === 'in_progress' && (
          <button style={{ ...S.btnSm, background: '#ECFDF5', color: '#059669' }} onClick={() => onAction('complete', task)}>
            Bajarildi
          </button>
        )}
        {task.status === 'overdue' && (
          <button style={{ ...S.btnSm, background: '#FEF2F2', color: '#DC2626' }} onClick={() => onAction('complete', task)}>
            Yakunla
          </button>
        )}
        {task.status === 'completed' && task.requires_verification && task.verification_status === 'unverified' && (
          <button style={{ ...S.btnSm, background: '#F5F3FF', color: '#7C3AED' }} onClick={() => onAction('verify', task)}>
            <Camera size={10}/> Tasdiqla
          </button>
        )}
        {['pending', 'in_progress', 'overdue'].includes(task.status) && (
          <button style={{ ...S.btnSm, background: '#F9FAFB', color: '#9CA3AF' }} onClick={() => onAction('cancel', task)}>
            Bekor
          </button>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function EmployeesPage() {
  const qc = useQueryClient();

  // Tab
  const [tab, setTab] = useState<'employees' | 'tasks'>('employees');

  // Employee filters
  const [empSearch,   setEmpSearch]   = useState('');
  const [empStatus,   setEmpStatus]   = useState('');
  const [empPosition, setEmpPosition] = useState('');

  // Task filters
  const [taskStatus,  setTaskStatus]  = useState('');
  const [taskType,    setTaskType]    = useState('');
  const [taskEmpId,   setTaskEmpId]   = useState('');

  // Modals
  const [empModal,  setEmpModal]  = useState<{ open: boolean; emp: Employee | null }>({ open: false, emp: null });
  const [taskModal, setTaskModal] = useState<{ open: boolean; task: WorkerTask | null }>({ open: false, task: null });
  const [verifyModal, setVerifyModal] = useState<WorkerTask | null>(null);
  const [completeModal, setCompleteModal] = useState<WorkerTask | null>(null);
  const [completionNote, setCompletionNote] = useState('');

  // ── Queries ────────────────────────────────────────────────────────────
  const empStatsQ = useQuery({
    queryKey: ['emp-stats'],
    queryFn:  () => apiFetch<EmployeeStats>('/api/v1/employees/stats'),
    staleTime: 30_000,
  });

  const empListQ = useQuery({
    queryKey: ['employees', empSearch, empStatus, empPosition],
    queryFn:  () => apiFetch<EmployeeListResponse>(
      `/api/v1/employees/?size=100${empSearch ? `&search=${empSearch}` : ''}${empStatus ? `&status=${empStatus}` : ''}${empPosition ? `&position=${empPosition}` : ''}`
    ),
    staleTime: 30_000,
  });

  const taskStatsQ = useQuery({
    queryKey: ['task-stats'],
    queryFn:  () => apiFetch<WorkerTaskStats>('/api/v1/employees/tasks/stats'),
    staleTime: 30_000,
  });

  const taskListQ = useQuery({
    queryKey: ['worker-tasks', taskStatus, taskType, taskEmpId],
    queryFn:  () => apiFetch<WorkerTaskListResponse>(
      `/api/v1/employees/tasks/?size=100${taskStatus ? `&status=${taskStatus}` : ''}${taskType ? `&task_type=${taskType}` : ''}${taskEmpId ? `&employee_id=${taskEmpId}` : ''}`
    ),
    staleTime: 15_000,
  });

  const employees = empListQ.data?.items || [];
  const tasks     = taskListQ.data?.items || [];
  const empStats  = empStatsQ.data;
  const taskStats = taskStatsQ.data;

  // ── Mutations ──────────────────────────────────────────────────────────
  const inv = () => {
    qc.invalidateQueries({ queryKey: ['employees'] });
    qc.invalidateQueries({ queryKey: ['emp-stats'] });
    qc.invalidateQueries({ queryKey: ['worker-tasks'] });
    qc.invalidateQueries({ queryKey: ['task-stats'] });
  };

  const createEmpM = useMutation({
    mutationFn: (d: any) => apiFetch('/api/v1/employees/', { method: 'POST', body: JSON.stringify(d) }),
    onSuccess: () => { inv(); setEmpModal({ open: false, emp: null }); },
  });

  const updateEmpM = useMutation({
    mutationFn: ({ id, d }: any) => apiFetch(`/api/v1/employees/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
    onSuccess: () => { inv(); setEmpModal({ open: false, emp: null }); },
  });

  const deactivateEmpM = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/employees/${id}/deactivate`, { method: 'POST' }),
    onSuccess: inv,
  });

  const createTaskM = useMutation({
    mutationFn: (d: any) => apiFetch('/api/v1/employees/tasks/', { method: 'POST', body: JSON.stringify(d) }),
    onSuccess: () => { inv(); setTaskModal({ open: false, task: null }); },
  });

  const startTaskM = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/employees/tasks/${id}/start`, { method: 'POST' }),
    onSuccess: inv,
  });

  const completeTaskM = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) =>
      apiFetch(`/api/v1/employees/tasks/${id}/complete`, { method: 'POST', body: JSON.stringify({ completion_notes: notes || null }) }),
    onSuccess: () => { inv(); setCompleteModal(null); setCompletionNote(''); },
  });

  const cancelTaskM = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/employees/tasks/${id}/cancel`, { method: 'POST' }),
    onSuccess: inv,
  });

  const verifyTaskM = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiFetch(`/api/v1/employees/tasks/${id}/verify`, { method: 'POST', body: JSON.stringify({ verification_status: status }) }),
    onSuccess: () => { inv(); setVerifyModal(null); },
  });

  // ── Task action handler ────────────────────────────────────────────────
  const handleTaskAction = (action: string, task: WorkerTask) => {
    if (action === 'start')    startTaskM.mutate(task.id);
    if (action === 'cancel')   cancelTaskM.mutate(task.id);
    if (action === 'complete') { setCompleteModal(task); setCompletionNote(''); }
    if (action === 'verify')   setVerifyModal(task);
  };

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
        * { box-sizing: border-box; }
      `}</style>

      <div style={S.page}>
        <div style={S.wrap}>

          {/* ── Page header ── */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 800, color: '#0D1117', margin: 0, lineHeight: 1 }}>Hodimlar</h1>
              <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>Ferma xodimlari va ularning vazifalari</p>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              {tab === 'employees' && (
                <button style={S.btnPri} onClick={() => setEmpModal({ open: true, emp: null })}>
                  <Plus size={14}/> Xodim qo'shish
                </button>
              )}
              {tab === 'tasks' && (
                <button style={S.btnPri} onClick={() => setTaskModal({ open: true, task: null })}>
                  <Plus size={14}/> Vazifa yaratish
                </button>
              )}
            </div>
          </div>

          {/* ── Stat boxes ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
            <StatBox val={empStats?.total ?? '—'}         label="Jami xodim"      color="#1E3EB4"/>
            <StatBox val={empStats?.active ?? '—'}        label="Faol"            color="#059669"/>
            <StatBox val={empStats?.on_leave ?? '—'}      label="Ta'tilda"        color="#D97706"/>
            <StatBox val={taskStats?.pending ?? '—'}      label="Kutayotgan vazifa" color="#6B7280"/>
            <StatBox val={taskStats?.in_progress ?? '—'}  label="Bajarilmoqda"    color="#2563EB"/>
            <StatBox val={taskStats?.overdue ?? '—'}      label="Muddati o'tdi"   color={taskStats?.overdue ? '#DC2626' : '#9CA3AF'}/>
          </div>

          {/* ── Tabs ── */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 16, background: '#fff', padding: 4, borderRadius: 12, border: '1px solid #E8EBF2', width: 'fit-content' }}>
            {([
              { key: 'employees', label: 'Xodimlar', icon: Users },
              { key: 'tasks',     label: 'Vazifalar', icon: ClipboardList },
            ] as const).map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '8px 18px', borderRadius: 9, border: 'none',
                  background: tab === t.key ? '#1E3EB4' : 'transparent',
                  color:      tab === t.key ? '#fff'    : '#6B7280',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
                  fontFamily: 'inherit',
                }}
              >
                <t.icon size={14}/> {t.label}
              </button>
            ))}
          </div>

          {/* ════════════════════════════════════════════
              TAB 1: XODIMLAR
          ════════════════════════════════════════════ */}
          {tab === 'employees' && (
            <>
              {/* Filters */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
                  <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: '#9CA3AF' }}/>
                  <input style={{ ...S.inp, paddingLeft: 33 }} placeholder="Ism yoki telefon bo'yicha qidirish..." value={empSearch} onChange={e => setEmpSearch(e.target.value)}/>
                </div>
                <select style={S.sel} value={empStatus} onChange={e => setEmpStatus(e.target.value)}>
                  <option value="">Barcha holatlar</option>
                  <option value="active">Faol</option>
                  <option value="on_leave">Ta'tilda</option>
                  <option value="inactive">Ishdan ketgan</option>
                </select>
                <select style={S.sel} value={empPosition} onChange={e => setEmpPosition(e.target.value)}>
                  <option value="">Barcha lavozimlar</option>
                  {Object.entries(POSITION_CFG).map(([k, v]) => (
                    <option key={k} value={k}>{v.icon} {v.label}</option>
                  ))}
                </select>
              </div>

              {/* Grid */}
              {empListQ.isLoading ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF', fontSize: 14 }}>Yuklanmoqda...</div>
              ) : employees.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>
                  <Users size={40} style={{ opacity: 0.2, marginBottom: 12 }}/>
                  <div style={{ fontSize: 14 }}>Xodim topilmadi</div>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                  {employees.map(emp => (
                    <EmployeeCard
                      key={emp.id}
                      emp={emp}
                      onClick={() => setEmpModal({ open: true, emp })}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {/* ════════════════════════════════════════════
              TAB 2: VAZIFALAR
          ════════════════════════════════════════════ */}
          {tab === 'tasks' && (
            <>
              {/* Filters */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                <select style={S.sel} value={taskStatus} onChange={e => setTaskStatus(e.target.value)}>
                  <option value="">Barcha holatlar</option>
                  {Object.entries(TASK_STATUS_CFG).map(([k, v]) => (
                    <option key={k} value={k}>{v.label}</option>
                  ))}
                </select>
                <select style={S.sel} value={taskType} onChange={e => setTaskType(e.target.value)}>
                  <option value="">Barcha turlar</option>
                  {Object.entries(TASK_TYPE_CFG).map(([k, v]) => (
                    <option key={k} value={k}>{v.icon} {v.label}</option>
                  ))}
                </select>
                <select style={S.sel} value={taskEmpId} onChange={e => setTaskEmpId(e.target.value)}>
                  <option value="">Barcha xodimlar</option>
                  {employees.map(e => (
                    <option key={e.id} value={e.id}>{e.full_name}</option>
                  ))}
                </select>
                {/* Completion rate */}
                {taskStats && (
                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px', background: '#fff', border: '1px solid #E8EBF2', borderRadius: 9 }}>
                    <CheckCircle size={13} color="#059669"/>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#059669', fontFamily: "'JetBrains Mono', monospace" }}>
                      {taskStats.completion_rate}%
                    </span>
                    <span style={{ fontSize: 11, color: '#9CA3AF' }}>bajarish ko'rsatkichi</span>
                  </div>
                )}
              </div>

              {/* Table */}
              <div style={S.card}>
                {/* Header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '2.5fr 1.2fr 100px 110px 120px 140px',
                  padding: '10px 20px', background: '#FAFBFD', borderBottom: '1px solid #E8EBF2', gap: 8,
                }}>
                  {['Vazifa', 'Xodim', 'Muhimlik', 'Muddat', 'Holat', 'Amal'].map(h => (
                    <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</span>
                  ))}
                </div>

                {taskListQ.isLoading ? (
                  <div style={{ textAlign: 'center', padding: 50, color: '#9CA3AF', fontSize: 13 }}>Yuklanmoqda...</div>
                ) : tasks.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 50 }}>
                    <ClipboardList size={36} style={{ color: '#E5E7EB', marginBottom: 12 }}/>
                    <div style={{ fontSize: 13, color: '#9CA3AF' }}>Vazifa topilmadi</div>
                  </div>
                ) : (
                  tasks.map(task => (
                    <TaskRow key={task.id} task={task} onAction={handleTaskAction}/>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Employee Modal ── */}
      {empModal.open && (
        <EmployeeModal
          emp={empModal.emp}
          onClose={() => setEmpModal({ open: false, emp: null })}
          onSave={d => {
            if (empModal.emp) updateEmpM.mutate({ id: empModal.emp.id, d });
            else              createEmpM.mutate(d);
          }}
        />
      )}

      {/* ── Task Modal ── */}
      {taskModal.open && (
        <TaskModal
          employees={employees}
          task={taskModal.task}
          onClose={() => setTaskModal({ open: false, task: null })}
          onSave={d => createTaskM.mutate(d)}
        />
      )}

      {/* ── Complete Modal ── */}
      {completeModal && (
        <div style={S.overlay} onClick={() => setCompleteModal(null)}>
          <div style={{ ...S.modal, maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid #F3F4F6' }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>Vazifani yakunlash</div>
              <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 3 }}>{completeModal.title}</div>
            </div>
            <div style={{ padding: '16px 22px' }}>
              <label style={S.label}>BAJARUVCHINNING IZOHI (ixtiyoriy)</label>
              <textarea
                style={{ ...S.inp, resize: 'vertical', minHeight: 80 } as any}
                value={completionNote}
                onChange={e => setCompletionNote(e.target.value)}
                placeholder="Vazifa bajarildi. Qo'shimcha izoh..."
              />
            </div>
            <div style={{ padding: '12px 22px 18px', borderTop: '1px solid #F3F4F6', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button style={S.btnSec} onClick={() => setCompleteModal(null)}>Bekor</button>
              <button
                style={{ ...S.btnPri, background: '#059669' }}
                onClick={() => completeTaskM.mutate({ id: completeModal.id, notes: completionNote })}
              >
                <CheckCircle size={13}/> Bajarildi deb belgilash
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Verify Modal ── */}
      {verifyModal && (
        <div style={S.overlay} onClick={() => setVerifyModal(null)}>
          <div style={{ ...S.modal, maxWidth: 400 }} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid #F3F4F6' }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#0D1117' }}>
                <Camera size={16} style={{ marginRight: 8, verticalAlign: 'middle', color: '#7C3AED' }}/>
                Kamera tasdiqlash
              </div>
              <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 3 }}>{verifyModal.title}</div>
            </div>
            <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>
                Kamera yozuvlarini tekshirgandan so'ng tasdiqlash natijasini kiriting:
              </p>
              <button
                style={{ ...S.btnSm, background: '#ECFDF5', color: '#059669', fontSize: 13, padding: '10px 16px', width: '100%', textAlign: 'center' }}
                onClick={() => verifyTaskM.mutate({ id: verifyModal.id, status: 'verified' })}
              >
                <CheckCircle size={13} style={{ marginRight: 6 }}/> Tasdiqlandi — Vazifa bajarilgan ko'rindi
              </button>
              <button
                style={{ ...S.btnSm, background: '#FEF2F2', color: '#DC2626', fontSize: 13, padding: '10px 16px', width: '100%', textAlign: 'center' }}
                onClick={() => verifyTaskM.mutate({ id: verifyModal.id, status: 'failed' })}
              >
                <XCircle size={13} style={{ marginRight: 6 }}/> Rad etildi — Kameradan ko'rinmadi
              </button>
            </div>
            <div style={{ padding: '10px 22px 16px', borderTop: '1px solid #F3F4F6', display: 'flex', justifyContent: 'flex-end' }}>
              <button style={S.btnSec} onClick={() => setVerifyModal(null)}>Yopish</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
