/**
 * Taurus Vision — AnimalsPage
 *
 * Jonivorlar ro'yxati sahifasi.
 *
 * FEATURELAR:
 *   1. Sahifalangan jadval (20 ta / sahifa)
 *   2. Filtrlar: qidiruv, tur, jins, holat
 *   3. Saralash (har bir ustun bo'yicha)
 *   4. Bitta qo'shish modali
 *   5. Tahrirlash modali
 *   6. O'chirish (tasdiqlash bilan)
 *   7. CSV orqali ommaviy import  ← B6 yangi feature
 *
 * OPTIMIZATSIYALAR:
 *   - useQuery: keshdan darhol ko'rsatish
 *   - useMutation: create/update/delete keyin kesh yangilash
 *   - Debounce: qidiruvda har harf = API call emas (300ms)
 */

import { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle, ChevronDown, ChevronLeft, ChevronRight,
  ChevronUp, ChevronsUpDown, Download, Edit2, Eye,
  FileText, Plus, RefreshCw, Search, Trash2, Upload,
  Users, X, CheckCircle, XCircle, SkipForward, ImagePlus, Image,
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

interface AnimalListResponse {
  items: Animal[];
  total: number;
  skip: number;
  limit: number;
}

interface BulkImportRowResult {
  row: number;
  tag_id: string | null;
  status: 'created' | 'skipped' | 'error';
  animal_id: number | null;
  message: string;
}

interface BulkImportResponse {
  total_rows: number;
  created: number;
  skipped: number;
  errors: number;
  results: BulkImportRowResult[];
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

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('uz-UZ', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    });
  } catch {
    return '—';
  }
}

// =============================================================================
// UI COMPONENTS
// =============================================================================

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES['active'];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

interface SortHeaderProps {
  field: SortField;
  label: string;
  current: SortField;
  order: SortOrder;
  onSort: (f: SortField) => void;
}

function SortHeader({ field, label, current, order, onSort }: SortHeaderProps) {
  const active = current === field;
  return (
    <th
      className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:text-gray-700 transition-colors"
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active
          ? order === 'asc'
            ? <ChevronUp className="w-3.5 h-3.5 text-blue-500" />
            : <ChevronDown className="w-3.5 h-3.5 text-blue-500" />
          : <ChevronsUpDown className="w-3.5 h-3.5 opacity-30" />
        }
      </span>
    </th>
  );
}

// =============================================================================
// ANIMAL MODAL (qo'shish / tahrirlash)
// =============================================================================

interface AnimalModalProps {
  initial?: Animal | null;
  onClose: () => void;
  onSaved: () => void;
}

function AnimalModal({ initial, onClose, onSaved }: AnimalModalProps) {
  const isEdit = !!initial;
  const [form, setForm] = useState({
    tag_id:           initial?.tag_id           ?? '',
    species:          initial?.species          ?? 'cattle',
    breed:            initial?.breed            ?? '',
    gender:           initial?.gender           ?? 'unknown',
    status:           initial?.status           ?? 'active',
    acquisition_date: initial?.acquisition_date
      ? initial.acquisition_date.slice(0, 10)
      : new Date().toISOString().slice(0, 10),
    notes:            initial?.notes            ?? '',
  });
  const [error, setError]         = useState('');
  const [saving, setSaving]       = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  // Saqlangandan keyin profil rasmi haqida so'rov
  const [pendingAnimalId, setPendingAnimalId] = useState<number | null>(null);
  const photoRef = useRef<HTMLInputElement>(null);

  const set = (field: string, value: string) =>
    setForm(prev => ({ ...prev, [field]: value }));

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  const uploadPhoto = async (animalId: number, asProfile: boolean) => {
    if (!photoFile) return;
    const fd = new FormData();
    fd.append('file', photoFile);
    await fetch(`/api/v1/animals/${animalId}/photos?set_as_profile=${asProfile}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('tv_access_token') ?? ''}` },
      body: fd,
    });
  };

  const handleSubmit = async () => {
    setError('');
    if (!form.tag_id.trim()) { setError("Tag ID majburiy"); return; }
    if (!form.species)        { setError("Tur tanlang");      return; }

    setSaving(true);
    try {
      const body = {
        tag_id:           form.tag_id.trim().toUpperCase(),
        species:          form.species,
        breed:            form.breed.trim() || null,
        gender:           form.gender,
        status:           form.status,
        acquisition_date: form.acquisition_date || null,
        notes:            form.notes.trim() || null,
      };

      let animalId: number;
      if (isEdit && initial) {
        await apiFetch(`/api/v1/animals/${initial.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        animalId = initial.id;
      } else {
        const created = await apiFetch<{ id: number }>('/api/v1/animals/', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        animalId = created.id;
      }

      // Rasm tanlangan bo'lsa — profil haqida so'rab olamiz
      if (photoFile) {
        setPendingAnimalId(animalId);
        return; // dialog ochiladi
      }

      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Xato yuz berdi');
    } finally {
      setSaving(false);
    }
  };

  // "Ha" — profil rasmi sifatida saqlash
  const handleConfirmProfile = async (asProfile: boolean) => {
    if (!pendingAnimalId) return;
    try {
      await uploadPhoto(pendingAnimalId, asProfile);
    } catch { /* rasm yuklanmasa ham davom etamiz */ }
    onSaved();
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">
            {isEdit ? 'Jonivorni tahrirlash' : 'Yangi jonivor qo\'shish'}
          </h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Tag ID */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Tag ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.tag_id}
              onChange={e => set('tag_id', e.target.value)}
              placeholder="JNV-001"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
            />
          </div>

          {/* Tur + Jins */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Tur <span className="text-red-500">*</span>
              </label>
              <select value={form.species} onChange={e => set('species', e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 bg-white">
                {SPECIES_OPTIONS.slice(1).map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">Jins</label>
              <select value={form.gender} onChange={e => set('gender', e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 bg-white">
                {GENDER_OPTIONS.slice(1).map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Zot + Holat */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">Zot</label>
              <input type="text" value={form.breed} onChange={e => set('breed', e.target.value)}
                placeholder="Holstein, Angus..."
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">Holat</label>
              <select value={form.status} onChange={e => set('status', e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 bg-white">
                {STATUS_OPTIONS.slice(1).map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Sotib olingan sana */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Sotib olingan sana</label>
            <input type="date" value={form.acquisition_date} onChange={e => set('acquisition_date', e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500" />
          </div>

          {/* Izoh */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Izoh</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              rows={2} placeholder="Qo'shimcha ma'lumot..."
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 resize-none" />
          </div>

          {/* Rasm tanlash */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Rasm (ixtiyoriy)
            </label>
            <div className="flex items-center gap-3">
              {photoPreview ? (
                <div className="relative w-14 h-14 rounded-xl overflow-hidden border-2 border-blue-200 shrink-0">
                  <img src={photoPreview} alt="preview" className="w-full h-full object-cover" />
                  <button
                    onClick={() => { setPhotoFile(null); setPhotoPreview(null); }}
                    className="absolute top-0.5 right-0.5 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
                    <X className="w-2.5 h-2.5 text-white" />
                  </button>
                </div>
              ) : (
                <div className="w-14 h-14 rounded-xl border-2 border-dashed border-gray-200 flex items-center justify-center bg-gray-50 shrink-0">
                  <Image className="w-5 h-5 text-gray-300" />
                </div>
              )}
              <button
                onClick={() => photoRef.current?.click()}
                className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 transition-colors">
                <ImagePlus className="w-4 h-4" />
                {photoPreview ? 'Almashtirish' : 'Rasm tanlash'}
              </button>
              <input ref={photoRef} type="file" accept="image/*"
                className="hidden" onChange={handlePhotoChange} />
            </div>
          </div>

          {/* Profil rasmi so'rovi dialogi */}
          {pendingAnimalId && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-blue-900 mb-1">
                Rasm saqlandi ✅
              </p>
              <p className="text-sm text-blue-700 mb-3">
                Bu rasmni <b>profil rasmi</b> sifatida ham saqlashmi?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleConfirmProfile(true)}
                  className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors">
                  Ha, saqlash
                </button>
                <button
                  onClick={() => handleConfirmProfile(false)}
                  className="px-4 py-2 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50 transition-colors">
                  Yo'q
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2.5 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-100 bg-gray-50/50 rounded-b-2xl">
          <button onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl transition-colors">
            Bekor qilish
          </button>
          {!pendingAnimalId && (
            <button onClick={handleSubmit} disabled={saving}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl disabled:opacity-50 transition-colors flex items-center gap-2">
              {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              {isEdit ? 'Saqlash' : "Qo'shish"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// CSV IMPORT MODAL  (B6)
// =============================================================================

interface CsvImportModalProps {
  onClose: () => void;
  onImported: () => void;
}

function CsvImportModal({ onClose, onImported }: CsvImportModalProps) {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkImportResponse | null>(null);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Namuna CSV ni yuklab olish
  const downloadTemplate = () => {
    window.open(`${config.apiUrl ?? ''}/api/v1/animals/import/template`, '_blank');
  };

  // Fayl tanlash yoki drag-drop
  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setError("Faqat .csv kengaytmali fayllar qabul qilinadi");
      return;
    }
    if (f.size > 2 * 1024 * 1024) {
      setError(`Fayl hajmi juda katta: ${(f.size / 1024 / 1024).toFixed(1)} MB. Maksimal: 2 MB`);
      return;
    }
    setError('');
    setResult(null);
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  // Import yuborish
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await apiFetch<BulkImportResponse>(
        `/api/v1/animals/import/csv?skip_duplicates=${skipDuplicates}`,
        { method: 'POST', body: formData },
      );
      setResult(res);
      if (res.created > 0) {
        onImported(); // Ro'yxatni yangilash
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Import xatosi');
    } finally {
      setUploading(false);
    }
  };

  // Natija ikonasi
  const rowIcon = (s: BulkImportRowResult['status']) => {
    if (s === 'created')  return <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />;
    if (s === 'skipped')  return <SkipForward className="w-4 h-4 text-amber-400 shrink-0" />;
    return <XCircle className="w-4 h-4 text-red-500 shrink-0" />;
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">CSV orqali import</h2>
              <p className="text-xs text-gray-400">Ko'p jonivorni bir vaqtda qo'shish</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Kontent */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">

          {/* Shablon yuklab olish */}
          <div className="flex items-center justify-between bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
            <div>
              <p className="text-sm font-medium text-blue-800">Namuna shablon</p>
              <p className="text-xs text-blue-600 mt-0.5">
                Birinchi marta ishlatsangiz, shablonni yuklab to'ldiring
              </p>
            </div>
            <button
              onClick={downloadTemplate}
              className="flex items-center gap-2 bg-white border border-blue-200 text-blue-700 text-sm font-medium px-3 py-2 rounded-lg hover:bg-blue-50 transition-colors shrink-0"
            >
              <Download className="w-3.5 h-3.5" />
              Yuklab olish
            </button>
          </div>

          {/* CSV formati haqida */}
          <div className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3">
            <p className="text-xs font-semibold text-gray-600 mb-2">CSV USTUNLARI:</p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-gray-500">
              <span><span className="text-gray-800 font-mono">tag_id</span> — Majburiy. Noyob ID (JNV-001)</span>
              <span><span className="text-gray-800 font-mono">gender</span> — Ixtiyoriy. male/female/unknown</span>
              <span><span className="text-gray-800 font-mono">species</span> — Majburiy. cattle/sheep/goat/horse</span>
              <span><span className="text-gray-800 font-mono">birth_date</span> — Ixtiyoriy. YYYY-MM-DD</span>
              <span><span className="text-gray-800 font-mono">breed</span> — Ixtiyoriy. Zot nomi</span>
              <span><span className="text-gray-800 font-mono">status</span> — Ixtiyoriy. active (default)</span>
            </div>
          </div>

          {/* Fayl tanlash */}
          {!result && (
            <>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className={`
                  border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
                  ${dragOver
                    ? 'border-blue-400 bg-blue-50'
                    : file
                      ? 'border-emerald-300 bg-emerald-50'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  }
                `}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
                />
                {file ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
                      <FileText className="w-6 h-6 text-emerald-600" />
                    </div>
                    <p className="text-sm font-semibold text-emerald-700">{file.name}</p>
                    <p className="text-xs text-emerald-500">
                      {(file.size / 1024).toFixed(1)} KB — boshqa fayl tanlash uchun bosing
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center">
                      <Upload className="w-6 h-6 text-gray-400" />
                    </div>
                    <p className="text-sm font-medium text-gray-600">
                      CSV faylni shu yerga tashlang yoki bosib tanlang
                    </p>
                    <p className="text-xs text-gray-400">Maksimal hajm: 2 MB · Faqat .csv</p>
                  </div>
                )}
              </div>

              {/* Sozlamalar */}
              <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">Takroriy tag_id lar</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {skipDuplicates
                      ? "Mavjud tag lar o'tkazib yuboriladi (xavfsiz)"
                      : "Mavjud tag lar xato sifatida belgilanadi"}
                  </p>
                </div>
                <button
                  onClick={() => setSkipDuplicates(p => !p)}
                  className={`
                    relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors
                    ${skipDuplicates ? 'bg-blue-600' : 'bg-gray-300'}
                  `}
                >
                  <span className={`
                    inline-block h-5 w-5 mt-0.5 rounded-full bg-white shadow transition-transform
                    ${skipDuplicates ? 'translate-x-5' : 'translate-x-0.5'}
                  `} />
                </button>
              </div>
            </>
          )}

          {/* Xato */}
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}

          {/* Natija */}
          {result && (
            <div className="space-y-4">
              {/* Umumiy statistika */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-emerald-700">{result.created}</p>
                  <p className="text-xs text-emerald-600 mt-0.5">Yaratildi</p>
                </div>
                <div className="bg-amber-50 border border-amber-100 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-amber-700">{result.skipped}</p>
                  <p className="text-xs text-amber-600 mt-0.5">O'tkazildi</p>
                </div>
                <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-red-700">{result.errors}</p>
                  <p className="text-xs text-red-600 mt-0.5">Xato</p>
                </div>
              </div>

              {/* Satr natijalari */}
              <div className="border border-gray-100 rounded-xl overflow-hidden">
                <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    Batafsil natija — {result.total_rows} ta satr
                  </p>
                </div>
                <div className="max-h-60 overflow-y-auto divide-y divide-gray-50">
                  {result.results.map(r => (
                    <div
                      key={r.row}
                      className={`flex items-start gap-3 px-4 py-2.5 text-sm ${
                        r.status === 'error' ? 'bg-red-50/50' : ''
                      }`}
                    >
                      {rowIcon(r.status)}
                      <div className="flex-1 min-w-0">
                        <span className="font-mono font-semibold text-gray-800 text-xs">
                          {r.tag_id ?? `Satr ${r.row}`}
                        </span>
                        {' '}
                        <span className="text-gray-500 text-xs">{r.message}</span>
                      </div>
                      <span className="text-xs text-gray-400 shrink-0 tabular-nums">#{r.row}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/50 rounded-b-2xl shrink-0">
          {result ? (
            <>
              <p className="text-xs text-gray-500">
                Import yakunlandi: <span className="font-semibold text-gray-700">{result.created}</span> ta yangi jonivor qo'shildi
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setResult(null); setFile(null); setError(''); }}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl transition-colors"
                >
                  Yana import
                </button>
                <button
                  onClick={onClose}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition-colors"
                >
                  Yopish
                </button>
              </div>
            </>
          ) : (
            <>
              <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl transition-colors">
                Bekor qilish
              </button>
              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {uploading
                  ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Import qilinmoqda...</>
                  : <><Upload className="w-3.5 h-3.5" /> Import qilish</>
                }
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function AnimalsPage() {
  const navigate    = useNavigate();
  const qClient     = useQueryClient();

  // State
  const [page, setPage]                 = useState(0);
  const [search, setSearch]             = useState('');
  const [debouncedSearch, setDebounced] = useState('');
  const [species, setSpecies]           = useState('');
  const [gender, setGender]             = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy]             = useState<SortField>('tag_id');
  const [sortOrder, setSortOrder]       = useState<SortOrder>('asc');
  const [showAdd, setShowAdd]           = useState(false);
  const [showImport, setShowImport]     = useState(false);
  const [editAnimal, setEditAnimal]     = useState<Animal | null>(null);

  // Debounce
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebounced(search);
      setPage(0);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  // Filtr o'zgarganda 1-sahifaga qaytish
  useEffect(() => { setPage(0); }, [species, gender, statusFilter, sortBy, sortOrder]);

  // Query parametrlar
  const queryParams = new URLSearchParams({
    skip:  String(page * PAGE_SIZE),
    limit: String(PAGE_SIZE),
  });
  if (debouncedSearch) queryParams.set('search_text', debouncedSearch);
  if (species)         queryParams.set('species', species);
  if (gender)          queryParams.set('gender', gender);
  if (statusFilter)    queryParams.set('status', statusFilter);
  queryParams.set('sort_by',    sortBy);
  queryParams.set('sort_order', sortOrder);

  // Qidirish yoki oddiy ro'yxat
  const endpoint = debouncedSearch || gender
    ? `/api/v1/animals/search?${queryParams}`
    : `/api/v1/animals/?skip=${page * PAGE_SIZE}&limit=${PAGE_SIZE}${species ? `&species=${species}` : ''}${statusFilter ? `&status=${statusFilter}` : ''}`;

  const { data, isFetching, isError, error, refetch } = useQuery<AnimalListResponse | Animal[]>({
    queryKey: [queryKeys.animals, page, debouncedSearch, species, gender, statusFilter, sortBy, sortOrder],
    queryFn: () => apiFetch(endpoint),
    placeholderData: (prev) => prev,
  });

  // Normalize response (search qaytaradi array, list qaytaradi object)
  const animals: Animal[] = Array.isArray(data) ? data : (data?.items ?? []);
  const total: number     = Array.isArray(data) ? data.length : (data?.total ?? 0);
  const totalPages        = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageStart         = page * PAGE_SIZE + 1;
  const pageEnd           = Math.min((page + 1) * PAGE_SIZE, total);

  // Faol filtrlar soni
  const activeFilters = [species, gender, statusFilter, debouncedSearch].filter(Boolean).length;

  // Saralash toggle
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/v1/animals/${id}`, { method: 'DELETE' }),
    onSuccess: () => qClient.invalidateQueries({ queryKey: [queryKeys.animals] }),
  });

  const handleDelete = (a: Animal) => {
    if (window.confirm(`"${a.tag_id}" ni o'chirishni tasdiqlaysizmi?`)) {
      deleteMutation.mutate(a.id);
    }
  };

  const handleSaved = () => {
    qClient.invalidateQueries({ queryKey: [queryKeys.animals] });
  };

  // =========================================================================
  // RENDER
  // =========================================================================

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
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2.5 border border-gray-200 rounded-xl text-gray-500 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            title="Yangilash"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>

          {/* CSV Import tugmasi */}
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-2 border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors shadow-sm"
            title="CSV orqali import"
          >
            <FileText className="w-4 h-4 text-gray-500" />
            CSV import
          </button>

          {/* Yangi qo'shish */}
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" /> Yangi qo'shish
          </button>
        </div>
      </div>

      {/* Filtrlar */}
      <div className="bg-white border border-gray-200 rounded-2xl p-4 mb-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Tag ID, zot bo'yicha qidirish..."
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
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
            {debouncedSearch && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-100">
                "{debouncedSearch}"
                <button onClick={() => setSearch('')} className="hover:text-blue-900 font-bold ml-0.5">×</button>
              </span>
            )}
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
            <button
              onClick={() => { setSearch(''); setSpecies(''); setGender(''); setStatusFilter(''); }}
              className="ml-auto text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2"
            >
              Barchasini tozalash
            </button>
          </div>
        )}
      </div>

      {/* Xato */}
      {isError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm mb-5">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error instanceof Error ? error.message : 'Xato yuz berdi'}
        </div>
      )}

      {/* Jadval (loading overlay bilan) */}
      <div className={`transition-opacity duration-150 ${isFetching ? 'opacity-70' : 'opacity-100'}`}>
        {animals.length === 0 && !isFetching ? (
          <div className="bg-white border border-gray-200 rounded-2xl p-16 text-center shadow-sm">
            <Users className="w-12 h-12 text-gray-200 mx-auto mb-3" />
            <p className="text-gray-500 font-medium mb-1">
              {debouncedSearch || activeFilters > 0 ? 'Hech narsa topilmadi' : "Hali jonivor qo'shilmagan"}
            </p>
            {!debouncedSearch && activeFilters === 0 && (
              <div className="flex items-center justify-center gap-2 mt-3">
                <button
                  onClick={() => setShowAdd(true)}
                  className="inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700"
                >
                  <Plus className="w-4 h-4" /> Birinchi jonivorni qo'shish
                </button>
                <button
                  onClick={() => setShowImport(true)}
                  className="inline-flex items-center gap-2 border border-gray-200 text-gray-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-gray-50"
                >
                  <FileText className="w-4 h-4" /> CSV dan import
                </button>
              </div>
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
                    <SortHeader field="tag_id"           label="Tag ID"           current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="species"          label="Tur"              current={sortBy} order={sortOrder} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Jins</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Zot</th>
                    <SortHeader field="status"           label="Holat"            current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="total_detections" label="Aniqlash"         current={sortBy} order={sortOrder} onSort={handleSort} />
                    <SortHeader field="last_detected_at" label="Oxirgi ko'rinish" current={sortBy} order={sortOrder} onSort={handleSort} />
                    <th className="px-4 py-3 w-24" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {animals.map(a => (
                    <tr
                      key={a.id}
                      onClick={() => navigate(`/animals/${a.id}`)}
                      className="hover:bg-blue-50/30 cursor-pointer transition-colors group"
                    >
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
                      <td className="px-4 py-3.5 text-sm text-gray-500 whitespace-nowrap">
                        {formatDate(a.last_detected_at)}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={e => { e.stopPropagation(); navigate(`/animals/${a.id}`); }}
                            className="p-1.5 text-blue-600 hover:bg-blue-100 rounded-lg"
                            title="Ko'rish"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); setEditAnimal(a); }}
                            className="p-1.5 text-gray-500 hover:bg-gray-100 rounded-lg"
                            title="Tahrirlash"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleDelete(a); }}
                            className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg"
                            title="O'chirish"
                          >
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
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="p-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const p = totalPages <= 5 ? i : Math.max(0, Math.min(totalPages - 5, page - 2)) + i;
                    return (
                      <button
                        key={p}
                        onClick={() => setPage(p)}
                        className={`w-8 h-8 text-xs rounded-lg border transition-colors ${
                          page === p
                            ? 'bg-blue-600 border-blue-600 text-white font-semibold'
                            : 'border-gray-200 text-gray-600 hover:bg-white'
                        }`}
                      >
                        {p + 1}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="p-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modallar */}
      {showAdd && (
        <AnimalModal
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); handleSaved(); }}
        />
      )}
      {editAnimal && (
        <AnimalModal
          initial={editAnimal}
          onClose={() => setEditAnimal(null)}
          onSaved={() => { setEditAnimal(null); handleSaved(); }}
        />
      )}
      {showImport && (
        <CsvImportModal
          onClose={() => setShowImport(false)}
          onImported={handleSaved}
        />
      )}
    </div>
  );
}