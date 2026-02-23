"""조문/섹션 단위 Chunk 재조합 — 그룹핑, 점수 합산, 컨텍스트 제한."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# Phase 17 정책
FAISS_TOP_K = 10  # 넉넉히 검색
MAX_GROUPS = 2  # 상위 그룹 1~2개
CHUNKS_PER_GROUP = 4  # 그룹당 chunk 3~6개
MAX_CONTEXT_CHARS = 3200  # 2500~3500 tokens ≈ ~3200자


def _group_key(meta: dict[str, Any]) -> str:
    """
    그룹핑 키 생성 (우선순위):
    Canonical: structure_path > doc_id + physical_page
    V2: article > section > doc_id + page
    """
    doc_id = (meta.get("doc_id") or "").strip()
    chunk_meta = meta.get("meta") or {}

    # Canonical: structure_path 기반
    structure_path = (chunk_meta.get("structure_path") or "").strip()
    if structure_path:
        return f"{doc_id}|canon|{structure_path}"

    # V2: article/section 기반
    article = (meta.get("article") or "").strip()
    section = (meta.get("section") or "").strip()
    page = ""
    pages = chunk_meta.get("pages") or []
    physical_page = chunk_meta.get("physical_page")
    if physical_page is not None:
        page = str(physical_page)
    elif pages:
        page = str(pages[0])

    if article and article != "_":
        if section and section != "_":
            return f"{doc_id}|{article}|{section}"
        return f"{doc_id}|{article}|"
    if section and section != "_":
        return f"{doc_id}|_|{section}"
    return f"{doc_id}|{page}"


def assemble_chunks(
    results: list[tuple[int, float, dict[str, Any]]],
    *,
    top_groups: int = MAX_GROUPS,
    chunks_per_group: int = CHUNKS_PER_GROUP,
    max_context_chars: int = MAX_CONTEXT_CHARS,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """
    FAISS 검색 결과를 조문/섹션 단위로 그룹핑하여 재조합.

    Args:
        results: [(idx, score, meta), ...] — faiss search 결과
        top_groups: 선택할 상위 그룹 수 (1~2)
        chunks_per_group: 그룹당 최대 chunk 수 (3~6)
        max_context_chars: 최종 컨텍스트 문자 수 제한

    Returns:
        (assembled_context, selected_chunks, debug_info)
    """
    if not results:
        return "", [], {"group_scores": {}, "selected_groups": []}

    # 그룹별 점수 합산
    groups: dict[str, list[tuple[int, float, dict]]] = defaultdict(list)
    for idx, score, meta in results:
        key = _group_key(meta)
        groups[key].append((idx, score, meta))

    group_scores: dict[str, float] = {}
    for key, items in groups.items():
        group_scores[key] = sum(s for _, s, _ in items)

    # 점수 높은 순 정렬
    sorted_keys = sorted(group_scores.keys(), key=lambda k: group_scores[k], reverse=True)
    selected_keys = sorted_keys[:top_groups]

    # 선택된 그룹에서 chunk 수집 (점수 순)
    selected: list[tuple[int, float, dict]] = []
    for key in selected_keys:
        items = sorted(groups[key], key=lambda x: x[1], reverse=True)
        selected.extend(items[:chunks_per_group])

    # 전체 점수 순으로 정렬 후 chunks_per_group * top_groups 제한
    selected = sorted(selected, key=lambda x: x[1], reverse=True)
    limit = min(len(selected), top_groups * chunks_per_group)
    selected = selected[:limit]

    # 컨텍스트 조립 (원문 순서 유지를 위해 doc_id, page, chunk_index 등으로 정렬)
    def sort_key(item: tuple[int, float, dict]) -> tuple:
        _, _, m = item
        chunk_meta = m.get("meta") or {}
        page = chunk_meta.get("physical_page")
        if page is None:
            pages = chunk_meta.get("pages") or [0]
            page = pages[0] if pages else 0
        return (m.get("doc_id", ""), page, m.get("chunk_index", 0))

    selected_sorted = sorted(selected, key=sort_key)

    parts: list[str] = []
    total_chars = 0
    selected_chunks: list[dict[str, Any]] = []

    for idx, score, meta in selected_sorted:
        # full_text 있으면 사용, 없으면 text (하위 호환)
        text = meta.get("full_text") or meta.get("text") or ""
        if not text:
            continue
        if total_chars + len(text) > max_context_chars:
            # 남은 여유만큼 잘라서 추가
            remain = max_context_chars - total_chars
            if remain > 100:
                text = text[:remain] + "..."
                parts.append(text)
                selected_chunks.append({"idx": idx, "score": score, "meta": meta})
            break
        parts.append(text)
        selected_chunks.append({"idx": idx, "score": score, "meta": meta})
        total_chars += len(text)

    assembled = "\n\n".join(parts)
    debug_info = {
        "group_scores": group_scores,
        "selected_groups": selected_keys,
        "total_chunks_selected": len(selected_chunks),
    }
    return assembled, selected_chunks, debug_info
