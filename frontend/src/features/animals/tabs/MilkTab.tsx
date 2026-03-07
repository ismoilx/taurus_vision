/**
 * Taurus Vision — Sut Tab Komponenti
 *
 * AnimalDetailPage ichidagi sut ishlab chiqarish tab kontenti.
 * Jonivorning sut tarixi, statistikasi va yangi yozuv qo'shish formi.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar
} from "recharts";
import { Droplets, Plus, TrendingUp, TrendingDown, Minus, X } from "lucide-react";
import { format, parseISO } from "date-fns";
import { apiFetch } from "../../../utils/apiFetch";

// ── Types ──────────────────────────────────────────────────────────────────

interface MilkRecord {
  id: number;
  animal_id: number;
  record_date: string;
  session: string;
  milk_kg: number;
  fat_percent?: number;
  protein_percent?: number;
  somatic_cell_count?: number;
  lactation_number?: number;
  days_in_milk?: number;
  quality_grade?: string;
  milked_by?: string;
  notes?: string;
}

interface MilkListResponse {
  items: MilkRecord[];
  total: number;
  page: number;
  page_size: number;
}

interface MilkSummary {
  animal_id: number;
  animal_tag: string;
  today_kg: number;
  last_7_days_kg: number;
  last_30_days_kg: number;
  stats_30d: {
    total_kg: number;
    avg_daily_kg: number;
    avg_fat_percent?: number;
    avg_protein_percent?: number;
    days_recorded: number;
    best_day_kg?: number;
  };
  recent_records: MilkRecord[];
}

interface Props {
  animalId: number;
  gender: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const SESSION_LABELS: Record<string, string> = {
  morning: "Ertalab", midday: "Tushda", evening: "Kechqurun", daily: "Kunlik"
};

const QUALITY_COLORS: Record<string, string> = {
  premium: "#16A34A", standard: "#2563EB", low: "#D97706", rejected: "#DC2626"
};

const QUALITY_LABELS: Record<string, string> = {
  premium: "Premium", standard: "Standart", low: "Past", rejected: "Rad etilgan"
};

// ── Component ──────────────────────────────────────────────────────────────

export function MilkTab({ animalId, gender }: Props) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    record_date: new Date().toISOString().slice(0, 10),
    session: "daily",
    milk_kg: "",
    fat_percent: "",
    protein_percent: "",
    somatic_cell_count: "",
    lactation_number: "",
    days_in_milk: "",
    milked_by: "",
    notes: "",
  });

  const { data: summary, isLoading: summaryLoading } = useQuery<MilkSummary>({
    queryKey: ["milk", "summary", animalId],
    queryFn: () => apiFetch(`/api/v1/milk/animal/${animalId}/summary`),
  });

  const { data: records } = useQuery<MilkListResponse>({
    queryKey: ["milk", "records", animalId],
    queryFn: () => apiFetch(`/api/v1/milk/animal/${animalId}?page_size=60`),
  });

  const addMut = useMutation({
    mutationFn: () => apiFetch("/api/v1/milk/", {
      method: "POST",
      body: JSON.stringify({
        animal_id: animalId,
        record_date: form.record_date,
        session: form.session,
        milk_kg: parseFloat(form.milk_kg),
        fat_percent: form.fat_percent ? parseFloat(form.fat_percent) : null,
        protein_percent: form.protein_percent ? parseFloat(form.protein_percent) : null,
        somatic_cell_count: form.somatic_cell_count ? parseInt(form.somatic_cell_count) : null,
        lactation_number: form.lactation_number ? parseInt(form.lactation_number) : null,
        days_in_milk: form.days_in_milk ? parseInt(form.days_in_milk) : null,
        milked_by: form.milked_by || null,
        notes: form.notes || null,
      }),
    }),
    onSuccess: () => {
      setMsg("✅ Sut yozuvi saqlandi!");
      setShowForm(false);
      setForm({
        record_date: new Date().toISOString().slice(0, 10),
        session: "daily", milk_kg: "", fat_percent: "", protein_percent: "",
        somatic_cell_count: "", lactation_number: "", days_in_milk: "",
        milked_by: "", notes: "",
      });
      qc.invalidateQueries({ queryKey: ["milk", "summary", animalId] });
      qc.invalidateQueries({ queryKey: ["milk", "records", animalId] });
    },
    onError: (e: Error) => setMsg(`❌ ${e.message}`),
  });

  // Chart data — so'nggi 30 kun kunlik sut
  const chartData = (records?.items ?? [])
    .slice()
    .sort((a, b) => a.record_date.localeCompare(b.record_date))
    .slice(-30)
    .map(r => ({
      date: format(parseISO(r.record_date), "dd/MM"),
      milk_kg: +r.milk_kg.toFixed(2),
    }));

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E2E8F0",
    borderRadius: 14, padding: "18px 20px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 11px", borderRadius: 8, fontSize: 13,
    border: "1.5px solid #E2E8F0", outline: "none", fontFamily: "inherit",
  };

  // Erkak jonivorga sut bo'lmaydi
  if (gender === "male") {
    return (
      <div style={{ ...card, textAlign: "center", padding: "60px 20px" }}>
        <Droplets size={40} color="#CBD5E1" style={{ margin: "0 auto 12px", display: "block" }} />
        <p style={{ fontSize: 15, color: "#94A3B8", margin: 0 }}>
          Erkak jonivorga sut yozuvi yuritilmaydi
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, animation: "fadein .25s" }}>
      {/* KPI Kartalar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
        {[
          ["Bugun", `${summary?.today_kg ?? 0} kg`, "#2563EB"],
          ["7 kun", `${summary?.last_7_days_kg ?? 0} kg`, "#7C3AED"],
          ["30 kun", `${summary?.last_30_days_kg ?? 0} kg`, "#059669"],
          ["Kunlik o'rt.", `${summary?.stats_30d?.avg_daily_kg ?? 0} kg`, "#D97706"],
        ].map(([label, value, color]) => (
          <div key={label as string} style={{ ...card, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
              {label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: color as string }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Grafik + Forma */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
        {/* Trend grafik */}
        <div style={card}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 16px", color: "#0F172A" }}>
            30 kunlik sut trendi
          </h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="milkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} unit=" kg" width={50} />
                <Tooltip formatter={(v: number) => [`${v} kg`, "Sut"]} />
                <Area
                  type="monotone" dataKey="milk_kg"
                  stroke="#2563EB" strokeWidth={2}
                  fill="url(#milkGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: "grid", placeItems: "center", color: "#94A3B8" }}>
              <div style={{ textAlign: "center" }}>
                <Droplets size={32} style={{ opacity: .3, display: "block", margin: "0 auto 8px" }} />
                <p style={{ fontSize: 13 }}>Ma'lumot yo'q</p>
              </div>
            </div>
          )}
        </div>

        {/* Statistika */}
        <div style={card}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 14px" }}>30 kun statistika</h3>
          {[
            ["Jami sut", `${summary?.stats_30d?.total_kg ?? 0} kg`],
            ["Yog' %", summary?.stats_30d?.avg_fat_percent ? `${summary.stats_30d.avg_fat_percent}%` : "—"],
            ["Oqsil %", summary?.stats_30d?.avg_protein_percent ? `${summary.stats_30d.avg_protein_percent}%` : "—"],
            ["Yozuv kunlari", `${summary?.stats_30d?.days_recorded ?? 0} kun`],
            ["Rekord kun", summary?.stats_30d?.best_day_kg ? `${summary.stats_30d.best_day_kg} kg` : "—"],
          ].map(([l, v]) => (
            <div key={l as string} style={{
              display: "flex", justifyContent: "space-between",
              padding: "7px 0", borderBottom: "1px solid #F8FAFC", fontSize: 13,
            }}>
              <span style={{ color: "#64748B" }}>{l}</span>
              <span style={{ fontWeight: 600 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Yangi yozuv qo'shish */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Sog'ish Tarixi</h3>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "7px 14px", borderRadius: 9, fontSize: 13, fontWeight: 500,
              background: showForm ? "#F1F5F9" : "#2563EB", color: showForm ? "#64748B" : "#fff",
              border: "none", cursor: "pointer", fontFamily: "inherit",
            }}
          >
            {showForm ? <><X size={13} /> Yopish</> : <><Plus size={13} /> Yangi yozuv</>}
          </button>
        </div>

        {/* Form */}
        {showForm && (
          <div style={{
            background: "#F8FAFC", borderRadius: 12, padding: 16, marginBottom: 16,
            border: "1px solid #E2E8F0",
          }}>
            {msg && (
              <div style={{
                padding: "8px 12px", borderRadius: 8, marginBottom: 12, fontSize: 13,
                background: msg.startsWith("✅") ? "#F0FDF4" : "#FEF2F2",
                color: msg.startsWith("✅") ? "#16A34A" : "#DC2626",
                border: `1px solid ${msg.startsWith("✅") ? "#BBF7D0" : "#FCA5A5"}`,
              }}>
                {msg}
              </div>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
              {[
                { label: "Sana *", key: "record_date", type: "date" },
                { label: "Sut (kg) *", key: "milk_kg", type: "number", placeholder: "0.0" },
                { label: "Yog' %", key: "fat_percent", type: "number", placeholder: "3.5" },
                { label: "Oqsil %", key: "protein_percent", type: "number", placeholder: "3.2" },
                { label: "SCC (ming/ml)", key: "somatic_cell_count", type: "number", placeholder: "150" },
                { label: "Laktatsiya #", key: "lactation_number", type: "number", placeholder: "1" },
                { label: "DIM (kun)", key: "days_in_milk", type: "number", placeholder: "45" },
                { label: "Kim sog'di", key: "milked_by", type: "text", placeholder: "Ism" },
              ].map(({ label, key, type, placeholder }) => (
                <div key={key}>
                  <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                    {label}
                  </label>
                  <input
                    type={type}
                    value={(form as any)[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                    placeholder={placeholder}
                    style={inputStyle}
                    step={type === "number" ? "0.01" : undefined}
                    min={type === "number" ? "0" : undefined}
                  />
                </div>
              ))}

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Sessiya
                </label>
                <select
                  value={form.session}
                  onChange={e => setForm(f => ({ ...f, session: e.target.value }))}
                  style={inputStyle}
                >
                  {Object.entries(SESSION_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                Izoh
              </label>
              <textarea
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                placeholder="Qo'shimcha izoh..."
                rows={2}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button
                onClick={() => {
                  if (!form.milk_kg) { setMsg("❌ Sut miqdori majburiy"); return; }
                  setMsg("");
                  addMut.mutate();
                }}
                disabled={addMut.isPending}
                style={{
                  padding: "9px 20px", borderRadius: 9, fontSize: 13, fontWeight: 600,
                  background: "#2563EB", color: "#fff", border: "none",
                  cursor: addMut.isPending ? "not-allowed" : "pointer",
                  opacity: addMut.isPending ? .6 : 1, fontFamily: "inherit",
                }}
              >
                {addMut.isPending ? "Saqlanmoqda..." : "Saqlash"}
              </button>
              <button
                onClick={() => { setShowForm(false); setMsg(""); }}
                style={{
                  padding: "9px 16px", borderRadius: 9, fontSize: 13,
                  background: "#F1F5F9", color: "#64748B",
                  border: "1px solid #E2E8F0", cursor: "pointer", fontFamily: "inherit",
                }}
              >
                Bekor
              </button>
            </div>
          </div>
        )}

        {/* Yozuvlar jadvali */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1.5px solid #E2E8F0" }}>
                {["Sana", "Sessiya", "Sut (kg)", "Yog' %", "Oqsil %", "SCC", "Sifat", "Kim"].map(h => (
                  <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 11, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".05em" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(records?.items ?? []).map(r => (
                <tr key={r.id} style={{ borderBottom: "1px solid #F8FAFC" }}>
                  <td style={{ padding: "9px 10px", fontWeight: 500 }}>
                    {format(parseISO(r.record_date), "dd.MM.yyyy")}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {SESSION_LABELS[r.session] ?? r.session}
                  </td>
                  <td style={{ padding: "9px 10px", fontWeight: 700, color: "#2563EB" }}>
                    {r.milk_kg.toFixed(2)} kg
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {r.fat_percent != null ? `${r.fat_percent}%` : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {r.protein_percent != null ? `${r.protein_percent}%` : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {r.somatic_cell_count != null ? `${r.somatic_cell_count}k` : "—"}
                  </td>
                  <td style={{ padding: "9px 10px" }}>
                    {r.quality_grade ? (
                      <span style={{
                        padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600,
                        background: `${QUALITY_COLORS[r.quality_grade]}15`,
                        color: QUALITY_COLORS[r.quality_grade],
                      }}>
                        {QUALITY_LABELS[r.quality_grade]}
                      </span>
                    ) : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {r.milked_by ?? "—"}
                  </td>
                </tr>
              ))}
              {(records?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: "40px 10px", textAlign: "center", color: "#94A3B8" }}>
                    Hali sut yozuvi yo'q
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}