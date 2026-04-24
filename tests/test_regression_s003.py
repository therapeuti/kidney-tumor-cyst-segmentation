"""Phase 1.4 regression test on real sample case S003.

Runs each core operation on the actual S003 data and verifies:
- Output shape is preserved
- No new labels are introduced (only 0, 1, 2, 3)
- changed_voxels in summary matches actual array diff
- Operation does not destroy all labels

Uses a cropped ROI around the kidney region to keep runtime reasonable.
"""

import os
import unittest

import nibabel as nib
import numpy as np

# Skip if S003 data not present
CASE_DIR = os.path.join(os.path.dirname(__file__), "..", "S003")
SEG_PATH = os.path.join(CASE_DIR, "S003_Segmentation_A.nii.gz")
CT_PATH = os.path.join(CASE_DIR, "S003_image_A.nii.gz")
HAS_DATA = os.path.exists(SEG_PATH) and os.path.exists(CT_PATH)

if HAS_DATA:
    from segtools_core import (
        ExpandParams,
        FillHolesParams,
        LabelConvexParams,
        RemoveHighIntensityParams,
        RemoveIsolatedParams,
        SmoothParams,
        TrimBoundaryParams,
        expand,
        fill_holes,
        label_convex,
        remove_high_intensity,
        remove_isolated,
        remove_low_intensity,
        smooth,
        trim_boundary,
    )


def _load_cropped_roi():
    """Load S003 and crop to a tight ROI around the organ to save memory/time."""
    seg_img = nib.load(SEG_PATH)
    seg_full = seg_img.get_fdata().astype(np.uint16)
    ct_full = nib.load(CT_PATH).get_fdata().astype(np.float32)
    zooms = tuple(float(v) for v in seg_img.header.get_zooms()[:3])

    organ_mask = seg_full > 0
    coords = np.argwhere(organ_mask)
    margin = 10
    mins = np.maximum(coords.min(axis=0) - margin, 0)
    maxs = np.minimum(coords.max(axis=0) + margin + 1, seg_full.shape)

    roi = tuple(slice(int(lo), int(hi)) for lo, hi in zip(mins, maxs))
    seg_crop = seg_full[roi].copy()
    ct_crop = ct_full[roi].copy()
    return seg_crop, ct_crop, zooms


@unittest.skipUnless(HAS_DATA, "S003 sample data not found")
class TestRegressionS003(unittest.TestCase):
    seg = None
    ct = None
    zooms = None

    @classmethod
    def setUpClass(cls):
        cls.seg, cls.ct, cls.zooms = _load_cropped_roi()
        cls.original_labels = set(np.unique(cls.seg))

    def _check_basics(self, result, summary):
        self.assertEqual(result.shape, self.seg.shape)
        result_labels = set(np.unique(result))
        self.assertTrue(result_labels.issubset({0, 1, 2, 3}),
                        f"Unexpected labels: {result_labels - {0, 1, 2, 3}}")
        actual_diff = int(np.sum(result != self.seg))
        self.assertEqual(summary.changed_voxels, actual_diff,
                         f"{summary.operation}: summary={summary.changed_voxels}, actual={actual_diff}")
        # Should not destroy all organ labels
        self.assertGreater(np.sum(result > 0), 0)

    def test_remove_isolated(self):
        result, summary = remove_isolated(self.seg, RemoveIsolatedParams(target="3"))
        self._check_basics(result, summary)

    def test_remove_low_intensity(self):
        result, summary = remove_low_intensity(self.seg, self.ct)
        self._check_basics(result, summary)

    def test_remove_high_intensity(self):
        result, summary = remove_high_intensity(
            self.seg, self.ct, RemoveHighIntensityParams(threshold=400))
        self._check_basics(result, summary)

    def test_fill_holes(self):
        result, summary = fill_holes(self.seg, FillHolesParams(target="3"))
        self._check_basics(result, summary)

    def test_smooth_kidney(self):
        result, summary = smooth(
            self.seg, self.zooms,
            SmoothParams(target="1", sigma=1.0, close_iter=1, open_iter=1))
        self._check_basics(result, summary)

    def test_smooth_tumor(self):
        result, summary = smooth(
            self.seg, self.zooms,
            SmoothParams(target="2", sigma=1.0, close_iter=1, open_iter=1))
        self._check_basics(result, summary)

    def test_expand(self):
        result, summary = expand(
            self.seg, self.ct,
            ExpandParams(target_label=1, mode="lower", threshold=120, iterations=2))
        self._check_basics(result, summary)

    def test_trim_boundary(self):
        result, summary = trim_boundary(
            self.seg, self.ct,
            TrimBoundaryParams(target="1", mode="range", max_iter=1))
        self._check_basics(result, summary)

    def test_label_convex(self):
        result, summary = label_convex(
            self.seg, LabelConvexParams(label=2, method="3d"))
        self._check_basics(result, summary)


if __name__ == "__main__":
    unittest.main()
