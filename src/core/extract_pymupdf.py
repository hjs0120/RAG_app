"""PyMuPDF 기반 페이지별 라인 추출."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import fitz  # PyMuPDF

from src.core.toc_detector import apply_toc_filter

# PyMuPDF span flags (bit 4 = bold)
_RE_STRUCTURAL_HEADER = re.compile(r"^제\s*\d+\s*[장절]")
# 장/절 제목 조각 (총칙, 일반사항, 정의 등) — 상단 여백에서도 보존
_TITLE_FRAGMENTS = frozenset(
    {"총칙", "일반사항", "정의", "적용", "범위", "목적", "용어"}
)
_TEXT_FONT_BOLD = getattr(fitz, "TEXT_FONT_BOLD", 16)


def extract_lines(
    pdf_path: str | Path,
    *,
    after_toc: bool = True,
    exclude_header_footer: bool = True,
    header_footer_margin_ratio: float = 0.08,
    progress_callback: Callable[[int, int], None] | None = None,
    **kwargs: Any,
) -> list[dict]:
    """
    PDF에서 페이지별 레이아웃 기반 라인을 추출한다.

    각 라인은 text, bbox, page, line_no 를 갖는다.
    after_toc는 Phase 4에서 적용하며, 현재는 전체 반환.

    Args:
        pdf_path: PDF 파일 경로
        after_toc: True면 차례(목차) 구간 이후부터만 반환 (Phase 4에서 적용)
        exclude_header_footer: True면 페이지 상/하단 여백 영역(머릿말/꼬리말) 라인 제외
        header_footer_margin_ratio: 상·하단에서 이 비율만큼(기본 8%) 제외. 장/절 헤더는 항상 포함
        progress_callback: (current_page_1based, total_pages) 호출
        **kwargs: 추후 옵션 (y_tolerance, hyphen_merge 등)

    Returns:
        라인 딕셔너리 리스트. 예: [{"text": "...", "bbox": [x0,y0,x1,y1], "page": 1, "line_no": 1}, ...]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        return []

    lines_out: list[dict] = []
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    try:
        for page_index in range(total_pages):
            page = doc[page_index]
            page_no = page_index + 1  # 1-based

            if progress_callback is not None:
                progress_callback(page_no, total_pages)

            block_dict = page.get_text("dict")
            blocks = block_dict.get("blocks") or []

            page_height = page.rect.height
            top_cut = page_height * header_footer_margin_ratio
            bottom_cut = page_height * (1.0 - header_footer_margin_ratio)

            line_no = 0
            for block in blocks:
                for line in block.get("lines") or []:
                    parts = []
                    segments: list[dict[str, Any]] = []
                    for span in line.get("spans") or []:
                        s_text = span.get("text", "")
                        parts.append(s_text)
                        flags = span.get("flags", 0)
                        font = span.get("font", "") or ""
                        is_bold = bool(
                            (flags & _TEXT_FONT_BOLD)
                            or "bold" in font.lower()
                            or "Bold" in font
                        )
                        segments.append({"text": s_text, "bold": is_bold})
                    text = "".join(parts).strip()
                    if not text:
                        continue
                    bbox = list(line["bbox"])
                    if exclude_header_footer:
                        # 장/절 헤더(제 N 장, 제 N 절) 및 제목 조각(총칙, 일반사항 등)은 여백에서도 보존
                        if not _RE_STRUCTURAL_HEADER.search(text):
                            if text.strip() in _TITLE_FRAGMENTS:
                                pass  # 제목 조각도 보존
                            else:
                                y0, y1 = bbox[1], bbox[3]
                                if y1 <= top_cut or y0 >= bottom_cut:
                                    continue
                    line_no += 1
                    lines_out.append({
                        "text": text,
                        "bbox": bbox,
                        "page": page_no,
                        "line_no": line_no,
                        "segments": segments,
                    })
    finally:
        doc.close()

    if after_toc and lines_out:
        lines_out = apply_toc_filter(lines_out, after_toc=True)
    return lines_out
