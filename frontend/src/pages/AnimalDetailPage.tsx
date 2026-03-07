import { useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Camera, Upload, Star, Scan, Trash2,
  ZoomIn, X, RefreshCw, CheckCircle, AlertTriangle,
  TrendingUp, TrendingDown, Minus, Scale, Activity,
  Heart, Plus, Download, ChevronRight, Droplets, Pill,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import { apiFetch } from "../utils/apiFetch";
import config from "../config";
import { useIsMobile } from "../hooks/useResponsive";
import { MilkTab } from "../features/animals/tabs/MilkTab";
import { MedicineTab } from "../features/animals/tabs/MedicineTab";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Photo {
  id: number;
  file_name: string;
  file_size?: number;
  url: string;
  is_profile: boolean;
  is_muzzle: boolean;
  created_at: string;
}

interface PhotosResp {
  animal_id: number;
  photos: Photo[];
}

interface Animal {
  id: number; tag_id: string; species: string; gender: string;
  status: string; breed?: string; notes?: string;
  acquisition_date?: string; birth_date?: string;
  category?: string;
  profile_image?: string | null; muzzle_image?: string | null;
  total_detections: number; last_detected_at: string | null;
  created_at: string;
}

interface WeightMeasurement {
  id: number; estimated_weight_kg: number;
  confidence_score: number; camera_id: string; timestamp: string;
}

interface ADILog {
  id: number; calculation_date: string;
  adi_score: number; category: string;
  scores?: {
    activity_score?: number; feeding_score?: number;
    drinking_score?: number; movement_score?: number;
    growth_score?: number;
  };
}

interface ADITrend {
  trend: { date: string; score: number; category: string }[];
  current?: ADILog;
}

interface HealthRecord {
  id: number; record_type: string; severity: string;
  diagnosis: string; symptoms?: string; treatment?: string;
  medication?: string; veterinarian?: string; cost?: number;
  recorded_at: string; is_resolved: boolean;
}

interface HealthResp { records: HealthRecord[]; total: number; }

// ─── Constants ───────────────────────────────────────────────────────────────

const CAT_STYLE = {
  healthy:  { label: "Sog'lom",  color: "#16A34A", bg: "#F0FDF4", ring: "#22C55E" },
  average:  { label: "O'rtacha", color: "#D97706", bg: "#FFFBEB", ring: "#FBBF24" },
  warning:  { label: "Diqqat",    color: "#EA580C", bg: "#FFF7ED", ring: "#FB923C" },
  critical: { label: "Kritik",    color: "#DC2626", bg: "#FEF2F2", ring: "#F87171" },
} as const;

const RECORD_TYPE_LABELS: Record<string, string> = {
  checkup: "Tekshiruv", treatment: "Davolash", vaccination: "Emlash",
  injury: "Shikast", surgery: "Operatsiya", illness: "Kasallik", other: "Boshqa",
};

// ─── Image URL helper ─────────────────────────────────────────────────────────
// config.apiUrl is "" (empty) → relative URL works with Vite proxy
const photoUrl = (id: number) =>
  `${config.apiUrl || ""}/api/v1/animals/photos/file/${id}`;

// ─── Spinner ──────────────────────────────────────────────────────────────────

function Spinner({ size = 20, color = "#2563EB" }: { size?: number; color?: string }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size, borderRadius: "50%",
      border: `2.5px solid ${color}22`, borderTopColor: color,
      animation: "spin .65s linear infinite", flexShrink: 0,
    }} />
  );
}

// ─── AvatarSlot — profil/muzzle rasm slotu ────────────────────────────────────

function AvatarSlot({
  label, sublabel, photoId, accentColor, borderColor, icon: Icon,
  onClick,
}: {
  label: string; sublabel: string;
  photoId?: number | null;
  accentColor: string; borderColor: string;
  icon: React.ElementType;
  onClick: () => void;
}) {
  const [err, setErr] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      {/* Image box */}
      <div
        role="button"
        onClick={onClick}
        title={`${label} ni o'zgartirish`}
        style={{
          width: 120, height: 120, borderRadius: 20, overflow: "hidden",
          border: `3px solid ${photoId && !err ? accentColor : "#D1D5DB"}`,
          background: "#F9FAFB", cursor: "pointer", position: "relative",
          boxShadow: photoId && !err
            ? `0 0 0 4px ${accentColor}22, 0 4px 20px ${accentColor}33`
            : "0 2px 8px rgba(0,0,0,0.08)",
          transition: "box-shadow .2s, transform .2s",
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.transform = "scale(1.04)";
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.transform = "";
        }}
      >
        {photoId && !err ? (
          <img
            src={photoUrl(photoId)}
            alt={label}
            onError={() => setErr(true)}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <div style={{
            width: "100%", height: "100%", display: "flex",
            flexDirection: "column", alignItems: "center", justifyContent: "center",
            gap: 6, background: "#F1F5F9",
          }}>
            <Icon size={28} color="#9CA3AF" />
            <span style={{ fontSize: 10, color: "#9CA3AF", textAlign: "center", padding: "0 8px" }}>
              Tanlash uchun bosing
            </span>
          </div>
        )}
        {/* Edit overlay */}
        <div style={{
          position: "absolute", inset: 0,
          background: "linear-gradient(to top, rgba(0,0,0,.5) 0%, transparent 55%)",
          display: "flex", alignItems: "flex-end", justifyContent: "center",
          paddingBottom: 8, opacity: 0, transition: "opacity .2s",
        }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.opacity = "1"}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.opacity = "0"}
        >
          <Camera size={16} color="#fff" />
        </div>
      </div>

      {/* Labels */}
      <div style={{ textAlign: "center" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600,
          background: photoId && !err ? `${accentColor}18` : "#F1F5F9",
          color: photoId && !err ? accentColor : "#6B7280",
          border: `1px solid ${photoId && !err ? `${accentColor}44` : "#E5E7EB"}`,
          cursor: "pointer",
        }} onClick={onClick}>
          <Icon size={10} />
          {photoId && !err ? "Almashtirish" : "Tanlash"}
        </div>
        <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 4 }}>{label}</div>
        <div style={{ fontSize: 9, color: "#C4C9D4" }}>{sublabel}</div>
      </div>
    </div>
  );
}

// ─── Lightbox ─────────────────────────────────────────────────────────────────

function Lightbox({ photoId, onClose }: { photoId: number; onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,.88)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        animation: "fadein .15s ease",
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: "absolute", top: 20, right: 20, width: 40, height: 40,
          borderRadius: "50%", border: "2px solid rgba(255,255,255,.25)",
          background: "rgba(255,255,255,.1)", color: "#fff",
          cursor: "pointer", display: "grid", placeItems: "center",
        }}
      >
        <X size={18} />
      </button>
      <img
        src={photoUrl(photoId)}
        alt=""
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: "92vw", maxHeight: "92vh", borderRadius: 12,
          objectFit: "contain", boxShadow: "0 32px 80px rgba(0,0,0,.6)",
          animation: "fadein .2s ease",
        }}
      />
    </div>
  );
}

// ─── Picker Modal ─────────────────────────────────────────────────────────────

function PickerModal({
  mode, photos, onSelect, onClose,
}: {
  mode: "profile" | "muzzle";
  photos: Photo[];
  onSelect: (p: Photo) => void;
  onClose: () => void;
}) {
  const isProfile = mode === "profile";
  const accentColor = isProfile ? "#2563EB" : "#7C3AED";
  const currentId = photos.find(p => isProfile ? p.is_profile : p.is_muzzle)?.id;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 8000,
        background: "rgba(15,23,42,.72)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20, animation: "fadein .15s ease",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "#fff", borderRadius: 20, width: "100%", maxWidth: 640,
          maxHeight: "82vh", display: "flex", flexDirection: "column",
          boxShadow: "0 32px 80px rgba(0,0,0,.28)",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "20px 24px 16px", borderBottom: "1px solid #F1F5F9",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0F172A" }}>
              {isProfile ? "📸 Profil rasmini tanlang" : "🔬 Tumshuq (Muzzle) rasmini tanlang"}
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94A3B8" }}>
              {isProfile
                ? "Jonivorning asosiy ko'rinish rasmi — ro'yxat, hisobotlarda ko'rinadi"
                : "AI identifikatsiya uchun ishlatiladigan tumshuq rasmi"}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: "50%", border: "none",
              background: "#F1F5F9", cursor: "pointer", display: "grid", placeItems: "center",
            }}
          >
            <X size={15} color="#64748B" />
          </button>
        </div>

        {/* Grid */}
        <div style={{ overflowY: "auto", padding: 20, flex: 1 }}>
          {photos.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <Camera size={40} color="#CBD5E1" style={{ margin: "0 auto 12px", display: "block" }} />
              <p style={{ color: "#94A3B8", fontSize: 14 }}>
                Hali rasm yuklanmagan. Avval rasm yuklang.
              </p>
            </div>
          ) : (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(148px, 1fr))",
              gap: 12,
            }}>
              {photos.map(p => {
                const isCurrent = p.id === currentId;
                const [imgErr, setImgErr] = useState(false);
                return (
                  <div
                    key={p.id}
                    onClick={() => onSelect(p)}
                    style={{
                      borderRadius: 14, overflow: "hidden", cursor: "pointer",
                      border: `${isCurrent ? 3 : 2}px solid ${isCurrent ? accentColor : "#E2E8F0"}`,
                      boxShadow: isCurrent ? `0 0 0 3px ${accentColor}33` : "none",
                      transition: "all .15s", background: "#F8FAFC",
                    }}
                    onMouseEnter={e => {
                      if (!isCurrent) {
                        (e.currentTarget as HTMLElement).style.borderColor = `${accentColor}88`;
                        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
                        (e.currentTarget as HTMLElement).style.boxShadow = "0 6px 20px rgba(0,0,0,.1)";
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isCurrent) {
                        (e.currentTarget as HTMLElement).style.borderColor = "#E2E8F0";
                        (e.currentTarget as HTMLElement).style.transform = "";
                        (e.currentTarget as HTMLElement).style.boxShadow = "none";
                      }
                    }}
                  >
                    <div style={{ position: "relative", height: 128 }}>
                      {!imgErr ? (
                        <img
                          src={photoUrl(p.id)}
                          alt={p.file_name}
                          onError={() => setImgErr(true)}
                          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                      ) : (
                        <div style={{
                          width: "100%", height: "100%", background: "#F1F5F9",
                          display: "grid", placeItems: "center",
                        }}>
                          <Camera size={24} color="#CBD5E1" />
                        </div>
                      )}
                      {isCurrent && (
                        <div style={{
                          position: "absolute", top: 6, right: 6, width: 22, height: 22,
                          borderRadius: "50%", background: accentColor,
                          display: "grid", placeItems: "center",
                          border: "2px solid #fff",
                        }}>
                          <CheckCircle size={13} color="#fff" />
                        </div>
                      )}
                    </div>
                    <div style={{
                      padding: "6px 8px", background: "#fff",
                      borderTop: "1px solid #F1F5F9",
                      fontSize: 10, color: "#94A3B8", textAlign: "center",
                    }}>
                      {format(new Date(p.created_at), "dd.MM.yy HH:mm")}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{
          padding: "10px 24px 14px", borderTop: "1px solid #F1F5F9",
          flexShrink: 0, background: "#FAFAFA", borderRadius: "0 0 20px 20px",
        }}>
          <p style={{ margin: 0, fontSize: 11, color: "#94A3B8", textAlign: "center" }}>
            Kerakli rasmga bosing. Yangi rasm yuklash uchun "Rasmlar" tabiga o'ting.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Photo Card ───────────────────────────────────────────────────────────────

function PhotoCard({
  photo, onSetProfile, onSetMuzzle, onDelete, onZoom,
}: {
  photo: Photo;
  onSetProfile: () => void;
  onSetMuzzle: () => void;
  onDelete: () => void;
  onZoom: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [imgErr, setImgErr] = useState(false);

  const borderColor = photo.is_profile ? "#2563EB" : photo.is_muzzle ? "#7C3AED" : "#E2E8F0";
  const borderW = photo.is_profile || photo.is_muzzle ? "2.5px" : "1.5px";

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderRadius: 14, overflow: "hidden", background: "#fff",
        border: `${borderW} solid ${borderColor}`,
        boxShadow: hovered ? "0 10px 28px rgba(0,0,0,.12)" : "0 1px 4px rgba(0,0,0,.06)",
        transform: hovered ? "translateY(-3px)" : "none",
        transition: "all .2s",
      }}
    >
      {/* Image area */}
      <div style={{ position: "relative", height: 190, overflow: "hidden", background: "#F8FAFC" }}>
        {!imgErr ? (
          <img
            src={photoUrl(photo.id)}
            alt={photo.file_name}
            onError={() => setImgErr(true)}
            style={{
              width: "100%", height: "100%", objectFit: "cover", display: "block",
              transition: "transform .3s",
              transform: hovered ? "scale(1.06)" : "scale(1)",
            }}
          />
        ) : (
          <div style={{
            width: "100%", height: "100%", display: "flex",
            flexDirection: "column", alignItems: "center", justifyContent: "center",
            gap: 8, background: "#F1F5F9",
          }}>
            <Camera size={32} color="#CBD5E1" />
            <span style={{ fontSize: 10, color: "#94A3B8", textAlign: "center",
              padding: "0 12px", wordBreak: "break-word" }}>
              {photo.file_name}
            </span>
          </div>
        )}

        {/* Status badges */}
        <div style={{
          position: "absolute", top: 8, left: 8,
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {photo.is_profile && (
            <span style={{
              background: "#2563EB", color: "#fff", fontSize: 10, fontWeight: 700,
              padding: "2px 8px", borderRadius: 6,
              boxShadow: "0 2px 6px rgba(37,99,235,.4)",
            }}>
              ★ Profil
            </span>
          )}
          {photo.is_muzzle && (
            <span style={{
              background: "#7C3AED", color: "#fff", fontSize: 10, fontWeight: 700,
              padding: "2px 8px", borderRadius: 6,
              boxShadow: "0 2px 6px rgba(124,58,237,.4)",
            }}>
              ⬡ Muzzle
            </span>
          )}
        </div>

        {/* Hover dark overlay + zoom */}
        <div style={{
          position: "absolute", inset: 0,
          background: "linear-gradient(to top, rgba(0,0,0,.55) 0%, transparent 55%)",
          opacity: hovered ? 1 : 0, transition: "opacity .2s",
          display: "flex", alignItems: "flex-end", justifyContent: "space-between",
          padding: "0 10px 10px",
        }}>
          <button
            onClick={onZoom}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "5px 10px", borderRadius: 7, border: "1.5px solid rgba(255,255,255,.7)",
              background: "rgba(255,255,255,.15)", backdropFilter: "blur(4px)",
              color: "#fff", fontSize: 11, fontWeight: 500, cursor: "pointer",
            }}
          >
            <ZoomIn size={13} /> Ko'rish
          </button>
          <button
            onClick={onDelete}
            style={{
              width: 30, height: 30, borderRadius: "50%",
              border: "1.5px solid rgba(255,255,255,.7)",
              background: "rgba(239,68,68,.7)", backdropFilter: "blur(4px)",
              display: "grid", placeItems: "center", cursor: "pointer",
            }}
          >
            <Trash2 size={13} color="#fff" />
          </button>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{
        padding: "10px 10px 10px",
        background: photo.is_profile ? "#EFF6FF" : photo.is_muzzle ? "#F5F3FF" : "#FAFAFA",
        borderTop: `1px solid ${borderColor}44`,
        display: "flex", gap: 6,
      }}>
        <button
          onClick={onSetProfile}
          title={photo.is_profile ? "Profil rasmi (tanlangan)" : "Profil rasmi sifatida belgilash"}
          style={{
            flex: 1, height: 30, borderRadius: 8, border: "none", cursor: "pointer",
            background: photo.is_profile ? "#2563EB" : "#E0E7FF",
            color: photo.is_profile ? "#fff" : "#2563EB",
            fontSize: 11, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
            transition: "all .15s",
          }}
        >
          <Star size={11} fill={photo.is_profile ? "#fff" : "none"} />
          Profil
        </button>
        <button
          onClick={onSetMuzzle}
          title={photo.is_muzzle ? "Muzzle rasmi (tanlangan)" : "AI uchun muzzle rasmi"}
          style={{
            flex: 1, height: 30, borderRadius: 8, border: "none", cursor: "pointer",
            background: photo.is_muzzle ? "#7C3AED" : "#EDE9FE",
            color: photo.is_muzzle ? "#fff" : "#7C3AED",
            fontSize: 11, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
            transition: "all .15s",
          }}
        >
          <Scan size={11} />
          Muzzle
        </button>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function AnimalDetailPage() {
  const { id }   = useParams<{ id: string }>();
  const nav      = useNavigate();
  const qc       = useQueryClient();
  const numId    = Number(id);
  const isMobile = useIsMobile();

  const [tab, setTab] = useState<"overview"|"adi"|"weight"|"health"|"milk"|"medicine"|"photos">("overview");
  const [picker, setPicker]     = useState<"profile"|"muzzle"|null>(null);
  const [lightbox, setLightbox] = useState<number|null>(null);
  const [uploading, setUploading] = useState(0);
  const uploadRef = useRef<HTMLInputElement>(null);

  const [showHForm, setShowHForm] = useState(false);
  const [hMsg, setHMsg]           = useState("");
  const [hForm, setHForm] = useState({
    record_type: "checkup", severity: "normal", diagnosis: "",
    symptoms: "", treatment: "", medication: "", veterinarian: "", cost: "",
  });

  // ── Queries ────────────────────────────────────────────────────────────────

  const { data: animal, isLoading, isError, error } = useQuery({
    queryKey: ["animals", numId],
    queryFn:  () => apiFetch<Animal>(`/api/v1/animals/${id}`),
    enabled:  !!id,
  });

  const { data: photosData, refetch: refetchPhotos } = useQuery<PhotosResp>({
    queryKey: ["animal-photos", numId],
    queryFn:  () => apiFetch<PhotosResp>(`/api/v1/animals/${id}/photos`),
    enabled:  !!id,
  });

  const { data: weightsRaw } = useQuery({
    queryKey: ["weights", numId],
    queryFn:  () => apiFetch<any>(`/api/v1/weights/animal/${id}`),
    enabled:  !!id,
  });

  const { data: adiTrend } = useQuery({
    queryKey: ["adi", "trend", numId],
    queryFn:  () => apiFetch<ADITrend>(`/api/v1/adi/animal/${id}/trend?days=30`),
    enabled:  !!id,
  });

  const { data: embsRaw } = useQuery({
    queryKey: ["embeddings", numId],
    queryFn:  () => apiFetch<any[]>(`/api/v1/identification/${id}/embeddings`),
    enabled:  !!id,
  });

  const { data: healthResp, isFetching: healthFetching } = useQuery({
    queryKey: ["health", "records", numId],
    queryFn:  () => apiFetch<HealthResp>(`/api/v1/health/animals/${id}/records?skip=0&limit=50`),
    enabled:  !!id && tab === "health",
  });

  // ── Derived ────────────────────────────────────────────────────────────────

  const photos = photosData?.photos ?? [];
  const profilePhoto = photos.find(p => p.is_profile);
  const muzzlePhoto  = photos.find(p => p.is_muzzle);

  const weights: WeightMeasurement[] = Array.isArray(weightsRaw)
    ? weightsRaw : (weightsRaw?.items ?? []);

  const embedCount = embsRaw?.length ?? 0;
  const healthRecords = healthResp?.records ?? [];

  const adiNow = adiTrend?.current ?? null;
  const adiCfg = adiNow
    ? (CAT_STYLE[adiNow.category as keyof typeof CAT_STYLE] ?? CAT_STYLE.average)
    : null;

  const adiChartData = [...(adiTrend?.trend ?? [])]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-30)
    .map(a => ({ date: format(parseISO(a.date), "dd/MM"), score: +a.score.toFixed(1) }));

  const weightsSorted = [...weights]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const weightChartData = weightsSorted.slice(-30)
    .map(w => ({ date: format(new Date(w.timestamp), "dd/MM"), weight: +w.estimated_weight_kg.toFixed(1) }));

  const latestW = weightsSorted.length ? weightsSorted[weightsSorted.length - 1]?.estimated_weight_kg : null;
  const prev7W  = weightsSorted.length > 7 ? weightsSorted[weightsSorted.length - 8]?.estimated_weight_kg : null;
  const wChange = latestW != null && prev7W != null ? latestW - prev7W : null;

  const trend = (() => {
    const arr = adiTrend?.trend ?? [];
    if (arr.length < 3) return "stable";
    const d = arr[arr.length - 1].score - arr[0].score;
    return d > 5 ? "improving" : d < -5 ? "declining" : "stable";
  })();

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length || !id) return;
    setUploading(files.length);
    try {
      await Promise.all(files.map(f => {
        const fd = new FormData();
        fd.append("file", f);
        return fetch(`${config.apiUrl || ""}/api/v1/animals/${id}/photos`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("tv_access_token") ?? ""}`,
          },
          body: fd,
        });
      }));
      await refetchPhotos();
      qc.invalidateQueries({ queryKey: ["animals", numId] });
    } finally {
      setUploading(0);
      if (uploadRef.current) uploadRef.current.value = "";
    }
  }, [id, numId, refetchPhotos, qc]);

  const handlePickerSelect = async (photo: Photo) => {
    if (!picker) return;
    const endpoint = picker === "profile"
      ? `/api/v1/animals/${id}/photos/${photo.id}/set-profile`
      : `/api/v1/animals/${id}/photos/${photo.id}/set-muzzle`;
    await apiFetch(endpoint, { method: "PATCH" });
    await refetchPhotos();
    qc.invalidateQueries({ queryKey: ["animals", numId] });
    setPicker(null);
  };

  const setProfilePhoto = async (photoId: number) => {
    await apiFetch(`/api/v1/animals/${id}/photos/${photoId}/set-profile`, { method: "PATCH" });
    await refetchPhotos(); qc.invalidateQueries({ queryKey: ["animals", numId] });
  };
  const setMuzzlePhoto = async (photoId: number) => {
    await apiFetch(`/api/v1/animals/${id}/photos/${photoId}/set-muzzle`, { method: "PATCH" });
    await refetchPhotos(); qc.invalidateQueries({ queryKey: ["animals", numId] });
  };
  const deletePhoto = async (photoId: number) => {
    await apiFetch(`/api/v1/animals/${id}/photos/${photoId}`, { method: "DELETE" });
    await refetchPhotos(); qc.invalidateQueries({ queryKey: ["animals", numId] });
  };

  const createHealthMut = useMutation({
    mutationFn: () => apiFetch(`/api/v1/health/animals/${id}/records`, {
      method: "POST",
      body: JSON.stringify({
        record_type: hForm.record_type, severity: hForm.severity,
        diagnosis:   hForm.diagnosis,
        symptoms:     hForm.symptoms     || undefined,
        treatment:    hForm.treatment    || undefined,
        medication:   hForm.medication   || undefined,
        veterinarian: hForm.veterinarian || undefined,
        cost: hForm.cost ? parseFloat(hForm.cost) : undefined,
      }),
    }),
    onSuccess: () => {
      setHMsg("✅ Saqlandi!");
      setShowHForm(false);
      setHForm({ record_type: "checkup", severity: "normal", diagnosis: "",
        symptoms: "", treatment: "", medication: "", veterinarian: "", cost: "" });
      qc.invalidateQueries({ queryKey: ["health", "records", numId] });
    },
    onError: (e: Error) => setHMsg(`❌ ${e.message}`),
  });

  const resolveHealthMut = useMutation({
    mutationFn: (rid: number) =>
      apiFetch(`/api/v1/health/records/${rid}/resolve`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["health", "records", numId] }),
  });

  // ── Styles ─────────────────────────────────────────────────────────────────

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E2E8F0",
    borderRadius: 16, padding: "20px 22px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "9px 12px", borderRadius: 9, fontSize: 13,
    border: "1.5px solid #E2E8F0", outline: "none", fontFamily: "inherit",
    transition: "border-color .15s",
  };

  // ── Loading / Error ────────────────────────────────────────────────────────

  if (isLoading) return (
    <div style={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}} @keyframes fadein{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`}</style>
      <Spinner size={36} />
    </div>
  );

  if (isError || !animal) return (
    <div style={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <AlertTriangle size={40} color="#DC2626" style={{ margin: "0 auto 12px", display: "block" }} />
        <p style={{ color: "#64748B" }}>{(error as Error)?.message ?? "Jonivor topilmadi"}</p>
        <button onClick={() => nav("/animals")} style={{
          color: "#2563EB", background: "none", border: "none", cursor: "pointer",
          fontSize: 14, display: "inline-flex", alignItems: "center", gap: 6,
        }}>
          <ArrowLeft size={14} /> Orqaga
        </button>
      </div>
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={{
      maxWidth: 1120, margin: "0 auto", padding: isMobile ? "14px 12px 80px" : "28px 20px 72px",
      fontFamily: "'Outfit', system-ui, sans-serif", color: "#0F172A",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes fadein  { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
        * { box-sizing: border-box; }
        button:focus-visible { outline: 2px solid #2563EB; outline-offset: 2px; }
        input:focus, select:focus { border-color: #2563EB !important; }
      `}</style>

      {/* Modals */}
      {lightbox !== null && <Lightbox photoId={lightbox} onClose={() => setLightbox(null)} />}
      {picker && (
        <PickerModal
          mode={picker}
          photos={photos}
          onSelect={handlePickerSelect}
          onClose={() => setPicker(null)}
        />
      )}

      {/* Back button */}
      <button onClick={() => nav("/animals")} style={{
        display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 20,
        background: "none", border: "none", cursor: "pointer", fontSize: 13,
        color: "#64748B", padding: 0, fontFamily: "inherit",
      }}>
        <ArrowLeft size={14} />
        Jonivorlar ro'yxati
      </button>

      {/* ═══════════════════ HEADER ═══════════════════ */}
      <div style={{
        ...card, marginBottom: 18, animation: "fadein .3s ease",
        background: "linear-gradient(135deg, #F8FAFF 0%, #FFFFFF 100%)",
      }}>
        <div style={{ display: "flex", gap: 28, flexWrap: "wrap", alignItems: "flex-start" }}>

          {/* Profile avatar */}
          <AvatarSlot
            label="Profil rasmi"
            sublabel="Asosiy ko'rinish"
            photoId={profilePhoto?.id}
            accentColor="#2563EB"
            borderColor="#BFDBFE"
            icon={Camera}
            onClick={() => setPicker("profile")}
          />

          {/* Muzzle avatar */}
          <AvatarSlot
            label="Tumshuq rasmi"
            sublabel="AI identifikatsiya"
            photoId={muzzlePhoto?.id}
            accentColor="#7C3AED"
            borderColor="#DDD6FE"
            icon={Scan}
            onClick={() => setPicker("muzzle")}
          />

          {/* Info block */}
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 6 }}>
              <h1 style={{
                margin: 0, fontSize: 28, fontWeight: 700, color: "#0F172A",
                fontFamily: "'JetBrains Mono', monospace", letterSpacing: ".02em",
              }}>
                {animal.tag_id}
              </h1>
              <span style={{
                padding: "3px 12px", borderRadius: 99, fontSize: 12, fontWeight: 600,
                background: animal.status === "active" ? "#F0FDF4" : "#F3F4F6",
                color:      animal.status === "active" ? "#16A34A" : "#6B7280",
                border: `1px solid ${animal.status === "active" ? "#BBF7D0" : "#E5E7EB"}`,
              }}>
                {animal.status === "active" ? "Faol" : animal.status}
              </span>
              {embedCount > 0 && (
                <span style={{
                  padding: "3px 12px", borderRadius: 99, fontSize: 12, fontWeight: 600,
                  background: "#F0FDF4", color: "#16A34A", border: "1px solid #BBF7D0",
                }}>
                  {embedCount} embedding
                </span>
              )}
            </div>

            <p style={{ margin: "0 0 16px", fontSize: 14, color: "#64748B", textTransform: "capitalize" }}>
              {animal.species}
              {" · "}
              {animal.gender === "male" ? "Erkak" : animal.gender === "female" ? "Urg'oqi" : "Noma'lum"}
              {animal.breed ? ` · ${animal.breed}` : ""}
            </p>

            <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
              {[
                ["Aniqlashlar",     `${animal.total_detections} ta`],
                ["Oxirgi ko'rinish", animal.last_detected_at
                  ? format(new Date(animal.last_detected_at), "dd.MM.yyyy")
                  : "—"],
                ["Qo'shilgan",      format(new Date(animal.created_at), "dd.MM.yyyy")],
              ].map(([label, value]) => (
                <div key={label}>
                  <div style={{ fontSize: 10, color: "#94A3B8", marginBottom: 3, textTransform: "uppercase", letterSpacing: ".06em", fontWeight: 600 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#374151" }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Refresh */}
          <button
            onClick={() => { qc.invalidateQueries({ queryKey: ["animals", numId] }); refetchPhotos(); }}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "7px 14px", borderRadius: 9,
              border: "1.5px solid #E2E8F0", background: "#F8FAFC",
              fontSize: 13, color: "#64748B", cursor: "pointer", fontFamily: "inherit",
              alignSelf: "flex-start",
            }}
          >
            <RefreshCw size={13} /> Yangilash
          </button>
        </div>
      </div>

      {/* ═══════════════════ KPI Cards ═══════════════════ */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        gap: 12, marginBottom: 18,
      }}>
        {/* ADI */}
        <div style={{
          ...card, padding: "16px 18px",
          background: adiCfg?.bg ?? "#F9FAFB",
          border: `1px solid ${adiNow ? adiCfg?.ring + "44" : "#E5E7EB"}`,
        }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6 }}>
            ADI Ball
          </div>
          {adiNow ? (
            <>
              <div style={{ fontSize: 30, fontWeight: 700, color: adiCfg?.color, lineHeight: 1 }}>
                {adiNow.adi_score.toFixed(0)}
              </div>
              <div style={{ fontSize: 12, fontWeight: 500, color: adiCfg?.color, marginTop: 4 }}>
                {adiCfg?.label}
              </div>
            </>
          ) : <div style={{ fontSize: 14, color: "#94A3B8" }}>—</div>}
        </div>

        {/* Weight */}
        <div style={{ ...card, padding: "16px 18px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6 }}>Joriy vazn</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>
            {latestW != null ? `${latestW.toFixed(1)} kg` : "—"}
          </div>
        </div>

        {/* 7-day weight change */}
        <div style={{ ...card, padding: "16px 18px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6 }}>7 kun o'zgarish</div>
          {wChange != null ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {wChange > 0
                ? <TrendingUp size={20} color="#16A34A" />
                : wChange < 0
                ? <TrendingDown size={20} color="#DC2626" />
                : <Minus size={20} color="#6B7280" />}
              <span style={{ fontSize: 22, fontWeight: 700, color: wChange > 0 ? "#16A34A" : wChange < 0 ? "#DC2626" : "#6B7280" }}>
                {wChange > 0 ? "+" : ""}{wChange.toFixed(1)} kg
              </span>
            </div>
          ) : <div style={{ fontSize: 14, color: "#94A3B8" }}>—</div>}
        </div>

        {/* Trend */}
        <div style={{ ...card, padding: "16px 18px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6 }}>ADI Trend</div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {trend === "improving"
              ? <><TrendingUp size={20} color="#16A34A" /><span style={{ fontSize: 13, fontWeight: 600, color: "#16A34A" }}>O'smoqda</span></>
              : trend === "declining"
              ? <><TrendingDown size={20} color="#DC2626" /><span style={{ fontSize: 13, fontWeight: 600, color: "#DC2626" }}>Tushmoqda</span></>
              : <><Minus size={20} color="#6B7280" /><span style={{ fontSize: 13, fontWeight: 600, color: "#6B7280" }}>Barqaror</span></>}
          </div>
        </div>

        {/* Photos */}
        <div style={{ ...card, padding: "16px 18px" }}>
          <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 6 }}>Rasmlar</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>{photos.length}</div>
          <button
            onClick={() => setTab("photos")}
            style={{
              marginTop: 6, fontSize: 11, color: "#2563EB", background: "none",
              border: "none", cursor: "pointer", padding: 0, fontFamily: "inherit",
              display: "inline-flex", alignItems: "center", gap: 3,
            }}
          >
            Ko'rish <ChevronRight size={11} />
          </button>
        </div>
      </div>

      {/* ═══════════════════ Tabs ═══════════════════ */}
      <div style={{
        display: "flex", gap: 2, marginBottom: 18,
        background: "#F1F5F9", borderRadius: 12, padding: 4,
        width: isMobile ? "100%" : "fit-content",
        overflowX: isMobile ? "auto" : "visible",
      }}>
        {([
          { key: "overview",  label: "Umumiy" },
          { key: "adi",       label: "ADI" },
          { key: "weight",    label: "Vazn" },
          { key: "health",    label: "Sog'liq" },
          { key: "milk",      label: "🥛 Sut" },
          { key: "medicine",  label: "💊 Dori" },
          { key: "photos",    label: "📸 Rasmlar" },
        ] as { key: typeof tab; label: string }[]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "7px 16px", borderRadius: 9, fontSize: 13, fontWeight: 500,
              cursor: "pointer", border: "none", transition: "all .15s", fontFamily: "inherit",
              background: tab === t.key ? "#fff" : "transparent",
              color:      tab === t.key ? "#2563EB" : "#64748B",
              boxShadow:  tab === t.key ? "0 1px 6px rgba(0,0,0,.08)" : "none",
              whiteSpace: "nowrap",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════ OVERVIEW ═══════════════════ */}
      {tab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16, animation: "fadein .25s" }}>
          <div style={card}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 16px" }}>Asosiy Ma'lumotlar</h3>
            {([
              ["Tag ID", animal.tag_id],
              ["Tur", animal.species],
              ["Jins", animal.gender === "male" ? "Erkak" : "Urg'oqi"],
              ["Zot", animal.breed ?? "—"],
              ["Holat", animal.status === "active" ? "Faol" : animal.status],
              ["Olingan", animal.acquisition_date ? format(new Date(animal.acquisition_date), "dd.MM.yyyy") : "—"],
              ["Tug'ilgan", animal.birth_date ? format(new Date(animal.birth_date), "dd.MM.yyyy") : "—"],
              ["Kategoriya", animal.category ?? "—"],
            ] as [string, string][]).map(([l, v]) => (
              <div key={l} style={{
                display: "flex", justifyContent: "space-between", padding: "8px 0",
                borderBottom: "1px solid #F8FAFC", fontSize: 13,
              }}>
                <span style={{ color: "#64748B" }}>{l}</span>
                <span style={{ fontWeight: 500, textTransform: "capitalize" }}>{v}</span>
              </div>
            ))}
          </div>

          <div style={card}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 18px" }}>ADI Bugungi Ko'rsatkichi</h3>
            {adiNow ? (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 18 }}>
                  <div style={{
                    width: 80, height: 80, borderRadius: "50%",
                    border: `5px solid ${adiCfg?.ring}`,
                    background: adiCfg?.bg,
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  }}>
                    <span style={{ fontSize: 24, fontWeight: 700, color: adiCfg?.color, lineHeight: 1 }}>
                      {adiNow.adi_score.toFixed(0)}
                    </span>
                    <span style={{ fontSize: 9, color: adiCfg?.color, opacity: .7 }}>/100</span>
                  </div>
                  <div>
                    <span style={{
                      display: "inline-block", padding: "4px 14px", borderRadius: 99,
                      background: adiCfg?.bg, color: adiCfg?.color, fontSize: 13,
                      fontWeight: 600, border: `1px solid ${adiCfg?.ring}44`,
                    }}>
                      {adiCfg?.label}
                    </span>
                    <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 6 }}>
                      {format(parseISO(adiNow.calculation_date), "dd.MM.yyyy")}
                    </div>
                  </div>
                </div>
                {adiNow.scores && (
                  <div>
                    {Object.entries({
                      "Oziqlanish": adiNow.scores.feeding_score,
                      "Faollik":    adiNow.scores.activity_score,
                      "O'sish":    adiNow.scores.growth_score,
                      "Harakat":    adiNow.scores.movement_score,
                    }).filter(([, v]) => v != null).map(([label, val]) => (
                      <div key={label} style={{ marginBottom: 10 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                          <span style={{ color: "#64748B" }}>{label}</span>
                          <span style={{ fontWeight: 600, color: "#374151" }}>{(val as number).toFixed(0)}</span>
                        </div>
                        <div style={{ height: 5, background: "#F1F5F9", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{
                            height: "100%", borderRadius: 3,
                            width: `${val}%`, background: adiCfg?.ring,
                            transition: "width .5s",
                          }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#94A3B8" }}>
                <Activity size={36} style={{ margin: "0 auto 10px", display: "block", opacity: .3 }} />
                <p style={{ fontSize: 14 }}>ADI ma'lumoti yo'q</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════ ADI ═══════════════════ */}
      {tab === "adi" && (
        <div style={{ animation: "fadein .25s" }}>
          <div style={card}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 20px" }}>ADI 30 Kunlik Grafik</h3>
            {adiChartData.length === 0 ? (
              <div style={{ textAlign: "center", padding: "60px 0", color: "#94A3B8" }}>
                <Activity size={36} style={{ margin: "0 auto 10px", display: "block", opacity: .3 }} />
                <p>Ma'lumot yo'q</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={adiChartData}>
                  <defs>
                    <linearGradient id="adiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#2563EB" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#2563EB" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#E2E8F0" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#E2E8F0" />
                  <Tooltip
                    contentStyle={{ borderRadius: 10, border: "1px solid #E2E8F0", fontSize: 12 }}
                    formatter={(v: any) => [`${Number(v).toFixed(1)}`, "ADI"]}
                  />
                  <Area
                    type="monotone" dataKey="score"
                    stroke="#2563EB" strokeWidth={2.5}
                    fill="url(#adiGrad)"
                    dot={{ r: 3, fill: "#2563EB", strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════ WEIGHT ═══════════════════ */}
            {tab === "weight" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, animation: "fadein .25s" }}>

          {/* ── E5: Tur standarti vs haqiqiy vazn ── */}
          {(() => {
            // Tur bo'yicha standart vaznlar (qoramol zootexnikasi normasi)
            const WEIGHT_STANDARDS: Record<string, {
              label: string;
              stages: { name: string; minAge: number; maxAge: number; minKg: number; maxKg: number; }[];
            }> = {
              cattle: {
                label: "Qoramol",
                stages: [
                  { name: "Buzoq (0-6 oy)",      minAge: 0,   maxAge: 6,   minKg: 40,  maxKg: 180  },
                  { name: "Yosh (6-18 oy)",       minAge: 6,   maxAge: 18,  minKg: 180, maxKg: 380  },
                  { name: "O'smir (18-30 oy)",    minAge: 18,  maxAge: 30,  minKg: 380, maxKg: 520  },
                  { name: "Yetuk (30+ oy)",       minAge: 30,  maxAge: 999, minKg: 450, maxKg: 750  },
                ],
              },
              sheep: {
                label: "Qo'y",
                stages: [
                  { name: "Qo'zi (0-4 oy)",      minAge: 0,  maxAge: 4,  minKg: 5,  maxKg: 35  },
                  { name: "Yosh (4-12 oy)",       minAge: 4,  maxAge: 12, minKg: 35, maxKg: 60  },
                  { name: "Yetuk (12+ oy)",       minAge: 12, maxAge: 999, minKg: 45, maxKg: 90  },
                ],
              },
              goat: {
                label: "Echki",
                stages: [
                  { name: "Bolasi (0-4 oy)",     minAge: 0,  maxAge: 4,  minKg: 3,  maxKg: 20  },
                  { name: "Yosh (4-12 oy)",       minAge: 4,  maxAge: 12, minKg: 20, maxKg: 35  },
                  { name: "Yetuk (12+ oy)",       minAge: 12, maxAge: 999, minKg: 30, maxKg: 60  },
                ],
              },
              horse: {
                label: "Ot",
                stages: [
                  { name: "Toy (0-12 oy)",        minAge: 0,  maxAge: 12, minKg: 50,  maxKg: 220  },
                  { name: "Yosh (12-36 oy)",       minAge: 12, maxAge: 36, minKg: 220, maxKg: 400  },
                  { name: "Yetuk (36+ oy)",        minAge: 36, maxAge: 999, minKg: 380, maxKg: 600 },
                ],
              },
            };

            const std = WEIGHT_STANDARDS[animal.species];
            if (!std) return null;

            // Yoshni hisoblash
            const ageMonths = animal.birth_date
              ? Math.floor((Date.now() - new Date(animal.birth_date).getTime()) / (1000 * 60 * 60 * 24 * 30.44))
              : null;

            // Mos bosqichni topish
            const stage = ageMonths != null
              ? std.stages.find(s => ageMonths >= s.minAge && ageMonths < s.maxAge) ?? std.stages[std.stages.length - 1]
              : std.stages[std.stages.length - 1];

            // Haqiqiy so'nggi vazn
            const lastW = weights.length > 0
              ? [...weights].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0]?.estimated_weight_kg
              : null;

            // Holat hisoblash
            let status: "normal" | "low" | "high" | "unknown" = "unknown";
            let pct = 50;
            if (lastW != null) {
              const mid = (stage.minKg + stage.maxKg) / 2;
              const range = stage.maxKg - stage.minKg;
              pct = Math.min(100, Math.max(0, ((lastW - stage.minKg) / range) * 100));
              if (lastW < stage.minKg * 0.9)      status = "low";
              else if (lastW > stage.maxKg * 1.1) status = "high";
              else                                 status = "normal";
            }

            const statusCfg = {
              normal:  { label: "Normada ✓",    color: "#059669", bg: "#ECFDF5", border: "#A7F3D0", bar: "#059669" },
              low:     { label: "Pastroq ↓",    color: "#DC2626", bg: "#FEF2F2", border: "#FECACA", bar: "#DC2626" },
              high:    { label: "Yuqoriroq ↑",  color: "#D97706", bg: "#FFFBEB", border: "#FDE68A", bar: "#D97706" },
              unknown: { label: "Ma'lumot yo'q", color: "#6B7280", bg: "#F9FAFB", border: "#E5E7EB", bar: "#D1D5DB" },
            };
            const sc = statusCfg[status];

            return (
              <div style={{
                background: "#fff", border: "1px solid #E2E8F0",
                borderRadius: 14, padding: "18px 20px",
                borderLeft: `4px solid ${sc.bar}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
                  <div>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 2px", color: "#0D1117" }}>
                      {std.label} — Vazn Standarti
                    </h3>
                    <p style={{ fontSize: 12, color: "#6B7280", margin: 0 }}>
                      {stage.name}
                      {ageMonths != null && ` • Yoshi: ${ageMonths} oy`}
                    </p>
                  </div>
                  <span style={{
                    padding: "5px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: sc.bg, color: sc.color, border: `1px solid ${sc.border}`,
                  }}>
                    {sc.label}
                  </span>
                </div>

                {/* Ko'rsatkichlar */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
                  {[
                    { label: "Haqiqiy vazn",    value: lastW != null ? `${lastW.toFixed(1)} kg` : "—",                  color: sc.color },
                    { label: "Norma (min–maks)", value: `${stage.minKg}–${stage.maxKg} kg`,                              color: "#374151" },
                    { label: "Farq",             value: lastW != null ? `${(lastW - (stage.minKg + stage.maxKg) / 2).toFixed(1)} kg` : "—", color: lastW == null ? "#6B7280" : lastW < stage.minKg ? "#DC2626" : lastW > stage.maxKg ? "#D97706" : "#059669" },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{
                      background: "#F8FAFC", borderRadius: 10, padding: "10px 12px", textAlign: "center",
                    }}>
                      <div style={{ fontSize: 10, color: "#9CA3AF", fontWeight: 600, marginBottom: 3 }}>{label}</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color }}>{value}</div>
                    </div>
                  ))}
                </div>

                {/* Progress bar */}
                <div style={{ marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#9CA3AF", marginBottom: 4 }}>
                    <span>{stage.minKg} kg</span>
                    <span style={{ color: "#6B7280", fontWeight: 600 }}>Ideal zona</span>
                    <span>{stage.maxKg} kg</span>
                  </div>
                  <div style={{
                    position: "relative", height: 10, borderRadius: 6,
                    background: "#F1F5F9", overflow: "hidden",
                  }}>
                    {/* Ideal zone highlight */}
                    <div style={{
                      position: "absolute", left: "5%", right: "5%", top: 0, bottom: 0,
                      background: "rgba(16,185,129,0.12)", borderRadius: 4,
                    }} />
                    {/* Current position */}
                    {lastW != null && (
                      <div style={{
                        position: "absolute",
                        left: `calc(${Math.min(97, Math.max(3, pct))}% - 6px)`,
                        top: -2, width: 14, height: 14,
                        borderRadius: "50%",
                        background: sc.bar,
                        border: "2px solid #fff",
                        boxShadow: `0 0 0 3px ${sc.bg}`,
                        zIndex: 2,
                        transition: "left .4s ease",
                      }} />
                    )}
                  </div>
                </div>

                {!animal.birth_date && (
                  <p style={{ fontSize: 11, color: "#9CA3AF", margin: "8px 0 0", textAlign: "center" }}>
                    ⚠ Tug'ilgan sana kiritilmagan — yosh bo'yicha aniq bosqich aniqlanmadi
                  </p>
                )}
              </div>
            );
          })()}

          <div style={card}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 20px" }}>Vazn Grafigi (so'nggi 30 ta)</h3>
            {weightChartData.length === 0 ? (
              <div style={{ textAlign: "center", padding: "60px 0", color: "#94A3B8" }}>
                <Scale size={36} style={{ margin: "0 auto 10px", display: "block", opacity: .3 }} />
                <p>Ma'lumot yo'q</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={weightChartData}>
                  <defs>
                    <linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#16A34A" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#16A34A" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#E2E8F0" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#E2E8F0" />
                  <Tooltip
                    contentStyle={{ borderRadius: 10, border: "1px solid #E2E8F0", fontSize: 12 }}
                    formatter={(v: any) => [`${Number(v).toFixed(1)} kg`, "Vazn"]}
                  />
                  <Area
                    type="monotone" dataKey="weight"
                    stroke="#16A34A" strokeWidth={2.5}
                    fill="url(#wGrad)"
                    dot={{ r: 2, fill: "#16A34A", strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          <div style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
                Barcha O'lchovlar ({weights.length} ta)
              </h3>
              <button
                onClick={() => window.open(`${config.apiUrl || ""}/api/v1/export/weights?animal_id=${id}&format=csv`, "_blank")}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "6px 14px", borderRadius: 8,
                  border: "1.5px solid #E2E8F0", background: "#F8FAFC",
                  fontSize: 12, color: "#64748B", cursor: "pointer", fontFamily: "inherit",
                }}
              >
                <Download size={13} /> CSV
              </button>
            </div>
            <div style={{ maxHeight: 340, overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#F8FAFC" }}>
                    {["Sana", "Vazn", "Ishonch", "Kamera"].map(h => (
                      <th key={h} style={{
                        padding: "8px 12px", textAlign: "left", fontSize: 11,
                        fontWeight: 600, color: "#64748B",
                        textTransform: "uppercase", letterSpacing: ".06em",
                        borderBottom: "1px solid #E2E8F0",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...weights]
                    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                    .map(w => (
                      <tr key={w.id} style={{ borderBottom: "1px solid #F8FAFC" }}>
                        <td style={{ padding: "9px 12px", color: "#374151" }}>
                          {format(new Date(w.timestamp), "dd.MM.yyyy HH:mm")}
                        </td>
                        <td style={{ padding: "9px 12px", fontWeight: 600 }}>
                          {w.estimated_weight_kg.toFixed(1)} kg
                        </td>
                        <td style={{ padding: "9px 12px" }}>
                          <span style={{ fontWeight: 500, color: w.confidence_score >= .85 ? "#16A34A" : "#D97706" }}>
                            {(w.confidence_score * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ padding: "9px 12px", color: "#64748B", fontSize: 12 }}>
                          {w.camera_id}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ HEALTH ═══════════════════ */}
      {tab === "health" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, animation: "fadein .25s" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, color: "#64748B" }}>
              Jami <b style={{ color: "#0F172A" }}>{healthResp?.total ?? 0}</b> ta yozuv
            </span>
            <button
              onClick={() => { setShowHForm(v => !v); setHMsg(""); }}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "8px 18px", borderRadius: 10, border: "none",
                background: showHForm ? "#F1F5F9" : "#2563EB",
                color: showHForm ? "#374151" : "#fff",
                fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
              }}
            >
              {showHForm ? <X size={14} /> : <Plus size={14} />}
              {showHForm ? "Bekor qilish" : "Yangi yozuv"}
            </button>
          </div>

          {showHForm && (
            <div style={{ ...card, animation: "fadein .2s" }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 18px" }}>Yangi Sog'liq Yozuvi</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#64748B", display: "block", marginBottom: 5 }}>Tur *</label>
                  <select value={hForm.record_type} onChange={e => setHForm(p => ({ ...p, record_type: e.target.value }))} style={inputStyle}>
                    {[["checkup","Tekshiruv"],["treatment","Davolash"],["vaccination","Emlash"],
                      ["injury","Shikast"],["surgery","Operatsiya"],["illness","Kasallik"],["other","Boshqa"]
                    ].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#64748B", display: "block", marginBottom: 5 }}>Jiddiylik *</label>
                  <select value={hForm.severity} onChange={e => setHForm(p => ({ ...p, severity: e.target.value }))} style={inputStyle}>
                    <option value="normal">Normal</option>
                    <option value="warning">Ogohlantirish</option>
                    <option value="critical">Kritik</option>
                  </select>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#64748B", display: "block", marginBottom: 5 }}>Diagnoz *</label>
                  <input
                    type="text" value={hForm.diagnosis} placeholder="Masalan: Tekshiruv o'tkazildi, sog'liq normal"
                    onChange={e => setHForm(p => ({ ...p, diagnosis: e.target.value }))}
                    style={{ ...inputStyle, borderColor: hForm.diagnosis ? "#E2E8F0" : "#FCA5A5" }}
                  />
                </div>
                {[["symptoms","Belgilar"],["treatment","Davolash usuli"],["medication","Dori-darmon"],["veterinarian","Veterinar"]].map(([f, l]) => (
                  <div key={f}>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "#64748B", display: "block", marginBottom: 5 }}>{l}</label>
                    <input type="text" value={hForm[f as keyof typeof hForm]}
                      onChange={e => setHForm(p => ({ ...p, [f]: e.target.value }))}
                      style={inputStyle} />
                  </div>
                ))}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#64748B", display: "block", marginBottom: 5 }}>Narx (UZS)</label>
                  <input type="number" value={hForm.cost} min="0" placeholder="0"
                    onChange={e => setHForm(p => ({ ...p, cost: e.target.value }))}
                    style={inputStyle} />
                </div>
              </div>
              {hMsg && (
                <div style={{
                  marginTop: 14, padding: "10px 14px", borderRadius: 9, fontSize: 13,
                  background: hMsg.startsWith("✅") ? "#F0FDF4" : "#FEF2F2",
                  color:      hMsg.startsWith("✅") ? "#16A34A" : "#DC2626",
                  border: `1px solid ${hMsg.startsWith("✅") ? "#BBF7D0" : "#FECACA"}`,
                }}>{hMsg}</div>
              )}
              <button
                onClick={() => { if (!hForm.diagnosis.trim()) return; createHealthMut.mutate(); }}
                disabled={!hForm.diagnosis.trim() || createHealthMut.isPending}
                style={{
                  marginTop: 16, width: "100%", padding: "11px 0", borderRadius: 10,
                  border: "none", cursor: hForm.diagnosis.trim() ? "pointer" : "not-allowed",
                  background: hForm.diagnosis.trim() ? "#2563EB" : "#E2E8F0",
                  color: hForm.diagnosis.trim() ? "#fff" : "#94A3B8",
                  fontSize: 14, fontWeight: 600,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  fontFamily: "inherit",
                }}
              >
                {createHealthMut.isPending ? <><Spinner size={16} color="#fff" /> Saqlanmoqda...</> : <><Heart size={15} /> Saqlash</>}
              </button>
            </div>
          )}

          {healthFetching ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}><Spinner /></div>
          ) : healthRecords.length === 0 ? (
            <div style={{ ...card, textAlign: "center", padding: "56px 24px" }}>
              <Heart size={40} color="#E2E8F0" style={{ margin: "0 auto 12px", display: "block" }} />
              <p style={{ color: "#94A3B8", fontSize: 14 }}>Sog'liq yozuvlari yo'q</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {healthRecords.map(rec => {
                const sc = rec.severity === "critical" ? "#DC2626" : rec.severity === "warning" ? "#D97706" : "#16A34A";
                return (
                  <div key={rec.id} style={{
                    background: "#fff", border: "1px solid #E2E8F0", borderRadius: 12,
                    padding: "16px 20px", borderLeft: `4px solid ${sc}`,
                    opacity: rec.is_resolved ? .7 : 1,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>
                            {RECORD_TYPE_LABELS[rec.record_type] ?? rec.record_type}
                          </span>
                          <span style={{
                            fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
                            background: rec.severity === "critical" ? "#FEF2F2" : rec.severity === "warning" ? "#FFFBEB" : "#F0FDF4",
                            color: sc,
                          }}>{rec.severity}</span>
                          {rec.is_resolved && (
                            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6,
                              background: "#F0FDF4", color: "#16A34A" }}>
                              ✓ Hal etilgan
                            </span>
                          )}
                        </div>
                        <p style={{ fontSize: 13, fontWeight: 500, color: "#374151", margin: "0 0 4px" }}>
                          {rec.diagnosis}
                        </p>
                        {rec.treatment && (
                          <p style={{ fontSize: 12, color: "#64748B", margin: "0 0 2px" }}>
                            <b>Davolash:</b> {rec.treatment}
                          </p>
                        )}
                        <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 11, color: "#94A3B8" }}>
                            {format(new Date(rec.recorded_at), "dd.MM.yyyy HH:mm")}
                          </span>
                          {rec.veterinarian && <span style={{ fontSize: 11, color: "#94A3B8" }}>{rec.veterinarian}</span>}
                          {rec.cost != null && <span style={{ fontSize: 11, color: "#94A3B8" }}>{rec.cost.toLocaleString()} UZS</span>}
                        </div>
                      </div>
                      {!rec.is_resolved && (
                        <button
                          onClick={() => resolveHealthMut.mutate(rec.id)}
                          style={{
                            display: "inline-flex", alignItems: "center", gap: 5,
                            padding: "6px 12px", borderRadius: 8,
                            background: "#F0FDF4", color: "#16A34A",
                            border: "1px solid #BBF7D0", cursor: "pointer",
                            fontSize: 12, fontWeight: 500, fontFamily: "inherit", flexShrink: 0,
                          }}
                        >
                          <CheckCircle size={12} /> Hal etildi
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════ SUT ═══════════════════ */}
      {tab === "milk" && (
        <MilkTab animalId={numId} gender={animal.gender} />
      )}

      {/* ═══════════════════ DORI ═══════════════════ */}
      {tab === "medicine" && (
        <MedicineTab animalId={numId} />
      )}

      {/* ═══════════════════ PHOTOS ═══════════════════ */}
      {tab === "photos" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20, animation: "fadein .25s" }}>

          {/* Upload bar */}
          <div style={{ ...card, padding: "18px 22px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
              {/* Stats */}
              <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4 }}>Jami rasmlar</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: "#0F172A" }}>{photos.length}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4 }}>AI Embedding</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: embedCount > 0 ? "#16A34A" : "#94A3B8" }}>{embedCount}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, justifyContent: "flex-end" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: profilePhoto ? "#2563EB" : "#E2E8F0" }} />
                    <span style={{ fontSize: 12, color: profilePhoto ? "#2563EB" : "#9CA3AF" }}>
                      Profil: {profilePhoto ? "✓ Belgilangan" : "Belgilanmagan"}
                    </span>
                    <button onClick={() => setPicker("profile")} style={{
                      fontSize: 11, color: "#2563EB", background: "none", border: "none",
                      cursor: "pointer", padding: 0, fontFamily: "inherit",
                    }}>
                      Tanlash →
                    </button>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: muzzlePhoto ? "#7C3AED" : "#E2E8F0" }} />
                    <span style={{ fontSize: 12, color: muzzlePhoto ? "#7C3AED" : "#9CA3AF" }}>
                      Muzzle: {muzzlePhoto ? "✓ Belgilangan" : "Belgilanmagan"}
                    </span>
                    <button onClick={() => setPicker("muzzle")} style={{
                      fontSize: 11, color: "#7C3AED", background: "none", border: "none",
                      cursor: "pointer", padding: 0, fontFamily: "inherit",
                    }}>
                      Tanlash →
                    </button>
                  </div>
                </div>
              </div>

              {/* Upload button */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                <button
                  onClick={() => uploadRef.current?.click()}
                  disabled={uploading > 0}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 8,
                    padding: "10px 22px", borderRadius: 10, border: "none",
                    background: "#2563EB", color: "#fff", fontSize: 13, fontWeight: 600,
                    cursor: uploading > 0 ? "not-allowed" : "pointer",
                    opacity: uploading > 0 ? .7 : 1, fontFamily: "inherit",
                  }}
                >
                  {uploading > 0
                    ? <><Spinner size={16} color="#fff" /> {uploading} ta yuklanmoqda...</>
                    : <><Upload size={15} /> Rasm yuklash</>}
                </button>
                <span style={{ fontSize: 11, color: "#94A3B8" }}>
                  💡 Ctrl+Click — bir vaqtda ko'p rasm tanlash
                </span>
              </div>
            </div>
            <input ref={uploadRef} type="file" accept="image/*" multiple style={{ display: "none" }} onChange={handleUpload} />
          </div>

          {/* Gallery */}
          {photos.length === 0 ? (
            <div style={{
              background: "#fff", border: "2px dashed #E2E8F0", borderRadius: 18,
              padding: "72px 24px", textAlign: "center",
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: 20, background: "#F1F5F9",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 18px",
              }}>
                <Camera size={32} color="#CBD5E1" />
              </div>
              <p style={{ fontSize: 16, fontWeight: 500, color: "#374151", marginBottom: 8 }}>
                Hali rasm yuklanmagan
              </p>
              <p style={{ fontSize: 13, color: "#94A3B8", marginBottom: 20 }}>
                Yuqoridagi tugmani bosib rasmlarni yuklang
              </p>
              <button
                onClick={() => uploadRef.current?.click()}
                style={{
                  padding: "9px 22px", borderRadius: 10, border: "1.5px solid #E2E8F0",
                  background: "#fff", color: "#64748B", cursor: "pointer",
                  fontSize: 13, fontFamily: "inherit",
                }}
              >
                Rasm yuklash
              </button>
            </div>
          ) : (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
              gap: 16,
            }}>
              {photos.map(photo => (
                <PhotoCard
                  key={photo.id}
                  photo={photo}
                  onSetProfile={() => setProfilePhoto(photo.id)}
                  onSetMuzzle={() => setMuzzlePhoto(photo.id)}
                  onDelete={() => deletePhoto(photo.id)}
                  onZoom={() => setLightbox(photo.id)}
                />
              ))}
            </div>
          )}

          {/* AI info card */}
          <div style={{
            ...card,
            background: "linear-gradient(135deg, #F0F7FF 0%, #F5F3FF 100%)",
            border: "1px solid #DBEAFE",
          }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 14px", color: "#1E40AF" }}>
              AI Identifikatsiya qanday ishlaydi?
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
              {[
                { n: "1", c: "#2563EB", t: "Rasm yuklang",     d: "Tumshuq rasmi — aniq, yaxshi yoritilgan. Kamida 5 ta." },
                { n: "2", c: "#7C3AED", t: "Embedding",        d: "MobileNetV2 128-o'lchamli vektor yaratadi." },
                { n: "3", c: "#16A34A", t: "Taqqoslash",       d: "Cosine o'xshashlik ≥ 0.85 bo'lsa — jonivor tanildi." },
                { n: "4", c: "#D97706", t: "ADI & Vazn",       d: "Tanilgan jonivorda avtomatik hisoblanadi." },
              ].map(({ n, c, t, d }) => (
                <div key={n} style={{ display: "flex", gap: 10 }}>
                  <div style={{
                    width: 26, height: 26, borderRadius: 8, background: c,
                    color: "#fff", display: "grid", placeItems: "center",
                    fontSize: 12, fontWeight: 700, flexShrink: 0,
                  }}>{n}</div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2, color: "#0F172A" }}>{t}</div>
                    <div style={{ fontSize: 11, color: "#64748B", lineHeight: 1.5 }}>{d}</div>
                  </div>
                </div>
              ))}
            </div>
            {embedCount < 5 && (
              <div style={{
                marginTop: 14, padding: "8px 14px", borderRadius: 8,
                background: "#FFFBEB", border: "1px solid #FDE68A",
                fontSize: 12, color: "#D97706", fontWeight: 500,
              }}>
                ⚠ Hozirda {embedCount} ta embedding bor. Kamida 5 ta rasm kerak — yana {5 - embedCount} ta qo'shing.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}