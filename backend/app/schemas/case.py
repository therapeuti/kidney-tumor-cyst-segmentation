from pydantic import BaseModel


class PhaseSummaryResponse(BaseModel):
    phase: str
    hasCt: bool
    shape: list[int]
    spacing: list[float]
    labels: list[int]


class CaseSummaryResponse(BaseModel):
    caseId: str
    phases: list[str]


class CaseDetailResponse(BaseModel):
    caseId: str
    phases: list[PhaseSummaryResponse]
