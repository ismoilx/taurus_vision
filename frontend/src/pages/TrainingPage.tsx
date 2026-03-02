/**
 * TrainingPage — Custom YOLO Fine-Tuning Boshqaruvi (Sprint 15-16)
 *
 * IMKONIYATLAR:
 *   - Dataset holati: yig'ilgan kadrlar soni, tayyor ekanlik indikatori
 *   - Training boshlash formasi (admin/manager): nom, epochlar, batch, img_size, auto_deploy
 *   - Barcha training run lar ro'yxati: holat, vaqt, metrikalar
 *   - Run tanlash → batafsil metrikalar: mAP50, precision, recall, loss
 *   - Aktiv training uchun real-vaqt polling (har 5 soniyada)
 *   - Model deploy: mAP50 taqqoslash, force deploy
 *   - Run o'chirish (pending/failed)
 *   - Deployed modelni ko'rsatish
 *
 * BACKEND:
 *   GET    /training/dataset-stats
 *   GET    /training/runs
 *   GET    /training/runs/{run_id}
 *   POST   /training/runs
 *   POST   /training/runs/{run_id}/deploy
 *   DELETE /training/runs/{run_id}
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Cpu, Database, PlayCircle, CheckCircle2, XCircle,
  Clock, Trash2, Upload, RefreshCw, ChevronRight,
  AlertTriangle, BarChart2, Target, Layers,
  Settings, Info, Zap, Activity, TrendingUp,
  Image, FlaskConical, Eye, Award,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts';
import { apiFetch } from '../utils/apiFetch';

// =============================================================================
// TYPES
// =============================================================================

type RunStatus =
  | 'pending'
  | 'collecting'
  | 'building'
  | 'training'
  | 'evaluating'
  | 'completed'
  | 'failed'
  | 'deployed';

interface DatasetStats {
  total_frames:    number;
  min_required:    number;
  is_ready:        boolean;
  cameras:         Record<string, number>;
  frames_dir:      string;
  collector_stats: Record<string, unknown> | null;
}

interface TrainingMetrics {
  map50:        number;
  map50_95:     number;
  precision:    number;
  recall:       number;
  box_loss:     number;
  cls_loss:     number;
  epochs_done:  number;
  best_epoch:   number;
  duration_sec: number;
}

interface DatasetInfo {
  n_total:     number;
  n_train:     number;
  n_val:       number;
  dataset_dir: string;
  yaml_path:   string;
  classes:     Record<string, string>;
}

interface TrainingRun {
  id:              number;
  run_name:        string;
  status:          RunStatus;
  base_model_name: string;
  epochs:          number;
  batch_size:      number;
  img_size:        number;
  freeze_layers:   number;
  dataset_info:    DatasetInfo | null;
  started_at:      string | null;
  completed_at:    string | null;
  metrics:         TrainingMetrics | null;
  error_message:   string | null;
  model_path:      string | null;
  is_deployed:     boolean;
  deployed_at:     string | null;
  notes:           string | null;
  created_at:      string;
  updated_at:      string;
  duration_seconds: number | null;
}

interface TrainingListResponse {
  total: number;
  items: TrainingRun[];
}

interface StartRequest {
  run_name:      string;
  epochs:        number;
  batch_size:    number;
  img_size:      number;
  freeze_layers: number;
  auto_deploy:   boolean;
  notes:         string;
}

interface StartResponse {
  run_id:   number;
  run_name: string;
  task_id:  string;
  message:  string;
}

interface DeployResponse {
  run_id:     number;
  model_path: string;
  map50:      number | null;
  message:    string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const STATUS_CFG: Record<RunStatus, {
  label: string; color: string; bg: string; border: string;
  icon: React.ElementType; pulse?: boolean;
}> = {
  pending:    { label: 'Kutmoqda',    color: '#6b7280', bg: '#f9fafb', border: '#e5e7eb', icon: Clock       },
  collecting: { label: 'Kadrlar',     color: '#6366f1', bg: '#eef2ff', border: '#c7d2fe', icon: Image       },
  building:   { label: 'Dataset',     color: '#8b5cf6', bg: '#f5f3ff', border: '#ddd6fe', icon: Database    },
  training:   { label: 'O\'qitilmoqda', color: '#f59e0b', bg: '#fffbeb', border: '#fde68a', icon: Cpu, pulse: true },
  evaluating: { label: 'Tekshirilmoqda', color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe', icon: FlaskConical, pulse: true },
  completed:  { label: 'Tayyor',      color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0', icon: CheckCircle2 },
  failed:     { label: 'Xato',        color: '#ef4444', bg: '#fef2f2', border: '#fecaca', icon: XCircle      },
  deployed:   { label: 'Ishlatilmoqda', color: '#1E3EB4', bg: '#eff6ff', border: '#93c5fd', icon: Zap         },
};

const ACTIVE_STATUSES: RunStatus[] = ['pending', 'collecting', 'building', 'training', 'evaluating'];

// =============================================================================
// SMALL COMPONENTS
// =============================================================================

function StatusBadge({ status, size = 'sm' }: { status: RunStatus; size?: 'xs' | 'sm' }) {
  const cfg = STATUS_CFG[status] ?? STATUS_CFG.pending;
  const Icon = cfg.icon;
  const pad = size === 'xs' ? 'px-1.5 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${pad}`}
      style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}
    >
      <Icon size={11} className={cfg.pulse ? 'animate-pulse' : ''} />
      {cfg.label}
    </span>
  );
}

function MetricCard({
  label, value, unit, color, sub,
}: {
  label: string; value: string | number; unit?: string; color?: string; sub?: string;
}) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 flex flex-col gap-1">
      <div className="text-xs text-gray-400 font-medium">{label}</div>
      <div className="flex items-end gap-1">
        <span
          className="text-xl font-black tabular-nums leading-none"
          style={{ color: color ?? '#111827' }}
        >
          {value}
        </span>
        {unit && <span className="text-xs text-gray-400 mb-0.5">{unit}</span>}
      </div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

function ProgressBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${Math.min(100, Math.max(0, pct))}%`, backgroundColor: color }}
      />
    </div>
  );
}

function SectionTitle({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={15} className="text-indigo-500" />
      <h2 className="font-semibold text-gray-800 text-sm">{title}</h2>
    </div>
  );
}

function formatDuration(sec: number | null): string {
  if (!sec) return '—';
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`;
  return `${Math.floor(sec / 3600)}s ${Math.floor((sec % 3600) / 60)}m`;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('uz-UZ', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

// =============================================================================
// DATASET STATUS CARD
// =============================================================================

function DatasetStatusCard({ stats, isLoading }: { stats: DatasetStats | undefined; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 animate-pulse">
        <div className="h-4 bg-gray-100 rounded w-40 mb-4" />
        <div className="h-12 bg-gray-100 rounded" />
      </div>
    );
  }

  const total    = stats?.total_frames ?? 0;
  const required = stats?.min_required ?? 30;
  const pct      = Math.min(100, (total / required) * 100);
  const ready    = stats?.is_ready ?? false;
  const cameras  = stats?.cameras ?? {};
  const camCount = Object.keys(cameras).length;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <SectionTitle icon={Image} title="Yig'ilgan Training Kadrlar" />

      <div className="flex items-end justify-between mb-3">
        <div>
          <span
            className="text-3xl font-black tabular-nums"
            style={{ color: ready ? '#10b981' : total > 0 ? '#f59e0b' : '#9ca3af' }}
          >
            {total.toLocaleString()}
          </span>
          <span className="text-sm text-gray-400 ml-2">/ {required} minimal</span>
        </div>
        {ready ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-green-50 text-green-700 text-xs font-bold border border-green-200">
            <CheckCircle2 size={12} /> Training uchun tayyor
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-bold border border-amber-200">
            <Clock size={12} /> {required - total} kadr kerak
          </span>
        )}
      </div>

      <ProgressBar pct={pct} color={ready ? '#10b981' : '#f59e0b'} />

      {camCount > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(cameras).map(([cam, count]) => (
            <span key={cam} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-medium border border-indigo-100">
              <Eye size={10} />
              {cam}: {count} kadr
            </span>
          ))}
        </div>
      )}

      {!ready && (
        <p className="mt-3 text-xs text-gray-400 leading-relaxed">
          Detection pipeline ishlayotganda kadrlar avtomatik yig'iladi. 
          Har 50 ta deteksiyadan 1 ta kadr saqlanadi.
        </p>
      )}
    </div>
  );
}

// =============================================================================
// RUN DETAIL PANEL
// =============================================================================

function RunDetailPanel({
  run,
  onDeploy,
  onDelete,
  isDeploying,
  isDeleting,
  isAdmin,
}: {
  run: TrainingRun;
  onDeploy: (force: boolean) => void;
  onDelete: () => void;
  isDeploying: boolean;
  isDeleting: boolean;
  isAdmin: boolean;
}) {
  const [showForce, setShowForce] = useState(false);
  const m = run.metrics;

  const metricsData = m
    ? [
        { name: 'mAP50',    value: +(m.map50    * 100).toFixed(1), color: '#6366f1' },
        { name: 'Precision',value: +(m.precision * 100).toFixed(1), color: '#10b981' },
        { name: 'Recall',   value: +(m.recall    * 100).toFixed(1), color: '#3b82f6' },
      ]
    : [];

  return (
    <div className="flex flex-col gap-5">

      {/* Header */}
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-bold text-gray-900 text-base leading-tight">{run.run_name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={run.status} />
              {run.is_deployed && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700 font-bold">
                  <Award size={10} /> Faol model
                </span>
              )}
            </div>
          </div>
          <span className="text-xs text-gray-400 font-mono shrink-0">#{run.id}</span>
        </div>
      </div>

      {/* Hyperparametrlar */}
      <div>
        <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Konfiguratsiya</div>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label="Base model"   value={run.base_model_name} />
          <MetricCard label="Epochlar"     value={run.epochs} />
          <MetricCard label="Batch size"   value={run.batch_size} />
          <MetricCard label="Img size"     value={run.img_size} unit="px" />
          <MetricCard label="Freeze"       value={run.freeze_layers} unit="qatlam" />
          <MetricCard
            label="Davomiylik"
            value={formatDuration(run.duration_seconds)}
          />
        </div>
      </div>

      {/* Dataset */}
      {run.dataset_info && (
        <div>
          <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Dataset</div>
          <div className="grid grid-cols-3 gap-2">
            <MetricCard label="Jami"  value={run.dataset_info.n_total} unit="kadr" />
            <MetricCard label="Train" value={run.dataset_info.n_train} />
            <MetricCard label="Val"   value={run.dataset_info.n_val}   />
          </div>
        </div>
      )}

      {/* Metrikalar */}
      {m && (
        <div>
          <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Natijalar</div>

          {/* Bar chart */}
          <div className="bg-gray-50 rounded-xl p-3 mb-2">
            <ResponsiveContainer width="100%" height={90}>
              <BarChart data={metricsData} margin={{ top: 4, right: 0, left: -28, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(v: number) => [`${v}%`, '']}
                  contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {metricsData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <MetricCard
              label="mAP50"
              value={(m.map50    * 100).toFixed(1)}
              unit="%"
              color="#6366f1"
            />
            <MetricCard
              label="mAP50-95"
              value={(m.map50_95 * 100).toFixed(1)}
              unit="%"
              color="#8b5cf6"
            />
            <MetricCard
              label="Precision"
              value={(m.precision * 100).toFixed(1)}
              unit="%"
              color="#10b981"
            />
            <MetricCard
              label="Recall"
              value={(m.recall    * 100).toFixed(1)}
              unit="%"
              color="#3b82f6"
            />
            <MetricCard label="Box loss" value={m.box_loss.toFixed(4)} color="#f59e0b" />
            <MetricCard label="Cls loss" value={m.cls_loss.toFixed(4)} color="#f97316" />
            <MetricCard label="Epoch"    value={`${m.epochs_done} / best: ${m.best_epoch}`} />
            <MetricCard
              label="Vaqt"
              value={formatDuration(m.duration_sec)}
            />
          </div>
        </div>
      )}

      {/* Xato xabari */}
      {run.error_message && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <XCircle size={14} className="text-red-500" />
            <span className="text-xs font-semibold text-red-700">Xato tafsiloti</span>
          </div>
          <p className="text-xs text-red-600 leading-relaxed font-mono break-all">
            {run.error_message}
          </p>
        </div>
      )}

      {/* Vaqt */}
      <div className="text-xs text-gray-400 space-y-1">
        <div className="flex justify-between">
          <span>Yaratildi:</span>
          <span className="font-medium text-gray-500">{formatDate(run.created_at)}</span>
        </div>
        {run.started_at && (
          <div className="flex justify-between">
            <span>Boshlandi:</span>
            <span className="font-medium text-gray-500">{formatDate(run.started_at)}</span>
          </div>
        )}
        {run.completed_at && (
          <div className="flex justify-between">
            <span>Yakunlandi:</span>
            <span className="font-medium text-gray-500">{formatDate(run.completed_at)}</span>
          </div>
        )}
        {run.deployed_at && (
          <div className="flex justify-between">
            <span>Deploy:</span>
            <span className="font-medium text-indigo-600">{formatDate(run.deployed_at)}</span>
          </div>
        )}
      </div>

      {/* Actions */}
      {isAdmin && (
        <div className="flex flex-col gap-2 pt-1">
          {/* Deploy */}
          {(run.status === 'completed' || run.status === 'deployed') && (
            <div>
              {!showForce ? (
                <button
                  onClick={() => onDeploy(false)}
                  disabled={isDeploying || run.is_deployed}
                  className="w-full py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    background: run.is_deployed ? '#ecfdf5' : '#1E3EB4',
                    color:      run.is_deployed ? '#10b981' : '#fff',
                    border:     run.is_deployed ? '1px solid #a7f3d0' : 'none',
                  }}
                >
                  {isDeploying ? (
                    <RefreshCw size={15} className="animate-spin" />
                  ) : run.is_deployed ? (
                    <><CheckCircle2 size={15} /> Hozir ishlatilmoqda</>
                  ) : (
                    <><Upload size={15} /> Modelni deploy qilish</>
                  )}
                </button>
              ) : null}

              {!run.is_deployed && (
                <button
                  onClick={() => {
                    setShowForce(true);
                    onDeploy(true);
                  }}
                  disabled={isDeploying}
                  className="w-full py-2 rounded-xl text-xs font-medium text-gray-400 hover:text-red-600 transition-colors mt-1"
                >
                  Majburan deploy (mAP50 tekshiruvisiz)
                </button>
              )}
            </div>
          )}

          {/* Delete */}
          {(run.status === 'pending' || run.status === 'failed' || run.status === 'completed') && (
            <button
              onClick={onDelete}
              disabled={isDeleting}
              className="w-full py-2 rounded-xl text-xs font-medium text-red-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center gap-2 transition-all border border-transparent hover:border-red-100"
            >
              {isDeleting ? <RefreshCw size={12} className="animate-spin" /> : <Trash2 size={12} />}
              Runni o'chirish
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// START FORM
// =============================================================================

function StartTrainingForm({
  onSubmit,
  isSubmitting,
  isReady,
}: {
  onSubmit: (data: StartRequest) => void;
  isSubmitting: boolean;
  isReady: boolean;
}) {
  const [form, setForm] = useState<StartRequest>({
    run_name:      '',
    epochs:        50,
    batch_size:    8,
    img_size:      640,
    freeze_layers: 10,
    auto_deploy:   false,
    notes:         '',
  });

  const set = <K extends keyof StartRequest>(k: K, v: StartRequest[K]) =>
    setForm(p => ({ ...p, [k]: v }));

  function LabeledInput({
    label, min, max, value, onChange, hint,
  }: {
    label: string; min: number; max: number;
    value: number; onChange: (v: number) => void; hint?: string;
  }) {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-semibold text-gray-600">{label}</label>
          <span className="text-xs font-mono font-bold text-indigo-600">{value}</span>
        </div>
        <input
          type="range"
          min={min} max={max}
          value={value}
          onChange={e => onChange(+e.target.value)}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-indigo-600"
          style={{ background: `linear-gradient(to right, #4f46e5 0%, #4f46e5 ${((value - min) / (max - min)) * 100}%, #e5e7eb ${((value - min) / (max - min)) * 100}%, #e5e7eb 100%)` }}
        />
        {hint && <div className="text-xs text-gray-400 mt-0.5">{hint}</div>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">

      {/* Run nomi */}
      <div>
        <label className="text-xs font-semibold text-gray-600 block mb-1">Run nomi</label>
        <input
          type="text"
          placeholder="masalan: Mart-2026-v1 (bo'sh qolsa avtomatik)"
          value={form.run_name}
          onChange={e => set('run_name', e.target.value)}
          maxLength={100}
          className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-800 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition placeholder-gray-300"
        />
      </div>

      {/* Sliderlar */}
      <LabeledInput
        label="Epochlar"
        min={5} max={200} value={form.epochs}
        onChange={v => set('epochs', v)}
        hint="CPU da 50 tavsiya etiladi (~2-3 soat)"
      />
      <LabeledInput
        label="Batch size"
        min={2} max={32} value={form.batch_size}
        onChange={v => set('batch_size', v)}
        hint="7.5GB RAM uchun 8 optimal"
      />
      <LabeledInput
        label="Img size (px)"
        min={320} max={1280} value={form.img_size}
        onChange={v => set('img_size', Math.round(v / 32) * 32)}
        hint="640 standart YOLO o'lchami"
      />
      <LabeledInput
        label="Freeze qatlamlar"
        min={0} max={23} value={form.freeze_layers}
        onChange={v => set('freeze_layers', v)}
        hint="0 = to'liq o'rgatish, 10 = faqat head"
      />

      {/* Auto deploy toggle */}
      <div
        className="flex items-center justify-between p-3 rounded-xl border border-gray-100 bg-gray-50 cursor-pointer select-none"
        onClick={() => set('auto_deploy', !form.auto_deploy)}
      >
        <div>
          <div className="text-sm font-semibold text-gray-700">Avtomatik deploy</div>
          <div className="text-xs text-gray-400 mt-0.5">
            mAP50 +2% yaxshilansa — avtomatik ishlatishga olish
          </div>
        </div>
        <div
          className="w-10 h-6 rounded-full transition-colors flex items-center px-0.5"
          style={{ background: form.auto_deploy ? '#4f46e5' : '#d1d5db' }}
        >
          <div
            className="w-5 h-5 bg-white rounded-full shadow-sm transition-transform"
            style={{ transform: form.auto_deploy ? 'translateX(16px)' : 'translateX(0)' }}
          />
        </div>
      </div>

      {/* Izoh */}
      <div>
        <label className="text-xs font-semibold text-gray-600 block mb-1">Izoh (ixtiyoriy)</label>
        <textarea
          placeholder="Bu run haqida eslatma..."
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          rows={2}
          maxLength={500}
          className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-800 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition placeholder-gray-300 resize-none"
        />
      </div>

      {/* Submit */}
      <button
        onClick={() => onSubmit(form)}
        disabled={isSubmitting || !isReady}
        className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: !isReady ? '#e5e7eb' : '#1E3EB4',
          color:      !isReady ? '#9ca3af' : '#fff',
        }}
      >
        {isSubmitting ? (
          <><RefreshCw size={15} className="animate-spin" /> Boshlanmoqda...</>
        ) : !isReady ? (
          <><Clock size={15} /> Kadrlar yetarli emas</>
        ) : (
          <><PlayCircle size={15} /> Training boshlash</>
        )}
      </button>

      {!isReady && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 border border-amber-100">
          <AlertTriangle size={14} className="text-amber-500 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700 leading-relaxed">
            Training uchun kamida <strong>30 ta kadr</strong> kerak.
            Detection pipeline ishlayotganda kadrlar avtomatik yig'iladi.
          </p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function TrainingPage() {
  const qc = useQueryClient();

  // Tanlangan run ID
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Toast notification
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  function showToast(msg: string, type: 'success' | 'error') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  // ── user role (App.tsx AuthProvider orqali)
  const [userRole, setUserRole] = useState<string>('viewer');
  useEffect(() => {
    try {
      const raw = localStorage.getItem('tv_user');
      if (raw) setUserRole(JSON.parse(raw).role ?? 'viewer');
    } catch { /* ignore */ }
  }, []);
  const isAdmin = userRole === 'admin';
  const canStart = userRole === 'admin' || userRole === 'manager';

  // ── Dataset stats
  const { data: datasetStats, isLoading: statsLoading } = useQuery<DatasetStats>({
    queryKey: ['training-dataset-stats'],
    queryFn: () => apiFetch('/api/v1/training/dataset-stats'),
    refetchInterval: 30_000,
  });

  // ── Runs list
  const { data: runsList, isLoading: runsLoading } = useQuery<TrainingListResponse>({
    queryKey: ['training-runs'],
    queryFn: () => apiFetch('/api/v1/training/runs?limit=50'),
    refetchInterval: 10_000,
  });

  // ── Aktiv run bo'lsa tez polling
  const hasActive = runsList?.items.some(r => ACTIVE_STATUSES.includes(r.status));
  useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(() => {
      qc.invalidateQueries({ queryKey: ['training-runs'] });
      if (selectedId) qc.invalidateQueries({ queryKey: ['training-run', selectedId] });
    }, 5000);
    return () => clearInterval(id);
  }, [hasActive, selectedId, qc]);

  // ── Tanlangan run detail
  const { data: selectedRun } = useQuery<TrainingRun>({
    queryKey: ['training-run', selectedId],
    queryFn:  () => apiFetch(`/api/v1/training/runs/${selectedId}`),
    enabled:  selectedId !== null,
    refetchInterval: hasActive ? 5_000 : false,
  });

  // Runs ro'yxatidan current run (detail yuklanmagan bo'lsa)
  const currentRun = selectedRun ?? runsList?.items.find(r => r.id === selectedId);

  // ── Start training
  const startMutation = useMutation<StartResponse, Error, StartRequest>({
    mutationFn: (body) => apiFetch('/api/v1/training/runs', {
      method: 'POST',
      body:   JSON.stringify(body),
    }),
    onSuccess: (data) => {
      showToast(`Training #${data.run_id} "${data.run_name}" boshlandi!`, 'success');
      setSelectedId(data.run_id);
      qc.invalidateQueries({ queryKey: ['training-runs'] });
    },
    onError: (err) => showToast(err.message, 'error'),
  });

  // ── Deploy
  const deployMutation = useMutation<DeployResponse, Error, { runId: number; force: boolean }>({
    mutationFn: ({ runId, force }) => apiFetch(`/api/v1/training/runs/${runId}/deploy`, {
      method: 'POST',
      body:   JSON.stringify({ force }),
    }),
    onSuccess: (data) => {
      showToast(`Model muvaffaqiyatli deploy qilindi! mAP50: ${data.map50?.toFixed(4) ?? '—'}`, 'success');
      qc.invalidateQueries({ queryKey: ['training-runs'] });
      qc.invalidateQueries({ queryKey: ['training-run', data.run_id] });
    },
    onError: (err) => showToast(err.message, 'error'),
  });

  // ── Delete
  const deleteMutation = useMutation<void, Error, number>({
    mutationFn: (runId) => apiFetch(`/api/v1/training/runs/${runId}`, { method: 'DELETE' }),
    onSuccess: () => {
      showToast("Run o'chirildi.", 'success');
      setSelectedId(null);
      qc.invalidateQueries({ queryKey: ['training-runs'] });
    },
    onError: (err) => showToast(err.message, 'error'),
  });

  const items   = runsList?.items ?? [];
  const deployed = items.find(r => r.is_deployed);

  return (
    <div className="min-h-screen bg-gray-50/60">

      {/* ── Toast ── */}
      {toast && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl shadow-xl text-sm font-semibold flex items-center gap-2 transition-all"
          style={{
            background: toast.type === 'success' ? '#ecfdf5' : '#fef2f2',
            color:      toast.type === 'success' ? '#065f46' : '#991b1b',
            border:     `1px solid ${toast.type === 'success' ? '#a7f3d0' : '#fca5a5'}`,
          }}
        >
          {toast.type === 'success'
            ? <CheckCircle2 size={16} />
            : <XCircle size={16} />
          }
          {toast.msg}
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-6">

        {/* ── Page Header ── */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-sm">
                <Cpu size={18} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-black text-gray-900">YOLO Training</h1>
                <p className="text-xs text-gray-400 mt-0.5">Custom model fine-tuning boshqaruvi</p>
              </div>
            </div>
          </div>

          {/* Deployed model badge */}
          {deployed && (
            <div className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-50 border border-indigo-100">
              <Zap size={14} className="text-indigo-500" />
              <div>
                <div className="text-xs font-bold text-indigo-700">{deployed.run_name}</div>
                <div className="text-xs text-indigo-400">
                  mAP50: {deployed.metrics ? (deployed.metrics.map50 * 100).toFixed(1) + '%' : '—'}
                </div>
              </div>
            </div>
          )}

          <button
            onClick={() => qc.invalidateQueries({ queryKey: ['training-runs'] })}
            className="p-2 rounded-xl border border-gray-200 hover:bg-gray-100 transition-colors"
            title="Yangilash"
          >
            <RefreshCw size={15} className={runsLoading ? 'animate-spin text-indigo-500' : 'text-gray-400'} />
          </button>
        </div>

        {/* ── Main Grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ══ LEFT COLUMN: Dataset stats + runs list ══ */}
          <div className="lg:col-span-2 flex flex-col gap-6">

            {/* Dataset Status */}
            <DatasetStatusCard stats={datasetStats} isLoading={statsLoading} />

            {/* Runs list */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity size={15} className="text-indigo-500" />
                  <h2 className="font-semibold text-gray-800 text-sm">Training Tarixi</h2>
                  {items.length > 0 && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full font-bold">
                      {items.length}
                    </span>
                  )}
                </div>

                {/* Aktiv training indikatori */}
                {hasActive && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-600 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    O'qitilmoqda
                  </div>
                )}
              </div>

              {runsLoading ? (
                <div className="divide-y divide-gray-50">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="px-5 py-4 animate-pulse flex gap-4">
                      <div className="w-10 h-10 bg-gray-100 rounded-xl" />
                      <div className="flex-1">
                        <div className="h-3 bg-gray-100 rounded w-32 mb-2" />
                        <div className="h-2.5 bg-gray-100 rounded w-48" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : items.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-14 text-gray-400">
                  <Cpu size={32} className="text-gray-200 mb-3" />
                  <p className="text-sm font-medium text-gray-400">Hali training yo'q</p>
                  <p className="text-xs text-gray-300 mt-1">
                    Dataset tayyor bo'lgach, training boshlang
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {items.map(run => {
                    const cfg    = STATUS_CFG[run.status] ?? STATUS_CFG.pending;
                    const Icon   = cfg.icon;
                    const active = ACTIVE_STATUSES.includes(run.status);

                    return (
                      <div
                        key={run.id}
                        onClick={() => setSelectedId(selectedId === run.id ? null : run.id)}
                        className={`px-5 py-3.5 flex items-center gap-4 cursor-pointer transition-colors ${
                          selectedId === run.id ? 'bg-indigo-50' : 'hover:bg-gray-50'
                        }`}
                      >
                        {/* Status icon */}
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                          style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
                        >
                          <Icon
                            size={16}
                            style={{ color: cfg.color }}
                            className={active ? 'animate-pulse' : ''}
                          />
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-gray-900 truncate">
                              {run.run_name}
                            </span>
                            {run.is_deployed && (
                              <span className="shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 text-xs font-bold">
                                <Award size={9} /> Faol
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <StatusBadge status={run.status} size="xs" />
                            {run.metrics && (
                              <span className="text-xs text-gray-400 font-mono">
                                mAP50: <span className="text-indigo-600 font-bold">
                                  {(run.metrics.map50 * 100).toFixed(1)}%
                                </span>
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-300 mt-0.5">
                            {formatDate(run.created_at)} · {run.epochs} epoch
                          </div>
                        </div>

                        <ChevronRight
                          size={15}
                          className={`shrink-0 transition-colors ${
                            selectedId === run.id ? 'text-indigo-400' : 'text-gray-200'
                          }`}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ══ RIGHT COLUMN: Start form or Run detail ══ */}
          <div className="lg:col-span-1 flex flex-col gap-6">

            {/* Start Training form (admin/manager) */}
            {canStart && !selectedId && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <SectionTitle icon={PlayCircle} title="Yangi Training" />
                <StartTrainingForm
                  onSubmit={(data) => startMutation.mutate(data)}
                  isSubmitting={startMutation.isPending}
                  isReady={datasetStats?.is_ready ?? false}
                />
              </div>
            )}

            {/* Run detail */}
            {selectedId && currentRun && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sticky top-6">
                <div className="flex items-center justify-between mb-4">
                  <SectionTitle icon={BarChart2} title="Run tafsiloti" />
                  <button
                    onClick={() => setSelectedId(null)}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    ✕ Yopish
                  </button>
                </div>
                <RunDetailPanel
                  run={currentRun}
                  onDeploy={(force) => deployMutation.mutate({ runId: currentRun.id, force })}
                  onDelete={() => deleteMutation.mutate(currentRun.id)}
                  isDeploying={deployMutation.isPending}
                  isDeleting={deleteMutation.isPending}
                  isAdmin={isAdmin}
                />
              </div>
            )}

            {/* Placeholder — run tanlanmagan va forma ham yo'q */}
            {!selectedId && !canStart && (
              <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-8 flex flex-col items-center justify-center text-center min-h-64">
                <Layers size={32} className="text-gray-200 mb-3" />
                <p className="text-sm font-medium text-gray-400">Run tanlang</p>
                <p className="text-xs text-gray-300 mt-1 max-w-40 leading-relaxed">
                  Ro'yxatdan runni bosing — batafsil metrikalar ko'rinadi
                </p>
              </div>
            )}

            {/* Info kartasi */}
            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-2xl border border-indigo-100 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Info size={14} className="text-indigo-500" />
                <span className="text-xs font-semibold text-indigo-700">Qanday ishlaydi?</span>
              </div>
              <div className="space-y-2">
                {[
                  { icon: Image,       text: 'Detection pipeline har 50 deteksiyadan 1 kadr yig\'adi' },
                  { icon: Database,    text: '30+ kadr yig\'ilgach YOLO format dataset yaratiladi' },
                  { icon: Cpu,         text: 'YOLOv11n backbone freeze, faqat head o\'qitiladi' },
                  { icon: TrendingUp,  text: 'mAP50 +2% yaxshilansa avtomatik deploy qilinadi' },
                ].map(({ icon: Icon, text }, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Icon size={12} className="text-indigo-400 mt-0.5 shrink-0" />
                    <span className="text-xs text-indigo-600 leading-relaxed">{text}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}