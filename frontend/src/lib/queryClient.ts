/**
 * Taurus Vision — TanStack Query Client
 *
 * ARXITEKTURA: "Server Push + Infinite Cache"
 *
 *   1. Ma'lumot bir marta API dan yuklanadi → keshda saqlanadi
 *   2. Tab yopilguncha kesh O'CHIRIIMAYDI (staleTime: Infinity)
 *   3. WebSocket event kelganda → queryClient.setQueryData() orqali
 *      kesh yangilanadi → UI darhol rerender bo'ladi (API call yo'q!)
 *
 * OQIM:
 *   Foydalanuvchi kirdi → API → kesh (♾️)
 *   Boshqa sahifaga o'tdi → keshdan 0ms da
 *   WS detection keldi → kesh yangilandi → UI o'zgardi
 *   Tab yopildi → kesh o'chirildi
 *
 * staleTime: Infinity — ma'lumot hech qachon "eskirgan" hisoblanmaydi
 *   ya'ni sahifaga qaytganda HECH QACHON background refetch bo'lmaydi.
 *   Faqat WebSocket yoki explicit invalidate() orqali yangilanadi.
 *
 * gcTime: Infinity — xotiradan hech qachon o'chirilmaydi (tab ochiq bo'lsa)
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // ♾️ ASOSIY O'ZGARISH: hech qachon "stale" emas → refetch yo'q
      staleTime: Infinity,

      // Tab yopilguncha xotiradan o'chirilmaydi
      gcTime: Infinity,

      // Fokus qaytganda refetch yo'q — WS o'zi yangilaydi
      refetchOnWindowFocus: false,

      // Xato bo'lsa 1 marta urinadi (2 edi → sahifalar qotib qolardi)
      retry: 1,
      retryDelay: 1_500,
    },
    mutations: {
      retry: 0,
    },
  },
});

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const queryKeys = {
  animals: {
    all:    ['animals'] as const,
    search: (params: Record<string, unknown>) => ['animals', 'search', params] as const,
    detail: (id: number) => ['animals', id] as const,
  },

  analytics: {
    overview:        ['analytics', 'overview'] as const,
    weightTrend:     (days: number) => ['analytics', 'weight-trend', days] as const,
    hourlyDetection: (from: string, to: string) => ['analytics', 'hourly', from, to] as const,
    health:          ['analytics', 'health'] as const,
  },

  pipeline: {
    status: ['pipeline', 'status'] as const,
  },

  alerts: {
    all:  ['alerts'] as const,
    list: (filter: string) => ['alerts', filter] as const,
    stats: ['alerts', 'stats'] as const,
  },

  predictions: {
    farmSummary: (date?: string) => ['predictions', 'farm-summary', date ?? 'today'] as const,
    atRisk:      ['predictions', 'at-risk'] as const,
    modelStatus: ['predictions', 'model-status'] as const,
  },
} as const;