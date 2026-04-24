from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.spatial import ConvexHull, Delaunay


LABEL_METADATA = {
    0: {"key": "background", "name_en": "Background", "name_cli": "BG"},
    1: {"key": "kidney", "name_en": "Kidney", "name_cli": "Kidney"},
    2: {"key": "tumor", "name_en": "Tumor", "name_cli": "Tumor"},
    3: {"key": "cyst", "name_en": "Cyst", "name_cli": "Cyst"},
}


FUNCTION_LABELS = {
    "1": "Label Analysis",
    "2": "Remove Isolated",
    "3": "Remove Low Intensity (<= 0)",
    "4": "Remove High Intensity (>= threshold)",
    "5": "Smoothing (Tumor/Cyst/Organ)",
    "6": "Boundary Expansion (Kidney/Tumor/Cyst)",
    "7": "Boundary Trimming (Organ/Tumor/Cyst)",
    "8": "Staircase Fill",
    "9": "Protrusion Removal",
    "10": "Fill Internal Holes",
    "11": "Relabel Isolated Kidney to Tumor",
    "12": "Convex Hull Labeling (Tumor/Cyst)",
    "13": "Merge Segmentations",
    "14": "Resample & Merge",
    "15": "Phase Comparison",
    "m": "Region Restricted Run",
    "r": "Rollback",
}


@dataclass(frozen=True)
class RemoveIsolatedParams:
    target: str
    keep_n: int = 2


@dataclass(frozen=True)
class RemoveHighIntensityParams:
    threshold: float = 400.0


@dataclass(frozen=True)
class FillHolesParams:
    target: str


@dataclass(frozen=True)
class SmoothParams:
    target: str
    sigma: float = 1.0
    close_iter: int = 3
    open_iter: int = 2
    keep_n: int = 2


@dataclass(frozen=True)
class ExpandParams:
    target_label: int
    mode: str
    threshold: float | None = None
    tolerance: float | None = None
    iterations: int = 5
    overwrite_kidney: bool = True


@dataclass(frozen=True)
class TrimBoundaryParams:
    target: str
    mode: str
    threshold: float | None = None
    tolerance: float | None = None
    max_iter: int = 1


@dataclass
class OperationSummary:
    operation: str
    changed_voxels: int = 0
    details: dict = field(default_factory=dict)


def get_label_name(label: int) -> str:
    meta = LABEL_METADATA.get(int(label))
    if meta is None:
        return f"label{int(label)}"
    return meta["name_cli"]


def surface_ratio(binary_mask: np.ndarray) -> float:
    total = int(np.sum(binary_mask))
    if total == 0:
        return 0.0
    eroded = ndimage.binary_erosion(binary_mask)
    surface = total - int(np.sum(eroded))
    return surface / total * 100.0


def remove_isolated(data: np.ndarray, params: RemoveIsolatedParams) -> tuple[np.ndarray, OperationSummary]:
    keep_n = params.keep_n if hasattr(params, "keep_n") else 2

    if params.target in ("1", "2", "3"):
        # Per-label mode: only process one specific label
        result = data.copy()
        details = {"target": params.target, "labels": []}
        result, label_summary = _remove_isolated_label(result, label=int(params.target), keep_n=keep_n)
        details["labels"].append(label_summary)
        changed = int(sum(item["removed_voxels"] for item in details["labels"]))
        return result, OperationSummary("remove_isolated", changed_voxels=changed, details=details)

    # "all" mode: find connected components across ALL labels (label > 0),
    # keep the largest keep_n components, remove everything else
    organ_mask = data > 0
    if not np.any(organ_mask):
        return data.copy(), OperationSummary("remove_isolated", details={"target": "all", "empty": True})

    labeled, n_comp = ndimage.label(organ_mask)
    if n_comp <= keep_n:
        return data.copy(), OperationSummary("remove_isolated", details={
            "target": "all", "components": int(n_comp),
            "kept_components": int(n_comp), "removed_components": 0, "removed_voxels": 0,
        })

    sizes = ndimage.sum(organ_mask, labeled, range(1, n_comp + 1))
    top_indices = np.argsort(sizes)[::-1][:keep_n]
    top_labels = set(int(i) + 1 for i in top_indices)

    result = data.copy()
    removed = 0
    for comp_idx in range(1, n_comp + 1):
        if comp_idx in top_labels:
            continue
        comp_mask = labeled == comp_idx
        removed += int(np.sum(comp_mask))
        result[comp_mask] = 0

    return result, OperationSummary("remove_isolated", changed_voxels=removed, details={
        "target": "all", "components": int(n_comp),
        "kept_components": keep_n, "removed_components": int(n_comp - keep_n),
        "removed_voxels": removed,
    })


def _remove_isolated_label(data: np.ndarray, label: int, keep_n: int) -> tuple[np.ndarray, dict]:
    mask = data == label
    if not np.any(mask):
        return data, {
            "label": label,
            "label_name": get_label_name(label),
            "components": 0,
            "kept_components": keep_n,
            "removed_components": 0,
            "removed_voxels": 0,
        }

    labeled, n_comp = ndimage.label(mask)
    if n_comp <= keep_n:
        return data, {
            "label": label,
            "label_name": get_label_name(label),
            "components": int(n_comp),
            "kept_components": int(n_comp),
            "removed_components": 0,
            "removed_voxels": 0,
        }

    sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
    top_indices = np.argsort(sizes)[::-1][:keep_n]
    top_labels = set(top_indices + 1)

    result = data.copy()
    removed = 0
    for comp_idx in range(1, n_comp + 1):
        if comp_idx in top_labels:
            continue
        comp_mask = labeled == comp_idx
        removed += int(np.sum(comp_mask))
        result[comp_mask] = 0

    return result, {
        "label": label,
        "label_name": get_label_name(label),
        "components": int(n_comp),
        "kept_components": int(keep_n),
        "removed_components": int(n_comp - keep_n),
        "removed_voxels": int(removed),
    }


def remove_low_intensity(data: np.ndarray, ct_data: np.ndarray | None) -> tuple[np.ndarray, OperationSummary]:
    if ct_data is None:
        raise ValueError("CT data is required for remove_low_intensity")

    low = ct_data <= 0
    result = data.copy()
    details = {"threshold": 0, "labels": []}

    for label in (1, 2):
        mask = (data == label) & low
        removed = int(np.sum(mask))
        result[mask] = 0
        details["labels"].append({
            "label": label,
            "label_name": get_label_name(label),
            "removed_voxels": removed,
        })

    changed = int(sum(item["removed_voxels"] for item in details["labels"]))
    return result, OperationSummary("remove_low_intensity", changed_voxels=changed, details=details)


def remove_high_intensity(
    data: np.ndarray,
    ct_data: np.ndarray | None,
    params: RemoveHighIntensityParams,
) -> tuple[np.ndarray, OperationSummary]:
    if ct_data is None:
        raise ValueError("CT data is required for remove_high_intensity")

    high = ct_data >= params.threshold
    result = data.copy()
    details = {"threshold": float(params.threshold), "labels": []}

    for label in (1, 2):
        mask = (data == label) & high
        removed = int(np.sum(mask))
        result[mask] = 0
        details["labels"].append({
            "label": label,
            "label_name": get_label_name(label),
            "removed_voxels": removed,
        })

    changed = int(sum(item["removed_voxels"] for item in details["labels"]))
    return result, OperationSummary("remove_high_intensity", changed_voxels=changed, details=details)


def fill_holes(data: np.ndarray, params: FillHolesParams) -> tuple[np.ndarray, OperationSummary]:
    result = data.copy()

    if params.target == "3":
        kidney_mask = data == 1
        tumor_mask = data == 2
        organ_mask = kidney_mask | tumor_mask
        filled = ndimage.binary_fill_holes(organ_mask).astype(np.uint8)
        new_voxels = (filled == 1) & ~organ_mask & (data != 3)
        result[new_voxels] = 1
        added = int(np.sum(new_voxels))
        return result, OperationSummary(
            "fill_holes",
            changed_voxels=added,
            details={"target": "organ", "assigned_label": 1, "added_voxels": added},
        )

    label = 3 if params.target == "4" else int(params.target)
    mask = data == label
    filled = ndimage.binary_fill_holes(mask).astype(np.uint8)
    new_voxels = (filled == 1) & ~mask
    result[new_voxels] = label
    added = int(np.sum(new_voxels))
    return result, OperationSummary(
        "fill_holes",
        changed_voxels=added,
        details={"target": get_label_name(label).lower(), "label": label, "added_voxels": added},
    )


def smooth(data: np.ndarray, zooms: tuple[float, float, float], params: SmoothParams) -> tuple[np.ndarray, OperationSummary]:
    target = params.target
    if target == "1":
        return _smooth_kidney(data, zooms, params)
    if target == "2":
        return _smooth_tumor(data, zooms, params)
    if target == "3":
        return _smooth_cyst(data, zooms, params)
    if target == "4":
        return _smooth_organ(data, zooms, params)
    raise ValueError(f"Unsupported smooth target: {target}")


def _sigma_voxels(sigma: float, zooms: tuple[float, float, float]) -> list[float]:
    return [sigma / float(z) for z in zooms]


def _smooth_kidney(data: np.ndarray, zooms: tuple[float, float, float], params: SmoothParams):
    kidney_mask = data == 1
    tumor_mask = data == 2
    cyst_mask = data == 3
    protect_mask = tumor_mask | cyst_mask
    before = int(np.sum(kidney_mask))
    if before == 0:
        return data.copy(), OperationSummary("smooth", details={"target": "kidney", "empty": True})

    mask = kidney_mask.astype(np.float64)
    struct = ndimage.generate_binary_structure(3, 1)
    if params.close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=params.close_iter).astype(np.float64)
    if params.open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=params.open_iter).astype(np.float64)

    smoothed = ndimage.gaussian_filter(mask, sigma=_sigma_voxels(params.sigma, zooms))
    mask_final = smoothed >= 0.5

    result = data.copy()
    lost = kidney_mask & ~mask_final
    result[lost] = 0
    new_kidney = mask_final & ~protect_mask & (result == 0)
    result[new_kidney] = 1

    after = int(np.sum(result == 1))
    return result, OperationSummary(
        "smooth",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target": "kidney",
            "before_voxels": before,
            "after_voxels": after,
            "before_surface": surface_ratio(kidney_mask.astype(np.uint8)),
            "after_surface": surface_ratio((result == 1).astype(np.uint8)),
        },
    )


def _smooth_tumor(data: np.ndarray, zooms: tuple[float, float, float], params: SmoothParams):
    tumor_mask = data == 2
    before = int(np.sum(tumor_mask))
    if before == 0:
        return data.copy(), OperationSummary("smooth", details={"target": "tumor", "empty": True})

    mask = tumor_mask.astype(np.float64)
    labeled, n_comp = ndimage.label(mask)
    removed_components = 0
    if n_comp > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        largest = np.argmax(sizes) + 1
        mask = (labeled == largest).astype(np.float64)
        removed_components = int(n_comp - 1)

    struct = ndimage.generate_binary_structure(3, 1)
    if params.close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=params.close_iter).astype(np.float64)
    if params.open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=params.open_iter).astype(np.float64)

    smoothed = ndimage.gaussian_filter(mask, sigma=_sigma_voxels(params.sigma, zooms))
    mask_final = smoothed >= 0.5

    result = data.copy()
    lost = tumor_mask & ~mask_final
    result[lost] = 0
    if int(np.sum(lost)) > 0:
        bg_dist = ndimage.distance_transform_edt(data != 0)
        kid_dist = ndimage.distance_transform_edt(data != 1)
        result[lost & (kid_dist < bg_dist)] = 1
    new_tumor = mask_final & (result != 3)
    result[new_tumor] = 2

    after = int(np.sum(result == 2))
    return result, OperationSummary(
        "smooth",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target": "tumor",
            "before_voxels": before,
            "after_voxels": after,
            "removed_components": removed_components,
            "before_surface": surface_ratio(tumor_mask.astype(np.uint8)),
            "after_surface": surface_ratio((result == 2).astype(np.uint8)),
        },
    )


def _smooth_cyst(data: np.ndarray, zooms: tuple[float, float, float], params: SmoothParams):
    cyst_mask = data == 3
    kidney_mask = data == 1
    before = int(np.sum(cyst_mask))
    if before == 0:
        return data.copy(), OperationSummary("smooth", details={"target": "cyst", "empty": True})

    allowed = kidney_mask | cyst_mask
    mask = cyst_mask.astype(np.float64)
    struct = ndimage.generate_binary_structure(3, 1)
    if params.close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=params.close_iter).astype(np.float64)
    if params.open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=params.open_iter).astype(np.float64)

    smoothed = ndimage.gaussian_filter(mask, sigma=_sigma_voxels(params.sigma, zooms))
    mask_final = (smoothed >= 0.5) & allowed
    mask_final = ndimage.binary_fill_holes(mask_final) & allowed

    result = data.copy()
    lost = cyst_mask & ~mask_final
    if int(np.sum(lost)) > 0:
        bg_dist = ndimage.distance_transform_edt(~(data == 0))
        kid_dist = ndimage.distance_transform_edt(~(data == 1))
        use_bg = bg_dist <= kid_dist
        result[lost & use_bg] = 0
        result[lost & ~use_bg] = 1
    result[mask_final] = 3

    after = int(np.sum(result == 3))
    return result, OperationSummary(
        "smooth",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target": "cyst",
            "before_voxels": before,
            "after_voxels": after,
            "before_surface": surface_ratio(cyst_mask.astype(np.uint8)),
            "after_surface": surface_ratio((result == 3).astype(np.uint8)),
        },
    )


def _smooth_organ(data: np.ndarray, zooms: tuple[float, float, float], params: SmoothParams):
    kidney_mask = data == 1
    tumor_mask = data == 2
    cyst_mask = data == 3
    before_kidney = int(np.sum(kidney_mask))
    if before_kidney == 0:
        return data.copy(), OperationSummary("smooth", details={"target": "organ", "empty": True})

    organ_mask = (kidney_mask | tumor_mask | cyst_mask).astype(np.uint8)
    labeled, n_comp = ndimage.label(organ_mask)
    removed_voxels = 0
    if n_comp > params.keep_n:
        sizes = ndimage.sum(organ_mask, labeled, range(1, n_comp + 1))
        top_indices = np.argsort(sizes)[::-1][: params.keep_n]
        top_labels = set(top_indices + 1)
        new_mask = np.zeros_like(organ_mask)
        for lbl in top_labels:
            new_mask[labeled == lbl] = 1
        removed_voxels = int(np.sum(organ_mask)) - int(np.sum(new_mask))
        organ_mask = new_mask.astype(np.uint8)
        labeled, n_comp = ndimage.label(organ_mask)

    struct = ndimage.generate_binary_structure(3, 1)
    smoothed_organ = np.zeros_like(organ_mask, dtype=np.uint8)
    for comp_id in range(1, n_comp + 1):
        comp = (labeled == comp_id).astype(np.float64)
        if params.close_iter > 0:
            comp = ndimage.binary_closing(comp, structure=struct, iterations=params.close_iter).astype(np.float64)
        if params.open_iter > 0:
            comp = ndimage.binary_opening(comp, structure=struct, iterations=params.open_iter).astype(np.float64)
        comp = ndimage.gaussian_filter(comp, sigma=_sigma_voxels(params.sigma, zooms))
        smoothed_organ = np.maximum(smoothed_organ, (comp >= 0.5).astype(np.uint8))

    result = data.copy()
    result[kidney_mask] = 0
    result[tumor_mask] = 0
    result[cyst_mask] = 0
    smoothed_mask = smoothed_organ == 1
    final_tumor = tumor_mask & smoothed_mask
    final_cyst = cyst_mask & smoothed_mask
    existing_organ = kidney_mask | tumor_mask | cyst_mask
    new_voxels = smoothed_mask & ~existing_organ
    new_labels = np.ones(data.shape, dtype=np.uint16)
    if int(np.sum(new_voxels)) > 0:
        min_dist = np.full(data.shape, np.inf)
        for lbl, lbl_mask in ((1, kidney_mask), (2, tumor_mask), (3, cyst_mask)):
            if not np.any(lbl_mask):
                continue
            dist = ndimage.distance_transform_edt(~lbl_mask)
            closer = dist < min_dist
            min_dist[closer] = dist[closer]
            new_labels[closer] = lbl
    final_kidney = (smoothed_mask & (kidney_mask | (new_voxels & (new_labels == 1)))) & ~final_tumor & ~final_cyst
    final_new_tumor = new_voxels & (new_labels == 2)
    final_new_cyst = new_voxels & (new_labels == 3)
    result[final_kidney] = 1
    result[final_tumor | final_new_tumor] = 2
    result[final_cyst | final_new_cyst] = 3

    return result, OperationSummary(
        "smooth",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target": "organ",
            "removed_voxels": removed_voxels,
            "before_surface": surface_ratio(organ_mask),
            "after_surface": surface_ratio((smoothed_organ == 1).astype(np.uint8)),
            "before_kidney_voxels": before_kidney,
            "after_kidney_voxels": int(np.sum(result == 1)),
        },
    )


def expand(data: np.ndarray, ct_data: np.ndarray | None, params: ExpandParams) -> tuple[np.ndarray, OperationSummary]:
    if ct_data is None:
        raise ValueError("CT data is required for expand")
    label = int(params.target_label)
    mask = data == label
    before = int(np.sum(mask))
    if before == 0:
        return data.copy(), OperationSummary("expand", details={"target_label": label, "empty": True})

    if label == 1:
        expandable = data == 0
    elif params.overwrite_kidney:
        expandable = (data == 0) | (data == 1)
    else:
        expandable = data == 0

    vals = ct_data[mask]
    val_mean = float(np.mean(vals))
    val_std = float(np.std(vals))
    if params.mode == "lower":
        threshold = float(params.threshold if params.threshold is not None else 120.0)
        hu_filter = ct_data >= threshold
        details = {"mode": "lower", "threshold": threshold}
    elif params.mode == "range":
        tolerance = float(params.tolerance if params.tolerance is not None else max(val_std * 2, 15))
        hu_lo = val_mean - tolerance
        hu_hi = val_mean + tolerance
        hu_filter = (ct_data >= hu_lo) & (ct_data <= hu_hi)
        details = {"mode": "range", "hu_lo": hu_lo, "hu_hi": hu_hi, "tolerance": tolerance}
    else:
        raise ValueError(f"Unsupported expand mode: {params.mode}")

    expand_mask = mask.copy()
    struct = ndimage.generate_binary_structure(3, 1)
    total_added = 0
    for _ in range(params.iterations):
        dilated = ndimage.binary_dilation(expand_mask, structure=struct)
        candidates = dilated & ~expand_mask & expandable
        accepted = candidates & hu_filter
        added = int(np.sum(accepted))
        total_added += added
        if added == 0:
            break
        expand_mask[accepted] = True

    result = data.copy()
    new_voxels = expand_mask & ~mask
    result[new_voxels] = label
    return result, OperationSummary(
        "expand",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target_label": label,
            "before_voxels": before,
            "after_voxels": int(np.sum(result == label)),
            "added_voxels": total_added,
            "label_mean": val_mean,
            "label_std": val_std,
            **details,
        },
    )


def trim_boundary(data: np.ndarray, ct_data: np.ndarray | None, params: TrimBoundaryParams) -> tuple[np.ndarray, OperationSummary]:
    if ct_data is None:
        raise ValueError("CT data is required for trim_boundary")
    if params.target == "1":
        return _trim_organ(data, ct_data, params)
    if params.target == "2":
        return _trim_single(data, ct_data, params, label=2, name="tumor")
    if params.target == "3":
        return _trim_single(data, ct_data, params, label=3, name="cyst")
    raise ValueError(f"Unsupported trim target: {params.target}")


def _build_trim_bad_mask(ct_data: np.ndarray, vals: np.ndarray, params: TrimBoundaryParams):
    val_mean = float(np.mean(vals))
    val_std = float(np.std(vals))
    if params.mode == "range":
        tolerance = float(params.tolerance if params.tolerance is not None else max(val_std * 2, 15))
        hu_lo = val_mean - tolerance
        hu_hi = val_mean + tolerance
        return (ct_data < hu_lo) | (ct_data > hu_hi), {"mode": "range", "hu_lo": hu_lo, "hu_hi": hu_hi, "tolerance": tolerance, "mean": val_mean, "std": val_std}
    if params.mode == "lower":
        threshold = float(params.threshold if params.threshold is not None else 0.0)
        return ct_data < threshold, {"mode": "lower", "threshold": threshold, "mean": val_mean, "std": val_std}
    if params.mode == "upper":
        threshold = float(params.threshold if params.threshold is not None else 400.0)
        return ct_data > threshold, {"mode": "upper", "threshold": threshold, "mean": val_mean, "std": val_std}
    raise ValueError(f"Unsupported trim mode: {params.mode}")


def _trim_single(data: np.ndarray, ct_data: np.ndarray, params: TrimBoundaryParams, label: int, name: str):
    mask = data == label
    before = int(np.sum(mask))
    if before == 0:
        return data.copy(), OperationSummary("trim_boundary", details={"target": name, "empty": True})
    hu_bad, condition = _build_trim_bad_mask(ct_data, ct_data[mask], params)
    struct = ndimage.generate_binary_structure(3, 1)
    result = data.copy()
    trimmed = mask.copy()
    bg_mask = data == 0
    for _ in range(params.max_iter):
        bg_adj = ndimage.binary_dilation(bg_mask, structure=struct)
        surface = trimmed & bg_adj
        to_remove = surface & hu_bad
        removed = int(np.sum(to_remove))
        if removed == 0:
            break
        trimmed = trimmed & ~to_remove
        result[to_remove] = 0
        bg_mask = bg_mask | to_remove
    after = int(np.sum(trimmed))
    return result, OperationSummary(
        "trim_boundary",
        changed_voxels=int(np.sum(result != data)),
        details={"target": name, "before_voxels": before, "after_voxels": after, **condition},
    )


def _trim_organ(data: np.ndarray, ct_data: np.ndarray, params: TrimBoundaryParams):
    organ_mask = (data == 1) | (data == 2) | (data == 3)
    before = int(np.sum(organ_mask))
    if before == 0:
        return data.copy(), OperationSummary("trim_boundary", details={"target": "organ", "empty": True})
    hu_bad, condition = _build_trim_bad_mask(ct_data, ct_data[organ_mask], params)
    struct = ndimage.generate_binary_structure(3, 1)
    result = data.copy()
    trimmed = organ_mask.copy()
    bg_mask = data == 0
    for _ in range(params.max_iter):
        bg_adj = ndimage.binary_dilation(bg_mask, structure=struct)
        surface = trimmed & bg_adj
        to_remove = surface & hu_bad
        removed = int(np.sum(to_remove))
        if removed == 0:
            break
        trimmed = trimmed & ~to_remove
        result[to_remove] = 0
        bg_mask = bg_mask | to_remove
    after = int(np.sum(trimmed))
    return result, OperationSummary(
        "trim_boundary",
        changed_voxels=int(np.sum(result != data)),
        details={
            "target": "organ",
            "before_voxels": before,
            "after_voxels": after,
            "to_background": int(np.sum(organ_mask & ~trimmed)),
            **condition,
        },
    )


# ──────────────────────────────────────────────
# Convex Hull Labeling
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class LabelConvexParams:
    label: int  # 2=tumor, 3=cyst
    method: str  # "3d" or "2d"
    component_indices: list[int] | None = None  # None = all
    slice_axis: int = 0  # only used when method="2d"


def label_convex(data: np.ndarray, params: LabelConvexParams) -> tuple[np.ndarray, OperationSummary]:
    label = params.label
    seed_mask = data == label
    n_seed = int(np.sum(seed_mask))

    if n_seed == 0:
        return data.copy(), OperationSummary(
            "label_convex", details={"label": label, "empty": True}
        )

    protect_label = 3 if label == 2 else 2
    protect_mask = data == protect_label

    labeled_arr, n_comp = ndimage.label(seed_mask)
    comp_info = []
    for ci in range(1, n_comp + 1):
        comp_mask = labeled_arr == ci
        comp_size = int(np.sum(comp_mask))
        comp_coords = np.argwhere(comp_mask)
        comp_info.append({
            "index": ci,
            "size": comp_size,
            "slice_min": int(comp_coords[:, 0].min()),
            "slice_max": int(comp_coords[:, 0].max()),
            "mask": comp_mask,
        })
    comp_info.sort(key=lambda x: -x["size"])

    if params.component_indices is not None:
        selected = [comp_info[i] for i in params.component_indices if 0 <= i < len(comp_info)]
    else:
        selected = comp_info

    if not selected:
        return data.copy(), OperationSummary(
            "label_convex", details={"label": label, "no_selection": True}
        )

    result = data.copy()
    total_added = 0
    component_details = []

    for comp in selected:
        comp_seed = comp["mask"]
        comp_n = comp["size"]

        if params.method == "3d":
            fill_mask = _label_convex_3d_pure(data.shape, comp_seed)
        else:
            fill_mask = _label_convex_2d_pure(data.shape, comp_seed, axis=params.slice_axis)

        if fill_mask is None:
            component_details.append({
                "size": comp_n, "added": 0, "skipped": True,
            })
            continue

        fill_mask = (fill_mask | comp_seed) & ~protect_mask | comp_seed
        added = int(np.sum(fill_mask)) - comp_n
        total_added += added
        result[fill_mask] = label
        component_details.append({
            "size": comp_n, "added": added, "skipped": False,
        })

    return result, OperationSummary(
        "label_convex",
        changed_voxels=total_added,
        details={
            "label": label,
            "label_name": get_label_name(label),
            "method": params.method,
            "n_components": n_comp,
            "processed_components": len(selected),
            "before_voxels": n_seed,
            "after_voxels": n_seed + total_added,
            "added_voxels": total_added,
            "components": component_details,
        },
    )


def _label_convex_3d_pure(shape: tuple, seed_mask: np.ndarray) -> np.ndarray | None:
    coords = np.argwhere(seed_mask)
    if len(coords) < 4:
        return None
    try:
        hull = ConvexHull(coords)
        delaunay = Delaunay(coords[hull.vertices])
    except Exception:
        return None

    margin = 1
    mins = np.maximum(coords.min(axis=0) - margin, 0)
    maxs = np.minimum(coords.max(axis=0) + margin + 1, shape)

    grid = np.mgrid[mins[0]:maxs[0], mins[1]:maxs[1], mins[2]:maxs[2]]
    test_points = grid.reshape(3, -1).T
    inside = delaunay.find_simplex(test_points) >= 0

    fill_mask = np.zeros(shape, dtype=bool)
    fill_mask[test_points[inside, 0], test_points[inside, 1], test_points[inside, 2]] = True
    return fill_mask


def _label_convex_2d_pure(shape: tuple, seed_mask: np.ndarray, axis: int = 0) -> np.ndarray | None:
    seed_slices = []
    for i in range(shape[axis]):
        sl = [slice(None)] * 3
        sl[axis] = i
        if np.any(seed_mask[tuple(sl)]):
            seed_slices.append(i)

    if len(seed_slices) == 0:
        return None

    other_axes = [s for idx, s in enumerate(shape) if idx != axis]
    hull_masks = {}

    for si in seed_slices:
        sl = [slice(None)] * 3
        sl[axis] = si
        slice_seed = seed_mask[tuple(sl)]
        coords_2d = np.argwhere(slice_seed)
        if len(coords_2d) < 3:
            hull_masks[si] = slice_seed.copy()
            continue
        try:
            hull = ConvexHull(coords_2d)
            delaunay = Delaunay(coords_2d[hull.vertices])
            grid = np.mgrid[0:other_axes[0], 0:other_axes[1]]
            test_pts = grid.reshape(2, -1).T
            inside = delaunay.find_simplex(test_pts) >= 0
            hull_mask = inside.reshape(other_axes[0], other_axes[1])
            hull_masks[si] = hull_mask | slice_seed
        except Exception:
            hull_masks[si] = slice_seed.copy()

    fill_mask = np.zeros(shape, dtype=bool)
    for si, hmask in hull_masks.items():
        sl = [slice(None)] * 3
        sl[axis] = si
        fill_mask[tuple(sl)] = hmask

    for idx in range(len(seed_slices) - 1):
        s_start = seed_slices[idx]
        s_end = seed_slices[idx + 1]
        if s_end - s_start <= 1:
            continue
        mask_start = hull_masks[s_start].astype(float)
        mask_end = hull_masks[s_end].astype(float)
        for si in range(s_start + 1, s_end):
            t = (si - s_start) / (s_end - s_start)
            interp = mask_start * (1 - t) + mask_end * t
            sl = [slice(None)] * 3
            sl[axis] = si
            fill_mask[tuple(sl)] = interp >= 0.5

    return fill_mask


# ──────────────────────────────────────────────
# Region Restriction
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class SliceRangeParams:
    axis: int
    start: int
    end: int


@dataclass(frozen=True)
class BoundingBoxParams:
    x_start: int
    x_end: int
    y_start: int
    y_end: int
    z_start: int
    z_end: int


@dataclass(frozen=True)
class DirectionCutParams:
    axis: int
    side: str  # "low" or "high"
    cut: int


@dataclass
class RegionParams:
    slice_range: SliceRangeParams | None = None
    bounding_box: BoundingBoxParams | None = None
    direction_cut: DirectionCutParams | None = None


def build_region_mask_from_params(shape: tuple, params: RegionParams) -> np.ndarray:
    mask = np.ones(shape, dtype=bool)

    if params.slice_range is not None:
        sr = params.slice_range
        axis = sr.axis
        slicing = [slice(None)] * 3
        slicing[axis] = slice(0, sr.start)
        mask[tuple(slicing)] = False
        slicing = [slice(None)] * 3
        slicing[axis] = slice(sr.end + 1, shape[axis])
        mask[tuple(slicing)] = False

    if params.bounding_box is not None:
        bb = params.bounding_box
        for ax, (lo, hi) in enumerate([(bb.x_start, bb.x_end), (bb.y_start, bb.y_end), (bb.z_start, bb.z_end)]):
            slicing = [slice(None)] * 3
            slicing[ax] = slice(0, lo)
            mask[tuple(slicing)] = False
            slicing = [slice(None)] * 3
            slicing[ax] = slice(hi + 1, shape[ax])
            mask[tuple(slicing)] = False

    if params.direction_cut is not None:
        dc = params.direction_cut
        slicing = [slice(None)] * 3
        if dc.side == "low":
            slicing[dc.axis] = slice(dc.cut, shape[dc.axis])
            mask[tuple(slicing)] = False
        else:
            slicing[dc.axis] = slice(0, dc.cut + 1)
            mask[tuple(slicing)] = False

    return mask


def apply_with_region(func, data: np.ndarray, region_mask: np.ndarray, **kwargs) -> np.ndarray:
    """Run func on full data, then keep changes only within region (+1 voxel boundary)."""
    result = func(data, **kwargs)
    struct = ndimage.generate_binary_structure(3, 1)
    expanded_region = ndimage.binary_dilation(region_mask, structure=struct, iterations=1)
    final = data.copy()
    final[expanded_region] = result[expanded_region]
    return final
