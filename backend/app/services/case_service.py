from pathlib import Path

import numpy as np
import nibabel as nib

from backend.app.core.case_loader import discover_case_dirs, get_case_dir, load_case_paths
from backend.app.schemas.case import CaseDetailResponse, CaseSummaryResponse, PhaseSummaryResponse


def _phase_summary(phase: str, seg_path: Path | None, img_path: Path | None) -> PhaseSummaryResponse:
    if seg_path is not None:
        ref_img = nib.load(str(seg_path))
        seg_data = np.round(np.asanyarray(ref_img.dataobj)).astype(np.uint16)
        labels = [int(v) for v in np.unique(seg_data)]
    elif img_path is not None:
        ref_img = nib.load(str(img_path))
        labels = [0]
    else:
        raise ValueError(f"No files for phase {phase}")
    shape = [int(v) for v in ref_img.shape[:3]]
    spacing = [float(v) for v in ref_img.header.get_zooms()[:len(shape)]]
    return PhaseSummaryResponse(
        phase=phase,
        hasCt=img_path is not None,
        shape=shape,
        spacing=spacing,
        labels=labels,
    )


def list_cases() -> list[CaseSummaryResponse]:
    items: list[CaseSummaryResponse] = []
    for case_dir in discover_case_dirs():
        phases = sorted(load_case_paths(case_dir).keys())
        items.append(CaseSummaryResponse(caseId=case_dir.name, phases=phases))
    return items


def get_case_detail(case_id: str) -> CaseDetailResponse | None:
    case_dir = get_case_dir(case_id)
    if case_dir is None:
        return None
    phase_paths = load_case_paths(case_dir)
    phases = [
        _phase_summary(phase, paths["seg"], paths["img"])
        for phase, paths in sorted(phase_paths.items())
    ]
    return CaseDetailResponse(caseId=case_id, phases=phases)
