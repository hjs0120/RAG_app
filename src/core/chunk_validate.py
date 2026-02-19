"""Chunk JSONL 검증 — 비어있지 않음, 길이, chunk_index, 원본 대비 누락 여부."""

from __future__ import annotations


def validate_chunks(
    chunks: list[dict],
    *,
    max_len: int = 1000,
    check_index_sequential: bool = True,
) -> tuple[bool, list[str]]:
    """
    Chunk 리스트 검증.
    - chunk text 비어있지 않은지
    - chunk 길이가 max_len 이하인지
    - (article, paragraph)별 chunk_index가 1부터 순차인지
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

    if check_index_sequential:
        from itertools import groupby
        # Phase 16: section 포함하여 (doc_id, article, section, paragraph)별 chunk_index 검사
        key_fn = lambda c: (
            c.get("doc_id"),
            c.get("article"),
            c.get("section"),
            c.get("paragraph"),
        )
        sorted_chunks = sorted(chunks, key=lambda c: (*key_fn(c), c.get("chunk_index", 0)))
        for key, group in groupby(sorted_chunks, key=key_fn):
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
