/**
 * FarmsPage — Multi-farm boshqaruv sahifasi
 *
 * Xususiyatlar:
 *   - Fermalar ro'yxati (karta ko'rinishida)
 *   - Yangi ferma qo'shish (ADMIN)
 *   - Ferma tahrirlash (ADMIN)
 *   - Ferma arxivlash (ADMIN)
 *   - Joriy ferma almashtirish (barcha foydalanuvchilar)
 *   - Har bir fermada jonivorlar statistikasi
 */

import { useState } from 'react';
import {
  MapPin, Phone, User, Building2, Plus, Edit2,
  Archive, CheckCircle, ChevronRight, AlertTriangle,
  RefreshCw, Clock,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { useAuth } from '../context/AuthContext';

// =============================================================================
// TYPES
// =============================================================================

interface FarmData {
  id:                  number;
  name:                string;
  description:         string | null;
  location:            string | null;
  owner_name:          string | null;
  phone:               string | null;
  is_active:           boolean;
  timezone_offset:     number;
  animal_count:        number;
  active_animal_count: number;
  created_at:          string;
}

interface FarmListResponse {
  items: FarmData[];
  total: number;
}

const EMPTY_FORM = {
  name:             '',
  description:      '',
  location:         '',
  owner_name:       '',
  phone:            '',
  timezone_offset:  5,
};

// =============================================================================
// HELPERS
// =============================================================================

const FARM_STORAGE_KEY = 'tv_current_farm';

function getCurrentFarmId(): number | null {
  try {
    const raw = localStorage.getItem(FARM_STORAGE_KEY);
    return raw ? parseInt(raw, 10) : null;
  } catch { return null; }
}

function setCurrentFarmId(id: number): void {
  try { localStorage.setItem(FARM_STORAGE_KEY, String(id)); } catch { /* ignore */ }
}

// =============================================================================
// PAGE
// =============================================================================

export default function FarmsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isAdmin = user?.role === 'admin';

  const [currentFarmId, setCurrentFarm] = useState<number | null>(getCurrentFarmId);
  const [showForm,   setShowForm]   = useState(false);
  const [editFarm,   setEditFarm]   = useState<FarmData | null>(null);
  const [form,       setForm]       = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // ─── Queries ──────────────────────────────────────────────────────────────

  const { data, isLoading } = useQuery({
    queryKey: ['farms'],
    queryFn:  () => apiFetch<FarmListResponse>('/api/v1/farms?limit=100'),
  });

  const farms = data?.items ?? [];

  // ─── Mutations ────────────────────────────────────────────────────────────

  const createMut = useMutation({
    mutationFn: (body: typeof EMPTY_FORM) =>
      apiFetch<FarmData>('/api/v1/farms', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['farms'] }); closeForm(); },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<typeof EMPTY_FORM> }) =>
      apiFetch<FarmData>(`/api/v1/farms/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['farms'] }); closeForm(); },
  });

  const switchMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ farm_id: number; farm_name: string; message: string }>(`/api/v1/farms/${id}/switch`, { method: 'POST' }),
    onSuccess: (res) => {
      setCurrentFarmId(res.farm_id);
      setCurrentFarm(res.farm_id);
      qc.invalidateQueries({ queryKey: ['farms'] });
    },
  });

  const deactivateMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch<FarmData>(`/api/v1/farms/${id}/deactivate`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['farms'] }),
  });

  // ─── Form helpers ─────────────────────────────────────────────────────────

  function openCreate() {
    setEditFarm(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
    setShowForm(true);
  }

  function openEdit(farm: FarmData) {
    setEditFarm(farm);
    setForm({
      name:            farm.name,
      description:     farm.description ?? '',
      location:        farm.location    ?? '',
      owner_name:      farm.owner_name  ?? '',
      phone:           farm.phone       ?? '',
      timezone_offset: farm.timezone_offset,
    });
    setFormErrors({});
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditFarm(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!form.name.trim() || form.name.length < 2) errs.name = 'Ferma nomi kamida 2 ta harf';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleSubmit() {
    if (!validate()) return;
    const body = {
      name:            form.name.trim(),
      description:     form.description.trim() || null,
      location:        form.location.trim()    || null,
      owner_name:      form.owner_name.trim()  || null,
      phone:           form.phone.trim()       || null,
      timezone_offset: form.timezone_offset,
    } as typeof EMPTY_FORM;

    if (editFarm) {
      updateMut.mutate({ id: editFarm.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  // ─── Styles ───────────────────────────────────────────────────────────────

  const inp: React.CSSProperties = {
    width: '100%', padding: '9px 12px', borderRadius: 8,
    border: '1px solid #E4E7ED', fontSize: 13,
    fontFamily: "'Outfit',sans-serif", outline: 'none',
    background: '#fff', color: '#0D1117', boxSizing: 'border-box',
  };

  const label: React.CSSProperties = {
    fontSize: 12, fontWeight: 600, color: '#374151',
    marginBottom: 5, display: 'block',
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: '24px 20px', maxWidth: 1100, margin: '0 auto' }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
            🏡 Fermalar
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280', fontFamily: "'Outfit',sans-serif" }}>
            {data?.total ?? 0} ta ferma — ferma tanlash uchun bosing
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={openCreate}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '9px 18px', borderRadius: 9,
              background: '#1E3EB4', color: '#fff', border: 'none',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
              fontFamily: "'Outfit',sans-serif",
            }}
          >
            <Plus size={14}/> Yangi ferma
          </button>
        )}
      </div>

      {/* ── Loading ────────────────────────────────────────────────────────── */}
      {isLoading && (
        <div style={{ display: 'grid', placeItems: 'center', height: 200 }}>
          <div style={{ width: 24, height: 24, border: '2px solid #E4E7ED', borderTopColor: '#1E3EB4', borderRadius: '50%', animation: 'tv-spin .65s linear infinite' }}/>
        </div>
      )}

      {/* ── Farm Cards ─────────────────────────────────────────────────────── */}
      {!isLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {farms.map(farm => {
            const isCurrent = farm.id === currentFarmId;
            const isSwitching = switchMut.isPending && switchMut.variables === farm.id;

            return (
              <div
                key={farm.id}
                style={{
                  background: '#fff',
                  border: `2px solid ${isCurrent ? '#1E3EB4' : '#E4E7ED'}`,
                  borderRadius: 14,
                  padding: 20,
                  position: 'relative',
                  opacity: farm.is_active ? 1 : 0.6,
                  transition: 'border-color .2s, box-shadow .2s',
                  boxShadow: isCurrent ? '0 0 0 4px rgba(30,62,180,0.08)' : 'none',
                }}
              >
                {/* Joriy ferma badge */}
                {isCurrent && (
                  <div style={{
                    position: 'absolute', top: 14, right: 14,
                    display: 'flex', alignItems: 'center', gap: 4,
                    background: '#EEF2FF', color: '#1E3EB4',
                    padding: '3px 9px', borderRadius: 20,
                    fontSize: 11, fontWeight: 700, fontFamily: "'JetBrains Mono',monospace",
                  }}>
                    <CheckCircle size={11}/> JORIY
                  </div>
                )}

                {/* Arxiv badge */}
                {!farm.is_active && (
                  <div style={{
                    position: 'absolute', top: 14, right: 14,
                    background: '#F3F4F6', color: '#9CA3AF',
                    padding: '3px 9px', borderRadius: 20,
                    fontSize: 11, fontWeight: 600, fontFamily: "'Outfit',sans-serif",
                  }}>
                    Arxiv
                  </div>
                )}

                {/* Ferma nomi */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, paddingRight: isCurrent ? 70 : 0 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 10,
                    background: isCurrent ? '#EEF2FF' : '#F7F8FA',
                    display: 'grid', placeItems: 'center', flexShrink: 0,
                  }}>
                    <Building2 size={18} color={isCurrent ? '#1E3EB4' : '#6B7280'}/>
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
                      {farm.name}
                    </h3>
                    {farm.description && (
                      <p style={{ margin: '2px 0 0', fontSize: 12, color: '#6B7280', fontFamily: "'Outfit',sans-serif" }}>
                        {farm.description.slice(0, 60)}{farm.description.length > 60 ? '…' : ''}
                      </p>
                    )}
                  </div>
                </div>

                {/* Meta info */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
                  {farm.location && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
                      <MapPin size={12} color="#9CA3AF"/><span>{farm.location}</span>
                    </div>
                  )}
                  {farm.owner_name && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
                      <User size={12} color="#9CA3AF"/><span>{farm.owner_name}</span>
                    </div>
                  )}
                  {farm.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
                      <Phone size={12} color="#9CA3AF"/><span>{farm.phone}</span>
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#6B7280' }}>
                    <Clock size={12} color="#9CA3AF"/>
                    <span>UTC+{farm.timezone_offset} · {new Date(farm.created_at).toLocaleDateString('uz-UZ')}</span>
                  </div>
                </div>

                {/* Statistika */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr',
                  gap: 8, marginBottom: 16,
                }}>
                  <div style={{ background: '#F7F8FA', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: '#0D1117', fontFamily: "'JetBrains Mono',monospace" }}>
                      {farm.animal_count}
                    </div>
                    <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>Jonivorlar</div>
                  </div>
                  <div style={{ background: farm.active_animal_count > 0 ? '#ECFDF5' : '#F7F8FA', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: farm.active_animal_count > 0 ? '#059669' : '#9CA3AF', fontFamily: "'JetBrains Mono',monospace" }}>
                      {farm.active_animal_count}
                    </div>
                    <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>Faol</div>
                  </div>
                </div>

                {/* Action buttons */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {/* Switch button */}
                  {farm.is_active && !isCurrent && (
                    <button
                      onClick={() => switchMut.mutate(farm.id)}
                      disabled={switchMut.isPending}
                      style={{
                        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                        padding: '9px 0', borderRadius: 8,
                        background: '#1E3EB4', color: '#fff', border: 'none',
                        fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        fontFamily: "'Outfit',sans-serif",
                        opacity: isSwitching ? 0.7 : 1,
                      }}
                    >
                      {isSwitching ? <RefreshCw size={13} style={{ animation: 'tv-spin .65s linear infinite' }}/> : <ChevronRight size={13}/>}
                      {isSwitching ? 'O\'tilmoqda…' : 'Shu fermaga o\'t'}
                    </button>
                  )}

                  {isCurrent && (
                    <div style={{
                      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                      padding: '9px 0', borderRadius: 8,
                      background: '#EEF2FF', color: '#1E3EB4',
                      fontSize: 13, fontWeight: 600,
                      fontFamily: "'Outfit',sans-serif",
                    }}>
                      <CheckCircle size={13}/> Joriy ferma
                    </div>
                  )}

                  {/* Edit */}
                  {isAdmin && (
                    <button
                      onClick={() => openEdit(farm)}
                      style={{
                        width: 36, height: 36, borderRadius: 8, display: 'grid', placeItems: 'center',
                        background: '#F7F8FA', border: '1px solid #E4E7ED', cursor: 'pointer',
                        flexShrink: 0,
                      }}
                    >
                      <Edit2 size={13} color="#6B7280"/>
                    </button>
                  )}

                  {/* Deactivate */}
                  {isAdmin && farm.is_active && !isCurrent && (
                    <button
                      onClick={() => {
                        if (confirm(`"${farm.name}" fermasini arxivlaysizmi?`))
                          deactivateMut.mutate(farm.id);
                      }}
                      style={{
                        width: 36, height: 36, borderRadius: 8, display: 'grid', placeItems: 'center',
                        background: '#FEF2F2', border: '1px solid #FECACA', cursor: 'pointer',
                        flexShrink: 0,
                      }}
                    >
                      <Archive size={13} color="#DC2626"/>
                    </button>
                  )}
                </div>
              </div>
            );
          })}

          {/* Empty state */}
          {farms.length === 0 && !isLoading && (
            <div style={{
              gridColumn: '1 / -1', textAlign: 'center', padding: '60px 20px',
              background: '#fff', borderRadius: 14, border: '1px solid #E4E7ED',
            }}>
              <Building2 size={32} color="#D1D5DB" style={{ margin: '0 auto 12px' }}/>
              <p style={{ margin: 0, fontSize: 14, color: '#9CA3AF', fontFamily: "'Outfit',sans-serif" }}>
                Hech qanday ferma yo'q. Yangi ferma qo'shing.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Switch error ───────────────────────────────────────────────────── */}
      {switchMut.isError && (
        <div style={{
          marginTop: 16, padding: '12px 16px', borderRadius: 10,
          background: '#FEF2F2', border: '1px solid #FECACA',
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 13, color: '#DC2626', fontFamily: "'Outfit',sans-serif",
        }}>
          <AlertTriangle size={14}/> Ferma almashtirishda xato. Qayta urinib ko'ring.
        </div>
      )}

      {/* ── Modal Form ─────────────────────────────────────────────────────── */}
      {showForm && (
        <>
          <div
            onClick={closeForm}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 100, backdropFilter: 'blur(2px)' }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: '#fff', borderRadius: 16, padding: 28,
            width: '100%', maxWidth: 480, zIndex: 101,
            boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 17, fontWeight: 800, color: '#0D1117', fontFamily: "'Outfit',sans-serif" }}>
              {editFarm ? '✏️ Ferma tahrirlash' : '🏡 Yangi ferma qo\'shish'}
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Nom */}
              <div>
                <label style={label}>Ferma nomi *</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Masalan: Toshkent Ferma #1"
                  style={{ ...inp, borderColor: formErrors.name ? '#EF4444' : '#E4E7ED' }}
                />
                {formErrors.name && <p style={{ margin: '4px 0 0', fontSize: 11, color: '#EF4444' }}>{formErrors.name}</p>}
              </div>

              {/* Tavsif */}
              <div>
                <label style={label}>Tavsif</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Ferma haqida qo'shimcha ma'lumot..."
                  rows={2}
                  style={{ ...inp, resize: 'vertical' }}
                />
              </div>

              {/* Manzil */}
              <div>
                <label style={label}>Manzil</label>
                <input
                  value={form.location}
                  onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
                  placeholder="Shahar, tuman, ko'cha"
                  style={inp}
                />
              </div>

              {/* 2 column */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={label}>Ferma egasi</label>
                  <input
                    value={form.owner_name}
                    onChange={e => setForm(f => ({ ...f, owner_name: e.target.value }))}
                    placeholder="Ismi sharifi"
                    style={inp}
                  />
                </div>
                <div>
                  <label style={label}>Telefon</label>
                  <input
                    value={form.phone}
                    onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                    placeholder="+998 __ ___ __ __"
                    style={inp}
                  />
                </div>
              </div>

              {/* Timezone */}
              <div>
                <label style={label}>Vaqt zonasi (UTC offset)</label>
                <select
                  value={form.timezone_offset}
                  onChange={e => setForm(f => ({ ...f, timezone_offset: parseInt(e.target.value) }))}
                  style={{ ...inp, cursor: 'pointer' }}
                >
                  {[-12,-11,-10,-9,-8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,9,10,11,12].map(o => (
                    <option key={o} value={o}>UTC{o >= 0 ? '+' : ''}{o} {o === 5 ? '(Toshkent)' : o === 3 ? '(Moskva)' : o === 0 ? '(London)' : ''}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Error */}
            {(createMut.isError || updateMut.isError) && (
              <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8, background: '#FEF2F2', color: '#DC2626', fontSize: 13 }}>
                Xato yuz berdi. Qayta urinib ko'ring.
              </div>
            )}

            {/* Buttons */}
            <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
              <button
                onClick={closeForm}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 9,
                  background: '#F7F8FA', border: '1px solid #E4E7ED',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  color: '#374151', fontFamily: "'Outfit',sans-serif",
                }}
              >
                Bekor qilish
              </button>
              <button
                onClick={handleSubmit}
                disabled={createMut.isPending || updateMut.isPending}
                style={{
                  flex: 2, padding: '10px 0', borderRadius: 9,
                  background: '#1E3EB4', color: '#fff', border: 'none',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  fontFamily: "'Outfit',sans-serif",
                  opacity: (createMut.isPending || updateMut.isPending) ? 0.7 : 1,
                }}
              >
                {(createMut.isPending || updateMut.isPending) ? 'Saqlanmoqda…' : (editFarm ? 'Saqlash' : 'Qo\'shish')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}