/**
 * Taurus Vision — Go'sht Ishlab Chiqarish Sahifasi
 *
 * Farm-level KPI, kunlik trend, per-record jadval,
 * maqsad va sifat bo'yicha breakdown, top jonivorlar.
 *
 * API: /meat/farm/summary, /meat/farm/daily, /meat/farm/records
 */

import { useState, useMemo, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  Beef, TrendingUp, TrendingDown, Minus, Search,
  ArrowUpDown, ArrowUp, ArrowDown, ChevronRight,
  AlertCircle, Plus, X, CheckCircle, Scale, BadgeCheck,
  Layers, BarChart2, Award, Calendar, DollarSign,
  ClipboardList, Filter, RefreshCw,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { apiFetch } from "../utils/apiFetch";

// ─── Ranglar ─────────────────────────────────────────────────────────────────
const QUALITY_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  premium:  { bg: "#EFF6FF", text: "#1D4ED8", label: "Premium (A+)" },
  choice:   { bg: "#F0FDF4", text: "#15803D", label: "Tanlangan (A)" },
  select:   { bg: "#FEFCE8", text: "#A16207", label: "Select (B)" },
  standard: { bg: "#F9FAFB", text: "#374151", label: "Standart (C)" },
  low:      { bg: "#FEF2F2", text: "#DC2626", label: "Past sifat" },
};
const PURPOSE_LABELS: Record<string, string> = {
  sale:       "Sotish",
  own_use:    "O'z iste'mol",
  export:     "Eksport",
  processing: "Qayta ishlash",
};
const PURPOSE_COLORS = ["#2563EB", "#7C3AED", "#059669", "#D97706"];
const CHART_COLORS   = ["#1D4ED8", "#15803D", "#A16207", "#374151", "#DC2626"];

// ─── Tiplar ───────────────────────────────────────────────────────────────────
interface FarmMeatSummary {
  today_animals_count: number;
  today_meat_kg: number;
  today_revenue: number | null;
  this_month_animals: number;
  this_month_kg: number;
  this_month_revenue: number | null;
  last_month_animals: number;
  last_month_kg: number;
  last_month_revenue: number | null;
  all_time_animals: number;
  all_time_kg: number;
  daily_trend: { date: string; meat_kg: number; animals_count: number; revenue: number | null; avg_dressing: number | null }[];
  purpose_breakdown: { purpose: string; count: number; meat_kg: number; revenue: number | null }[];
  quality_breakdown: { grade: string; count: number; meat_kg: number; percent: number }[];
  top_animals: { animal_id: number; tag_id: string; name: string; species: string; total_meat_kg: number; total_revenue: number | null; avg_dressing: number | null; last_date: string }[];
}

interface MeatRecord {
  id: number;
  animal_id: number;
  tag_id: string;
  name: string;
  species: string;
  breed: string;
  slaughter_date: string;
  purpose: string;
  live_weight_kg: number | null;
  carcass_weight_kg: number | null;
  dressing_percent: number | null;
  meat_kg: number;
  bone_kg: number | null;
  fat_kg: number | null;
  offal_kg: number | null;
  hide_kg: number | null;
  quality_grade: string | null;
  ph_value: number | null;
  price_per_kg: number | null;
  total_revenue: number | null;
  veterinary_check: boolean;
  slaughtered_by: string | null;
  notes: string | null;
}

type SortKey = "slaughter_date" | "meat_kg" | "live_weight_kg" | "dressing_percent" | "total_revenue";
type SortDir = "asc" | "desc";
type Tab = "overview" | "records" | "analytics";

// ─── Yordamchi komponentlar ───────────────────────────────────────────────────

const card: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #E2E8F0",
  borderRadius: 14,
  padding: "18px 20px",
};

function Trend({ value }: { value: number }) {
  if (value > 0) return <span style={{ color: "#16A34A", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><TrendingUp size={14} />+{value.toFixed(1)}%</span>;
  if (value < 0) return <span style={{ color: "#DC2626", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><TrendingDown size={14} />{value.toFixed(1)}%</span>;
  return <span style={{ color: "#6B7280", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><Minus size={14} />0%</span>;
}

function QualityBadge({ grade }: { grade: string | null }) {
  if (!grade) return <span style={{ color: "#9CA3AF", fontSize: 12 }}>—</span>;
  const q = QUALITY_COLORS[grade] ?? { bg: "#F3F4F6", text: "#6B7280", label: grade };
  return (
    <span style={{
      background: q.bg, color: q.text, fontSize: 11, fontWeight: 700,
      borderRadius: 5, padding: "2px 7px", border: `1px solid ${q.text}25`,
      whiteSpace: "nowrap",
    }}>{q.label}</span>
  );
}

function SortIcon({ col, current, dir }: { col: SortKey; current: SortKey; dir: SortDir }) {
  if (col !== current) return <ArrowUpDown size={12} style={{ opacity: 0.35 }} />;
  return dir === "desc" ? <ArrowDown size={12} color="#2563EB" /> : <ArrowUp size={12} color="#2563EB" />;
}

function formatMoney(val: number | null) {
  if (val === null || val === undefined) return "—";
  return new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 }).format(val) + " so'm";
}

// ─── Add Record Modal ─────────────────────────────────────────────────────────

function AddRecordModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({
    animal_id: "",
    slaughter_date: format(new Date(), "yyyy-MM-dd"),
    purpose: "sale",
    live_weight_kg: "",
    carcass_weight_kg: "",
    meat_kg: "",
    bone_kg: "",
    fat_kg: "",
    offal_kg: "",
    hide_kg: "",
    quality_grade: "",
    ph_value: "",
    price_per_kg: "",
    veterinary_check: false,
    slaughtered_by: "",
    notes: "",
  });
  const [err, setErr] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch("/api/v1/meat/", {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Content-Type": "application/json" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meat"] });
      onSuccess();
      onClose();
    },
    onError: (e: unknown) => {
      setErr(e instanceof Error ? e.message : "Xato yuz berdi");
    },
  });

  function handleSubmit() {
    if (!form.animal_id || !form.meat_kg) {
      setErr("Jonivor ID va go'sht miqdori majburiy");
      return;
    }
    const payload: Record<string, unknown> = {
      animal_id:      parseInt(form.animal_id),
      slaughter_date: form.slaughter_date,
      purpose:        form.purpose,
      meat_kg:        parseFloat(form.meat_kg),
      veterinary_check: form.veterinary_check,
    };
    if (form.live_weight_kg)    payload.live_weight_kg    = parseFloat(form.live_weight_kg);
    if (form.carcass_weight_kg) payload.carcass_weight_kg = parseFloat(form.carcass_weight_kg);
    if (form.bone_kg)           payload.bone_kg           = parseFloat(form.bone_kg);
    if (form.fat_kg)            payload.fat_kg            = parseFloat(form.fat_kg);
    if (form.offal_kg)          payload.offal_kg          = parseFloat(form.offal_kg);
    if (form.hide_kg)           payload.hide_kg           = parseFloat(form.hide_kg);
    if (form.quality_grade)     payload.quality_grade     = form.quality_grade;
    if (form.ph_value)          payload.ph_value          = parseFloat(form.ph_value);
    if (form.price_per_kg)      payload.price_per_kg      = parseFloat(form.price_per_kg);
    if (form.slaughtered_by)    payload.slaughtered_by    = form.slaughtered_by;
    if (form.notes)             payload.notes             = form.notes;
    mutation.mutate(payload);
  }

  const inp: React.CSSProperties = {
    width: "100%", padding: "8px 12px", borderRadius: 8,
    border: "1px solid #E2E8F0", fontSize: 13, outline: "none",
    fontFamily: "inherit", color: "#0F172A", background: "#FAFAFA",
    boxSizing: "border-box",
  };
  const label: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: "#64748B",
    textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4,
    display: "block",
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
      zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center",
      padding: 16,
    }} onClick={onClose}>
      <div style={{
        background: "#fff", borderRadius: 18, padding: 28, width: "100%", maxWidth: 600,
        maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 24px 60px rgba(0,0,0,.2)",
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}>
              <Beef size={20} color="#DC2626" /> Yangi so'yish yozuvi
            </h2>
            <p style={{ margin: "3px 0 0", fontSize: 12, color: "#94A3B8" }}>Go'sht ishlab chiqarish ma'lumotlarini kiriting</p>
          </div>
          <button onClick={onClose} style={{ border: "none", background: "#F1F5F9", borderRadius: 9, cursor: "pointer", padding: "6px 8px", display: "flex" }}>
            <X size={16} color="#64748B" />
          </button>
        </div>

        {err && (
          <div style={{ background: "#FEF2F2", color: "#DC2626", borderRadius: 9, padding: "10px 14px", marginBottom: 16, fontSize: 13 }}>
            {err}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {/* Jonivor ID */}
          <div style={{ gridColumn: "1/-1" }}>
            <label style={label}>Jonivor ID *</label>
            <input style={inp} type="number" placeholder="Jonivor ID raqami" value={form.animal_id}
              onChange={e => setForm(f => ({ ...f, animal_id: e.target.value }))} />
          </div>

          {/* So'yish sanasi */}
          <div>
            <label style={label}>So'yish sanasi *</label>
            <input style={inp} type="date" value={form.slaughter_date}
              onChange={e => setForm(f => ({ ...f, slaughter_date: e.target.value }))} />
          </div>

          {/* Maqsad */}
          <div>
            <label style={label}>Maqsad</label>
            <select style={{ ...inp }} value={form.purpose}
              onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}>
              <option value="sale">Sotish</option>
              <option value="own_use">O'z iste'mol</option>
              <option value="export">Eksport</option>
              <option value="processing">Qayta ishlash</option>
            </select>
          </div>

          {/* Tirik vazn */}
          <div>
            <label style={label}>Tirik vazn (kg)</label>
            <input style={inp} type="number" step="0.1" placeholder="Masalan: 450" value={form.live_weight_kg}
              onChange={e => setForm(f => ({ ...f, live_weight_kg: e.target.value }))} />
          </div>

          {/* Karkas vazni */}
          <div>
            <label style={label}>Karkas vazni (kg)</label>
            <input style={inp} type="number" step="0.1" placeholder="Masalan: 240" value={form.carcass_weight_kg}
              onChange={e => setForm(f => ({ ...f, carcass_weight_kg: e.target.value }))} />
          </div>

          {/* Go'sht miqdori */}
          <div>
            <label style={label}>Sof go'sht (kg) *</label>
            <input style={inp} type="number" step="0.1" placeholder="Masalan: 180" value={form.meat_kg}
              onChange={e => setForm(f => ({ ...f, meat_kg: e.target.value }))} />
          </div>

          {/* Suyak */}
          <div>
            <label style={label}>Suyak (kg)</label>
            <input style={inp} type="number" step="0.1" placeholder="Masalan: 40" value={form.bone_kg}
              onChange={e => setForm(f => ({ ...f, bone_kg: e.target.value }))} />
          </div>

          {/* Yog' */}
          <div>
            <label style={label}>Yog' (kg)</label>
            <input style={inp} type="number" step="0.1" value={form.fat_kg}
              onChange={e => setForm(f => ({ ...f, fat_kg: e.target.value }))} />
          </div>

          {/* Ichki organlar */}
          <div>
            <label style={label}>Ichki organlar (kg)</label>
            <input style={inp} type="number" step="0.1" value={form.offal_kg}
              onChange={e => setForm(f => ({ ...f, offal_kg: e.target.value }))} />
          </div>

          {/* Teri */}
          <div>
            <label style={label}>Teri (kg)</label>
            <input style={inp} type="number" step="0.1" value={form.hide_kg}
              onChange={e => setForm(f => ({ ...f, hide_kg: e.target.value }))} />
          </div>

          {/* Sifat darajasi */}
          <div>
            <label style={label}>Sifat darajasi</label>
            <select style={{ ...inp }} value={form.quality_grade}
              onChange={e => setForm(f => ({ ...f, quality_grade: e.target.value }))}>
              <option value="">— Tanlang —</option>
              <option value="premium">Premium (A+)</option>
              <option value="choice">Tanlangan (A)</option>
              <option value="select">Select (B)</option>
              <option value="standard">Standart (C)</option>
              <option value="low">Past sifat</option>
            </select>
          </div>

          {/* pH */}
          <div>
            <label style={label}>pH qiymati (5.4–6.8)</label>
            <input style={inp} type="number" step="0.1" min="4" max="8" placeholder="Masalan: 5.8" value={form.ph_value}
              onChange={e => setForm(f => ({ ...f, ph_value: e.target.value }))} />
          </div>

          {/* Narx */}
          <div>
            <label style={label}>1 kg narxi (so'm)</label>
            <input style={inp} type="number" placeholder="Masalan: 85000" value={form.price_per_kg}
              onChange={e => setForm(f => ({ ...f, price_per_kg: e.target.value }))} />
          </div>

          {/* So'ygan */}
          <div>
            <label style={label}>Kim so'ydi</label>
            <input style={inp} type="text" placeholder="Xodim ismi" value={form.slaughtered_by}
              onChange={e => setForm(f => ({ ...f, slaughtered_by: e.target.value }))} />
          </div>

          {/* Vet tekshiruv */}
          <div style={{ gridColumn: "1/-1", display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" id="vet_check" checked={form.veterinary_check}
              onChange={e => setForm(f => ({ ...f, veterinary_check: e.target.checked }))}
              style={{ width: 16, height: 16, cursor: "pointer" }} />
            <label htmlFor="vet_check" style={{ fontSize: 13, color: "#374151", cursor: "pointer" }}>
              Veterinariya tekshiruvi o'tkazildi
            </label>
          </div>

          {/* Izoh */}
          <div style={{ gridColumn: "1/-1" }}>
            <label style={label}>Izoh</label>
            <textarea style={{ ...inp, resize: "vertical", minHeight: 72 }} placeholder="Qo'shimcha ma'lumotlar..." value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{
            padding: "9px 20px", borderRadius: 9, border: "1px solid #E2E8F0",
            background: "#fff", fontSize: 13, cursor: "pointer", fontFamily: "inherit", color: "#374151",
          }}>Bekor qilish</button>
          <button onClick={handleSubmit} disabled={mutation.isPending} style={{
            padding: "9px 22px", borderRadius: 9, border: "none",
            background: mutation.isPending ? "#94A3B8" : "#DC2626",
            color: "#fff", fontSize: 13, fontWeight: 600, cursor: mutation.isPending ? "default" : "pointer",
            fontFamily: "inherit", display: "flex", alignItems: "center", gap: 7,
          }}>
            {mutation.isPending ? <><RefreshCw size={14} />Saqlanmoqda...</> : <><Plus size={14} />Saqlash</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Asosiy sahifa ────────────────────────────────────────────────────────────

export default function MeatProductionPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [days, setDays] = useState(30);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("slaughter_date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const [filterPurpose, setFilterPurpose] = useState("");
  const [filterGrade, setFilterGrade] = useState("");
  const PAGE_SIZE = 15;

  const { data: summary, isLoading: summaryLoading } = useQuery<FarmMeatSummary>({
    queryKey: ["meat", "farm", "summary"],
    queryFn: () => apiFetch("/api/v1/meat/farm/summary"),
  });

  const { data: records = [], isLoading: recordsLoading } = useQuery<MeatRecord[]>({
    queryKey: ["meat", "farm", "records"],
    queryFn: () => apiFetch("/api/v1/meat/farm/records"),
  });

  const monthChange = summary && summary.last_month_kg > 0
    ? ((summary.this_month_kg - summary.last_month_kg) / summary.last_month_kg) * 100
    : 0;

  // Qidiruv + filtr + saralash
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return records
      .filter(r =>
        (!q || r.tag_id.toLowerCase().includes(q) || r.name.toLowerCase().includes(q) || r.species.toLowerCase().includes(q)) &&
        (!filterPurpose || r.purpose === filterPurpose) &&
        (!filterGrade || r.quality_grade === filterGrade)
      )
      .sort((a, b) => {
        const av = (a[sortKey] as number | null) ?? 0;
        const bv = (b[sortKey] as number | null) ?? 0;
        const diff = av - bv;
        return sortDir === "desc" ? -diff : diff;
      });
  }, [records, search, sortKey, sortDir, filterPurpose, filterGrade]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortKey(key); setSortDir("desc"); }
    setPage(1);
  }

  // ── KPI kartalar ma'lumotlari
  const kpiCards = [
    { label: "Bugun (jonivorlar)", value: `${summary?.today_animals_count ?? 0} ta`, sub: summary?.today_meat_kg ? `${summary.today_meat_kg} kg` : "", color: "#DC2626" },
    { label: "Bu oy go'sht", value: `${(summary?.this_month_kg ?? 0).toFixed(1)} kg`, sub: `${summary?.this_month_animals ?? 0} ta jonivor`, color: "#7C3AED" },
    { label: "O'tgan oy", value: `${(summary?.last_month_kg ?? 0).toFixed(1)} kg`, sub: `${summary?.last_month_animals ?? 0} ta`, color: "#64748B" },
    { label: "Jami barcha vaqt", value: `${(summary?.all_time_kg ?? 0).toFixed(0)} kg`, sub: `${summary?.all_time_animals ?? 0} ta jonivor`, color: "#059669" },
    { label: "Bu oy tushum", value: summary?.this_month_revenue ? formatMoney(summary.this_month_revenue) : "—", sub: "Jami savdo", color: "#F59E0B" },
  ];

  return (
    <div style={{
      maxWidth: 1240, margin: "0 auto",
      padding: "24px 20px 80px",
      fontFamily: "'Outfit', system-ui, sans-serif", color: "#0F172A",
    }}>
      <style>{`
        @keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
        *{box-sizing:border-box}
        .row-hover:hover{background:#FFF5F5 !important;cursor:pointer;}
        .pg-btn{padding:5px 10px;border-radius:7px;border:1px solid #E2E8F0;background:#fff;font-size:12px;cursor:pointer;color:#374151;font-family:inherit;transition:all .15s;}
        .pg-btn:hover{background:#F1F5F9;}
        .pg-btn.active{background:#DC2626;color:#fff;border-color:#DC2626;font-weight:600;}
        .pg-btn:disabled{opacity:.4;cursor:default;}
        .sort-th{display:flex;align-items:center;gap:5px;padding:10px 14px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;cursor:pointer;white-space:nowrap;background:none;border:none;font-family:inherit;text-align:left;transition:color .15s;color:#6B7280;}
        .sort-th:hover{color:#DC2626 !important;}
        .tab-btn{padding:9px 18px;border-radius:9px;border:none;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;transition:all .15s;}
      `}</style>

      {/* ── Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, display: "flex", alignItems: "center", gap: 10 }}>
            <Beef size={26} color="#DC2626" /> Go'sht Ishlab Chiqarish
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748B" }}>
            So'yish statistikasi, go'sht massasi va moliyaviy natijalar
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          style={{
            display: "flex", alignItems: "center", gap: 7,
            padding: "10px 20px", borderRadius: 10, border: "none",
            background: "#DC2626", color: "#fff", fontSize: 13,
            fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            boxShadow: "0 2px 8px rgba(220,38,38,.3)",
          }}
        >
          <Plus size={16} /> Yangi yozuv
        </button>
      </div>

      {/* ── KPI Kartalar ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 20 }}>
        {kpiCards.map(({ label, value, sub, color }) => (
          <div key={label} style={{ ...card, padding: "14px 16px", animation: "fadein .3s" }}>
            <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color }}>{summaryLoading ? "—" : value}</div>
            {sub && <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 3 }}>{sub}</div>}
          </div>
        ))}
        <div style={{ ...card, padding: "14px 16px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>Oy taqqoslovi</div>
          <Trend value={monthChange} />
          <div style={{ fontSize: 11, color: "#CBD5E1", marginTop: 4 }}>go'sht miqdori</div>
        </div>
      </div>

      {/* ── Tab navigatsiya ── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20, background: "#F8FAFC", borderRadius: 12, padding: 4, width: "fit-content" }}>
        {([
          { key: "overview",  label: "Umumiy ko'rinish", icon: <BarChart2 size={14} /> },
          { key: "records",   label: "Yozuvlar jadvali", icon: <ClipboardList size={14} /> },
          { key: "analytics", label: "Tahlil",           icon: <Layers size={14} /> },
        ] as { key: Tab; label: string; icon: React.ReactNode }[]).map(t => (
          <button
            key={t.key}
            className="tab-btn"
            onClick={() => setTab(t.key)}
            style={{
              background: tab === t.key ? "#fff" : "transparent",
              color: tab === t.key ? "#DC2626" : "#64748B",
              fontWeight: tab === t.key ? 600 : 500,
              boxShadow: tab === t.key ? "0 1px 4px rgba(0,0,0,.08)" : "none",
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ════════════════════ TAB: OVERVIEW ════════════════════ */}
      {tab === "overview" && (
        <div style={{ animation: "fadein .25s" }}>
          {/* Trend grafik */}
          <div style={{ ...card, marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Kunlik go'sht ishlab chiqarish trendi</h3>
              <div style={{ display: "flex", gap: 4, background: "#F1F5F9", borderRadius: 8, padding: 3 }}>
                {[7, 14, 30, 60].map(d => (
                  <button key={d} onClick={() => setDays(d)} style={{
                    padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 500,
                    border: "none", cursor: "pointer", fontFamily: "inherit",
                    background: days === d ? "#fff" : "transparent",
                    color: days === d ? "#DC2626" : "#64748B",
                    boxShadow: days === d ? "0 1px 3px rgba(0,0,0,.08)" : "none",
                  }}>{d} kun</button>
                ))}
              </div>
            </div>
            {(summary?.daily_trend?.length ?? 0) > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={summary!.daily_trend}>
                  <defs>
                    <linearGradient id="meatGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#DC2626" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#DC2626" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="date" tickFormatter={d => format(parseISO(d), "dd/MM")} tick={{ fontSize: 11, fill: "#94A3B8" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} unit=" kg" width={55} />
                  <Tooltip
                    formatter={(v: number, name: string) => [
                      name === "meat_kg" ? `${v} kg` : `${v} ta`,
                      name === "meat_kg" ? "Go'sht" : "Jonivorlar",
                    ]}
                    labelFormatter={d => format(parseISO(d as string), "dd.MM.yyyy")}
                  />
                  <Area type="monotone" dataKey="meat_kg" name="meat_kg" stroke="#DC2626" strokeWidth={2.5}
                    fill="url(#meatGrad)" dot={{ fill: "#DC2626", r: 3 }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 240, display: "grid", placeItems: "center", color: "#94A3B8" }}>
                <div style={{ textAlign: "center" }}>
                  <Beef size={40} style={{ opacity: .15, display: "block", margin: "0 auto 10px" }} />
                  <p style={{ fontSize: 13, margin: 0 }}>So'yish ma'lumoti yo'q</p>
                </div>
              </div>
            )}
          </div>

          {/* Purpose + Quality breakdown */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
            {/* Maqsad bo'yicha */}
            <div style={card}>
              <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 7 }}>
                <Filter size={15} color="#64748B" /> Maqsad bo'yicha
              </h3>
              {(summary?.purpose_breakdown?.length ?? 0) > 0 ? (
                <div>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={summary!.purpose_breakdown} dataKey="count" nameKey="purpose"
                        cx="50%" cy="50%" outerRadius={65} innerRadius={40}>
                        {summary!.purpose_breakdown.map((entry, i) => (
                          <Cell key={i} fill={PURPOSE_COLORS[i % PURPOSE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number, name: string) => [v + " ta", PURPOSE_LABELS[name] || name]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                    {summary!.purpose_breakdown.map((p, i) => (
                      <div key={p.purpose} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                          <div style={{ width: 10, height: 10, borderRadius: 3, background: PURPOSE_COLORS[i % PURPOSE_COLORS.length] }} />
                          <span style={{ fontSize: 12, color: "#374151" }}>{PURPOSE_LABELS[p.purpose] || p.purpose}</span>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: "#0F172A" }}>{p.count} ta</span>
                          <span style={{ fontSize: 11, color: "#94A3B8", marginLeft: 6 }}>{p.meat_kg.toFixed(0)} kg</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ height: 200, display: "grid", placeItems: "center", color: "#CBD5E1", fontSize: 13 }}>Ma'lumot yo'q</div>
              )}
            </div>

            {/* Sifat bo'yicha */}
            <div style={card}>
              <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 7 }}>
                <Award size={15} color="#64748B" /> Sifat darajasi bo'yicha
              </h3>
              {(summary?.quality_breakdown?.length ?? 0) > 0 ? (
                <div>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={summary!.quality_breakdown} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                      <YAxis type="category" dataKey="grade"
                        tickFormatter={g => QUALITY_COLORS[g]?.label.split("(")[0].trim() || g}
                        tick={{ fontSize: 10, fill: "#64748B" }} width={75} />
                      <Tooltip
                        formatter={(v: number) => [v.toFixed(1) + " kg", "Go'sht"]}
                        labelFormatter={g => QUALITY_COLORS[g]?.label || g}
                      />
                      <Bar dataKey="meat_kg" radius={[0, 6, 6, 0]}>
                        {summary!.quality_breakdown.map((entry, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 6 }}>
                    {summary!.quality_breakdown.map((q, i) => (
                      <div key={q.grade} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                          <div style={{ width: 10, height: 10, borderRadius: 3, background: CHART_COLORS[i % CHART_COLORS.length] }} />
                          <span style={{ fontSize: 12, color: "#374151" }}>{QUALITY_COLORS[q.grade]?.label || q.grade}</span>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{q.percent}% · {q.count} ta</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ height: 200, display: "grid", placeItems: "center", color: "#CBD5E1", fontSize: 13 }}>Ma'lumot yo'q</div>
              )}
            </div>
          </div>

          {/* Top jonivorlar */}
          <div style={card}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
              <Award size={16} color="#F59E0B" /> Top go'sht beruvchi jonivorlar (joriy oy)
            </h3>
            {(summary?.top_animals?.length ?? 0) > 0 ? (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #F1F5F9" }}>
                      {["#", "Jonivor", "Go'sht (kg)", "Tushum", "So'yish foizi", "Sana"].map(h => (
                        <th key={h} style={{ padding: "8px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: ".06em", textAlign: "left", whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {summary!.top_animals.map((a, i) => (
                      <tr key={a.animal_id} className="row-hover"
                        onClick={() => navigate(`/animals/${a.animal_id}`)}
                        style={{ borderBottom: "1px solid #FAFAFA" }}>
                        <td style={{ padding: "10px 14px" }}>
                          <span style={{
                            width: 24, height: 24, borderRadius: 7,
                            background: i === 0 ? "#FBBF24" : i === 1 ? "#9CA3AF" : i === 2 ? "#CD7F32" : "#F1F5F9",
                            color: i < 3 ? "#fff" : "#6B7280",
                            fontSize: 11, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center",
                          }}>{i + 1}</span>
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{ width: 32, height: 32, borderRadius: 8, background: "#FEF2F2", display: "flex", alignItems: "center", justifyContent: "center" }}>
                              <Beef size={15} color="#DC2626" />
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13, fontFamily: "'JetBrains Mono',monospace" }}>{a.tag_id}</div>
                              <div style={{ fontSize: 11, color: "#64748B" }}>{a.name || a.species || "—"}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: "10px 14px", fontWeight: 700, fontSize: 15, color: "#DC2626" }}>{a.total_meat_kg.toFixed(1)} kg</td>
                        <td style={{ padding: "10px 14px", fontSize: 13, color: "#059669", fontWeight: 600 }}>{formatMoney(a.total_revenue)}</td>
                        <td style={{ padding: "10px 14px" }}>
                          {a.avg_dressing ? (
                            <span style={{ fontSize: 12, fontWeight: 600, color: a.avg_dressing >= 55 ? "#059669" : a.avg_dressing >= 48 ? "#D97706" : "#DC2626",
                              background: a.avg_dressing >= 55 ? "#ECFDF5" : a.avg_dressing >= 48 ? "#FFFBEB" : "#FEF2F2",
                              borderRadius: 5, padding: "2px 8px" }}>
                              {a.avg_dressing.toFixed(1)}%
                            </span>
                          ) : "—"}
                        </td>
                        <td style={{ padding: "10px 14px", fontSize: 12, color: "#94A3B8" }}>
                          {a.last_date ? format(parseISO(a.last_date), "dd.MM.yyyy") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#CBD5E1", fontSize: 13 }}>Bu oyda so'yish yozuvi yo'q</div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════ TAB: RECORDS ════════════════════ */}
      {tab === "records" && (
        <div style={{ ...card, animation: "fadein .25s" }}>
          {/* Jadval header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>So'yish yozuvlari</h3>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: "#94A3B8" }}>{filtered.length} ta yozuv</p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {/* Qidiruv */}
              <div style={{ position: "relative" }}>
                <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#9CA3AF" }} />
                <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Qidirish..."
                  style={{ paddingLeft: 32, paddingRight: 12, paddingTop: 8, paddingBottom: 8, border: "1px solid #E2E8F0", borderRadius: 9, fontSize: 13, outline: "none", fontFamily: "inherit", width: 180, color: "#0F172A" }} />
              </div>
              {/* Filter maqsad */}
              <select value={filterPurpose} onChange={e => { setFilterPurpose(e.target.value); setPage(1); }}
                style={{ padding: "8px 12px", border: "1px solid #E2E8F0", borderRadius: 9, fontSize: 13, outline: "none", fontFamily: "inherit", color: "#374151", background: "#fff" }}>
                <option value="">Barcha maqsad</option>
                {Object.entries(PURPOSE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {/* Filter sifat */}
              <select value={filterGrade} onChange={e => { setFilterGrade(e.target.value); setPage(1); }}
                style={{ padding: "8px 12px", border: "1px solid #E2E8F0", borderRadius: 9, fontSize: 13, outline: "none", fontFamily: "inherit", color: "#374151", background: "#fff" }}>
                <option value="">Barcha sifat</option>
                {Object.entries(QUALITY_COLORS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </div>
          </div>

          {recordsLoading ? (
            <div style={{ padding: "48px 0", textAlign: "center", color: "#94A3B8", fontSize: 13 }}>Yuklanmoqda…</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: "56px 0", textAlign: "center", color: "#94A3B8" }}>
              <AlertCircle size={40} style={{ opacity: .2, display: "block", margin: "0 auto 12px" }} />
              <p style={{ fontSize: 14, margin: 0 }}>{search || filterPurpose || filterGrade ? "Qidiruv natijasi topilmadi" : "So'yish yozuvi yo'q"}</p>
            </div>
          ) : (
            <>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #F1F5F9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", textAlign: "left", letterSpacing: ".06em" }}>Jonivor</th>
                      <button className="sort-th" style={{ color: sortKey === "slaughter_date" ? "#DC2626" : "#6B7280" } as React.CSSProperties}
                        onClick={() => handleSort("slaughter_date")}>Sana <SortIcon col="slaughter_date" current={sortKey} dir={sortDir} /></button>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", textAlign: "left", letterSpacing: ".06em", whiteSpace: "nowrap" }}>Maqsad</th>
                      <button className="sort-th" style={{ color: sortKey === "live_weight_kg" ? "#DC2626" : "#6B7280" } as React.CSSProperties}
                        onClick={() => handleSort("live_weight_kg")}>Tirik vazn <SortIcon col="live_weight_kg" current={sortKey} dir={sortDir} /></button>
                      <button className="sort-th" style={{ color: sortKey === "meat_kg" ? "#DC2626" : "#6B7280" } as React.CSSProperties}
                        onClick={() => handleSort("meat_kg")}>Go'sht <SortIcon col="meat_kg" current={sortKey} dir={sortDir} /></button>
                      <button className="sort-th" style={{ color: sortKey === "dressing_percent" ? "#DC2626" : "#6B7280" } as React.CSSProperties}
                        onClick={() => handleSort("dressing_percent")}>So'yish % <SortIcon col="dressing_percent" current={sortKey} dir={sortDir} /></button>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", textAlign: "left", letterSpacing: ".06em", whiteSpace: "nowrap" }}>Sifat</th>
                      <button className="sort-th" style={{ color: sortKey === "total_revenue" ? "#DC2626" : "#6B7280" } as React.CSSProperties}
                        onClick={() => handleSort("total_revenue")}>Tushum <SortIcon col="total_revenue" current={sortKey} dir={sortDir} /></button>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", textAlign: "left", letterSpacing: ".06em" }}>Vet</th>
                      <th style={{ width: 32 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {paged.map((r, i) => (
                      <tr key={r.id} className="row-hover"
                        onClick={() => navigate(`/animals/${r.animal_id}`)}
                        style={{ borderBottom: i < paged.length - 1 ? "1px solid #F8FAFC" : "none" }}>
                        {/* Jonivor */}
                        <td style={{ padding: "11px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                            <div style={{ width: 34, height: 34, borderRadius: 9, background: "#FFF0F0", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                              <Beef size={16} color="#DC2626" />
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13, color: "#0F172A", fontFamily: "'JetBrains Mono',monospace" }}>{r.tag_id}</div>
                              <div style={{ fontSize: 11, color: "#64748B", marginTop: 1 }}>{r.name || r.species || "—"}</div>
                            </div>
                          </div>
                        </td>
                        {/* Sana */}
                        <td style={{ padding: "11px 14px", fontSize: 12, color: "#374151", whiteSpace: "nowrap" }}>
                          {format(parseISO(r.slaughter_date), "dd.MM.yyyy")}
                        </td>
                        {/* Maqsad */}
                        <td style={{ padding: "11px 14px" }}>
                          <span style={{ fontSize: 11, fontWeight: 600, color: "#7C3AED", background: "#F5F3FF", borderRadius: 5, padding: "2px 8px" }}>
                            {PURPOSE_LABELS[r.purpose] || r.purpose}
                          </span>
                        </td>
                        {/* Tirik vazn */}
                        <td style={{ padding: "11px 14px", fontSize: 13, color: "#374151" }}>
                          {r.live_weight_kg ? `${r.live_weight_kg} kg` : "—"}
                        </td>
                        {/* Go'sht */}
                        <td style={{ padding: "11px 14px" }}>
                          <div style={{ fontSize: 15, fontWeight: 700, color: "#DC2626" }}>{r.meat_kg.toFixed(1)} kg</div>
                          {r.bone_kg && <div style={{ fontSize: 10, color: "#94A3B8" }}>+ {r.bone_kg}kg suyak</div>}
                        </td>
                        {/* So'yish foizi */}
                        <td style={{ padding: "11px 14px" }}>
                          {r.dressing_percent ? (
                            <span style={{
                              fontSize: 12, fontWeight: 600,
                              color: r.dressing_percent >= 55 ? "#059669" : r.dressing_percent >= 48 ? "#D97706" : "#DC2626",
                              background: r.dressing_percent >= 55 ? "#ECFDF5" : r.dressing_percent >= 48 ? "#FFFBEB" : "#FEF2F2",
                              borderRadius: 5, padding: "2px 8px",
                            }}>{r.dressing_percent.toFixed(1)}%</span>
                          ) : "—"}
                        </td>
                        {/* Sifat */}
                        <td style={{ padding: "11px 14px" }}><QualityBadge grade={r.quality_grade} /></td>
                        {/* Tushum */}
                        <td style={{ padding: "11px 14px", fontSize: 12, color: "#059669", fontWeight: 600 }}>
                          {formatMoney(r.total_revenue)}
                        </td>
                        {/* Vet */}
                        <td style={{ padding: "11px 14px" }}>
                          {r.veterinary_check
                            ? <CheckCircle size={16} color="#059669" />
                            : <X size={16} color="#CBD5E1" />}
                        </td>
                        <td style={{ padding: "11px 10px" }}><ChevronRight size={14} color="#CBD5E1" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 14, paddingTop: 12, borderTop: "1px solid #F1F5F9", flexWrap: "wrap", gap: 8 }}>
                  <span style={{ fontSize: 12, color: "#94A3B8" }}>
                    {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} / {filtered.length} ta
                  </span>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button className="pg-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹ Oldingi</button>
                    {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                      const p = totalPages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= totalPages - 3 ? totalPages - 6 + i : page - 3 + i;
                      return <button key={p} className={`pg-btn${p === page ? " active" : ""}`} onClick={() => setPage(p)}>{p}</button>;
                    })}
                    <button className="pg-btn" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Keyingi ›</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ════════════════════ TAB: ANALYTICS ════════════════════ */}
      {tab === "analytics" && (
        <div style={{ animation: "fadein .25s" }}>
          {/* So'yish tarkibi */}
          <div style={{ ...card, marginBottom: 20 }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
              <Scale size={16} color="#64748B" /> O'rtacha jonivor tarkibi (bu oy)
            </h3>
            {records.length > 0 ? (() => {
              const hasMeat  = records.filter(r => r.meat_kg);
              const hasBone  = records.filter(r => r.bone_kg);
              const hasFat   = records.filter(r => r.fat_kg);
              const hasOffal = records.filter(r => r.offal_kg);
              const hasHide  = records.filter(r => r.hide_kg);
              const avg = (arr: MeatRecord[], key: keyof MeatRecord) =>
                arr.length ? arr.reduce((s, r) => s + ((r[key] as number) || 0), 0) / arr.length : 0;

              const breakdown = [
                { name: "Sof go'sht",    value: avg(hasMeat, "meat_kg"),   color: "#DC2626" },
                { name: "Suyak",         value: avg(hasBone, "bone_kg"),   color: "#7C3AED" },
                { name: "Yog'",          value: avg(hasFat, "fat_kg"),     color: "#F59E0B" },
                { name: "Ichki organlar",value: avg(hasOffal, "offal_kg"), color: "#059669" },
                { name: "Teri",          value: avg(hasHide, "hide_kg"),   color: "#64748B" },
              ].filter(b => b.value > 0);

              const total = breakdown.reduce((s, b) => s + b.value, 0);

              return (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "center" }}>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie data={breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%"
                        outerRadius={90} innerRadius={55} paddingAngle={2}>
                        {breakdown.map((b, i) => <Cell key={i} fill={b.color} />)}
                      </Pie>
                      <Tooltip formatter={(v: number) => [v.toFixed(1) + " kg", ""]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {breakdown.map(b => (
                      <div key={b.name}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                            <div style={{ width: 10, height: 10, borderRadius: 3, background: b.color }} />
                            <span style={{ fontSize: 13, color: "#374151" }}>{b.name}</span>
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 700, color: "#0F172A" }}>
                            {b.value.toFixed(1)} kg
                          </span>
                        </div>
                        <div style={{ background: "#F1F5F9", borderRadius: 4, height: 6, overflow: "hidden" }}>
                          <div style={{ background: b.color, height: "100%", width: `${total > 0 ? (b.value / total) * 100 : 0}%`, borderRadius: 4, transition: "width .5s" }} />
                        </div>
                        <div style={{ fontSize: 10, color: "#94A3B8", marginTop: 2 }}>
                          {total > 0 ? ((b.value / total) * 100).toFixed(1) : 0}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })() : (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#CBD5E1", fontSize: 13 }}>Ma'lumot yo'q</div>
            )}
          </div>

          {/* Jonivor boshiga o'rtacha ko'rsatkichlar */}
          <div style={{ ...card, marginBottom: 20 }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
              <BarChart2 size={16} color="#64748B" /> O'rtacha ko'rsatkichlar (bu oy)
            </h3>
            {records.length > 0 ? (() => {
              const validDressing = records.filter(r => r.dressing_percent);
              const validLive     = records.filter(r => r.live_weight_kg);
              const validMeat     = records.filter(r => r.meat_kg);
              const validRevenue  = records.filter(r => r.total_revenue);
              const avg = (arr: MeatRecord[], key: keyof MeatRecord) =>
                arr.length ? arr.reduce((s, r) => s + ((r[key] as number) || 0), 0) / arr.length : 0;

              const stats = [
                { label: "O'rtacha so'yish foizi", value: `${avg(validDressing, "dressing_percent").toFixed(1)}%`, icon: <Scale size={18} color="#7C3AED" />, bg: "#F5F3FF" },
                { label: "O'rtacha tirik vazn",    value: `${avg(validLive, "live_weight_kg").toFixed(0)} kg`,    icon: <Scale size={18} color="#2563EB" />, bg: "#EFF6FF" },
                { label: "O'rtacha go'sht",         value: `${avg(validMeat, "meat_kg").toFixed(1)} kg`,           icon: <Beef size={18} color="#DC2626" />,  bg: "#FFF0F0" },
                { label: "O'rtacha tushum",         value: formatMoney(avg(validRevenue, "total_revenue")),         icon: <DollarSign size={18} color="#059669" />, bg: "#ECFDF5" },
                { label: "Jami so'yish",            value: `${records.length} ta`,                                 icon: <ClipboardList size={18} color="#F59E0B" />, bg: "#FFFBEB" },
              ];

              return (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
                  {stats.map(s => (
                    <div key={s.label} style={{ background: s.bg, borderRadius: 12, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ opacity: .7 }}>{s.icon}</div>
                      <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em" }}>{s.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#0F172A" }}>{s.value}</div>
                    </div>
                  ))}
                </div>
              );
            })() : (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#CBD5E1", fontSize: 13 }}>Ma'lumot yo'q</div>
            )}
          </div>

          {/* Jonivor turlari bo'yicha go'sht */}
          {records.length > 0 && (() => {
            const bySpecies = records.reduce((acc, r) => {
              const sp = r.species || "other";
              if (!acc[sp]) acc[sp] = { species: sp, count: 0, meat_kg: 0 };
              acc[sp].count++;
              acc[sp].meat_kg += r.meat_kg;
              return acc;
            }, {} as Record<string, { species: string; count: number; meat_kg: number }>);
            const speciesData = Object.values(bySpecies).sort((a, b) => b.meat_kg - a.meat_kg);

            const SPECIES_LABELS: Record<string, string> = { cattle: "Qoramol", sheep: "Qo'y", goat: "Echki", horse: "Ot", other: "Boshqa" };
            return (
              <div style={card}>
                <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                  <BadgeCheck size={16} color="#64748B" /> Jonivor turi bo'yicha go'sht
                </h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={speciesData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis dataKey="species" tickFormatter={s => SPECIES_LABELS[s] || s} tick={{ fontSize: 12, fill: "#64748B" }} />
                    <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} unit=" kg" />
                    <Tooltip
                      formatter={(v: number, name: string) => [
                        name === "meat_kg" ? `${v.toFixed(1)} kg` : `${v} ta`,
                        name === "meat_kg" ? "Go'sht" : "Jonivorlar",
                      ]}
                      labelFormatter={s => SPECIES_LABELS[s] || s}
                    />
                    <Bar dataKey="meat_kg" name="meat_kg" fill="#DC2626" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="count"   name="count"   fill="#7C3AED" radius={[6, 6, 0, 0]} />
                    <Legend formatter={v => v === "meat_kg" ? "Go'sht (kg)" : "Jonivorlar (ta)"} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            );
          })()}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <AddRecordModal
          onClose={() => setShowModal(false)}
          onSuccess={() => queryClient.invalidateQueries({ queryKey: ["meat"] })}
        />
      )}
    </div>
  );
}