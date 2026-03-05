"""Raw JSONL → Canonical JSON 변환 — 민법 등 일반 법령 (제 N조 형식)."""

from __future__ import annotations

import re

from src.core.base_mapper import BaseStructureMapper
from src.core.rules import RuleMatch, match_article_statute

# 편/장/절 + 제 N조 (article) + 항/호/목. 101. 미포함.
_RE_NEW_SECTION_STATUTE = re.compile(
    r"^(?:\d+\s*편|제\s*\d+\s*[장절]|제\s*\d+\s*조|\d\.\s+[가-힣]|\(\d+\)\s|[(（][가나다라마바사아자차카타파하][)）]\s)"
)


class StatuteStructureMapper(BaseStructureMapper):
    """
    민법 등 일반 법령용 Mapper.

    조(Article) 패턴: ^제\\s*\\d+\\s*조 (제 1조, 제 274조, ...)
    """

    def _extract_article_no(self, text: str) -> RuleMatch | None:
        """법령 조문: 제 N조 형식."""
        return match_article_statute(text)

    def get_section_pattern(self) -> re.Pattern[str]:
        """법령: 제 N조 기준 새 섹션."""
        return _RE_NEW_SECTION_STATUTE
