"""doc_type에 따른 Mapper 인스턴스 반환."""

from __future__ import annotations

from src.core.base_mapper import BaseStructureMapper
from src.core.marine_mapper import MarineStructureMapper
from src.core.statute_mapper import StatuteStructureMapper

_MARINE = MarineStructureMapper()
_STATUTE = StatuteStructureMapper()


def get_mapper(doc_type: str) -> BaseStructureMapper:
    """
    doc_type에 따라 적절한 Mapper 인스턴스 반환.

    Args:
        doc_type: "marine" | "regulation" → MarineStructureMapper
                  "statute" | "law" → StatuteStructureMapper
                  그 외 → MarineStructureMapper (기본값)

    Returns:
        BaseStructureMapper 인스턴스
    """
    normalized = (doc_type or "").strip().lower()
    if normalized in ("statute", "law"):
        return _STATUTE
    return _MARINE
