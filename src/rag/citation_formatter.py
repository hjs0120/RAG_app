"""Canonical 레코드 출처 문자열 자동 생성."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.canonical_schema import CanonicalRecord


def format_citation_from_meta(meta: dict[str, Any]) -> str:
    """
    FAISS 검색 결과 meta dict에서 출처 문자열 생성.
    Canonical: structure_path 기반. V2: article/section/paragraph.
    출력 예: "p.7, 제 1 장 총칙 > 제 101조"
    """
    chunk_meta = meta.get("meta") or {}
    structure_path = chunk_meta.get("structure_path") or ""
    page = meta.get("page")
    if page is None:
        page = chunk_meta.get("physical_page")
    if page is None:
        pages = chunk_meta.get("pages") or []
        page = pages[0] if pages else ""

    parts: list[str] = []
    if page is not None and page != "":
        parts.append(f"p.{page}")
    if structure_path:
        parts.append(structure_path)
    if parts:
        return ", ".join(parts)

    # V2 fallback: article/section/paragraph
    article = (meta.get("article") or "").strip()
    section = (meta.get("section") or "").strip()
    paragraph = (meta.get("paragraph") or "").strip()
    v2_parts = []
    if article and article != "_":
        v2_parts.append(f"제{article}조" if article.isdigit() else article)
    if section and section not in ("_", article):
        v2_parts.append(section)
    if paragraph and paragraph not in ("0", "_"):
        v2_parts.append(f"({paragraph})항" if paragraph.isdigit() else paragraph)
    if v2_parts:
        return f"p.{page}, " + ", ".join(v2_parts) if page else ", ".join(v2_parts)
    return f"p.{page}" if page else ""


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
