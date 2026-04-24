import base64
from io import BytesIO

import numpy as np
from PIL import Image

from backend.app.core.coordinate import normalize_axis
from backend.app.core.editing import (
    apply_edit_to_slice,
    brush_mask,
    display_to_volume,
    extract_slice_view,
    flood_fill_mask,
    interpolate_slices,
    polygon_mask,
    region_grow_3d,
    relabel_3d_component,
    write_slice_view,
)
from backend.app.schemas.edit import (
    BrushEditRequest,
    EditResponse,
    FloodFillRequest,
    MagicWandApplyRequest,
    MagicWandPreviewRequest,
    MagicWandPreviewResponse,
    PolygonEditRequest,
    RelabelRequest,
    SliceInterpolateRequest,
)
from backend.app.services.session_service import session_service
from backend.app.services.viewer_service import viewer_service


class EditService:
    def apply_brush(self, session, payload: BrushEditRequest) -> EditResponse:
        axis = normalize_axis(payload.axis)
        slice_view = extract_slice_view(session.seg_data, axis, payload.sliceIndex)
        height, width = slice_view.shape
        mask = brush_mask(width, height, [tuple(point) for point in payload.points], payload.radius)
        return self._apply_mask(
            session,
            axis=axis,
            slice_index=payload.sliceIndex,
            slice_view=slice_view,
            edit_mask=mask,
            label=payload.label,
            mode=payload.mode,
            overwrite=payload.overwrite,
            preserve_labels=payload.preserveLabels,
        )

    def apply_polygon(self, session, payload: PolygonEditRequest) -> EditResponse:
        axis = normalize_axis(payload.axis)
        slice_view = extract_slice_view(session.seg_data, axis, payload.sliceIndex)
        height, width = slice_view.shape
        mask = polygon_mask(width, height, [tuple(point) for point in payload.vertices])
        return self._apply_mask(
            session,
            axis=axis,
            slice_index=payload.sliceIndex,
            slice_view=slice_view,
            edit_mask=mask,
            label=payload.label,
            mode=payload.mode,
            overwrite=payload.overwrite,
            preserve_labels=payload.preserveLabels,
        )

    def apply_flood_fill(self, session, payload: FloodFillRequest) -> EditResponse:
        axis = normalize_axis(payload.axis)
        slice_view = extract_slice_view(session.seg_data, axis, payload.sliceIndex)
        fill_mask = flood_fill_mask(slice_view, payload.x, payload.y)
        return self._apply_mask(
            session,
            axis=axis,
            slice_index=payload.sliceIndex,
            slice_view=slice_view,
            edit_mask=fill_mask,
            label=payload.label,
            mode="paint",
            overwrite=payload.overwrite,
            preserve_labels=payload.preserveLabels,
        )

    def apply_interpolate(self, session, payload: SliceInterpolateRequest) -> EditResponse:
        axis = normalize_axis(payload.axis)
        result, changed = interpolate_slices(
            session.seg_data, axis, payload.startSlice, payload.endSlice, payload.label,
        )
        if changed > 0:
            session_service.push_snapshot(session)
            session.seg_data[:] = result
        return EditResponse(
            ok=True,
            changedVoxels=changed,
            session=session_service.session_status(session),
        )

    def apply_relabel(self, session, payload: RelabelRequest) -> EditResponse:
        axis = normalize_axis(payload.axis)
        result, changed, from_label = relabel_3d_component(
            session.seg_data, axis, payload.sliceIndex, payload.x, payload.y, payload.toLabel,
        )
        if changed > 0:
            session_service.push_snapshot(session)
            session.seg_data[:] = result
        return EditResponse(
            ok=True,
            changedVoxels=changed,
            session=session_service.session_status(session),
        )

    def _get_seed(self, session, axis: str, slice_index: int, x: int, y: int) -> tuple[int, int, int]:
        slice_view = extract_slice_view(session.seg_data, axis, slice_index)
        display_height = slice_view.shape[0]
        return display_to_volume(axis, x, y, slice_index, display_height)

    def preview_magic_wand(self, session, payload: MagicWandPreviewRequest) -> MagicWandPreviewResponse:
        axis = normalize_axis(payload.axis)
        viewer_service.ensure_ct_loaded(session)
        if session.ct_data is None:
            raise ValueError("CT data not available for magic wand")

        seed = self._get_seed(session, axis, payload.sliceIndex, payload.x, payload.y)
        mask, seed_hu, tol = region_grow_3d(
            session.ct_data, seed, payload.tolerance, payload.maxVoxels, 1,
        )
        selected = int(np.sum(mask))
        if selected == 0:
            session.preview_mask = None
            return MagicWandPreviewResponse(
                ok=True, selectedVoxels=0, sliceMin=0, sliceMax=0,
                seedHU=round(seed_hu, 1), toleranceHU=round(tol, 1),
            )

        # Cache 3D mask in session for slice-by-slice retrieval
        session.preview_mask = mask
        coords = np.argwhere(mask)

        selected_hu = session.ct_data[mask]
        return MagicWandPreviewResponse(
            ok=True,
            selectedVoxels=selected,
            sliceMin=int(coords.min(axis=0)[0]),
            sliceMax=int(coords.max(axis=0)[0]),
            seedHU=round(seed_hu, 1),
            toleranceHU=round(tol, 1),
            meanHU=round(float(selected_hu.mean()), 1),
            minHU=round(float(selected_hu.min()), 1),
            maxHU=round(float(selected_hu.max()), 1),
        )

    def get_preview_mask_slice(self, session, axis: str, index: int) -> bytes | None:
        """Return PNG bytes of the preview mask for a given axis/slice.

        Colors: green = added, red = removed, yellow = relabel.
        Uses checkerboard pattern for clarity.
        """
        if session.preview_mask is None:
            return None
        from backend.app.core.viewer import extract_slice

        raw = session.preview_mask
        # Handle both boolean masks (magic wand) and int8 diff maps (postprocess)
        if raw.dtype == bool:
            mask_slice = extract_slice(raw.astype(np.uint8), axis, index)
            if not np.any(mask_slice):
                return None
            h, w = mask_slice.shape
            yy, xx = np.mgrid[0:h, 0:w]
            checker = ((yy // 2) + (xx // 2)) % 2 == 0
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[(mask_slice > 0) & checker] = [0, 255, 100, 180]
        else:
            mask_slice = extract_slice(raw, axis, index)
            if not np.any(mask_slice):
                return None
            h, w = mask_slice.shape
            yy, xx = np.mgrid[0:h, 0:w]
            checker = ((yy // 2) + (xx // 2)) % 2 == 0
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            # Added voxels: green
            rgba[(mask_slice == 1) & checker] = [0, 255, 100, 180]
            # Removed voxels: red
            rgba[(mask_slice == -1) & checker] = [255, 60, 60, 180]
            # Changed label: yellow
            rgba[(mask_slice == 2) & checker] = [255, 255, 0, 180]

        buf = BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
        return buf.getvalue()

    def apply_magic_wand(self, session, payload: MagicWandApplyRequest) -> EditResponse:
        # Use cached mask from preview if available, otherwise recompute
        if session.preview_mask is not None:
            mask = session.preview_mask
        else:
            axis = normalize_axis(payload.axis)
            viewer_service.ensure_ct_loaded(session)
            if session.ct_data is None:
                raise ValueError("CT data not available for magic wand")
            seed = self._get_seed(session, axis, payload.sliceIndex, payload.x, payload.y)
            mask, _, _ = region_grow_3d(
                session.ct_data, seed, payload.tolerance, payload.maxVoxels, 1,
            )

        preserve = (
            np.isin(session.seg_data, payload.preserveLabels) if payload.preserveLabels
            else np.zeros_like(mask)
        )
        target = mask & ~preserve
        if not payload.overwrite:
            target &= (session.seg_data == 0) | (session.seg_data == payload.label)

        changed = int(np.sum(session.seg_data[target] != payload.label))
        if changed > 0:
            session_service.push_snapshot(session)
            session.seg_data[target] = payload.label

        session.preview_mask = None
        return EditResponse(
            ok=True,
            changedVoxels=changed,
            session=session_service.session_status(session),
        )

    def clear_preview_mask(self, session) -> None:
        session.preview_mask = None

    def _apply_mask(self, session, axis, slice_index, slice_view, edit_mask, label, mode, overwrite, preserve_labels):
        updated_slice, changed = apply_edit_to_slice(
            slice_view,
            edit_mask=edit_mask,
            label=label,
            mode=mode,
            overwrite=overwrite,
            preserve_labels=preserve_labels,
        )
        if changed > 0:
            session_service.push_snapshot(session)
            write_slice_view(session.seg_data, axis, slice_index, updated_slice)

        return EditResponse(
            ok=True,
            changedVoxels=changed,
            session=session_service.session_status(session),
        )


edit_service = EditService()
