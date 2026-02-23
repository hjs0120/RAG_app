"""Raw JSONL → Canonical JSON 변환 규칙 (해양구조물 규칙)."""

from __future__ import annotations

from typing import Any

from src.core.rules import RuleMatch, classify_line
from src.core.canonical_schema import (
    CanonicalRecord,
    CanonicalSource,
    CanonicalLocation,
    CanonicalStructureItem,
    CanonicalContent,
)


def _rule_match_to_label(matched: RuleMatch) -> str:
    """RuleMatch를 Canonical structure label로 변환."""
    if matched.kind == "chapter":
        return matched.value  # "제 1 장 총칙"
    if matched.kind == "section":
        return matched.value  # "제 1 절 일반사항"
    if matched.kind == "article":
        return f"제 {matched.value}조"
    if matched.kind == "paragraph":
        v = matched.value
        if v.isdigit():
            return f"{v}항"
        if v.startswith("(") and v.endswith(")"):
            return v
        return v
    if matched.kind == "part":
        return matched.value  # "1편"
    return matched.value


def _build_structure(stack: list[tuple[int, str, str]]) -> list[CanonicalStructureItem]:
    """스택을 CanonicalStructureItem 리스트로 변환."""
    return [
        CanonicalStructureItem(level=lev, type=tp, label=lab)
        for lev, tp, lab in stack
    ]


def map_to_canonical(
    raw_blocks: list[dict],
    source_meta: dict[str, Any] | None = None,
    *,
    doc_type: str = "regulation",
    language: str = "ko",
) -> list[CanonicalRecord]:
    """
    Raw JSONL 블록을 CanonicalRecord 리스트로 변환.

    rules.classify_line으로 각 블록 텍스트 분류 후, 상태머신 방식으로
    chapter/section/article/paragraph 계층 스택을 유지하며 CanonicalRecord 생성.

    Args:
        raw_blocks: extract_pdf_raw 추출 결과 (doc_id, block_type, page, text, ...)
        source_meta: { "file_name": "...", "organization": "KR", "version": "2024" } 등
        doc_type: 문서 유형 (기본 "regulation")
        language: 본문 언어 (기본 "ko")

    Returns:
        CanonicalRecord 리스트 (bbox 제외)
    """
    source_meta = source_meta or {}
    file_name = source_meta.get("file_name", "")
    organization = source_meta.get("organization")
    version = source_meta.get("version")

    # 계층 스택: (level, type, label). level 1=chapter, 2=section, 3=article, 4=paragraph
    _LEVEL = {"part": 0, "chapter": 1, "section": 2, "article": 3, "paragraph": 4}
    stack: list[tuple[int, str, str]] = []

    records: list[CanonicalRecord] = []
    doc_id = ""

    for block in raw_blocks:
        doc_id = block.get("doc_id", doc_id) or doc_id
        text = (block.get("text") or "").strip()
        page = block.get("page", 0)
        block_type = block.get("block_type", "text")

        # 표/그림 캡션: doc_type="caption" 또는 structure 없이 content만
        if block_type in ("table_caption", "figure_caption"):
            rec = _make_record(
                doc_id=doc_id,
                doc_type="caption",
                text=text,
                page=page,
                file_name=file_name,
                organization=organization,
                version=version,
                structure=[],
                language=language,
            )
            records.append(rec)
            continue

        # 분류 시도
        matched: RuleMatch | None = classify_line(text) if text else None

        if matched:
            lev = _LEVEL.get(matched.kind, 0)
            label = _rule_match_to_label(matched)
            # 동급 이하 제거 후 push
            while stack and stack[-1][0] >= lev:
                stack.pop()
            stack.append((lev, matched.kind, label))

        # structure: 분류된 경우 스택 기반, 아니면 빈 리스트
        structure_items = _build_structure(stack) if matched or stack else []
        # 분류 불가 블록: structure 생략 (현재 스택 유지하되, 명시적 새 항목 없음)
        if not matched and stack:
            structure_items = _build_structure(stack)
        elif not matched:
            structure_items = []

        rec = _make_record(
            doc_id=doc_id,
            doc_type=doc_type,
            text=text,
            page=page,
            file_name=file_name,
            organization=organization,
            version=version,
            structure=structure_items,
            language=language,
        )
        records.append(rec)

    return records


def _make_record(
    *,
    doc_id: str,
    doc_type: str,
    text: str,
    page: int,
    file_name: str,
    organization: str | None,
    version: str | None,
    structure: list[CanonicalStructureItem],
    language: str,
) -> CanonicalRecord:
    """CanonicalRecord 생성."""
    source = CanonicalSource(file_name=file_name, organization=organization, version=version) if file_name else None
    location = CanonicalLocation(physical_page=int(page)) if page else None
    content = CanonicalContent(text=text, language=language)
    return CanonicalRecord(
        doc_id=doc_id,
        doc_type=doc_type,
        content=content,
        source=source,
        location=location,
        structure=structure,
    )
