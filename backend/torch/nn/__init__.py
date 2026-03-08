"""
torch.nn stub — test muhiti uchun.
"""
import numpy as np


class Module:
    """Base neural network module stub."""

    def __init__(self):
        self._modules = {}
        self._parameters = {}

    def __call__(self, x):
        return x

    def eval(self):
        return self

    def train(self, mode=True):
        return self

    def to(self, device):
        return self

    def parameters(self):
        return iter([])

    def forward(self, x):
        return x


class Sequential(Module):
    def __init__(self, *modules):
        super().__init__()
        self._seq = list(modules)

    def __call__(self, x):
        result = x
        for m in self._seq:
            result = m(result) if callable(m) else result
        return result


class AdaptiveAvgPool2d(Module):
    def __init__(self, output_size):
        super().__init__()
        self.output_size = output_size

    def __call__(self, x):
        return x


class Flatten(Module):
    def __init__(self, start_dim=1):
        super().__init__()

    def __call__(self, x):
        from torch import Tensor
        import numpy as np
        if isinstance(x, Tensor):
            return Tensor(x._data.reshape(x._data.shape[0], -1))
        return x


class Linear(Module):
    def __init__(self, in_features, out_features, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features


class ReLU(Module):
    def __call__(self, x):
        return x


class Dropout(Module):
    def __init__(self, p=0.5):
        super().__init__()


class BatchNorm2d(Module):
    def __init__(self, num_features):
        super().__init__()


class Conv2d(Module):
    def __init__(self, in_channels, out_channels, kernel_size, **kwargs):
        super().__init__()


class Parameter:
    def __init__(self, data, requires_grad=True):
        self.data = data
        self.requires_grad = requires_grad