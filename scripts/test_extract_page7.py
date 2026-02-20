"""물리 7페이지(첫 본문) 추출 테스트 — 제 1 장 총칙, 제 1 절 일반사항, 101. 적용 포함 여부 확인.

실행: python scripts/test_extract_page7.py
(PDF는 data/ 폴더 또는 프로젝트 루트에 두세요.)
"""

import sys
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pymupdf import extract_lines
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.parse_state_machine import parse_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter
from src.core.export_jsonl import merge_paragraphs, build_record


def main() -> None:
    data_dir = ROOT / "data"
    pdf_candidates = list(data_dir.glob("*.pdf")) if data_dir.exists() else []
    if not pdf_candidates:
        pdf_path = ROOT / "이동식 해양구조물 규칙_2024.pdf"
        if not pdf_path.exists():
            print("PDF 파일을 찾을 수 없습니다. data/ 폴더 또는 프로젝트 루트에 PDF를 넣어주세요.")
            return
    else:
        pdf_path = pdf_candidates[0]

    print(f"PDF: {pdf_path.name}")
    print("=" * 60)

    # 1. Extract (after_toc=True, exclude_header_footer=True)
    raw = extract_lines(
        pdf_path,
        after_toc=True,
        exclude_header_footer=True,
    )
    print(f"1. Extract (raw): {len(raw)} lines")

    # 2. Rebuild
    rebuilt = rebuild_lines(raw, y_tolerance=2.0, hyphen_merge=False)
    print(f"2. Rebuild: {len(rebuilt)} lines")

    # 3. Normalize
    lines = normalize_lines(rebuilt)
    print(f"3. Normalize: {len(lines)} lines")

    # 4. Filters
    lines = apply_table_figure_filter(
        lines, table_caption_only=True, figure_caption_only=True
    )
    lines = apply_equation_filter(lines, exclude_equation=True)
    print(f"4. After filters: {len(lines)} lines")

    # 5. Parse
    parsed = parse_lines(lines)
    print(f"5. Parse: {len(parsed)} lines")

    # 6. Merge paragraphs (Export와 동일)
    merged = merge_paragraphs(parsed)
    print(f"6. Merge paragraphs: {len(merged)} records")
    print()

    # 첫 본문 페이지 = content_start
    content_start = parsed[0].get("page") if parsed else None
    print(f"Content start (첫 본문 PDF 페이지): {content_start}")
    print()

    # page 7 (물리) 레코드만 필터
    page7 = [m for m in merged if m.get("page") == 7]
    print(f"물리 7페이지 레코드 수: {len(page7)}")
    print()

    # 상위 20개 출력
    to_show = page7[:20] if page7 else merged[:20]
    print("--- 물리 7페이지 상위 레코드 (text, path.chapter, path.section, path.article) ---")
    for i, rec in enumerate(to_show):
        path = rec.get("path") or {}
        text_preview = (rec.get("text") or "")[:60].replace("\n", " ")
        if len(rec.get("text") or "") > 60:
            text_preview += "..."
        print(f"[{i+1}] page={rec.get('page')} line_no={rec.get('line_no')}")
        print(f"    path: ch={path.get('chapter')} sec={path.get('section')} art={path.get('article')} para={path.get('paragraph')}")
        print(f"    text: {text_preview}")
        print()

    # 검증: 제 1 장 총칙, 제 1 절 일반사항, 101. 적용 포함 여부
    texts = [r.get("text", "") for r in page7]
    has_chapter = any("제 1 장" in t or "제1장" in t for t in texts)
    has_chapter_total = any("총칙" in t for t in texts)
    has_section = any("제 1 절" in t or "제1절" in t for t in texts)
    has_section_common = any("일반사항" in t for t in texts)
    has_101 = any("101." in t or "101 " in t for t in texts)

    print("--- 검증 결과 ---")
    print(f"  '제 1 장' 포함: {has_chapter}")
    print(f"  '총칙' 포함: {has_chapter_total}")
    print(f"  '제 1 절' 포함: {has_section}")
    print(f"  '일반사항' 포함: {has_section_common}")
    print(f"  '101.' 포함: {has_101}")
    ok = has_chapter and has_section and has_101
    print(f"  => 추출 적절: {'OK' if ok else 'NG (누락 있음)'}")


if __name__ == "__main__":
    main()
