"""Phase 2 수동 검증 — extract_pdf_raw, raw_validator.

실행: python scripts/test_extract_pdf_raw_phase2.py

검증 항목:
1. extract_raw() 실행 -> bbox, style.font_size, block_id 포함
2. after_toc 옵션 동작 확인
3. raw_validator.validate() 통과
4. (V2 extract_pymupdf는 Phase 6에서 삭제됨 — 비교 생략)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pdf_raw import extract_raw
from src.core.raw_validator import validate as raw_validate


def main() -> None:
    # 테스트 데이터: phase_v3.md 명시 — data/이동식 해양구조물 규칙_2024-7-92.pdf
    pdf_path = ROOT / "data" / "이동식 해양구조물 규칙_2024-7-92.pdf"
    if not pdf_path.exists():
        print(f"테스트 데이터를 찾을 수 없습니다: {pdf_path}")
        return

    print("=" * 60)
    print("Phase 2 수동 검증: extract_pdf_raw, raw_validator")
    print("=" * 60)

    # 1. extract_raw 실행
    print("\n[1] extract_raw() 실행")
    blocks = extract_raw(
        pdf_path,
        doc_id="MOUS_RULE_2024",
        after_toc=True,
        exclude_header_footer=True,
        table_caption_only=True,
        figure_caption_only=True,
        exclude_equation=True,
    )
    print(f"  블록 수: {len(blocks)}")

    if not blocks:
        print("  [FAIL] 블록이 없습니다.")
        return

    # 2. bbox, style.font_size, block_id 포함 확인
    print("\n[2] bbox, style.font_size, block_id 포함 확인")
    sample = blocks[0]
    has_bbox = "bbox" in sample and len(sample.get("bbox", [])) >= 4
    has_style = "style" in sample
    has_font_size = has_style and "font_size" in sample.get("style", {})
    has_block_id = "block_id" in sample
    if has_bbox and has_font_size and has_block_id:
        print(f"  [OK] bbox={sample['bbox'][:4]}..., style.font_size={sample['style']['font_size']}, block_id={sample['block_id']}")
    else:
        print(f"  [FAIL] bbox={has_bbox}, font_size={has_font_size}, block_id={has_block_id}")

    # 3. raw_validator 검증
    print("\n[3] raw_validator.validate(blocks)")
    errors = raw_validate(blocks)
    if errors:
        for idx, msg in errors[:5]:
            print(f"  [FAIL] 블록 {idx}: {msg}")
        if len(errors) > 5:
            print(f"  ... 외 {len(errors)-5}건")
        return
    print("  [OK] 모든 블록 검증 통과")

    # 4. after_toc 옵션 확인 (첫 블록이 "제 1 장" 근처인지)
    print("\n[4] after_toc 옵션 동작 확인")
    first_text = blocks[0].get("text", "")
    has_chapter = "제" in first_text and ("장" in first_text or "절" in first_text)
    if has_chapter or "총칙" in first_text or "일반사항" in first_text:
        print(f"  [OK] 첫 블록: {first_text[:50]}...")
    else:
        print(f"  [INFO] 첫 블록: {first_text[:80]}...")
        # after_toc=False로 비교
        blocks_no_toc = extract_raw(pdf_path, doc_id="MOUS_RULE_2024", after_toc=False)
        print(f"  after_toc=False 시 블록 수: {len(blocks_no_toc)} (비교용)")

    # 5. (V2 비교 생략 — extract_pymupdf는 Phase 6에서 삭제됨)
    print("\n[5] 텍스트 통계")
    raw_texts = [b.get("text", "").strip() for b in blocks if b.get("text")]
    print(f"  Raw 텍스트 블록 수: {len(raw_texts)}")

    # 샘플 블록 출력
    print("\n--- 상위 5개 Raw 블록 샘플 ---")
    for i, b in enumerate(blocks[:5]):
        print(f"[{i+1}] block_id={b['block_id']} page={b['page']} block_type={b['block_type']}")
        print(f"    text: {(b.get('text') or '')[:60]}...")
        print(f"    bbox: {b.get('bbox', [])[:4]}, style: {b.get('style', {})}")

    print("\n" + "=" * 60)
    print("Phase 2 수동 검증 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
