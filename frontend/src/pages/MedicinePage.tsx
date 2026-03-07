/**
 * Taurus Vision — Dori-Darmon Ombori Sahifasi
 *
 * Veterinariya ombori: barcha dorlar, kam qolganlar, muddatlar,
 * ombor to'ldirish va yangi dori qo'shish.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Pill, Plus, X, AlertTriangle, Clock, Package,
  Search, RefreshCw, TrendingDown, CheckCircle,
} from "lucide-react";
import { format } from "date-fns";
import { apiFetch } from "../utils/apiFetch";

// ── Types ──────────────────────────────────────────────────────────────────

interface Medicine {
  id: number;
  name: string;
  generic_name?: string;
  medicine_type: string;
  manufacturer?: string;
  batch_number?: string;
  quantity: number;
  unit: string;
  min_stock_quantity: number;
  purchase_price?: number;
  expiry_date?: string;
  dosage_instructions?: string;
  is_active: boolean;
  is_low_stock: boolean;
  is_expired: boolean;
  days_until_expiry?: number;
  notes?: string;
}

interface MedicineListResp {
  items: Medicine[];
  total: number;
  low_stock_count: number;
  expired_count: number;
  expiring_soon_count: number;
}

interface InventorySummary {
  total_medicines: number;
  active_medicines: number;
  low_stock_items: Medicine[];
  expired_items: Medicine[];
  expiring_soon_items: Medicine[];
  total_value: number;
}

// ── Constants ──────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  vaccine: "💉 Vaksina", antibiotic: "🦠 Antibiotik",
  antiparasitic: "🐛 Parazitga", vitamin: "💊 Vitamin",
  hormone: "⚗️ Gormonal", analgesic: "🩹 Og'riq qold.",
  antifungal: "🍄 Zamburug'", disinfectant: "🧪 Dezinfek.",
  supplement: "🌿 Qo'shimcha", other: "📋 Boshqa",
};

const UNIT_LABELS: Record<string, string> = {
  ml: "ml", l: "l", mg: "mg", g: "g",
  tablet: "tab", dose: "doza", vial: "flakon", pack: "quti",
};

// ── Component ──────────────────────────────────────────────────────────────

export default function MedicinePage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [showRestockModal, setShowRestockModal] = useState<Medicine | null>(null);
  const [activeTab, setActiveTab] = useState<"all"|"low"|"expiring">("all");
  const [msg, setMsg] = useState("");

  const [addForm, setAddForm] = useState({
    name: "", generic_name: "", medicine_type: "antibiotic",
    manufacturer: "", batch_number: "", quantity: "",
    unit: "ml", min_stock_quantity: "10",
    purchase_price: "", expiry_date: "",
    dosage_instructions: "", notes: "", species_applicable: "",
  });

  const [restockForm, setRestockForm] = useState({
    quantity_to_add: "", batch_number: "", expiry_date: "",
    purchase_price: "", notes: "",
  });

  // Queries
  const { data: medicines, isLoading, refetch } = useQuery<MedicineListResp>({
    queryKey: ["medicine", "list", typeFilter, search],
    queryFn: () => {
      const params = new URLSearchParams({
        page_size: "100",
        active_only: "true",
      });
      if (typeFilter) params.append("medicine_type", typeFilter);
      if (search) params.append("search", search);
      return apiFetch(`/api/v1/medicine/?${params}`);
    },
  });

  const { data: summary } = useQuery<InventorySummary>({
    queryKey: ["medicine", "summary"],
    queryFn: () => apiFetch("/api/v1/medicine/summary"),
  });

  // Mutations
  const addMut = useMutation({
    mutationFn: () => apiFetch("/api/v1/medicine/", {
      method: "POST",
      body: JSON.stringify({
        name: addForm.name,
        generic_name: addForm.generic_name || null,
        medicine_type: addForm.medicine_type,
        manufacturer: addForm.manufacturer || null,
        batch_number: addForm.batch_number || null,
        quantity: parseFloat(addForm.quantity) || 0,
        unit: addForm.unit,
        min_stock_quantity: parseFloat(addForm.min_stock_quantity) || 10,
        purchase_price: addForm.purchase_price ? parseFloat(addForm.purchase_price) : null,
        expiry_date: addForm.expiry_date || null,
        dosage_instructions: addForm.dosage_instructions || null,
        notes: addForm.notes || null,
        species_applicable: addForm.species_applicable || null,
      }),
    }),
    onSuccess: () => {
      setMsg("✅ Dori qo'shildi!");
      setShowAddForm(false);
      setAddForm({
        name: "", generic_name: "", medicine_type: "antibiotic",
        manufacturer: "", batch_number: "", quantity: "", unit: "ml",
        min_stock_quantity: "10", purchase_price: "", expiry_date: "",
        dosage_instructions: "", notes: "", species_applicable: "",
      });
      qc.invalidateQueries({ queryKey: ["medicine"] });
    },
    onError: (e: Error) => setMsg(`❌ ${e.message}`),
  });

  const restockMut = useMutation({
    mutationFn: (medicineId: number) => apiFetch(`/api/v1/medicine/${medicineId}/restock`, {
      method: "POST",
      body: JSON.stringify({
        quantity_to_add: parseFloat(restockForm.quantity_to_add),
        batch_number: restockForm.batch_number || null,
        expiry_date: restockForm.expiry_date || null,
        purchase_price: restockForm.purchase_price ? parseFloat(restockForm.purchase_price) : null,
        notes: restockForm.notes || null,
      }),
    }),
    onSuccess: () => {
      setMsg("✅ Ombor to'ldirildi!");
      setShowRestockModal(null);
      setRestockForm({ quantity_to_add: "", batch_number: "", expiry_date: "", purchase_price: "", notes: "" });
      qc.invalidateQueries({ queryKey: ["medicine"] });
    },
    onError: (e: Error) => setMsg(`❌ ${e.message}`),
  });

  const deactivateMut = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/v1/medicine/${id}`, { method: "DELETE" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medicine"] }); },
  });

  // Filtered items
  const displayItems = (() => {
    const all = medicines?.items ?? [];
    if (activeTab === "low") return summary?.low_stock_items ?? [];
    if (activeTab === "expiring") return [
      ...(summary?.expired_items ?? []),
      ...(summary?.expiring_soon_items ?? []),
    ];
    return all;
  })();

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E2E8F0",
    borderRadius: 14, padding: "18px 20px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 11px", borderRadius: 8, fontSize: 13,
    border: "1.5px solid #E2E8F0", outline: "none", fontFamily: "inherit",
  };

  return (
    <div style={{
      maxWidth: 1200, margin: "0 auto",
      padding: "24px 20px 72px",
      fontFamily: "'Outfit', system-ui, sans-serif", color: "#0F172A",
    }}>
      <style>{`@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}} *{box-sizing:border-box}`}</style>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, display: "flex", alignItems: "center", gap: 10 }}>
            <Pill size={24} color="#7C3AED" /> Dori-Darmon Ombori
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748B" }}>
            Veterinariya preparatlari va dori-darmonlar boshqaruvi
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600,
            background: "#7C3AED", color: "#fff", border: "none", cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <Plus size={15} /> Yangi dori qo'shish
        </button>
      </div>

      {/* Xabar */}
      {msg && (
        <div style={{
          padding: "10px 16px", borderRadius: 10, marginBottom: 16, fontSize: 13,
          background: msg.startsWith("✅") ? "#F0FDF4" : "#FEF2F2",
          color: msg.startsWith("✅") ? "#16A34A" : "#DC2626",
          border: `1px solid ${msg.startsWith("✅") ? "#BBF7D0" : "#FCA5A5"}`,
        }}>
          {msg} <button onClick={() => setMsg("")} style={{ background: "none", border: "none", cursor: "pointer", marginLeft: 8, fontSize: 16, opacity: .5 }}>×</button>
        </div>
      )}

      {/* KPI kartalar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 20 }}>
        {[
          ["Jami dorlar", summary?.total_medicines ?? 0, "#2563EB"],
          ["Kam qolganlar", summary?.low_stock_items?.length ?? 0, "#D97706"],
          ["Muddati o'tgan", summary?.expired_items?.length ?? 0, "#DC2626"],
          ["Tez tugaydi", summary?.expiring_soon_items?.length ?? 0, "#F59E0B"],
        ].map(([label, value, color]) => (
          <div key={label as string} style={{ ...card, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
              {label}
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, color: color as string }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Filter va qidiruv */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        {/* Tab filter */}
        <div style={{ display: "flex", gap: 2, background: "#F1F5F9", borderRadius: 10, padding: 3 }}>
          {[
            { key: "all", label: "Barchasi" },
            { key: "low", label: `⚠️ Kam (${summary?.low_stock_items?.length ?? 0})` },
            { key: "expiring", label: `⏰ Muddat (${(summary?.expired_items?.length ?? 0) + (summary?.expiring_soon_items?.length ?? 0)})` },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as any)}
              style={{
                padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 500,
                border: "none", cursor: "pointer", fontFamily: "inherit",
                background: activeTab === t.key ? "#fff" : "transparent",
                color: activeTab === t.key ? "#2563EB" : "#64748B",
                boxShadow: activeTab === t.key ? "0 1px 4px rgba(0,0,0,.08)" : "none",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Qidiruv */}
        <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94A3B8" }} />
          <input
            type="text" value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Dori nomi bo'yicha qidiruv..."
            style={{ ...inputStyle, paddingLeft: 32 }}
          />
        </div>

        {/* Tur filter */}
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          style={{ ...inputStyle, width: "auto", minWidth: 160 }}
        >
          <option value="">Barcha turlar</option>
          {Object.entries(TYPE_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>

        <button onClick={() => refetch()} style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "8px 14px", borderRadius: 9, fontSize: 13,
          background: "#F8FAFC", color: "#64748B",
          border: "1px solid #E2E8F0", cursor: "pointer", fontFamily: "inherit",
        }}>
          <RefreshCw size={13} /> Yangilash
        </button>
      </div>

      {/* Dorlar jadvali */}
      <div style={card}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1.5px solid #E2E8F0" }}>
                {["Dori nomi", "Tur", "Qoldiq", "Min. qoldiq", "Muddat", "Narxi", "Holat", "Amallar"].map(h => (
                  <th key={h} style={{
                    padding: "10px 12px", textAlign: "left",
                    fontSize: 11, color: "#94A3B8", fontWeight: 600,
                    textTransform: "uppercase", letterSpacing: ".05em",
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={8} style={{ padding: "40px", textAlign: "center", color: "#94A3B8" }}>Yuklanmoqda...</td></tr>
              ) : displayItems.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: "50px", textAlign: "center", color: "#94A3B8" }}>
                    <Pill size={36} style={{ opacity: .2, display: "block", margin: "0 auto 12px" }} />
                    <p style={{ margin: 0 }}>Dorlar topilmadi</p>
                  </td>
                </tr>
              ) : (
                displayItems.map(m => (
                  <tr key={m.id} style={{
                    borderBottom: "1px solid #F8FAFC",
                    background: m.is_expired ? "#FEF2F2" : m.is_low_stock ? "#FFFBEB" : "transparent",
                  }}>
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ fontWeight: 600, color: "#0F172A" }}>{m.name}</div>
                      {m.generic_name && (
                        <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>{m.generic_name}</div>
                      )}
                      {m.manufacturer && (
                        <div style={{ fontSize: 11, color: "#64748B" }}>{m.manufacturer}</div>
                      )}
                    </td>
                    <td style={{ padding: "10px 12px", color: "#64748B" }}>
                      {TYPE_LABELS[m.medicine_type] ?? m.medicine_type}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <span style={{
                        fontWeight: 700,
                        color: m.is_low_stock ? "#D97706" : "#16A34A",
                      }}>
                        {m.quantity} {UNIT_LABELS[m.unit] ?? m.unit}
                      </span>
                    </td>
                    <td style={{ padding: "10px 12px", color: "#64748B" }}>
                      {m.min_stock_quantity} {UNIT_LABELS[m.unit] ?? m.unit}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      {m.expiry_date ? (
                        <span style={{
                          color: m.is_expired ? "#DC2626" : (m.days_until_expiry ?? 999) < 30 ? "#D97706" : "#16A34A",
                          fontWeight: 500,
                        }}>
                          {format(new Date(m.expiry_date), "dd.MM.yyyy")}
                          {m.is_expired && " ⚠️"}
                          {!m.is_expired && (m.days_until_expiry ?? 999) < 30 && ` (${m.days_until_expiry} kun)`}
                        </span>
                      ) : "—"}
                    </td>
                    <td style={{ padding: "10px 12px", color: "#64748B" }}>
                      {m.purchase_price ? `${m.purchase_price.toLocaleString()} so'm` : "—"}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      {m.is_expired ? (
                        <span style={{ padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "#FEE2E2", color: "#DC2626" }}>
                          Muddati o'tgan
                        </span>
                      ) : m.is_low_stock ? (
                        <span style={{ padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "#FEF3C7", color: "#92400E" }}>
                          Kam qoldi
                        </span>
                      ) : (
                        <span style={{ padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: "#F0FDF4", color: "#16A34A" }}>
                          Yaxshi
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          onClick={() => { setShowRestockModal(m); setRestockForm({ quantity_to_add: "", batch_number: m.batch_number ?? "", expiry_date: m.expiry_date ?? "", purchase_price: "", notes: "" }); }}
                          style={{
                            padding: "4px 10px", borderRadius: 7, fontSize: 12, fontWeight: 500,
                            background: "#EEF2FF", color: "#4F46E5",
                            border: "none", cursor: "pointer", fontFamily: "inherit",
                          }}
                        >
                          To'ldirish
                        </button>
                        <button
                          onClick={() => { if (window.confirm(`"${m.name}" ni arxivlashni tasdiqlaysizmi?`)) deactivateMut.mutate(m.id); }}
                          style={{
                            padding: "4px 10px", borderRadius: 7, fontSize: 12, fontWeight: 500,
                            background: "#F1F5F9", color: "#64748B",
                            border: "none", cursor: "pointer", fontFamily: "inherit",
                          }}
                        >
                          Arxiv
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Yangi dori formi modali */}
      {showAddForm && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 9999, padding: 16,
        }}>
          <div style={{
            background: "#fff", borderRadius: 18, padding: 28,
            width: "100%", maxWidth: 600, maxHeight: "90vh", overflowY: "auto",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Yangi dori qo'shish</h2>
              <button onClick={() => setShowAddForm(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94A3B8" }}>
                <X size={20} />
              </button>
            </div>

            {msg && (
              <div style={{
                padding: "8px 12px", borderRadius: 8, marginBottom: 14, fontSize: 13,
                background: msg.startsWith("✅") ? "#F0FDF4" : "#FEF2F2",
                color: msg.startsWith("✅") ? "#16A34A" : "#DC2626",
              }}>{msg}</div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { label: "Dori nomi *", key: "name", type: "text", full: true },
                { label: "Umumiy nomi", key: "generic_name", type: "text", full: true },
                { label: "Ishlab chiqaruvchi", key: "manufacturer", type: "text" },
                { label: "Partiya raqami", key: "batch_number", type: "text" },
                { label: "Miqdor *", key: "quantity", type: "number" },
                { label: "Minimal qoldiq", key: "min_stock_quantity", type: "number" },
                { label: "Narx (so'm/birlik)", key: "purchase_price", type: "number" },
                { label: "Yaroqlilik muddati", key: "expiry_date", type: "date" },
              ].map(({ label, key, type, full }) => (
                <div key={key} style={full ? { gridColumn: "1 / -1" } : {}}>
                  <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>{label}</label>
                  <input
                    type={type}
                    value={(addForm as any)[key]}
                    onChange={e => setAddForm(f => ({ ...f, [key]: e.target.value }))}
                    style={inputStyle}
                    min={type === "number" ? "0" : undefined}
                    step={type === "number" ? "0.01" : undefined}
                  />
                </div>
              ))}

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>Dori turi *</label>
                <select value={addForm.medicine_type} onChange={e => setAddForm(f => ({ ...f, medicine_type: e.target.value }))} style={inputStyle}>
                  {Object.entries(TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>O'lchov birligi</label>
                <select value={addForm.unit} onChange={e => setAddForm(f => ({ ...f, unit: e.target.value }))} style={inputStyle}>
                  {Object.entries(UNIT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>

              <div style={{ gridColumn: "1 / -1" }}>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>Berish ko'rsatmasi</label>
                <textarea value={addForm.dosage_instructions} onChange={e => setAddForm(f => ({ ...f, dosage_instructions: e.target.value }))}
                  rows={2} style={{ ...inputStyle, resize: "vertical" }} placeholder="Doza va berish yo'li haqida..." />
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                onClick={() => { if (!addForm.name) { setMsg("❌ Dori nomi majburiy"); return; } setMsg(""); addMut.mutate(); }}
                disabled={addMut.isPending}
                style={{
                  padding: "10px 22px", borderRadius: 10, fontSize: 14, fontWeight: 600,
                  background: "#7C3AED", color: "#fff", border: "none",
                  cursor: addMut.isPending ? "not-allowed" : "pointer",
                  opacity: addMut.isPending ? .6 : 1, fontFamily: "inherit",
                }}
              >
                {addMut.isPending ? "Saqlanmoqda..." : "Saqlash"}
              </button>
              <button onClick={() => { setShowAddForm(false); setMsg(""); }}
                style={{ padding: "10px 18px", borderRadius: 10, fontSize: 14, background: "#F1F5F9", color: "#64748B", border: "1px solid #E2E8F0", cursor: "pointer", fontFamily: "inherit" }}>
                Bekor
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ombor to'ldirish modali */}
      {showRestockModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 9999, padding: 16,
        }}>
          <div style={{ background: "#fff", borderRadius: 18, padding: 28, width: "100%", maxWidth: 440 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
                Ombor to'ldirish — {showRestockModal.name}
              </h2>
              <button onClick={() => setShowRestockModal(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94A3B8" }}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: 13, color: "#64748B", marginBottom: 16 }}>
              Joriy qoldiq: <strong>{showRestockModal.quantity} {showRestockModal.unit}</strong>
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                { label: "Qo'shiladigan miqdor *", key: "quantity_to_add", type: "number" },
                { label: "Partiya raqami", key: "batch_number", type: "text" },
                { label: "Yangi muddat", key: "expiry_date", type: "date" },
                { label: "Xarid narxi (so'm)", key: "purchase_price", type: "number" },
                { label: "Izoh", key: "notes", type: "text" },
              ].map(({ label, key, type }) => (
                <div key={key}>
                  <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>{label}</label>
                  <input
                    type={type} value={(restockForm as any)[key]}
                    onChange={e => setRestockForm(f => ({ ...f, [key]: e.target.value }))}
                    style={inputStyle} min={type === "number" ? "0" : undefined} step={type === "number" ? "0.01" : undefined}
                  />
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                onClick={() => {
                  if (!restockForm.quantity_to_add) { setMsg("❌ Miqdor kiriting"); return; }
                  restockMut.mutate(showRestockModal.id);
                }}
                disabled={restockMut.isPending}
                style={{
                  padding: "9px 20px", borderRadius: 9, fontSize: 13, fontWeight: 600,
                  background: "#7C3AED", color: "#fff", border: "none",
                  cursor: restockMut.isPending ? "not-allowed" : "pointer",
                  opacity: restockMut.isPending ? .6 : 1, fontFamily: "inherit",
                }}
              >
                {restockMut.isPending ? "Saqlanmoqda..." : "To'ldirish"}
              </button>
              <button onClick={() => setShowRestockModal(null)}
                style={{ padding: "9px 16px", borderRadius: 9, fontSize: 13, background: "#F1F5F9", color: "#64748B", border: "1px solid #E2E8F0", cursor: "pointer", fontFamily: "inherit" }}>
                Bekor
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}