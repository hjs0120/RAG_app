"""Raw JSONL 스키마 검증."""

from __future__ import annotations


def validate(blocks: list) -> list[tuple[int, str]]:
    """
    Raw 블록 리스트 검증.

    필수 필드: doc_id, source_type, block_id, block_type, text

    Returns:
        유효하지 않은 블록의 (인덱스, 오류메시지) 리스트.
        빈 리스트면 모두 유효.
    """
    errors: list[tuple[int, str]] = []

    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            errors.append((i, f"Invalid block type: {type(block).__name__}"))
            continue

        if not block.get("doc_id"):
            errors.append((i, "doc_id is required"))
            continue
        if not str(block.get("doc_id", "")).strip():
            errors.append((i, "doc_id must be non-empty"))
            continue

        if block.get("source_type") is None:
            errors.append((i, "source_type is required"))
            continue
        if not str(block.get("source_type", "")).strip():
            errors.append((i, "source_type must be non-empty"))
            continue

        if block.get("block_id") is None:
            errors.append((i, "block_id is required"))
            continue

        if block.get("block_type") is None:
            errors.append((i, "block_type is required"))
            continue
        if not str(block.get("block_type", "")).strip():
            errors.append((i, "block_type must be non-empty"))
            continue

        if block.get("text") is None:
            errors.append((i, "text is required"))
            continue
        if not isinstance(block.get("text"), str):
            errors.append((i, "text must be string"))
            continue

    return errors
