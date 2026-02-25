"""bge-m3 임베딩 — 로컬 모델 로드, batch encode, normalize."""

from __future__ import annotations

import os
from pathlib import Path

# bge-m3 로딩 시 "Loading weights" 진행 바 로그 억제
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# 프로젝트 루트 기준 로컬 모델 경로 (app.py 상위 = src/core/ 상위 2단계)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BGE_MODEL_PATH = _PROJECT_ROOT / "models" / "bge-m3"
DEFAULT_BATCH_SIZE = 32


def _get_device() -> str:
    """CUDA 사용 가능 시 cuda, 아니면 cpu."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def preload_model() -> None:
    """bge-m3 모델을 미리 메모리에 로드. 이미 로드된 경우 캐시된 인스턴스 반환."""
    get_model()


def get_model() -> "SentenceTransformer":
    """bge-m3 모델 싱글톤 로드 (lazy). 이미 로드되어 있으면 캐시 반환.
    DB 생성 탭 임베딩 후 사용 탭 사전모델 로드 시 동일 인스턴스 재사용."""
    if not hasattr(get_model, "_model"):
        from sentence_transformers import SentenceTransformer

        path = str(BGE_MODEL_PATH)
        if not Path(path).exists():
            raise FileNotFoundError(
                f"bge-m3 모델이 없습니다: {path}\n"
                "다운로드: python scripts/download_bge_m3.py"
            )
        get_model._model = SentenceTransformer(path, device=_get_device())
    return get_model._model


def encode_texts(
    texts: list[str],
    *,
    model: "SentenceTransformer | None" = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    normalize: bool = True,
) -> np.ndarray:
    """
    텍스트 리스트를 bge-m3로 임베딩.
    - normalize=True 시 FAISS IndexFlatIP(내적)과 cosine 유사도 동일
    Returns:
        embeddings (N x D) float32
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    m = model or get_model()
    embs = m.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 100,
    )
    return np.asarray(embs, dtype=np.float32)


def encode_query(query: str, *, model: "SentenceTransformer | None" = None) -> np.ndarray:
    """단일 쿼리 임베딩 (1 x D)."""
    return encode_texts([query], model=model, normalize=True)
