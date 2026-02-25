"""PDF를 페이지별 JPG로 변환하여 storage/pdf_images/{doc_id}/ 에 저장 (Phase 5)."""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.pdf_to_images import export_pdf_to_images

OUTPUT_DIR = ROOT / "storage" / "pdf_images"


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/export_pdf_images.py <pdf_path> <doc_id>")
        print("Example: python scripts/export_pdf_images.py data/이동식_해양구조물_규칙_2024-7-92.pdf 이동식_해양구조물_규칙_2024-7-92")
        sys.exit(1)
    pdf_path = Path(sys.argv[1])
    doc_id = sys.argv[2]
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path
    out = export_pdf_to_images(
        pdf_path,
        doc_id,
        OUTPUT_DIR,
        progress_callback=lambda cur, total: print(f"  page {cur}/{total}"),
    )
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
