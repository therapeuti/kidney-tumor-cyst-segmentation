from fastapi import APIRouter, HTTPException

from backend.app.schemas.case import CaseDetailResponse, CaseSummaryResponse
from backend.app.schemas.comparison import ComparisonResponse
from backend.app.services.case_service import get_case_detail, list_cases
from backend.app.services.comparison_service import compare_phases


router = APIRouter()


@router.get("/cases", response_model=list[CaseSummaryResponse])
def get_cases() -> list[CaseSummaryResponse]:
    return list_cases()


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: str) -> CaseDetailResponse:
    case_detail = get_case_detail(case_id)
    if case_detail is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return case_detail


@router.get("/cases/{case_id}/compare", response_model=ComparisonResponse)
def get_phase_comparison(case_id: str) -> ComparisonResponse:
    try:
        return compare_phases(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
