"""PDF → Raw JSONL 변환 — 블록 단위 추출 (V3)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import fitz  # PyMuPDF

from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.toc_detector import apply_toc_filter
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter

# PyMuPDF span flags
_RE_STRUCTURAL_HEADER = re.compile(r"^제\s*\d+\s*[장절]")
_TITLE_FRAGMENTS = frozenset(
    {"총칙", "일반사항", "정의", "적용", "범위", "목적", "용어"}
)
_TEXT_FONT_BOLD = getattr(fitz, "TEXT_FONT_BOLD", 16)


def extract_raw(
    pdf_path: str | Path,
    *,
    doc_id: str = "",
    after_toc: bool = True,
    exclude_header_footer: bool = True,
    header_footer_margin_ratio: float = 0.08,
    table_caption_only: bool = True,
    figure_caption_only: bool = True,
    exclude_equation: bool = True,
    y_tolerance: float = 2.0,
    hyphen_merge: bool = False,
    paragraph_merge: bool = True,
    max_pages: int | None = None,
    new_section_pattern: re.Pattern[str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    **kwargs: Any,
) -> list[dict]:
    """
    PDF에서 블록 단위 Raw JSONL을 생성한다.

    기존 extract_pymupdf + line_rebuild + normalize + toc_detector +
    table_figure_filter + equation_filter 로직을 통합하여 Raw 스펙으로 반환.

    Args:
        pdf_path: PDF 파일 경로
        doc_id: 문서 식별자 (미입력 시 파일명 기반 생성)
        after_toc: True면 차례 구간 이후부터만 반환
        exclude_header_footer: True면 머릿말/꼬리말 영역 제외
        header_footer_margin_ratio: 상·하단 제외 비율 (기본 8%)
        table_caption_only: True면 표 제목만, 본문 제외
        figure_caption_only: True면 그림 제목만, 본문 제외
        exclude_equation: True면 수식 블록 제외
        y_tolerance: 같은 줄 y 병합 허용 거리
        hyphen_merge: 하이픈 줄바꿈 병합
        paragraph_merge: 문단 연속 병합
        max_pages: 지정 시 해당 페이지까지만 추출 (Dry-run용)
        new_section_pattern: doc_type별 섹션 구분 패턴 (매퍼.get_section_pattern())
        progress_callback: (current_page, total_pages) 호출

    Returns:
        Raw 블록 리스트. 각 블록: doc_id, source_type, block_id, block_type,
        page, text, bbox, style (font_size, bold, indent)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        return []

    if not doc_id:
        doc_id = pdf_path.stem.replace(" ", "_")

    # 1. 라인 추출 (font_size 포함)
    lines = _extract_lines_with_style(
        pdf_path,
        exclude_header_footer=exclude_header_footer,
        header_footer_margin_ratio=header_footer_margin_ratio,
        max_pages=max_pages,
        progress_callback=progress_callback,
    )

    # 2. TOC 필터
    if after_toc and lines:
        lines = apply_toc_filter(lines, after_toc=True)

    # 3. Rebuild (y-merge, header merge, paragraph merge 등)
    lines = rebuild_lines(
        lines,
        y_tolerance=y_tolerance,
        hyphen_merge=hyphen_merge,
        paragraph_merge=paragraph_merge,
        new_section_pattern=new_section_pattern,
    )

    # 4. Normalize
    lines = normalize_lines(lines)

    # 5. 표/그림 필터
    lines = apply_table_figure_filter(
        lines,
        table_caption_only=table_caption_only,
        figure_caption_only=figure_caption_only,
    )

    # 6. 수식 필터
    lines = apply_equation_filter(lines, exclude_equation=exclude_equation)

    # 7. Raw 블록 형식으로 변환
    blocks: list[dict] = []
    for block_id, line in enumerate(lines, start=1):
        block = _line_to_raw_block(line, doc_id=doc_id, block_id=block_id)
        blocks.append(block)

    return blocks


def _extract_lines_with_style(
    pdf_path: Path,
    *,
    exclude_header_footer: bool = True,
    header_footer_margin_ratio: float = 0.08,
    max_pages: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """PDF에서 라인 추출 (text, bbox, page, line_no, segments 포함 font_size)."""
    lines_out: list[dict] = []
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    end_page = min(max_pages, total_pages) if max_pages is not None else total_pages

    try:
        for page_index in range(end_page):
            page = doc[page_index]
            page_no = page_index + 1

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
                    max_size = 0.0
                    any_bold = False
                    for span in line.get("spans") or []:
                        s_text = span.get("text", "")
                        parts.append(s_text)
                        flags = span.get("flags", 0)
                        font = span.get("font", "") or ""
                        size = float(span.get("size", 0) or 0)
                        if size > max_size:
                            max_size = size
                        is_bold = bool(
                            (flags & _TEXT_FONT_BOLD)
                            or "bold" in font.lower()
                            or "Bold" in font
                        )
                        if is_bold:
                            any_bold = True
                        segments.append({
                            "text": s_text,
                            "bold": is_bold,
                            "size": size,
                        })
                    text = "".join(parts).strip()
                    if not text:
                        continue
                    bbox = list(line["bbox"])
                    if exclude_header_footer:
                        if not _RE_STRUCTURAL_HEADER.search(text):
                            if text.strip() not in _TITLE_FRAGMENTS:
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
                        "_font_size": max_size if max_size > 0 else 10.0,
                        "_bold": any_bold,
                        "_indent": bbox[0] if bbox else 0.0,
                    })
    finally:
        doc.close()

    return lines_out


def _line_to_raw_block(line: dict, *, doc_id: str, block_id: int) -> dict:
    """라인 dict를 Raw JSONL 블록 형식으로 변환."""
    block_type = line.get("block_type", "text")
    bbox = line.get("bbox", [0, 0, 0, 0])
    segments = line.get("segments") or []

    # style: segments에서 파생 (rebuild 시 _font_size 등이 유실될 수 있음)
    font_sizes = [float(s.get("size") or 0) for s in segments if s.get("size")]
    font_size = max(font_sizes, default=10.0) or 10.0
    bold = any(bool(s.get("bold")) for s in segments)
    indent = float(bbox[0]) if len(bbox) >= 4 else 0.0

    return {
        "doc_id": doc_id,
        "source_type": "pdf",
        "block_id": block_id,
        "block_type": block_type,
        "page": line.get("page", 0),
        "text": line.get("text", ""),
        "bbox": [float(x) for x in bbox],
        "style": {
            "font_size": font_size,
            "bold": bold,
            "indent": indent,
        },
    }
