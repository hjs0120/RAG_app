"""표제목·그림제목 정규식 패턴 — Phase 11."""

from __future__ import annotations

import re
from typing import Pattern


def _table_caption_pattern() -> Pattern:
    """
    표 제목 패턴.
    - 표 1, 표 2, 표 1-1 / 별표 1 / 〈표 1〉, [표 1]
    """
    return re.compile(
        r"^(?:표\s*\d+(?:-\d+)?|별표\s*\d+|[〈\[\(]?\s*표\s*\d+\s*[〉\]\)]?)\s*",
        re.IGNORECASE,
    )


def _figure_caption_pattern() -> Pattern:
    """
    그림 제목 패턴.
    - 그림 1, Figure 1, Fig. 1 / 〈그림 1〉, [그림 1]
    """
    return re.compile(
        r"^(?:그림\s*\d+|Figure\s*\d+|Fig\.\s*\d+|[〈\[\(]?\s*그림\s*\d+\s*[〉\]\)]?)\s*",
        re.IGNORECASE,
    )


def is_table_caption(line: str) -> bool:
    """라인 텍스트가 표 제목 패턴에 맞으면 True."""
    if not line or not line.strip():
        return False
    return _table_caption_pattern().match(line.strip()) is not None


def is_figure_caption(line: str) -> bool:
    """라인 텍스트가 그림 제목 패턴에 맞으면 True."""
    if not line or not line.strip():
        return False
    return _figure_caption_pattern().match(line.strip()) is not None
