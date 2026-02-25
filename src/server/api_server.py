"""FastAPI API 서버 — POST /api/ask, RAG 연동."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(PROJECT_ROOT))

from src.db.db_manager import load_index
from src.rag.rag_pipeline import RAGPipeline
from src.rag.rag_config import FAISS_TOP_K, DEFAULT_OLLAMA_MODEL
from src.core.embedding_bge import preload_model
from src.llm.ollama_client import OllamaClient


def _log(msg: str) -> None:
    """로그 출력 (서브프로세스 stdout → Admin UI 로그창)."""
    print(msg, flush=True)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """서버 시작 시 bge-m3, FAISS, Ollama 모델 사전 로드."""
    _log("INFO:     bge-m3 임베딩 모델 로딩 중...")
    try:
        preload_model()
        _log("INFO:     bge-m3 로드 완료")
    except Exception as e:
        _log(f"WARNING:  bge-m3 로드 실패: {e} (첫 요청 시 로드 시도)")
    _log("INFO:     FAISS 인덱스 로딩 중...")
    try:
        _get_pipeline()
        _log("INFO:     FAISS 인덱스 로드 완료")
    except Exception as e:
        _log(f"WARNING:  FAISS 인덱스 로드 실패: {e} (첫 요청 시 로드 시도)")
    _log("INFO:     Ollama 모델 로딩 중...")
    try:
        OllamaClient().load_model(DEFAULT_OLLAMA_MODEL)
        _log(f"INFO:     Ollama 모델 로드 완료 ({DEFAULT_OLLAMA_MODEL})")
    except Exception as e:
        _log(f"WARNING:  Ollama 모델 로드 실패: {e} (첫 요청 시 로드 시도)")
    yield
    # shutdown: 정리 작업 (필요 시)


app = FastAPI(title="RAG API", version="0.1.0", lifespan=_lifespan)

# CORS: Web Client 도메인 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용. 운영 시 특정 origin으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역: 인덱스/파이프라인 (첫 요청 시 로드)
_pipeline: RAGPipeline | None = None
_default_output_dir = PROJECT_ROOT / "output"
_default_index_path = _default_output_dir / "rules.index"


def _get_pipeline() -> RAGPipeline:
    """인덱스 로드 후 RAGPipeline 반환. 없으면 예외."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if not _default_index_path.exists():
        raise RuntimeError(
            f"FAISS 인덱스가 없습니다: {_default_index_path}\n"
            "DB 생성 탭에서 먼저 임베딩을 생성하세요."
        )
    index, meta_list = load_index(_default_index_path, use_gpu=True)
    _pipeline = RAGPipeline(index=index, meta_list=meta_list)
    return _pipeline


# --- Request/Response 모델 ---


class AskRequest(BaseModel):
    """POST /api/ask Request body."""

    query: str
    top_k: int = 5


class SourceItem(BaseModel):
    """출처 1건."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


class AskResponse(BaseModel):
    """POST /api/ask Response."""

    status: str  # "success" | "error"
    answer: str
    sources: list[SourceItem]


def _meta_to_source_item(meta: dict[str, Any]) -> SourceItem:
    """faiss meta를 SourceItem으로 변환."""
    chunk_id = meta.get("chunk_id") or ""
    text = meta.get("full_text") or meta.get("text") or ""
    sub = meta.get("meta") or {}
    metadata = {
        "structure_path": sub.get("structure_path") or "",
        "physical_page": sub.get("physical_page"),
        "file_name": sub.get("file_name") or "",
        "doc_id": meta.get("doc_id") or "",  # PDF 조회용 (chunk_id와 분리)
    }
    return SourceItem(chunk_id=chunk_id, text=text, metadata=metadata)


# --- 엔드포인트 ---


@app.get("/health")
def health() -> dict:
    """서버 상태 확인."""
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def api_ask(body: AskRequest) -> AskResponse:
    """
    RAG 질의응답.
    - query: 질문
    - top_k: 검색 Chunk 수 (기본 5)
    """
    try:
        pipeline = _get_pipeline()
        top_k = max(1, min(20, body.top_k or FAISS_TOP_K))
        result = pipeline.run_query(body.query, top_k=top_k)

        sources = [_meta_to_source_item(m) for m in result.sources_meta]
        return AskResponse(
            status="success",
            answer=result.answer,
            sources=sources,
        )
    except RuntimeError as e:
        return AskResponse(
            status="error",
            answer=str(e),
            sources=[],
        )
    except Exception as e:
        return AskResponse(
            status="error",
            answer=f"오류: {e}",
            sources=[],
        )
