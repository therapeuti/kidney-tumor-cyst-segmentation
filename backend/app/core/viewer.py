from io import BytesIO

import numpy as np
from PIL import Image

from backend.app.core.coordinate import axis_index


def _extract_raw_slice(volume, axis: str, index: int) -> np.ndarray:
    ax = axis_index(axis)
    if index < 0 or index >= volume.shape[ax]:
        raise ValueError(f"Slice index out of range for axis {axis}: {index}")

    if ax == 0:
        slice_data = volume[index, :, :]
    elif ax == 1:
        slice_data = volume[:, index, :]
    else:
        slice_data = volume[:, :, index]
    return np.asarray(slice_data)


def to_display_orientation(slice_data: np.ndarray) -> np.ndarray:
    return np.flipud(np.asarray(slice_data).T)


def from_display_orientation(slice_data: np.ndarray) -> np.ndarray:
    return np.flipud(np.asarray(slice_data)).T


def extract_slice(volume, axis: str, index: int) -> np.ndarray:
    return to_display_orientation(_extract_raw_slice(volume, axis, index))


def render_ct_slice_png(slice_data: np.ndarray, window: float, level: float) -> bytes:
    lower = level - window / 2.0
    upper = level + window / 2.0
    if upper <= lower:
        upper = lower + 1.0

    clipped = np.clip(slice_data.astype(np.float32), lower, upper)
    normalized = (clipped - lower) / (upper - lower)
    image = (normalized * 255.0).astype(np.uint8)

    buffer = BytesIO()
    Image.fromarray(image, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()
