from pydantic import BaseModel


class PhaseLabelStats(BaseModel):
    phase: str
    label: int
    labelName: str
    voxelCount: int


class PhasePairDice(BaseModel):
    phaseA: str
    phaseB: str
    label: int
    labelName: str
    dice: float


class ComparisonResponse(BaseModel):
    caseId: str
    phases: list[str]
    labelStats: list[PhaseLabelStats]
    diceScores: list[PhasePairDice]
