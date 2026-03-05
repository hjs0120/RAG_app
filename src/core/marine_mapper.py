"""Raw JSONL → Canonical JSON 변환 — 해양구조물 규칙 (101., 202. 형식)."""

from __future__ import annotations

from src.core.base_mapper import BaseStructureMapper
from src.core.rules import RuleMatch, match_article


class MarineStructureMapper(BaseStructureMapper):
    """
    해양구조물 규칙용 Mapper.

    조(Article) 패턴: ^(\\d{2,})\\. (101., 202., ...)
    """

    def _extract_article_no(self, text: str) -> RuleMatch | None:
        """해양규칙 조문: 101., 202. 형식."""
        return match_article(text)
