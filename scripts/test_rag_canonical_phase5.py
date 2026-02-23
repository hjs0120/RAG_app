"""Phase 5 수동 검증 — FAISS 연동 및 RAG 출처 표기 개선.

실행: python scripts/test_rag_canonical_phase5.py

검증 항목:
1. Canonical Chunk로 build_index_from_chunks() 실행 → rules.index, rules_meta.jsonl 생성
2. meta_list에 structure_path, physical_page 포함 확인
3. citation_formatter.format_citation_from_meta 출력 확인
4. rag_pipeline._format_source 출처 문자열 확인
5. V2 인덱스 로드 하위 호환 확인 (기존 rules.index가 있으면)

faiss 미설치 시: format_citation_from_meta만 검증 (faiss 의존 없이)
"""

import sys
import tempfile
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# faiss 없으면 src.rag 패키지 로드 시 실패 → citation_formatter만 직접 로드
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

from src.core.extract_pdf_raw import extract_raw
from src.core.rule_marine_regulation import map_to_canonical
from src.core.chunk_builder import build_chunks, TARGET_LEN, MAX_LEN, MIN_CHUNK_LEN

if HAS_FAISS:
    from src.rag.citation_formatter import format_citation_from_meta
    from src.core.faiss_index import build_index_from_chunks, load_index
    from src.rag.rag_pipeline import _format_source
else:
    _spec = importlib.util.spec_from_file_location(
        "citation_formatter",
        ROOT / "src" / "rag" / "citation_formatter.py",
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    format_citation_from_meta = _mod.format_citation_from_meta


def main() -> None:
    pdf_path = ROOT / "data" / "이동식 해양구조물 규칙_2024-7-92.pdf"
    if not pdf_path.exists():
        print(f"테스트 데이터를 찾을 수 없습니다: {pdf_path}")
        return

    print("=" * 60)
    print("Phase 5 수동 검증: FAISS 연동 및 RAG 출처 표기")
    print("=" * 60)

    # 1. Raw -> Canonical -> Chunk
    print("\n[1] Raw -> Canonical -> Chunk 생성")
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
    chunks = build_chunks(
        canonical_records,
        target_len=TARGET_LEN,
        max_len=MAX_LEN,
        min_chunk_len=MIN_CHUNK_LEN,
    )
    print(f"  Chunk: {len(chunks)}개")

    # 2. build_index_from_chunks (faiss 필요)
    print("\n[2] build_index_from_chunks() 실행")
    if not HAS_FAISS:
        print("  [SKIP] faiss 미설치 - pip install faiss-cpu")
        print("\n[3] format_citation_from_meta 샘플 (Chunk meta로 시뮬레이션)")
        for i, c in enumerate(chunks[:5]):
            meta_sim = {
                "doc_id": c.get("doc_id"),
                "page": (c.get("meta") or {}).get("physical_page"),
                "meta": c.get("meta") or {},
            }
            cite = format_citation_from_meta(meta_sim)
            src = f"[{i+1}] {meta_sim.get('doc_id', '')}, {cite}"
            print(f"  citation: {cite[:60]}...")
            print(f"  source:   {src[:70]}...")
        print("\n" + "=" * 60)
        print("Phase 5 수동 검증 완료 (faiss 없음)")
        print("=" * 60)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        idx_path, meta_path = build_index_from_chunks(
            chunks,
            output_dir=tmpdir,
            stem="rules",
        )
        print(f"  index: {idx_path}")
        print(f"  meta:  {meta_path}")

        # meta_list 로드
        _, meta_list = load_index(idx_path, meta_path, use_gpu=False)
        print(f"  meta_list: {len(meta_list)}개")

        # structure_path, physical_page 포함 확인
        has_structure = sum(1 for m in meta_list if (m.get("meta") or {}).get("structure_path"))
        has_page = sum(1 for m in meta_list if m.get("page") is not None)
        print(f"  structure_path 있음: {has_structure}/{len(meta_list)}")
        print(f"  page 있음: {has_page}/{len(meta_list)}")

        if has_structure > 0 and has_page > 0:
            print("  [OK] Canonical Chunk 메타 저장 확인")
        else:
            print("  [WARN] structure_path 또는 page 일부 누락 (제목 등은 structure_path 빈 경우 있음)")

        # 3. format_citation_from_meta, _format_source 샘플
        print("\n[3] 출처 문자열 샘플")
        sample = [m for m in meta_list if (m.get("meta") or {}).get("structure_path")][:3]
        for i, m in enumerate(sample or meta_list[:3]):
            cite = format_citation_from_meta(m)
            src = _format_source(i + 1, m)
            print(f"  citation: {cite[:60]}...")
            print(f"  source:   {src[:70]}...")

        # 4. V2 인덱스 하위 호환
        print("\n[4] V2 인덱스 하위 호환")
        v2_index_path = ROOT / "output" / "rules.index"
        v2_meta_path = ROOT / "output" / "rules_meta.jsonl"
        if v2_index_path.exists():
            try:
                v2_index, v2_meta = load_index(v2_index_path, v2_meta_path, use_gpu=False)
                print(f"  V2 인덱스 로드: {v2_index.ntotal}개")
                print("  [OK] V2 인덱스 하위 호환")
            except Exception as e:
                print(f"  [WARN] V2 로드 실패: {e}")
        else:
            print("  [INFO] V2 인덱스 없음 (output/rules.index) — 스킵")

    print("\n" + "=" * 60)
    print("Phase 5 수동 검증 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
