/**
 * Taurus Vision — Nasl va Zotchilik Boshqaruvi (Sprint 25-26)
 *
 * TABLAR:
 *   1. Joriy Holat  — statistika kartalar + aktiv homiladorliklar progress
 *   2. Barcha Yozuvlar — filtr + jadval + CRUD
 *   3. Shajara       — animal tanlab, avlodlar daraxti
 *   4. Tavsiyalar    — AI scoring bilan juft tavsiyalari
 *
 * MODALLAR:
 *   - Yangi nasl yozuvi (create)
 *   - Homiladorlikni tasdiqlash
 *   - Tug'ilishni qayd etish
 *   - Detail ko'rish
 */

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Baby, Heart, Calendar, Search, Plus, RefreshCw,
  ChevronDown, ChevronRight, X, CheckCircle, AlertTriangle,
  TrendingUp, Activity, Clock, Filter, Star,
  GitBranch, Zap, Info, Edit, Trash2, Eye,
  ArrowRight, Target, Award, BarChart2,
} from 'lucide-react';
import { apiFetch } from '../utils/apiFetch';

// ─── Types ───────────────────────────────────────────────────────────────────

interface AnimalBrief {
  id: number; tag_id: string; species: string;
  breed: string | null; gender: string; status: string;
}

interface OffspringResp {
  id: number; birth_order: number; gender: string | null;
  birth_weight_kg: number | null; outcome: string;
  animal_id: number | null; animal_tag_id: string | null; notes: string | null;
}

interface BreedingRecord {
  id: number; farm_id: number | null;
  mother_id: number; father_id: number | null;
  external_sire_tag: string | null; external_sire_breed: string | null;
  mating_date: string; mating_method: string;
  status: string; gestation_days: number;
  expected_birth_date: string | null;
  pregnancy_confirmed_at: string | null;
  pregnancy_check_method: string | null;
  actual_birth_date: string | null;
  live_offspring_count: number; stillborn_count: number;
  birth_complications: string | null;
  abort_date: string | null; abort_reason: string | null;
  veterinarian: string | null; notes: string | null;
  pregnancy_progress_pct: number | null;
  days_until_birth: number | null;
  is_overdue: boolean; total_offspring: number; sire_label: string;
  mother: AnimalBrief | null; father: AnimalBrief | null;
  offspring: OffspringResp[];
  created_at: string;
}

interface BreedingList { total: number; page: number; size: number; pages: number; items: BreedingRecord[]; }

interface Stats {
  total_records: number; active_pregnancies: number; planned: number;
  birthed_this_year: number; failed_this_year: number; aborted_this_year: number;
  total_live_offspring: number; total_stillborn: number;
  avg_litter_size: number; stillbirth_rate_pct: number;
  overdue_count: number; due_next_7_days: number; due_next_30_days: number;
  by_mating_method: Record<string, number>;
  monthly_births: { month: string; count: number }[];
}

interface GenealogyNode {
  animal_id: number | null; tag_id: string | null; species: string | null;
  breed: string | null; gender: string | null; birth_date: string | null;
  is_external: boolean; external_label: string | null;
  mother: GenealogyNode | null; father: GenealogyNode | null; generation: number;
}

interface Recommendation {
  mother: AnimalBrief; sire_animal: AnimalBrief | null; sire_external_label: string | null;
  total_score: number; genetic_diversity_score: number; adi_compatibility_score: number;
  weight_compatibility_score: number; breed_compatibility_score: number;
  recommendation_reason: string; warnings: string[];
  estimated_gestation_days: number;
  expected_birth_range_start: string; expected_birth_range_end: string;
}

interface RecommendationList {
  total_females_eligible: number; total_sires_available: number;
  recommendations: Recommendation[]; generated_at: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  planned: 'Rejalashtirilgan', confirmed_pregnant: 'Homilador',
  birthed: 'Tug\'ildi', failed: 'Muvaffaqiyatsiz', aborted: 'Abort',
};
const STATUS_COLOR: Record<string, string> = {
  planned: '#6B7280', confirmed_pregnant: '#10B981',
  birthed: '#3B82F6', failed: '#EF4444', aborted: '#F59E0B',
};
const METHOD_LABEL: Record<string, string> = {
  natural: 'Tabiiy', artificial_insemination: 'Sun\'iy', embryo_transfer: 'Embrion',
};
const SPECIES_ICON: Record<string, string> = {
  cattle: '🐄', sheep: '🐑', goat: '🐐', horse: '🐴', other: '🐾',
};

function fmtDate(d: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('uz-UZ', { day: '2-digit', month: 'short', year: 'numeric' });
}

function scoreColor(s: number) {
  if (s >= 80) return '#10B981';
  if (s >= 60) return '#F59E0B';
  return '#EF4444';
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color, icon: Icon }:
  { label: string; value: number | string; sub?: string; color: string; icon: any }) {
  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 12, padding: '16px 20px', flex: 1, minWidth: 150,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{ width: 34, height: 34, borderRadius: 8, background: color + '18',
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={16} color={color} />
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function PregnancyCard({ rec }: { rec: BreedingRecord }) {
  const pct = rec.pregnancy_progress_pct ?? 0;
  const left = rec.days_until_birth;
  const overdue = rec.is_overdue;
  const barColor = overdue ? '#EF4444' : (pct > 80 ? '#F59E0B' : '#10B981');

  return (
    <div style={{
      background: 'var(--card)', border: `1px solid ${overdue ? '#EF444430' : 'var(--border)'}`,
      borderRadius: 10, padding: 16, marginBottom: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{SPECIES_ICON[rec.mother?.species || 'other']}</span>
          <div>
            <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 14 }}>
              {rec.mother?.tag_id ?? `#${rec.mother_id}`}
            </span>
            {rec.mother?.breed && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>
                {rec.mother.breed}
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {overdue && (
            <span style={{
              fontSize: 10, padding: '2px 7px', borderRadius: 12,
              background: '#EF444418', color: '#EF4444', fontWeight: 600,
            }}>MUDDATI O'TDI</span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {rec.gestation_days} kun gestatsiya
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ background: 'var(--bg)', borderRadius: 99, height: 8, marginBottom: 6 }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', borderRadius: 99,
          background: barColor, transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11,
        color: 'var(--text-muted)' }}>
        <span>{pct.toFixed(0)}% tugallangan</span>
        <span>
          {overdue
            ? `${Math.abs(left ?? 0)} kun kechikdi`
            : left !== null ? `${left} kun qoldi` : '—'
          }
        </span>
      </div>

      <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
        <span>🗓 Juftlashish: {fmtDate(rec.mating_date)}</span>
        <span>🎯 Kutilgan: {fmtDate(rec.expected_birth_date)}</span>
        <span>♂ {rec.sire_label}</span>
      </div>
    </div>
  );
}

function GenealogyTree({ node, depth = 0 }: { node: GenealogyNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.mother || node.father;

  const nodeColor = node.is_external ? '#F59E0B' :
    (node.gender === 'female' ? '#EC4899' : '#3B82F6');

  return (
    <div style={{ marginLeft: depth > 0 ? 28 : 0, marginTop: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {depth > 0 && (
          <div style={{ width: 20, height: 1, background: 'var(--border)' }} />
        )}
        {hasChildren && (
          <button onClick={() => setExpanded(!expanded)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--text-muted)' }}>
            {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </button>
        )}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
          background: nodeColor + '12', border: `1px solid ${nodeColor}30`,
          borderRadius: 8, cursor: 'default',
        }}>
          <span style={{ fontSize: 14 }}>
            {node.gender === 'female' ? '♀' : node.gender === 'male' ? '♂' : '?'}
          </span>
          <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
            {node.tag_id ?? node.external_label ?? 'Noma\'lum'}
          </span>
          {node.species && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {SPECIES_ICON[node.species]} {node.breed || node.species}
            </span>
          )}
          {node.is_external && (
            <span style={{
              fontSize: 9, padding: '1px 5px', borderRadius: 4,
              background: '#F59E0B20', color: '#F59E0B', fontWeight: 600,
            }}>TASHQI</span>
          )}
        </div>
      </div>

      {expanded && hasChildren && (
        <div style={{ borderLeft: '1px dashed var(--border)', marginLeft: 24, paddingLeft: 4 }}>
          {node.mother && <GenealogyTree node={node.mother} depth={depth + 1} />}
          {node.father && <GenealogyTree node={node.father} depth={depth + 1} />}
        </div>
      )}
    </div>
  );
}

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = (value / max) * 100;
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11,
        color: 'var(--text-muted)', marginBottom: 2 }}>
        <span>{label}</span>
        <span>{value}/{max}</span>
      </div>
      <div style={{ background: 'var(--bg)', borderRadius: 4, height: 5 }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4,
          background: scoreColor((value / max) * 100) }} />
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function BreedingPage() {
  const qc = useQueryClient();

  const [tab, setTab] = useState<'overview' | 'records' | 'genealogy' | 'recommendations'>('overview');
  const [showCreate, setShowCreate] = useState(false);
  const [showConfirm, setShowConfirm] = useState<BreedingRecord | null>(null);
  const [showBirth, setShowBirth] = useState<BreedingRecord | null>(null);
  const [showDetail, setShowDetail] = useState<BreedingRecord | null>(null);
  const [genealogyAnimalId, setGenealogyAnimalId] = useState('');
  const [genealogyGen, setGenealogyGen] = useState(3);

  // Filters
  const [statusFilter, setStatusFilter]   = useState('');
  const [speciesFilter, setSpeciesFilter] = useState('');
  const [page, setPage] = useState(1);

  // Create form
  const [cForm, setCForm] = useState({
    mother_id: '', father_id: '', external_sire_tag: '', external_sire_breed: '',
    mating_date: new Date().toISOString().split('T')[0],
    mating_method: 'natural', use_external: false,
    veterinarian: '', notes: '',
  });

  // Confirm form
  const [confirmForm, setConfirmForm] = useState({
    check_method: 'ultrasound', check_notes: '',
    confirmed_at: new Date().toISOString().split('T')[0],
  });

  // Birth form
  const [birthForm, setBirthForm] = useState({
    actual_birth_date: new Date().toISOString().split('T')[0],
    birth_complications: '', notes: '',
    offspring: [{ birth_order: 1, gender: 'unknown', birth_weight_kg: '', outcome: 'alive', notes: '' }],
  });

  // ── Queries ──
  const { data: stats, isLoading: statsLoading } = useQuery<Stats>({
    queryKey: ['breeding-stats'],
    queryFn: () => apiFetch('/breeding/stats'),
    refetchInterval: 60_000,
  });

  const { data: activePregancies, isLoading: pregLoading } = useQuery<BreedingRecord[]>({
    queryKey: ['breeding-active'],
    queryFn: () => apiFetch('/breeding/active-pregnancies'),
    enabled: tab === 'overview',
    refetchInterval: 30_000,
  });

  const { data: records, isLoading: recLoading } = useQuery<BreedingList>({
    queryKey: ['breeding-records', statusFilter, speciesFilter, page],
    queryFn: () => apiFetch(
      `/breeding/records?page=${page}&size=15` +
      (statusFilter ? `&status=${statusFilter}` : '') +
      (speciesFilter ? `&species=${speciesFilter}` : '')
    ),
    enabled: tab === 'records',
  });

  const { data: genealogy, isLoading: geneLoading, refetch: refetchGene } = useQuery<GenealogyNode>({
    queryKey: ['breeding-genealogy', genealogyAnimalId, genealogyGen],
    queryFn: () => apiFetch(`/breeding/genealogy/${genealogyAnimalId}?max_generations=${genealogyGen}`),
    enabled: false,
  });

  const { data: recommendations, isLoading: recmLoading } = useQuery<RecommendationList>({
    queryKey: ['breeding-recommendations', speciesFilter],
    queryFn: () => apiFetch(
      `/breeding/recommendations?top_n=20` +
      (speciesFilter ? `&species=${speciesFilter}` : '')
    ),
    enabled: tab === 'recommendations',
  });

  const { data: females } = useQuery<AnimalBrief[]>({
    queryKey: ['breeding-females'],
    queryFn: () => apiFetch('/breeding/available-females'),
    enabled: showCreate,
  });

  const { data: males } = useQuery<AnimalBrief[]>({
    queryKey: ['breeding-males'],
    queryFn: () => apiFetch('/breeding/available-males'),
    enabled: showCreate,
  });

  // ── Mutations ──
  const createMut = useMutation({
    mutationFn: (body: object) => apiFetch('/breeding/records', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['breeding'] }); setShowCreate(false); },
  });

  const confirmMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: object }) =>
      apiFetch(`/breeding/records/${id}/confirm-pregnancy`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['breeding'] }); setShowConfirm(null); },
  });

  const birthMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: object }) =>
      apiFetch(`/breeding/records/${id}/record-birth`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['breeding'] }); setShowBirth(null); },
  });

  const failMut = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/breeding/records/${id}/mark-failed`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['breeding'] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiFetch(`/breeding/records/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['breeding'] }),
  });

  // ── Handlers ──
  const inp: React.CSSProperties = {
    width: '100%', padding: '8px 10px', borderRadius: 7,
    border: '1px solid var(--border)', background: 'var(--bg)',
    color: 'var(--text-primary)', fontSize: 13, boxSizing: 'border-box',
    outline: 'none',
  };
  const sel: React.CSSProperties = { ...inp };
  const btn = (color = '#10B981'): React.CSSProperties => ({
    padding: '8px 16px', borderRadius: 7, border: 'none',
    background: color, color: '#fff', fontWeight: 600, fontSize: 13,
    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
  });
  const ghostBtn: React.CSSProperties = {
    padding: '8px 14px', borderRadius: 7, border: '1px solid var(--border)',
    background: 'none', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 13,
    cursor: 'pointer',
  };

  function handleCreate() {
    const body: Record<string, any> = {
      mother_id: parseInt(cForm.mother_id),
      mating_date: cForm.mating_date,
      mating_method: cForm.mating_method,
      veterinarian: cForm.veterinarian || undefined,
      notes: cForm.notes || undefined,
    };
    if (cForm.use_external) {
      body.external_sire_tag = cForm.external_sire_tag;
      body.external_sire_breed = cForm.external_sire_breed || undefined;
    } else {
      body.father_id = parseInt(cForm.father_id);
    }
    createMut.mutate(body);
  }

  function handleConfirm() {
    if (!showConfirm) return;
    confirmMut.mutate({ id: showConfirm.id, body: confirmForm });
  }

  function handleBirth() {
    if (!showBirth) return;
    const body = {
      actual_birth_date: birthForm.actual_birth_date,
      birth_complications: birthForm.birth_complications || undefined,
      notes: birthForm.notes || undefined,
      offspring: birthForm.offspring.map(o => ({
        birth_order: o.birth_order,
        gender: o.gender,
        birth_weight_kg: o.birth_weight_kg ? parseFloat(o.birth_weight_kg) : undefined,
        outcome: o.outcome,
        notes: o.notes || undefined,
      })),
    };
    birthMut.mutate({ id: showBirth.id, body });
  }

  // ── UI ──
  const tabs = [
    { key: 'overview',         label: 'Joriy Holat',   icon: Activity },
    { key: 'records',          label: 'Yozuvlar',       icon: Calendar },
    { key: 'genealogy',        label: 'Shajara',         icon: GitBranch },
    { key: 'recommendations',  label: 'Tavsiyalar',      icon: Zap },
  ] as const;

  const overlay: React.CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
    zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center',
    backdropFilter: 'blur(2px)',
  };
  const modal: React.CSSProperties = {
    background: 'var(--card)', borderRadius: 14, padding: 28,
    minWidth: 480, maxWidth: 620, width: '95%', maxHeight: '90vh',
    overflow: 'auto', position: 'relative', boxShadow: '0 24px 60px rgba(0,0,0,0.3)',
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            display: 'flex', alignItems: 'center', gap: 10 }}>
            <Baby size={22} color="#EC4899" /> Nasl va Zotchilik
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
            Homiladorlik kuzatuvi · Shajara daraxti · AI juft tavsiyalari
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} style={btn('#EC4899')}>
          <Plus size={15} /> Yangi Nasl Yozuvi
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24,
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 10, padding: 4, width: 'fit-content' }}>
        {tabs.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key as any)} style={{
            padding: '8px 16px', borderRadius: 7, border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: 500,
            background: tab === key ? '#EC4899' : 'none',
            color: tab === key ? '#fff' : 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'all 0.2s',
          }}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* ══════════════════ TAB 1: OVERVIEW ══════════════════ */}
      {tab === 'overview' && (
        <div>
          {/* Stats */}
          {statsLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Yuklanmoqda...</div>
          ) : stats && (
            <>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
                <StatCard label="Jami yozuvlar" value={stats.total_records} color="#6B7280" icon={Calendar} />
                <StatCard label="Homilador" value={stats.active_pregnancies}
                  sub={`+ ${stats.planned} rejalashtirilgan`} color="#10B981" icon={Heart} />
                <StatCard label="Tug'ildi (bu yil)" value={stats.birthed_this_year}
                  sub={`${stats.total_live_offspring} tirik nasl`} color="#3B82F6" icon={Baby} />
                <StatCard label="7 kunda kutiladi" value={stats.due_next_7_days}
                  color="#F59E0B" icon={Clock} />
                <StatCard label="Muddati o'tdi" value={stats.overdue_count}
                  color="#EF4444" icon={AlertTriangle} />
                <StatCard label="O'rtacha nasl" value={stats.avg_litter_size.toFixed(1)}
                  sub={`${stats.stillbirth_rate_pct}% o'lik tug'ilish`} color="#8B5CF6" icon={TrendingUp} />
              </div>

              {/* Usul breakdown */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
                {Object.entries(stats.by_mating_method).map(([method, count]) => (
                  <div key={method} style={{
                    padding: '6px 12px', borderRadius: 8,
                    background: 'var(--card)', border: '1px solid var(--border)',
                    fontSize: 12, color: 'var(--text-secondary)',
                  }}>
                    {METHOD_LABEL[method] || method}: <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Active Pregnancies */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
              Aktiv Homiladorliklar
            </h2>
            <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 12,
              background: '#10B98118', color: '#10B981', fontWeight: 600 }}>
              {activePregancies?.length ?? 0} ta
            </span>
            <button onClick={() => qc.invalidateQueries({ queryKey: ['breeding-active'] })}
              style={{ marginLeft: 'auto', ...ghostBtn, padding: '5px 10px', fontSize: 12 }}>
              <RefreshCw size={12} />
            </button>
          </div>

          {pregLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Yuklanmoqda...</div>
          ) : !activePregancies?.length ? (
            <div style={{
              textAlign: 'center', padding: '40px 20px',
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, color: 'var(--text-muted)', fontSize: 14,
            }}>
              <Heart size={32} style={{ opacity: 0.3, display: 'block', margin: '0 auto 10px' }} />
              Hozirda faol homiladorlik yo'q
            </div>
          ) : (
            activePregancies.map(rec => <PregnancyCard key={rec.id} rec={rec} />)
          )}
        </div>
      )}

      {/* ══════════════════ TAB 2: RECORDS ══════════════════ */}
      {tab === 'records' && (
        <div>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
              style={{ ...sel, width: 'auto', minWidth: 160 }}>
              <option value="">Barcha holatlar</option>
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select value={speciesFilter} onChange={e => { setSpeciesFilter(e.target.value); setPage(1); }}
              style={{ ...sel, width: 'auto', minWidth: 140 }}>
              <option value="">Barcha turlar</option>
              {['cattle', 'sheep', 'goat', 'horse', 'other'].map(s => (
                <option key={s} value={s}>{SPECIES_ICON[s]} {s}</option>
              ))}
            </select>
            <button onClick={() => qc.invalidateQueries({ queryKey: ['breeding-records'] })}
              style={{ ...ghostBtn }}>
              <RefreshCw size={13} />
            </button>
          </div>

          {/* Table */}
          {recLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Yuklanmoqda...</div>
          ) : (
            <>
              <div style={{ borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: 'var(--card)' }}>
                      {['#', 'Ona jonivor', 'Ota', 'Juftlashish', 'Kutilgan tug\'ilish', 'Holat', 'Nasllar', 'Amallar'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11,
                          fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase',
                          letterSpacing: '0.04em', borderBottom: '1px solid var(--border)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(records?.items || []).map((rec, idx) => (
                      <tr key={rec.id} style={{
                        borderBottom: '1px solid var(--border)',
                        background: idx % 2 === 0 ? 'transparent' : 'var(--card)',
                      }}>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600 }}>
                          {rec.id}
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                            {SPECIES_ICON[rec.mother?.species || 'other']} {rec.mother?.tag_id ?? `#${rec.mother_id}`}
                          </span>
                          {rec.mother?.breed && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{rec.mother.breed}</div>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                          {rec.father?.tag_id ?? rec.external_sire_tag ?? '—'}
                          {(rec.external_sire_tag && !rec.father) && (
                            <span style={{ fontSize: 10, color: '#F59E0B', marginLeft: 4 }}>tashqi</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                          {fmtDate(rec.mating_date)}
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                            {METHOD_LABEL[rec.mating_method]}
                          </div>
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                          {fmtDate(rec.expected_birth_date)}
                          {rec.is_overdue && (
                            <span style={{ fontSize: 10, color: '#EF4444', marginLeft: 4, fontWeight: 600 }}>
                              !kechikdi
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{
                            fontSize: 11, padding: '3px 9px', borderRadius: 20, fontWeight: 600,
                            background: STATUS_COLOR[rec.status] + '18',
                            color: STATUS_COLOR[rec.status],
                          }}>
                            {STATUS_LABEL[rec.status]}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                          {rec.status === 'birthed'
                            ? `${rec.live_offspring_count} tirik`
                            : '—'
                          }
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button onClick={() => setShowDetail(rec)} title="Ko'rish"
                              style={{ ...ghostBtn, padding: '4px 8px' }}>
                              <Eye size={13} />
                            </button>
                            {rec.status === 'planned' && (
                              <button onClick={() => setShowConfirm(rec)} title="Homiladorlikni tasdiqlash"
                                style={{ ...ghostBtn, padding: '4px 8px', color: '#10B981', borderColor: '#10B98140' }}>
                                <CheckCircle size={13} />
                              </button>
                            )}
                            {rec.status === 'confirmed_pregnant' && (
                              <button onClick={() => setShowBirth(rec)} title="Tug'ilishni qayd etish"
                                style={{ ...ghostBtn, padding: '4px 8px', color: '#3B82F6', borderColor: '#3B82F640' }}>
                                <Baby size={13} />
                              </button>
                            )}
                            {['planned', 'failed'].includes(rec.status) && (
                              <button onClick={() => deleteMut.mutate(rec.id)} title="O'chirish"
                                style={{ ...ghostBtn, padding: '4px 8px', color: '#EF4444', borderColor: '#EF444440' }}>
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {records && records.pages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
                  {Array.from({ length: records.pages }, (_, i) => i + 1).map(p => (
                    <button key={p} onClick={() => setPage(p)} style={{
                      padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)',
                      background: p === page ? '#EC4899' : 'none',
                      color: p === page ? '#fff' : 'var(--text-secondary)',
                      cursor: 'pointer', fontWeight: 500, fontSize: 13,
                    }}>{p}</button>
                  ))}
                </div>
              )}

              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 10, textAlign: 'right' }}>
                Jami: {records?.total ?? 0} ta yozuv
              </div>
            </>
          )}
        </div>
      )}

      {/* ══════════════════ TAB 3: GENEALOGY ══════════════════ */}
      {tab === 'genealogy' && (
        <div>
          <div style={{
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 20, marginBottom: 20,
          }}>
            <h3 style={{ margin: '0 0 14px', fontSize: 15, fontWeight: 700 }}>
              🌳 Shajara daraxti izlash
            </h3>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Jonivor ID
                </label>
                <input value={genealogyAnimalId}
                  onChange={e => setGenealogyAnimalId(e.target.value)}
                  placeholder="Masalan: 42"
                  style={{ ...inp }} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Avlod chuqurligi
                </label>
                <select value={genealogyGen} onChange={e => setGenealogyGen(+e.target.value)}
                  style={{ ...sel, width: 120 }}>
                  {[1, 2, 3, 4, 5].map(n => (
                    <option key={n} value={n}>{n} avlod</option>
                  ))}
                </select>
              </div>
              <button onClick={() => refetchGene()}
                disabled={!genealogyAnimalId}
                style={{ ...btn('#EC4899'), opacity: genealogyAnimalId ? 1 : 0.4 }}>
                <GitBranch size={14} /> Ko'rish
              </button>
            </div>
          </div>

          {geneLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Shajara yuklanmoqda...</div>
          ) : genealogy ? (
            <div style={{
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, padding: 24,
            }}>
              <div style={{ display: 'flex', gap: 16, marginBottom: 16, fontSize: 12, color: 'var(--text-muted)' }}>
                <span>♀ <span style={{ color: '#EC4899' }}>Urg'ochi</span></span>
                <span>♂ <span style={{ color: '#3B82F6' }}>Erkak</span></span>
                <span style={{ color: '#F59E0B' }}>■ Tashqi ota</span>
              </div>
              <GenealogyTree node={genealogy} />
            </div>
          ) : (
            <div style={{
              textAlign: 'center', padding: '60px 20px',
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, color: 'var(--text-muted)',
            }}>
              <GitBranch size={36} style={{ opacity: 0.2, display: 'block', margin: '0 auto 12px' }} />
              Jonivor ID kiriting va "Ko'rish" tugmasini bosing
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ TAB 4: RECOMMENDATIONS ══════════════════ */}
      {tab === 'recommendations' && (
        <div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
            <select value={speciesFilter} onChange={e => setSpeciesFilter(e.target.value)}
              style={{ ...sel, width: 'auto', minWidth: 140 }}>
              <option value="">Barcha turlar</option>
              {['cattle', 'sheep', 'goat', 'horse'].map(s => (
                <option key={s} value={s}>{SPECIES_ICON[s]} {s}</option>
              ))}
            </select>
            <button onClick={() => qc.invalidateQueries({ queryKey: ['breeding-recommendations'] })}
              style={{ ...ghostBtn }}>
              <RefreshCw size={13} />
            </button>
            {recommendations && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {recommendations.total_females_eligible} ona • {recommendations.total_sires_available} ota →{' '}
                {recommendations.recommendations.length} tavsiya
              </span>
            )}
          </div>

          {recmLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Tavsiyalar hisoblanmoqda...</div>
          ) : !recommendations?.recommendations.length ? (
            <div style={{
              textAlign: 'center', padding: '60px 20px',
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, color: 'var(--text-muted)',
            }}>
              <Zap size={36} style={{ opacity: 0.2, display: 'block', margin: '0 auto 12px' }} />
              Naslga tayyor jonivorlar topilmadi
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {recommendations.recommendations.map((rec, i) => (
                <div key={i} style={{
                  background: 'var(--card)', border: '1px solid var(--border)',
                  borderRadius: 12, padding: 18,
                  borderLeft: `3px solid ${scoreColor(rec.total_score)}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    {/* Rank */}
                    <div style={{
                      width: 32, height: 32, borderRadius: '50%',
                      background: scoreColor(rec.total_score) + '18',
                      color: scoreColor(rec.total_score),
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 13, flexShrink: 0,
                    }}>
                      {i + 1}
                    </div>

                    {/* Animals */}
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ padding: '6px 10px', borderRadius: 7,
                        background: '#EC489918', border: '1px solid #EC489940' }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#EC4899' }}>♀ </span>
                        <span style={{ fontWeight: 700, fontSize: 13 }}>{rec.mother.tag_id}</span>
                        {rec.mother.breed && (
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                            {rec.mother.breed}
                          </span>
                        )}
                      </div>
                      <ArrowRight size={14} color="var(--text-muted)" />
                      <div style={{ padding: '6px 10px', borderRadius: 7,
                        background: '#3B82F618', border: '1px solid #3B82F640' }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#3B82F6' }}>♂ </span>
                        <span style={{ fontWeight: 700, fontSize: 13 }}>
                          {rec.sire_animal?.tag_id ?? rec.sire_external_label ?? '—'}
                        </span>
                        {rec.sire_animal?.breed && (
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                            {rec.sire_animal.breed}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Total score */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: scoreColor(rec.total_score) }}>
                        {rec.total_score}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>/ 100 ball</div>
                    </div>
                  </div>

                  {/* Score breakdown */}
                  <div style={{ marginBottom: 10 }}>
                    <ScoreBar label="Genetik xilma-xillik" value={rec.genetic_diversity_score} max={40} />
                    <ScoreBar label="ADI mos kelishi" value={rec.adi_compatibility_score} max={30} />
                    <ScoreBar label="Vazn nisbati" value={rec.weight_compatibility_score} max={20} />
                    <ScoreBar label="Zot uyg'unligi" value={rec.breed_compatibility_score} max={10} />
                  </div>

                  {/* Details */}
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    💡 {rec.recommendation_reason}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    🗓 Gestatsiya: {rec.estimated_gestation_days} kun •{' '}
                    Kutilgan tug'ilish: {fmtDate(rec.expected_birth_range_start)} —{' '}
                    {fmtDate(rec.expected_birth_range_end)}
                  </div>
                  {rec.warnings.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {rec.warnings.map((w, wi) => (
                        <span key={wi} style={{
                          fontSize: 11, padding: '2px 8px', borderRadius: 12, marginRight: 6,
                          background: '#EF444418', color: '#EF4444',
                        }}>⚠ {w}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ MODAL: CREATE ══════════════════ */}
      {showCreate && (
        <div style={overlay} onClick={() => setShowCreate(false)}>
          <div style={modal} onClick={e => e.stopPropagation()}>
            <button onClick={() => setShowCreate(false)}
              style={{ position: 'absolute', top: 16, right: 16, background: 'none',
                border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
              <X size={18} />
            </button>
            <h3 style={{ margin: '0 0 20px', fontWeight: 700, fontSize: 17 }}>
              🐾 Yangi Nasl Yozuvi
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Ona jonivor *
                </label>
                <select value={cForm.mother_id}
                  onChange={e => setCForm({ ...cForm, mother_id: e.target.value })}
                  style={sel}>
                  <option value="">— Tanlang —</option>
                  {(females || []).map(f => (
                    <option key={f.id} value={f.id}>
                      {SPECIES_ICON[f.species]} {f.tag_id} {f.breed ? `(${f.breed})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
                  <input type="checkbox" checked={cForm.use_external}
                    onChange={e => setCForm({ ...cForm, use_external: e.target.checked })} />
                  <span style={{ fontSize: 13 }}>Tashqi ota (boshqa fermadan)</span>
                </label>

                {cForm.use_external ? (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Tashqi ota tag ID *
                      </label>
                      <input value={cForm.external_sire_tag}
                        onChange={e => setCForm({ ...cForm, external_sire_tag: e.target.value })}
                        placeholder="EXT-001" style={inp} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                        Zoti
                      </label>
                      <input value={cForm.external_sire_breed}
                        onChange={e => setCForm({ ...cForm, external_sire_breed: e.target.value })}
                        placeholder="Aberdeen Angus" style={inp} />
                    </div>
                  </div>
                ) : (
                  <div>
                    <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                      Ota jonivor (ichki) *
                    </label>
                    <select value={cForm.father_id}
                      onChange={e => setCForm({ ...cForm, father_id: e.target.value })}
                      style={sel}>
                      <option value="">— Tanlang —</option>
                      {(males || []).map(m => (
                        <option key={m.id} value={m.id}>
                          {SPECIES_ICON[m.species]} {m.tag_id} {m.breed ? `(${m.breed})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                    Juftlashish sanasi *
                  </label>
                  <input type="date" value={cForm.mating_date}
                    onChange={e => setCForm({ ...cForm, mating_date: e.target.value })}
                    style={inp} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                    Usul
                  </label>
                  <select value={cForm.mating_method}
                    onChange={e => setCForm({ ...cForm, mating_method: e.target.value })}
                    style={sel}>
                    <option value="natural">Tabiiy</option>
                    <option value="artificial_insemination">Sun'iy urug'lantirish</option>
                    <option value="embryo_transfer">Embrion ko'chirish</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Veterinar
                </label>
                <input value={cForm.veterinarian}
                  onChange={e => setCForm({ ...cForm, veterinarian: e.target.value })}
                  placeholder="Ismi sharif" style={inp} />
              </div>

              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Izoh
                </label>
                <textarea value={cForm.notes}
                  onChange={e => setCForm({ ...cForm, notes: e.target.value })}
                  placeholder="Ixtiyoriy..."
                  rows={2}
                  style={{ ...inp, resize: 'vertical' }} />
              </div>
            </div>

            {createMut.error && (
              <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 7,
                background: '#EF444418', color: '#EF4444', fontSize: 12 }}>
                Xato: {String((createMut.error as any)?.message || createMut.error)}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
              <button onClick={() => setShowCreate(false)} style={ghostBtn}>Bekor</button>
              <button onClick={handleCreate} disabled={createMut.isPending}
                style={{ ...btn('#EC4899'), flex: 1, justifyContent: 'center' }}>
                {createMut.isPending ? 'Saqlanmoqda...' : '💾 Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════ MODAL: CONFIRM PREGNANCY ══════════════════ */}
      {showConfirm && (
        <div style={overlay} onClick={() => setShowConfirm(null)}>
          <div style={{ ...modal, minWidth: 400 }} onClick={e => e.stopPropagation()}>
            <button onClick={() => setShowConfirm(null)}
              style={{ position: 'absolute', top: 16, right: 16, background: 'none',
                border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
              <X size={18} />
            </button>
            <h3 style={{ margin: '0 0 6px', fontWeight: 700, fontSize: 17 }}>
              ✅ Homiladorlikni Tasdiqlash
            </h3>
            <p style={{ margin: '0 0 18px', fontSize: 13, color: 'var(--text-muted)' }}>
              {showConfirm.mother?.tag_id} — {fmtDate(showConfirm.mating_date)} juftlashgan
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Tasdiqlash sanasi
                </label>
                <input type="date" value={confirmForm.confirmed_at}
                  onChange={e => setConfirmForm({ ...confirmForm, confirmed_at: e.target.value })}
                  style={inp} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Tekshiruv usuli
                </label>
                <select value={confirmForm.check_method}
                  onChange={e => setConfirmForm({ ...confirmForm, check_method: e.target.value })}
                  style={sel}>
                  <option value="ultrasound">Ultratovush</option>
                  <option value="blood_test">Qon tahlili</option>
                  <option value="rectal_exam">Rektal tekshiruv</option>
                  <option value="visual">Vizual kuzatuv</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Natija / Izoh
                </label>
                <textarea value={confirmForm.check_notes}
                  onChange={e => setConfirmForm({ ...confirmForm, check_notes: e.target.value })}
                  placeholder="Ultratovush xulosasi..."
                  rows={2} style={{ ...inp, resize: 'vertical' }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
              <button onClick={() => setShowConfirm(null)} style={ghostBtn}>Bekor</button>
              <button onClick={handleConfirm} disabled={confirmMut.isPending}
                style={{ ...btn('#10B981'), flex: 1, justifyContent: 'center' }}>
                {confirmMut.isPending ? '...' : '✅ Tasdiqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════ MODAL: RECORD BIRTH ══════════════════ */}
      {showBirth && (
        <div style={overlay} onClick={() => setShowBirth(null)}>
          <div style={{ ...modal, minWidth: 520 }} onClick={e => e.stopPropagation()}>
            <button onClick={() => setShowBirth(null)}
              style={{ position: 'absolute', top: 16, right: 16, background: 'none',
                border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
              <X size={18} />
            </button>
            <h3 style={{ margin: '0 0 6px', fontWeight: 700, fontSize: 17 }}>
              🍼 Tug'ilishni Qayd Etish
            </h3>
            <p style={{ margin: '0 0 18px', fontSize: 13, color: 'var(--text-muted)' }}>
              {showBirth.mother?.tag_id} • Kutilgan: {fmtDate(showBirth.expected_birth_date)}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Tug'ilish sanasi
                </label>
                <input type="date" value={birthForm.actual_birth_date}
                  onChange={e => setBirthForm({ ...birthForm, actual_birth_date: e.target.value })}
                  style={inp} />
              </div>

              {/* Offspring */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    Tug'ilgan nasllar
                  </label>
                  <button onClick={() => setBirthForm({
                    ...birthForm,
                    offspring: [...birthForm.offspring, {
                      birth_order: birthForm.offspring.length + 1,
                      gender: 'unknown', birth_weight_kg: '', outcome: 'alive', notes: '',
                    }],
                  })} style={{ ...ghostBtn, fontSize: 12, padding: '4px 10px' }}>
                    <Plus size={12} /> Qo'shish
                  </button>
                </div>

                {birthForm.offspring.map((off, idx) => (
                  <div key={idx} style={{
                    padding: 12, border: '1px solid var(--border)',
                    borderRadius: 8, marginBottom: 8, background: 'var(--bg)',
                  }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)',
                        width: 60, flexShrink: 0 }}>#{idx + 1} nasl</span>
                      <select value={off.gender}
                        onChange={e => {
                          const newOff = [...birthForm.offspring];
                          newOff[idx] = { ...newOff[idx], gender: e.target.value };
                          setBirthForm({ ...birthForm, offspring: newOff });
                        }}
                        style={{ ...sel, flex: 1 }}>
                        <option value="female">♀ Urg'ochi</option>
                        <option value="male">♂ Erkak</option>
                        <option value="unknown">Noma'lum</option>
                      </select>
                      <select value={off.outcome}
                        onChange={e => {
                          const newOff = [...birthForm.offspring];
                          newOff[idx] = { ...newOff[idx], outcome: e.target.value };
                          setBirthForm({ ...birthForm, offspring: newOff });
                        }}
                        style={{ ...sel, flex: 1 }}>
                        <option value="alive">✅ Tirik</option>
                        <option value="stillborn">💔 O'lik tug'ilgan</option>
                        <option value="died_shortly">⚠️ Ko'p o'tmay o'ldi</option>
                      </select>
                      <input type="number" step="0.1" value={off.birth_weight_kg}
                        onChange={e => {
                          const newOff = [...birthForm.offspring];
                          newOff[idx] = { ...newOff[idx], birth_weight_kg: e.target.value };
                          setBirthForm({ ...birthForm, offspring: newOff });
                        }}
                        placeholder="Vazn kg"
                        style={{ ...inp, width: 90, flexShrink: 0 }} />
                      {birthForm.offspring.length > 1 && (
                        <button onClick={() => {
                          const newOff = birthForm.offspring.filter((_, i) => i !== idx)
                            .map((o, i) => ({ ...o, birth_order: i + 1 }));
                          setBirthForm({ ...birthForm, offspring: newOff });
                        }} style={{ background: 'none', border: 'none', cursor: 'pointer',
                          color: '#EF4444', padding: 4 }}>
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Tug'ilish asoratlari
                </label>
                <input value={birthForm.birth_complications}
                  onChange={e => setBirthForm({ ...birthForm, birth_complications: e.target.value })}
                  placeholder="Ixtiyoriy..." style={inp} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
              <button onClick={() => setShowBirth(null)} style={ghostBtn}>Bekor</button>
              <button onClick={handleBirth} disabled={birthMut.isPending}
                style={{ ...btn('#3B82F6'), flex: 1, justifyContent: 'center' }}>
                {birthMut.isPending ? '...' : '🍼 Tug\'ilishni Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════ MODAL: DETAIL ══════════════════ */}
      {showDetail && (
        <div style={overlay} onClick={() => setShowDetail(null)}>
          <div style={{ ...modal }} onClick={e => e.stopPropagation()}>
            <button onClick={() => setShowDetail(null)}
              style={{ position: 'absolute', top: 16, right: 16, background: 'none',
                border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
              <X size={18} />
            </button>
            <h3 style={{ margin: '0 0 16px', fontWeight: 700, fontSize: 16 }}>
              Nasl Yozuvi #{showDetail.id}
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 13 }}>
              {[
                ['Holat', <span style={{ color: STATUS_COLOR[showDetail.status], fontWeight: 700 }}>
                  {STATUS_LABEL[showDetail.status]}</span>],
                ['Ona', showDetail.mother?.tag_id ?? `#${showDetail.mother_id}`],
                ['Ota', showDetail.father?.tag_id ?? showDetail.external_sire_tag ?? '—'],
                ['Juftlashish', fmtDate(showDetail.mating_date)],
                ['Usul', METHOD_LABEL[showDetail.mating_method]],
                ['Gestatsiya', `${showDetail.gestation_days} kun`],
                ['Kutilgan', fmtDate(showDetail.expected_birth_date)],
                ['Haqiqiy', fmtDate(showDetail.actual_birth_date)],
                ['Tirik nasllar', showDetail.live_offspring_count],
                ['O\'lik tug\'ilgan', showDetail.stillborn_count],
                ['Veterinar', showDetail.veterinarian || '—'],
                ['Yaratildi', fmtDate(showDetail.created_at)],
              ].map(([k, v], i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{String(k)}</div>
                  <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{v}</div>
                </div>
              ))}
            </div>

            {showDetail.notes && (
              <div style={{ marginTop: 14, padding: 12, background: 'var(--bg)',
                borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                📝 {showDetail.notes}
              </div>
            )}

            {showDetail.offspring.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Tug'ilgan nasllar:</div>
                {showDetail.offspring.map(off => (
                  <div key={off.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 10px', background: 'var(--bg)',
                    borderRadius: 7, marginBottom: 5, fontSize: 12,
                  }}>
                    <span>{off.gender === 'female' ? '♀' : off.gender === 'male' ? '♂' : '?'}</span>
                    <span style={{ fontWeight: 600 }}>#{off.birth_order}</span>
                    {off.birth_weight_kg && <span>{off.birth_weight_kg} kg</span>}
                    <span style={{ color: off.outcome === 'alive' ? '#10B981' : '#EF4444' }}>
                      {off.outcome === 'alive' ? 'Tirik' : off.outcome === 'stillborn' ? "O'lik" : 'Ko\'p o\'tmay'}
                    </span>
                    {off.animal_tag_id && (
                      <span style={{ marginLeft: 'auto', fontSize: 11,
                        color: '#3B82F6', fontWeight: 600 }}>
                        → {off.animal_tag_id}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}