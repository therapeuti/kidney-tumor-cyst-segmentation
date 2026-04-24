import unittest

import numpy as np

from segtools_core import (
    ExpandParams,
    SmoothParams,
    TrimBoundaryParams,
    expand,
    smooth,
    trim_boundary,
)


class SegtoolsCoreValidationTests(unittest.TestCase):
    def test_smooth_kidney_preserves_tumor_and_cyst_labels(self) -> None:
        shape = (16, 16, 16)
        data = np.zeros(shape, dtype=np.uint16)
        data[4:12, 4:12, 4:12] = 1
        data[12:14, 7:9, 7:9] = 1
        tumor_region = (slice(7, 9), slice(7, 9), slice(7, 9))
        cyst_region = (slice(5, 7), slice(5, 7), slice(5, 7))
        data[tumor_region] = 2
        data[cyst_region] = 3

        result, summary = smooth(
            data,
            (1.0, 1.0, 1.0),
            SmoothParams(target="1", sigma=1.0, close_iter=1, open_iter=1),
        )

        self.assertTrue(np.all(result[tumor_region] == 2))
        self.assertTrue(np.all(result[cyst_region] == 3))
        self.assertGreater(summary.changed_voxels, 0)

    def test_expand_lower_adds_only_adjacent_allowed_region(self) -> None:
        shape = (16, 16, 16)
        ct = np.full(shape, -100.0, dtype=np.float32)
        data = np.zeros(shape, dtype=np.uint16)
        data[6:10, 6:10, 6:10] = 1
        ct[5:11, 5:11, 5:11] = 150.0
        ct[0:2, 0:2, 0:2] = 150.0

        result, summary = expand(
            data,
            ct,
            ExpandParams(target_label=1, mode="lower", threshold=120, iterations=2),
        )

        self.assertGreater(summary.details["added_voxels"], 0)
        self.assertTrue(np.all(result[0:2, 0:2, 0:2] == 0))

    def test_expand_range_respects_similarity_window(self) -> None:
        shape = (16, 16, 16)
        ct = np.full(shape, 20.0, dtype=np.float32)
        data = np.zeros(shape, dtype=np.uint16)
        data[5:11, 5:11, 5:11] = 1
        data[7:9, 7:9, 7:9] = 2
        ct[7:9, 7:9, 7:9] = 80.0
        ct[6:10, 6:10, 6:10] = 82.0
        ct[5, 5, 5] = 10.0

        result, summary = expand(
            data,
            ct,
            ExpandParams(target_label=2, mode="range", tolerance=5, iterations=1),
        )

        self.assertGreater(summary.details["added_voxels"], 0)
        self.assertNotEqual(result[5, 5, 5], 2)

    def test_trim_boundary_upper_removes_surface_voxels(self) -> None:
        shape = (16, 16, 16)
        data = np.zeros(shape, dtype=np.uint16)
        data[4:12, 4:12, 4:12] = 1
        ct = np.full(shape, 100.0, dtype=np.float32)
        ct[4, 4:12, 4:12] = 500.0
        ct[11, 4:12, 4:12] = 500.0

        result, summary = trim_boundary(
            data,
            ct,
            TrimBoundaryParams(target="1", mode="upper", threshold=400, max_iter=1),
        )

        self.assertLess(np.sum(result == 1), np.sum(data == 1))
        self.assertEqual(result[7, 7, 7], 1)
        self.assertEqual(summary.details["target"], "organ")

    def test_trim_boundary_lower_removes_exposed_tumor_surface(self) -> None:
        shape = (16, 16, 16)
        data = np.zeros(shape, dtype=np.uint16)
        data[4:12, 4:12, 4:12] = 2
        ct = np.full(shape, 100.0, dtype=np.float32)
        ct[4, 4:12, 4:12] = -20.0

        result, summary = trim_boundary(
            data,
            ct,
            TrimBoundaryParams(target="2", mode="lower", threshold=0, max_iter=1),
        )

        self.assertLess(np.sum(result == 2), np.sum(data == 2))
        self.assertEqual(summary.details["target"], "tumor")


if __name__ == "__main__":
    unittest.main()
