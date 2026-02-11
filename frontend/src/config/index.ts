/**
 * Application configuration.
 * 
 * Centralizes environment variables and app constants.
 */

export const config = {
  // API endpoints
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000',
  
  // Application
  appName: import.meta.env.VITE_APP_NAME || 'Taurus Vision',
  appVersion: import.meta.env.VITE_APP_VERSION || '0.1.0',
  
  // WebSocket
  ws: {
    // Reconnection settings (exponential backoff)
    reconnectInterval: 1000, // Start at 1 second
    reconnectIntervalMax: 30000, // Max 30 seconds
    reconnectDecay: 1.5, // Exponential multiplier
    maxReconnectAttempts: 10, // Give up after 10 attempts
  },
  
  // UI
  ui: {
    maxRecentMeasurements: 50, // Max items in live feed
    updateAnimationDuration: 300, // ms
  },
} as const;

export default config;