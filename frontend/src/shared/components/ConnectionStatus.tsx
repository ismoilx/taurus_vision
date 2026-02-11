/**
 * Connection status indicator.
 * 
 * Displays WebSocket connection state with visual feedback.
 */

import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { ConnectionStatus as Status } from '../types';

interface ConnectionStatusProps {
  status: Status;
  reconnectAttempt?: number;
}

export function ConnectionStatus({ status, reconnectAttempt = 0 }: ConnectionStatusProps) {
  const getStatusConfig = () => {
    switch (status) {
      case Status.CONNECTED:
        return {
          icon: Wifi,
          text: 'Connected',
          color: 'text-success-600',
          bgColor: 'bg-success-50',
          dotColor: 'bg-success-500',
          animate: false,
        };
      
      case Status.CONNECTING:
        return {
          icon: Loader2,
          text: 'Connecting...',
          color: 'text-primary-600',
          bgColor: 'bg-primary-50',
          dotColor: 'bg-primary-500',
          animate: true,
        };
      
      case Status.RECONNECTING:
        return {
          icon: Loader2,
          text: `Reconnecting (${reconnectAttempt})...`,
          color: 'text-warning-600',
          bgColor: 'bg-warning-50',
          dotColor: 'bg-warning-500',
          animate: true,
        };
      
      case Status.DISCONNECTED:
      case Status.ERROR:
        return {
          icon: WifiOff,
          text: status === Status.ERROR ? 'Connection Error' : 'Disconnected',
          color: 'text-danger-600',
          bgColor: 'bg-danger-50',
          dotColor: 'bg-danger-500',
          animate: false,
        };
      
      default:
        return {
          icon: WifiOff,
          text: 'Unknown',
          color: 'text-gray-600',
          bgColor: 'bg-gray-50',
          dotColor: 'bg-gray-500',
          animate: false,
        };
    }
  };
  
  const config = getStatusConfig();
  const Icon = config.icon;
  
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${config.bgColor}`}>
      {/* Animated dot */}
      <span className="relative flex h-2 w-2">
        {config.animate && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.dotColor} opacity-75`}></span>
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${config.dotColor}`}></span>
      </span>
      
      {/* Icon */}
      <Icon 
        className={`h-4 w-4 ${config.color} ${config.animate ? 'animate-spin' : ''}`}
      />
      
      {/* Text */}
      <span className={`text-sm font-medium ${config.color}`}>
        {config.text}
      </span>
    </div>
  );
}