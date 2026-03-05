"""Raw JSONL → Canonical JSON 변환 — 해양구조물 규칙 (101., 202. 형식)."""

from __future__ import annotations

import re

from src.core.base_mapper import BaseStructureMapper
from src.core.rules import RuleMatch, match_article

# 편/장/절 + 101. (article) + 항/호/목. 제 N조 미포함.
_RE_NEW_SECTION_MARINE = re.compile(
    r"^(?:\d+\s*편|제\s*\d+\s*[장절]|\d{2,}\.\s|\d\.\s+[가-힣]|\(\d+\)\s|[(（][가나다라마바사아자차카타파하][)）]\s)"
)


class MarineStructureMapper(BaseStructureMapper):
    """
    해양구조물 규칙용 Mapper.

    조(Article) 패턴: ^(\\d{2,})\\. (101., 202., ...)
    """

    def _extract_article_no(self, text: str) -> RuleMatch | None:
        """해양규칙 조문: 101., 202. 형식."""
        return match_article(text)

    def get_section_pattern(self) -> re.Pattern[str]:
        """해양규칙: 101. 기준 새 섹션."""
        return _RE_NEW_SECTION_MARINE
