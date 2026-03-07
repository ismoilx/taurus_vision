/**
 * Taurus Vision — Farm Tasks Page (Sprint 19-20)
 *
 * Ferma vazifalarini boshqarish interfeysi.
 *
 * API:
 *   GET    /api/v1/tasks/       — ro'yxat
 *   GET    /api/v1/tasks/stats  — statistika
 *   POST   /api/v1/tasks/       — yaratish
 *   PATCH  /api/v1/tasks/{id}   — yangilash
 *   POST   /api/v1/tasks/{id}/start    — boshlash
 *   POST   /api/v1/tasks/{id}/complete — bajarildi
 *   POST   /api/v1/tasks/{id}/cancel   — bekor qilish
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2, Clock, AlertTriangle, Plus,
  RefreshCw, Play, XCircle, Filter,
  Stethoscope, Syringe, Droplets, Weight,
  ClipboardList, Scissors, Brush, Tag,
  Truck, Wheat, AlarmClock, MoreHorizontal,
} from 'lucide-react';
import { formatDistanceToNow, format, isPast } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';
import { useIsMobile } from '../hooks/useResponsive';

// ─── Types ───────────────────────────────────────────────────────────────────

type TaskStatus   = 'pending' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';
type TaskPriority = 'low' | 'medium' | 'high' | 'critical';
type TaskType     =
  | 'vaccination' | 'health_check' | 'medication' | 'quarantine'
  | 'cleaning' | 'grooming' | 'hoof_trim'
  | 'feeding' | 'watering' | 'supplement'
  | 'weighing' | 'tagging' | 'transfer' | 'other';

interface FarmTask {
  id: number;
  title: string;
  description?: string;
  task_type: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  due_date?: string;
  completed_at?: string;
  animal_id?: number;
  assigned_to?: number;
  is_overdue: boolean;
  notes?: string;
  created_at: string;
}

interface TaskListResponse {
  items: FarmTask[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface TaskStats {
  total_open: number;
  total_overdue: number;
  total_today: number;
  total_completed_today: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  critical_overdue: FarmTask[];
}

interface CreateTaskForm {
  title: string;
  task_type: TaskType;
  priority: TaskPriority;
  due_date: string;
  description: string;
  animal_id: string;
  assigned_to: string;
}

// ─── Config ──────────────────────────────────────────────────────────────────

const TASK_TYPE_CONFIG: Record<TaskType, { label: string; icon: React.ReactNode; color: string }> = {
  vaccination:  { label: 'Emlash',        icon: <Syringe  size={14}/>, color: '#7C3AED' },
  health_check: { label: 'Ko\'rik',       icon: <Stethoscope size={14}/>, color: '#0891B2' },
  medication:   { label: 'Dori',          icon: <Droplets size={14}/>, color: '#059669' },
  quarantine:   { label: 'Karantin',      icon: <AlertTriangle size={14}/>, color: '#DC2626' },
  cleaning:     { label: 'Tozalash',      icon: <Brush    size={14}/>, color: '#D97706' },
  grooming:     { label: 'Parvarishlash', icon: <Scissors size={14}/>, color: '#8B5CF6' },
  hoof_trim:    { label: 'Tuyoq',         icon: <Scissors size={14}/>, color: '#6366F1' },
  feeding:      { label: 'Oziqlanish',    icon: <Wheat    size={14}/>, color: '#16A34A' },
  watering:     { label: 'Suv',           icon: <Droplets size={14}/>, color: '#0369A1' },
  supplement:   { label: 'Qo\'shimcha',   icon: <Plus     size={14}/>, color: '#65A30D' },
  weighing:     { label: 'Og\'irlik',     icon: <Weight   size={14}/>, color: '#92400E' },
  tagging:      { label: 'Belgi',         icon: <Tag      size={14}/>, color: '#374151' },
  transfer:     { label: 'Ko\'chirish',   icon: <Truck    size={14}/>, color: '#6B7280' },
  other:        { label: 'Boshqa',        icon: <ClipboardList size={14}/>, color: '#9CA3AF' },
};

const PRIORITY_CONFIG: Record<TaskPriority, { label: string; color: string; bg: string; border: string }> = {
  critical: { label: 'Kritik',  color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
  high:     { label: 'Yuqori',  color: '#EA580C', bg: '#FFF7ED', border: '#FED7AA' },
  medium:   { label: 'O\'rta',  color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  low:      { label: 'Past',    color: '#6B7280', bg: '#F9FAFB', border: '#E5E7EB' },
};

const STATUS_CONFIG: Record<TaskStatus, { label: string; color: string; bg: string }> = {
  pending:     { label: 'Kutmoqda',   color: '#6B7280', bg: '#F3F4F6' },
  in_progress: { label: 'Jarayonda', color: '#2563EB', bg: '#EFF6FF' },
  completed:   { label: 'Bajarildi', color: '#16A34A', bg: '#F0FDF4' },
  overdue:     { label: 'Muddati o\'tdi', color: '#DC2626', bg: '#FEF2F2' },
  cancelled:   { label: 'Bekor',     color: '#9CA3AF', bg: '#F9FAFB' },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDue(dateStr?: string, isOverdue?: boolean): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isOverdue) return `${format(d, 'dd MMM, HH:mm')} ⚠️`;
  return format(d, 'dd MMM, HH:mm');
}

// ─── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({
  label, value, color, bg,
}: { label: string; value: number; color: string; bg: string }) {
  return (
    <div style={{
      background: bg,
      border: `1px solid ${color}30`,
      borderRadius: 12,
      padding: '14px 18px',
      flex: 1,
      minWidth: 120,
    }}>
      <div style={{ fontSize: 24, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2, fontWeight: 500 }}>
        {label}
      </div>
    </div>
  );
}

// ─── Task Row ─────────────────────────────────────────────────────────────────

function TaskRow({
  task,
  onStart,
  onComplete,
  onCancel,
  loading,
}: {
  task: FarmTask;
  onStart: (id: number) => void;
  onComplete: (id: number) => void;
  onCancel: (id: number) => void;
  loading: boolean;
}) {
  const typeCfg     = TASK_TYPE_CONFIG[task.task_type];
  const priorityCfg = PRIORITY_CONFIG[task.priority];
  const statusCfg   = STATUS_CONFIG[task.status];

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${task.is_overdue ? '#FECACA' : '#E4E7ED'}`,
      borderLeft: `3px solid ${task.is_overdue ? '#DC2626' : priorityCfg.color}`,
      borderRadius: 10,
      padding: '12px 16px',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    }}>

      {/* Type icon */}
      <div style={{
        width: 34, height: 34,
        borderRadius: 8,
        background: `${typeCfg.color}15`,
        display: 'grid', placeItems: 'center',
        flexShrink: 0,
        color: typeCfg.color,
      }}>
        {typeCfg.icon}
      </div>

      {/* Main info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 14, fontWeight: 600,
            color: '#0D1117',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            maxWidth: 320,
          }}>
            {task.title}
          </span>

          {/* Priority badge */}
          <span style={{
            fontSize: 10, fontWeight: 700,
            letterSpacing: '0.05em',
            padding: '2px 7px',
            borderRadius: 20,
            background: priorityCfg.bg,
            color: priorityCfg.color,
            border: `1px solid ${priorityCfg.border}`,
          }}>
            {priorityCfg.label.toUpperCase()}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
          {/* Task type */}
          <span style={{ fontSize: 11, color: typeCfg.color, fontWeight: 500 }}>
            {typeCfg.label}
          </span>

          {/* Due date */}
          <span style={{
            fontSize: 11,
            color: task.is_overdue ? '#DC2626' : '#6B7280',
            display: 'flex', alignItems: 'center', gap: 3,
            fontWeight: task.is_overdue ? 600 : 400,
          }}>
            <AlarmClock size={11}/>
            {formatDue(task.due_date, task.is_overdue)}
          </span>

          {/* Animal */}
          {task.animal_id && (
            <span style={{ fontSize: 11, color: '#6B7280' }}>
              🐄 #{task.animal_id}
            </span>
          )}
        </div>
      </div>

      {/* Status */}
      <span style={{
        fontSize: 11, fontWeight: 600,
        padding: '3px 10px',
        borderRadius: 20,
        background: statusCfg.bg,
        color: statusCfg.color,
        flexShrink: 0,
        whiteSpace: 'nowrap',
      }}>
        {statusCfg.label}
      </span>

      {/* Actions */}
      {task.status !== 'completed' && task.status !== 'cancelled' && (
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          {(task.status === 'pending' || task.status === 'overdue') && (
            <button
              onClick={() => onStart(task.id)}
              disabled={loading}
              title="Boshlash"
              style={{
                padding: '5px 10px', borderRadius: 7,
                background: '#EFF6FF', color: '#2563EB',
                border: '1px solid #BFDBFE',
                cursor: 'pointer', fontSize: 11, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              <Play size={11}/> Boshlash
            </button>
          )}

          <button
            onClick={() => onComplete(task.id)}
            disabled={loading}
            title="Bajarildi"
            style={{
              padding: '5px 10px', borderRadius: 7,
              background: '#F0FDF4', color: '#16A34A',
              border: '1px solid #BBF7D0',
              cursor: 'pointer', fontSize: 11, fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            <CheckCircle2 size={11}/> Bajarildi
          </button>

          <button
            onClick={() => onCancel(task.id)}
            disabled={loading}
            title="Bekor qilish"
            style={{
              padding: '5px 7px', borderRadius: 7,
              background: '#F9FAFB', color: '#9CA3AF',
              border: '1px solid #E5E7EB',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center',
            }}
          >
            <XCircle size={13}/>
          </button>
        </div>
      )}

      {task.status === 'completed' && (
        <span style={{ fontSize: 11, color: '#16A34A', flexShrink: 0 }}>
          ✓ {task.completed_at
            ? formatDistanceToNow(new Date(task.completed_at), { addSuffix: true })
            : ''}
        </span>
      )}
    </div>
  );
}

// ─── Create Modal ─────────────────────────────────────────────────────────────

function CreateModal({
  onClose,
  onSubmit,
  loading,
}: {
  onClose: () => void;
  onSubmit: (data: CreateTaskForm) => void;
  loading: boolean;
}) {
  const [form, setForm] = useState<CreateTaskForm>({
    title:       '',
    task_type:   'health_check',
    priority:    'medium',
    due_date:    '',
    description: '',
    animal_id:   '',
    assigned_to: '',
  });

  const set = (k: keyof CreateTaskForm, v: string) =>
    setForm(f => ({ ...f, [k]: v }));

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.4)',
      display: 'grid', placeItems: 'center',
      padding: 16,
    }} onClick={onClose}>
      <div
        style={{
          background: '#fff', borderRadius: 16,
          width: '100%', maxWidth: 480,
          padding: '24px 28px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        }}
        onClick={e => e.stopPropagation()}
      >
        <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700, color: '#0D1117' }}>
          Yangi Vazifa
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Title */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
              Sarlavha *
            </label>
            <input
              value={form.title}
              onChange={e => set('title', e.target.value)}
              placeholder="Masalan: JNV-042 — FMD emlash"
              style={{
                width: '100%', padding: '8px 12px',
                border: '1px solid #E4E7ED', borderRadius: 8,
                fontSize: 13, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Type + Priority row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
                Vazifa turi *
              </label>
              <select
                value={form.task_type}
                onChange={e => set('task_type', e.target.value as TaskType)}
                style={{
                  width: '100%', padding: '8px 10px',
                  border: '1px solid #E4E7ED', borderRadius: 8,
                  fontSize: 13, background: '#fff', outline: 'none',
                }}
              >
                {Object.entries(TASK_TYPE_CONFIG).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
                Muhimlik *
              </label>
              <select
                value={form.priority}
                onChange={e => set('priority', e.target.value as TaskPriority)}
                style={{
                  width: '100%', padding: '8px 10px',
                  border: '1px solid #E4E7ED', borderRadius: 8,
                  fontSize: 13, background: '#fff', outline: 'none',
                }}
              >
                {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Due date */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
              Muddat
            </label>
            <input
              type="datetime-local"
              value={form.due_date}
              onChange={e => set('due_date', e.target.value)}
              style={{
                width: '100%', padding: '8px 12px',
                border: '1px solid #E4E7ED', borderRadius: 8,
                fontSize: 13, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Animal + Assigned row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
                Jonivor ID
              </label>
              <input
                type="number"
                value={form.animal_id}
                onChange={e => set('animal_id', e.target.value)}
                placeholder="Ixtiyoriy"
                style={{
                  width: '100%', padding: '8px 12px',
                  border: '1px solid #E4E7ED', borderRadius: 8,
                  fontSize: 13, outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
                Bajaruvchi ID
              </label>
              <input
                type="number"
                value={form.assigned_to}
                onChange={e => set('assigned_to', e.target.value)}
                placeholder="Ixtiyoriy"
                style={{
                  width: '100%', padding: '8px 12px',
                  border: '1px solid #E4E7ED', borderRadius: 8,
                  fontSize: 13, outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 5 }}>
              Tavsif
            </label>
            <textarea
              value={form.description}
              onChange={e => set('description', e.target.value)}
              placeholder="Batafsil ko'rsatmalar..."
              rows={3}
              style={{
                width: '100%', padding: '8px 12px',
                border: '1px solid #E4E7ED', borderRadius: 8,
                fontSize: 13, outline: 'none', resize: 'vertical',
                boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '9px 18px', borderRadius: 9,
              background: '#F3F4F6', color: '#6B7280',
              border: '1px solid #E4E7ED',
              cursor: 'pointer', fontSize: 13, fontWeight: 600,
            }}
          >
            Bekor
          </button>
          <button
            onClick={() => onSubmit(form)}
            disabled={!form.title.trim() || loading}
            style={{
              padding: '9px 22px', borderRadius: 9,
              background: form.title.trim() ? '#1E3EB4' : '#E4E7ED',
              color: form.title.trim() ? '#fff' : '#9CA3AF',
              border: 'none',
              cursor: form.title.trim() ? 'pointer' : 'default',
              fontSize: 13, fontWeight: 600,
            }}
          >
            {loading ? 'Saqlanmoqda...' : 'Saqlash'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TasksPage() {
  const qc = useQueryClient();
  const isMobile = useIsMobile();

  const [statusFilter,   setStatusFilter]   = useState<string>('open');
  const [typeFilter,     setTypeFilter]     = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [showCreate,     setShowCreate]     = useState(false);
  const [actionLoading,  setActionLoading]  = useState<number | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────

  const statsQuery = useQuery<TaskStats>({
    queryKey: ['task-stats'],
    queryFn:  () => apiFetch('/api/v1/tasks/stats'),
    refetchInterval: 60_000,
  });

  // Build query params
  const params = new URLSearchParams();
  if (statusFilter === 'open') {
    ['pending', 'in_progress', 'overdue'].forEach(s => params.append('status', s));
  } else if (statusFilter && statusFilter !== 'all') {
    params.append('status', statusFilter);
  }
  if (typeFilter)     params.set('task_type', typeFilter);
  if (priorityFilter) params.set('priority',  priorityFilter);
  params.set('page_size', '50');

  const tasksQuery = useQuery<TaskListResponse>({
    queryKey: ['tasks', statusFilter, typeFilter, priorityFilter],
    queryFn:  () => apiFetch(`/api/v1/tasks/?${params.toString()}`),
    refetchInterval: 30_000,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tasks'] });
    qc.invalidateQueries({ queryKey: ['task-stats'] });
  };

  const createMutation = useMutation({
    mutationFn: (data: CreateTaskForm) => {
      const body: Record<string, unknown> = {
        title:     data.title,
        task_type: data.task_type,
        priority:  data.priority,
      };
      if (data.due_date)    body.due_date    = new Date(data.due_date).toISOString();
      if (data.description) body.description = data.description;
      if (data.animal_id)   body.animal_id   = Number(data.animal_id);
      if (data.assigned_to) body.assigned_to = Number(data.assigned_to);
      return apiFetch('/api/v1/tasks/', { method: 'POST', body: JSON.stringify(body) });
    },
    onSuccess: () => { setShowCreate(false); invalidate(); },
  });

  const startMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/tasks/${id}/start`, { method: 'POST' }),
    onSuccess: invalidate,
  });

  const completeMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/tasks/${id}/complete`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: invalidate,
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/tasks/${id}/cancel`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: invalidate,
  });

  const handleAction = async (
    action: 'start' | 'complete' | 'cancel',
    id: number,
  ) => {
    setActionLoading(id);
    try {
      if (action === 'start')    await startMutation.mutateAsync(id);
      if (action === 'complete') await completeMutation.mutateAsync(id);
      if (action === 'cancel')   await cancelMutation.mutateAsync(id);
    } finally {
      setActionLoading(null);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const stats = statsQuery.data;
  const tasks = tasksQuery.data?.items ?? [];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: isMobile ? '14px 12px 80px' : '24px 20px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: isMobile ? 18 : 22, fontWeight: 700, color: '#0D1117' }}>
            Farm Vazifalari
          </h1>
          {!isMobile && (
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280' }}>
              Emlash, ko'rik, parvarishlash va boshqa ferma vazifalari
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => invalidate()}
            style={{
              padding: '8px 12px', borderRadius: 9,
              background: '#F3F4F6', color: '#6B7280',
              border: '1px solid #E4E7ED',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 13,
            }}
          >
            <RefreshCw size={14}/>
          </button>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              padding: '8px 16px', borderRadius: 9,
              background: '#1E3EB4', color: '#fff',
              border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 13, fontWeight: 600,
            }}
          >
            <Plus size={15}/> Yangi Vazifa
          </button>
        </div>
      </div>

      {/* Stat cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2,1fr)' : 'repeat(4,1fr)', gap: 10, marginBottom: 20 }}>
          <StatCard label="Ochiq"          value={stats.total_open}            color="#2563EB" bg="#EFF6FF"/>
          <StatCard label="Muddati o'tdi"  value={stats.total_overdue}         color="#DC2626" bg="#FEF2F2"/>
          <StatCard label="Bugun"          value={stats.total_today}           color="#D97706" bg="#FFFBEB"/>
          <StatCard label="Bugun bajarildi" value={stats.total_completed_today} color="#16A34A" bg="#F0FDF4"/>
        </div>
      )}

      {/* Critical overdue warning */}
      {stats && stats.critical_overdue.length > 0 && (
        <div style={{
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: 10,
          padding: '12px 16px',
          marginBottom: 16,
          display: 'flex', alignItems: 'flex-start', gap: 10,
        }}>
          <AlertTriangle size={16} color="#DC2626" style={{ flexShrink: 0, marginTop: 1 }}/>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#DC2626', marginBottom: 4 }}>
              Muddati o'tgan kritik vazifalar ({stats.critical_overdue.length} ta)
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {stats.critical_overdue.map(t => (
                <span key={t.id} style={{
                  fontSize: 11, padding: '2px 8px',
                  background: '#fff', border: '1px solid #FECACA',
                  borderRadius: 6, color: '#DC2626',
                }}>
                  {t.title}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        background: '#fff', border: '1px solid #E4E7ED',
        borderRadius: 12, padding: '12px 16px',
        marginBottom: 16,
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      }}>
        <Filter size={14} color="#6B7280"/>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{
            padding: '6px 10px', borderRadius: 7,
            border: '1px solid #E4E7ED', fontSize: 12,
            background: '#F9FAFB', outline: 'none', cursor: 'pointer',
          }}
        >
          <option value="open">Ochiq (pending + jarayonda + muddati o'tgan)</option>
          <option value="pending">Kutmoqda</option>
          <option value="in_progress">Jarayonda</option>
          <option value="overdue">Muddati o'tdi</option>
          <option value="completed">Bajarildi</option>
          <option value="all">Barchasi</option>
        </select>

        {/* Type filter */}
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          style={{
            padding: '6px 10px', borderRadius: 7,
            border: '1px solid #E4E7ED', fontSize: 12,
            background: '#F9FAFB', outline: 'none', cursor: 'pointer',
          }}
        >
          <option value="">Barcha turlar</option>
          {Object.entries(TASK_TYPE_CONFIG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>

        {/* Priority filter */}
        <select
          value={priorityFilter}
          onChange={e => setPriorityFilter(e.target.value)}
          style={{
            padding: '6px 10px', borderRadius: 7,
            border: '1px solid #E4E7ED', fontSize: 12,
            background: '#F9FAFB', outline: 'none', cursor: 'pointer',
          }}
        >
          <option value="">Barcha muhimlik</option>
          {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>

        {/* Count */}
        {tasksQuery.data && (
          <span style={{ fontSize: 12, color: '#6B7280', marginLeft: 'auto' }}>
            {tasksQuery.data.total} ta vazifa
          </span>
        )}
      </div>

      {/* Task list */}
      {tasksQuery.isLoading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF', fontSize: 14 }}>
          Yuklanmoqda...
        </div>
      ) : tasks.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '48px 20px',
          background: '#F9FAFB', borderRadius: 12,
          border: '1px dashed #E4E7ED',
        }}>
          <ClipboardList size={32} color="#D1D5DB" style={{ margin: '0 auto 12px' }}/>
          <div style={{ fontSize: 14, color: '#9CA3AF', fontWeight: 500 }}>
            Vazifalar topilmadi
          </div>
          <div style={{ fontSize: 12, color: '#D1D5DB', marginTop: 4 }}>
            Filtrni o'zgartirib ko'ring yoki yangi vazifa qo'shing
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tasks.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              onStart={id => handleAction('start', id)}
              onComplete={id => handleAction('complete', id)}
              onCancel={id => handleAction('cancel', id)}
              loading={actionLoading === task.id}
            />
          ))}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onSubmit={data => createMutation.mutate(data)}
          loading={createMutation.isPending}
        />
      )}
    </div>
  );
}