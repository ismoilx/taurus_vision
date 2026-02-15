"""
Prometheus metrics for monitoring.

Provides application metrics in Prometheus format:
- Request counts and latencies
- Database query times
- AI inference times
- System resources
- Business metrics (animals, detections, etc.)
"""

from typing import Dict, Any
import time
from datetime import datetime
from collections import defaultdict
import threading


class MetricsCollector:
    """
    Lightweight metrics collector for Prometheus.
    
    Tracks:
    - HTTP request counts and durations
    - Database operation times
    - AI inference times
    - Business metrics
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self._lock = threading.Lock()
        
        # HTTP metrics
        self.http_requests_total = defaultdict(int)  # {method_path: count}
        self.http_request_duration_seconds = defaultdict(list)  # {method_path: [durations]}
        
        # Database metrics
        self.db_query_duration_seconds = []
        self.db_query_total = 0
        
        # AI metrics
        self.ai_inference_duration_seconds = []
        self.ai_inference_total = 0
        
        # Business metrics (updated by services)
        self.animals_total = 0
        self.detections_total = 0
        self.measurements_total = 0
        
        # System start time
        self.start_time = time.time()
    
    def record_http_request(self, method: str, path: str, duration: float) -> None:
        """Record HTTP request metrics."""
        with self._lock:
            key = f"{method} {path}"
            self.http_requests_total[key] += 1
            self.http_request_duration_seconds[key].append(duration)
            
            # Keep only last 1000 measurements per endpoint
            if len(self.http_request_duration_seconds[key]) > 1000:
                self.http_request_duration_seconds[key] = \
                    self.http_request_duration_seconds[key][-1000:]
    
    def record_db_query(self, duration: float) -> None:
        """Record database query time."""
        with self._lock:
            self.db_query_total += 1
            self.db_query_duration_seconds.append(duration)
            
            # Keep only last 1000 measurements
            if len(self.db_query_duration_seconds) > 1000:
                self.db_query_duration_seconds = self.db_query_duration_seconds[-1000:]
    
    def record_ai_inference(self, duration: float) -> None:
        """Record AI inference time."""
        with self._lock:
            self.ai_inference_total += 1
            self.ai_inference_duration_seconds.append(duration)
            
            # Keep only last 1000 measurements
            if len(self.ai_inference_duration_seconds) > 1000:
                self.ai_inference_duration_seconds = self.ai_inference_duration_seconds[-1000:]
    
    def update_business_metrics(
        self,
        animals: int = None,
        detections: int = None,
        measurements: int = None,
    ) -> None:
        """Update business metrics from database."""
        with self._lock:
            if animals is not None:
                self.animals_total = animals
            if detections is not None:
                self.detections_total = detections
            if measurements is not None:
                self.measurements_total = measurements
    
    def get_prometheus_metrics(self) -> str:
        """
        Generate Prometheus-formatted metrics.
        
        Returns:
            Metrics in Prometheus exposition format
        """
        lines = []
        
        # Metadata
        lines.append("# HELP taurus_vision_info Application information")
        lines.append("# TYPE taurus_vision_info gauge")
        lines.append(f'taurus_vision_info{{version="0.1.0"}} 1')
        lines.append("")
        
        # Uptime
        uptime = time.time() - self.start_time
        lines.append("# HELP taurus_vision_uptime_seconds Application uptime in seconds")
        lines.append("# TYPE taurus_vision_uptime_seconds counter")
        lines.append(f"taurus_vision_uptime_seconds {uptime:.2f}")
        lines.append("")
        
        # HTTP request counts
        lines.append("# HELP taurus_vision_http_requests_total Total HTTP requests")
        lines.append("# TYPE taurus_vision_http_requests_total counter")
        with self._lock:
            for key, count in self.http_requests_total.items():
                method, path = key.split(" ", 1)
                lines.append(
                    f'taurus_vision_http_requests_total{{method="{method}",path="{path}"}} {count}'
                )
        lines.append("")
        
        # HTTP request durations
        lines.append("# HELP taurus_vision_http_request_duration_seconds HTTP request duration")
        lines.append("# TYPE taurus_vision_http_request_duration_seconds summary")
        with self._lock:
            for key, durations in self.http_request_duration_seconds.items():
                if durations:
                    method, path = key.split(" ", 1)
                    avg = sum(durations) / len(durations)
                    lines.append(
                        f'taurus_vision_http_request_duration_seconds{{method="{method}",path="{path}"}} {avg:.4f}'
                    )
        lines.append("")
        
        # Database queries
        lines.append("# HELP taurus_vision_db_queries_total Total database queries")
        lines.append("# TYPE taurus_vision_db_queries_total counter")
        lines.append(f"taurus_vision_db_queries_total {self.db_query_total}")
        lines.append("")
        
        with self._lock:
            if self.db_query_duration_seconds:
                avg_db = sum(self.db_query_duration_seconds) / len(self.db_query_duration_seconds)
                lines.append("# HELP taurus_vision_db_query_duration_seconds Average database query duration")
                lines.append("# TYPE taurus_vision_db_query_duration_seconds gauge")
                lines.append(f"taurus_vision_db_query_duration_seconds {avg_db:.4f}")
                lines.append("")
        
        # AI inferences
        lines.append("# HELP taurus_vision_ai_inferences_total Total AI inferences")
        lines.append("# TYPE taurus_vision_ai_inferences_total counter")
        lines.append(f"taurus_vision_ai_inferences_total {self.ai_inference_total}")
        lines.append("")
        
        with self._lock:
            if self.ai_inference_duration_seconds:
                avg_ai = sum(self.ai_inference_duration_seconds) / len(self.ai_inference_duration_seconds)
                lines.append("# HELP taurus_vision_ai_inference_duration_seconds Average AI inference duration")
                lines.append("# TYPE taurus_vision_ai_inference_duration_seconds gauge")
                lines.append(f"taurus_vision_ai_inference_duration_seconds {avg_ai:.4f}")
                lines.append("")
        
        # Business metrics
        lines.append("# HELP taurus_vision_animals_total Total animals in system")
        lines.append("# TYPE taurus_vision_animals_total gauge")
        lines.append(f"taurus_vision_animals_total {self.animals_total}")
        lines.append("")
        
        lines.append("# HELP taurus_vision_detections_total Total detections recorded")
        lines.append("# TYPE taurus_vision_detections_total gauge")
        lines.append(f"taurus_vision_detections_total {self.detections_total}")
        lines.append("")
        
        lines.append("# HELP taurus_vision_measurements_total Total weight measurements")
        lines.append("# TYPE taurus_vision_measurements_total gauge")
        lines.append(f"taurus_vision_measurements_total {self.measurements_total}")
        lines.append("")
        
        return "\n".join(lines)


# Global metrics collector
metrics = MetricsCollector()
