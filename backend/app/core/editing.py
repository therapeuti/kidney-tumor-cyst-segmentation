from collections import deque
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw

from backend.app.core.coordinate import axis_index
from backend.app.core.viewer import from_display_orientation, to_display_orientation


def _empty_mask(width: int, height: int) -> Image.Image:
    return Image.new("1", (width, height), 0)


def brush_mask(width: int, height: int, points: Iterable[tuple[float, float]], radius: int) -> np.ndarray:
    image = _empty_mask(width, height)
    draw = ImageDraw.Draw(image)
    points = list(points)
    if not points:
        return np.zeros((height, width), dtype=bool)

    if len(points) == 1:
        x, y = points[0]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=1)
    else:
        for start, end in zip(points[:-1], points[1:]):
            draw.line((start[0], start[1], end[0], end[1]), fill=1, width=max(1, radius * 2))
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=1)

    return np.array(image, dtype=bool)


def polygon_mask(width: int, height: int, vertices: Iterable[tuple[float, float]]) -> np.ndarray:
    image = _empty_mask(width, height)
    draw = ImageDraw.Draw(image)
    vertices = list(vertices)
    if len(vertices) >= 3:
        draw.polygon(vertices, outline=1, fill=1)
    return np.array(image, dtype=bool)


def flood_fill_mask(slice_data: np.ndarray, x: int, y: int) -> np.ndarray:
    """Create a mask of the connected region at (x, y) with the same label value."""
    height, width = slice_data.shape
    if x < 0 or x >= width or y < 0 or y >= height:
        return np.zeros_like(slice_data, dtype=bool)

    target_label = int(slice_data[y, x])
    mask = np.zeros_like(slice_data, dtype=bool)
    stack = [(x, y)]
    visited = set()

    while stack:
        cx, cy = stack.pop()
        if (cx, cy) in visited:
            continue
        if cx < 0 or cx >= width or cy < 0 or cy >= height:
            continue
        if int(slice_data[cy, cx]) != target_label:
            continue
        visited.add((cx, cy))
        mask[cy, cx] = True
        stack.append((cx - 1, cy))
        stack.append((cx + 1, cy))
        stack.append((cx, cy - 1))
        stack.append((cx, cy + 1))

    return mask


def interpolate_slices(
    volume: np.ndarray,
    axis: str,
    start: int,
    end: int,
    label: int,
) -> tuple[np.ndarray, int]:
    """Interpolate a label between two slices using morphological distance-based blending.

    Returns (modified_volume, changed_voxels).
    """
    from scipy import ndimage as _ndi

    ax = axis_index(axis)
    if start > end:
        start, end = end, start
    if end - start <= 1:
        return volume.copy(), 0

    def get_raw(vol, idx):
        if ax == 0:
            return vol[idx, :, :]
        if ax == 1:
            return vol[:, idx, :]
        return vol[:, :, idx]

    def set_raw(vol, idx, data):
        if ax == 0:
            vol[idx, :, :] = data
        elif ax == 1:
            vol[:, idx, :] = data
        else:
            vol[:, :, idx] = data

    mask_start = (get_raw(volume, start) == label).astype(float)
    mask_end = (get_raw(volume, end) == label).astype(float)

    result = volume.copy()
    changed = 0

    for si in range(start + 1, end):
        t = (si - start) / (end - start)
        interp = mask_start * (1 - t) + mask_end * t
        fill = interp >= 0.5
        current = get_raw(result, si)
        new_slice = current.copy()
        to_fill = fill & (current != label)
        new_slice[to_fill] = label
        changed += int(np.sum(to_fill))
        set_raw(result, si, new_slice)

    return result, changed


def display_to_volume(axis: str, x: int, y: int, slice_index: int, display_height: int) -> tuple[int, int, int]:
    """Convert display (x, y) on a given axis/slice to volume (i, j, k) coordinates."""
    flipped_y = display_height - 1 - y
    ax = axis_index(axis)
    if ax == 0:
        return (slice_index, x, flipped_y)
    if ax == 1:
        return (x, slice_index, flipped_y)
    return (x, flipped_y, slice_index)


def region_grow_3d(
    ct_volume: np.ndarray,
    seed: tuple[int, int, int],
    tolerance: float,
    max_voxels: int,
    neighborhood_radius: int,
) -> tuple[np.ndarray, float, float]:
    """3D region growing from a seed point on CT data.

    Uses the seed point's HU value ± tolerance (fixed HU range).

    Returns (boolean mask, seed_hu, tolerance_used).
    """
    shape = ct_volume.shape
    seed_hu = float(ct_volume[seed])
    lower = seed_hu - tolerance
    upper = seed_hu + tolerance

    mask = np.zeros(shape, dtype=bool)
    mask[seed] = True

    queue: deque[tuple[int, int, int]] = deque([seed])
    count = 1
    neighbors = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

    while queue and count < max_voxels:
        ci, cj, ck = queue.popleft()
        for di, dj, dk in neighbors:
            ni, nj, nk = ci + di, cj + dj, ck + dk
            if 0 <= ni < shape[0] and 0 <= nj < shape[1] and 0 <= nk < shape[2]:
                if not mask[ni, nj, nk]:
                    val = float(ct_volume[ni, nj, nk])
                    if lower <= val <= upper:
                        mask[ni, nj, nk] = True
                        queue.append((ni, nj, nk))
                        count += 1
                        if count >= max_voxels:
                            break

    return mask, seed_hu, tolerance


def relabel_3d_component(
    volume: np.ndarray, axis: str, slice_index: int, x: int, y: int, to_label: int,
) -> tuple[np.ndarray, int, int]:
    """Relabel the 3D connected component at the clicked point.

    Returns (modified_volume, changed_voxels, from_label).
    """
    from scipy import ndimage as _ndi

    ax = axis_index(axis)
    slice_view = extract_slice_view(volume, axis, slice_index)
    height, width = slice_view.shape
    if x < 0 or x >= width or y < 0 or y >= height:
        return volume.copy(), 0, 0

    from_label = int(slice_view[y, x])
    if from_label == 0 or from_label == to_label:
        return volume.copy(), 0, from_label

    # Display orientation is flipud(raw.T), so reverse:
    # display[y, x] = raw[x, H-1-y]  where H = display height
    flipped_y = height - 1 - y
    if ax == 0:
        vox = (slice_index, x, flipped_y)
    elif ax == 1:
        vox = (x, slice_index, flipped_y)
    else:
        vox = (x, flipped_y, slice_index)

    # Find 3D connected component
    label_mask = volume == from_label
    labeled, _ = _ndi.label(label_mask)
    comp_id = labeled[vox]
    if comp_id == 0:
        return volume.copy(), 0, from_label

    comp_mask = labeled == comp_id
    changed = int(np.sum(comp_mask))

    result = volume.copy()
    result[comp_mask] = to_label
    return result, changed, from_label


def extract_slice_view(volume: np.ndarray, axis: str, index: int) -> np.ndarray:
    ax = axis_index(axis)
    if ax == 0:
        return to_display_orientation(volume[index, :, :])
    if ax == 1:
        return to_display_orientation(volume[:, index, :])
    return to_display_orientation(volume[:, :, index])


def write_slice_view(volume: np.ndarray, axis: str, index: int, slice_data: np.ndarray) -> None:
    raw_slice = from_display_orientation(slice_data)
    ax = axis_index(axis)
    if ax == 0:
        volume[index, :, :] = raw_slice
    elif ax == 1:
        volume[:, index, :] = raw_slice
    else:
        volume[:, :, index] = raw_slice


def apply_edit_to_slice(
    slice_data: np.ndarray,
    edit_mask: np.ndarray,
    label: int,
    mode: str,
    overwrite: bool,
    preserve_labels: list[int],
) -> tuple[np.ndarray, int]:
    result = slice_data.copy()
    preserve = np.isin(result, preserve_labels) if preserve_labels else np.zeros_like(result, dtype=bool)

    if mode == "erase":
        target = edit_mask & ~preserve
        changed = int(np.sum(result[target] != 0))
        result[target] = 0
        return result, changed

    if mode != "paint" and mode != "fill":
        raise ValueError(f"Unsupported edit mode: {mode}")

    target = edit_mask & ~preserve
    if not overwrite:
        target &= (result == 0) | (result == label)

    changed = int(np.sum(result[target] != label))
    result[target] = label
    return result, changed
