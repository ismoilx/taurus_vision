/**
 * Taurus Vision — Shared TypeScript Types
 *
 * WebSocket va API javob tiplari.
 */

// =============================================================================
// WEBSOCKET CONNECTION STATUS
// =============================================================================

export type ConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'error';

export const ConnectionStatus = {
  CONNECTING:   'connecting',
  CONNECTED:    'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
  ERROR:        'error',
} as const;

// =============================================================================
// WEBSOCKET MESSAGE TYPES
// =============================================================================

/**
 * Backend dan keladigan barcha WebSocket xabar turlari:
 *   - connection : Ulangandan keyin bir marta keladi
 *   - detection  : Har yangi jonivor aniqlanganda (pipeline aktiv bo'lsa)
 *   - heartbeat  : Har 30 soniyada ulanishni tirik ushlab turadi
 */
export interface WebSocketMessage {
  type: 'connection' | 'detection' | 'heartbeat';
  status?: string;          // connection xabarida
  message?: string;         // connection xabarida
  timestamp?: string;       // ISO 8601
  active_connections?: number;

  // detection xabarida quyidagi maydonlar bo'ladi
  camera_id?:            string;
  animal_id?:            number | null;
  animal_tag_id?:        string;
  class_name?:           string;
  confidence?:           number;
  confidence_score?:     number;
  estimated_weight_kg?:  number;
  bbox?:                 { x: number; y: number; w: number; h: number };
  identified?:           boolean;
  pipeline_stats?:       { fps: number; frames: number };
}

// =============================================================================
// LIVE WEIGHT UPDATE (LiveFeedPage uchun maplab ishlatiladigan format)
// =============================================================================

export interface LiveWeightUpdate {
  animal_id:            number;
  animal_tag_id:        string;
  estimated_weight_kg:  number;
  confidence_score:     number;
  camera_id:            string;
  timestamp:            string;
}