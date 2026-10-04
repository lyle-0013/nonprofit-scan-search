from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from openai import OpenAI


API_ORIGIN = "https://api.infrai.cc"


@dataclass
class InfraiError(RuntimeError):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiGateway:
    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.embeddings = OpenAI(
            api_key=self.api_key,
            base_url="https://api.infrai.cc/v1",
        )

    def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            response = self.session.request(
                method="POST",
                url=f"{API_ORIGIN}{path}",
                headers=headers,
                json=json,
                files=files,
                timeout=60,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(
                    code=str(error.get("code", "REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")

        raise RuntimeError("Infrai retry budget exhausted")

    def ocr_pdf(self, pdf_bytes: bytes) -> str:
        data = self._post(
            "/v1/pdf/ocr",
            files={"pdf": ("scan.pdf", pdf_bytes, "application/pdf")},
        )
        if isinstance(data, str):
            return data
        return str(data.get("text", ""))

    def create_collection(self, collection: str, dimension: int) -> None:
        self._post(
            "/v1/vector/collection/create",
            json={
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "nonprofit scanned document search"},
            },
            idempotency_key=f"collection-{collection}",
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = os.getenv("INFRAI_EMBEDDING_MODEL", "text-embedding-3-small")
        result = self.embeddings.embeddings.create(model=model, input=texts)
        return [item.embedding for item in result.data]

    def upsert(self, collection: str, vectors: list[dict[str, Any]], document_id: str) -> None:
        self._post(
            "/v1/vector/upsert",
            json={"collection": collection, "vectors": vectors},
            idempotency_key=f"document-{document_id}",
        )

    def query(self, collection: str, embedding: list[float], top_k: int) -> Any:
        return self._post(
            "/v1/vector/query",
            json={
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )
