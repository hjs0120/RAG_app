"""Phase 3 수동 검증 — rule_marine_regulation map_to_canonical.

실행: python scripts/test_rule_marine_phase3.py

검증 항목:
1. map_to_canonical(raw_blocks, source_meta) 실행
2. CanonicalRecord.structure에 chapter/section/article/paragraph 계층 확인
3. canonical_validator.validate() 통과
4. citation_formatter.format_citation() 출력 형태 확인
5. V2 parse_state_machine 결과와 구조 비교
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pdf_raw import extract_raw
from src.core.rule_marine_regulation import map_to_canonical
from src.core.canonical_validator import validate as canonical_validate
from src.core.parse_state_machine import parse_lines
from src.core.extract_pymupdf import extract_lines
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "citation_formatter",
    ROOT / "src" / "rag" / "citation_formatter.py",
)
_cf_mod = importlib.util.module_from_spec(_spec)
_cf_mod.__package__ = "src.rag"
sys.modules["src.rag.citation_formatter"] = _cf_mod
_spec.loader.exec_module(_cf_mod)
format_citation = _cf_mod.format_citation


def main() -> None:
    # 테스트 데이터: phase_v3.md 명시 — data/이동식 해양구조물 규칙_2024-7-92.pdf
    pdf_path = ROOT / "data" / "이동식 해양구조물 규칙_2024-7-92.pdf"
    if not pdf_path.exists():
        print(f"테스트 데이터를 찾을 수 없습니다: {pdf_path}")
        return

    print("=" * 60)
    print("Phase 3 수동 검증: rule_marine_regulation map_to_canonical")
    print("=" * 60)

    # 1. Raw 블록 추출
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
    print(f"  Raw 블록: {len(raw_blocks)}, Canonical 레코드: {len(canonical_records)}")

    if not canonical_records:
        print("  [FAIL] Canonical 레코드가 없습니다.")
        return

    # 2. structure 계층 확인
    print("\n[2] structure 계층 확인 (상위 5개)")
    for i, rec in enumerate(canonical_records[:5]):
        struct_str = " > ".join(f"{s.type}={s.label}" for s in rec.structure) or "(none)"
        print(f"  [{i+1}] {rec.content.text[:40]}...")
        print(f"      structure: {struct_str}")

    # 3. canonical_validator 검증
    print("\n[3] canonical_validator.validate()")
    errors = canonical_validate(canonical_records)
    if errors:
        for idx, msg in errors[:5]:
            print(f"  [FAIL] 레코드 {idx}: {msg}")
        return
    print("  [OK] 모든 레코드 검증 통과")

    # 4. citation_formatter 출력
    print("\n[4] citation_formatter.format_citation() 샘플")
    sample_records = [r for r in canonical_records if len(r.structure) >= 3][:3]
    for i, rec in enumerate(sample_records or canonical_records[:3]):
        cite = format_citation(rec)
        print(f"  [{i+1}] {cite}")

    expected_style = "p.7" in (format_citation(canonical_records[2]) if len(canonical_records) > 2 else "")
    if sample_records and ">" in format_citation(sample_records[0]):
        print("  [OK] 'p.N, 제 X 장 > ...' 형태 확인")
    else:
        print("  [INFO] citation 형태 확인")

    # 5. V2 parse_state_machine과 구조 비교
    print("\n[5] V2 parse_state_machine 결과와 비교")
    v2_raw = extract_lines(pdf_path, after_toc=True, exclude_header_footer=True)
    v2_rebuilt = rebuild_lines(v2_raw, y_tolerance=2.0, hyphen_merge=False)
    v2_norm = normalize_lines(v2_rebuilt)
    v2_filtered = apply_table_figure_filter(v2_norm, table_caption_only=True, figure_caption_only=True)
    v2_filtered = apply_equation_filter(v2_filtered, exclude_equation=True)
    v2_parsed = parse_lines(v2_filtered)

    v2_chapters = set()
    v2_articles = set()
    for r in v2_parsed[:200]:
        p = r.get("path") or {}
        if p.get("chapter"):
            v2_chapters.add(p["chapter"])
        if p.get("article"):
            v2_articles.add(p["article"])

    canon_chapters = set()
    canon_articles = set()
    for r in canonical_records[:200]:
        for s in r.structure:
            if s.type == "chapter":
                canon_chapters.add(s.label)
            if s.type == "article":
                canon_articles.add(s.label)

    print(f"  V2 chapter 수: {len(v2_chapters)}, Canonical: {len(canon_chapters)}")
    print(f"  V2 article 수: {len(v2_articles)}, Canonical: {len(canon_articles)}")
    overlap_ch = len(v2_chapters & canon_chapters)
    overlap_art = len(v2_articles & canon_articles)
    print(f"  chapter 공통: {overlap_ch}, article 공통: {overlap_art}")
    if overlap_ch >= len(v2_chapters) * 0.8 and overlap_art >= len(v2_articles) * 0.8:
        print("  [OK] V2와 구조 대략 일치")
    else:
        print("  [INFO] 형식 차이로 일부 불일치 가능 (제 101조 vs 101 등)")

    print("\n" + "=" * 60)
    print("Phase 3 수동 검증 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
