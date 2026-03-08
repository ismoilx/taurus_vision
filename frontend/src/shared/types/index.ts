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
// TRACKER TYPES
// =============================================================================

/** Bitta track ning holati */
export type TrackState = 'tentative' | 'unidentified' | 'identified' | 'lost';

/** Bitta kuzatilayotgan qoramol (tracker dan keladi) */
export interface TrackedAnimal {
  track_id:             number;        // Vaqtincha ID (tracker beradi)
  animal_id:            number | null; // Haqiqiy ID (faqat identified da)
  tag_id:               string | null; // Masalan: "JNV-042" (faqat identified da)
  state:                TrackState;
  bbox_color:           'orange' | 'red' | 'green';
  bbox: {
    x: number;   // cx normalized
    y: number;   // cy normalized
    w: number;
    h: number;
  };
  confidence:           number;   // YOLO detection confidence
  identification_score: number;   // Cosine similarity (0 = tanilmagan)
  id_attempts:          number;   // Necha marta urinildi
}

/** Tracker stats */
export interface TrackerStats {
  active_tracks:         number;
  identified_tracks:     number;
  unidentified_tracks:   number;
  total_tracks_created:  number;
  total_identifications: number;
  total_body_attempts:   number;
  total_muzzle_attempts: number;
  frame_count:           number;
}

/** Backend dan keladigan tracked_detections WS xabari */
export interface TrackedDetectionsMessage {
  type:   'tracked_detections';
  camera: string;
  tracks: TrackedAnimal[];
  stats:  TrackerStats;
}

// =============================================================================
// WEBSOCKET MESSAGE TYPES
// =============================================================================

/**
 * Backend dan keladigan barcha WebSocket xabar turlari:
 *   - connection         : Ulangandan keyin bir marta keladi
 *   - detection          : Legacy (eski pipeline) — hali qoldirilgan
 *   - tracked_detections : Yangi tracker pipeline (CattleTracker)
 *   - heartbeat          : Har 30 soniyada ulanishni tirik ushlab turadi
 */
export interface WebSocketMessage {
  type: 'connection' | 'detection' | 'tracked_detections' | 'heartbeat'
      | 'alert' | 'new_alert' | 'pipeline_status' | 'pipeline_update'
      | 'animal_update';
  status?: string;
  message?: string;
  timestamp?: string;
  active_connections?: number;

  // detection (legacy)
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

  // tracked_detections (yangi)
  camera?:  string;
  tracks?:  TrackedAnimal[];
  stats?:   TrackerStats;
}

// =============================================================================
// LIVE WEIGHT UPDATE (LiveFeedPage detection log uchun)
// =============================================================================

export interface LiveWeightUpdate {
  animal_id:            number;
  animal_tag_id:        string;
  estimated_weight_kg:  number;
  confidence_score:     number;
  camera_id:            string;
  timestamp:            string;
}

// =============================================================================
// LIVE TRACKED UPDATE (LiveFeedPage tracker log uchun)
// =============================================================================

export interface LiveTrackedUpdate {
  camera_id:    string;
  track_id:     number;
  animal_id:    number | null;
  tag_id:       string | null;
  state:        TrackState;
  bbox_color:   'orange' | 'red' | 'green';
  confidence:   number;
  id_score:     number;
  timestamp:    string;
}