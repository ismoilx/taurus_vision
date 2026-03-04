/**
 * Taurus Vision — Feed Management Page (Sprint 20)
 *
 * 3 tab ko'rinish:
 *   📦 Ombor    — zaxiralar, miqdor, low-stock warning
 *   📋 Tarix    — oziqlantiruv yozuvlari
 *   ➕ Oziqlantiruv — yangi yozuv qo'shish
 *
 * API:
 *   GET  /api/v1/feed/stocks/       — ombor
 *   GET  /api/v1/feed/stocks/stats  — statistika
 *   POST /api/v1/feed/stocks/       — yangi zaxira
 *   POST /api/v1/feed/stocks/{id}/restock — to'ldirish
 *   GET  /api/v1/feed/records/      — tarix
 *   POST /api/v1/feed/records/      — oziqlantiruv
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package, ClipboardList, Plus, RefreshCw,
  AlertTriangle, TrendingDown, Wheat, Droplets,
  ChevronDown, CheckCircle2, X,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ───────────────────────────────────────────────────────────────────

type FeedType = 'hay'|'wheat_straw'|'corn_silage'|'grain_mix'|'concentrate'|'mineral_block'|'water'|'other';
type FeedUnit = 'kg'|'ton'|'liter';

interface FeedStock {
  id:               number;
  feed_type:        FeedType;
  name:             string;
  description?:     string;
  unit:             FeedUnit;
  current_kg:       number;
  min_threshold_kg: number;
  unit_cost_uzs?:   number;
  supplier?:        string;
  expiry_date?:     string;
  is_active:        boolean;
  is_low:           boolean;
  is_expired:       boolean;
  stock_percent:    number;
  total_value_uzs?: number;
  low_stock_alerted: boolean;
  updated_at:       string;
}

interface FeedStockListResponse {
  items:           FeedStock[];
  total:           number;
  low_stock_count: number;
  expired_count:   number;
  total_value_uzs?: number;
}

interface FeedRecord {
  id:          number;
  stock_id:    number;
  animal_id?:  number;
  quantity_kg: number;
  fed_at:      string;
  stock_name?: string;
  feed_type?:  string;
  animal_tag_id?: string;
  feeder_name?: string;
  notes?:      string;
}

interface FeedRecordListResponse {
  items:    FeedRecord[];
  total:    number;
  total_kg: number;
}

interface DailyConsumption { date: string; total_kg: number; by_type: Record<string,number>; }

interface FeedStats {
  total_stocks:         number;
  active_stocks:        number;
  low_stock_count:      number;
  expired_count:        number;
  total_inventory_kg:   number;
  total_value_uzs?:     number;
  consumed_today_kg:    number;
  consumed_this_week_kg: number;
  low_stocks:           FeedStock[];
  daily_trend:          DailyConsumption[];
}

// ─── Config ──────────────────────────────────────────────────────────────────

const FEED_TYPE_CFG: Record<FeedType, { label: string; color: string; bg: string; emoji: string }> = {
  hay:           { label: 'Pichan',       color: '#92400E', bg: '#FEF3C7', emoji: '🌾' },
  wheat_straw:   { label: 'Bug\'doy somi', color: '#B45309', bg: '#FEF9C3', emoji: '🌿' },
  corn_silage:   { label: 'Makkajo\'xori', color: '#65A30D', bg: '#F7FEE7', emoji: '🌽' },
  grain_mix:     { label: 'Don aralashmasi', color: '#D97706', bg: '#FFFBEB', emoji: '🌾' },
  concentrate:   { label: 'Konsentrat',   color: '#7C3AED', bg: '#F5F3FF', emoji: '💊' },
  mineral_block: { label: 'Mineral blok', color: '#0891B2', bg: '#ECFEFF', emoji: '🧱' },
  water:         { label: 'Suv',          color: '#2563EB', bg: '#EFF6FF', emoji: '💧' },
  other:         { label: 'Boshqa',       color: '#6B7280', bg: '#F9FAFB', emoji: '📦' },
};

function fmt(n: number, decimals = 1) { return n.toFixed(decimals); }
function fmtUZS(n?: number) { return n ? `${(n/1000000).toFixed(1)}M so'm` : '—'; }

// ─── Stock Progress Bar ───────────────────────────────────────────────────────

function StockBar({ pct, isLow }: { pct: number; isLow: boolean }) {
  const clampedPct = Math.min(pct, 300);
  const width      = Math.min(clampedPct / 3, 100); // normalize to 0-100% visually
  const color      = isLow ? (pct < 25 ? '#DC2626' : '#EA580C') : '#16A34A';

  return (
    <div style={{ height: 4, background: '#F3F4F6', borderRadius: 4, overflow: 'hidden', flex: 1 }}>
      <div style={{
        height: '100%', width: `${width}%`,
        background: color, borderRadius: 4,
        transition: 'width .3s ease',
        minWidth: pct > 0 ? 4 : 0,
      }}/>
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color, bg }: {
  label: string; value: string|number; sub?: string; color: string; bg: string;
}) {
  return (
    <div style={{
      background: bg, border: `1px solid ${color}20`,
      borderRadius: 12, padding: '14px 18px', flex: 1, minWidth: 130,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: "'JetBrains Mono',monospace", lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: '#6B7280', marginTop: 3, fontWeight: 500 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

// ─── Stock Card ──────────────────────────────────────────────────────────────

function StockCard({ stock, onRestock }: { stock: FeedStock; onRestock: (s: FeedStock) => void }) {
  const cfg = FEED_TYPE_CFG[stock.feed_type];
  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${stock.is_low ? '#FECACA' : stock.is_expired ? '#FDE68A' : '#E4E7ED'}`,
      borderTop: `3px solid ${stock.is_low ? '#DC2626' : cfg.color}`,
      borderRadius: 12, padding: '14px 16px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 22, width: 36, height: 36,
            display: 'grid', placeItems: 'center',
            background: cfg.bg, borderRadius: 9,
          }}>{cfg.emoji}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#0D1117', lineHeight: 1.2 }}>
              {stock.name}
            </div>
            <div style={{ fontSize: 11, color: cfg.color, marginTop: 2, fontWeight: 500 }}>
              {cfg.label}
            </div>
          </div>
        </div>

        {stock.is_low && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '3px 8px',
            background: '#FEF2F2', color: '#DC2626',
            border: '1px solid #FECACA', borderRadius: 20,
            display: 'flex', alignItems: 'center', gap: 3,
          }}>
            <AlertTriangle size={10}/> KAM
          </span>
        )}
        {stock.is_expired && !stock.is_low && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '3px 8px',
            background: '#FFFBEB', color: '#D97706',
            border: '1px solid #FDE68A', borderRadius: 20,
          }}>
            ⚠️ MUDDAT O'TDI
          </span>
        )}
      </div>

      {/* Amount */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{
          fontSize: 20, fontWeight: 700,
          color: stock.is_low ? '#DC2626' : '#0D1117',
          fontFamily: "'JetBrains Mono',monospace",
        }}>
          {fmt(stock.current_kg)}
        </span>
        <span style={{ fontSize: 12, color: '#6B7280' }}>kg</span>
        <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 'auto' }}>
          min: {fmt(stock.min_threshold_kg)} kg
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <StockBar pct={stock.stock_percent} isLow={stock.is_low}/>
        <span style={{
          fontSize: 10, fontWeight: 600, flexShrink: 0,
          color: stock.is_low ? '#DC2626' : '#6B7280',
        }}>
          {fmt(stock.stock_percent, 0)}%
        </span>
      </div>

      {/* Meta */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 10, color: '#9CA3AF' }}>
          {stock.total_value_uzs ? fmtUZS(stock.total_value_uzs) : ''}
          {stock.supplier ? ` · ${stock.supplier}` : ''}
        </span>
        <button
          onClick={() => onRestock(stock)}
          style={{
            padding: '5px 12px', borderRadius: 7,
            background: '#EFF6FF', color: '#2563EB',
            border: '1px solid #BFDBFE',
            fontSize: 11, fontWeight: 600, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <Plus size={11}/> To'ldirish
        </button>
      </div>
    </div>
  );
}

// ─── Mini Trend Chart ─────────────────────────────────────────────────────────

function TrendChart({ data }: { data: DailyConsumption[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map(d => d.total_kg), 1);
  const last7 = data.slice(-7);

  return (
    <div style={{
      background: '#fff', border: '1px solid #E4E7ED',
      borderRadius: 12, padding: '14px 16px',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
        So'nggi 7 kunlik iste'mol (kg)
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 60 }}>
        {last7.map((d, i) => {
          const h = Math.max((d.total_kg / max) * 52, 4);
          const isToday = i === last7.length - 1;
          return (
            <div key={d.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 8, color: '#9CA3AF', fontFamily: "'JetBrains Mono',monospace" }}>
                {fmt(d.total_kg, 0)}
              </span>
              <div style={{
                width: '100%', height: h,
                background: isToday ? '#1E3EB4' : '#BFDBFE',
                borderRadius: '3px 3px 0 0',
              }}/>
              <span style={{ fontSize: 8, color: '#9CA3AF' }}>
                {d.date.slice(5)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Modals ───────────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.4)',
      display: 'grid', placeItems: 'center', padding: 16,
    }} onClick={onClose}>
      <div style={{
        background: '#fff', borderRadius: 16,
        width: '100%', maxWidth: 440,
        padding: '22px 26px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0D1117' }}>{title}</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF' }}>
            <X size={18}/>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 11, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 4 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px',
  border: '1px solid #E4E7ED', borderRadius: 8,
  fontSize: 13, outline: 'none', boxSizing: 'border-box',
  fontFamily: "'Outfit',sans-serif",
};

const btnPrimary: React.CSSProperties = {
  padding: '9px 22px', borderRadius: 9,
  background: '#1E3EB4', color: '#fff',
  border: 'none', cursor: 'pointer',
  fontSize: 13, fontWeight: 600,
};

// Create Stock Modal
function CreateStockModal({ onClose, onSubmit, loading }: {
  onClose: () => void; onSubmit: (d: any) => void; loading: boolean;
}) {
  const [f, setF] = useState({
    name: '', feed_type: 'hay' as FeedType, unit: 'kg' as FeedUnit,
    current_kg: '0', min_threshold_kg: '100',
    unit_cost_uzs: '', supplier: '', notes: '',
  });
  const set = (k: string, v: string) => setF(p => ({ ...p, [k]: v }));

  return (
    <Modal title="Yangi Ozuqa Zaxirasi" onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FieldGroup label="Nomi *">
          <input value={f.name} onChange={e => set('name', e.target.value)}
            placeholder="Masalan: Yozgi pichan" style={inputStyle}/>
        </FieldGroup>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <FieldGroup label="Turi *">
            <select value={f.feed_type} onChange={e => set('feed_type', e.target.value)} style={inputStyle}>
              {Object.entries(FEED_TYPE_CFG).map(([k, v]) => (
                <option key={k} value={k}>{v.emoji} {v.label}</option>
              ))}
            </select>
          </FieldGroup>
          <FieldGroup label="Birlik">
            <select value={f.unit} onChange={e => set('unit', e.target.value)} style={inputStyle}>
              <option value="kg">Kilogram (kg)</option>
              <option value="ton">Tonna</option>
              <option value="liter">Litr</option>
            </select>
          </FieldGroup>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <FieldGroup label="Boshlang'ich miqdor (kg)">
            <input type="number" value={f.current_kg} onChange={e => set('current_kg', e.target.value)}
              min="0" style={inputStyle}/>
          </FieldGroup>
          <FieldGroup label="Minimal chegara (kg)">
            <input type="number" value={f.min_threshold_kg} onChange={e => set('min_threshold_kg', e.target.value)}
              min="0" style={inputStyle}/>
          </FieldGroup>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <FieldGroup label="Narxi (UZS/kg)">
            <input type="number" value={f.unit_cost_uzs} onChange={e => set('unit_cost_uzs', e.target.value)}
              placeholder="Ixtiyoriy" min="0" style={inputStyle}/>
          </FieldGroup>
          <FieldGroup label="Yetkazib beruvchi">
            <input value={f.supplier} onChange={e => set('supplier', e.target.value)}
              placeholder="Ixtiyoriy" style={inputStyle}/>
          </FieldGroup>
        </div>

        <FieldGroup label="Izoh">
          <textarea value={f.notes} onChange={e => set('notes', e.target.value)}
            rows={2} style={{ ...inputStyle, resize: 'vertical' }}/>
        </FieldGroup>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
        <button onClick={onClose} style={{ ...btnPrimary, background: '#F3F4F6', color: '#6B7280' }}>
          Bekor
        </button>
        <button
          onClick={() => onSubmit({
            name: f.name, feed_type: f.feed_type, unit: f.unit,
            current_kg: parseFloat(f.current_kg) || 0,
            min_threshold_kg: parseFloat(f.min_threshold_kg) || 100,
            unit_cost_uzs: f.unit_cost_uzs ? parseInt(f.unit_cost_uzs) : undefined,
            supplier: f.supplier || undefined,
            notes: f.notes || undefined,
          })}
          disabled={!f.name.trim() || loading}
          style={{ ...btnPrimary, opacity: f.name.trim() ? 1 : 0.5 }}
        >
          {loading ? 'Saqlanmoqda...' : 'Saqlash'}
        </button>
      </div>
    </Modal>
  );
}

// Restock Modal
function RestockModal({ stock, onClose, onSubmit, loading }: {
  stock: FeedStock; onClose: () => void; onSubmit: (d: any) => void; loading: boolean;
}) {
  const [qty, setQty]       = useState('');
  const [notes, setNotes]   = useState('');

  return (
    <Modal title={`To'ldirish — ${stock.name}`} onClose={onClose}>
      <div style={{
        background: '#F9FAFB', borderRadius: 10, padding: '10px 14px', marginBottom: 16,
        display: 'flex', gap: 16,
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#DC2626', fontFamily: "'JetBrains Mono',monospace" }}>
            {fmt(stock.current_kg)}
          </div>
          <div style={{ fontSize: 10, color: '#6B7280' }}>Hozir (kg)</div>
        </div>
        <div style={{ fontSize: 20, color: '#9CA3AF', alignSelf: 'center' }}>→</div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#16A34A', fontFamily: "'JetBrains Mono',monospace" }}>
            {fmt(stock.current_kg + (parseFloat(qty) || 0))}
          </div>
          <div style={{ fontSize: 10, color: '#6B7280' }}>Keyin (kg)</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FieldGroup label="Qo'shiladigan miqdor (kg) *">
          <input type="number" value={qty} onChange={e => setQty(e.target.value)}
            placeholder="0.0" min="0.1" step="0.1" style={inputStyle} autoFocus/>
        </FieldGroup>
        <FieldGroup label="Izoh">
          <input value={notes} onChange={e => setNotes(e.target.value)}
            placeholder="Yetkazib beruvchi, partiya raqami..." style={inputStyle}/>
        </FieldGroup>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
        <button onClick={onClose} style={{ ...btnPrimary, background: '#F3F4F6', color: '#6B7280' }}>
          Bekor
        </button>
        <button
          onClick={() => onSubmit({ quantity_kg: parseFloat(qty), notes: notes || undefined })}
          disabled={!qty || parseFloat(qty) <= 0 || loading}
          style={{ ...btnPrimary, background: '#16A34A', opacity: (qty && parseFloat(qty) > 0) ? 1 : 0.5 }}
        >
          {loading ? 'Saqlanmoqda...' : '✓ To\'ldirish'}
        </button>
      </div>
    </Modal>
  );
}

// Feed Record Modal
function FeedRecordModal({ stocks, onClose, onSubmit, loading }: {
  stocks: FeedStock[]; onClose: () => void; onSubmit: (d: any) => void; loading: boolean;
}) {
  const [f, setF] = useState({ stock_id: '', quantity_kg: '', animal_id: '', notes: '' });
  const set = (k: string, v: string) => setF(p => ({ ...p, [k]: v }));

  const selectedStock = stocks.find(s => s.id === parseInt(f.stock_id));
  const qty           = parseFloat(f.quantity_kg) || 0;
  const notEnough     = selectedStock && qty > selectedStock.current_kg;

  return (
    <Modal title="Oziqlantiruv Yozuvi" onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FieldGroup label="Ozuqa zaxirasi *">
          <select value={f.stock_id} onChange={e => set('stock_id', e.target.value)} style={inputStyle}>
            <option value="">Tanlang...</option>
            {stocks.filter(s => s.is_active).map(s => (
              <option key={s.id} value={s.id}>
                {FEED_TYPE_CFG[s.feed_type].emoji} {s.name} ({fmt(s.current_kg)} kg qoldi)
              </option>
            ))}
          </select>
        </FieldGroup>

        <FieldGroup label="Miqdor (kg) *">
          <input type="number" value={f.quantity_kg} onChange={e => set('quantity_kg', e.target.value)}
            placeholder="0.0" min="0.1" step="0.1" style={{
              ...inputStyle,
              borderColor: notEnough ? '#FECACA' : undefined,
            }}/>
          {notEnough && (
            <div style={{ fontSize: 11, color: '#DC2626', marginTop: 3 }}>
              ⚠️ Yetarli emas: {fmt(selectedStock!.current_kg)} kg mavjud
            </div>
          )}
        </FieldGroup>

        <FieldGroup label="Jonivor ID (ixtiyoriy — bo'sh = butun poda)">
          <input type="number" value={f.animal_id} onChange={e => set('animal_id', e.target.value)}
            placeholder="Masalan: 42" style={inputStyle}/>
        </FieldGroup>

        <FieldGroup label="Izoh">
          <input value={f.notes} onChange={e => set('notes', e.target.value)}
            placeholder="Ishtaha, maxsus holat..." style={inputStyle}/>
        </FieldGroup>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
        <button onClick={onClose} style={{ ...btnPrimary, background: '#F3F4F6', color: '#6B7280' }}>
          Bekor
        </button>
        <button
          onClick={() => onSubmit({
            stock_id:    parseInt(f.stock_id),
            quantity_kg: qty,
            animal_id:   f.animal_id ? parseInt(f.animal_id) : undefined,
            notes:       f.notes || undefined,
          })}
          disabled={!f.stock_id || !qty || notEnough || loading}
          style={{ ...btnPrimary, opacity: (f.stock_id && qty && !notEnough) ? 1 : 0.5 }}
        >
          {loading ? 'Saqlanmoqda...' : '✓ Saqlash'}
        </button>
      </div>
    </Modal>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type Tab = 'inventory' | 'history';

export default function FeedPage() {
  const qc = useQueryClient();

  const [tab,            setTab]          = useState<Tab>('inventory');
  const [showCreate,     setShowCreate]   = useState(false);
  const [restockStock,   setRestockStock] = useState<FeedStock | null>(null);
  const [showFeedRecord, setShowFeedRecord] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['feed-stocks'] });
    qc.invalidateQueries({ queryKey: ['feed-stats'] });
    qc.invalidateQueries({ queryKey: ['feed-records'] });
  };

  // ── Queries ──────────────────────────────────────────────────────────────
  const statsQ = useQuery<FeedStats>({
    queryKey: ['feed-stats'],
    queryFn:  () => apiFetch('/api/v1/feed/stocks/stats'),
    refetchInterval: 60_000,
  });

  const stocksQ = useQuery<FeedStockListResponse>({
    queryKey: ['feed-stocks'],
    queryFn:  () => apiFetch('/api/v1/feed/stocks/'),
    refetchInterval: 30_000,
  });

  const recordsQ = useQuery<FeedRecordListResponse>({
    queryKey: ['feed-records'],
    queryFn:  () => apiFetch('/api/v1/feed/records/?page_size=50'),
    enabled:  tab === 'history',
  });

  // ── Mutations ─────────────────────────────────────────────────────────────
  const createMut = useMutation({
    mutationFn: (d: any) => apiFetch('/api/v1/feed/stocks/', { method: 'POST', body: JSON.stringify(d) }),
    onSuccess: () => { setShowCreate(false); invalidate(); },
  });

  const restockMut = useMutation({
    mutationFn: ({ id, d }: { id: number; d: any }) =>
      apiFetch(`/api/v1/feed/stocks/${id}/restock`, { method: 'POST', body: JSON.stringify(d) }),
    onSuccess: () => { setRestockStock(null); invalidate(); },
  });

  const recordMut = useMutation({
    mutationFn: (d: any) => apiFetch('/api/v1/feed/records/', { method: 'POST', body: JSON.stringify(d) }),
    onSuccess: () => { setShowFeedRecord(false); invalidate(); },
  });

  const stats  = statsQ.data;
  const stocks = stocksQ.data?.items ?? [];
  const records = recordsQ.data?.items ?? [];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#0D1117' }}>
            🌾 Ozuqa Boshqaruvi
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280' }}>
            Inventar, oziqlantiruv tarixi, iste'mol tahlili
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => invalidate()} style={{
            padding: '8px 12px', borderRadius: 9, background: '#F3F4F6', color: '#6B7280',
            border: '1px solid #E4E7ED', cursor: 'pointer',
          }}>
            <RefreshCw size={14}/>
          </button>
          <button onClick={() => setShowFeedRecord(true)} style={{
            padding: '8px 14px', borderRadius: 9, background: '#16A34A', color: '#fff',
            border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 5,
          }}>
            <Wheat size={14}/> Oziqlantiruv
          </button>
          <button onClick={() => setShowCreate(true)} style={{
            padding: '8px 14px', borderRadius: 9, background: '#1E3EB4', color: '#fff',
            border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 5,
          }}>
            <Plus size={14}/> Zaxira
          </button>
        </div>
      </div>

      {/* Stat cards */}
      {stats && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <StatCard label="Aktiv zaxiralar"   value={stats.active_stocks}
            color="#2563EB" bg="#EFF6FF"/>
          <StatCard label="Jami inventar"     value={`${stats.total_inventory_kg.toFixed(0)} kg`}
            sub={fmtUZS(stats.total_value_uzs)} color="#374151" bg="#F9FAFB"/>
          <StatCard label="Bugun iste'mol"    value={`${stats.consumed_today_kg} kg`}
            color="#16A34A" bg="#F0FDF4"/>
          <StatCard label="Haftalik iste'mol" value={`${stats.consumed_this_week_kg} kg`}
            color="#7C3AED" bg="#F5F3FF"/>
          {stats.low_stock_count > 0 && (
            <StatCard label="Kam zaxiralar" value={stats.low_stock_count}
              sub="To'ldirish kerak" color="#DC2626" bg="#FEF2F2"/>
          )}
        </div>
      )}

      {/* Low stock warning */}
      {stats && stats.low_stock_count > 0 && (
        <div style={{
          background: '#FEF2F2', border: '1px solid #FECACA',
          borderRadius: 10, padding: '10px 14px', marginBottom: 14,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <AlertTriangle size={14} color="#DC2626"/>
          <span style={{ fontSize: 12, color: '#DC2626', fontWeight: 600 }}>
            {stats.low_stock_count} ta zaxira minimal chegaradan past:&nbsp;
          </span>
          <span style={{ fontSize: 12, color: '#DC2626' }}>
            {stats.low_stocks.slice(0,3).map(s => s.name).join(', ')}
            {stats.low_stocks.length > 3 ? ` +${stats.low_stocks.length - 3} ta` : ''}
          </span>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 2, marginBottom: 16,
        background: '#F3F4F6', borderRadius: 10, padding: 4, width: 'fit-content',
      }}>
        {([
          { id: 'inventory', label: '📦 Ombor',  count: stocksQ.data?.total },
          { id: 'history',   label: '📋 Tarix',  count: recordsQ.data?.total },
        ] as const).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '7px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: tab === t.id ? '#fff' : 'transparent',
            color: tab === t.id ? '#0D1117' : '#6B7280',
            fontWeight: tab === t.id ? 600 : 400,
            fontSize: 13, fontFamily: "'Outfit',sans-serif",
            boxShadow: tab === t.id ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            transition: 'all .15s',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            {t.label}
            {t.count != null && (
              <span style={{
                fontSize: 10, background: tab === t.id ? '#E4E7ED' : 'transparent',
                padding: '1px 6px', borderRadius: 10, fontFamily: "'JetBrains Mono',monospace",
              }}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* INVENTORY TAB */}
      {tab === 'inventory' && (
        <div>
          {/* Trend chart */}
          {stats?.daily_trend?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <TrendChart data={stats.daily_trend}/>
            </div>
          )}

          {stocksQ.isLoading ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>Yuklanmoqda...</div>
          ) : stocks.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '48px 20px',
              background: '#F9FAFB', borderRadius: 12, border: '1px dashed #E4E7ED',
            }}>
              <Package size={32} color="#D1D5DB" style={{ margin: '0 auto 12px' }}/>
              <div style={{ fontSize: 14, color: '#9CA3AF', fontWeight: 500 }}>
                Zaxiralar topilmadi
              </div>
              <button onClick={() => setShowCreate(true)} style={{
                ...btnPrimary, marginTop: 14, display: 'inline-flex', alignItems: 'center', gap: 5,
              }}>
                <Plus size={13}/> Birinchi zaxirani qo'shish
              </button>
            </div>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: 12,
            }}>
              {stocks.map(stock => (
                <StockCard key={stock.id} stock={stock} onRestock={setRestockStock}/>
              ))}
            </div>
          )}
        </div>
      )}

      {/* HISTORY TAB */}
      {tab === 'history' && (
        <div>
          {recordsQ.data && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 12, padding: '8px 14px',
              background: '#F9FAFB', borderRadius: 9, border: '1px solid #E4E7ED',
            }}>
              <span style={{ fontSize: 12, color: '#6B7280' }}>
                {recordsQ.data.total} ta yozuv
              </span>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>
                Jami: <span style={{ color: '#1E3EB4', fontFamily: "'JetBrains Mono',monospace" }}>
                  {fmt(recordsQ.data.total_kg)} kg
                </span>
              </span>
            </div>
          )}

          {recordsQ.isLoading ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>Yuklanmoqda...</div>
          ) : records.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF', fontSize: 13 }}>
              Hali yozuvlar yo'q
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {records.map(rec => {
                const ft = (rec.feed_type || 'other') as FeedType;
                const cfg = FEED_TYPE_CFG[ft] || FEED_TYPE_CFG.other;
                return (
                  <div key={rec.id} style={{
                    background: '#fff', border: '1px solid #E4E7ED',
                    borderRadius: 9, padding: '10px 14px',
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}>
                    <span style={{ fontSize: 18, flexShrink: 0 }}>{cfg.emoji}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0D1117' }}>
                        {rec.stock_name || `Zaxira #${rec.stock_id}`}
                      </div>
                      <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
                        {rec.animal_tag_id ? `🐄 ${rec.animal_tag_id}` : '🐄 Butun poda'}
                        {rec.feeder_name ? ` · ${rec.feeder_name}` : ''}
                        {rec.notes ? ` · ${rec.notes}` : ''}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{
                        fontSize: 15, fontWeight: 700, color: '#0D1117',
                        fontFamily: "'JetBrains Mono',monospace",
                      }}>
                        {fmt(rec.quantity_kg)} kg
                      </div>
                      <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>
                        {formatDistanceToNow(new Date(rec.fed_at), { addSuffix: true })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateStockModal
          onClose={() => setShowCreate(false)}
          onSubmit={d => createMut.mutate(d)}
          loading={createMut.isPending}
        />
      )}

      {restockStock && (
        <RestockModal
          stock={restockStock}
          onClose={() => setRestockStock(null)}
          onSubmit={d => restockMut.mutate({ id: restockStock.id, d })}
          loading={restockMut.isPending}
        />
      )}

      {showFeedRecord && (
        <FeedRecordModal
          stocks={stocks}
          onClose={() => setShowFeedRecord(false)}
          onSubmit={d => recordMut.mutate(d)}
          loading={recordMut.isPending}
        />
      )}
    </div>
  );
}