from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    caseId: str
    phase: str


class SessionResponse(BaseModel):
    sessionId: str
    caseId: str
    phase: str
    dirty: bool
    canUndo: bool
    canRedo: bool


class SessionStatusResponse(SessionResponse):
    shape: list[int]
    spacing: list[float]
    labels: list[int]


class SaveSessionResponse(BaseModel):
    saved: bool
    dirty: bool
    backupPath: str | None = None
