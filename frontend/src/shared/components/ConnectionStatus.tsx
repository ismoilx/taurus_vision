import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { ConnectionStatus as Status } from '../types';

interface ConnectionStatusProps {
  status: Status;
  reconnectAttempt?: number;
}

export function ConnectionStatus({ status, reconnectAttempt = 0 }: ConnectionStatusProps) {
  // Tailwind purge-safe: all classes written in full, no dynamic strings
  const cfg = {
    [Status.CONNECTED]: {
      wrap: 'bg-green-50',
      dot:  'bg-green-500',
      ping: 'bg-green-400',
      icon: Wifi,
      iconCls: 'text-green-600',
      text: 'Connected',
      textCls: 'text-green-700',
      animate: false,
    },
    [Status.CONNECTING]: {
      wrap: 'bg-blue-50',
      dot:  'bg-blue-500',
      ping: 'bg-blue-400',
      icon: Loader2,
      iconCls: 'text-blue-600',
      text: 'Connecting...',
      textCls: 'text-blue-700',
      animate: true,
    },
    [Status.RECONNECTING]: {
      wrap: 'bg-yellow-50',
      dot:  'bg-yellow-500',
      ping: 'bg-yellow-400',
      icon: Loader2,
      iconCls: 'text-yellow-600',
      text: `Reconnecting (${reconnectAttempt})...`,
      textCls: 'text-yellow-700',
      animate: true,
    },
    [Status.ERROR]: {
      wrap: 'bg-red-50',
      dot:  'bg-red-500',
      ping: 'bg-red-400',
      icon: WifiOff,
      iconCls: 'text-red-600',
      text: 'Connection Error',
      textCls: 'text-red-700',
      animate: false,
    },
    [Status.DISCONNECTED]: {
      wrap: 'bg-gray-100',
      dot:  'bg-gray-400',
      ping: 'bg-gray-300',
      icon: WifiOff,
      iconCls: 'text-gray-500',
      text: 'Disconnected',
      textCls: 'text-gray-600',
      animate: false,
    },
  } as const;

  const c = cfg[status] ?? cfg[Status.DISCONNECTED];
  const Icon = c.icon;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${c.wrap}`}>
      {/* Dot */}
      <span className="relative flex h-2 w-2">
        {c.animate && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${c.ping} opacity-75`} />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${c.dot}`} />
      </span>

      {/* Icon */}
      <Icon className={`h-4 w-4 ${c.iconCls} ${c.animate ? 'animate-spin' : ''}`} />

      {/* Text */}
      <span className={`text-sm font-medium ${c.textCls}`}>{c.text}</span>
    </div>
  );
}