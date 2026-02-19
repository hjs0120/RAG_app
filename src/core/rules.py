"""정규식 규칙 정의 — chapter, section, article, paragraph."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


# 목(가나다…) 한글 한 글자
_목_문자 = "가나다라마바사아자차카타파하"


@dataclass
class RuleMatch:
    """규칙 매칭 결과."""
    kind: str  # "chapter" | "section" | "article" | "paragraph"
    value: str  # 표시용 값 (예: "제 1 장 총칙", "101", "1")
    full_text: str  # 매칭된 전체 라인 텍스트(앞부분)
    article_section: str | None = None  # article인 경우 "101. 적용"에서 "적용" 추출


def _chapter_pattern() -> Pattern:
    """제 n 장 … (예: 제 1 장 총칙)."""
    return re.compile(r"^제\s*(\d+)\s*장\s*(.*)$", re.IGNORECASE)


def _section_pattern() -> Pattern:
    """제 n 절 … (예: 제 1 절 일반사항)."""
    return re.compile(r"^제\s*(\d+)\s*절\s*(.*)$", re.IGNORECASE)


def _article_pattern() -> Pattern:
    """조문 번호 101., 202. 등 (2자리 이상 숫자 + 점)."""
    return re.compile(r"^(\d{2,})\.\s*(.*)$")


def _paragraph_item_pattern() -> Pattern:
    """항: 1. 2. (숫자 한 자리 + 점 + 공백)."""
    return re.compile(r"^([1-9])\.\s+(.*)$")


def _paragraph_sub_item_pattern() -> Pattern:
    """호: (1) (2)."""
    return re.compile(r"^\((\d+)\)\s*(.*)$")


def _paragraph_sub_sub_pattern() -> Pattern:
    """목: (가) (나) …."""
    return re.compile(r"^([(（]" + f"[{_목_문자}]" + r"[)）])\s*(.*)$")


def match_chapter(line: str) -> RuleMatch | None:
    """라인이 장(chapter) 패턴이면 RuleMatch 반환."""
    m = _chapter_pattern().match(line.strip())
    if not m:
        return None
    num, rest = m.group(1), m.group(2)
    label = f"제 {num} 장 {rest.strip()}" if rest.strip() else f"제 {num} 장"
    return RuleMatch(kind="chapter", value=label, full_text=line.strip())


def match_section(line: str) -> RuleMatch | None:
    """라인이 절(section) 패턴이면 RuleMatch 반환."""
    m = _section_pattern().match(line.strip())
    if not m:
        return None
    num, rest = m.group(1), m.group(2)
    label = f"제 {num} 절 {rest.strip()}" if rest.strip() else f"제 {num} 절"
    return RuleMatch(kind="section", value=label, full_text=line.strip())


def match_article(line: str) -> RuleMatch | None:
    """라인이 조문(article) 패턴이면 RuleMatch 반환. 2자리 이상 숫자.
    '101. 적용', '101. 하중' 등에서 절 이름(article_section) 추출.
    """
    m = _article_pattern().match(line.strip())
    if not m:
        return None
    num, rest = m.group(1), m.group(2)
    section_name = rest.strip() if rest else None
    return RuleMatch(
        kind="article",
        value=num,
        full_text=line.strip(),
        article_section=section_name or None,
    )


def match_paragraph(line: str) -> RuleMatch | None:
    """라인이 항/호/목(paragraph) 패턴이면 RuleMatch 반환."""
    s = line.strip()
    m = _paragraph_item_pattern().match(s)
    if m:
        return RuleMatch(kind="paragraph", value=m.group(1), full_text=s)
    m = _paragraph_sub_item_pattern().match(s)
    if m:
        return RuleMatch(kind="paragraph", value=f"({m.group(1)})", full_text=s)  # 호
    m = _paragraph_sub_sub_pattern().match(s)
    if m:
        return RuleMatch(kind="paragraph", value=m.group(1), full_text=s)
    return None


def classify_line(line: str) -> RuleMatch | None:
    """
    라인을 순서대로 검사해 chapter → section → article → paragraph 중
    첫 번째로 매칭되는 규칙을 반환. 매칭 없으면 None.
    """
    r = match_chapter(line)
    if r:
        return r
    r = match_section(line)
    if r:
        return r
    r = match_article(line)
    if r:
        return r
    r = match_paragraph(line)
    if r:
        return r
    return None
