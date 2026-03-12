"""
Camera tests uchun pytest fixture lar.

Muammo: test_rtsp_camera.py va test_usb_camera.py @patch('cv2.VideoCapture') bilan
birgalikda mock_opencv_capture fixture idan foydalanadi.

  @patch('cv2.VideoCapture')
  def test_start_success(self, mock_capture_class, mock_opencv_capture):
      mock_capture_class.return_value = mock_opencv_capture
      ...

  - mock_capture_class → @patch dekoratori inject qiladi (birinchi argument)
  - mock_opencv_capture → pytest fixture (bu fayl orqali)
"""
import pytest
from unittest.mock import MagicMock
import numpy as np

import cv2


# ---------------------------------------------------------------------------
# Muvaffaqiyatli VideoCapture (isOpened → True)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_opencv_capture():
    """
    cv2.VideoCapture mock — muvaffaqiyatli ulanish.

    Kamero to'g'ri ishlagandek ko'rsatadi:
      - isOpened() → True
      - read()     → (True, 640x480 BGR frame)
      - get(FPS)   → 25.0
      - get(WIDTH) → 640
      - get(HEIGHT)→ 480
    """
    mock = MagicMock()
    mock.isOpened.return_value = True

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock.read.return_value = (True, frame)

    # get() uchun side_effect QO'YMAYMIZ — testlar o'zlari kerak bo'lganda
    # mock_opencv_capture.get.return_value = ... deb o'zgartiradi.
    # side_effect qo'yilsa, return_value ni override qilib bo'lmaydi (MagicMock qoidasi).
    mock.get.return_value = 25.0  # default: 25 FPS / 640x480
    return mock


# ---------------------------------------------------------------------------
# Muvaffaqiyatsiz VideoCapture (isOpened → False)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_opencv_capture_failed():
    """
    cv2.VideoCapture mock — ulanish muvaffaqiyatsiz.

    Kamera ochilmagan holatni taqlid qiladi:
      - isOpened() → False
      - read()     → (False, None)
    """
    mock = MagicMock()
    mock.isOpened.return_value = False
    mock.read.return_value = (False, None)
    return mock