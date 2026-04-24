AXIS_TO_INDEX = {
    "sagittal": 0,
    "coronal": 1,
    "axial": 2,
}


def normalize_axis(axis: str) -> str:
    axis_key = axis.lower()
    if axis_key not in AXIS_TO_INDEX:
        raise ValueError(f"Unsupported axis: {axis}")
    return axis_key


def axis_index(axis: str) -> int:
    return AXIS_TO_INDEX[normalize_axis(axis)]
