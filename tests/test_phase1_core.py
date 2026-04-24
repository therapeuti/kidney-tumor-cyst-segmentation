"""Phase 1.4 tests for segtools_core pure functions.

Covers:
- Output shape preservation across all operations
- No-CT-required vs CT-required operation behavior
- Changed voxel counts and summary structure
- label_convex and region restriction helpers
"""

import unittest

import numpy as np

from segtools_core import (
    BoundingBoxParams,
    DirectionCutParams,
    ExpandParams,
    FillHolesParams,
    LabelConvexParams,
    OperationSummary,
    RegionParams,
    RemoveHighIntensityParams,
    RemoveIsolatedParams,
    SliceRangeParams,
    SmoothParams,
    TrimBoundaryParams,
    apply_with_region,
    build_region_mask_from_params,
    expand,
    fill_holes,
    label_convex,
    remove_high_intensity,
    remove_isolated,
    remove_low_intensity,
    smooth,
    trim_boundary,
)


def _make_kidney_tumor_data(shape=(20, 20, 20)):
    """Helper: kidney block with embedded tumor and cyst."""
    data = np.zeros(shape, dtype=np.uint16)
    data[4:16, 4:16, 4:16] = 1  # kidney
    data[7:11, 7:11, 7:11] = 2  # tumor
    data[12:14, 12:14, 12:14] = 3  # cyst
    return data


def _make_ct(shape=(20, 20, 20), value=100.0):
    return np.full(shape, value, dtype=np.float32)


# ──────────────────────────────────────────────
# 1. Output shape preservation
# ───────────────────────────────���──────────────


class TestOutputShapePreservation(unittest.TestCase):
    """Every operation must return data with the same shape and dtype family."""

    def setUp(self):
        self.shape = (20, 20, 20)
        self.data = _make_kidney_tumor_data(self.shape)
        self.ct = _make_ct(self.shape)
        self.zooms = (1.0, 1.0, 1.0)

    def _check(self, result, summary):
        self.assertEqual(result.shape, self.shape)
        self.assertTrue(np.issubdtype(result.dtype, np.integer))
        self.assertIsInstance(summary, OperationSummary)

    def test_remove_isolated_shape(self):
        result, summary = remove_isolated(self.data, RemoveIsolatedParams(target="3"))
        self._check(result, summary)

    def test_remove_low_intensity_shape(self):
        result, summary = remove_low_intensity(self.data, self.ct)
        self._check(result, summary)

    def test_remove_high_intensity_shape(self):
        result, summary = remove_high_intensity(self.data, self.ct, RemoveHighIntensityParams(threshold=400))
        self._check(result, summary)

    def test_fill_holes_shape(self):
        result, summary = fill_holes(self.data, FillHolesParams(target="1"))
        self._check(result, summary)

    def test_smooth_shape(self):
        result, summary = smooth(self.data, self.zooms, SmoothParams(target="1", sigma=1.0))
        self._check(result, summary)

    def test_expand_shape(self):
        result, summary = expand(self.data, self.ct, ExpandParams(target_label=1, mode="lower", threshold=50))
        self._check(result, summary)

    def test_trim_boundary_shape(self):
        ct = self.ct.copy()
        ct[4, :, :] = -50.0  # make surface bad so trimming actually runs
        result, summary = trim_boundary(self.data, ct, TrimBoundaryParams(target="1", mode="lower", threshold=0))
        self._check(result, summary)

    def test_label_convex_shape(self):
        result, summary = label_convex(self.data, LabelConvexParams(label=2, method="3d"))
        self._check(result, summary)


# ──────────────────────────────────────────────
# 2. CT-required vs no-CT operations
# ──────────────────────────────────────────────


class TestCTRequirement(unittest.TestCase):
    """CT-required ops must raise when ct_data is None; non-CT ops must work without CT."""

    def setUp(self):
        self.data = _make_kidney_tumor_data()

    def test_remove_isolated_no_ct_needed(self):
        result, summary = remove_isolated(self.data, RemoveIsolatedParams(target="1"))
        self.assertIsInstance(summary, OperationSummary)

    def test_fill_holes_no_ct_needed(self):
        result, summary = fill_holes(self.data, FillHolesParams(target="3"))
        self.assertIsInstance(summary, OperationSummary)

    def test_label_convex_no_ct_needed(self):
        result, summary = label_convex(self.data, LabelConvexParams(label=2, method="3d"))
        self.assertIsInstance(summary, OperationSummary)

    def test_remove_low_intensity_requires_ct(self):
        with self.assertRaises(ValueError):
            remove_low_intensity(self.data, None)

    def test_remove_high_intensity_requires_ct(self):
        with self.assertRaises(ValueError):
            remove_high_intensity(self.data, None, RemoveHighIntensityParams())

    def test_expand_requires_ct(self):
        with self.assertRaises(ValueError):
            expand(self.data, None, ExpandParams(target_label=1, mode="lower"))

    def test_trim_boundary_requires_ct(self):
        with self.assertRaises(ValueError):
            trim_boundary(self.data, None, TrimBoundaryParams(target="1", mode="range"))


# ──────────────────────────────────────────────
# 3. Changed voxel counts and summary structure
# ──────────────────────────────────────────────


class TestSummaryStructure(unittest.TestCase):
    """Summaries must have correct operation name, non-negative changed_voxels,
    and changed_voxels must match actual array diff."""

    def setUp(self):
        self.data = _make_kidney_tumor_data()
        self.ct = _make_ct()
        self.zooms = (1.0, 1.0, 1.0)

    def _verify_summary(self, original, result, summary, expected_op):
        self.assertEqual(summary.operation, expected_op)
        self.assertGreaterEqual(summary.changed_voxels, 0)
        actual_diff = int(np.sum(result != original))
        self.assertEqual(summary.changed_voxels, actual_diff,
                         f"{expected_op}: summary says {summary.changed_voxels} but actual diff is {actual_diff}")

    def test_remove_isolated_summary(self):
        # Add multiple small isolated kidney components (keep_n=2, so 3rd+ removed)
        data = self.data.copy()
        data[0, 0, 0] = 1
        data[0, 0, 19] = 1
        data[0, 19, 0] = 1
        result, summary = remove_isolated(data, RemoveIsolatedParams(target="1"))
        self._verify_summary(data, result, summary, "remove_isolated")
        self.assertGreater(summary.changed_voxels, 0)
        self.assertIn("labels", summary.details)

    def test_remove_low_intensity_summary(self):
        ct = self.ct.copy()
        ct[4:6, 4:6, 4:6] = -10.0  # make some kidney voxels low
        result, summary = remove_low_intensity(self.data, ct)
        self._verify_summary(self.data, result, summary, "remove_low_intensity")

    def test_remove_high_intensity_summary(self):
        ct = self.ct.copy()
        ct[7:9, 7:9, 7:9] = 500.0  # make some tumor voxels high
        result, summary = remove_high_intensity(self.data, ct, RemoveHighIntensityParams(threshold=400))
        self._verify_summary(self.data, result, summary, "remove_high_intensity")
        self.assertGreater(summary.changed_voxels, 0)

    def test_fill_holes_summary(self):
        # Punch a hole in the kidney
        data = self.data.copy()
        data[10, 10, 10] = 0
        result, summary = fill_holes(data, FillHolesParams(target="1"))
        self._verify_summary(data, result, summary, "fill_holes")
        self.assertGreater(summary.changed_voxels, 0)

    def test_smooth_summary(self):
        result, summary = smooth(self.data, self.zooms, SmoothParams(target="2", sigma=1.0, close_iter=1, open_iter=1))
        self._verify_summary(self.data, result, summary, "smooth")

    def test_expand_summary(self):
        result, summary = expand(self.data, self.ct, ExpandParams(target_label=1, mode="lower", threshold=50, iterations=1))
        self._verify_summary(self.data, result, summary, "expand")
        self.assertIn("added_voxels", summary.details)

    def test_trim_boundary_summary(self):
        ct = self.ct.copy()
        ct[4, 4:16, 4:16] = -50.0
        result, summary = trim_boundary(self.data, ct, TrimBoundaryParams(target="1", mode="lower", threshold=0, max_iter=1))
        self._verify_summary(self.data, result, summary, "trim_boundary")

    def test_label_convex_summary(self):
        result, summary = label_convex(self.data, LabelConvexParams(label=2, method="3d"))
        self._verify_summary(self.data, result, summary, "label_convex")
        self.assertIn("added_voxels", summary.details)


# ──────────────────────────────────────────────
# 4. label_convex specific tests
# ──────────────────────────────────────────────


class TestLabelConvex(unittest.TestCase):
    def test_3d_fills_interior(self):
        data = np.zeros((20, 20, 20), dtype=np.uint16)
        data[5:15, 5:15, 5:15] = 1
        # Place a connected tumor seed block spanning enough points for ConvexHull
        data[7:13, 7:13, 7] = 2
        data[7:13, 7:13, 12] = 2
        data[7:13, 7, 7:13] = 2
        data[7:13, 12, 7:13] = 2

        result, summary = label_convex(data, LabelConvexParams(label=2, method="3d"))
        self.assertGreater(summary.details["added_voxels"], 0)
        # Interior point should be filled
        self.assertEqual(result[10, 10, 10], 2)

    def test_2d_fills_slices(self):
        data = np.zeros((20, 20, 20), dtype=np.uint16)
        data[5:15, 5:15, 5:15] = 1
        # L-shaped connected tumor seed per slice — hull will fill the concavity
        for s in range(8, 12):
            data[s, 7:13, 7:9] = 2   # vertical bar
            data[s, 11:13, 7:13] = 2  # horizontal bar at bottom

        result, summary = label_convex(data, LabelConvexParams(label=2, method="2d", slice_axis=0))
        self.assertGreater(summary.details["added_voxels"], 0)

    def test_empty_seed_returns_unchanged(self):
        data = np.zeros((10, 10, 10), dtype=np.uint16)
        data[3:7, 3:7, 3:7] = 1
        result, summary = label_convex(data, LabelConvexParams(label=2, method="3d"))
        self.assertTrue(summary.details.get("empty", False))
        np.testing.assert_array_equal(result, data)

    def test_protect_other_label(self):
        data = np.zeros((20, 20, 20), dtype=np.uint16)
        data[5:15, 5:15, 5:15] = 1
        for x in (7, 12):
            for y in (7, 12):
                for z in (7, 12):
                    data[x, y, z] = 2
        # Place cyst in the middle — should be protected
        data[9, 9, 9] = 3

        result, summary = label_convex(data, LabelConvexParams(label=2, method="3d"))
        self.assertEqual(result[9, 9, 9], 3)

    def test_component_indices_selection(self):
        data = np.zeros((20, 20, 20), dtype=np.uint16)
        data[5:15, 5:15, 5:15] = 1
        # Two separate tumor clusters
        data[6:8, 6:8, 6:8] = 2
        data[12:14, 12:14, 12:14] = 2
        # Process only first component (sorted by size, both are same size)
        result, summary = label_convex(data, LabelConvexParams(label=2, method="3d", component_indices=[0]))
        self.assertEqual(summary.details["processed_components"], 1)


# ──────────────────────────────────────────────
# 5. Region restriction tests
# ──────────────────────────────────────────────


class TestRegionRestriction(unittest.TestCase):
    def test_slice_range(self):
        shape = (20, 20, 20)
        params = RegionParams(slice_range=SliceRangeParams(axis=0, start=5, end=14))
        mask = build_region_mask_from_params(shape, params)
        self.assertEqual(mask.shape, shape)
        self.assertTrue(np.all(mask[5:15, :, :]))
        self.assertFalse(np.any(mask[0:5, :, :]))
        self.assertFalse(np.any(mask[15:, :, :]))

    def test_bounding_box(self):
        shape = (20, 20, 20)
        params = RegionParams(bounding_box=BoundingBoxParams(
            x_start=5, x_end=14, y_start=5, y_end=14, z_start=5, z_end=14,
        ))
        mask = build_region_mask_from_params(shape, params)
        self.assertTrue(mask[10, 10, 10])
        self.assertFalse(mask[0, 0, 0])
        self.assertFalse(mask[19, 19, 19])

    def test_direction_cut_low(self):
        shape = (20, 20, 20)
        params = RegionParams(direction_cut=DirectionCutParams(axis=0, side="low", cut=10))
        mask = build_region_mask_from_params(shape, params)
        self.assertTrue(np.all(mask[0:10, :, :]))
        self.assertFalse(np.any(mask[10:, :, :]))

    def test_direction_cut_high(self):
        shape = (20, 20, 20)
        params = RegionParams(direction_cut=DirectionCutParams(axis=0, side="high", cut=10))
        mask = build_region_mask_from_params(shape, params)
        self.assertTrue(np.all(mask[11:, :, :]))
        self.assertFalse(np.any(mask[:11, :, :]))

    def test_combined_params(self):
        shape = (20, 20, 20)
        params = RegionParams(
            slice_range=SliceRangeParams(axis=0, start=5, end=14),
            bounding_box=BoundingBoxParams(x_start=0, x_end=19, y_start=8, y_end=12, z_start=0, z_end=19),
        )
        mask = build_region_mask_from_params(shape, params)
        self.assertTrue(mask[10, 10, 10])
        self.assertFalse(mask[2, 10, 10])   # outside slice range
        self.assertFalse(mask[10, 2, 10])   # outside bbox y

    def test_empty_params_returns_all_true(self):
        shape = (10, 10, 10)
        mask = build_region_mask_from_params(shape, RegionParams())
        self.assertTrue(np.all(mask))

    def test_apply_with_region_limits_changes(self):
        shape = (20, 20, 20)
        data = np.zeros(shape, dtype=np.uint16)
        data[5:15, 5:15, 5:15] = 1

        region_mask = build_region_mask_from_params(shape, RegionParams(
            slice_range=SliceRangeParams(axis=0, start=5, end=9),
        ))

        def fill_all_zeros(d, **kw):
            r = d.copy()
            r[r == 0] = 1
            return r

        result = apply_with_region(fill_all_zeros, data, region_mask)
        # Within region (+ 1 voxel boundary): changes applied
        self.assertEqual(result[7, 0, 0], 1)
        # Far outside region: unchanged
        self.assertEqual(result[15, 0, 0], 0)


if __name__ == "__main__":
    unittest.main()
