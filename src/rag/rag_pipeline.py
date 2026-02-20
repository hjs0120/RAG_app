"""RAG 파이프라인 오케스트레이션 — run_query, RAGResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.embedding_bge import encode_query
from src.core.faiss_index import search
from src.llm.ollama_client import OllamaClient
from src.rag.chunk_assembler import assemble_chunks
from src.rag.prompt_templates import build_rag_chat_messages
from src.rag.rag_config import (
    FAISS_TOP_K,
    SCORE_THRESHOLD,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TEMPERATURE,
    DEFAULT_OLLAMA_NUM_CTX,
)

NO_GROUNDS_MSG = "관련 근거를 찾지 못했습니다."


def _format_source(i: int, meta: dict[str, Any]) -> str:
    """chunk meta 기반 출처 문자열. [1] doc_id=..., page=..., section=..., chunk_id=..."""
    doc_id = meta.get("doc_id") or ""
    page = meta.get("page")
    if page is None:
        chunk_meta = meta.get("meta") or {}
        pages = chunk_meta.get("pages") or []
        page = pages[0] if pages else ""
    section = meta.get("section") or ""
    chunk_id = meta.get("chunk_id") or ""
    return f"[{i}] doc_id={doc_id}, page={page}, section={section}, chunk_id={chunk_id}"


@dataclass
class RAGResult:
    """RAG 쿼리 결과."""

    question: str
    retrieved_chunks: list[tuple[int, float, dict[str, Any]]]
    assembled_context: str
    answer: str
    sources: list[str]
    debug_info: dict[str, Any] = field(default_factory=dict)


class RAGPipeline:
    """RAG 파이프라인 — FAISS 검색, Chunk 재조합, Ollama 답변."""

    def __init__(
        self,
        index: Any,
        meta_list: list[dict[str, Any]],
        *,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        self.index = index
        self.meta_list = meta_list
        self.ollama = ollama_client or OllamaClient()

    def run_query(
        self,
        question: str,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        temperature: float = DEFAULT_OLLAMA_TEMPERATURE,
        num_ctx: int = DEFAULT_OLLAMA_NUM_CTX,
        top_k: int = FAISS_TOP_K,
        score_threshold: float = SCORE_THRESHOLD,
    ) -> RAGResult:
        """
        질문에 대한 RAG 파이프라인 실행.
        - FAISS 검색 → Chunk 재조합 → 출처 생성 → Ollama 답변
        - score_threshold 이하면 LLM 호출 없이 "관련 근거를 찾지 못했습니다" 반환
        """
        # 1. 쿼리 임베딩 & FAISS 검색
        q_emb = encode_query(question)
        results = search(self.index, q_emb, self.meta_list, top_k=top_k)

        # 2. 근거 부족 시 거절 (검색 결과가 없을 때만 fallback, 점수 낮아도 결과 있으면 LLM에 맡김)
        if not results:
            return RAGResult(
                question=question,
                retrieved_chunks=[],
                assembled_context="",
                answer=NO_GROUNDS_MSG,
                sources=[],
                debug_info={"reason": "no_results"},
            )

        # 검색 결과가 있으면 점수가 낮아도 LLM에 맡김 (threshold로 short-circuit 안 함)
        # 3. Chunk 재조합
        assembled, selected_chunks, debug_info = assemble_chunks(results)
        if not assembled.strip():
            return RAGResult(
                question=question,
                retrieved_chunks=results,
                assembled_context="",
                answer=NO_GROUNDS_MSG,
                sources=[],
                debug_info={**debug_info, "reason": "empty_assembled"},
            )

        # 4. 출처 목록 생성
        sources = [
            _format_source(i + 1, sc["meta"])
            for i, sc in enumerate(selected_chunks)
        ]

        # 5. Ollama 답변 생성 (instruct 모델용 /api/chat 사용)
        messages = build_rag_chat_messages(assembled, sources, question)
        try:
            answer = self.ollama.generate_chat(
                messages,
                model=model,
                temperature=temperature,
                num_ctx=num_ctx,
            )
        except RuntimeError as e:
            answer = str(e)

        return RAGResult(
            question=question,
            retrieved_chunks=results,
            assembled_context=assembled,
            answer=answer,
            sources=sources,
            debug_info=debug_info,
        )
