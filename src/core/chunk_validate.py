"""Chunk JSONL 검증 — 비어있지 않음, 길이, chunk_index, Canonical 필드, 원본 대비 누락 여부."""

from __future__ import annotations


def _is_canonical_chunk(c: dict) -> bool:
    """Canonical 형식 Chunk 여부 (chunk_id 또는 meta.structure_path 존재)."""
    if c.get("chunk_id"):
        return True
    meta = c.get("meta") or c.get("metadata") or {}
    return "structure_path" in meta


def validate_chunks(
    chunks: list[dict],
    *,
    max_len: int = 1000,
    check_index_sequential: bool = True,
    check_canonical: bool = True,
) -> tuple[bool, list[str]]:
    """
    Chunk 리스트 검증.
    - chunk text 비어있지 않은지
    - chunk 길이가 max_len 이하인지
    - (article, paragraph)별 chunk_index가 1부터 순차인지 (V2)
    - Canonical Chunk: chunk_id, doc_id, meta.structure_path 필수 확인

    Returns:
        (모두 통과 여부, 메시지 리스트)
    """
    messages: list[str] = []
    all_ok = True

    for i, c in enumerate(chunks):
        text = (c.get("text") or "").strip()
        if not text:
            all_ok = False
            messages.append(f"Chunk {i+1}: text가 비어 있습니다.")
        length = len(text)
        if length > max_len:
            all_ok = False
            messages.append(f"Chunk {i+1}: 길이 {length} > max_len({max_len})")

        if check_canonical and _is_canonical_chunk(c):
            if not c.get("doc_id"):
                all_ok = False
                messages.append(f"Chunk {i+1}: Canonical chunk에 doc_id가 없습니다.")
            if not c.get("chunk_id"):
                all_ok = False
                messages.append(f"Chunk {i+1}: Canonical chunk에 chunk_id가 없습니다.")
            meta = c.get("meta") or c.get("metadata") or {}
            if "structure_path" not in meta:
                all_ok = False
                messages.append(f"Chunk {i+1}: Canonical chunk에 meta.structure_path가 없습니다.")

    if check_index_sequential:
        from itertools import groupby

        # Canonical chunk는 chunk_index 검사 제외
        v2_chunks = [c for c in chunks if not _is_canonical_chunk(c)]
        if v2_chunks:
            key_fn = lambda c: (
                c.get("doc_id"),
                c.get("article"),
                c.get("section"),
                c.get("paragraph"),
            )
            sorted_v2 = sorted(v2_chunks, key=lambda c: (*key_fn(c), c.get("chunk_index", 0)))
            for key, group in groupby(sorted_v2, key=key_fn):
                indices = [c.get("chunk_index") for c in group]
                expected = list(range(1, len(indices) + 1))
                if indices != expected:
                    all_ok = False
                    messages.append(
                        f"doc_id/article/section/paragraph {key}: chunk_index가 1부터 순차가 아님 (got {indices})"
                    )

    if all_ok:
        messages.append("검증 통과: text 비어있지 않음, 길이 제한 준수, chunk_index 순차.")
    return all_ok, messages


def validate_chunk_text_coverage(
    original_records: list[dict],
    chunks: list[dict],
) -> tuple[bool, list[str]]:
    """
    원본 레코드의 전체 텍스트가 chunk에 누락 없이 포함되었는지 간단 검사.
    (공백/정규화 차이로 인해 완전 일치가 아니어도 됨 — 원본 문자 집합이 chunk 합계에 포함되는지 정도)
    """
    messages: list[str] = []
    orig_text = " ".join((r.get("text") or "").strip() for r in original_records).replace(" ", "")
    chunk_text = "".join((c.get("text") or "").replace(" ", "") for c in chunks)
    # 원본에서 공백 제거한 길이 vs chunk 합계에서 공백 제거한 길이 (대략적)
    if len(orig_text) > 0 and len(chunk_text) < len(orig_text) * 0.95:
        messages.append(
            f"원본 대비 텍스트 누락 가능성: 원본(공백제거) {len(orig_text)}자, chunk 합계 {len(chunk_text)}자"
        )
        return False, messages
    messages.append("원본 대비 chunk 텍스트 누락 검사: 통과(대략).")
    return True, messages
