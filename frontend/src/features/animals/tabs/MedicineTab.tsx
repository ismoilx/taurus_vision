/**
 * Taurus Vision — Dori Tarixi Tab Komponenti
 *
 * AnimalDetailPage ichida — bitta jonivorga berilgan dorlar tarixi.
 * Ombordan dori berish formi + tarix jadvali.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pill, Plus, X, AlertTriangle, Clock } from "lucide-react";
import { format } from "date-fns";
import { apiFetch } from "../../../utils/apiFetch";

// ── Types ──────────────────────────────────────────────────────────────────

interface MedicineItem {
  id: number;
  name: string;
  medicine_type: string;
  quantity: number;
  unit: string;
  is_low_stock: boolean;
  is_expired: boolean;
}

interface UsageRecord {
  id: number;
  medicine_id: number;
  medicine_name?: string;
  medicine_unit?: string;
  given_date: string;
  quantity_given: number;
  admin_route?: string;
  given_by?: string;
  next_dose_date?: string;
  withdrawal_date?: string;
  is_in_withdrawal: boolean;
  notes?: string;
}

interface UsageListResponse {
  items: UsageRecord[];
  total: number;
}

interface Props {
  animalId: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const ROUTE_LABELS: Record<string, string> = {
  injection_im: "Mushak ichiga",
  injection_iv: "Vena ichiga",
  injection_sc: "Teri ostiga",
  oral: "Og'iz orqali",
  topical: "Tashqi",
  intranasal: "Burun orqali",
  other: "Boshqa",
};

// ── Component ──────────────────────────────────────────────────────────────

export function MedicineTab({ animalId }: Props) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    medicine_id: "",
    quantity_given: "",
    admin_route: "injection_im",
    given_by: "",
    next_dose_date: "",
    withdrawal_date: "",
    notes: "",
  });

  // Barcha dorlar (ombordan tanlab olish uchun)
  const { data: medicines } = useQuery<{ items: MedicineItem[]; total: number }>({
    queryKey: ["medicine", "list"],
    queryFn: () => apiFetch("/api/v1/medicine/?active_only=true&page_size=100"),
  });

  // Jonivorning dori tarixi
  const { data: usages } = useQuery<UsageListResponse>({
    queryKey: ["medicine", "usage", animalId],
    queryFn: () => apiFetch(`/api/v1/medicine/usage/animal/${animalId}?page_size=50`),
  });

  const giveMut = useMutation({
    mutationFn: () => apiFetch("/api/v1/medicine/usage/", {
      method: "POST",
      body: JSON.stringify({
        medicine_id: parseInt(form.medicine_id),
        animal_id: animalId,
        quantity_given: parseFloat(form.quantity_given),
        admin_route: form.admin_route || null,
        given_by: form.given_by || null,
        next_dose_date: form.next_dose_date || null,
        withdrawal_date: form.withdrawal_date || null,
        notes: form.notes || null,
      }),
    }),
    onSuccess: () => {
      setMsg("✅ Dori berildi va yozuv saqlandi!");
      setShowForm(false);
      setForm({
        medicine_id: "", quantity_given: "", admin_route: "injection_im",
        given_by: "", next_dose_date: "", withdrawal_date: "", notes: "",
      });
      qc.invalidateQueries({ queryKey: ["medicine", "usage", animalId] });
      qc.invalidateQueries({ queryKey: ["medicine", "list"] });
    },
    onError: (e: Error) => setMsg(`❌ ${e.message}`),
  });

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E2E8F0",
    borderRadius: 14, padding: "18px 20px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 11px", borderRadius: 8, fontSize: 13,
    border: "1.5px solid #E2E8F0", outline: "none", fontFamily: "inherit",
  };

  const selectedMedicine = medicines?.items.find(m => m.id === parseInt(form.medicine_id));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, animation: "fadein .25s" }}>

      {/* Karantin ogohlantirishlari */}
      {(usages?.items ?? []).filter(u => u.is_in_withdrawal).length > 0 && (
        <div style={{
          padding: "12px 16px", borderRadius: 12, background: "#FFFBEB",
          border: "1px solid #FDE68A", display: "flex", alignItems: "center", gap: 10,
        }}>
          <AlertTriangle size={16} color="#D97706" />
          <span style={{ fontSize: 13, color: "#92400E", fontWeight: 500 }}>
            Bu jonivor hozir sut/go'sht karantin davrida
          </span>
        </div>
      )}

      {/* Asosiy panel */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Dori Berish Tarixi</h3>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "7px 14px", borderRadius: 9, fontSize: 13, fontWeight: 500,
              background: showForm ? "#F1F5F9" : "#7C3AED", color: showForm ? "#64748B" : "#fff",
              border: "none", cursor: "pointer", fontFamily: "inherit",
            }}
          >
            {showForm ? <><X size={13} /> Yopish</> : <><Plus size={13} /> Dori ber</>}
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

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
              {/* Dori tanlash */}
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Dori tanlang *
                </label>
                <select
                  value={form.medicine_id}
                  onChange={e => setForm(f => ({ ...f, medicine_id: e.target.value }))}
                  style={inputStyle}
                >
                  <option value="">— Dori tanlang —</option>
                  {(medicines?.items ?? []).map(m => (
                    <option key={m.id} value={m.id} disabled={m.is_expired}>
                      {m.name} ({m.quantity} {m.unit})
                      {m.is_expired ? " ⚠️ Muddati o'tgan" : ""}
                      {m.is_low_stock ? " ⚠️ Kam" : ""}
                    </option>
                  ))}
                </select>
                {selectedMedicine && (
                  <div style={{ fontSize: 11, color: "#64748B", marginTop: 4 }}>
                    Omborда: {selectedMedicine.quantity} {selectedMedicine.unit}
                    {selectedMedicine.is_low_stock && (
                      <span style={{ color: "#D97706", marginLeft: 8 }}>⚠️ Kam qoldi</span>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Miqdor * {selectedMedicine && `(${selectedMedicine.unit})`}
                </label>
                <input
                  type="number" min="0" step="0.01"
                  value={form.quantity_given}
                  onChange={e => setForm(f => ({ ...f, quantity_given: e.target.value }))}
                  placeholder="0.0"
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Berish yo'li
                </label>
                <select
                  value={form.admin_route}
                  onChange={e => setForm(f => ({ ...f, admin_route: e.target.value }))}
                  style={inputStyle}
                >
                  {Object.entries(ROUTE_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Kim berdi
                </label>
                <input
                  type="text" value={form.given_by}
                  onChange={e => setForm(f => ({ ...f, given_by: e.target.value }))}
                  placeholder="Veterinar ismi"
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Keyingi doza
                </label>
                <input
                  type="date" value={form.next_dose_date}
                  onChange={e => setForm(f => ({ ...f, next_dose_date: e.target.value }))}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>
                  Karantin tugash (sut/go'sht)
                </label>
                <input
                  type="date" value={form.withdrawal_date}
                  onChange={e => setForm(f => ({ ...f, withdrawal_date: e.target.value }))}
                  style={inputStyle}
                />
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 12, color: "#64748B", fontWeight: 500, display: "block", marginBottom: 4 }}>Izoh</label>
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
                  if (!form.medicine_id) { setMsg("❌ Dori tanlang"); return; }
                  if (!form.quantity_given) { setMsg("❌ Miqdor kiriting"); return; }
                  setMsg("");
                  giveMut.mutate();
                }}
                disabled={giveMut.isPending}
                style={{
                  padding: "9px 20px", borderRadius: 9, fontSize: 13, fontWeight: 600,
                  background: "#7C3AED", color: "#fff", border: "none",
                  cursor: giveMut.isPending ? "not-allowed" : "pointer",
                  opacity: giveMut.isPending ? .6 : 1, fontFamily: "inherit",
                }}
              >
                {giveMut.isPending ? "Saqlanmoqda..." : "Saqlash"}
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

        {/* Tarix jadvali */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1.5px solid #E2E8F0" }}>
                {["Sana", "Dori", "Miqdor", "Yo'li", "Kim berdi", "Keyingi doza", "Karantin", "Holat"].map(h => (
                  <th key={h} style={{
                    padding: "8px 10px", textAlign: "left",
                    fontSize: 11, color: "#94A3B8", fontWeight: 600,
                    textTransform: "uppercase", letterSpacing: ".05em",
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(usages?.items ?? []).map(u => (
                <tr key={u.id} style={{
                  borderBottom: "1px solid #F8FAFC",
                  background: u.is_in_withdrawal ? "#FFFBEB" : "transparent",
                }}>
                  <td style={{ padding: "9px 10px", fontWeight: 500 }}>
                    {format(new Date(u.given_date), "dd.MM.yyyy HH:mm")}
                  </td>
                  <td style={{ padding: "9px 10px", fontWeight: 600, color: "#7C3AED" }}>
                    {u.medicine_name ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px" }}>
                    {u.quantity_given} {u.medicine_unit ?? ""}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {u.admin_route ? (ROUTE_LABELS[u.admin_route] ?? u.admin_route) : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {u.given_by ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {u.next_dose_date
                      ? format(new Date(u.next_dose_date), "dd.MM.yyyy")
                      : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", color: "#64748B" }}>
                    {u.withdrawal_date
                      ? format(new Date(u.withdrawal_date), "dd.MM.yyyy")
                      : "—"}
                  </td>
                  <td style={{ padding: "9px 10px" }}>
                    {u.is_in_withdrawal ? (
                      <span style={{
                        padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600,
                        background: "#FEF3C7", color: "#92400E",
                      }}>
                        Karantin
                      </span>
                    ) : (
                      <span style={{
                        padding: "2px 8px", borderRadius: 99, fontSize: 11, fontWeight: 600,
                        background: "#F0FDF4", color: "#16A34A",
                      }}>
                        Tugagan
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {(usages?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: "40px 10px", textAlign: "center", color: "#94A3B8" }}>
                    <Pill size={28} style={{ opacity: .3, display: "block", margin: "0 auto 8px" }} />
                    Hali dori berilmagan
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