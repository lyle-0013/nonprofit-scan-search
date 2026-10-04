from __future__ import annotations

import base64
import binascii
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .archive_workflow import NonprofitArchive
from .infrai_gateway import InfraiError, InfraiGateway


class IndexDocumentRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=120)
    document_type: Literal["donor_receipt", "volunteer_reminder", "campaign_report"]
    pdf_base64: str = Field(min_length=8)


class IndexDocumentResponse(BaseModel):
    document_id: str
    chunks_indexed: int


class AskArchiveRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class AskArchiveResponse(BaseModel):
    answer: str
    document_id: str
    document_type: str
    recommended_action: str
    score: float


api = FastAPI(title="Nonprofit Scan Search")
_archive: NonprofitArchive | None = None


def archive() -> NonprofitArchive:
    global _archive
    if _archive is None:
        _archive = NonprofitArchive(InfraiGateway())
    return _archive


@api.exception_handler(InfraiError)
async def infrai_error_handler(_: Request, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(status_code=status, content={"error": exc.code, "detail": exc.detail})


@api.post("/documents/index", response_model=IndexDocumentResponse)
def index_document(request: IndexDocumentRequest) -> IndexDocumentResponse:
    try:
        pdf_bytes = base64.b64decode(request.pdf_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="pdf_base64 must contain valid base64") from exc
    chunks = archive().index_document(request.document_id, request.document_type, pdf_bytes)
    return IndexDocumentResponse(document_id=request.document_id, chunks_indexed=chunks)


@api.post("/archive/ask", response_model=AskArchiveResponse)
def ask_archive(request: AskArchiveRequest) -> AskArchiveResponse:
    answer = archive().ask(request.question, request.top_k)
    if answer is None:
        raise HTTPException(status_code=404, detail="No indexed passage matched the question")
    return AskArchiveResponse(**answer.__dict__)
