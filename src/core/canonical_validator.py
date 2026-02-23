"""Canonical JSON 스키마 검증 유틸."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canonical_schema import CanonicalRecord


def validate(records: list) -> list[tuple[int, str]]:
    """
    CanonicalRecord 리스트 검증.
    Returns:
        유효하지 않은 레코드의 (인덱스, 오류메시지) 리스트.
        빈 리스트면 모두 유효.
    """
    errors: list[tuple[int, str]] = []

    for i, rec in enumerate(records):
        # CanonicalRecord 인스턴스인 경우
        if hasattr(rec, "doc_id") and hasattr(rec, "content"):
            err = _validate_record(rec)
        # dict인 경우
        elif isinstance(rec, dict):
            err = _validate_dict(rec)
        else:
            errors.append((i, f"Invalid record type: {type(rec).__name__}"))
            continue

        if err:
            errors.append((i, err))

    return errors


def _validate_record(rec: "CanonicalRecord") -> str | None:
    """CanonicalRecord 인스턴스 검증."""
    if not rec.doc_id or not rec.doc_id.strip():
        return "doc_id is required and must be non-empty"
    if not rec.doc_type or not rec.doc_type.strip():
        return "doc_type is required and must be non-empty"
    if not rec.content or not rec.content.text.strip():
        return "content.text is required and must be non-empty"

    # structure level 순서 검증
    if rec.structure:
        prev_level = -1
        for item in rec.structure:
            if item.level <= prev_level:
                return (
                    f"structure level must be strictly increasing: "
                    f"got level {item.level} after {prev_level}"
                )
            prev_level = item.level

    return None


def _validate_dict(d: dict) -> str | None:
    """dict 레코드 검증 (필수 필드만)."""
    doc_id = d.get("doc_id")
    if doc_id is None:
        return "doc_id is required"
    if not str(doc_id).strip():
        return "doc_id must be non-empty"

    doc_type = d.get("doc_type")
    if doc_type is None:
        return "doc_type is required"
    if not str(doc_type).strip():
        return "doc_type must be non-empty"

    content = d.get("content")
    if content is None:
        return "content is required"
    if not isinstance(content, dict):
        return "content must be an object"
    text = content.get("text")
    if text is None:
        return "content.text is required"
    if not str(text).strip():
        return "content.text must be non-empty"

    # structure level 순서 검증
    structure = d.get("structure") or []
    if structure:
        prev_level = -1
        for item in structure:
            if not isinstance(item, dict):
                return "structure item must be an object"
            level = item.get("level")
            if level is None:
                return "structure item must have level"
            try:
                level = int(level)
            except (TypeError, ValueError):
                return "structure item level must be integer"
            if level <= prev_level:
                return (
                    f"structure level must be strictly increasing: "
                    f"got level {level} after {prev_level}"
                )
            prev_level = level

    return None
