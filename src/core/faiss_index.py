"""FAISS 인덱스 — IndexFlatIP 생성/저장/로드, 메타데이터 연동."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import faiss

from src.core.embedding_bge import encode_query, encode_texts


def _index_path_from_base(base: str | Path, stem: str = "rules") -> Path:
    """base 디렉터리에서 index 파일 경로."""
    base = Path(base)
    return base / f"{stem}.index"


def _meta_path_from_base(base: str | Path, stem: str = "rules") -> Path:
    """base 디렉터리에서 meta JSONL 파일 경로."""
    base = Path(base)
    return base / f"{stem}_meta.jsonl"


def create_index(
    embeddings: np.ndarray,
) -> faiss.IndexFlatIP:
    """
    정규화된 임베딩으로 IndexFlatIP 생성.
    embeddings: (N x D) float32, L2-normalized 권장.
    """
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    return index


def save_index(
    index: faiss.IndexFlatIP,
    meta_list: list[dict[str, Any]],
    output_dir: str | Path,
    stem: str = "rules",
) -> tuple[Path, Path]:
    """
    FAISS 인덱스와 메타데이터를 저장.
    Windows에서 한글 등 유니코드 경로 시 faiss.write_index 오류를 피하기 위해,
    임시 경로(ASCII)에 먼저 쓰고 최종 경로로 복사한다.

    Returns:
        (index_path, meta_path)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    idx_path = _index_path_from_base(output_dir, stem)
    meta_path = _meta_path_from_base(output_dir, stem)

    # FAISS C++ 백엔드는 Windows에서 유니코드 경로를 처리하지 못함
    # → temp(ASCII 경로)에 먼저 저장 후 복사
    with tempfile.TemporaryDirectory() as tmp:
        tmp_idx = Path(tmp) / f"{stem}.index"
        faiss.write_index(index, str(tmp_idx))
        shutil.copy2(tmp_idx, idx_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        for rec in meta_list:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return idx_path, meta_path


def _index_to_gpu_if_available(index: faiss.Index) -> faiss.Index:
    """GPU 사용 가능 시 인덱스를 GPU로 이전하여 검색 속도 향상."""
    try:
        if hasattr(faiss, "get_num_gpus") and faiss.get_num_gpus() > 0:
            res = faiss.StandardGpuResources()
            return faiss.index_cpu_to_gpu(res, 0, index)
    except Exception:
        pass
    return index


def load_index(
    index_path: str | Path,
    meta_path: str | Path | None = None,
    use_gpu: bool = True,
) -> tuple[faiss.Index, list[dict[str, Any]]]:
    """
    FAISS 인덱스와 메타데이터 로드.
    meta_path가 None이면 index_path 기반으로 rules_meta.jsonl 추론.
    Windows에서 유니코드 경로 시 FileIOReader 오류를 피하기 위해,
    인덱스 파일을 temp(ASCII 경로)로 복사한 뒤 읽는다.
    use_gpu=True이고 faiss-gpu 사용 시 인덱스를 GPU로 이전.

    Returns:
        (index, meta_list)
    """
    index_path = Path(index_path)
    # FAISS C++ 백엔드는 Windows에서 유니코드 경로 처리 불가 → temp에 복사 후 읽기
    with tempfile.TemporaryDirectory() as tmp:
        tmp_idx = Path(tmp) / "rules.index"
        shutil.copy2(index_path, tmp_idx)
        index = faiss.read_index(str(tmp_idx))

    if use_gpu:
        index = _index_to_gpu_if_available(index)

    if meta_path is None:
        meta_path = index_path.parent / f"{index_path.stem}_meta.jsonl"
    else:
        meta_path = Path(meta_path)

    meta_list: list[dict[str, Any]] = []
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    meta_list.append(json.loads(line))

    return index, meta_list


def search(
    index: faiss.Index,
    query_embedding: np.ndarray,
    meta_list: list[dict[str, Any]],
    top_k: int = 5,
) -> list[tuple[int, float, dict[str, Any]]]:
    """
    쿼리 임베딩으로 top-k 검색.
    query_embedding: (1 x D) float32, normalized.
    Returns:
        [(idx, score, meta_dict), ...]
    """
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    scores, indices = index.search(query_embedding, min(top_k, index.ntotal))
    results: list[tuple[int, float, dict[str, Any]]] = []
    for i, (idx, score) in enumerate(zip(indices[0], scores[0])):
        if idx < 0:
            continue
        meta = meta_list[idx] if idx < len(meta_list) else {"chunk_id": str(idx)}
        results.append((int(idx), float(score), meta))
    return results


def build_index_from_chunks(
    chunks: list[dict[str, Any]],
    *,
    text_key: str = "text",
    output_dir: str | Path,
    stem: str = "rules",
    batch_size: int = 32,
    progress_callback: Any | None = None,
) -> tuple[Path, Path]:
    """
    Chunk JSONL 레코드에서 임베딩 생성 후 FAISS 인덱스 저장.
    - chunk_id가 없으면 doc_id_article_paragraph_chunk_index로 생성
    - meta_list에는 chunk 전체 정보 저장

    Returns:
        (index_path, meta_path)
    """
    texts = []
    meta_list = []
    for i, c in enumerate(chunks):
        t = c.get(text_key) or ""
        texts.append(t)

        # chunk_id 생성 (Phase 16: section 포함)
        chunk_id = c.get("chunk_id")
        if not chunk_id:
            doc_id = c.get("doc_id", "")
            article = c.get("article", "")
            section = c.get("section", "")
            paragraph = c.get("paragraph", "")
            chunk_index = c.get("chunk_index", i + 1)
            chunk_id = f"{doc_id}_{article}_{section}_{paragraph}_{chunk_index}"

        chunk_meta = c.get("meta") or {}
        # Canonical: physical_page 우선, V2: pages[0]
        page = chunk_meta.get("physical_page")
        if page is None:
            pages = chunk_meta.get("pages") or []
            page = pages[0] if pages else None

        meta_list.append({
            "chunk_id": chunk_id,
            "text": t[:500],
            "full_text": t,
            "meta": chunk_meta,
            "doc_id": c.get("doc_id"),
            "article": c.get("article"),
            "section": c.get("section"),
            "paragraph": c.get("paragraph"),
            "chunk_index": c.get("chunk_index"),
            "page": page,
        })

    # 배치별 임베딩 (진행률 콜백 지원)
    all_embs: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        batch_texts = texts[start:end]
        batch_embs = encode_texts(batch_texts, batch_size=len(batch_texts), normalize=True)
        for row in batch_embs:
            all_embs.append(row.tolist())
        if progress_callback:
            progress_callback(end, len(chunks))

    embeddings = np.array(all_embs, dtype=np.float32)
    index = create_index(embeddings)
    return save_index(index, meta_list, output_dir, stem)
