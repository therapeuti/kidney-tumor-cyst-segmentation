from itertools import combinations

import nibabel as nib
import numpy as np

from backend.app.core.case_loader import get_case_dir, load_case_paths
from backend.app.schemas.comparison import (
    ComparisonResponse,
    PhaseLabelStats,
    PhasePairDice,
)
from segtools_core import get_label_name

LABELS = [1, 2, 3]


def dice_coefficient(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    intersection = int(np.sum(mask_a & mask_b))
    total = int(np.sum(mask_a)) + int(np.sum(mask_b))
    if total == 0:
        return 1.0
    return 2.0 * intersection / total


def compare_phases(case_id: str) -> ComparisonResponse:
    case_dir = get_case_dir(case_id)
    if case_dir is None:
        raise FileNotFoundError(f"Case not found: {case_id}")

    paths = load_case_paths(case_dir)
    phase_data: dict[str, np.ndarray] = {}

    for phase, files in sorted(paths.items()):
        seg_path = files.get("seg")
        if seg_path is None or not seg_path.exists():
            continue
        seg = nib.load(str(seg_path)).get_fdata().astype(np.uint16)
        phase_data[phase] = seg

    phases = sorted(phase_data.keys())
    if not phases:
        raise ValueError(f"No segmentation files found for {case_id}")

    label_stats: list[PhaseLabelStats] = []
    for phase in phases:
        data = phase_data[phase]
        for label in LABELS:
            count = int(np.sum(data == label))
            label_stats.append(PhaseLabelStats(
                phase=phase, label=label, labelName=get_label_name(label), voxelCount=count,
            ))

    dice_scores: list[PhasePairDice] = []
    for pa, pb in combinations(phases, 2):
        da, db = phase_data[pa], phase_data[pb]
        if da.shape != db.shape:
            continue
        for label in LABELS:
            d = dice_coefficient(da == label, db == label)
            dice_scores.append(PhasePairDice(
                phaseA=pa, phaseB=pb, label=label, labelName=get_label_name(label), dice=round(d, 4),
            ))

    return ComparisonResponse(caseId=case_id, phases=phases, labelStats=label_stats, diceScores=dice_scores)
