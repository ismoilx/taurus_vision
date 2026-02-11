export enum ConnectionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error',
}

export interface WebSocketMessage {
  type: 'connection' | 'weight_update' | 'heartbeat';
  data?: any;
  status?: string;
  message?: string;
  timestamp?: number;
}

export interface LiveWeightUpdate {
  animal_id: number;
  animal_tag_id: string;
  estimated_weight_kg: number;
  confidence_score: number;
  camera_id: string;
  timestamp: string;
}
