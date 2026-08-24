from fastapi import APIRouter

from app import extraction
from app.schemas import ExtractionRequest, ExtractionResponse

router = APIRouter(prefix="/extraction", tags=["extraction"])


@router.post("/infer", response_model=ExtractionResponse)
def infer(payload: ExtractionRequest):
    return extraction.infer_application_fields(payload)
