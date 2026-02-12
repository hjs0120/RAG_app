"""정규화 — 공백 정리, 헤더/푸터 제거."""

from __future__ import annotations

import re


def normalize_line(text: str) -> str:
    """
    한 라인 텍스트 공백 정규화 (스텁).

    - 연속 공백을 하나로
    - 앞뒤 공백 제거
    Phase 7에서 헤더/푸터 제거 등 보완 예정.
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    s = re.sub(r"[ \t]+", " ", s)
    return s


def normalize_lines(lines: list[dict]) -> list[dict]:
    """라인 리스트 각 항목의 text에 normalize_line 적용."""
    out = []
    for ln in lines:
        row = dict(ln)
        row["text"] = normalize_line(row.get("text", ""))
        out.append(row)
    return out
