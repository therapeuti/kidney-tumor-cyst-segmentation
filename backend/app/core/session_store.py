from dataclasses import dataclass
from typing import Any

import nibabel as nib
import numpy as np

from backend.app.core.history import HistoryManager


@dataclass
class SessionRecord:
    session_id: str
    case_id: str
    phase: str
    seg_path: str
    img_path: str | None
    seg_img: nib.Nifti1Image
    seg_data: np.ndarray
    ct_img: Any | None
    ct_data: np.ndarray | None
    history: HistoryManager
    dirty: bool = False
    preview_mask: np.ndarray | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def add(self, session: SessionRecord) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)


session_store = SessionStore()
