/**
 * Taurus Vision — Sut Ishlab Chiqarish Sahifasi
 *
 * Ferma bo'yicha sut statistikasi, kunlik trend,
 * va barcha sut beruvchi jonivorlar xulosasi.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar,
} from "recharts";
import { Droplets, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { format, parseISO } from "date-fns";
import { apiFetch } from "../utils/apiFetch";

interface FarmMilkSummary {
  today_total_kg: number;
  this_month_kg: number;
  last_month_kg: number;
  active_dairy_animals: number;
  avg_per_animal_kg: number;
  daily_trend: { date: string; total_kg: number; animal_count: number; avg_fat?: number }[];
}

export default function MilkProductionPage() {
  const [days, setDays] = useState(30);

  const { data: summary, isLoading } = useQuery<FarmMilkSummary>({
    queryKey: ["milk", "farm", "summary"],
    queryFn: () => apiFetch("/api/v1/milk/farm/summary"),
  });

  const { data: trend = [] } = useQuery<any[]>({
    queryKey: ["milk", "farm", "trend", days],
    queryFn: () => apiFetch(`/api/v1/milk/farm/daily?days=${days}`),
  });

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E2E8F0",
    borderRadius: 14, padding: "18px 20px",
  };

  const monthChange = summary
    ? summary.last_month_kg > 0
      ? ((summary.this_month_kg - summary.last_month_kg) / summary.last_month_kg) * 100
      : 0
    : 0;

  return (
    <div style={{
      maxWidth: 1200, margin: "0 auto",
      padding: "24px 20px 72px",
      fontFamily: "'Outfit', system-ui, sans-serif", color: "#0F172A",
    }}>
      <style>{`@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}} *{box-sizing:border-box}`}</style>

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
          { label: "Bugun", value: `${summary?.today_total_kg ?? 0} kg`, color: "#2563EB" },
          { label: "Bu oy", value: `${summary?.this_month_kg?.toFixed(0) ?? 0} kg`, color: "#7C3AED" },
          { label: "O'tgan oy", value: `${summary?.last_month_kg?.toFixed(0) ?? 0} kg`, color: "#64748B" },
          { label: "Faol jonivoz", value: `${summary?.active_dairy_animals ?? 0} ta`, color: "#059669" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...card, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
              {label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}

        {/* Oylik taqqoslov */}
        <div style={{ ...card, padding: "14px 16px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 6 }}>
            Oy taqqoslovi
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {monthChange > 0
              ? <><TrendingUp size={18} color="#16A34A" /><span style={{ fontSize: 18, fontWeight: 700, color: "#16A34A" }}>+{monthChange.toFixed(1)}%</span></>
              : monthChange < 0
              ? <><TrendingDown size={18} color="#DC2626" /><span style={{ fontSize: 18, fontWeight: 700, color: "#DC2626" }}>{monthChange.toFixed(1)}%</span></>
              : <><Minus size={18} color="#6B7280" /><span style={{ fontSize: 18, fontWeight: 700, color: "#6B7280" }}>0%</span></>
            }
          </div>
        </div>
      </div>

      {/* Trend grafik */}
      <div style={{ ...card, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Kunlik sut trendi</h3>
          <div style={{ display: "flex", gap: 4, background: "#F1F5F9", borderRadius: 8, padding: 3 }}>
            {[7, 14, 30, 60].map(d => (
              <button key={d}
                onClick={() => setDays(d)}
                style={{
                  padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 500,
                  border: "none", cursor: "pointer", fontFamily: "inherit",
                  background: days === d ? "#fff" : "transparent",
                  color: days === d ? "#2563EB" : "#64748B",
                  boxShadow: days === d ? "0 1px 3px rgba(0,0,0,.08)" : "none",
                }}>
                {d} kun
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div style={{ height: 250, display: "grid", placeItems: "center", color: "#94A3B8" }}>Yuklanmoqda...</div>
        ) : trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={trend}>
              <defs>
                <linearGradient id="milkAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis
                dataKey="date"
                tickFormatter={d => format(parseISO(d), "dd/MM")}
                tick={{ fontSize: 11, fill: "#94A3B8" }}
              />
              <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} unit=" kg" width={55} />
              <Tooltip
                formatter={(v: number, name: string) => [
                  name === "total_kg" ? `${v} kg` : `${v} ta`,
                  name === "total_kg" ? "Jami sut" : "Jonivorlar",
                ]}
                labelFormatter={d => format(parseISO(d as string), "dd.MM.yyyy")}
              />
              <Area
                type="monotone" dataKey="total_kg"
                stroke="#2563EB" strokeWidth={2}
                fill="url(#milkAreaGrad)"
                dot={{ fill: "#2563EB", r: 3 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 250, display: "grid", placeItems: "center", color: "#94A3B8" }}>
            <div style={{ textAlign: "center" }}>
              <Droplets size={36} style={{ opacity: .2, display: "block", margin: "0 auto 10px" }} />
              <p style={{ fontSize: 14 }}>Hali sut ma'lumoti yo'q</p>
              <p style={{ fontSize: 12, marginTop: 4 }}>Jonivor tafsilot sahifasidan sut yozuvlarini qo'shing</p>
            </div>
          </div>
        )}
      </div>

      {/* Jonivorlar bo'yicha jadval */}
      <div style={card}>
        <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 16px" }}>
          Jonivorlar bo'yicha sut (bu oy)
        </h3>
        <p style={{ fontSize: 13, color: "#94A3B8", textAlign: "center", padding: "30px 0" }}>
          Har bir jonivorning sut ko'rsatkichlarini ko'rish uchun<br />
          <strong>Jonivorlar</strong> → Jonivor tafsiloti → <strong>🥛 Sut</strong> bo'limiga o'ting
        </p>
      </div>
    </div>
  );
}