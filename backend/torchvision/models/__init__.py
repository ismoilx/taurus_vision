"""
torchvision.models stub — test muhiti uchun.
"""
import numpy as np


class _Weights:
    IMAGENET1K_V1 = "imagenet1k_v1"


class MobileNet_V2_Weights:
    IMAGENET1K_V1 = "imagenet1k_v1"
    DEFAULT = "imagenet1k_v1"


class _FakeFeatures:
    """MobileNetV2 features stub."""
    def __call__(self, x):
        return x


class _FakeMobileNetV2:
    """MobileNetV2 model stub."""
    def __init__(self):
        self.features = _FakeFeatures()

    def parameters(self):
        return iter([])

    def eval(self):
        return self

    def to(self, device):
        return self

    def __call__(self, x):
        from torch import Tensor
        import numpy as np
        # Return fake 1280-dim embedding
        batch = 1
        fake = np.random.randn(batch, 1280).astype(np.float32)
        return Tensor(fake)


def mobilenet_v2(weights=None, pretrained=False):
    """Return fake MobileNetV2 model."""
    return _FakeMobileNetV2()


def resnet50(weights=None, pretrained=False):
    return _FakeMobileNetV2()


def efficientnet_b0(weights=None, pretrained=False):
    return _FakeMobileNetV2()