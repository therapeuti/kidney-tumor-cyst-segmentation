from pydantic import BaseModel, Field

from backend.app.schemas.session import SessionStatusResponse


class BrushEditRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    points: list[list[float]]
    radius: int = Field(ge=1, le=128)
    label: int = Field(ge=0)
    mode: str
    overwrite: bool = False
    preserveLabels: list[int] = Field(default_factory=list)


class PolygonEditRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    vertices: list[list[float]]
    label: int = Field(ge=0)
    mode: str
    overwrite: bool = False
    preserveLabels: list[int] = Field(default_factory=list)


class FloodFillRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    label: int = Field(ge=0)
    overwrite: bool = False
    preserveLabels: list[int] = Field(default_factory=list)


class SliceInterpolateRequest(BaseModel):
    axis: str
    startSlice: int = Field(ge=0)
    endSlice: int = Field(ge=0)
    label: int = Field(ge=1)


class RelabelRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    toLabel: int = Field(ge=0)


class MagicWandPreviewRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    tolerance: float = Field(default=50.0, ge=1, le=500)
    maxVoxels: int = Field(default=500000, ge=100, le=5000000)


class MagicWandPreviewResponse(BaseModel):
    ok: bool
    selectedVoxels: int
    sliceMin: int
    sliceMax: int
    seedHU: float
    toleranceHU: float
    meanHU: float = 0.0
    minHU: float = 0.0
    maxHU: float = 0.0


class MagicWandApplyRequest(BaseModel):
    axis: str
    sliceIndex: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    tolerance: float = Field(default=50.0, ge=1, le=500)
    maxVoxels: int = Field(default=500000, ge=100, le=5000000)
    label: int = Field(ge=1)
    overwrite: bool = False
    preserveLabels: list[int] = Field(default_factory=list)


class EditResponse(BaseModel):
    ok: bool
    changedVoxels: int
    session: SessionStatusResponse
