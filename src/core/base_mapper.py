"""Raw JSONL → Canonical JSON 변환 공통 베이스 (V5 전략 패턴)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from src.core.rules import RuleMatch, match_chapter, match_paragraph, match_part, match_section
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
        return matched.value
    if matched.kind == "section":
        return matched.value
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
        return matched.value
    return matched.value


def _build_structure(stack: list[tuple[int, str, str]]) -> list[CanonicalStructureItem]:
    """스택을 CanonicalStructureItem 리스트로 변환."""
    return [
        CanonicalStructureItem(level=lev, type=tp, label=lab)
        for lev, tp, lab in stack
    ]


class BaseStructureMapper(ABC):
    """
    Raw JSONL → Canonical JSON 변환 공통 베이스.

    문서별 조(Article) 패턴만 _extract_article_no로 구현하고,
    편/장/절/항/호/목은 rules.py 공통 패턴 사용.
    """

    _LEVEL = {"part": 0, "chapter": 1, "section": 2, "article": 3, "paragraph": 4}

    @abstractmethod
    def _extract_article_no(self, text: str) -> RuleMatch | None:
        """
        조(Article) 번호 추출 — 문서별로 다른 패턴.

        해양규칙: ^(\\d{2,})\\. (101., 202.)
        법령: ^제\\s*\\d+\\s*조 (제 1조, 제 274조)
        """
        ...

    @abstractmethod
    def get_section_pattern(self) -> re.Pattern[str]:
        """
        line_rebuild에서 새 섹션/항 시작으로 인식할 정규식.

        문서 타입별로 조(article) 패턴만 다르고, 편/장/절/항/호/목은 공통.
        """
        ...

    def _classify_line(self, text: str) -> RuleMatch | None:
        """part → chapter → section → article(자식 구현) → paragraph 순서로 분류."""
        for fn in (match_part, match_chapter, match_section):
            r = fn(text)
            if r:
                return r
        r = self._extract_article_no(text)
        if r:
            return r
        return match_paragraph(text)

    def check_compatibility(
        self, raw_blocks: list[dict], max_pages: int = 5
    ) -> tuple[bool, int]:
        """
        문서 앞부분 Raw 블록에서 매퍼 핵심 패턴(조/항) 발견 여부 검사.

        Args:
            raw_blocks: Raw JSONL 블록 리스트
            max_pages: 검사 대상 최대 페이지 수 (기본 5)

        Returns:
            (호환 여부, 발견된 패턴 수)
        """
        count = 0
        for block in raw_blocks:
            page = block.get("page", 0)
            if page > max_pages:
                break
            text = (block.get("text") or "").strip()
            if not text:
                continue
            if self._extract_article_no(text) is not None:
                count += 1
        return (count > 0, count)

    def map_to_canonical(
        self,
        raw_blocks: list[dict],
        source_meta: dict[str, Any] | None = None,
        *,
        doc_type: str = "regulation",
        language: str = "ko",
    ) -> list[CanonicalRecord]:
        """
        Raw JSONL 블록을 CanonicalRecord 리스트로 변환.

        Args:
            raw_blocks: extract_pdf_raw 추출 결과
            source_meta: file_name, organization, version 등
            doc_type: 문서 유형
            language: 본문 언어

        Returns:
            CanonicalRecord 리스트
        """
        source_meta = source_meta or {}
        file_name = source_meta.get("file_name", "")
        organization = source_meta.get("organization")
        version = source_meta.get("version")

        stack: list[tuple[int, str, str]] = []
        records: list[CanonicalRecord] = []
        doc_id = ""

        for block in raw_blocks:
            doc_id = block.get("doc_id", doc_id) or doc_id
            text = (block.get("text") or "").strip()
            page = block.get("page", 0)
            block_type = block.get("block_type", "text")

            if block_type in ("table_caption", "figure_caption"):
                rec = self._make_record(
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

            matched: RuleMatch | None = self._classify_line(text) if text else None

            if matched:
                lev = self._LEVEL.get(matched.kind, 0)
                label = _rule_match_to_label(matched)
                while stack and stack[-1][0] >= lev:
                    stack.pop()
                stack.append((lev, matched.kind, label))

            structure_items = _build_structure(stack) if matched or stack else []
            if not matched and stack:
                structure_items = _build_structure(stack)
            elif not matched:
                structure_items = []

            rec = self._make_record(
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
        self,
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
        source = (
            CanonicalSource(
                file_name=file_name,
                organization=organization,
                version=version,
            )
            if file_name
            else None
        )
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
