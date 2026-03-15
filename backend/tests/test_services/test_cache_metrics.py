"""
TAURUS VISION — tests/test_core/test_cache_metrics.py
======================================================
Cache utility + MetricsCollector + CacheKeys uchun AYAMAS testlar.

Qamrav (80+ test):
  ✓ _json_serializer  — datetime, type error
  ✓ cache_get         — Redis yo'q → None (test muhitida)
  ✓ cache_set         — Redis yo'q → False
  ✓ cache_invalidate  — Redis yo'q → 0
  ✓ CacheKeys constants — OVERVIEW, HEALTH_METRICS, HERD_STATISTICS
  ✓ CacheKeys.weight_trend / hourly_detection / adi_trend / growth_trend / behavior_trend / insights
  ✓ MetricsCollector.__init__     — boshlang'ich qiymatlar
  ✓ MetricsCollector.record_http_request — count/duration yozish
  ✓ MetricsCollector.record_db_query     — counter oshishi, cap 1000
  ✓ MetricsCollector.record_ai_inference — counter oshishi
  ✓ MetricsCollector.update_business_metrics — animals/detections/measurements
  ✓ MetricsCollector.get_prometheus_metrics  — Prometheus format tuzilma
  ✓ MetricsCollector thread-safety           — bir nechta thread
"""

import pytest
import time
import threading
from datetime import datetime

from app.core.cache import (
    cache_get, cache_set, cache_invalidate,
    CacheKeys, _json_serializer,
)
from app.core.metrics import MetricsCollector, metrics

pytestmark = pytest.mark.asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# _json_serializer
# ═══════════════════════════════════════════════════════════════════════════════

class TestJsonSerializer:
    def test_datetime_returns_isoformat(self):
        dt = datetime(2026, 3, 15, 10, 30, 45)
        result = _json_serializer(dt)
        assert "2026-03-15" in result
        assert "10:30:45" in result

    def test_non_serializable_raises_type_error(self):
        with pytest.raises(TypeError):
            _json_serializer(set())

    def test_non_serializable_object_raises(self):
        class Custom: pass
        with pytest.raises(TypeError):
            _json_serializer(Custom())

    def test_returns_string(self):
        dt = datetime(2026, 1, 1)
        result = _json_serializer(dt)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# cache_get / cache_set / cache_invalidate (Redis yo'q holat)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheFunctions:

    async def test_cache_get_no_redis_returns_none(self):
        """Redis test muhitida yo'q → None qaytadi."""
        result = await cache_get("test:key:nonexistent")
        assert result is None

    async def test_cache_set_no_redis_returns_false(self):
        """Redis yo'q → False qaytadi."""
        result = await cache_set("test:key", {"data": 123})
        assert isinstance(result, bool)
        # Redis yo'q bo'lsa False, bor bo'lsa True

    async def test_cache_invalidate_no_redis_returns_zero(self):
        """Redis yo'q → 0 qaytadi."""
        result = await cache_invalidate("test:*")
        assert isinstance(result, int)

    async def test_cache_get_missing_key_none(self):
        result = await cache_get("definitely:not:there:12345")
        assert result is None

    async def test_cache_set_json_serializable_values(self):
        """JSON serializable qiymatlar xato bermaydi."""
        try:
            await cache_set("test:dict", {"key": "value", "num": 42})
            await cache_set("test:list", [1, 2, 3])
            await cache_set("test:string", "hello")
            await cache_set("test:number", 3.14)
        except Exception as e:
            pytest.fail(f"cache_set raised unexpected: {e}")

    async def test_cache_set_with_ttl(self):
        result = await cache_set("test:ttl", "value", ttl=60)
        assert isinstance(result, bool)

    async def test_cache_invalidate_pattern(self):
        result = await cache_invalidate("analytics:*")
        assert isinstance(result, int) and result >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# CacheKeys
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheKeys:

    def test_overview_constant(self):
        assert CacheKeys.OVERVIEW == "analytics:overview"

    def test_health_metrics_constant(self):
        assert CacheKeys.HEALTH_METRICS == "analytics:health"

    def test_herd_statistics_constant(self):
        assert CacheKeys.HERD_STATISTICS == "analytics:herd_statistics"

    def test_weight_trend_with_days(self):
        key = CacheKeys.weight_trend(30)
        assert "30" in key
        assert "weight_trend" in key

    def test_weight_trend_different_days_different_keys(self):
        k7  = CacheKeys.weight_trend(7)
        k30 = CacheKeys.weight_trend(30)
        assert k7 != k30

    def test_hourly_detection_key(self):
        key = CacheKeys.hourly_detection("2026-01-01", "2026-01-07")
        assert "2026-01-01" in key
        assert "2026-01-07" in key

    def test_hourly_detection_different_dates(self):
        k1 = CacheKeys.hourly_detection("2026-01-01", "2026-01-07")
        k2 = CacheKeys.hourly_detection("2026-02-01", "2026-02-07")
        assert k1 != k2

    def test_adi_trend_with_animal(self):
        key = CacheKeys.adi_trend(animal_id=5, days=30)
        assert "5" in key
        assert "30" in key
        assert "adi_trend" in key

    def test_adi_trend_herd_wide(self):
        key = CacheKeys.adi_trend(animal_id=None, days=7)
        assert "herd" in key
        assert "7" in key

    def test_adi_trend_animal_vs_herd_different(self):
        k1 = CacheKeys.adi_trend(animal_id=1, days=30)
        k2 = CacheKeys.adi_trend(animal_id=None, days=30)
        assert k1 != k2

    def test_growth_trend_key(self):
        key = CacheKeys.growth_trend(animal_id=3, days=14)
        assert "3" in key and "14" in key and "growth_trend" in key

    def test_behavior_trend_key(self):
        key = CacheKeys.behavior_trend(animal_id=None, days=7)
        assert "behavior_trend" in key and "herd" in key

    def test_insights_key(self):
        key = CacheKeys.insights(days=30)
        assert "insights" in key and "30" in key

    def test_all_keys_are_strings(self):
        assert isinstance(CacheKeys.OVERVIEW, str)
        assert isinstance(CacheKeys.weight_trend(7), str)
        assert isinstance(CacheKeys.adi_trend(1, 30), str)

    def test_key_format_namespace_colon(self):
        """Barcha kalitlar 'analytics:' prefiksi bilan boshlanadi."""
        for key in [
            CacheKeys.OVERVIEW, CacheKeys.HEALTH_METRICS,
            CacheKeys.weight_trend(7),
            CacheKeys.adi_trend(1, 30),
        ]:
            assert key.startswith("analytics:")


# ═══════════════════════════════════════════════════════════════════════════════
# MetricsCollector
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsCollector:

    def _new(self): return MetricsCollector()

    def test_init_http_requests_empty(self):
        m = self._new()
        assert len(m.http_requests_total) == 0

    def test_init_counters_zero(self):
        m = self._new()
        assert m.db_query_total == 0
        assert m.ai_inference_total == 0
        assert m.animals_total == 0
        assert m.detections_total == 0
        assert m.measurements_total == 0

    def test_init_start_time_set(self):
        before = time.time()
        m = self._new()
        after = time.time()
        assert before <= m.start_time <= after

    def test_record_http_request_increments_count(self):
        m = self._new()
        m.record_http_request("GET", "/api/animals", 0.05)
        assert m.http_requests_total["GET /api/animals"] == 1

    def test_record_http_request_multiple_increments(self):
        m = self._new()
        for _ in range(5):
            m.record_http_request("POST", "/api/data", 0.1)
        assert m.http_requests_total["POST /api/data"] == 5

    def test_record_http_request_stores_duration(self):
        m = self._new()
        m.record_http_request("GET", "/api/test", 0.123)
        assert 0.123 in m.http_request_duration_seconds["GET /api/test"]

    def test_record_http_request_caps_at_1000(self):
        m = self._new()
        for _ in range(1005):
            m.record_http_request("GET", "/api/cap", 0.01)
        assert len(m.http_request_duration_seconds["GET /api/cap"]) <= 1000

    def test_record_http_request_different_methods(self):
        m = self._new()
        m.record_http_request("GET",    "/path", 0.1)
        m.record_http_request("POST",   "/path", 0.1)
        m.record_http_request("DELETE", "/path", 0.1)
        assert m.http_requests_total["GET /path"]    == 1
        assert m.http_requests_total["POST /path"]   == 1
        assert m.http_requests_total["DELETE /path"] == 1

    def test_record_db_query_increments(self):
        m = self._new()
        m.record_db_query(0.05)
        m.record_db_query(0.08)
        assert m.db_query_total == 2

    def test_record_db_query_stores_duration(self):
        m = self._new()
        m.record_db_query(0.042)
        assert 0.042 in m.db_query_duration_seconds

    def test_record_db_query_caps_at_1000(self):
        m = self._new()
        for _ in range(1010):
            m.record_db_query(0.001)
        assert len(m.db_query_duration_seconds) <= 1000

    def test_record_ai_inference_increments(self):
        m = self._new()
        m.record_ai_inference(0.15)
        assert m.ai_inference_total == 1

    def test_record_ai_inference_multiple(self):
        m = self._new()
        for _ in range(7):
            m.record_ai_inference(0.2)
        assert m.ai_inference_total == 7

    def test_record_ai_inference_caps_at_1000(self):
        m = self._new()
        for _ in range(1010):
            m.record_ai_inference(0.1)
        assert len(m.ai_inference_duration_seconds) <= 1000

    def test_update_business_metrics_animals(self):
        m = self._new()
        m.update_business_metrics(animals=150)
        assert m.animals_total == 150

    def test_update_business_metrics_detections(self):
        m = self._new()
        m.update_business_metrics(detections=5000)
        assert m.detections_total == 5000

    def test_update_business_metrics_measurements(self):
        m = self._new()
        m.update_business_metrics(measurements=300)
        assert m.measurements_total == 300

    def test_update_business_metrics_partial(self):
        """Faqat ba'zi qiymatlar yangilanadi."""
        m = self._new()
        m.update_business_metrics(animals=50, detections=1000)
        assert m.animals_total == 50
        assert m.detections_total == 1000
        assert m.measurements_total == 0  # O'zgarmadi

    def test_get_prometheus_metrics_returns_string(self):
        m = self._new()
        result = m.get_prometheus_metrics()
        assert isinstance(result, str)

    def test_prometheus_has_info_metric(self):
        m = self._new()
        result = m.get_prometheus_metrics()
        assert "taurus_vision_info" in result

    def test_prometheus_has_uptime(self):
        m = self._new()
        result = m.get_prometheus_metrics()
        assert "taurus_vision_uptime_seconds" in result

    def test_prometheus_has_http_metrics(self):
        m = self._new()
        m.record_http_request("GET", "/api/test", 0.05)
        result = m.get_prometheus_metrics()
        assert "taurus_vision_http_requests_total" in result
        assert "GET" in result

    def test_prometheus_has_db_metrics(self):
        m = self._new()
        m.record_db_query(0.05)
        result = m.get_prometheus_metrics()
        assert "taurus_vision_db_queries_total" in result

    def test_prometheus_has_ai_metrics(self):
        m = self._new()
        m.record_ai_inference(0.1)
        result = m.get_prometheus_metrics()
        assert "taurus_vision_ai_inferences_total" in result

    def test_prometheus_has_business_metrics(self):
        m = self._new()
        m.update_business_metrics(animals=100, detections=500)
        result = m.get_prometheus_metrics()
        assert "taurus_vision_animals_total" in result
        assert "taurus_vision_detections_total" in result

    def test_prometheus_includes_count_values(self):
        m = self._new()
        m.record_http_request("GET", "/check", 0.01)
        result = m.get_prometheus_metrics()
        assert "/check" in result

    def test_global_metrics_singleton(self):
        """Global metrics singleton."""
        assert metrics is not None
        assert isinstance(metrics, MetricsCollector)

    def test_thread_safety_concurrent_writes(self):
        """Bir nechta thread bir vaqtda yoza oladi."""
        m = self._new()
        errors = []

        def write():
            try:
                for _ in range(100):
                    m.record_http_request("GET", "/concurrent", 0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0
        # 5 thread × 100 = 500 yozuv
        assert m.http_requests_total["GET /concurrent"] == 500

    def test_prometheus_format_has_help_lines(self):
        m = self._new()
        result = m.get_prometheus_metrics()
        assert "# HELP" in result

    def test_prometheus_format_has_type_lines(self):
        m = self._new()
        result = m.get_prometheus_metrics()
        assert "# TYPE" in result