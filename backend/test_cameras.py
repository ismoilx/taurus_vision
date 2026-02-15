"""
Camera implementation test script.

Tests RTSP and USB camera implementations manually.
"""

import asyncio
import time
import cv2
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.camera.usb_camera import USBCamera
from app.services.camera.rtsp_camera import RTSPCamera


def test_usb_camera():
    """Test USB camera implementation."""
    print("=" * 70)
    print("Testing USB Camera")
    print("=" * 70)
    
    # List available cameras
    print("\nScanning for USB cameras...")
    available = USBCamera.list_available_cameras()
    print(f"Available USB cameras: {available}")
    
    if not available:
        print("WARNING: No USB cameras found")
        return False
    
    # Test first camera
    device_index = available[0]
    print(f"\nTesting camera at index {device_index}...")
    
    camera = USBCamera(
        camera_id="USB-TEST-01",
        device_index=device_index,
        width=640,
        height=480,
        fps=10,
    )
    
    try:
        # Start camera
        camera.start()
        
        if not camera.is_opened():
            print("ERROR: Failed to open camera")
            return False
        
        print(f"Camera opened successfully")
        print(f"Resolution: {camera.get_resolution()}")
        print(f"FPS: {camera.get_fps()}")
        
        # Capture frames
        print("\nCapturing 10 frames...")
        success_count = 0
        
        for i in range(10):
            frame = camera.get_frame()
            
            if frame is not None:
                success_count += 1
                print(f"Frame {i+1}: {frame.shape} - OK")
            else:
                print(f"Frame {i+1}: FAILED")
            
            time.sleep(0.1)
        
        # Show statistics
        stats = camera.get_stats()
        print(f"\nStatistics:")
        print(f"  Frames captured: {stats['frame_count']}")
        print(f"  Errors: {stats['error_count']}")
        print(f"  Success rate: {success_count}/10")
        
        # Stop camera
        camera.stop()
        print("\nCamera stopped")
        
        return success_count >= 8  # At least 80% success
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rtsp_camera():
    """Test RTSP camera implementation."""
    print("\n" + "=" * 70)
    print("Testing RTSP Camera")
    print("=" * 70)
    
    # Test URL
    rtsp_url = input("\nEnter RTSP URL (or press Enter to skip): ").strip()
    
    if not rtsp_url:
        print("Skipping RTSP test (no URL provided)")
        return None
    
    print(f"\nTesting RTSP stream: {rtsp_url}")
    
    camera = RTSPCamera(
        camera_id="RTSP-TEST-01",
        rtsp_url=rtsp_url,
        width=640,
        height=480,
        fps=10,
        connection_timeout=5,
    )
    
    try:
        # Start camera
        print("Connecting...")
        camera.start()
        
        # Wait for connection
        time.sleep(2)
        
        if not camera.is_opened():
            print("ERROR: Failed to connect to RTSP stream")
            print("Possible reasons:")
            print("  - Invalid URL")
            print("  - Network not reachable")
            print("  - Authentication failed")
            print("  - Stream not available")
            return False
        
        print(f"RTSP stream connected")
        print(f"Resolution: {camera.get_resolution()}")
        print(f"FPS: {camera.get_fps()}")
        
        # Capture frames
        print("\nCapturing 10 frames...")
        success_count = 0
        
        for i in range(10):
            frame = camera.get_frame()
            
            if frame is not None:
                success_count += 1
                print(f"Frame {i+1}: {frame.shape} - OK")
            else:
                print(f"Frame {i+1}: FAILED")
            
            time.sleep(0.1)
        
        # Show statistics
        stats = camera.get_stats()
        print(f"\nStatistics:")
        print(f"  Frames captured: {stats['frame_count']}")
        print(f"  Errors: {stats['error_count']}")
        print(f"  Success rate: {success_count}/10")
        
        # Stop camera
        camera.stop()
        print("\nCamera stopped")
        
        return success_count >= 8
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all camera tests."""
    print("\n" + "=" * 70)
    print("CAMERA IMPLEMENTATION TEST SUITE")
    print("=" * 70)
    
    results = {}
    
    # Test USB camera
    results['usb'] = test_usb_camera()
    
    # Test RTSP camera
    results['rtsp'] = test_rtsp_camera()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    
    if results['usb'] is True:
        print("USB Camera:  PASS")
    elif results['usb'] is False:
        print("USB Camera:  FAIL")
    else:
        print("USB Camera:  SKIPPED")
    
    if results['rtsp'] is True:
        print("RTSP Camera: PASS")
    elif results['rtsp'] is False:
        print("RTSP Camera: FAIL")
    else:
        print("RTSP Camera: SKIPPED")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
