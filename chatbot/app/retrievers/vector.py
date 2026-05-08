import json
import os
from typing import Any, Dict, List

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from .base import BaseRetriever
from .schemas import RetrievalResult
from .text import repair_mojibake


DEFAULT_EMBEDDING_MODEL = os.environ.get(
    "RETRIEVAL_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


class VectorRetriever(BaseRetriever):
    def __init__(self, chunks_jsonl: str, model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self.chunks: List[Dict[str, Any]] = []
        self.embedding_inputs: List[str] = []

        with open(chunks_jsonl, "r", encoding="utf-8") as handle:
            for line in handle:
                chunk = json.loads(line)
                self.chunks.append(chunk)
                self.embedding_inputs.append(self._chunk_text(chunk))

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval()

        self.chunk_embeddings = self._encode_texts(self.embedding_inputs)

    def search(self, query: str, k: int = 4) -> List[RetrievalResult]:
        if not self.chunks:
            return []

        query_embedding = self._encode_texts([query or ""])
        scores = torch.matmul(self.chunk_embeddings, query_embedding[0])
        limit = max(0, min(k, len(self.chunks)))
        if limit <= 0:
            return []

        top_scores, top_indices = torch.topk(scores, k=limit)
        results: List[RetrievalResult] = []
        for rank, chunk_index in enumerate(top_indices.tolist()):
            chunk = dict(self.chunks[chunk_index])
            chunk["score"] = float(top_scores[rank].item())
            results.append(RetrievalResult.from_hit(chunk, idx=chunk_index))
        return results

    def _encode_texts(self, texts: List[str], batch_size: int = 16) -> torch.Tensor:
        batches: List[torch.Tensor] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = self.model(**encoded)
            pooled = self._mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
            batches.append(F.normalize(pooled, p=2, dim=1))
        return torch.cat(batches, dim=0) if batches else torch.empty((0, 0))

    def _mean_pool(self, last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        masked = last_hidden_state * mask
        summed = masked.sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        return summed / counts

    def _chunk_text(self, chunk: Dict[str, Any]) -> str:
        title = repair_mojibake((chunk.get("title") or "").strip())
        url = repair_mojibake((chunk.get("url") or "").strip())
        content = repair_mojibake((chunk.get("content") or "").strip())
        return "\n".join(part for part in (title, url, content) if part)
