/**
 * AnimalsPage — Optimized with TanStack Query
 *
 * OPTIMIZATSIYALAR:
 *   1. useQuery: sahifaga qaytganda ma'lumot keshdan darhol ko'rsatiladi
 *   2. keepPreviousData: sahifa/filter almashtirganda eski data "titrab" yo'qolmaydi
 *   3. useMutation: delete/create/update dan keyin keshni avtomatik yangilaydi
 *   4. Debounce: useState/useRef bilan — qidiruvda har harf = API call emas
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, Plus, RefreshCw, AlertCircle, Search,
  ChevronDown, ChevronUp, ChevronsUpDown,
  Eye, Edit2, Trash2, Upload, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { queryKeys } from '../lib/queryClient';
import config from '../config';

// =============================================================================
// TYPES
// =============================================================================

interface Animal {
  id: number;
  tag_id: string;
  species: string;
  gender: string;
  status: string;
  breed?: string;
  notes?: string;
  acquisition_date?: string;
  total_detections: number;
  last_detected_at: string | null;
}

interface AnimalSearchResponse {
  items: Animal[];
  total: number;
  skip: number;
  limit: number;
}

type SortField = 'tag_id' | 'species' | 'status' | 'total_detections' | 'last_detected_at';
type SortOrder = 'asc' | 'desc';

// =============================================================================
// CONSTANTS
// =============================================================================

const SPECIES_OPTIONS = [
  { value: '', label: 'Barcha turlar' },
  { value: 'cattle', label: 'Cattle (Qoramol)' },
  { value: 'sheep', label: "Sheep (Qo'y)" },
  { value: 'goat', label: 'Goat (Echki)' },
  { value: 'horse', label: 'Horse (Ot)' },
  { value: 'other', label: 'Boshqa' },
];

const GENDER_OPTIONS = [
  { value: '', label: 'Barcha jinslar' },
  { value: 'male', label: 'Erkak' },
  { value: 'female', label: "Urg'ochi" },
  { value: 'unknown', label: "Noma'lum" },
];

const STATUS_OPTIONS = [
  { value: '', label: 'Barcha holatlar' },
  { value: 'active', label: 'Faol' },
  { value: 'quarantine', label: 'Karantin' },
  { value: 'sick', label: 'Kasal' },
  { value: 'sold', label: 'Sotilgan' },
  { value: 'deceased', label: 'Vafot etgan' },
  { value: 'transferred', label: "Ko'chirilgan" },
];

const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  active:      { bg: 'bg-emerald-50',  text: 'text-emerald-700', dot: 'bg-emerald-500' },
  quarantine:  { bg: 'bg-amber-50',    text: 'text-amber-700',   dot: 'bg-amber-500'   },
  sick:        { bg: 'bg-red-50',      text: 'text-red-700',     dot: 'bg-red-500'     },
  sold:        { bg: 'bg-sky-50',      text: 'text-sky-700',     dot: 'bg-sky-500'     },
  deceased:    { bg: 'bg-gray-100',    text: 'text-gray-500',    dot: 'bg-gray-400'    },
  transferred: { bg: 'bg-violet-50',   text: 'text-violet-700',  dot: 'bg-violet-500'  },
};

const STATUS_LABELS: Record<string, string> = {
  active: 'Faol', quarantine: 'Karantin', sick: 'Kasal',
  sold: 'Sotilgan', deceased: 'Vafot etgan', transferred: "Ko'chirilgan",
};

const PAGE_SIZE = 20;

// =============================================================================
// HELPERS
// =============================================================================

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_STYLES[status] ?? STATUS_STYLES.active;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function SortHeader({ field, label, current, order, onSort }: {
  field: SortField; label: string; current: SortField; order: SortOrder;
  onSort: (f: SortField) => void;
}) {
  const active = current === field;
  return (
    <th onClick={() => onSort(field)}
      className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:text-gray-800 transition-colors group">
      <div className="flex items-center gap-1">
        {label}
        <span className={`transition-opacity ${active ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
          {active
            ? (order === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />)
            : <ChevronsUpDown size={12} />}
        </span>
      </div>
    </th>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short', year: 'numeric' });
}

// =============================================================================
// MODAL
// =============================================================================

interface AnimalFormData {
  tag_id: string; species: string; gender: string;
  acquisition_date: string; breed: string; notes: string; photo?: File | null;
}

function AnimalModal({ initial, onClose, onSaved }: {
  initial?: Animal; onClose: () => void; onSaved: () => void;
}) {
  const isEdit = Boolean(initial);
  const fileRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<AnimalFormData>({
    tag_id: initial?.tag_id ?? '', species: initial?.species ?? 'cattle',
    gender: initial?.gender ?? 'male',
    acquisition_date: initial?.acquisition_date ? initial.acquisition_date.split('T')[0] : new Date().toISOString().split('T')[0],
    breed: initial?.breed ?? '', notes: initial?.notes ?? '', photo: null,
  });
  const [photoPreview, setPhotoPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (key: keyof AnimalFormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm(p => ({ ...p, [key]: key === 'tag_id' ? e.target.value.toUpperCase() : e.target.value }));

  async function handleSubmit() {
    if (!form.tag_id.trim()) { setError('Tag ID kiritilishi shart'); return; }
    setLoading(true); setError('');
    try {
      const body = { ...form, photo: undefined, acquisition_date: `${form.acquisition_date}T00:00:00`,
        breed: form.breed || undefined, notes: form.notes || undefined };
      if (isEdit) {
        await apiFetch(`/api/v1/animals/${initial!.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      } else {
        const created = await apiFetch<{ id: number }>('/api/v1/animals/', { method: 'POST', body: JSON.stringify(body) });
        if (form.photo && created?.id) {
          try {
            const fd = new FormData(); fd.append('photo', form.photo);
            const token = localStorage.getItem('tv_access_token');
            await fetch(`${config.apiUrl}/api/v1/identification/register/${created.id}`,
              { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd });
          } catch { /* rasm yuklanmasa ham jonivor saqlanadi */ }
        }
      }
      onSaved(); onClose();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Xato'); }
    finally { setLoading(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">
            {isEdit ? 'Jonivorni tahrirlash' : "Yangi jonivor qo'shish"}
          </h2>
        </div>
        <div className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Tag ID *</label>
            <input type="text" value={form.tag_id} onChange={set('tag_id')} placeholder="JNV-001"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Tur</label>
              <select value={form.species} onChange={set('species')}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm">
                <option value="cattle">Cattle</option><option value="sheep">Sheep</option>
                <option value="goat">Goat</option><option value="horse">Horse</option><option value="other">Boshqa</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Jins</label>
              <select value={form.gender} onChange={set('gender')}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm">
                <option value="male">Erkak</option><option value="female">Urg'ochi</option><option value="unknown">Noma'lum</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Kiritilgan sana</label>
            <input type="date" value={form.acquisition_date} onChange={set('acquisition_date')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Zot</label>
            <input type="text" value={form.breed} onChange={set('breed')} placeholder="Angus, Hereford..."
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Izohlar</label>
            <textarea value={form.notes} onChange={set('notes')} rows={2}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm resize-none" />
          </div>
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Identifikatsiya rasmi</label>
              <div onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-gray-200 rounded-xl p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-colors">
                {photoPreview
                  ? <img src={photoPreview} alt="preview" className="max-h-28 mx-auto rounded-lg object-cover" />
                  : <div className="text-gray-400"><Upload className="w-6 h-6 mx-auto mb-1" /><p className="text-sm">Rasm tanlash</p></div>}
                <input ref={fileRef} type="file" accept="image/*" className="hidden"
                  onChange={e => {
                    const f = e.target.files?.[0]; if (!f) return;
                    setForm(p => ({ ...p, photo: f }));
                    const r = new FileReader(); r.onload = ev => setPhotoPreview(ev.target?.result as string); r.readAsDataURL(f);
                  }} />
              </div>
              {form.photo && <p className="text-xs text-emerald-600 mt-1">✓ {form.photo.name}</p>}
            </div>
          )}
        </div>
        <div className="p-6 border-t border-gray-100 flex gap-3">
          <button onClick={onClose} disabled={loading}
            className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
            Bekor qilish
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Saqlanmoqda...' : isEdit ? 'Saqlash' : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function AnimalsPage() {
  const navigate  = useNavigate();
  const qClient   = useQueryClient();

  // ─── Filter state ──────────────────────────────────────────────────────────
  const [search, setSearch]             = useState('');
  const [debouncedSearch, setDebSearch] = useState('');
  const [species, setSpecies]           = useState('');
  const [gender, setGender]             = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy]             = useState<SortField>('tag_id');
  const [sortOrder, setSortOrder]       = useState<SortOrder>('asc');
  const [page, setPage]                 = useState(0);

  const [showAdd, setShowAdd]       = useState(false);
  const [editAnimal, setEditAnimal] = useState<Animal | null>(null);

  // Debounce — 350ms kechikish, har harf = API call bo'lmaydi
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebSearch(search);
      setPage(0);
    }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Filter o'zgarganda pagedan qaytish
  useEffect(() => { setPage(0); }, [species, gender, statusFilter, sortBy, sortOrder]);

  // ─── Query params object ────────────────────────────────────────────────────
  const queryParams = {
    page, sortBy, sortOrder,
    search: debouncedSearch,
    species, gender, status: statusFilter,
  };

  // ─── Data fetching (TanStack Query) ───────────────────────────────────────
  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: queryKeys.animals.search(queryParams),
    queryFn: async () => {
      const params = new URLSearchParams({
        skip: String(page * PAGE_SIZE),
        limit: String(PAGE_SIZE),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (debouncedSearch) params.set('search_text', debouncedSearch);
      if (species)         params.set('species', species);
      if (gender)          params.set('gender', gender);
      if (statusFilter)    params.set('status', statusFilter);
      const res = await apiFetch<any>(`/api/v1/animals/search?${params}`);
      if (Array.isArray(res)) return { items: res as Animal[], total: res.length };
      return { items: (res.items ?? []) as Animal[], total: (res.total ?? 0) as number };
    },
    // Sahifaga qaytganda eski data ko'rinib turadi, background da yangilanadi
    placeholderData: (prev) => prev,
  });

  const animals = data?.items ?? [];
  const total   = data?.total ?? 0;

  // ─── Mutations ─────────────────────────────────────────────────────────────
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/animals/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      // Barcha animals qidruv keshini tozalaymiz
      qClient.invalidateQueries({ queryKey: queryKeys.animals.all });
    },
    onError: (e: Error) => alert("O'chirish xatolik: " + e.message),
  });

  function handleSort(field: SortField) {
    if (sortBy === field) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortOrder('asc'); }
  }

  async function handleDelete(animal: Animal) {
    if (!window.confirm(`"${animal.tag_id}" ni o'chirishga ishonchingiz komilmi?`)) return;
    deleteMutation.mutate(animal.id);
  }

  function handleSaved() {
    qClient.invalidateQueries({ queryKey: queryKeys.animals.all });
  }

  const totalPages  = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageStart   = page * PAGE_SIZE + 1;
  const pageEnd     = Math.min((page + 1) * PAGE_SIZE, total);
  const activeFilters = [species, gender, statusFilter].filter(Boolean).length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jonivorlar</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {isFetching && animals.length === 0
              ? 'Yuklanmoqda...'
              : total > 0
              ? `Jami ${total} ta jonivor`
              : "Ro'yxat bo'sh"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} disabled={isFetching}
            className="p-2.5 border border-gray-200 rounded-xl text-gray-500 hover:bg-gray-50 disabled:opacity-50 transition-colors">
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-sm">
            <Plus className="w-4 h-4" /> Yangi qo'shish
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-2xl p-4 mb-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Tag ID, zot bo'yicha qidirish..."
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>
          <select value={species} onChange={e => setSpecies(e.target.value)}
            className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 text-gray-700 bg-white">
            {SPECIES_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={gender} onChange={e => setGender(e.target.value)}
            className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 text-gray-700 bg-white">
            {GENDER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 text-gray-700 bg-white">
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {activeFilters > 0 && (
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-400">Faol filtrlar:</span>
            {species && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-100">
                {SPECIES_OPTIONS.find(o => o.value === species)?.label}
                <button onClick={() => setSpecies('')} className="hover:text-blue-900 font-bold ml-0.5">×</button>
              </span>
            )}
            {gender && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-100">
                {GENDER_OPTIONS.find(o => o.value === gender)?.label}
                <button onClick={() => setGender('')} className="hover:text-blue-900 font-bold ml-0.5">×</button>
              </span>
            )}
            {statusFilter && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-100">
                {STATUS_OPTIONS.find(o => o.value === statusFilter)?.label}
                <button onClick={() => setStatusFilter('')} className="hover:text-blue-900 font-bold ml-0.5">×</button>
              </span>
            )}
            <button onClick={() => { setSpecies(''); setGender(''); setStatusFilter(''); }}
              className="ml-auto text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2">
              Barchasini tozalash
            </button>
          </div>
        )}
      </div>

      {/* Error */}
      {isError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm mb-5">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error instanceof Error ? error.message : 'Xato yuz berdi'}
        </div>
      )}

      {/* Subtle loading overlay — eski data ko'rinib turadi */}
      <div className={`transition-opacity duration-150 ${isFetching ? 'opacity-70' : 'opacity-100'}`}>

        {animals.length === 0 && !isFetching ? (
          <div className="bg-white border border-gray-200 rounded-2xl p-16 text-center shadow-sm">
            <Users className="w-12 h-12 text-gray-200 mx-auto mb-3" />
            <p className="text-gray-500 font-medium mb-1">
              {debouncedSearch || activeFilters > 0 ? 'Hech narsa topilmadi' : "Hali jonivor qo'shilmagan"}
            </p>
            {!debouncedSearch && !activeFilters && (
              <button onClick={() => setShowAdd(true)}
                className="mt-3 inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700">
                <Plus className="w-4 h-4" /> Birinchi jonivorni qo'shish
              </button>
            )}
          </div>
        ) : animals.length === 0 && isFetching ? (
          <div className="bg-white border border-gray-200 rounded-2xl p-16 text-center text-gray-400 shadow-sm">
            <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin opacity-30" />
            <p className="text-sm">Yuklanmoqda...</p>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50/80 border-b border-gray-200">
                  <tr>
                    <SortHeader field="tag_id"           label="Tag ID"          current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="species"          label="Tur"             current={sortBy} order={sortOrder} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Jins</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Zot</th>
                    <SortHeader field="status"           label="Holat"           current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="total_detections" label="Aniqlash"        current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="last_detected_at" label="Oxirgi ko'rinish" current={sortBy} order={sortOrder} onSort={handleSort} />
                    <th className="px-4 py-3 w-24" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {animals.map(a => (
                    <tr key={a.id} onClick={() => navigate(`/animals/${a.id}`)}
                      className="hover:bg-blue-50/30 cursor-pointer transition-colors group">
                      <td className="px-4 py-3.5">
                        <span className="font-mono font-semibold text-gray-900 text-sm">{a.tag_id}</span>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-gray-600 capitalize">{a.species}</td>
                      <td className="px-4 py-3.5 text-sm text-gray-600 capitalize">{a.gender}</td>
                      <td className="px-4 py-3.5 text-sm text-gray-500">{a.breed || '—'}</td>
                      <td className="px-4 py-3.5"><StatusBadge status={a.status} /></td>
                      <td className="px-4 py-3.5">
                        <span className={`text-sm font-semibold tabular-nums ${a.total_detections > 0 ? 'text-gray-900' : 'text-gray-300'}`}>
                          {a.total_detections.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-gray-500 whitespace-nowrap">{formatDate(a.last_detected_at)}</td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={e => { e.stopPropagation(); navigate(`/animals/${a.id}`); }}
                            className="p-1.5 text-blue-600 hover:bg-blue-100 rounded-lg" title="Ko'rish">
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={e => { e.stopPropagation(); setEditAnimal(a); }}
                            className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-lg" title="Tahrirlash">
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={e => { e.stopPropagation(); handleDelete(a); }}
                            className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg" title="O'chirish">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/50">
                <span className="text-xs text-gray-500 tabular-nums">
                  {pageStart}–{pageEnd} / {total} ta
                </span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                    className="p-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const p = totalPages <= 5 ? i : Math.max(0, Math.min(totalPages - 5, page - 2)) + i;
                    return (
                      <button key={p} onClick={() => setPage(p)}
                        className={`w-8 h-8 text-xs rounded-lg border transition-colors ${page === p ? 'bg-blue-600 border-blue-600 text-white font-semibold' : 'border-gray-200 text-gray-600 hover:bg-white'}`}>
                        {p + 1}
                      </button>
                    );
                  })}
                  <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                    className="p-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showAdd && <AnimalModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); handleSaved(); }} />}
      {editAnimal && <AnimalModal initial={editAnimal} onClose={() => setEditAnimal(null)} onSaved={() => { setEditAnimal(null); handleSaved(); }} />}
    </div>
  );
}