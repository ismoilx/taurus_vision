/**
 * Taurus Vision — Sut Ishlab Chiqarish Sahifasi
 *
 * Farm-level KPI, kunlik trend va per-animal jadval.
 * API: /milk/farm/summary, /milk/farm/daily, /milk/farm/animals
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import {
  Droplets, TrendingUp, TrendingDown, Minus,
  Search, ArrowUpDown, ArrowUp, ArrowDown,
  ChevronRight, AlertCircle,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { apiFetch } from "../utils/apiFetch";

// ── Tiplar ────────────────────────────────────────────────────────────────────

interface FarmMilkSummary {
  today_total_kg: number;
  this_month_kg: number;
  last_month_kg: number;
  active_dairy_animals: number;
  avg_per_animal_kg: number;
  daily_trend: { date: string; total_kg: number; animal_count: number; avg_fat?: number }[];
}

interface AnimalMilkStat {
  animal_id: number;
  tag_id: string;
  name: string;
  species: string;
  month_kg: number;
  today_kg: number;
  avg_daily_kg: number;
  avg_fat_percent: number | null;
  days_recorded: number;
  last_record_date: string;
}

type SortKey = "month_kg" | "today_kg" | "avg_daily_kg" | "days_recorded";
type SortDir = "asc" | "desc";

// ── Yordamchi komponentlar ────────────────────────────────────────────────────

const card: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #E2E8F0",
  borderRadius: 14,
  padding: "18px 20px",
};

function Trend({ value }: { value: number }) {
  if (value > 0)  return <span style={{ color: "#16A34A", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><TrendingUp size={14} />+{value.toFixed(1)}%</span>;
  if (value < 0)  return <span style={{ color: "#DC2626", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><TrendingDown size={14} />{value.toFixed(1)}%</span>;
  return <span style={{ color: "#6B7280", display: "flex", alignItems: "center", gap: 3, fontSize: 13, fontWeight: 600 }}><Minus size={14} />0%</span>;
}

function SortIcon({ col, current, dir }: { col: SortKey; current: SortKey; dir: SortDir }) {
  if (col !== current) return <ArrowUpDown size={12} style={{ opacity: 0.35 }} />;
  return dir === "desc" ? <ArrowDown size={12} color="#2563EB" /> : <ArrowUp size={12} color="#2563EB" />;
}

function QualityBadge({ fat }: { fat: number | null }) {
  if (fat === null) return <span style={{ color: "#9CA3AF", fontSize: 12 }}>—</span>;
  const [label, color] =
    fat >= 4.0 ? ["A+", "#059669"] :
    fat >= 3.5 ? ["A", "#16A34A"] :
    fat >= 3.0 ? ["B", "#D97706"] :
                 ["C", "#DC2626"];
  return (
    <span style={{
      background: color + "18", color, fontSize: 11, fontWeight: 700,
      borderRadius: 5, padding: "2px 7px", border: `1px solid ${color}30`,
    }}>
      {label} {fat.toFixed(1)}%
    </span>
  );
}

// ── Asosiy sahifa ─────────────────────────────────────────────────────────────

export default function MilkProductionPage() {
  const navigate = useNavigate();
  const [days,    setDays]    = useState(30);
  const [search,  setSearch]  = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("month_kg");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page,    setPage]    = useState(1);
  const PAGE_SIZE = 15;

  const { data: summary, isLoading: summaryLoading } = useQuery<FarmMilkSummary>({
    queryKey: ["milk", "farm", "summary"],
    queryFn: () => apiFetch("/api/v1/milk/farm/summary"),
  });

  const { data: trend = [] } = useQuery<{ date: string; total_kg: number }[]>({
    queryKey: ["milk", "farm", "trend", days],
    queryFn: () => apiFetch(`/api/v1/milk/farm/daily?days=${days}`),
  });

  const { data: animalStats = [], isLoading: statsLoading } = useQuery<AnimalMilkStat[]>({
    queryKey: ["milk", "farm", "animals"],
    queryFn: () => apiFetch("/api/v1/milk/farm/animals"),
  });

  const monthChange = summary && summary.last_month_kg > 0
    ? ((summary.this_month_kg - summary.last_month_kg) / summary.last_month_kg) * 100
    : 0;

  // Qidiruv + saralash
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return animalStats
      .filter(a =>
        !q ||
        a.tag_id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        a.species.toLowerCase().includes(q)
      )
      .sort((a, b) => {
        const diff = (a[sortKey] as number) - (b[sortKey] as number);
        return sortDir === "desc" ? -diff : diff;
      });
  }, [animalStats, search, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortKey(key); setSortDir("desc"); }
    setPage(1);
  }

  const thStyle = (key: SortKey): React.CSSProperties => ({
    padding: "10px 14px",
    fontSize: 11,
    fontWeight: 600,
    color: sortKey === key ? "#2563EB" : "#6B7280",
    textTransform: "uppercase",
    letterSpacing: ".06em",
    cursor: "pointer",
    whiteSpace: "nowrap",
    background: "none",
    border: "none",
    textAlign: "left",
    fontFamily: "inherit",
    display: "flex",
    alignItems: "center",
    gap: 5,
  });

  return (
    <div style={{
      maxWidth: 1200, margin: "0 auto",
      padding: "24px 20px 72px",
      fontFamily: "'Outfit', system-ui, sans-serif", color: "#0F172A",
    }}>
      <style>{`
        @keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
        *{box-sizing:border-box}
        .row-hover:hover{background:#F8FAFF !important; cursor:pointer;}
        .pg-btn{padding:5px 10px;border-radius:7px;border:1px solid #E2E8F0;background:#fff;font-size:12px;cursor:pointer;color:#374151;font-family:inherit;transition:all .15s;}
        .pg-btn:hover{background:#F1F5F9;}
        .pg-btn.active{background:#2563EB;color:#fff;border-color:#2563EB;font-weight:600;}
        .pg-btn:disabled{opacity:.4;cursor:default;}
        .sort-th{display:flex;align-items:center;gap:5px;padding:10px 14px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;cursor:pointer;white-space:nowrap;background:none;border:none;font-family:inherit;text-align:left;transition:color .15s;}
        .sort-th:hover{color:#2563EB !important;}
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, display: "flex", alignItems: "center", gap: 10 }}>
          <Droplets size={24} color="#2563EB" /> Sut Ishlab Chiqarish
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748B" }}>
          Ferma bo'yicha kunlik va oylik sut statistikasi
        </p>
      </div>

      {/* KPI kartalar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Bugun",       value: `${summary?.today_total_kg ?? 0} kg`,                 color: "#2563EB" },
          { label: "Bu oy",       value: `${(summary?.this_month_kg ?? 0).toFixed(0)} kg`,      color: "#7C3AED" },
          { label: "O'tgan oy",   value: `${(summary?.last_month_kg ?? 0).toFixed(0)} kg`,      color: "#64748B" },
          { label: "Faol jonivor",value: `${summary?.active_dairy_animals ?? 0} ta`,            color: "#059669" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...card, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
              {label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color }}>{summaryLoading ? "—" : value}</div>
          </div>
        ))}

        <div style={{ ...card, padding: "14px 16px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
            Oy taqqoslovi
          </div>
          <Trend value={monthChange} />
        </div>
      </div>

      {/* Trend grafik */}
      <div style={{ ...card, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Kunlik sut trendi</h3>
          <div style={{ display: "flex", gap: 4, background: "#F1F5F9", borderRadius: 8, padding: 3 }}>
            {[7, 14, 30, 60].map(d => (
              <button key={d} onClick={() => setDays(d)} style={{
                padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 500,
                border: "none", cursor: "pointer", fontFamily: "inherit",
                background: days === d ? "#fff" : "transparent",
                color: days === d ? "#2563EB" : "#64748B",
                boxShadow: days === d ? "0 1px 3px rgba(0,0,0,.08)" : "none",
              }}>{d} kun</button>
            ))}
          </div>
        </div>

        {trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trend}>
              <defs>
                <linearGradient id="milkGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" tickFormatter={d => format(parseISO(d), "dd/MM")} tick={{ fontSize: 11, fill: "#94A3B8" }} />
              <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} unit=" kg" width={55} />
              <Tooltip
                formatter={(v: number) => [`${v} kg`, "Jami sut"]}
                labelFormatter={d => format(parseISO(d as string), "dd.MM.yyyy")}
              />
              <Area type="monotone" dataKey="total_kg" stroke="#2563EB" strokeWidth={2}
                fill="url(#milkGrad)" dot={{ fill: "#2563EB", r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 220, display: "grid", placeItems: "center", color: "#94A3B8" }}>
            <div style={{ textAlign: "center" }}>
              <Droplets size={36} style={{ opacity: .2, display: "block", margin: "0 auto 8px" }} />
              <p style={{ fontSize: 13, margin: 0 }}>Sut ma'lumoti yo'q</p>
            </div>
          </div>
        )}
      </div>

      {/* Per-animal jadval */}
      <div style={card}>
        {/* Jadval header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Jonivorlar bo'yicha sut</h3>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "#94A3B8" }}>
              {filtered.length} ta jonivor · joriy oy
            </p>
          </div>
          {/* Qidiruv */}
          <div style={{ position: "relative" }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#9CA3AF" }} />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Tag yoki nom qidirish…"
              style={{
                paddingLeft: 32, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
                border: "1px solid #E2E8F0", borderRadius: 9, fontSize: 13,
                outline: "none", fontFamily: "inherit", width: 220, color: "#0F172A",
              }}
            />
          </div>
        </div>

        {statsLoading ? (
          <div style={{ padding: "40px 0", textAlign: "center", color: "#94A3B8", fontSize: 13 }}>
            Yuklanmoqda…
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "48px 0", textAlign: "center", color: "#94A3B8" }}>
            <AlertCircle size={36} style={{ opacity: .2, display: "block", margin: "0 auto 10px" }} />
            <p style={{ fontSize: 14, margin: 0 }}>
              {search ? "Qidiruv natijasi topilmadi" : "Bu oyda sut yozuvi yo'q"}
            </p>
            {!search && (
              <p style={{ fontSize: 12, marginTop: 6, color: "#CBD5E1" }}>
                Jonivor tafsilot sahifasidan sut yozuvlari qo'shing
              </p>
            )}
          </div>
        ) : (
          <>
            {/* Jadval */}
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #F1F5F9" }}>
                    <th style={{ ...thStyle("month_kg"), color: "#6B7280", cursor: "default" }}>Jonivor</th>
                    <button className="sort-th" style={{ color: sortKey === "today_kg" ? "#2563EB" : "#6B7280" } as React.CSSProperties}
                      onClick={() => handleSort("today_kg")} >
                      Bugun <SortIcon col="today_kg" current={sortKey} dir={sortDir} />
                    </button>
                    <button className="sort-th" style={{ color: sortKey === "month_kg" ? "#2563EB" : "#6B7280" } as React.CSSProperties}
                      onClick={() => handleSort("month_kg")} >
                      Bu oy <SortIcon col="month_kg" current={sortKey} dir={sortDir} />
                    </button>
                    <button className="sort-th" style={{ color: sortKey === "avg_daily_kg" ? "#2563EB" : "#6B7280" } as React.CSSProperties}
                      onClick={() => handleSort("avg_daily_kg")} >
                      Kunlik o'rt. <SortIcon col="avg_daily_kg" current={sortKey} dir={sortDir} />
                    </button>
                    <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: ".06em", textAlign: "left", whiteSpace: "nowrap" }}>
                      Sifat (yog')
                    </th>
                    <button className="sort-th" style={{ color: sortKey === "days_recorded" ? "#2563EB" : "#6B7280" } as React.CSSProperties}
                      onClick={() => handleSort("days_recorded")} >
                      Kun soni <SortIcon col="days_recorded" current={sortKey} dir={sortDir} />
                    </button>
                    <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: ".06em", textAlign: "left", whiteSpace: "nowrap" }}>
                      Oxirgi yozuv
                    </th>
                    <th style={{ width: 32 }} />
                  </tr>
                </thead>
                <tbody>
                  {paged.map((a, i) => (
                    <tr
                      key={a.animal_id}
                      className="row-hover"
                      onClick={() => navigate(`/animals/${a.animal_id}`)}
                      style={{
                        borderBottom: i < paged.length - 1 ? "1px solid #F8FAFC" : "none",
                        background: "#fff",
                        transition: "background .1s",
                      }}
                    >
                      {/* Jonivor */}
                      <td style={{ padding: "11px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                          <div style={{
                            width: 34, height: 34, borderRadius: 9,
                            background: "#EFF6FF",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                          }}>
                            <Droplets size={16} color="#2563EB" />
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13, color: "#0F172A", fontFamily: "'JetBrains Mono',monospace" }}>
                              {a.tag_id}
                            </div>
                            <div style={{ fontSize: 11, color: "#64748B", marginTop: 1 }}>
                              {a.name || a.species || "—"}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Bugun */}
                      <td style={{ padding: "11px 14px", fontSize: 14, fontWeight: 600,
                        color: a.today_kg > 0 ? "#0F172A" : "#CBD5E1" }}>
                        {a.today_kg > 0 ? `${a.today_kg} kg` : "—"}
                      </td>

                      {/* Bu oy */}
                      <td style={{ padding: "11px 14px" }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#2563EB" }}>
                          {a.month_kg.toFixed(1)} kg
                        </div>
                      </td>

                      {/* Kunlik o'rtacha */}
                      <td style={{ padding: "11px 14px", fontSize: 13, color: "#374151" }}>
                        {a.avg_daily_kg.toFixed(1)} kg
                      </td>

                      {/* Sifat */}
                      <td style={{ padding: "11px 14px" }}>
                        <QualityBadge fat={a.avg_fat_percent} />
                      </td>

                      {/* Kun soni */}
                      <td style={{ padding: "11px 14px" }}>
                        <span style={{
                          fontSize: 12, fontWeight: 600,
                          color: a.days_recorded >= 20 ? "#059669" : a.days_recorded >= 10 ? "#D97706" : "#DC2626",
                          background: a.days_recorded >= 20 ? "#ECFDF5" : a.days_recorded >= 10 ? "#FFFBEB" : "#FEF2F2",
                          borderRadius: 5, padding: "2px 8px",
                        }}>
                          {a.days_recorded} kun
                        </span>
                      </td>

                      {/* Oxirgi yozuv */}
                      <td style={{ padding: "11px 14px", fontSize: 12, color: "#94A3B8" }}>
                        {format(parseISO(a.last_record_date), "dd.MM.yyyy")}
                      </td>

                      {/* Arrow */}
                      <td style={{ padding: "11px 10px" }}>
                        <ChevronRight size={14} color="#CBD5E1" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                marginTop: 14, paddingTop: 12, borderTop: "1px solid #F1F5F9",
                flexWrap: "wrap", gap: 8,
              }}>
                <span style={{ fontSize: 12, color: "#94A3B8" }}>
                  {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} / {filtered.length} ta
                </span>
                <div style={{ display: "flex", gap: 4 }}>
                  <button className="pg-btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹ Oldingi</button>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                    const p = totalPages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= totalPages - 3 ? totalPages - 6 + i : page - 3 + i;
                    return (
                      <button key={p} className={`pg-btn${p === page ? " active" : ""}`} onClick={() => setPage(p)}>
                        {p}
                      </button>
                    );
                  })}
                  <button className="pg-btn" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Keyingi ›</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}