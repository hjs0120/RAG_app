"""
표/그림 구간 감지 — 표제목·그림제목만 남기고 본문(표 셀, 그림 설명) 제외. Phase 11.
"""

from __future__ import annotations

from typing import Literal

from src.core.rules import classify_line
from src.core.table_figure_rules import is_table_caption, is_figure_caption


_State = Literal["body", "in_table_body", "in_figure_body"]


def _is_section_or_chapter(line: dict) -> bool:
    """장/절 헤더(제 n 장, 제 n 절)이면 True. 표/그림 본문 구간 종료 판단용."""
    text = (line.get("text") or "").strip()
    if not text:
        return False
    r = classify_line(text)
    return r is not None and r.kind in ("chapter", "section")


def apply_table_figure_filter(
    lines: list[dict],
    *,
    table_caption_only: bool = True,
    figure_caption_only: bool = True,
) -> list[dict]:
    """
    표 제목만 / 그림 제목만 남기고, 표 본문·그림 본문 구간 라인은 제외한다.

    - 표제목 다음부터 다음 표제목/그림제목/장·절 헤더가 나올 때까지 → 표 본문(제외)
    - 그림제목 다음부터 다음 그림제목/표제목/장·절 헤더가 나올 때까지 → 그림 본문(제외)
    - 남기는 라인에는 block_type "table_caption" / "figure_caption" 메타를 붙인다.

    Args:
        lines: text, bbox, page, line_no 를 갖는 라인 리스트
        table_caption_only: True면 표 본문 제외, 표제목 라인만 유지
        figure_caption_only: True면 그림 본문 제외, 그림제목 라인만 유지

    Returns:
        필터링된 라인 리스트. 표/그림 제목 라인에는 "block_type" 키가 추가됨.
    """
    if not lines:
        return []
    if not table_caption_only and not figure_caption_only:
        return list(lines)

    out: list[dict] = []
    state: _State = "body"

    for line in lines:
        row = dict(line)
        text = (row.get("text") or "").strip()
        is_table = is_table_caption(text)
        is_figure = is_figure_caption(text)
        is_section = _is_section_or_chapter(row)

        if state == "body":
            if is_table and table_caption_only:
                row["block_type"] = "table_caption"
                out.append(row)
                state = "in_table_body"
            elif is_figure and figure_caption_only:
                row["block_type"] = "figure_caption"
                out.append(row)
                state = "in_figure_body"
            else:
                out.append(row)
        elif state == "in_table_body":
            if is_table:
                row["block_type"] = "table_caption"
                out.append(row)
            elif is_figure and figure_caption_only:
                row["block_type"] = "figure_caption"
                out.append(row)
                state = "in_figure_body"
            elif is_section:
                out.append(row)
                state = "body"
            else:
                pass  # 표 본문 → 제외
        else:  # in_figure_body
            if is_figure:
                row["block_type"] = "figure_caption"
                out.append(row)
            elif is_table and table_caption_only:
                row["block_type"] = "table_caption"
                out.append(row)
                state = "in_table_body"
            elif is_section:
                out.append(row)
                state = "body"
            else:
                pass  # 그림 본문 → 제외

    return out
