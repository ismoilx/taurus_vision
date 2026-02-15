#!/usr/bin/env python3
"""
Test runner script for Taurus Vision.

Runs different test suites with various configurations:
- Unit tests
- Integration tests
- Coverage reports
- Performance benchmarks
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print results."""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}\n")
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"\n❌ FAILED: {description}")
        return False
    else:
        print(f"\n✅ PASSED: {description}")
        return True


def main():
    """Main test runner."""
    # Change to backend directory
    backend_dir = Path(__file__).parent
    
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                  TAURUS VISION - TEST SUITE                    ║
    ║                    Sprint 2: Camera Tests                      ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    tests = []
    
    # 1. Unit tests - Camera Services
    tests.append((
        "python -m pytest tests/test_services/test_camera/ -v -m 'unit and camera' --tb=short",
        "Unit Tests: Camera Services"
    ))
    
    # 2. Unit tests - Simulated Camera
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_simulated_camera.py -v",
        "Unit Tests: Simulated Camera"
    ))
    
    # 3. Unit tests - Camera Manager
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_camera_manager.py -v",
        "Unit Tests: Camera Manager"
    ))
    
    # 4. Unit tests - Camera Factory
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_camera_factory.py -v",
        "Unit Tests: Camera Factory"
    ))
    
    # 5. Unit tests - RTSP Camera
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_rtsp_camera.py -v",
        "Unit Tests: RTSP Camera"
    ))
    
    # 6. Unit tests - USB Camera
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_usb_camera.py -v",
        "Unit Tests: USB Camera"
    ))
    
    # 7. Unit tests - Edge Cases
    tests.append((
        "python -m pytest tests/test_services/test_camera/test_edge_cases.py -v",
        "Unit Tests: Edge Cases"
    ))
    
    # 8. API tests
    tests.append((
        "python -m pytest tests/test_api/ -v -m 'api'",
        "API Tests: Camera Endpoints"
    ))
    
    # 9. Integration tests
    tests.append((
        "python -m pytest tests/test_integration/ -v -m 'integration'",
        "Integration Tests: Camera + Detection"
    ))
    
    # 10. All tests with coverage
    tests.append((
        "python -m pytest tests/ -v --cov=app.services.camera --cov=app.api.v1.endpoints.cameras --cov-report=term-missing --cov-report=html",
        "Full Test Suite with Coverage"
    ))
    
    # Run tests
    results = []
    for cmd, description in tests:
        success = run_command(cmd, description)
        results.append((description, success))
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}\n")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {passed}/{total} test suites passed")
    print(f"{'='*70}\n")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {total - passed} test suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
