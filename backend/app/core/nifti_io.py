from pathlib import Path
import shutil

import nibabel as nib
import numpy as np


def load_segmentation(seg_path: Path) -> tuple[nib.Nifti1Image, np.ndarray]:
    seg_img = nib.load(str(seg_path))
    seg_data = np.round(np.asanyarray(seg_img.dataobj)).astype(np.uint16)
    return seg_img, seg_data


def save_segmentation(seg_path: Path, data: np.ndarray, source_img: nib.Nifti1Image) -> None:
    new_header = source_img.header.copy()
    new_header.set_data_dtype(np.uint16)
    new_header["scl_slope"] = 1
    new_header["scl_inter"] = 0
    new_img = nib.Nifti1Image(data, source_img.affine, new_header)
    nib.save(new_img, str(seg_path))


def create_empty_segmentation(ct_path: Path) -> tuple[nib.Nifti1Image, np.ndarray]:
    """Create an empty (all-zeros) segmentation matching the CT image geometry."""
    ct_img = nib.load(str(ct_path))
    shape = ct_img.shape[:3]
    seg_data = np.zeros(shape, dtype=np.uint16)
    seg_img = nib.Nifti1Image(seg_data, ct_img.affine)
    seg_img.header.set_data_dtype(np.uint16)
    seg_img.header["scl_slope"] = 1
    seg_img.header["scl_inter"] = 0
    return seg_img, seg_data


def ensure_backup(seg_path: Path) -> Path:
    backup_dir = seg_path.parent / "backup_original"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / seg_path.name
    if not backup_path.exists():
        shutil.copy2(seg_path, backup_path)
    return backup_path
