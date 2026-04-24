from segtools_core import (
    BoundingBoxParams,
    DirectionCutParams,
    ExpandParams,
    FillHolesParams,
    LabelConvexParams,
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

from backend.app.schemas.postprocess import (
    PostprocessApplyResponse,
    PostprocessFunctionDefinition,
    PostprocessParamDefinition,
    PostprocessParamOption,
    PostprocessPreviewResponse,
    PostprocessRequest,
)
from backend.app.services.session_service import session_service
from backend.app.services.viewer_service import viewer_service


FUNCTION_REGISTRY: dict[str, PostprocessFunctionDefinition] = {
    "remove_isolated": PostprocessFunctionDefinition(
        key="remove_isolated",
        label="Remove Isolated Components",
        requiresCt=False,
        params=[
            PostprocessParamDefinition(
                key="target",
                label="Target",
                type="select",
                default="all",
                options=[
                    PostprocessParamOption(label="All", value="all"),
                    PostprocessParamOption(label="Kidney", value="1"),
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="3"),
                ],
            ),
            PostprocessParamDefinition(
                key="keep_n",
                label="Components to keep",
                type="number",
                default=2,
            )
        ],
    ),
    "remove_low_intensity": PostprocessFunctionDefinition(
        key="remove_low_intensity",
        label="Remove Low Intensity",
        requiresCt=True,
        params=[],
    ),
    "remove_high_intensity": PostprocessFunctionDefinition(
        key="remove_high_intensity",
        label="Remove High Intensity",
        requiresCt=True,
        params=[
            PostprocessParamDefinition(
                key="threshold",
                label="Threshold",
                type="number",
                default=400,
            )
        ],
    ),
    "fill_holes": PostprocessFunctionDefinition(
        key="fill_holes",
        label="Fill Holes",
        requiresCt=False,
        params=[
            PostprocessParamDefinition(
                key="target",
                label="Target",
                type="select",
                default="3",
                options=[
                    PostprocessParamOption(label="Whole Organ", value="3"),
                    PostprocessParamOption(label="Kidney", value="1"),
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="4"),
                ],
            )
        ],
    ),
    "smooth": PostprocessFunctionDefinition(
        key="smooth",
        label="Smooth",
        requiresCt=False,
        params=[
            PostprocessParamDefinition(
                key="target",
                label="Target",
                type="select",
                default="1",
                options=[
                    PostprocessParamOption(label="Kidney", value="1"),
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="3"),
                    PostprocessParamOption(label="Whole organ", value="4"),
                ],
            ),
            PostprocessParamDefinition(key="sigma", label="Sigma (mm)", type="number", default=1.0),
            PostprocessParamDefinition(key="close_iter", label="Closing iterations", type="number", default=3),
            PostprocessParamDefinition(key="open_iter", label="Opening iterations", type="number", default=2),
            PostprocessParamDefinition(key="keep_n", label="Components to keep", type="number", default=2, required=False),
        ],
    ),
    "expand": PostprocessFunctionDefinition(
        key="expand",
        label="Boundary Expansion",
        requiresCt=True,
        params=[
            PostprocessParamDefinition(
                key="target_label",
                label="Target label",
                type="select",
                default="1",
                options=[
                    PostprocessParamOption(label="Kidney", value="1"),
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="3"),
                ],
            ),
            PostprocessParamDefinition(
                key="mode",
                label="Mode",
                type="select",
                default="lower",
                options=[
                    PostprocessParamOption(label="Lower bound", value="lower"),
                    PostprocessParamOption(label="Range", value="range"),
                ],
            ),
            PostprocessParamDefinition(key="threshold", label="Threshold", type="number", default=120, required=False),
            PostprocessParamDefinition(key="tolerance", label="Tolerance", type="number", default=25, required=False),
            PostprocessParamDefinition(key="iterations", label="Iterations", type="number", default=5),
            PostprocessParamDefinition(key="overwrite_kidney", label="Overwrite kidney", type="boolean", default=False),
        ],
    ),
    "trim_boundary": PostprocessFunctionDefinition(
        key="trim_boundary",
        label="Trim Boundary",
        requiresCt=True,
        params=[
            PostprocessParamDefinition(
                key="target",
                label="Target",
                type="select",
                default="1",
                options=[
                    PostprocessParamOption(label="Whole organ", value="1"),
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="3"),
                ],
            ),
            PostprocessParamDefinition(
                key="mode",
                label="Mode",
                type="select",
                default="range",
                options=[
                    PostprocessParamOption(label="Range", value="range"),
                    PostprocessParamOption(label="Lower bound", value="lower"),
                    PostprocessParamOption(label="Upper bound", value="upper"),
                ],
            ),
            PostprocessParamDefinition(key="threshold", label="Threshold", type="number", default=400, required=False),
            PostprocessParamDefinition(key="tolerance", label="Tolerance", type="number", default=25, required=False),
            PostprocessParamDefinition(key="max_iter", label="Max iterations", type="number", default=1),
        ],
    ),
    "label_convex": PostprocessFunctionDefinition(
        key="label_convex",
        label="Convex Hull Labeling",
        requiresCt=False,
        params=[
            PostprocessParamDefinition(
                key="label",
                label="Target label",
                type="select",
                default="2",
                options=[
                    PostprocessParamOption(label="Tumor", value="2"),
                    PostprocessParamOption(label="Cyst", value="3"),
                ],
            ),
            PostprocessParamDefinition(
                key="method",
                label="Method",
                type="select",
                default="3d",
                options=[
                    PostprocessParamOption(label="3D ConvexHull", value="3d"),
                    PostprocessParamOption(label="2D slice-by-slice", value="2d"),
                ],
            ),
            PostprocessParamDefinition(
                key="slice_axis",
                label="Slice axis (2D only)",
                type="select",
                default="2",
                options=[
                    PostprocessParamOption(label="Sagittal", value="0"),
                    PostprocessParamOption(label="Coronal", value="1"),
                    PostprocessParamOption(label="Axial", value="2"),
                ],
            ),
        ],
    ),
}


class PostprocessService:
    def list_functions(self) -> list[PostprocessFunctionDefinition]:
        return list(FUNCTION_REGISTRY.values())

    def preview(self, session, payload: PostprocessRequest) -> PostprocessPreviewResponse:
        result, summary = self._run(session, payload, apply_changes=False)
        diff = result != session.seg_data
        changed = int(diff.sum())
        # Cache diff as int8: +1 = added (was background), -1 = removed (becomes background)
        if changed > 0:
            import numpy as np
            diff_map = np.zeros(session.seg_data.shape, dtype=np.int8)
            added = diff & (session.seg_data == 0)   # background → label
            removed = diff & (result == 0)            # label → background
            changed_label = diff & ~added & ~removed  # label → different label
            diff_map[added] = 1
            diff_map[removed] = -1
            diff_map[changed_label] = 2
            session.preview_mask = diff_map
        else:
            session.preview_mask = None
        return PostprocessPreviewResponse(
            ok=True,
            changedVoxels=changed,
            summary={
                "operation": summary.operation,
                "details": summary.details,
            },
        )

    def apply(self, session, payload: PostprocessRequest) -> PostprocessApplyResponse:
        result, summary = self._run(session, payload, apply_changes=True)
        changed = int((result != session.seg_data).sum())
        if changed > 0:
            session_service.push_snapshot(session)
            session.seg_data = result
        session.preview_mask = None
        return PostprocessApplyResponse(
            ok=True,
            changedVoxels=changed,
            summary={
                "operation": summary.operation,
                "details": summary.details,
            },
            session=session_service.session_status(session),
        )

    @staticmethod
    def _parse_region(params: dict, shape: tuple) -> RegionParams | None:
        region_raw = params.pop("region", None)
        if not region_raw or not isinstance(region_raw, dict):
            return None
        sr = region_raw.get("slice_range")
        bb = region_raw.get("bounding_box")
        dc = region_raw.get("direction_cut")
        return RegionParams(
            slice_range=SliceRangeParams(axis=int(sr["axis"]), start=int(sr["start"]), end=int(sr["end"])) if sr else None,
            bounding_box=BoundingBoxParams(
                x_start=int(bb["x_start"]), x_end=int(bb["x_end"]),
                y_start=int(bb["y_start"]), y_end=int(bb["y_end"]),
                z_start=int(bb["z_start"]), z_end=int(bb["z_end"]),
            ) if bb else None,
            direction_cut=DirectionCutParams(axis=int(dc["axis"]), side=str(dc["side"]), cut=int(dc["cut"])) if dc else None,
        )

    def _run(self, session, payload: PostprocessRequest, apply_changes: bool):
        fn = payload.function
        if fn not in FUNCTION_REGISTRY:
            raise ValueError(f"Unsupported postprocess function: {fn}")

        data = session.seg_data.copy()
        ct_data = session.ct_data
        if FUNCTION_REGISTRY[fn].requiresCt:
            viewer_service.ensure_ct_loaded(session)
            ct_data = session.ct_data

        params = dict(payload.params)
        region_params = self._parse_region(params, data.shape)

        result, summary = self._run_function(fn, data, ct_data, params, session)

        if region_params is not None:
            region_mask = build_region_mask_from_params(data.shape, region_params)
            restricted = apply_with_region(lambda d, **kw: result, data, region_mask)
            return restricted, summary

        return result, summary

    def _run_function(self, fn, data, ct_data, params, session):
        if fn == "remove_isolated":
            return remove_isolated(data, RemoveIsolatedParams(
                target=str(params.get("target", "all")),
                keep_n=int(params.get("keep_n", 2)),
            ))
        if fn == "remove_low_intensity":
            return remove_low_intensity(data, ct_data)
        if fn == "remove_high_intensity":
            threshold = float(params.get("threshold", 400))
            return remove_high_intensity(data, ct_data, RemoveHighIntensityParams(threshold=threshold))
        if fn == "fill_holes":
            return fill_holes(data, FillHolesParams(target=str(params.get("target", "3"))))
        if fn == "smooth":
            zooms = tuple(float(v) for v in session.seg_img.header.get_zooms()[:3])
            return smooth(
                data,
                zooms,
                SmoothParams(
                    target=str(params.get("target", "1")),
                    sigma=float(params.get("sigma", 1.0)),
                    close_iter=int(params.get("close_iter", 3)),
                    open_iter=int(params.get("open_iter", 2)),
                    keep_n=int(params.get("keep_n", 2)),
                ),
            )
        if fn == "expand":
            return expand(
                data,
                ct_data,
                ExpandParams(
                    target_label=int(params.get("target_label", 1)),
                    mode=str(params.get("mode", "lower")),
                    threshold=None if params.get("threshold") in (None, "") else float(params.get("threshold")),
                    tolerance=None if params.get("tolerance") in (None, "") else float(params.get("tolerance")),
                    iterations=int(params.get("iterations", 5)),
                    overwrite_kidney=params.get("overwrite_kidney", False) in (True, "true", "True", 1),
                ),
            )
        if fn == "trim_boundary":
            return trim_boundary(
                data,
                ct_data,
                TrimBoundaryParams(
                    target=str(params.get("target", "1")),
                    mode=str(params.get("mode", "range")),
                    threshold=None if params.get("threshold") in (None, "") else float(params.get("threshold")),
                    tolerance=None if params.get("tolerance") in (None, "") else float(params.get("tolerance")),
                    max_iter=int(params.get("max_iter", 1)),
                ),
            )
        if fn == "label_convex":
            return label_convex(
                data,
                LabelConvexParams(
                    label=int(params.get("label", 2)),
                    method=str(params.get("method", "3d")),
                    component_indices=None,
                    slice_axis=int(params.get("slice_axis", 0)),
                ),
            )

        raise ValueError(f"Unsupported postprocess function: {fn}")


postprocess_service = PostprocessService()
