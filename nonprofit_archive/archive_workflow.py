from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Literal

from .infrai_gateway import InfraiGateway


DocumentType = Literal["donor_receipt", "volunteer_reminder", "campaign_report"]

NEXT_ACTION: dict[str, str] = {
    "donor_receipt": "prepare_donor_acknowledgement",
    "volunteer_reminder": "confirm_volunteer_schedule",
    "campaign_report": "review_campaign_results",
}


def chunk_text(text: str, words_per_chunk: int = 180) -> list[str]:
    words = text.split()
    return [" ".join(words[start : start + words_per_chunk]) for start in range(0, len(words), words_per_chunk)]


@dataclass(frozen=True)
class ArchiveAnswer:
    answer: str
    document_id: str
    document_type: str
    recommended_action: str
    score: float


def choose_answer(matches: list[dict[str, Any]]) -> ArchiveAnswer | None:
    if not matches:
        return None
    strongest = max(matches, key=lambda match: float(match.get("score", 0)))
    metadata = strongest.get("metadata") or {}
    document_type = str(metadata.get("document_type", "campaign_report"))
    return ArchiveAnswer(
        answer=str(metadata.get("text", "")),
        document_id=str(metadata.get("document_id", "")),
        document_type=document_type,
        recommended_action=NEXT_ACTION.get(document_type, "review_campaign_results"),
        score=float(strongest.get("score", 0)),
    )


class NonprofitArchive:
    def __init__(self, gateway: InfraiGateway) -> None:
        self.gateway = gateway
        self.collection = os.getenv("INFRAI_COLLECTION", "nonprofit-document-archive")
        self.dimension = int(os.getenv("INFRAI_EMBEDDING_DIMENSION", "1536"))
        self._collection_ready = False

    def index_document(self, document_id: str, document_type: DocumentType, pdf_bytes: bytes) -> int:
        if not self._collection_ready:
            self.gateway.create_collection(self.collection, self.dimension)
            self._collection_ready = True

        chunks = chunk_text(self.gateway.ocr_pdf(pdf_bytes))
        if not chunks:
            return 0
        embeddings = self.gateway.embed(chunks)
        vectors = []
        for index, (text, values) in enumerate(zip(chunks, embeddings, strict=True)):
            vector_id = hashlib.sha256(f"{document_id}:{index}".encode()).hexdigest()
            vectors.append(
                {
                    "id": vector_id,
                    "values": values,
                    "metadata": {
                        "document_id": document_id,
                        "document_type": document_type,
                        "chunk_index": index,
                        "text": text,
                    },
                }
            )
        self.gateway.upsert(self.collection, vectors, document_id)
        return len(vectors)

    def ask(self, question: str, top_k: int) -> ArchiveAnswer | None:
        question_vector = self.gateway.embed([question])[0]
        data = self.gateway.query(self.collection, question_vector, top_k)
        matches = data if isinstance(data, list) else data.get("matches", [])
        return choose_answer(matches)
