from pydantic import BaseModel


class LabelDisplayResponse(BaseModel):
    id: int
    key: str
    name: str
    color: list[int]


class SessionMetaResponse(BaseModel):
    shape: list[int]
    spacing: list[float]
    labels: list[LabelDisplayResponse]


class SliceMaskResponse(BaseModel):
    encoding: str
    labels: list[int]
    data: list[list[int]]


class SliceResponse(BaseModel):
    axis: str
    index: int
    width: int
    height: int
    ctImageUrl: str | None
    mask: SliceMaskResponse
