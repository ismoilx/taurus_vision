import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../utils/apiFetch';
import { useResponsive } from '../hooks/useResponsive';

interface OverviewStats {
  animals: { total: number; active: number };
}

interface SpeciesDistribution {
  species: string;
  count: number;
}

const COLORS: Record<string, string> = {
  cattle: '#2563EB',
  sheep: '#10B981',
  goat: '#F59E0B',
  horse: '#8B5CF6',
  other: '#9CA3AF',
};

interface DonutLabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  outerRadius: number;
  value: number;
  payload: { species: string; count: number };
}

function DonutLabel({ cx, cy, midAngle, outerRadius, value, payload }: DonutLabelProps) {
  if (value <= 0) return null;

  const RADIAN = Math.PI / 180;
  const radius = outerRadius + 18;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  const isRight = x > cx;
  const lineStartX = cx + (outerRadius + 4) * Math.cos(-midAngle * RADIAN);
  const lineStartY = cy + (outerRadius + 4) * Math.sin(-midAngle * RADIAN);
  const lineEndX = cx + (outerRadius + 22) * Math.cos(-midAngle * RADIAN);
  const lineEndY = cy + (outerRadius + 22) * Math.sin(-midAngle * RADIAN);

  const label =
    payload.species === 'cattle'
      ? 'Qoramollar soni'
      : payload.species === 'sheep'
      ? "Qo'ylar soni"
      : payload.species === 'goat'
      ? 'Echkilar soni'
      : payload.species === 'horse'
      ? 'Otlar soni'
      : 'Boshqa jonivorlar';

  const color = COLORS[payload.species] ?? '#9CA3AF';

  return (
    <g>
      <line x1={lineStartX} y1={lineStartY} x2={lineEndX} y2={lineEndY} stroke={color} strokeWidth={1.4} />
      <text
        x={x}
        y={y}
        fill={color}
        textAnchor={isRight ? 'start' : 'end'}
        dominantBaseline="central"
        style={{ fontSize: 11, fontWeight: 600 }}
      >
        {label}: {value}
      </text>
    </g>
  );
}

export default function DashboardPage() {
  const { isMobile } = useResponsive();

  const { data: overview } = useQuery<OverviewStats>({
    queryKey: ['analytics', 'overview'],
    queryFn: () => apiFetch<OverviewStats>('/api/v1/analytics/overview'),
    staleTime: 60_000,
  });

  // Agar sendpointingiz boshqa bo‘lsa, shu URLni moslab o‘zgartirasiz:
  const { data: speciesRaw } = useQuery<SpeciesDistribution[]>({
    queryKey: ['analytics', 'species-distribution'],
    queryFn: () => apiFetch<SpeciesDistribution[]>('/api/v1/analytics/species-distribution'),
    staleTime: 5 * 60_000,
  });

  const totalAnimals = overview?.animals?.total ?? 0;

  const donutData = useMemo(
    () =>
      (speciesRaw ?? []).map((s) => ({
        species: s.species,
        value: s.count,
      })),
    [speciesRaw],
  );

  const centerLabel = totalAnimals > 0 ? String(totalAnimals) : '—';

  return (
    <div
      style={{
        background: '#ffffff',
        minHeight: 'calc(100vh - 56px)',
        padding: isMobile ? '14px 12px 24px' : '20px 24px 32px',
        display: 'flex',
        gap: 24,
      }}
    >
      {/* Chap tomondagi katta doirachali diogramma */}
      <div
        style={{
          flex: '0 0 420px',
          maxWidth: 480,
          borderRadius: 24,
          border: '1px solid #E5E7EB',
          boxShadow: '0 10px 30px rgba(15,23,42,0.06)',
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <h2
          style={{
            width: '100%',
            margin: 0,
            marginBottom: 16,
            fontSize: 16,
            fontWeight: 700,
            color: '#111827',
          }}
        >
          Podadagi jonivorlar turlari
        </h2>

        <div
          style={{
            width: '100%',
            maxWidth: 420,
            height: isMobile ? 260 : 320,
            position: 'relative',
          }}
        >
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="species"
                innerRadius="55%"
                outerRadius="85%"
                paddingAngle={2}
                stroke="#ffffff"
                strokeWidth={2}
                labelLine={false}
                label={DonutLabel as any}
              >
                {donutData.map((entry, index) => (
                  <Cell key={index} fill={COLORS[entry.species] ?? '#9CA3AF'} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          {/* Markazdagi jami son va yozuv */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <span
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: '#111827',
              }}
            >
              {centerLabel}
            </span>
            <span
              style={{
                marginTop: 4,
                fontSize: 11,
                fontWeight: 500,
                color: '#6B7280',
              }}
            >
              Jami jonivorlar soni
            </span>
          </div>
        </div>
      </div>

      {/* O'ng tomon hozircha bo'sh, keyin boshqa komponentlar qo'shamiz */}
      <div style={{ flex: 1 }} />
    </div>
  );
}