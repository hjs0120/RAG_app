"""PDF 페이지를 이미지(JPG)로 변환 — 웹 뷰어용 (Phase 5)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

# DPI 150~200: 웹에서 글자 가독성
DEFAULT_DPI = 150
# JPG quality 80: 용량 절감, 텍스트 위주 문서 가독성 유지
DEFAULT_JPEG_QUALITY = 80


def _safe_doc_id_dir(doc_id: str) -> str:
    """디렉터리명으로 쓸 수 있도록 doc_id 정규화 (슬래시 등 제거)."""
    if not doc_id or not doc_id.strip():
        return "unknown"
    s = doc_id.strip()
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s or "unknown"


def export_pdf_to_images(
    pdf_path: str | Path,
    doc_id: str,
    output_dir: str | Path,
    *,
    dpi: int = DEFAULT_DPI,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """
    PDF 각 페이지를 JPG로 변환하여 output_dir/{doc_id}/1.jpg, 2.jpg, ... 로 저장.

    Args:
        pdf_path: PDF 파일 경로
        doc_id: 문서 식별자 (폴더명에 사용, 슬래시 등은 _로 치환)
        output_dir: 이미지 루트 디렉터리 (예: storage/pdf_images)
        dpi: 렌더 해상도 (기본 150)
        jpeg_quality: JPG 품질 1~100 (기본 80)
        progress_callback: (current_page_1based, total_pages) 호출

    Returns:
        저장된 디렉터리 경로 (output_dir / safe_doc_id)
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")

    safe_id = _safe_doc_id_dir(doc_id)
    out_sub = output_dir / safe_id
    out_sub.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    try:
        total = len(doc)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for page_no in range(total):
            page = doc[page_no]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_path = out_sub / f"{page_no + 1}.jpg"
            pix.save(str(img_path), jpg_quality=jpeg_quality)
            if progress_callback:
                progress_callback(page_no + 1, total)
    finally:
        doc.close()

    return out_sub
