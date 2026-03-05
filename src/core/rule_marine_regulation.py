"""Raw JSONL → Canonical JSON 변환 규칙 (해양구조물 규칙).

V5: MarineStructureMapper 위임, 하위 호환용 map_to_canonical 유지.
"""

from __future__ import annotations

from typing import Any

from src.core.canonical_schema import CanonicalRecord
from src.core.marine_mapper import MarineStructureMapper

# 하위 호환: 기존 map_to_canonical 함수 시그니처 유지
_MARINE_MAPPER = MarineStructureMapper()


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
    return _MARINE_MAPPER.map_to_canonical(
        raw_blocks,
        source_meta,
        doc_type=doc_type,
        language=language,
    )
