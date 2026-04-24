from pathlib import Path
import uuid

from backend.app.core.case_loader import get_case_dir, load_case_paths
from backend.app.core.history import HistoryManager
from backend.app.core.nifti_io import create_empty_segmentation, ensure_backup, load_segmentation, save_segmentation
from backend.app.core.session_store import SessionRecord, session_store
from backend.app.schemas.session import SaveSessionResponse, SessionResponse, SessionStatusResponse


class SessionService:
    def create_session(self, case_id: str, phase: str) -> SessionResponse:
        case_dir = get_case_dir(case_id)
        if case_dir is None:
            raise FileNotFoundError(f"Case not found: {case_id}")

        phase_paths = load_case_paths(case_dir)
        normalized_phase = phase.upper()
        if normalized_phase not in phase_paths:
            raise ValueError(f"Phase not found for case {case_id}: {phase}")

        paths = phase_paths[normalized_phase]
        img_path = paths["img"]

        if paths["seg"] is not None:
            seg_path = Path(paths["seg"])
            seg_img, seg_data = load_segmentation(seg_path)
        elif img_path is not None:
            # CT-only case: create empty segmentation from CT geometry
            seg_img, seg_data = create_empty_segmentation(Path(img_path))
            seg_path = case_dir / f"{case_id}_Segmentation_{normalized_phase}.nii.gz"
        else:
            raise ValueError(f"No segmentation or CT image for case {case_id} phase {phase}")

        session = SessionRecord(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            phase=normalized_phase,
            seg_path=str(seg_path),
            img_path=str(img_path) if img_path is not None else None,
            seg_img=seg_img,
            seg_data=seg_data,
            ct_img=None,
            ct_data=None,
            history=HistoryManager(),
            dirty=False,
        )
        session_store.add(session)
        return SessionResponse(
            sessionId=session.session_id,
            caseId=session.case_id,
            phase=session.phase,
            dirty=session.dirty,
            canUndo=session.history.can_undo,
            canRedo=session.history.can_redo,
        )

    def get_session(self, session_id: str) -> SessionRecord | None:
        return session_store.get(session_id)

    def session_status(self, session: SessionRecord) -> SessionStatusResponse:
        shape = [int(v) for v in session.seg_data.shape]
        spacing = [float(v) for v in session.seg_img.header.get_zooms()[: len(shape)]]
        labels = [int(v) for v in sorted(set(session.seg_data.ravel().tolist()))]
        return SessionStatusResponse(
            sessionId=session.session_id,
            caseId=session.case_id,
            phase=session.phase,
            dirty=session.dirty,
            canUndo=session.history.can_undo,
            canRedo=session.history.can_redo,
            shape=shape,
            spacing=spacing,
            labels=labels,
        )

    def save_session(self, session: SessionRecord) -> SaveSessionResponse:
        seg_path = Path(session.seg_path)
        backup_path_str: str | None = None
        if seg_path.exists():
            backup_path = ensure_backup(seg_path)
            backup_path_str = str(backup_path)
        save_segmentation(seg_path, session.seg_data, session.seg_img)
        session.dirty = False
        return SaveSessionResponse(saved=True, dirty=False, backupPath=backup_path_str)

    def push_snapshot(self, session: SessionRecord) -> None:
        session.history.push(session.seg_data)
        session.dirty = True

    def undo(self, session: SessionRecord) -> SessionStatusResponse:
        session.seg_data = session.history.undo(session.seg_data)
        session.dirty = True
        return self.session_status(session)

    def redo(self, session: SessionRecord) -> SessionStatusResponse:
        session.seg_data = session.history.redo(session.seg_data)
        session.dirty = True
        return self.session_status(session)


session_service = SessionService()
