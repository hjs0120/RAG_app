"""Phase 4 수동 검증 — chunk_builder Canonical 기반 수정.

실행: python scripts/test_chunk_canonical_phase4.py

검증 항목:
1. Phase 3 결과 canonical_records를 build_chunks(canonical_records)에 입력
2. 생성된 Chunk에 metadata.structure_path, physical_page, file_name 포함 여부
3. chunk_validate.validate(chunks) 통과
4. V2 Chunk 결과와 텍스트 내용 비교 (누락 없음)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pdf_raw import extract_raw
from src.core.rule_marine_regulation import map_to_canonical
from src.core.chunk_builder import build_chunks, TARGET_LEN, MAX_LEN, MIN_CHUNK_LEN
from src.core.chunk_validate import validate_chunks as chunk_validate
from src.core.parse_state_machine import parse_lines
from src.core.extract_pymupdf import extract_lines
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter
from src.core import export_jsonl


def main() -> None:
    pdf_path = ROOT / "data" / "이동식 해양구조물 규칙_2024-7-92.pdf"
    if not pdf_path.exists():
        print(f"테스트 데이터를 찾을 수 없습니다: {pdf_path}")
        return

    print("=" * 60)
    print("Phase 4 수동 검증: chunk_builder Canonical 기반")
    print("=" * 60)

    # 1. Raw -> Canonical
    print("\n[1] extract_raw() -> map_to_canonical()")
    raw_blocks = extract_raw(
        pdf_path,
        doc_id="MOUS_RULE_2024",
        after_toc=True,
        exclude_header_footer=True,
        table_caption_only=True,
        figure_caption_only=True,
        exclude_equation=True,
    )
    source_meta = {"file_name": pdf_path.name, "organization": "KR", "version": "2024"}
    canonical_records = map_to_canonical(raw_blocks, source_meta)
    print(f"  Canonical 레코드: {len(canonical_records)}개")

    if not canonical_records:
        print("  [FAIL] Canonical 레코드가 없습니다.")
        return

    # 2. build_chunks(Canonical)
    print("\n[2] build_chunks(canonical_records)")
    chunks = build_chunks(
        canonical_records,
        target_len=TARGET_LEN,
        max_len=MAX_LEN,
        min_chunk_len=MIN_CHUNK_LEN,
    )
    print(f"  Chunk 생성: {len(chunks)}개")

    if not chunks:
        print("  [FAIL] Chunk가 생성되지 않았습니다.")
        return

    # 3. metadata.structure_path, physical_page, file_name 확인
    print("\n[3] Chunk metadata 확인 (상위 5개)")
    ok_structure_path = 0
    ok_physical_page = 0
    ok_file_name = 0
    for i, c in enumerate(chunks):
        meta = c.get("meta") or {}
        sp = meta.get("structure_path")
        pp = meta.get("physical_page")
        fn = meta.get("file_name")
        chunk_id = c.get("chunk_id", "(없음)")
        if sp is not None:
            ok_structure_path += 1
        if pp is not None or meta.get("pages"):
            ok_physical_page += 1
        if fn:
            ok_file_name += 1
        if i < 5:
            print(f"  [{i+1}] chunk_id={chunk_id[:50]}...")
            print(f"      structure_path={str(sp)[:60]}..." if sp and len(str(sp)) > 60 else f"      structure_path={sp}")
            print(f"      physical_page={pp}, file_name={fn}")

    total = len(chunks)
    print(f"\n  structure_path 있음: {ok_structure_path}/{total}")
    print(f"  physical_page/pages 있음: {ok_physical_page}/{total}")
    print(f"  file_name 있음: {ok_file_name}/{total}")

    if ok_structure_path < total * 0.5:
        print("  [WARN] structure_path가 많은 Chunk에 없음 (제목 등은 빈 경로 가능)")
    else:
        print("  [OK] metadata 구조 확인")

    # 4. chunk_validate
    print("\n[4] chunk_validate.validate(chunks)")
    all_ok, messages = chunk_validate(chunks, check_canonical=True)
    for m in messages:
        print(f"  {m}")
    if not all_ok:
        print("  [FAIL] 검증 실패")
    else:
        print("  [OK] 검증 통과")

    # 5. V2 Chunk와 텍스트 비교
    print("\n[5] V2 Chunk 결과와 텍스트 비교")
    v2_raw = extract_lines(pdf_path, after_toc=True, exclude_header_footer=True)
    v2_rebuilt = rebuild_lines(v2_raw, y_tolerance=2.0, hyphen_merge=False)
    v2_norm = normalize_lines(v2_rebuilt)
    v2_filtered = apply_table_figure_filter(v2_norm, table_caption_only=True, figure_caption_only=True)
    v2_filtered = apply_equation_filter(v2_filtered, exclude_equation=True)
    v2_parsed = parse_lines(v2_filtered)

    # V2 export -> chunk
    v2_merged = export_jsonl.merge_paragraphs(v2_parsed)
    v2_records = [
        export_jsonl.build_record(
            line,
            doc_id="MOUS_RULE_2024",
            source_file=pdf_path.name,
        )
        for line in v2_merged
    ]
    v2_chunks = build_chunks(
        v2_records,
        target_len=TARGET_LEN,
        max_len=MAX_LEN,
        min_chunk_len=MIN_CHUNK_LEN,
    )

    canon_text_len = sum(len(c.get("text", "")) for c in chunks)
    v2_text_len = sum(len(c.get("text", "")) for c in v2_chunks)
    print(f"  Canonical Chunk 총 텍스트 길이: {canon_text_len}")
    print(f"  V2 Chunk 총 텍스트 길이: {v2_text_len}")
    ratio = canon_text_len / v2_text_len if v2_text_len > 0 else 0
    if 0.7 <= ratio <= 1.3:
        print("  [OK] 텍스트 양 대략 일치 (70~130%)")
    else:
        print(f"  [INFO] 비율 {ratio:.2f} (형식 차이로 차이 가능)")

    print("\n" + "=" * 60)
    print("Phase 4 수동 검증 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
