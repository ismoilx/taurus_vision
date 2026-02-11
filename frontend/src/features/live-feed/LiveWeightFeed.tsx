/**
 * Live Weight Feed Feature.
 * 
 * Real-time dashboard for weight measurements from AI cameras.
 */

import { useState, useEffect, useCallback } from 'react';
import { Activity, AlertCircle } from 'lucide-react';
import { useWebSocket } from '../../shared/hooks/useWebSocket';
import { ConnectionStatus } from '../../shared/components/ConnectionStatus';
import { LiveFeedCard } from './components/LiveFeedCard';
import { LiveWeightUpdate, WebSocketMessage, ConnectionStatus as Status } from '../../shared/types';
import config from '../../config';

export function LiveWeightFeed() {
  const [measurements, setMeasurements] = useState<LiveWeightUpdate[]>([]);
  const [newMeasurementId, setNewMeasurementId] = useState<number | null>(null);
  
  // WebSocket connection
  const { status, lastMessage } = useWebSocket(
    `${config.wsUrl}/api/v1/live/ws`,
    {
      onMessage: handleMessage,
      onConnect: handleConnect,
      onDisconnect: handleDisconnect,
    }
  );
  
  /**
   * Handle incoming WebSocket messages.
   */
  function handleMessage(message: WebSocketMessage) {
    console.log('[LiveFeed] Message received:', message);
    
    if (message.type === 'weight_update' && message.data) {
      // Add new measurement to the top of the list
      setMeasurements(prev => {
        const newList = [message.data!, ...prev];
        
        // Keep only last N measurements
        if (newList.length > config.ui.maxRecentMeasurements) {
          return newList.slice(0, config.ui.maxRecentMeasurements);
        }
        
        return newList;
      });
      
      // Highlight new measurement
      setNewMeasurementId(message.data.measurement_id);
      
      // Remove highlight after animation
      setTimeout(() => {
        setNewMeasurementId(null);
      }, config.ui.updateAnimationDuration + 1000);
    }
  }
  
  /**
   * Handle connection established.
   */
  function handleConnect() {
    console.log('[LiveFeed] Connected to live feed');
  }
  
  /**
   * Handle disconnection.
   */
  function handleDisconnect() {
    console.log('[LiveFeed] Disconnected from live feed');
  }
  
  /**
   * Fetch recent measurements on mount (REST API).
   */
  const fetchRecentMeasurements = useCallback(async () => {
    try {
      const response = await fetch(
        `${config.apiUrl}/api/v1/weights/recent?limit=20&min_confidence=0.5`
      );
      
      if (response.ok) {
        const data = await response.json();
        setMeasurements(data);
        console.log('[LiveFeed] Loaded recent measurements:', data.length);
      }
    } catch (error) {
      console.error('[LiveFeed] Failed to fetch recent measurements:', error);
    }
  }, []);
  
  // Load initial data
  useEffect(() => {
    fetchRecentMeasurements();
  }, [fetchRecentMeasurements]);
  
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-primary-100 rounded-lg">
              <Activity className="h-8 w-8 text-primary-600" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Live Weight Feed
              </h1>
              <p className="text-gray-600 mt-1">
                Real-time AI weight measurements
              </p>
            </div>
          </div>
          
          {/* Connection Status */}
          <ConnectionStatus status={status} />
        </div>
      </div>
      
      {/* Stats Bar */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Total Measurements */}
          <div className="card">
            <div className="text-sm text-gray-600 mb-1">Total Displayed</div>
            <div className="text-2xl font-bold text-gray-900">
              {measurements.length}
            </div>
          </div>
          
          {/* Connection Status */}
          <div className="card">
            <div className="text-sm text-gray-600 mb-1">Status</div>
            <div className="text-2xl font-bold">
              {status === Status.CONNECTED ? (
                <span className="text-success-600">Live</span>
              ) : (
                <span className="text-danger-600">Offline</span>
              )}
            </div>
          </div>
          
          {/* Average Confidence */}
          <div className="card">
            <div className="text-sm text-gray-600 mb-1">Avg Confidence</div>
            <div className="text-2xl font-bold text-gray-900">
              {measurements.length > 0
                ? (
                    (measurements.reduce((sum, m) => sum + m.confidence_score, 0) /
                      measurements.length) *
                    100
                  ).toFixed(0)
                : 0}%
            </div>
          </div>
        </div>
      </div>
      
      {/* Feed */}
      <div className="max-w-7xl mx-auto">
        {status === Status.ERROR && (
          <div className="card bg-danger-50 border-danger-200 mb-6">
            <div className="flex items-center gap-3 text-danger-700">
              <AlertCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">Connection Error</p>
                <p className="text-sm">
                  Unable to connect to live feed. Please check your connection and refresh.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {measurements.length === 0 ? (
          <div className="card text-center py-12">
            <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 text-lg">
              {status === Status.CONNECTED
                ? 'Waiting for measurements...'
                : 'Connecting to live feed...'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {measurements.map((measurement) => (
              <LiveFeedCard
                key={measurement.measurement_id}
                measurement={measurement}
                isNew={measurement.measurement_id === newMeasurementId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
