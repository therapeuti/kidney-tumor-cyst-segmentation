from urllib.parse import urlencode

import nibabel as nib

from backend.app.core.coordinate import normalize_axis
from backend.app.core.labels import label_metadata_list
from backend.app.core.viewer import extract_slice, render_ct_slice_png
from backend.app.schemas.viewer import SessionMetaResponse, SliceMaskResponse, SliceResponse


class ViewerService:
    def session_meta(self, session) -> SessionMetaResponse:
        shape = [int(v) for v in session.seg_data.shape]
        spacing = [float(v) for v in session.seg_img.header.get_zooms()[: len(shape)]]
        return SessionMetaResponse(
            shape=shape,
            spacing=spacing,
            labels=label_metadata_list(),
        )

    def ensure_ct_image(self, session) -> None:
        if session.ct_img is not None or session.img_path is None:
            return
        session.ct_img = nib.load(session.img_path)

    def ensure_ct_loaded(self, session) -> None:
        if session.ct_data is not None or session.img_path is None:
            return
        self.ensure_ct_image(session)
        session.ct_data = session.ct_img.get_fdata(dtype="float32")

    def session_slice(self, session, axis: str, index: int, window: float, level: float) -> SliceResponse:
        axis = normalize_axis(axis)
        mask_slice = extract_slice(session.seg_data, axis, index)
        height, width = [int(v) for v in mask_slice.shape]

        ct_url = None
        if session.img_path is not None:
            query = urlencode({"axis": axis, "index": index, "window": window, "level": level})
            ct_url = f"/api/sessions/{session.session_id}/slice-image?{query}"

        return SliceResponse(
            axis=axis,
            index=index,
            width=width,
            height=height,
            ctImageUrl=ct_url,
            mask=SliceMaskResponse(
                encoding="raw",
                labels=[int(v) for v in sorted(set(mask_slice.ravel().tolist()))],
                data=mask_slice.astype(int).tolist(),
            ),
        )

    def slice_image(self, session, axis: str, index: int, window: float, level: float) -> bytes:
        axis = normalize_axis(axis)
        if session.img_path is None:
            raise ValueError("CT image is not available for this session.")
        self.ensure_ct_image(session)
        ct_slice = extract_slice(session.ct_img.dataobj, axis, index)
        return render_ct_slice_png(ct_slice, window=window, level=level)


viewer_service = ViewerService()
