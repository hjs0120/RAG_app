"""DB Manager — 인덱스 로드/저장, 증분 추가, Chunk 삭제, 재구성."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from src.core.embedding_bge import encode_texts
from src.core.faiss_index import (
    create_index,
    load_index as _faiss_load_index,
    save_index as _faiss_save_index,
)


def load_index(
    index_path: str | Path,
    meta_path: str | Path | None = None,
    use_gpu: bool = True,
) -> tuple[Any, list[dict[str, Any]]]:
    """
    FAISS 인덱스와 메타데이터 로드.

    Args:
        index_path: .index 파일 경로
        meta_path: _meta.jsonl 파일 경로. None이면 index_path 기반으로 추론
        use_gpu: FAISS GPU 사용 여부

    Returns:
        (faiss_index, meta_list)
    """
    return _faiss_load_index(index_path, meta_path=meta_path, use_gpu=use_gpu)


def save_index(
    index: Any,
    meta_list: list[dict[str, Any]],
    index_path: str | Path,
    meta_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """
    FAISS 인덱스와 메타데이터 저장.

    Args:
        index: faiss.Index
        meta_list: 벡터별 메타데이터 (doc_id, section, article, page, chunk_id, full_text 등)
        index_path: .index 저장 경로
        meta_path: _meta.jsonl 저장 경로. None이면 index_path 기반으로 추론

    Returns:
        (index_path, meta_path)
    """
    index_path = Path(index_path)
    if meta_path is None:
        meta_path = index_path.parent / f"{index_path.stem}_meta.jsonl"
    else:
        meta_path = Path(meta_path)

    output_dir = index_path.parent
    stem = index_path.stem
    return _faiss_save_index(index, meta_list, output_dir, stem)


def _chunk_to_meta(c: dict[str, Any], text: str, i: int) -> dict[str, Any]:
    """Chunk dict를 FAISS meta 형식으로 변환."""
    chunk_id = c.get("chunk_id")
    if not chunk_id:
        doc_id = c.get("doc_id", "")
        article = c.get("article", "")
        section = c.get("section", "")
        paragraph = c.get("paragraph", "")
        chunk_index = c.get("chunk_index", i + 1)
        chunk_id = f"{doc_id}_{article}_{section}_{paragraph}_{chunk_index}"

    chunk_meta = c.get("meta") or {}
    pages = chunk_meta.get("pages") or []
    page = pages[0] if pages else None

    return {
        "chunk_id": chunk_id,
        "text": text[:500],
        "full_text": text,
        "meta": chunk_meta,
        "doc_id": c.get("doc_id"),
        "article": c.get("article"),
        "section": c.get("section"),
        "paragraph": c.get("paragraph"),
        "chunk_index": c.get("chunk_index"),
        "page": page,
    }


def append_chunks(
    chunk_list: list[dict[str, Any]],
    index_path: str | Path,
    meta_path: str | Path | None = None,
    *,
    text_key: str = "text",
    batch_size: int = 32,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[Path, Path]:
    """
    기존 인덱스에 새 chunk를 증분 추가.

    기존 index + meta 로드 → 새 chunk 임베딩 생성 → add → 저장.

    Args:
        chunk_list: Chunk dict 리스트 (text, chunk_id, doc_id, article, section 등)
        index_path: 기존 .index 파일 경로
        meta_path: 기존 _meta.jsonl 경로. None이면 자동 추론
        text_key: 텍스트 필드 키 (기본 "text")
        batch_size: 임베딩 배치 크기
        progress_callback: (current, total) 호출

    Returns:
        (index_path, meta_path)

    Raises:
        FileNotFoundError: index 또는 meta 파일 없음
    """
    index_path = Path(index_path)
    if meta_path is None:
        meta_path = index_path.parent / f"{index_path.stem}_meta.jsonl"
    else:
        meta_path = Path(meta_path)

    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"인덱스가 없습니다. index={index_path}, meta={meta_path}\n"
            "먼저 임베딩 탭에서 FAISS를 생성하세요."
        )

    index, meta_list = _faiss_load_index(index_path, meta_path, use_gpu=False)

    texts = []
    new_meta_list = []
    for i, c in enumerate(chunk_list):
        t = c.get(text_key) or ""
        texts.append(t)
        new_meta_list.append(_chunk_to_meta(c, t, i))

    if not texts:
        return index_path, meta_path

    embeddings = encode_texts(texts, batch_size=batch_size, normalize=True)
    index.add(np.asarray(embeddings, dtype=np.float32))

    for i, nm in enumerate(new_meta_list):
        meta_list.append(nm)
        if progress_callback:
            progress_callback(i + 1, len(new_meta_list))

    return save_index(index, meta_list, index_path, meta_path)


def remove_chunks(
    chunk_ids: list[str],
    index_path: str | Path,
    meta_path: str | Path | None = None,
    *,
    batch_size: int = 32,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[Path, Path]:
    """
    지정 chunk_id들을 인덱스에서 제거 (제외 후 재구성).

    FAISS IndexFlatIP는 개별 벡터 삭제를 지원하지 않으므로,
    제거 대상 제외 → 새 index 재구성 → 저장.

    Args:
        chunk_ids: 제거할 chunk_id 리스트
        index_path: .index 파일 경로
        meta_path: _meta.jsonl 경로. None이면 자동 추론
        batch_size: 재임베딩 배치 크기
        progress_callback: (current, total) 호출

    Returns:
        (index_path, meta_path)
    """
    index_path = Path(index_path)
    if meta_path is None:
        meta_path = index_path.parent / f"{index_path.stem}_meta.jsonl"
    else:
        meta_path = Path(meta_path)

    chunk_id_set = set(chunk_ids)
    index, meta_list = _faiss_load_index(index_path, meta_path, use_gpu=False)

    filtered_meta = [m for m in meta_list if m.get("chunk_id") not in chunk_id_set]
    return rebuild_index(
        filtered_meta,
        index_path,
        meta_path,
        batch_size=batch_size,
        progress_callback=progress_callback,
    )


def rebuild_index(
    meta_list: list[dict[str, Any]],
    index_path: str | Path,
    meta_path: str | Path | None = None,
    *,
    batch_size: int = 32,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[Path, Path]:
    """
    meta_list만 있을 때 전체 인덱스 재구성.

    full_text로 재임베딩 → 새 index 생성 → 저장.
    meta에 full_text가 없으면 text 사용.

    Args:
        meta_list: 벡터 메타 리스트 (full_text 또는 text 필수)
        index_path: 저장할 .index 경로
        meta_path: 저장할 _meta.jsonl 경로. None이면 자동 추론
        batch_size: 임베딩 배치 크기
        progress_callback: (current, total) 호출

    Returns:
        (index_path, meta_path)
    """
    index_path = Path(index_path)
    if meta_path is None:
        meta_path = index_path.parent / f"{index_path.stem}_meta.jsonl"
    else:
        meta_path = Path(meta_path)

    if not meta_list:
        raise ValueError("meta_list가 비어 있습니다.")

    texts = []
    for m in meta_list:
        t = m.get("full_text") or m.get("text") or ""
        texts.append(t)

    all_embs: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        batch = texts[start:end]
        embs = encode_texts(batch, batch_size=len(batch), normalize=True)
        for row in embs:
            all_embs.append(row)
        if progress_callback:
            progress_callback(end, len(texts))

    embeddings = np.array(all_embs, dtype=np.float32)
    index = create_index(embeddings)
    return save_index(index, meta_list, index_path, meta_path)
