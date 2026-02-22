/**
 * Animals List Page
 * 
 * View all animals with filtering and CRUD operations
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Plus,
  RefreshCw,
  AlertCircle,
  Search,
  Filter,
  Edit2,
  Trash2,
  Eye,
  Upload, Camera } from 'lucide-react';
import config from '../config';
import { apiFetch } from '../utils/apiFetch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const API = config.apiUrl;

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function AnimalBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    inactive: 'bg-gray-100 text-gray-800',
    sold: 'bg-blue-100 text-blue-800',
    deceased: 'bg-red-100 text-red-800',
  };

  return (
    <span
      className={`px-2.5 py-1 rounded-full text-xs font-medium capitalize ${
        colors[status] || colors.active
      }`}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Add/Edit Modal
// ---------------------------------------------------------------------------

interface AnimalFormData {
  tag_id: string;
  species: string;
  gender: string;
  acquisition_date: string;
  breed: string;
  notes: string;
  photo?: File | null;
}

function AnimalModal({
  initial,
  onClose,
  onSaved,
}: {
  initial?: Animal;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = Boolean(initial);

  const [form, setForm] = useState<AnimalFormData>({
    tag_id: initial?.tag_id ?? '',
    species: initial?.species ?? 'cattle',
    gender: initial?.gender ?? 'male',
    acquisition_date: initial?.acquisition_date
      ? initial.acquisition_date.split('T')[0]
      : new Date().toISOString().split('T')[0],
    breed: initial?.breed ?? '',
    notes: initial?.notes ?? '',
    photo: null,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [photoPreview, setPhotoPreview] = useState<string>('');
  const fileRef = useRef<HTMLInputElement>(null);

  const set =
    (key: keyof AnimalFormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((p) => ({
        ...p,
        [key]: key === 'tag_id' ? e.target.value.toUpperCase() : e.target.value,
      }));

  async function handleSubmit() {
    if (!form.tag_id.trim()) {
      setError('Tag ID kiritilishi shart');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const body = {
        ...form,
        acquisition_date: `${form.acquisition_date}T00:00:00`,
        breed: form.breed || undefined,
        notes: form.notes || undefined,
      };
      if (isEdit) {
        await apiFetch(`/api/v1/animals/${initial!.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
      } else {
        const created = await apiFetch<{ id: number }>('/api/v1/animals/', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        // Rasm yuklash (ixtiyoriy)
        if (form.photo && created?.id) {
          try {
            const fd = new FormData();
            fd.append('photo', form.photo);
            const token = localStorage.getItem('tv_access_token');
            await fetch(`${config.apiUrl}/api/v1/identification/register/${created.id}`, {
              method: 'POST',
              headers: token ? { Authorization: `Bearer ${token}` } : {},
              body: fd,
            });
          } catch { /* rasm yuklanmasa ham jonivor saqlanadi */ }
        }
      }
      onSaved();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            {isEdit ? 'Jonivorni tahrirlash' : 'Yangi jonivor qo\'shish'}
          </h2>
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tag ID *
            </label>
            <input
              type="text"
              value={form.tag_id}
              onChange={set('tag_id')}
              placeholder="ANGUS-001"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Tur</label>
              <select
                value={form.species}
                onChange={set('species')}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="cattle">Cattle (Qoramol)</option>
                <option value="sheep">Sheep (Qo'y)</option>
                <option value="goat">Goat (Echki)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Jins</label>
              <select
                value={form.gender}
                onChange={set('gender')}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="male">Male (Erkak)</option>
                <option value="female">Female (Urg'ochi)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kiritilgan sana
            </label>
            <input
              type="date"
              value={form.acquisition_date}
              onChange={set('acquisition_date')}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Zot (ixtiyoriy)
            </label>
            <input
              type="text"
              value={form.breed}
              onChange={set('breed')}
              placeholder="Angus, Hereford..."
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Izohlar (ixtiyoriy)
            </label>
            <textarea
              value={form.notes}
              onChange={set('notes')}
              rows={3}
              placeholder="Qo'shimcha ma'lumotlar..."
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          {/* Rasm yuklash */}
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Identifikatsiya rasmi (ixtiyoriy)
              </label>
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
              >
                {photoPreview ? (
                  <img src={photoPreview} alt="preview"
                    className="max-h-32 mx-auto rounded-lg object-cover" />
                ) : (
                  <div className="text-gray-400">
                    <Upload className="w-8 h-8 mx-auto mb-2" />
                    <p className="text-sm">Rasm yuklash uchun bosing</p>
                    <p className="text-xs mt-1">JPG, PNG</p>
                  </div>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    setForm(p => ({ ...p, photo: f }));
                    const r = new FileReader();
                    r.onload = ev => setPhotoPreview(ev.target?.result as string);
                    r.readAsDataURL(f);
                  }}
                />
              </div>
              {form.photo && (
                <p className="text-xs text-green-600 mt-1">✅ {form.photo.name}</p>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t border-gray-200 flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Bekor qilish
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
          >
            {loading ? 'Saqlanmoqda...' : isEdit ? 'Saqlash' : "Qo'shish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AnimalsPage() {
  const navigate = useNavigate();

  const [animals, setAnimals] = useState<Animal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [photoPreview, setPhotoPreview] = useState<string>('');
  const fileRef = useRef<HTMLInputElement>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const [showAddModal, setShowAddModal] = useState(false);
  const [editAnimal, setEditAnimal] = useState<Animal | null>(null);
  const [deleteAnimal, setDeleteAnimal] = useState<Animal | null>(null);

  // ---------------------------------------------------------------------------
  // Load Data
  // ---------------------------------------------------------------------------

  useEffect(() => {
    loadAnimals();
  }, [searchQuery, filterStatus]);

  async function loadAnimals() {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        limit: '100',
        skip: '0',
      });
      if (searchQuery) params.set('search', searchQuery);
      if (filterStatus !== 'all') params.set('status', filterStatus);

      const data = await apiFetch<AnimalListResponse>(
        `/api/v1/animals/?${params}`
      );
      setAnimals(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xato');
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Delete Handler
  // ---------------------------------------------------------------------------

  async function handleDelete(animal: Animal) {
    const confirmed = window.confirm(
      `${animal.tag_id} ni o'chirishga ishonchingiz komilmi?`
    );
    if (!confirmed) return;

    try {
      await apiFetch(`/api/v1/animals/${animal.id}`, { method: 'DELETE' });
      loadAnimals();
      setDeleteAnimal(null);
    } catch (err) {
      alert('O\'chirish xatolik: ' + (err instanceof Error ? err.message : ''));
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Jonivorlar</h1>
          <p className="text-gray-600 mt-1">Jami {total} ta jonivor ro'yxatda</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadAnimals}
            disabled={loading}
            className="p-2.5 text-gray-600 hover:text-gray-900 hover:bg-white border border-gray-300 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 bg-green-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-green-700 transition-colors shadow-sm"
          >
            <Plus className="w-5 h-5" />
            Yangi qo'shish
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tag ID yoki zot bo'yicha qidirish..."
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 appearance-none"
            >
              <option value="all">Barcha holatlar</option>
              <option value="active">Faol</option>
              <option value="inactive">Nofaol</option>
              <option value="sold">Sotilgan</option>
              <option value="deceased">Vafot etgan</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && animals.length === 0 ? (
        <div className="text-center py-16 text-gray-400">Yuklanmoqda...</div>
      ) : animals.length === 0 ? (
        <div className="text-center py-16">
          <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 text-lg mb-2">
            {searchQuery || filterStatus !== 'all'
              ? 'Hech narsa topilmadi'
              : 'Hali jonivor qo\'shilmagan'}
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-4 inline-flex items-center gap-2 bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700"
          >
            <Plus className="w-5 h-5" />
            Birinchi jonivorni qo'shish
          </button>
        </div>
      ) : (
        /* Table */
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {['Tag ID', 'Tur', 'Jins', 'Zot', 'Holat', 'Aniqlash', ''].map((h) => (
                  <th
                    key={h}
                    className="text-left px-6 py-4 text-xs font-semibold text-gray-600 uppercase tracking-wider"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {animals.map((a) => (
                <tr
                  key={a.id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer group"
                  onClick={() => navigate(`/animals/${a.id}`)}
                >
                  <td className="px-6 py-4 font-mono font-semibold text-gray-900">
                    {a.tag_id}
                  </td>
                  <td className="px-6 py-4 text-gray-600 capitalize">{a.species}</td>
                  <td className="px-6 py-4 text-gray-600 capitalize">{a.gender}</td>
                  <td className="px-6 py-4 text-gray-600">{a.breed || '—'}</td>
                  <td className="px-6 py-4">
                    <AnimalBadge status={a.status} />
                  </td>
                  <td className="px-6 py-4 text-gray-700 font-medium">
                    {a.total_detections}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/animals/${a.id}`);
                        }}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Ko'rish"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditAnimal(a);
                        }}
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Tahrirlash"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(a);
                        }}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="O'chirish"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AnimalModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false);
            loadAnimals();
          }}
        />
      )}

      {editAnimal && (
        <AnimalModal
          initial={editAnimal}
          onClose={() => setEditAnimal(null)}
          onSaved={() => {
            setEditAnimal(null);
            loadAnimals();
          }}
        />
      )}
    </div>
  );
}