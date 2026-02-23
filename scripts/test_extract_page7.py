"""물리 7페이지(첫 본문) 추출 테스트 — 제 1 장 총칙, 제 1 절 일반사항, 101. 적용 포함 여부 확인.

실행: python scripts/test_extract_page7.py
(PDF는 data/ 폴더 또는 프로젝트 루트에 두세요.)
V3: extract_pdf_raw + rule_marine_regulation 사용.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pdf_raw import extract_raw
from src.core.rule_marine_regulation import map_to_canonical


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

    # V3: Raw 추출
    raw_blocks = extract_raw(
        pdf_path,
        doc_id="MOUS_RULE_2024",
        after_toc=True,
        exclude_header_footer=True,
        table_caption_only=True,
        figure_caption_only=True,
        exclude_equation=True,
    )
    print(f"1. Raw 추출: {len(raw_blocks)} blocks")

    # Canonical 변환
    source_meta = {"file_name": pdf_path.name}
    canonical = map_to_canonical(raw_blocks, source_meta)
    print(f"2. Canonical 변환: {len(canonical)} records")
    print()

    # page 7 레코드만 필터
    page7 = [r for r in canonical if r.location and r.location.physical_page == 7]
    print(f"물리 7페이지 레코드 수: {len(page7)}")
    print()

    # 상위 20개 출력
    to_show = page7[:20] if page7 else canonical[:20]
    print("--- 물리 7페이지 상위 레코드 ---")
    for i, rec in enumerate(to_show):
        struct_str = " > ".join(s.label for s in rec.structure) if rec.structure else "(없음)"
        text_preview = (rec.content.text or "")[:60].replace("\n", " ")
        if len(rec.content.text or "") > 60:
            text_preview += "..."
        page_no = rec.location.physical_page if rec.location else "?"
        print(f"[{i+1}] page={page_no}")
        print(f"    structure: {struct_str}")
        print(f"    text: {text_preview}")
        print()

    # 검증: 제 1 장 총칙, 제 1 절 일반사항, 101. 적용 포함 여부
    texts = [r.content.text or "" for r in page7]
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
