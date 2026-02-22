"""물리 7페이지 파이프라인 디버그 — 제 1 장 총칙, 제 1 절 일반사항 추적."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pymupdf import extract_lines
from src.core.toc_detector import detect_toc_start, apply_toc_filter
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter
from src.core.parse_state_machine import parse_lines


def _find(lines, keywords, label):
    hits = []
    for i, ln in enumerate(lines):
        t = ln.get("text", "")
        for k in keywords:
            if k in t:
                hits.append((i, ln.get("page"), t[:70]))
                break
    print(f"  [{label}] {len(hits)} lines")
    for i, p, t in hits[:10]:
        print(f"    [{i}] p{p}: {t}")
    return hits


def main():
    data_dir = ROOT / "data"
    pdf_candidates = list(data_dir.glob("*.pdf")) if data_dir.exists() else []
    pdf_path = pdf_candidates[0] if pdf_candidates else ROOT / "이동식 해양구조물 규칙_2024.pdf"
    if not pdf_path.exists():
        print("PDF 없음")
        return

    raw = extract_lines(pdf_path, after_toc=False, exclude_header_footer=True)
    _, body_start = detect_toc_start(raw)
    print(f"TOC body_start index: {body_start} (total raw: {len(raw)})")

    kw = ["제 1 장", "총칙", "제 1 절", "일반사항", "101."]
    print("\n--- Raw (before TOC) ---")
    _find(raw, kw, "raw")

    after_toc = apply_toc_filter(raw, after_toc=True)
    print("\n--- After TOC ---")
    _find(after_toc, kw, "after_toc")
    if after_toc:
        print("  First 5 lines:")
        for i, ln in enumerate(after_toc[:5]):
            print(f"    [{i}] p{ln.get('page')} {ln.get('text','')[:60]}")

    rebuilt = rebuild_lines(after_toc, y_tolerance=2.0, hyphen_merge=False)
    print("\n--- After Rebuild ---")
    _find(rebuilt, kw, "rebuilt")

    norm = normalize_lines(rebuilt)
    print("\n--- After Normalize ---")
    _find(norm, kw, "normalize")

    filt = apply_table_figure_filter(norm, table_caption_only=True, figure_caption_only=True)
    filt = apply_equation_filter(filt, exclude_equation=True)
    print("\n--- After table/equation filters ---")
    _find(filt, kw, "filters")

    parsed = parse_lines(filt)
    page7 = [p for p in parsed if p.get("page") == 7]
    print(f"\n--- Page 7 parsed: {len(page7)} lines ---")
    for i, ln in enumerate(page7[:15]):
        t = ln.get("text", "")[:50]
        ch = (ln.get("path") or {}).get("chapter")
        print(f"  [{i}] {ch} | {t}")


if __name__ == "__main__":
    main()
