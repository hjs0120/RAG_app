"""Canonical 레코드 출처 문자열 자동 생성."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.canonical_schema import CanonicalRecord


def format_citation(record: "CanonicalRecord") -> str:
    """
    CanonicalRecord에서 출처 문자열 생성.
    출력 예: "p.7, 제 1 장 총칙 > 제 101조"
    structure 없을 경우: "p.7" 또는 "p.7" (location만 있을 때)
    location도 없으면: "" 또는 최소한의 정보
    """
    parts: list[str] = []

    # 페이지
    if record.location and record.location.physical_page is not None:
        parts.append(f"p.{record.location.physical_page}")

    # 구조 경로 (structure를 " > "로 연결)
    if record.structure:
        path_str = " > ".join(s.label for s in record.structure)
        parts.append(path_str)

    return ", ".join(parts) if parts else ""
