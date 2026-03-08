"""
PyTorch stub — test muhiti uchun.
Haqiqiy torch o'rnatilmaganda import xatosiz o'tishi uchun.
"""
import numpy as np
from contextlib import contextmanager


# ── Tensor ────────────────────────────────────────────────────────────────────

class Tensor:
    def __init__(self, data):
        if isinstance(data, np.ndarray):
            self._data = data
        else:
            self._data = np.array(data, dtype=np.float32)

    def numpy(self):
        return self._data.astype(np.float32)

    def squeeze(self, dim=None):
        if dim is not None:
            return Tensor(np.squeeze(self._data, axis=dim))
        return Tensor(np.squeeze(self._data))

    def to(self, device):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def __repr__(self):
        return f"Tensor(shape={self._data.shape})"


def from_numpy(arr: np.ndarray) -> Tensor:
    return Tensor(arr)


def zeros(*shape, dtype=None):
    return Tensor(np.zeros(shape, dtype=np.float32))


def ones(*shape, dtype=None):
    return Tensor(np.ones(shape, dtype=np.float32))


def randn(*shape):
    return Tensor(np.random.randn(*shape).astype(np.float32))


def no_grad():
    return _NoGradContext()


class _NoGradContext:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __call__(self, fn):
        return fn


@contextmanager
def inference_mode():
    yield


# ── Device ────────────────────────────────────────────────────────────────────

def device(name: str):
    return name


def cuda_is_available():
    return False


class cuda:
    @staticmethod
    def is_available():
        return False


# ── nn module (re-exported) ───────────────────────────────────────────────────

from torch import nn