/**
 * Live Feed Card Component.
 * 
 * Displays individual weight measurement with animation.
 */

import { Scale, Camera, Clock } from 'lucide-react';
import type { LiveWeightUpdate } from '../../../shared/types';
import { formatDistanceToNow } from 'date-fns';

interface LiveFeedCardProps {
  measurement: LiveWeightUpdate;
  isNew?: boolean;
}

export function LiveFeedCard({ measurement, isNew = false }: LiveFeedCardProps) {
  const {
    animal_tag_id,
    estimated_weight_kg,
    confidence_score,
    camera_id,
    timestamp,
  } = measurement;
  
  // Format confidence as percentage
  const confidencePercent = (confidence_score * 100).toFixed(0);
  
  // Determine confidence badge color
  const getConfidenceBadge = () => {
    if (confidence_score >= 0.9) {
      return 'badge-success';
    } else if (confidence_score >= 0.7) {
      return 'badge-warning';
    } else {
      return 'badge-danger';
    }
  };
  
  // Format timestamp
  const timeAgo = formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  
  return (
    <div 
      className={`card hover:shadow-md transition-all duration-300 ${
        isNew ? 'ring-2 ring-primary-500 animate-pulse-slow' : ''
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        {/* Animal Tag */}
        <div>
          <h3 className="text-lg font-bold text-gray-900">
            {animal_tag_id}
          </h3>
          <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
            <Clock className="h-3 w-3" />
            {timeAgo}
          </p>
        </div>
        
        {/* New Badge */}
        {isNew && (
          <span className="badge bg-primary-100 text-primary-700 animate-pulse">
            New
          </span>
        )}
      </div>
      
      {/* Weight Display */}
      <div className="mb-3">
        <div className="flex items-baseline gap-2">
          <Scale className="h-5 w-5 text-primary-600" />
          <span className="text-3xl font-bold text-gray-900">
            {estimated_weight_kg.toFixed(1)}
          </span>
          <span className="text-lg text-gray-600">kg</span>
        </div>
      </div>
      
      {/* Metadata */}
      <div className="flex items-center justify-between text-sm">
        {/* Camera */}
        <div className="flex items-center gap-1.5 text-gray-600">
          <Camera className="h-4 w-4" />
          <span>{camera_id}</span>
        </div>
        
        {/* Confidence */}
        <span className={`badge ${getConfidenceBadge()}`}>
          {confidencePercent}% confidence
        </span>
      </div>
    </div>
  );
}
