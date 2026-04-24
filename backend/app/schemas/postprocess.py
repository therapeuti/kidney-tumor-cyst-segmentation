from pydantic import BaseModel, Field

from backend.app.schemas.session import SessionStatusResponse


class PostprocessParamOption(BaseModel):
    label: str
    value: str | int | float


class PostprocessParamDefinition(BaseModel):
    key: str
    label: str
    type: str
    required: bool = True
    default: str | int | float | bool | None = None
    options: list[PostprocessParamOption] = Field(default_factory=list)


class PostprocessFunctionDefinition(BaseModel):
    key: str
    label: str
    requiresCt: bool = False
    params: list[PostprocessParamDefinition]


class PostprocessRequest(BaseModel):
    function: str
    params: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class PostprocessPreviewResponse(BaseModel):
    ok: bool
    changedVoxels: int
    summary: dict


class PostprocessApplyResponse(BaseModel):
    ok: bool
    changedVoxels: int
    summary: dict
    session: SessionStatusResponse
