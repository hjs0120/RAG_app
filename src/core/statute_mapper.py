"""Raw JSONL → Canonical JSON 변환 — 민법 등 일반 법령 (제 N조 형식)."""

from __future__ import annotations

from src.core.base_mapper import BaseStructureMapper
from src.core.rules import RuleMatch, match_article_statute


class StatuteStructureMapper(BaseStructureMapper):
    """
    민법 등 일반 법령용 Mapper.

    조(Article) 패턴: ^제\\s*\\d+\\s*조 (제 1조, 제 274조, ...)
    """

    def _extract_article_no(self, text: str) -> RuleMatch | None:
        """법령 조문: 제 N조 형식."""
        return match_article_statute(text)
