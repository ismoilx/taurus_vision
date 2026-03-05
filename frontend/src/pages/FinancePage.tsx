/**
 * Taurus Vision — Finance Page (Q4)
 *
 * 4 tab:
 *   1. Dashboard  — KPI kartalar, daromad/xarajat grafik, kategoriya donut
 *   2. Operatsiyalar — jadval, filtr, qo'shish/tahrirlash/o'chirish
 *   3. Trendlar   — 6/12 oylik bar chart, oylik taqqoslash
 *   4. ROI        — Jonivorlar bo'yicha ROI hisoboti
 */

import { useState, useCallback } from 'react';
import {
  useQuery, useMutation, useQueryClient,
} from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line,
} from 'recharts';
import {
  TrendingUp, TrendingDown, DollarSign, ShoppingCart,
  Plus, Edit2, Trash2, ChevronDown, X, Check, AlertCircle,
  BarChart2, List, Activity, Award, Filter, Download,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';
import { format, startOfMonth, endOfMonth } from 'date-fns';

// =============================================================================
// TYPES
// =============================================================================

interface FinanceSummary {
  period_label:        string;
  date_from:           string;
  date_to:             string;
  total_income:        number;
  total_expense:       number;
  net_profit:          number;
  roi_percent:         number;
  income_count:        number;
  expense_count:       number;
  expense_by_category: CategoryStat[];
  income_by_category:  CategoryStat[];
  prev_income:         number | null;
  prev_expense:        number | null;
  prev_profit:         number | null;
  income_change_pct:   number | null;
  expense_change_pct:  number | null;
  profit_change_pct:   number | null;
}

interface CategoryStat {
  category:    string;
  label:       string;
  amount_uzs:  number;
  percent:     number;
  count:       number;
}

interface FinanceTrend {
  month:       string;
  month_label: string;
  income:      number;
  expense:     number;
  profit:      number;
}

interface FinanceTrends {
  months:        FinanceTrend[];
  total_income:  number;
  total_expense: number;
  total_profit:  number;
}

interface Transaction {
  id:               number;
  type:             'income' | 'expense';
  category:         string;
  amount_uzs:       number;
  amount_usd:       number | null;
  description:      string;
  notes:            string | null;
  transaction_date: string;
  payment_method:   string;
  receipt_number:   string | null;
  animal_id:        number | null;
  animal_tag:       string | null;
  created_by:       number | null;
  creator_name:     string | null;
  created_at:       string;
}

interface TransactionListResponse {
  items: Transaction[];
  total: number;
  page:  number;
  size:  number;
  pages: number;
}

interface AnimalROI {
  animal_id:     number;
  tag_id:        string;
  species:       string;
  total_income:  number;
  total_expense: number;
  net_profit:    number;
  roi_percent:   number;
  tx_count:      number;
}

interface ROIReport {
  date_from:     string;
  date_to:       string;
  animals:       AnimalROI[];
  farm_income:   number;
  farm_expense:  number;
  total_income:  number;
  total_expense: number;
  total_profit:  number;
  overall_roi:   number;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const EXPENSE_CATEGORIES = [
  { value: 'feed',       label: 'Yem va ozuqa'   },
  { value: 'veterinary', label: 'Veterinariya'   },
  { value: 'equipment',  label: 'Uskunalar'      },
  { value: 'labor',      label: 'Mehnat'         },
  { value: 'utilities',  label: 'Kommunal'       },
  { value: 'transport',  label: 'Tashish'        },
  { value: 'other',      label: 'Boshqa'         },
];

const INCOME_CATEGORIES = [
  { value: 'animal_sale', label: 'Jonivor sotish' },
  { value: 'milk_sale',   label: 'Sut'            },
  { value: 'meat_sale',   label: "Go'sht"         },
  { value: 'wool_sale',   label: 'Jun'            },
  { value: 'subsidy',     label: 'Subsidiya'      },
  { value: 'other',       label: 'Boshqa'         },
];

const PAYMENT_METHODS = [
  { value: 'cash',     label: 'Naqd'         },
  { value: 'transfer', label: "Bank o'tkazma" },
  { value: 'credit',   label: 'Kredit'       },
];

const EXPENSE_COLORS = [
  '#EF4444', '#F97316', '#EAB308', '#84CC16', '#06B6D4', '#8B5CF6', '#EC4899',
];
const INCOME_COLORS  = [
  '#10B981', '#3B82F6', '#6366F1', '#F59E0B', '#14B8A6', '#A855F7',
];

// =============================================================================
// HELPERS
// =============================================================================

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function fmtFull(n: number): string {
  return n.toLocaleString('ru-RU') + ' so\'m';
}

function getCategoryLabel(type: 'income' | 'expense', cat: string): string {
  const list = type === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;
  return list.find(c => c.value === cat)?.label ?? cat;
}

function paymentLabel(m: string): string {
  return PAYMENT_METHODS.find(p => p.value === m)?.label ?? m;
}

// =============================================================================
// SUB COMPONENTS
// =============================================================================

// ── KPI Card ─────────────────────────────────────────────────────────────────
interface KpiProps {
  label:      string;
  value:      number;
  icon:       React.ReactNode;
  color:      string;
  bgColor:    string;
  change?:    number | null;
  suffix?:    string;
}

function KpiCard({ label, value, icon, color, bgColor, change, suffix = 'so\'m' }: KpiProps) {
  const isPos = change !== null && change !== undefined && change >= 0;
  return (
    <div style={{
      background: '#fff', borderRadius: 14, padding: '20px 22px',
      border: '1px solid #E4E7ED', flex: 1, minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>{label}</span>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: bgColor, display: 'grid', placeItems: 'center' }}>
          {icon}
        </div>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#0D1117', letterSpacing: '-0.02em' }}>
        {fmt(value)}
        <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 400, marginLeft: 4 }}>{suffix}</span>
      </div>
      {change !== null && change !== undefined && (
        <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
          {isPos
            ? <TrendingUp size={12} color="#10B981" />
            : <TrendingDown size={12} color="#EF4444" />}
          <span style={{ fontSize: 11, color: isPos ? '#10B981' : '#EF4444', fontWeight: 600 }}>
            {isPos ? '+' : ''}{change.toFixed(1)}% o'tgan davrga nisbatan
          </span>
        </div>
      )}
    </div>
  );
}

// ── Transaction Modal ─────────────────────────────────────────────────────────
interface TxModalProps {
  tx?:      Transaction | null;
  onClose:  () => void;
  onSaved:  () => void;
}

function TransactionModal({ tx, onClose, onSaved }: TxModalProps) {
  const isEdit = !!tx;
  const qc     = useQueryClient();

  const [type,        setType]        = useState<'income' | 'expense'>(tx?.type ?? 'expense');
  const [category,    setCategory]    = useState(tx?.category ?? 'feed');
  const [amount,      setAmount]      = useState(tx ? String(tx.amount_uzs) : '');
  const [amountUsd,   setAmountUsd]   = useState(tx?.amount_usd ? String(tx.amount_usd) : '');
  const [description, setDescription] = useState(tx?.description ?? '');
  const [notes,       setNotes]       = useState(tx?.notes ?? '');
  const [txDate,      setTxDate]      = useState(
    tx?.transaction_date ?? format(new Date(), 'yyyy-MM-dd'),
  );
  const [payment,     setPayment]     = useState(tx?.payment_method ?? 'cash');
  const [receipt,     setReceipt]     = useState(tx?.receipt_number ?? '');
  const [err,         setErr]         = useState<string | null>(null);

  const categories = type === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

  // Reset category when type changes
  const handleTypeChange = (t: 'income' | 'expense') => {
    setType(t);
    setCategory(t === 'income' ? 'animal_sale' : 'feed');
  };

  const mutation = useMutation({
    mutationFn: async () => {
      const body = {
        type,
        category,
        amount_uzs:       parseInt(amount.replace(/\s/g, ''), 10),
        amount_usd:       amountUsd ? parseFloat(amountUsd) : null,
        description:      description.trim(),
        notes:            notes.trim() || null,
        transaction_date: txDate,
        payment_method:   payment,
        receipt_number:   receipt.trim() || null,
      };
      if (isEdit) {
        return apiFetch(`/api/v1/finance/transactions/${tx!.id}`, {
          method: 'PATCH', body: JSON.stringify(body),
        });
      }
      return apiFetch('/api/v1/finance/transactions', {
        method: 'POST', body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['finance'] });
      onSaved();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
    border: '1px solid #D1D5DB', outline: 'none', background: '#FAFAFA',
    fontFamily: "'Outfit', sans-serif",
  };
  const sel: React.CSSProperties = { ...inp, cursor: 'pointer' };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300,
      background: 'rgba(0,0,0,0.45)', display: 'grid', placeItems: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#fff', borderRadius: 18, padding: '28px 30px',
        width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
      }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#0D1117' }}>
            {isEdit ? 'Operatsiyani tahrirlash' : 'Yangi operatsiya'}
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6B7280' }}>
            <X size={20} />
          </button>
        </div>

        {err && (
          <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
            <AlertCircle size={14} color="#EF4444" />
            <span style={{ fontSize: 12, color: '#DC2626' }}>{err}</span>
          </div>
        )}

        {/* Type selector */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {(['expense', 'income'] as const).map(t => (
            <button key={t} onClick={() => handleTypeChange(t)} style={{
              flex: 1, padding: '10px 0', borderRadius: 10, border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, fontFamily: "'Outfit', sans-serif",
              background: type === t
                ? (t === 'income' ? '#ECFDF5' : '#FEF2F2')
                : '#F7F8FA',
              color: type === t
                ? (t === 'income' ? '#059669' : '#DC2626')
                : '#6B7280',
              boxShadow: type === t ? `0 0 0 2px ${t === 'income' ? '#10B981' : '#EF4444'}` : 'none',
              transition: 'all .15s',
            }}>
              {t === 'income' ? '+ Daromad' : '− Xarajat'}
            </button>
          ))}
        </div>

        {/* Fields */}
        <div style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>KATEGORIYA *</label>
              <select value={category} onChange={e => setCategory(e.target.value)} style={sel}>
                {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>SANA *</label>
              <input type="date" value={txDate} onChange={e => setTxDate(e.target.value)}
                max={format(new Date(), 'yyyy-MM-dd')} style={inp} />
            </div>
          </div>

          <div>
            <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>TAVSIF *</label>
            <input type="text" value={description} onChange={e => setDescription(e.target.value)}
              placeholder="Masalan: Iyun uchun pichan — 500 kg" style={inp} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>MIQDOR (SO'M) *</label>
              <input type="number" value={amount} onChange={e => setAmount(e.target.value)}
                placeholder="2500000" min="1" style={inp} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>MIQDOR (USD, ixtiyoriy)</label>
              <input type="number" value={amountUsd} onChange={e => setAmountUsd(e.target.value)}
                placeholder="190" min="0.01" step="0.01" style={inp} />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>TO'LOV USULI</label>
              <select value={payment} onChange={e => setPayment(e.target.value)} style={sel}>
                {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>CHEK RAQAMI</label>
              <input type="text" value={receipt} onChange={e => setReceipt(e.target.value)}
                placeholder="INV-2026-001" style={inp} />
            </div>
          </div>

          <div>
            <label style={{ fontSize: 11, color: '#6B7280', fontWeight: 600, display: 'block', marginBottom: 4 }}>IZOH</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Qo'shimcha ma'lumot..." rows={2}
              style={{ ...inp, resize: 'vertical', minHeight: 60 }} />
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '11px 0', borderRadius: 10, border: '1px solid #E4E7ED',
            background: '#F7F8FA', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            color: '#374151', fontFamily: "'Outfit', sans-serif",
          }}>Bekor qilish</button>
          <button
            onClick={() => {
              setErr(null);
              if (!amount || parseInt(amount) <= 0) { setErr("Miqdor musbat bo'lishi kerak"); return; }
              if (!description.trim()) { setErr("Tavsif kiritilishi shart"); return; }
              mutation.mutate();
            }}
            disabled={mutation.isPending}
            style={{
              flex: 2, padding: '11px 0', borderRadius: 10, border: 'none',
              background: type === 'income' ? '#10B981' : '#EF4444',
              color: '#fff', cursor: mutation.isPending ? 'not-allowed' : 'pointer',
              fontSize: 13, fontWeight: 700, fontFamily: "'Outfit', sans-serif",
              opacity: mutation.isPending ? 0.7 : 1, transition: 'opacity .15s',
            }}>
            {mutation.isPending ? 'Saqlanmoqda...' : (isEdit ? 'Saqlash' : 'Qo\'shish')}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

type Tab = 'dashboard' | 'transactions' | 'trends' | 'roi';

export default function FinancePage() {
  const [tab,        setTab]        = useState<Tab>('dashboard');
  const [dateFrom,   setDateFrom]   = useState(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
  const [dateTo,     setDateTo]     = useState(format(new Date(), 'yyyy-MM-dd'));
  const [trendMonths, setTrendMonths] = useState(12);
  const [txPage,     setTxPage]     = useState(1);
  const [txTypeF,    setTxTypeF]    = useState<string>('');
  const [txCatF,     setTxCatF]     = useState<string>('');
  const [modal,      setModal]      = useState<{ open: boolean; tx: Transaction | null }>({ open: false, tx: null });
  const [deleteId,   setDeleteId]   = useState<number | null>(null);

  const qc = useQueryClient();

  // Queries
  const { data: summary, isLoading: sumLoading } = useQuery<FinanceSummary>({
    queryKey: ['finance', 'summary', dateFrom, dateTo],
    queryFn:  () => apiFetch(`/api/v1/finance/summary?date_from=${dateFrom}&date_to=${dateTo}`),
    staleTime: 60_000,
  });

  const { data: trends, isLoading: trendsLoading } = useQuery<FinanceTrends>({
    queryKey: ['finance', 'trends', trendMonths],
    queryFn:  () => apiFetch(`/api/v1/finance/trends?months=${trendMonths}`),
    staleTime: 60_000,
  });

  const { data: txList, isLoading: txLoading } = useQuery<TransactionListResponse>({
    queryKey: ['finance', 'tx', txPage, txTypeF, txCatF, dateFrom, dateTo],
    queryFn:  () => {
      const params = new URLSearchParams({
        page: String(txPage), size: '20',
        ...(txTypeF && { type: txTypeF }),
        ...(txCatF  && { category: txCatF }),
        date_from: dateFrom, date_to: dateTo,
      });
      return apiFetch(`/api/v1/finance/transactions?${params}`);
    },
    staleTime: 30_000,
  });

  const { data: roi, isLoading: roiLoading } = useQuery<ROIReport>({
    queryKey: ['finance', 'roi', dateFrom, dateTo],
    queryFn:  () => apiFetch(`/api/v1/finance/roi?date_from=${dateFrom}&date_to=${dateTo}`),
    staleTime: 60_000,
    enabled:  tab === 'roi',
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/finance/transactions/${id}`, { method: 'DELETE' }),
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: ['finance'] });
      setDeleteId(null);
    },
  });

  // ── Styles ────────────────────────────────────────────────────────────────
  const tabBtn = (t: Tab): React.CSSProperties => ({
    padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontSize: 13, fontWeight: tab === t ? 600 : 400,
    background: tab === t ? '#1E3EB4' : 'transparent',
    color:      tab === t ? '#fff'    : '#6B7280',
    fontFamily: "'Outfit', sans-serif", transition: 'all .15s',
  });

  const cardStyle: React.CSSProperties = {
    background: '#fff', borderRadius: 14, padding: '20px 22px',
    border: '1px solid #E4E7ED',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11, color: '#6B7280', fontWeight: 700,
    letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 6,
    display: 'block',
  };

  const inp: React.CSSProperties = {
    padding: '8px 12px', borderRadius: 8, border: '1px solid #E4E7ED',
    fontSize: 13, fontFamily: "'Outfit', sans-serif", background: '#FAFAFA',
    outline: 'none', color: '#0D1117',
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: '24px 28px', maxWidth: 1400, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0D1117', margin: 0 }}>
            💰 Moliyaviy Boshqaruv
          </h1>
          <p style={{ fontSize: 13, color: '#6B7280', margin: '4px 0 0' }}>
            Daromad, xarajat, foyda va ROI kuzatuvi
          </p>
        </div>

        {/* Date range + Add */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={inp} />
          <span style={{ color: '#9CA3AF', fontSize: 13 }}>—</span>
          <input type="date" value={dateTo}   onChange={e => setDateTo(e.target.value)}   style={inp} />
          <button
            onClick={() => setModal({ open: true, tx: null })}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '9px 16px', borderRadius: 10, border: 'none',
              background: '#1E3EB4', color: '#fff', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, fontFamily: "'Outfit', sans-serif",
            }}>
            <Plus size={15} /> Yangi operatsiya
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 22, background: '#F7F8FA', padding: 4, borderRadius: 12, width: 'fit-content' }}>
        {([
          ['dashboard',    'Dashboard',      BarChart2],
          ['transactions', 'Operatsiyalar',  List],
          ['trends',       'Trendlar',       Activity],
          ['roi',          'ROI',            Award],
        ] as [Tab, string, React.ElementType][]).map(([t, label, Icon]) => (
          <button key={t} onClick={() => setTab(t)} style={tabBtn(t)}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon size={13} /> {label}
            </span>
          </button>
        ))}
      </div>

      {/* ════════════════════ TAB: DASHBOARD ════════════════════ */}
      {tab === 'dashboard' && (
        <div style={{ display: 'grid', gap: 18 }}>

          {/* KPI Cards */}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <KpiCard
              label="Jami daromad" value={summary?.total_income ?? 0}
              icon={<TrendingUp size={16} color="#059669" />}
              color="#059669" bgColor="#ECFDF5"
              change={summary?.income_change_pct ?? null}
            />
            <KpiCard
              label="Jami xarajat" value={summary?.total_expense ?? 0}
              icon={<ShoppingCart size={16} color="#DC2626" />}
              color="#DC2626" bgColor="#FEF2F2"
              change={summary?.expense_change_pct ? -summary.expense_change_pct : null}
            />
            <KpiCard
              label="Sof foyda" value={summary?.net_profit ?? 0}
              icon={<DollarSign size={16} color="#1E3EB4" />}
              color="#1E3EB4" bgColor="rgba(30,62,180,0.08)"
              change={summary?.profit_change_pct ?? null}
            />
            <KpiCard
              label="ROI" value={summary?.roi_percent ?? 0}
              icon={<Award size={16} color="#D97706" />}
              color="#D97706" bgColor="#FFFBEB"
              suffix="%" change={null}
            />
          </div>

          {/* Charts row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

            {/* Expense donut */}
            <div style={cardStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 16px' }}>
                Xarajatlar taqsimoti
              </h3>
              {summary?.expense_by_category?.length ? (
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  <ResponsiveContainer width={160} height={160}>
                    <PieChart>
                      <Pie
                        data={summary.expense_by_category}
                        dataKey="amount_uzs"
                        nameKey="label"
                        cx="50%" cy="50%"
                        innerRadius={45} outerRadius={72}
                        paddingAngle={2}
                      >
                        {summary.expense_by_category.map((_, i) => (
                          <Cell key={i} fill={EXPENSE_COLORS[i % EXPENSE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => fmtFull(v)} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ flex: 1, display: 'grid', gap: 6 }}>
                    {summary.expense_by_category.map((c, i) => (
                      <div key={c.category} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <div style={{ width: 9, height: 9, borderRadius: 2, background: EXPENSE_COLORS[i % EXPENSE_COLORS.length], flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: '#374151', flex: 1 }}>{c.label}</span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#0D1117' }}>{c.percent}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: 13, color: '#9CA3AF', textAlign: 'center', margin: '30px 0' }}>
                  Ma'lumot yo'q
                </p>
              )}
            </div>

            {/* Income donut */}
            <div style={cardStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 16px' }}>
                Daromadlar taqsimoti
              </h3>
              {summary?.income_by_category?.length ? (
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  <ResponsiveContainer width={160} height={160}>
                    <PieChart>
                      <Pie
                        data={summary.income_by_category}
                        dataKey="amount_uzs"
                        nameKey="label"
                        cx="50%" cy="50%"
                        innerRadius={45} outerRadius={72}
                        paddingAngle={2}
                      >
                        {summary.income_by_category.map((_, i) => (
                          <Cell key={i} fill={INCOME_COLORS[i % INCOME_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => fmtFull(v)} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ flex: 1, display: 'grid', gap: 6 }}>
                    {summary.income_by_category.map((c, i) => (
                      <div key={c.category} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <div style={{ width: 9, height: 9, borderRadius: 2, background: INCOME_COLORS[i % INCOME_COLORS.length], flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: '#374151', flex: 1 }}>{c.label}</span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#0D1117' }}>{c.percent}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: 13, color: '#9CA3AF', textAlign: 'center', margin: '30px 0' }}>
                  Ma'lumot yo'q
                </p>
              )}
            </div>
          </div>

          {/* Summary stats */}
          {summary && (
            <div style={cardStyle}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 14px' }}>
                {summary.period_label} — Xulosa
              </h3>
              <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
                {[
                  { label: "Operatsiyalar (daromad)",  value: `${summary.income_count} ta` },
                  { label: "Operatsiyalar (xarajat)",  value: `${summary.expense_count} ta` },
                  { label: "O'tgan davr daromad",      value: summary.prev_income != null ? fmtFull(summary.prev_income) : '—' },
                  { label: "O'tgan davr xarajat",      value: summary.prev_expense != null ? fmtFull(summary.prev_expense) : '—' },
                  { label: "O'tgan davr foyda",        value: summary.prev_profit != null  ? fmtFull(summary.prev_profit)  : '—' },
                ].map(item => (
                  <div key={item.label}>
                    <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#0D1117' }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ════════════════════ TAB: TRANSACTIONS ════════════════════ */}
      {tab === 'transactions' && (
        <div style={{ display: 'grid', gap: 16 }}>

          {/* Filters */}
          <div style={{ ...cardStyle, padding: '14px 18px', display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Filter size={14} color="#6B7280" />
            <select value={txTypeF} onChange={e => { setTxTypeF(e.target.value); setTxPage(1); }} style={{ ...inp, minWidth: 140 }}>
              <option value="">Barcha tur</option>
              <option value="income">Daromad</option>
              <option value="expense">Xarajat</option>
            </select>
            <select value={txCatF} onChange={e => { setTxCatF(e.target.value); setTxPage(1); }} style={{ ...inp, minWidth: 160 }}>
              <option value="">Barcha kategoriya</option>
              <optgroup label="Xarajat">
                {EXPENSE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </optgroup>
              <optgroup label="Daromad">
                {INCOME_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </optgroup>
            </select>
            <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 'auto' }}>
              Jami: {txList?.total ?? 0} ta operatsiya
            </span>
          </div>

          {/* Table */}
          <div style={cardStyle}>
            {txLoading ? (
              <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Yuklanmoqda...</p>
            ) : !txList?.items?.length ? (
              <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Operatsiyalar topilmadi</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #E4E7ED' }}>
                      {['Sana', 'Tur', 'Kategoriya', 'Tavsif', 'Miqdor', "To'lov", 'Jonivor', ''].map(h => (
                        <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#9CA3AF', letterSpacing: '0.06em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {txList.items.map(tx => (
                      <tr key={tx.id} style={{ borderBottom: '1px solid #F3F4F6', transition: 'background .1s' }}
                        onMouseEnter={e => (e.currentTarget.style.background = '#FAFAFA')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                        <td style={{ padding: '11px 14px', color: '#374151', whiteSpace: 'nowrap' }}>
                          {tx.transaction_date}
                        </td>
                        <td style={{ padding: '11px 14px' }}>
                          <span style={{
                            padding: '3px 9px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                            background: tx.type === 'income' ? '#ECFDF5' : '#FEF2F2',
                            color:      tx.type === 'income' ? '#059669' : '#DC2626',
                          }}>
                            {tx.type === 'income' ? '+' : '−'} {tx.type === 'income' ? 'Daromad' : 'Xarajat'}
                          </span>
                        </td>
                        <td style={{ padding: '11px 14px', color: '#374151' }}>
                          {getCategoryLabel(tx.type, tx.category)}
                        </td>
                        <td style={{ padding: '11px 14px', color: '#0D1117', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {tx.description}
                        </td>
                        <td style={{ padding: '11px 14px', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", whiteSpace: 'nowrap',
                          color: tx.type === 'income' ? '#059669' : '#DC2626' }}>
                          {tx.type === 'income' ? '+' : '−'}{fmt(tx.amount_uzs)}
                          {tx.amount_usd && <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 4 }}>/ ${tx.amount_usd}</span>}
                        </td>
                        <td style={{ padding: '11px 14px', color: '#6B7280' }}>
                          {paymentLabel(tx.payment_method)}
                        </td>
                        <td style={{ padding: '11px 14px' }}>
                          {tx.animal_tag
                            ? <span style={{ padding: '2px 7px', background: '#EFF6FF', borderRadius: 5, fontSize: 11, color: '#1D4ED8', fontWeight: 600 }}>{tx.animal_tag}</span>
                            : <span style={{ color: '#D1D5DB', fontSize: 11 }}>—</span>}
                        </td>
                        <td style={{ padding: '11px 14px' }}>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button onClick={() => setModal({ open: true, tx })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6B7280', padding: 4 }}>
                              <Edit2 size={14} />
                            </button>
                            <button onClick={() => setDeleteId(tx.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444', padding: 4 }}>
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {txList && txList.pages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
                {Array.from({ length: txList.pages }, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => setTxPage(p)} style={{
                    width: 32, height: 32, borderRadius: 8, border: 'none', cursor: 'pointer',
                    background: p === txPage ? '#1E3EB4' : '#F7F8FA',
                    color:      p === txPage ? '#fff'    : '#374151',
                    fontSize: 13, fontWeight: p === txPage ? 700 : 400,
                    fontFamily: "'Outfit', sans-serif",
                  }}>{p}</button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════ TAB: TRENDS ════════════════════ */}
      {tab === 'trends' && (
        <div style={{ display: 'grid', gap: 16 }}>

          <div style={{ ...cardStyle, padding: '14px 18px', display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: '#6B7280' }}>Ko'rsatish:</span>
            {[6, 12].map(m => (
              <button key={m} onClick={() => setTrendMonths(m)} style={{
                padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                background: trendMonths === m ? '#1E3EB4' : '#F7F8FA',
                color:      trendMonths === m ? '#fff'    : '#374151',
                fontSize: 13, fontWeight: 600, fontFamily: "'Outfit', sans-serif",
              }}>{m} oy</button>
            ))}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 20 }}>
              {[
                { label: 'Daromad',  color: '#10B981', value: trends?.total_income  ?? 0 },
                { label: 'Xarajat',  color: '#EF4444', value: trends?.total_expense ?? 0 },
                { label: 'Foyda',    color: '#1E3EB4', value: trends?.total_profit  ?? 0 },
              ].map(i => (
                <div key={i.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 3, background: i.color }} />
                  <span style={{ fontSize: 11, color: '#6B7280' }}>{i.label}:</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#0D1117' }}>{fmt(i.value)}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 18px' }}>
              Oylik daromad vs xarajat
            </h3>
            {trendsLoading ? (
              <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Yuklanmoqda...</p>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={trends?.months ?? []} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis dataKey="month_label" tick={{ fontSize: 11, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v: number) => fmtFull(v)} labelStyle={{ fontWeight: 600 }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="income"  name="Daromad"  fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={32} />
                  <Bar dataKey="expense" name="Xarajat"  fill="#EF4444" radius={[4, 4, 0, 0]} maxBarSize={32} />
                  <Bar dataKey="profit"  name="Foyda"    fill="#1E3EB4" radius={[4, 4, 0, 0]} maxBarSize={32} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Monthly table */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 14px' }}>Oylik jadval</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #E4E7ED' }}>
                    {['Oy', 'Daromad', 'Xarajat', 'Foyda', 'Balans'].map(h => (
                      <th key={h} style={{ padding: '9px 14px', textAlign: h === 'Oy' ? 'left' : 'right', fontSize: 11, fontWeight: 700, color: '#9CA3AF', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(trends?.months ?? []).slice().reverse().map(m => (
                    <tr key={m.month} style={{ borderBottom: '1px solid #F3F4F6' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 500, color: '#0D1117' }}>{m.month_label}</td>
                      <td style={{ padding: '10px 14px', textAlign: 'right', color: '#059669', fontWeight: 600 }}>+{fmt(m.income)}</td>
                      <td style={{ padding: '10px 14px', textAlign: 'right', color: '#DC2626', fontWeight: 600 }}>−{fmt(m.expense)}</td>
                      <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 700, color: m.profit >= 0 ? '#059669' : '#DC2626' }}>
                        {m.profit >= 0 ? '+' : ''}{fmt(m.profit)}
                      </td>
                      <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                        <span style={{
                          padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                          background: m.profit >= 0 ? '#ECFDF5' : '#FEF2F2',
                          color:      m.profit >= 0 ? '#059669' : '#DC2626',
                        }}>
                          {m.expense > 0 ? `${((m.income / m.expense - 1) * 100).toFixed(0)}% ROI` : '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════ TAB: ROI ════════════════════ */}
      {tab === 'roi' && (
        <div style={{ display: 'grid', gap: 16 }}>

          {/* Summary */}
          {roi && (
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {[
                { label: 'Jami daromad',  value: roi.total_income,  color: '#059669', bg: '#ECFDF5' },
                { label: 'Jami xarajat',  value: roi.total_expense, color: '#DC2626', bg: '#FEF2F2' },
                { label: 'Sof foyda',     value: roi.total_profit,  color: '#1E3EB4', bg: 'rgba(30,62,180,0.07)' },
                { label: 'Umumiy ROI',    value: roi.overall_roi,   color: '#D97706', bg: '#FFFBEB', suffix: '%' },
              ].map(k => (
                <div key={k.label} style={{ ...cardStyle, flex: 1, minWidth: 140 }}>
                  <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 6 }}>{k.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: k.color }}>
                    {k.suffix ? `${k.value.toFixed(1)}${k.suffix}` : fmt(k.value)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Animals table */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0D1117', margin: '0 0 16px' }}>
              Jonivorlar bo'yicha ROI
            </h3>
            {roiLoading ? (
              <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>Yuklanmoqda...</p>
            ) : !roi?.animals?.length ? (
              <p style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>
                Jonivorlarga bog'langan operatsiyalar yo'q
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #E4E7ED' }}>
                      {['Jonivor', 'Tur', 'Daromad', 'Xarajat', 'Foyda', 'ROI %', "Operatsiya"].map(h => (
                        <th key={h} style={{ padding: '9px 14px', textAlign: h === 'Jonivor' || h === 'Tur' ? 'left' : 'right', fontSize: 11, fontWeight: 700, color: '#9CA3AF', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {roi.animals.map(a => (
                      <tr key={a.animal_id} style={{ borderBottom: '1px solid #F3F4F6' }}>
                        <td style={{ padding: '11px 14px' }}>
                          <span style={{ padding: '3px 9px', background: '#EFF6FF', borderRadius: 6, fontSize: 12, fontWeight: 700, color: '#1D4ED8' }}>{a.tag_id}</span>
                        </td>
                        <td style={{ padding: '11px 14px', color: '#6B7280' }}>{a.species}</td>
                        <td style={{ padding: '11px 14px', textAlign: 'right', color: '#059669', fontWeight: 600 }}>+{fmt(a.total_income)}</td>
                        <td style={{ padding: '11px 14px', textAlign: 'right', color: '#DC2626', fontWeight: 600 }}>−{fmt(a.total_expense)}</td>
                        <td style={{ padding: '11px 14px', textAlign: 'right', fontWeight: 700, color: a.net_profit >= 0 ? '#059669' : '#DC2626' }}>
                          {a.net_profit >= 0 ? '+' : ''}{fmt(a.net_profit)}
                        </td>
                        <td style={{ padding: '11px 14px', textAlign: 'right' }}>
                          <span style={{
                            padding: '4px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                            background: a.roi_percent >= 0 ? '#ECFDF5' : '#FEF2F2',
                            color:      a.roi_percent >= 0 ? '#059669' : '#DC2626',
                          }}>
                            {a.roi_percent >= 0 ? '+' : ''}{a.roi_percent.toFixed(1)}%
                          </span>
                        </td>
                        <td style={{ padding: '11px 14px', textAlign: 'right', color: '#6B7280' }}>{a.tx_count} ta</td>
                      </tr>
                    ))}
                  </tbody>
                  {roi.farm_income > 0 || roi.farm_expense > 0 ? (
                    <tfoot>
                      <tr style={{ borderTop: '2px solid #E4E7ED', background: '#F9FAFB' }}>
                        <td colSpan={2} style={{ padding: '10px 14px', fontWeight: 600, color: '#374151' }}>Ferma (umumiy)</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: '#059669', fontWeight: 600 }}>+{fmt(roi.farm_income)}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: '#DC2626', fontWeight: 600 }}>−{fmt(roi.farm_expense)}</td>
                        <td colSpan={3} />
                      </tr>
                    </tfoot>
                  ) : null}
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════ MODAL: Add/Edit ════════ */}
      {modal.open && (
        <TransactionModal
          tx={modal.tx}
          onClose={() => setModal({ open: false, tx: null })}
          onSaved={() => setModal({ open: false, tx: null })}
        />
      )}

      {/* ════════ CONFIRM DELETE ════════ */}
      {deleteId !== null && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.45)',
          display: 'grid', placeItems: 'center',
        }} onClick={() => setDeleteId(null)}>
          <div style={{
            background: '#fff', borderRadius: 16, padding: '28px 32px', width: 360,
            boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: '#FEF2F2', display: 'grid', placeItems: 'center' }}>
                <Trash2 size={18} color="#DC2626" />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0D1117', margin: 0 }}>O'chirishni tasdiqlang</h3>
            </div>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 22 }}>
              Bu operatsiya butunlay o'chiriladi. Bu amalni qaytarib bo'lmaydi.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setDeleteId(null)} style={{
                flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid #E4E7ED',
                background: '#F7F8FA', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                fontFamily: "'Outfit', sans-serif", color: '#374151',
              }}>Bekor</button>
              <button
                onClick={() => deleteMutation.mutate(deleteId)}
                disabled={deleteMutation.isPending}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 10, border: 'none',
                  background: '#DC2626', color: '#fff', cursor: 'pointer',
                  fontSize: 13, fontWeight: 700, fontFamily: "'Outfit', sans-serif",
                  opacity: deleteMutation.isPending ? 0.7 : 1,
                }}>
                {deleteMutation.isPending ? 'O\'chirilmoqda...' : 'O\'chirish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}