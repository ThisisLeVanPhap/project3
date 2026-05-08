from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    title: str = ""
    source: str = ""
    score: float = 0.0
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_context_block(self, max_chars: int = 900) -> str:
        content = self.text.strip()
        if not content:
            return ""

        title = self.title.strip()
        source = self.source.strip()
        return f"- {title} ({source}): {content[:max_chars]}"

    @classmethod
    def from_hit(
        cls,
        hit: Dict[str, Any],
        idx: int = 0,
        tenant_id: Optional[str] = None,
    ) -> "RetrievalResult":
        metadata = dict(hit.get("metadata") or {})

        url = (hit.get("url") or "").strip()
        if url and "url" not in metadata:
            metadata["url"] = url

        return cls(
            doc_id=str(hit.get("doc_id") or hit.get("id") or url or f"doc-{idx}"),
            chunk_id=str(hit.get("chunk_id") or hit.get("id") or f"chunk-{idx}"),
            text=(hit.get("text") or hit.get("content") or "").strip(),
            title=(hit.get("title") or "").strip(),
            source=(hit.get("source") or url).strip(),
            score=float(hit.get("score", 0.0) or 0.0),
            tenant_id=tenant_id if tenant_id is not None else hit.get("tenant_id"),
            metadata=metadata,
        )
